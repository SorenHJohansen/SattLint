"""Analyzer execution helpers for the checks pipeline."""

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from dataclasses import dataclass
from time import perf_counter
from typing import Any, cast

from sattlint.parser_api import BasePicture

from ..analyzers import catalog as analysis_catalog_module
from ..analyzers import dispatch as analysis_dispatch_module
from ..analyzers.framework import (
    AnalysisSharedArtifacts,
    AnalyzerSpec,
    SimpleReport,
    build_analysis_context,
)
from ..cache import AnalysisReportCache
from ..config.types import ConfigDict
from ..core import profiling as profiling_module
from ..core.debug import debug_enabled
from ..core.terminal import flush_stdout
from ..core.timings import NamedTimings, PhaseTiming, TimingBottleneck
from ..models.project_graph import ProjectGraph
from ..project import loading as project_loading_module
from . import analyzer_workers
from . import output as output_module
from .checks_records import snapshot_module_tree
from .checks_results import ChecksAnalyzerResult, ChecksTargetResult
from .findings import extract_report_findings

__all__ = [
    "AnalyzerExecution",
    "TargetExecution",
    "TargetRunOutcome",
    "execute_target",
    "get_enabled_analyzers",
    "partition_analyzers",
    "resolve_job_count",
    "run_per_run_analyzer",
]


@dataclass(frozen=True, slots=True)
class TargetExecution:
    """Dependencies already resolved by the checks entry point for one run."""

    cfg: ConfigDict
    analyzers: tuple[AnalyzerSpec, ...]
    per_target_analyzers: tuple[AnalyzerSpec, ...]
    report_cache: AnalysisReportCache | None
    report_cache_key: Callable[[str, str], str]
    profiler: profiling_module.ProfileRecorder
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool]
    emit_line: Callable[[str], None]
    # The module tree only feeds a persisted run record's navigation tree, so a run
    # that will not be stored must not pay to build it.
    build_module_tree: bool = True
    # None means "pick a worker count from the analyzer count and the CPU count";
    # 1 keeps every analyzer in this process.
    jobs: int | None = None


@dataclass(frozen=True, slots=True)
class AnalyzerExecution:
    result: ChecksAnalyzerResult
    cancelled: bool = False


@dataclass(frozen=True, slots=True)
class TargetRunOutcome:
    target: ChecksTargetResult
    cancelled: bool = False


def get_enabled_analyzers() -> list[Any]:
    return cast(list[Any], analysis_catalog_module.get_selectable_analyzers())


def _analyzer_failure_message(name: str, exc: Exception, *, debug: bool) -> str:
    """Describe a failed analyzer without putting internals in shared output."""
    return analyzer_workers.analyzer_failure_message(name, exc, debug=debug)


def _analysis_status_text(target_name: str, spec: AnalyzerSpec) -> str:
    return f"Analyzing {target_name}: {spec.name} ({spec.key})"


def resolve_job_count(requested: int | None, analyzer_count: int) -> int:
    """The number of workers one target's analyzer loop will use."""
    return analyzer_workers.resolve_job_count(requested, analyzer_count)


def _profile_analyzers_enabled() -> bool:
    return os.environ.get("SATTLINT_PROFILE_ANALYZERS", "").strip().casefold() in {"1", "true", "yes", "on"}


def _shared_artifact_profile_text(target_name: str, shared_artifacts: AnalysisSharedArtifacts) -> str:
    counters = shared_artifacts.counters
    return (
        "Analyzer reuse profile for "
        f"{target_name}: shared-artifact-holders={counters.shared_artifact_holders_created}, "
        f"variable-foundation-builds={counters.variable_foundation_builds}, "
        f"variable-root-traversals={counters.variable_root_traversals}, "
        f"local-env-builds={counters.local_env_builds}"
    )


