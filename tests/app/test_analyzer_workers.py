# pyright: reportUnknownLambdaType=false, reportPrivateUsage=false
"""Tests for the analyzer worker pool and its single-analyzer execution."""

from __future__ import annotations

import io
import multiprocessing
import pickle
import sys
from collections.abc import Callable, Generator
from typing import Any, cast

import pytest

from sattlint.analyzers import dispatch as analysis_dispatch_module
from sattlint.analyzers.framework import AnalysisContext, AnalyzerSpec, Issue
from sattlint.application import analyzer_workers
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
def test_run_jobs_pooled_terminates_the_workers_when_the_caller_stops_early() -> None:
    specs = {"first": make_spec("first", lambda _context: ReportDouble(summary="first done"))}
    run = _pooled_run(specs)
    pending: Generator[tuple[analyzer_workers.AnalyzerJobResult, ...]] = analyzer_workers.run_jobs_pooled(
        run, (("first",),), workers=1
    )

    (first,) = next(pending)
    pending.close()

    assert first.key == "first"
    assert analyzer_workers._worker_run is None
    assert not [child for child in multiprocessing.active_children() if child.name.startswith("ForkPoolWorker")]


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
