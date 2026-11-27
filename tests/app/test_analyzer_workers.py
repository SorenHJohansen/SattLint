# pyright: reportUnknownLambdaType=false, reportPrivateUsage=false
"""Tests for the analyzer worker pool and its single-analyzer execution."""

from __future__ import annotations

import io
import multiprocessing
import os
import pickle
import signal
import sys
import threading
import time
from collections.abc import Callable, Generator
from multiprocessing.process import BaseProcess
from typing import Any, cast

import pytest

from sattlint.analyzers import dispatch as analysis_dispatch_module
from sattlint.analyzers.framework import AnalysisContext, AnalyzerSpec, Issue
from sattlint.application import analyzer_workers
from sattlint.cli.entry import build_cli_parser
from sattlint.config import DEFAULT_CONFIG
from sattlint.config.types import ConfigDict
from sattlint.core.timings import PhaseTiming
from sattlint.models.project_graph import ProjectGraph
from tests.helpers import AnalysisGraphStub, named_object


class ReportDouble:
    """A minimal analyzer report: a summary, issues, and optional phase timings."""

    def __init__(
        self,
        *,
        summary: str = "summary",
        issues: list[Issue] | None = None,
        phase_timings: list[PhaseTiming] | None = None,
    ) -> None:
        self.name = "Report"
        self.issues = [] if issues is None else issues
        self._summary = summary
        self.phase_timings = phase_timings

    def summary(self) -> str:
        return self._summary


def make_run(
    *,
    target_name: str = "TargetA",
    specs: dict[str, AnalyzerSpec] | None = None,
) -> analyzer_workers.AnalyzerRun:
    context = AnalysisContext(base_picture=cast(Any, named_object("TargetA")))
    return analyzer_workers.AnalyzerRun(
        cfg=cast(ConfigDict, DEFAULT_CONFIG.copy()),
        target_name=target_name,
        context=context,
        graph=cast(ProjectGraph, AnalysisGraphStub(unavailable_libraries=set())),
        report_cache=None,
        report_cache_key=lambda _project, _analyzer: "cache-key",
        specs={} if specs is None else specs,
    )


def make_spec(
    key: str,
    run: Callable[[AnalysisContext], object],
    *,
    name: str | None = None,
) -> AnalyzerSpec:
    return AnalyzerSpec(
        key=key,
        name=name or key.title(),
        description="",
        run=cast(Any, run),
    )


def test_resolve_job_count_keeps_a_single_analyzer_in_process() -> None:
    assert analyzer_workers.resolve_job_count(None, 0) == 1
    assert analyzer_workers.resolve_job_count(None, 1) == 1
    assert analyzer_workers.resolve_job_count(8, 1) == 1


def test_resolve_job_count_keeps_a_sequential_request_at_one_worker() -> None:
    assert analyzer_workers.resolve_job_count(1, 13) == 1


def test_cli_jobs_defaults_to_one_worker() -> None:
    args = build_cli_parser().parse_args(["analyze"])

    assert args.jobs == 1


def test_cli_jobs_zero_requests_the_automatic_count() -> None:
    args = build_cli_parser().parse_args(["analyze", "--jobs", "0"])

    assert args.jobs == 0


def test_cli_jobs_honors_an_explicit_positive_request() -> None:
    args = build_cli_parser().parse_args(["analyze", "--jobs", "4"])

    assert args.jobs == 4


def test_resolve_job_count_defaults_to_a_bounded_worker_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analyzer_workers.os, "process_cpu_count", lambda: 64)

    assert analyzer_workers.resolve_job_count(None, 13) == analyzer_workers.AUTO_JOB_LIMIT
    assert analyzer_workers.resolve_job_count(0, 13) == analyzer_workers.AUTO_JOB_LIMIT
    assert analyzer_workers.resolve_job_count(None, 2) == 2


def test_resolve_job_count_keeps_a_single_worker_on_a_single_cpu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analyzer_workers.os, "process_cpu_count", lambda: 1)

    assert analyzer_workers.resolve_job_count(None, 13) == 1


