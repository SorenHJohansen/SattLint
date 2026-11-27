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

The workers run in a process executor whose broken state is part of its public
contract: if a worker dies while it holds a job, every future still waiting for
an answer fails with ``BrokenProcessPool`` instead of blocking the run. The
parent turns those keys into failed results and finishes the run with them.
"""

from __future__ import annotations

import io
import multiprocessing
import os
from collections.abc import Callable, Generator, Mapping, Sequence
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, replace
from multiprocessing.process import BaseProcess
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


def _failed_job_result(
    run: AnalyzerRun,
    key: str,
    summary: str,
    *,
    output_lines: tuple[str, ...] = (),
) -> AnalyzerJobResult:
    spec = run.specs[key]
    return AnalyzerJobResult(
        key=key,
        result=ChecksAnalyzerResult(
            key=spec.key,
            name=str(spec.name),
            status="failed",
            summary=summary,
            issue_count=0,
        ),
        output_lines=output_lines,
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
    return _failed_job_result(run, key, message, output_lines=output_lines)


def _worker_stopped_result(run: AnalyzerRun, key: str) -> AnalyzerJobResult:
    """Fail an analyzer whose worker died before it could report.

    The message is fixed on purpose: the run history and the UI read it, and the
    reason a process disappeared is not something the parent can explain, so the
    text names the lost work without exposing process internals.
    """
    spec = run.specs[key]
    return _failed_job_result(run, key, f"Analyzer worker stopped before completing {spec.name}.")


def pooling_supported() -> bool:
    """Whether this platform can fork workers that inherit the loaded graph."""
    return "fork" in multiprocessing.get_all_start_methods()


def resolve_job_count(requested: int | None, analyzer_count: int) -> int:
    """Return the number of workers a target's analyzer loop should use.

    ``None`` and ``0`` both mean automatic: pick a bounded count from the CPU
    count. The CLI maps ``--jobs 0`` to ``None``, and its own default is ``1``,
    so a plain run stays sequential without reaching the automatic branch.
    """
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


def _live_executor_processes(executor: ProcessPoolExecutor) -> Mapping[int, BaseProcess] | None:
    # ``shutdown`` waits for running tasks, and the public ``terminate_workers``
    # only exists from Python 3.14, so the private worker map is the only way to
    # stop a cancelled run's workers promptly.
    processes: Mapping[int, BaseProcess] | None = executor._processes  # pyright: ignore[reportPrivateUsage]
    return processes


def _shutdown_executor(executor: ProcessPoolExecutor, *, terminate: bool) -> None:
    """Stop the pool, terminating live workers when the run did not finish."""
    processes = _live_executor_processes(executor)
    if terminate and processes is not None:
        for process in processes.values():
            if process.is_alive():
                process.terminate()
    executor.shutdown(wait=True, cancel_futures=terminate)


def _job_results(
    futures: Mapping[Future[tuple[AnalyzerJobResult, ...]], tuple[str, ...]],
    run: AnalyzerRun,
    jobs: tuple[tuple[str, ...], ...],
) -> Generator[tuple[AnalyzerJobResult, ...]]:
    """Yield finished jobs in completion order, failing the ones a dead worker lost."""
    unreported = dict(futures)
    reported: set[str] = set()
    broken = False
    for future in as_completed(unreported):
        try:
            group = future.result()
        except BrokenProcessPool:
            broken = True
            break
        del unreported[future]
        reported.update(job.key for job in group)
        yield group

    if not broken:
        return

    # The executor marks every pending task failed when a worker dies, and a
    # task that already finished keeps its result. Report those first, then fail
    # the keys whose worker never got to answer.
    for future in unreported:
        if not future.done():
            continue
        try:
            group = future.result()
        except BrokenProcessPool:
            continue
        reported.update(job.key for job in group)
        yield group

    for job in jobs:
        missing = tuple(key for key in job if key not in reported)
        if not missing:
            continue
        reported.update(missing)
        yield tuple(_worker_stopped_result(run, key) for key in missing)


def run_jobs_pooled(
    run: AnalyzerRun,
    jobs: tuple[tuple[str, ...], ...],
    workers: int,
) -> Generator[tuple[AnalyzerJobResult, ...]]:
    """Yield each job's analyzer results in completion order.

    The workers are forked here, after the project graph exists, so they inherit
    it instead of loading or pickling it again. A worker that dies mid-job makes
    the executor broken; the remaining keys are reported as failed instead of
    waiting forever. The pool is terminated when the caller stops consuming,
    which is what a cancelled run does.
    """
    global _worker_run

    context = multiprocessing.get_context("fork")
    _worker_run = _WorkerRun(run=run)
    try:
        executor = ProcessPoolExecutor(max_workers=workers, mp_context=context)
    except BaseException:
        _worker_run = None
        raise
    finished = False
    try:
        futures = {executor.submit(_worker_entry, job): job for job in jobs}
        yield from _job_results(futures, run, jobs)
        finished = True
    finally:
        _worker_run = None
        _shutdown_executor(executor, terminate=not finished)