def run_per_run_analyzer(
    spec: AnalyzerSpec,
    cfg: ConfigDict,
) -> ChecksAnalyzerResult:
    started_at = perf_counter()
    try:
        context = build_analysis_context(
            cast(BasePicture, None),
            debug=debug_enabled(cfg),
            config=cfg,
            create_shared_artifacts=True,
            program_ast_loader=project_loading_module.load_program_ast,
            program_ast_batch_loader=project_loading_module.load_program_asts,
        )
        report = analysis_dispatch_module.run_registry_analyzer(spec, context)
    except Exception as exc:  # noqa: BLE001 - a per-run failure should not abort the run
        return ChecksAnalyzerResult(
            key=spec.key,
            name=spec.name,
            status="failed",
            summary=_analyzer_failure_message(spec.name, exc, debug=debug_enabled(cfg)),
            issue_count=0,
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
        )
    typed_report = cast(SimpleReport, report)
    summary_text = typed_report.summary()
    findings = extract_report_findings(typed_report, default_name=spec.name)
    return ChecksAnalyzerResult(
        key=spec.key,
        name=spec.name,
        status="completed",
        summary=summary_text,
        report_kind=type(report).__name__,
        issue_count=len(findings),
        findings=findings,
        duration_ms=round((perf_counter() - started_at) * 1000, 3),
    )


def partition_analyzers(analyzers: list[AnalyzerSpec]) -> tuple[list[AnalyzerSpec], list[AnalyzerSpec]]:
    per_target: list[AnalyzerSpec] = []
    per_run: list[AnalyzerSpec] = []
    for spec in analyzers:
        # ``AnalyzerSpec.scope`` defaults to per-target; a dispatch double may
        # omit it. Any other value is a wiring error, not a reason to drop the
        # analyzer from both passes without a word.
        scope = getattr(spec, "scope", "per-target")
        if scope == "per-target":
            per_target.append(spec)
        elif scope == "per-run":
            per_run.append(spec)
        else:
            raise ValueError(f"Analyzer {spec.key!r} declares an unsupported scope {scope!r}")
    return per_target, per_run


def _run_target_analyzer(
    run: analyzer_workers.AnalyzerRun,
    spec: AnalyzerSpec,
    execution: TargetExecution,
    analyzer_timings_ms: dict[str, float],
    analyzer_phase_timings_ms: dict[str, tuple[PhaseTiming, ...]],
    *,
    compute_fn: Callable[[], analyzer_workers.AnalyzerJobResult],
) -> AnalyzerExecution:
    """Run one analyzer, print its section, and record its timing.

    ``compute_fn`` either runs the analyzer here or waits for a worker's result,
    so the printed output and the recorded timings stay identical in both modes.
    """
    execution.emit_line(f"\n=== {spec.name} ({spec.key}) ===")
    flush_stdout()
    analyzer_started_at = perf_counter()
    try:
        job = output_module.run_with_live_status(_analysis_status_text(run.target_name, spec), compute_fn)
    except Exception as exc:  # noqa: BLE001 - report and keep the run going
        analyzer_timings_ms[spec.key] = round((perf_counter() - analyzer_started_at) * 1000, 3)
        message = _analyzer_failure_message(str(spec.name), exc, debug=debug_enabled(execution.cfg))
        execution.emit_line(f"❌ {message}")
        return AnalyzerExecution(
            result=ChecksAnalyzerResult(
                key=spec.key,
                name=str(spec.name),
                status="failed",
                summary=message,
                issue_count=0,
                duration_ms=analyzer_timings_ms[spec.key],
            )
        )
    except KeyboardInterrupt:
        analyzer_timings_ms[spec.key] = round((perf_counter() - analyzer_started_at) * 1000, 3)
        return AnalyzerExecution(
            result=ChecksAnalyzerResult(
                key=spec.key,
                name=str(spec.name),
                status="cancelled",
                duration_ms=analyzer_timings_ms[spec.key],
            ),
            cancelled=True,
        )
    for line in job.output_lines:
        execution.emit_line(line)
    if job.result.duration_ms is not None:
        analyzer_timings_ms[spec.key] = job.result.duration_ms
    if job.phase_timings_ms:
        analyzer_phase_timings_ms[spec.key] = job.phase_timings_ms
    if job.result.summary is not None:
        execution.emit_line(job.result.summary)
    return AnalyzerExecution(result=job.result)


def _next_pooled_job(
    pending: Generator[tuple[analyzer_workers.AnalyzerJobResult, ...]],
    completed: dict[str, analyzer_workers.AnalyzerJobResult],
    key: str,
) -> analyzer_workers.AnalyzerJobResult:
    """Wait for one key's result, buffering the analyzers that finish earlier."""
    while key not in completed:
        try:
            group = next(pending)
        except StopIteration:
            raise RuntimeError(f"The analyzer workers ended without a result for {key!r}.") from None
        for job in group:
            completed[job.key] = job
    return completed.pop(key)