def test_resolve_job_count_honors_and_caps_an_explicit_request() -> None:
    assert analyzer_workers.resolve_job_count(3, 13) == 3
    assert analyzer_workers.resolve_job_count(9, 4) == 4


def test_resolve_job_count_rejects_a_negative_request() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        analyzer_workers.resolve_job_count(-1, 4)


def test_pooling_supported_follows_the_available_start_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(multiprocessing, "get_all_start_methods", lambda: ["spawn"])
    assert analyzer_workers.pooling_supported() is False

    monkeypatch.setattr(multiprocessing, "get_all_start_methods", lambda: ["fork", "spawn"])
    assert analyzer_workers.pooling_supported() is True


def test_analyze_job_normalizes_the_report_into_a_result_record() -> None:
    phase_timings = [PhaseTiming(phase="walk", duration_ms=12.5)]
    report = ReportDouble(
        summary="one issue",
        issues=[Issue(kind="unused", message="never read")],
        phase_timings=phase_timings,
    )
    run = make_run(specs={"first": make_spec("first", lambda _context: report, name="First")})

    job = analyzer_workers.analyze_job(run, "first")

    assert job.key == "first"
    assert job.cancelled is False
    assert job.output_lines == ()
    assert job.phase_timings_ms[0].phase == "walk"
    assert job.result.key == "first"
    assert job.result.name == "First"
    assert job.result.status == "completed"
    assert job.result.summary == "one issue"
    assert job.result.report_kind == "ReportDouble"
    assert job.result.issue_count == 1
    assert job.result.duration_ms is not None
    assert job.result.findings[0].kind == "unused"
    assert job.result.findings[0].module_path == ("TargetA",)


def test_analyze_job_runs_the_report_cache_and_passes_its_report_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def fake_cache(graph: object, *, run_fn: Callable[[], object], **kwargs: object) -> object:
        calls.append((str(getattr(graph, "analysis_cache_key", None)), cast(str, kwargs["analyzer_cache_key"])))
        return run_fn()

    monkeypatch.setattr(analyzer_workers.report_cache_module, "run_with_analysis_report_cache", fake_cache)
    run = make_run(specs={"first": make_spec("first", lambda _context: ReportDouble(summary="cached"))})

    job = analyzer_workers.analyze_job(run, "first")

    assert calls == [("None", "first")]
    assert job.result.summary == "cached"


def test_analyze_job_lets_the_analyzer_failure_escape() -> None:
    def explode(_context: AnalysisContext) -> object:
        raise RuntimeError("internal detail")

    run = make_run(specs={"first": make_spec("first", explode)})

    with pytest.raises(RuntimeError, match="internal detail"):
        analyzer_workers.analyze_job(run, "first")


def test_degraded_job_result_hides_the_exception_text_by_default() -> None:
    run = make_run(specs={"first": make_spec("first", lambda _context: ReportDouble(), name="First")})

    job = analyzer_workers.degraded_job_result(run, "first", RuntimeError("secret path"))

    assert job.key == "first"
    assert job.result.status == "failed"
    assert job.result.issue_count == 0
    assert job.result.summary == "First failed: RuntimeError"


def test_degraded_job_result_keeps_detail_in_debug_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = make_run(specs={"first": make_spec("first", lambda _context: ReportDouble(), name="First")})
    debug_cfg = cast(ConfigDict, {**DEFAULT_CONFIG.copy(), "debug": True})
    run = analyzer_workers.AnalyzerRun(
        cfg=debug_cfg,
        target_name=run.target_name,
        context=run.context,
        graph=run.graph,
        report_cache=None,
        report_cache_key=run.report_cache_key,
        specs=run.specs,
    )

    job = analyzer_workers.degraded_job_result(run, "first", RuntimeError("secret path"))

    assert job.result.summary == "First failed: secret path"


