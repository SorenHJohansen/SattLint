"""Run per-target analyzers in-process or across a forked worker pool.

Every per-target analyzer reads the same loaded project graph and the same
analysis context, and an analyzer is pure Python: it holds the GIL for its whole
run, so threads cannot overlap two of them. Processes can. The parent loads the
graph once and forks its workers afterwards, so the workers share the parsed
graph copy-on-write and pay memory only for the artifacts they build.

Analyzers may still read each other's shared artifacts as an optional
memoization (the ``variables`` collector publishes views for derived analyzers).
Each worker starts from the empty artifact holder the parent had at fork time,
so a worker recomputes what it needs instead of reading another worker's state.
That only costs time; every analyzer can run standalone.

Results come back in completion order. The caller drains them in the run's
declared analyzer order, so the printed output and the stored run record stay
deterministic no matter which analyzer finishes first.
"""

from __future__ import annotations

import io
import multiprocessing
import os
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, replace
from time import perf_counter
from typing import cast

from sattlint.parser_api import BasePicture

from ..analyzers import dispatch as analysis_dispatch_module
from ..analyzers.framework import AnalysisContext, AnalyzerSpec
from ..analyzers.shared.instance_paths import rewrite_typedef_paths
from ..cache import AnalysisReportCache
from ..config.types import ConfigDict
from ..core import profiling as profiling_module
from ..core.debug import debug_enabled
from ..core.timings import PhaseTiming
from ..models.project_graph import ProjectGraph
from ..project import cache as report_cache_module
from ..reporting.target_report import normalize_report_target_name
from .checks_results import ChecksAnalyzerResult
from .findings import extract_report_findings

__all__ = [
    "AUTO_JOB_LIMIT",
    "SEQUENTIAL_GROUPS",
    "AnalyzerJobResult",
    "AnalyzerRun",
    "analyze_job",
    "analyzer_failure_message",
    "analyzer_jobs",
    "degraded_job_result",
    "pooling_supported",
    "resolve_job_count",
    "run_jobs_pooled",
]

# A parallel run is bounded by its slowest analyzer, so past a handful of workers
# the only thing that grows is the resident memory of the forked children.
AUTO_JOB_LIMIT = 4

#: Analyzers that share work run in one worker, in the listed order.
#:
#: ``variables`` publishes the collected views that ``datatype-fields`` consumes,
#: so a split across workers repeats the whole variable traversal. In one worker
#: the second pass becomes field evidence only.
SEQUENTIAL_GROUPS: tuple[tuple[str, ...], ...] = (("variables", "datatype-fields"),)


def analyzer_jobs(analyzer_keys: Sequence[str]) -> tuple[tuple[str, ...], ...]:
    """Group the selected analyzer keys into the jobs one worker runs.

    A group is used only when every member is selected, and its members keep
    their selection order. Everything else is one analyzer per job.
    """
    grouped: dict[str, tuple[str, ...]] = {}
    for group in SEQUENTIAL_GROUPS:
        members = tuple(key for key in analyzer_keys if key in group)
        if len(members) > 1:
            for key in members:
                grouped[key] = members
    jobs: list[tuple[str, ...]] = []
    seen: set[str] = set()
    for key in analyzer_keys:
        if key in seen:
            continue
        members = grouped.get(key, (key,))
        jobs.append(members)
        seen.update(members)
    return tuple(jobs)


@dataclass(frozen=True, slots=True)
class AnalyzerRun:
    """Everything one per-target analyzer needs, prepared before any fork."""

    cfg: ConfigDict
    target_name: str
    context: AnalysisContext
    graph: ProjectGraph
    report_cache: AnalysisReportCache | None
    report_cache_key: Callable[[str, str], str]
    specs: Mapping[str, AnalyzerSpec]


@dataclass(frozen=True, slots=True)
class AnalyzerJobResult:
    """One analyzer's finished result, safe to send across a process boundary."""

    key: str
    result: ChecksAnalyzerResult
    phase_timings_ms: tuple[PhaseTiming, ...] = ()
    # Lines an analyzer wrote to stdout/stderr. Only a worker captures them; an
    # in-process run writes them straight to the console instead.
    output_lines: tuple[str, ...] = ()
    cancelled: bool = False


def analyzer_failure_message(name: str, exc: BaseException, *, debug: bool) -> str:
    """Describe a failed analyzer without putting internals in shared output.

    The exception text can carry internal paths, values, and local names, and the
    summary reaches run history, CI logs, and the UI. In a normal run the message
    names the exception type only; ``debug`` keeps the full text for the person
    diagnosing the failure.
    """
    if debug:
        return f"{name} failed: {exc}"
    return f"{name} failed: {type(exc).__name__}"


def _rewrite_typedef_issue_paths(report: object, base_picture: BasePicture) -> None:
    for attr in ("issues", "hits"):
        items = getattr(report, attr, None)
        if isinstance(items, list):
            setattr(report, attr, rewrite_typedef_paths(cast(list[object], items), base_picture))