def _iter_analyzer_executions(
    run: analyzer_workers.AnalyzerRun,
    specs: tuple[AnalyzerSpec, ...],
    execution: TargetExecution,
    analyzer_timings_ms: dict[str, float],
    analyzer_phase_timings_ms: dict[str, tuple[PhaseTiming, ...]],
    jobs: int,
) -> Generator[AnalyzerExecution]:
    """Yield one execution per analyzer, in the declared analyzer order."""
    if jobs <= 1:
        for spec in specs:
            yield _run_target_analyzer(
                run,
                spec,
                execution,
                analyzer_timings_ms,
                analyzer_phase_timings_ms,
                compute_fn=lambda spec=spec: analyzer_workers.analyze_job(run, spec.key),
            )
        return

    pending = analyzer_workers.run_jobs_pooled(
        run,
        analyzer_workers.analyzer_jobs(tuple(spec.key for spec in specs)),
        jobs,
    )
    completed: dict[str, analyzer_workers.AnalyzerJobResult] = {}
    try:
        for spec in specs:
            yield _run_target_analyzer(
                run,
                spec,
                execution,
                analyzer_timings_ms,
                analyzer_phase_timings_ms,
                compute_fn=lambda spec=spec: _next_pooled_job(pending, completed, spec.key),
            )
    finally:
        # A cancelled run stops consuming here; closing the generator terminates
        # the workers instead of leaving them running the rest of the queue.
        pending.close()


def _analyzer_phase_bottleneck(
    analyzer_phase_timings_ms: dict[str, tuple[PhaseTiming, ...]],
) -> TimingBottleneck | None:
    bottleneck: TimingBottleneck | None = None
    for analyzer_key, phase_timings in analyzer_phase_timings_ms.items():
        candidate = profiling_module.bottleneck_from_phase_timings(
            phase_timings,
            kind="analyzer-phase",
            analyzer_key=analyzer_key,
        )
        if candidate is None:
            continue
        if bottleneck is None or candidate.duration_ms > bottleneck.duration_ms:
            bottleneck = candidate
    return bottleneck


def _target_profiler_payload(
    execution: TargetExecution,
    analyzer_timings_ms: dict[str, float],
    analyzer_phase_timings_ms: dict[str, tuple[PhaseTiming, ...]],
    stage_timings_ms: NamedTimings,
    graphics_timings_ms: NamedTimings,
    analyzer_bottleneck: TimingBottleneck | None,
    analyzer_phase_bottleneck: TimingBottleneck | None,
    job_count: int,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "selected_analyzers": [spec.key for spec in execution.analyzers],
        "analyzer_timings_ms": dict(analyzer_timings_ms),
        "jobs": job_count,
    }
    if stage_timings_ms:
        payload["stage_timings_ms"] = stage_timings_ms.to_dict()
    if graphics_timings_ms:
        payload["graphics_timings_ms"] = graphics_timings_ms.to_dict()
    if analyzer_phase_timings_ms:
        payload["analyzer_phase_timings_ms"] = {
            analyzer_key: [phase.to_dict() for phase in phase_timings]
            for analyzer_key, phase_timings in analyzer_phase_timings_ms.items()
        }
    if analyzer_bottleneck is not None:
        payload["analyzer_bottleneck"] = analyzer_bottleneck.to_dict()
        payload["bottleneck_kind"] = "analyzer"
        payload["bottleneck"] = analyzer_bottleneck.to_dict()
    if analyzer_phase_bottleneck is not None:
        payload["analyzer_phase_bottleneck"] = analyzer_phase_bottleneck.to_dict()
        payload["bottleneck_kind"] = "analyzer-phase"
        payload["bottleneck"] = analyzer_phase_bottleneck.to_dict()
    return payload