def test_worker_entry_captures_analyzer_output(monkeypatch: pytest.MonkeyPatch) -> None:
    run = make_run(specs={"first": make_spec("first", lambda _context: ReportDouble(summary="done"))})
    real_analyze_job = analyzer_workers.analyze_job

    def fake_analyze_job(_run: analyzer_workers.AnalyzerRun, key: str) -> analyzer_workers.AnalyzerJobResult:
        print("progress")
        sys.stderr.write("warning\n")
        return analyzer_workers.AnalyzerJobResult(
            key=key,
            result=real_analyze_job(_run, key).result,
        )

    monkeypatch.setattr(analyzer_workers, "analyze_job", fake_analyze_job)
    monkeypatch.setattr(analyzer_workers, "_worker_run", analyzer_workers._WorkerRun(run=run))

    (job,) = analyzer_workers._worker_entry(("first",))

    assert job.output_lines == ("progress", "warning")
    assert job.result.summary == "done"


def test_worker_entry_turns_a_raised_analyzer_into_a_failure_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = make_run(specs={"first": make_spec("first", lambda _context: ReportDouble(), name="First")})

    def explode(_run: analyzer_workers.AnalyzerRun, _key: str) -> analyzer_workers.AnalyzerJobResult:
        print("before the failure")
        raise RuntimeError("worker detail")

    monkeypatch.setattr(analyzer_workers, "analyze_job", explode)
    monkeypatch.setattr(analyzer_workers, "_worker_run", analyzer_workers._WorkerRun(run=run))

    (job,) = analyzer_workers._worker_entry(("first",))

    assert job.result.status == "failed"
    assert job.result.summary == "First failed: RuntimeError"
    assert job.output_lines == ("before the failure",)


def test_worker_entry_requires_a_prepared_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(analyzer_workers, "_worker_run", None)

    with pytest.raises(RuntimeError, match="without a prepared run"):
        analyzer_workers._worker_entry(("first",))


def test_captured_lines_splits_the_captured_stream() -> None:
    buffer = io.StringIO()
    buffer.write("one\ntwo\n")

    assert analyzer_workers._captured_lines(buffer) == ("one", "two")


pytestmark_pooled = pytest.mark.skipif(
    "fork" not in multiprocessing.get_all_start_methods(),
    reason="the worker pool needs the fork start method",
)


def _pooled_run(specs: dict[str, AnalyzerSpec]) -> analyzer_workers.AnalyzerRun:
    return make_run(target_name="TargetA", specs=specs)


def _block_the_worker(_context: AnalysisContext) -> object:
    """Hold a worker until the test kills it or the run shuts the pool down."""
    threading.Event().wait()
    return ReportDouble()


def _child_pids() -> frozenset[int]:
    return frozenset(child.pid for child in multiprocessing.active_children() if child.pid is not None)


def _new_children(existing: frozenset[int]) -> list[BaseProcess]:
    return [child for child in multiprocessing.active_children() if child.pid is not None and child.pid not in existing]


def _drain_within(
    pending: Generator[tuple[analyzer_workers.AnalyzerJobResult, ...]],
    *,
    timeout: float,
) -> list[tuple[analyzer_workers.AnalyzerJobResult, ...]]:
    groups: list[tuple[analyzer_workers.AnalyzerJobResult, ...]] = []
    failures: list[BaseException] = []

    def consume() -> None:
        try:
            groups.extend(pending)
        except BaseException as exc:  # noqa: BLE001 - re-raised on the test thread
            failures.append(exc)

    thread = threading.Thread(target=consume, daemon=True)
    thread.start()
    thread.join(timeout)
    assert not thread.is_alive(), "the pooled run did not finish before the deadline"
    if failures:
        raise failures[0]
    return groups