def analyze_job(run: AnalyzerRun, key: str) -> AnalyzerJobResult:
    """Run one analyzer and normalize its report into a result record.

    Raises whatever the analyzer raises; the caller decides whether that becomes
    a failure record (``degraded_job_result``) or a cancellation.
    """
    spec = run.specs[key]
    started_at = perf_counter()
    report = report_cache_module.run_with_analysis_report_cache(
        run.graph,
        report_cache=run.report_cache,
        analyzer_cache_key=spec.key,
        run_fn=lambda: analysis_dispatch_module.run_registry_analyzer(spec, run.context),
        compute_analysis_report_cache_key_fn=run.report_cache_key,
    )
    duration_ms = round((perf_counter() - started_at) * 1000, 3)

    _rewrite_typedef_issue_paths(report, run.context.base_picture)
    phase_timings_ms = profiling_module.normalize_phase_timings_ms(getattr(report, "phase_timings", None))
    report = normalize_report_target_name(report, run.target_name)
    summary_text = report.summary()
    findings = extract_report_findings(report, default_name=run.target_name)
    return AnalyzerJobResult(
        key=key,
        result=ChecksAnalyzerResult(
            key=spec.key,
            name=str(spec.name),
            status="completed",
            summary=summary_text,
            report_kind=type(report).__name__,
            issue_count=len(findings),
            findings=findings,
            duration_ms=duration_ms,
            phase_timings_ms=phase_timings_ms,
        ),
        phase_timings_ms=phase_timings_ms,
    )


def degraded_job_result(
    run: AnalyzerRun,
    key: str,
    exc: BaseException,
    *,
    output_lines: tuple[str, ...] = (),
) -> AnalyzerJobResult:
    """Turn a raised analyzer into a failure record so the run keeps going."""
    spec = run.specs[key]
    message = analyzer_failure_message(str(spec.name), exc, debug=debug_enabled(run.cfg))
    return AnalyzerJobResult(
        key=key,
        result=ChecksAnalyzerResult(
            key=spec.key,
            name=str(spec.name),
            status="failed",
            summary=message,
            issue_count=0,
        ),
        output_lines=output_lines,
    )


def pooling_supported() -> bool:
    """Whether this platform can fork workers that inherit the loaded graph."""
    return "fork" in multiprocessing.get_all_start_methods()


def resolve_job_count(requested: int | None, analyzer_count: int) -> int:
    """Return the number of workers a target's analyzer loop should use."""
    if requested is not None and requested < 0:
        raise ValueError("The worker count cannot be negative.")
    if analyzer_count <= 1:
        return 1
    if requested:
        return min(requested, analyzer_count)
    cpu_count = os.process_cpu_count() or 1
    return max(1, min(AUTO_JOB_LIMIT, cpu_count, analyzer_count))


@dataclass(frozen=True, slots=True)
class _WorkerRun:
    """The parent's prepared run, inherited by every forked worker."""

    run: AnalyzerRun


_worker_run: _WorkerRun | None = None


def _captured_lines(buffer: io.StringIO) -> tuple[str, ...]:
    return tuple(buffer.getvalue().splitlines())


def _worker_entry(keys: tuple[str, ...]) -> tuple[AnalyzerJobResult, ...]:
    """Worker process entry point: run one job's analyzers and answer for each."""
    worker_run = _worker_run
    if worker_run is None:
        raise RuntimeError("Analyzer worker started without a prepared run.")

    run = worker_run.run
    results: list[AnalyzerJobResult] = []
    for key in keys:
        buffer = io.StringIO()
        try:
            # An analyzer prints progress for the person watching the run. In a
            # worker that stream belongs to the parent, which prints it in
            # analyzer order.
            with redirect_stdout(buffer), redirect_stderr(buffer):
                result = analyze_job(run, key)
        except BaseException as exc:  # noqa: BLE001 - a worker must answer, never die quietly
            results.append(degraded_job_result(run, key, exc, output_lines=_captured_lines(buffer)))
            continue
        results.append(replace(result, output_lines=_captured_lines(buffer)))
    return tuple(results)


def run_jobs_pooled(
    run: AnalyzerRun,
    jobs: tuple[tuple[str, ...], ...],
    workers: int,
) -> Generator[tuple[AnalyzerJobResult, ...]]:
    """Yield each job's analyzer results in completion order.

    The workers are forked here, after the project graph exists, so they inherit
    it instead of loading or pickling it again. The pool is terminated when the
    caller stops consuming, which is what a cancelled run does.
    """
    global _worker_run

    context = multiprocessing.get_context("fork")
    _worker_run = _WorkerRun(run=run)
    try:
        pool = context.Pool(processes=workers)
    except BaseException:
        _worker_run = None
        raise
    try:
        yield from pool.imap_unordered(_worker_entry, jobs, chunksize=1)
    finally:
        _worker_run = None
        pool.terminate()
        pool.join()