def execute_target(
    target_name: str,
    project_bp: BasePicture,
    graph: ProjectGraph,
    *,
    execution: TargetExecution,
    load_duration_ms: float | None = None,
) -> TargetRunOutcome:
    target_analyzers: list[ChecksAnalyzerResult] = []
    target_started_at = perf_counter()
    analyzer_timings_ms: dict[str, float] = {}
    analyzer_phase_timings_ms: dict[str, tuple[PhaseTiming, ...]] = {}
    stage_timings_ms = profiling_module.normalize_named_timings_ms(
        getattr(graph, "load_stage_timings", None), scale=1000.0
    )
    graphics_timings_ms = profiling_module.normalize_named_timings_ms(
        getattr(graph, "graphics_load_timings", None),
        scale=1000.0,
    )
    is_library = execution.target_is_library_fn(execution.cfg, project_bp, graph)
    module_tree = (
        snapshot_module_tree(project_bp, graph, target_name)
        if execution.build_module_tree and isinstance(cast(object, project_bp), BasePicture)
        else None
    )
    context = build_analysis_context(
        project_bp,
        graph=graph,
        debug=debug_enabled(execution.cfg),
        target_is_library=is_library,
        config=execution.cfg,
        create_shared_artifacts=True,
    )
    execution.emit_line(f"\n=== Target: {target_name} ===")
    flush_stdout()
    run = analyzer_workers.AnalyzerRun(
        cfg=execution.cfg,
        target_name=target_name,
        context=context,
        graph=graph,
        report_cache=execution.report_cache,
        report_cache_key=execution.report_cache_key,
        specs={spec.key: spec for spec in execution.per_target_analyzers},
    )
    job_count = resolve_job_count(execution.jobs, len(execution.per_target_analyzers))
    if job_count > 1 and not analyzer_workers.pooling_supported():
        # Platforms without fork cannot share the loaded graph, so the analyzer
        # loop stays in-process instead of reloading the project per worker.
        job_count = 1
    if job_count > 1:
        run_count = len(execution.per_target_analyzers)
        execution.emit_line(f"Running {run_count} analyzers across {job_count} worker processes")
    executions = _iter_analyzer_executions(
        run,
        execution.per_target_analyzers,
        execution,
        analyzer_timings_ms,
        analyzer_phase_timings_ms,
        job_count,
    )
    try:
        for outcome in executions:
            target_analyzers.append(outcome.result)
            if not outcome.cancelled:
                continue
            execution.profiler.emit(
                operation="checks",
                target_name=target_name,
                duration_ms=(perf_counter() - target_started_at) * 1000,
                cancelled=True,
                payload={
                    "selected_analyzers": [selected.key for selected in execution.analyzers],
                    "analyzer_timings_ms": dict(analyzer_timings_ms),
                    "jobs": job_count,
                },
            )
            return TargetRunOutcome(
                target=ChecksTargetResult(
                    target_name=target_name,
                    is_library=is_library,
                    analyzers=tuple(target_analyzers),
                    module=module_tree,
                    stage_timings_ms=stage_timings_ms or None,
                    graphics_timings_ms=graphics_timings_ms or None,
                    load_duration_ms=load_duration_ms,
                ),
                cancelled=True,
            )
    finally:
        executions.close()
    analyzer_bottleneck = profiling_module.bottleneck_from_named_timings(analyzer_timings_ms, kind="analyzer")
    analyzer_phase_bottleneck = _analyzer_phase_bottleneck(analyzer_phase_timings_ms)
    execution.profiler.emit(
        operation="checks",
        target_name=target_name,
        duration_ms=(perf_counter() - target_started_at) * 1000,
        success=True,
        payload=_target_profiler_payload(
            execution,
            analyzer_timings_ms,
            analyzer_phase_timings_ms,
            stage_timings_ms,
            graphics_timings_ms,
            analyzer_bottleneck,
            analyzer_phase_bottleneck,
            job_count,
        ),
    )
    shared_artifact_profile: str | None = None
    if _profile_analyzers_enabled() and context.shared_artifacts is not None:
        shared_artifact_profile = _shared_artifact_profile_text(target_name, context.shared_artifacts)
        execution.emit_line(shared_artifact_profile)
    return TargetRunOutcome(
        target=ChecksTargetResult(
            target_name=target_name,
            is_library=is_library,
            analyzers=tuple(target_analyzers),
            module=module_tree,
            stage_timings_ms=stage_timings_ms or None,
            graphics_timings_ms=graphics_timings_ms or None,
            analyzer_bottleneck=analyzer_bottleneck,
            analyzer_phase_bottleneck=analyzer_phase_bottleneck,
            shared_artifact_profile=shared_artifact_profile,
            load_duration_ms=load_duration_ms,
        )
    )