def _close_within(
    pending: Generator[tuple[analyzer_workers.AnalyzerJobResult, ...]],
    *,
    timeout: float,
) -> None:
    failures: list[BaseException] = []

    def close() -> None:
        try:
            pending.close()
        except BaseException as exc:  # noqa: BLE001 - re-raised on the test thread
            failures.append(exc)

    thread = threading.Thread(target=close, daemon=True)
    thread.start()
    thread.join(timeout)
    assert not thread.is_alive(), "closing the pooled run did not return before the deadline"
    if failures:
        raise failures[0]


@pytestmark_pooled
def test_run_jobs_pooled_returns_every_analyzer_result() -> None:
    specs = {
        key: make_spec(key, lambda _context, key=key: ReportDouble(summary=f"{key} done"))
        for key in ("first", "second", "third")
    }
    run = _pooled_run(specs)

    jobs = (("first",), ("second",), ("third",))
    results = [job for group in analyzer_workers.run_jobs_pooled(run, jobs, workers=2) for job in group]

    assert {job.key for job in results} == {"first", "second", "third"}
    assert all(job.result.status == "completed" for job in results)
    assert {job.result.summary for job in results} == {"first done", "second done", "third done"}


@pytestmark_pooled
def test_run_jobs_pooled_keeps_each_analyzers_output_with_its_result() -> None:
    def noisy(key: str) -> Callable[[AnalysisContext], object]:
        def run(_context: AnalysisContext) -> object:
            print(f"{key} says hello")
            return ReportDouble(summary=f"{key} done")

        return run

    specs = {key: make_spec(key, noisy(key)) for key in ("first", "second")}
    run = _pooled_run(specs)

    jobs = (("first",), ("second",))
    results = {job.key: job for group in analyzer_workers.run_jobs_pooled(run, jobs, workers=2) for job in group}

    assert results["first"].output_lines == ("first says hello",)
    assert results["second"].output_lines == ("second says hello",)


@pytestmark_pooled
def test_run_jobs_pooled_reports_a_failure_without_stopping_the_batch() -> None:
    def explode(_context: AnalysisContext) -> object:
        raise RuntimeError("boom")

    specs = {
        "first": make_spec("first", explode, name="First"),
        "second": make_spec("second", lambda _context: ReportDouble(summary="second done")),
    }
    run = _pooled_run(specs)

    jobs = (("first",), ("second",))
    results = {job.key: job for group in analyzer_workers.run_jobs_pooled(run, jobs, workers=2) for job in group}

    assert results["first"].result.status == "failed"
    assert results["first"].result.summary == "First failed: RuntimeError"
    assert results["second"].result.status == "completed"


@pytestmark_pooled
def test_run_jobs_pooled_fails_the_unreported_key_when_a_worker_is_killed() -> None:
    specs = {
        "first": make_spec("first", lambda _context: ReportDouble(summary="first done")),
        "second": make_spec("second", _block_the_worker, name="Second"),
    }
    run = _pooled_run(specs)
    existing = _child_pids()
    pending = analyzer_workers.run_jobs_pooled(run, (("first",), ("second",)), workers=2)

    (first,) = next(pending)
    workers = _new_children(existing)
    assert workers, "the pooled run started no worker process"
    for worker in workers:
        assert worker.pid is not None
        os.kill(worker.pid, signal.SIGKILL)

    started_at = time.monotonic()
    groups = _drain_within(pending, timeout=5.0)
    elapsed = time.monotonic() - started_at

    results = {job.key: job for group in groups for job in group}
    assert first.key == "first"
    assert elapsed < 5.0
    assert set(results) == {"second"}
    assert results["second"].result.status == "failed"
    assert results["second"].result.summary == "Analyzer worker stopped before completing Second."
    assert results["second"].result.issue_count == 0
    assert analyzer_workers._worker_run is None
    assert all(not worker.is_alive() for worker in workers)


@pytestmark_pooled
def test_run_jobs_pooled_fails_every_key_of_a_lost_group() -> None:
    specs = {
        "first": make_spec("first", lambda _context: ReportDouble(summary="first done")),
        "second": make_spec("second", _block_the_worker, name="Second"),
        "third": make_spec("third", lambda _context: ReportDouble(summary="third done"), name="Third"),
    }
    run = _pooled_run(specs)
    existing = _child_pids()
    pending = analyzer_workers.run_jobs_pooled(run, (("first",), ("second", "third")), workers=2)

    (first,) = next(pending)
    workers = _new_children(existing)
    assert workers, "the pooled run started no worker process"
    for worker in workers:
        assert worker.pid is not None
        os.kill(worker.pid, signal.SIGKILL)

    groups = _drain_within(pending, timeout=5.0)
    results = {job.key: job for group in groups for job in group}

    assert first.key == "first"
    assert set(results) == {"second", "third"}
    assert all(job.result.status == "failed" for job in results.values())
    assert {results["second"].result.summary, results["third"].result.summary} == {
        "Analyzer worker stopped before completing Second.",
        "Analyzer worker stopped before completing Third.",
    }
    assert all(job.result.issue_count == 0 for job in results.values())
    assert all(not worker.is_alive() for worker in workers)


@pytestmark_pooled
def test_run_jobs_pooled_terminates_the_workers_when_the_caller_stops_early() -> None:
    specs = {
        "first": make_spec("first", lambda _context: ReportDouble(summary="first done")),
        "second": make_spec("second", _block_the_worker),
    }
    run = _pooled_run(specs)
    existing = _child_pids()
    pending: Generator[tuple[analyzer_workers.AnalyzerJobResult, ...]] = analyzer_workers.run_jobs_pooled(
        run, (("first",), ("second",)), workers=2
    )

    (first,) = next(pending)
    workers = _new_children(existing)
    assert workers, "the pooled run started no worker process"

    started_at = time.monotonic()
    _close_within(pending, timeout=5.0)
    elapsed = time.monotonic() - started_at

    assert first.key == "first"
    assert elapsed < 5.0
    assert analyzer_workers._worker_run is None
    assert all(not worker.is_alive() for worker in workers)


def test_reports_are_plain_data_that_survives_a_process_boundary() -> None:
    """The pool sends results, never the graph or the context."""
    report = ReportDouble(issues=[Issue(kind="unused", message="never read")])
    run = make_run(specs={"first": make_spec("first", lambda _context: report)})

    job = analyzer_workers.analyze_job(run, "first")

    restored = cast(analyzer_workers.AnalyzerJobResult, pickle.loads(pickle.dumps(job)))

    assert restored == job


def test_dispatch_is_the_only_analyzer_entry_point() -> None:
    """The worker runs analyzers through the same registry dispatch as the CLI."""
    calls: list[str] = []
    report = ReportDouble(summary="dispatched")
    run = make_run(specs={"first": make_spec("first", lambda _context: report)})

    original = analysis_dispatch_module.run_registry_analyzer
    try:
        analysis_dispatch_module.run_registry_analyzer = lambda spec, context: (
            calls.append(spec.key) or report  # type: ignore[func-returns-value]
        )
        analyzer_workers.analyze_job(run, "first")
    finally:
        analysis_dispatch_module.run_registry_analyzer = original

    assert calls == ["first"]


def test_analyzers_that_share_work_form_one_job() -> None:
    """`variables` publishes the views `datatype-fields` consumes."""
    jobs = analyzer_workers.analyzer_jobs(("sfc", "variables", "datatype-fields"))

    assert jobs == (("sfc",), ("variables", "datatype-fields"))


def test_a_group_keeps_only_the_selected_members() -> None:
    assert analyzer_workers.analyzer_jobs(("datatype-fields",)) == (("datatype-fields",),)
    assert analyzer_workers.analyzer_jobs(("variables", "sfc")) == (("variables",), ("sfc",))


def test_unrelated_analyzers_stay_one_job_each() -> None:
    jobs = analyzer_workers.analyzer_jobs(("sfc", "same-cycle", "dataflow"))

    assert jobs == (("sfc",), ("same-cycle",), ("dataflow",))
