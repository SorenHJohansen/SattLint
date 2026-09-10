"""Checks runner for the application layer.

Runs the selected analyzers across every loaded target and folds the per-target
and per-analyzer results into a ``ChecksRunResult``.  Elevated from the old flat
``app_analysis`` / ``_app_analysis_checks`` modules as part of the Phase 2
layered refactor.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Set
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from ..analyzers import catalog as analysis_catalog_module
from ..analyzers import dispatch as analysis_dispatch_module
from ..analyzers.framework import (
    AnalysisSharedArtifacts,
    Issue,
    SimpleReport,
    build_analysis_context,
)
from ..analyzers.icf.analyzer import analyze_icf_configuration
from ..analyzers.rule_profiles import apply_rule_profile_to_report
from ..analyzers.shared.instance_paths import rewrite_typedef_paths
from ..analyzers.variables import IssueKind
from ..cache import AnalysisReportCache, compute_analysis_report_cache_key, get_cache_dir
from ..config.types import ConfigDict
from ..core import profiling as profiling_module
from ..core.debug import debug_enabled
from ..core.terminal import flush_stdout
from ..models.project_graph import ProjectGraph
from ..project import cache as report_cache_module
from ..reporting.target_report import normalize_report_target_name
from ..reporting.variables_report import VariablesReport
from ..runs import (
    DEFAULT_RUN_HISTORY_LIMIT,
    RunAnalyzerRecord,
    RunRecord,
    RunTargetRecord,
    get_runs_dir,
    prune_runs,
    save_run,
)
from . import output as output_module
from . import project as project_application
from .findings import AnalysisFinding, extract_report_findings

LoadedProject = project_application.LoadedProject
LIBRARY_SUPPRESSED_ANALYZER_KEYS = frozenset({"picture-display-paths"})
ICF_ANALYZER_KEY = "icf"
ICF_TARGET_NAME = "ICF configuration"


@dataclass(frozen=True, slots=True)
class ChecksAnalyzerResult:
    key: str
    name: str
    status: str
    summary: str | None = None
    report_kind: str | None = None
    issue_count: int | None = None
    findings: tuple[AnalysisFinding, ...] = ()
    duration_ms: float | None = None
    phase_timings_ms: tuple[dict[str, object], ...] = ()
    selected_issue_kinds: tuple[str, ...] | None = None
    skip_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ChecksTargetResult:
    target_name: str
    is_library: bool
    analyzers: tuple[ChecksAnalyzerResult, ...]
    stage_timings_ms: dict[str, float] | None = None
    graphics_timings_ms: dict[str, float] | None = None
    analyzer_bottleneck: dict[str, object] | None = None
    analyzer_phase_bottleneck: dict[str, object] | None = None
    shared_artifact_profile: str | None = None


@dataclass(frozen=True, slots=True)
class ChecksRunResult:
    output_lines: tuple[str, ...]
    targets: tuple[ChecksTargetResult, ...] = ()
    selected_analyzers: tuple[str, ...] = ()
    selected_issue_kinds: tuple[str, ...] | None = None
    cancelled: bool = False


def _normalized_issue_kind_value(raw_kind: object) -> str | None:
    if isinstance(raw_kind, IssueKind):
        return raw_kind.value
    value = getattr(raw_kind, "value", raw_kind)
    text = str(value).strip() if value is not None else ""
    return text or None


def normalize_selected_issue_kind_values(selected_issue_kinds: Set[str] | None) -> frozenset[str] | None:
    if selected_issue_kinds is None:
        return None
    normalized = {
        issue_kind
        for raw_kind in selected_issue_kinds
        if (issue_kind := _normalized_issue_kind_value(raw_kind)) is not None
    }
    return frozenset(normalized)


def format_selected_issue_kind_values(selected_issue_kinds: frozenset[str] | None) -> str | None:
    if not selected_issue_kinds:
        return None
    return ", ".join(sorted(selected_issue_kinds))


def selected_issue_kind_tuple(selected_issue_kinds: frozenset[str] | None) -> tuple[str, ...] | None:
    if not selected_issue_kinds:
        return None
    return tuple(sorted(selected_issue_kinds))


def _issue_count_for_report(report: object) -> int | None:
    issues = getattr(report, "issues", None)
    if not isinstance(issues, list):
        return None
    return len(cast(list[object], issues))


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _run_history_enabled(cfg: ConfigDict) -> bool:
    run_history = cast(object, cfg.get("run_history"))
    if isinstance(run_history, dict):
        mapping = cast(dict[str, object], run_history)
        return bool(mapping.get("enabled", True))
    return True


def _run_history_limit(cfg: ConfigDict) -> int:
    run_history = cast(object, cfg.get("run_history"))
    if isinstance(run_history, dict):
        mapping = cast(dict[str, object], run_history)
        limit = mapping.get("limit", DEFAULT_RUN_HISTORY_LIMIT)
        if isinstance(limit, int) and not isinstance(limit, bool) and limit > 0:
            return limit
    return DEFAULT_RUN_HISTORY_LIMIT


def _project_tag(cfg: ConfigDict) -> str:
    targets = cast(object, cfg.get("analyzed_programs_and_libraries", []))
    if isinstance(targets, list):
        return ", ".join(str(target) for target in cast(list[object], targets) if str(target).strip())
    return ""


def _run_analyzer_record(result: ChecksAnalyzerResult) -> RunAnalyzerRecord:
    return RunAnalyzerRecord(
        key=result.key,
        name=result.name,
        status=result.status,
        summary=result.summary,
        report_kind=result.report_kind,
        issue_count=result.issue_count,
        findings=result.findings,
        duration_ms=result.duration_ms,
        phase_timings_ms=result.phase_timings_ms,
        selected_issue_kinds=result.selected_issue_kinds,
        skip_reason=result.skip_reason,
    )


def _run_target_record(result: ChecksTargetResult) -> RunTargetRecord:
    return RunTargetRecord(
        target_name=result.target_name,
        is_library=result.is_library,
        analyzers=tuple(_run_analyzer_record(analyzer) for analyzer in result.analyzers),
        stage_timings_ms=result.stage_timings_ms,
        graphics_timings_ms=result.graphics_timings_ms,
    )


def build_run_record(result: ChecksRunResult, cfg: ConfigDict, *, started_at: str | None = None) -> RunRecord:
    """Convert a checks run result into a persisted run record."""
    return RunRecord(
        run_id="",
        started_at=started_at or _utc_now_iso(),
        finished_at=_utc_now_iso(),
        project_tag=_project_tag(cfg),
        selected_analyzers=result.selected_analyzers,
        selected_issue_kinds=result.selected_issue_kinds,
        targets=tuple(_run_target_record(target) for target in result.targets),
        output_lines=result.output_lines,
    )


def _persist_run_result(result: ChecksRunResult, cfg: ConfigDict, *, started_at: str) -> None:
    if result.cancelled or not _run_history_enabled(cfg):
        return
    runs_dir = get_runs_dir()
    record = build_run_record(result, cfg, started_at=started_at)
    save_run(record, runs_dir=runs_dir)
    prune_runs(runs_dir, limit=_run_history_limit(cfg))


def _filter_report_for_selected_issue_kinds(
    report: object,
    selected_issue_kinds: frozenset[str] | None,
) -> object:
    if not selected_issue_kinds or isinstance(report, VariablesReport):
        return report

    issues = getattr(report, "issues", None)
    if not isinstance(issues, list):
        return report

    typed_issues = cast(list[object], issues)
    filtered_issues: list[Issue] = [
        issue
        for issue in typed_issues
        if isinstance(issue, Issue)
        and _normalized_issue_kind_value(getattr(issue, "kind", None)) in selected_issue_kinds
    ]
    report_name = str(getattr(report, "name", getattr(report, "basepicture_name", "Analysis")) or "Analysis")
    return SimpleReport(name=report_name, issues=filtered_issues)


def _get_enabled_analyzers() -> list[Any]:
    return cast(list[Any], analysis_catalog_module.get_default_cli_analyzers())


def _analysis_status_text(target_name: str, spec: Any) -> str:
    return f"Analyzing {target_name}: {spec.name} ({spec.key})"


def _profile_analyzers_enabled() -> bool:
    return os.environ.get("SATTLINT_PROFILE_ANALYZERS", "").strip().casefold() in {"1", "true", "yes", "on"}


def _shared_artifact_profile_text(target_name: str, shared_artifacts: AnalysisSharedArtifacts) -> str:
    counters = shared_artifacts.counters
    return (
        "Analyzer reuse profile for "
        f"{target_name}: shared-artifact-holders={counters.shared_artifact_holders_created}, "
        f"variable-foundation-builds={counters.variable_foundation_builds}, "
        f"semantic-precomputed-reports={counters.semantic_precomputed_reports_used}, "
        f"semantic-reruns={counters.semantic_analyzer_reruns}, "
        f"local-env-builds={counters.local_env_builds}"
    )


def _iter_loaded_projects(cfg: ConfigDict) -> Iterator[LoadedProject]:
    return project_application.iter_loaded_projects(cfg)


def _run_whole_run_analyzer(
    spec: Any,
    cfg: ConfigDict,
    selected_issue_kinds: frozenset[str] | None,
) -> ChecksAnalyzerResult | None:
    if getattr(spec, "key", None) != ICF_ANALYZER_KEY:
        return None
    started_at = perf_counter()
    try:
        report = analyze_icf_configuration(None, config=cfg, debug=debug_enabled(cfg))
    except Exception as exc:  # noqa: BLE001 - a whole-run failure should not abort the run
        return ChecksAnalyzerResult(
            key=ICF_ANALYZER_KEY,
            name=str(getattr(spec, "name", ICF_ANALYZER_KEY)),
            status="failed",
            summary=f"ICF validation failed: {exc}",
            issue_count=0,
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
        )
    report = apply_rule_profile_to_report(spec.key, report, cfg)
    report = _filter_report_for_selected_issue_kinds(report, selected_issue_kinds)
    typed_report = cast(SimpleReport, report)
    summary_text = typed_report.summary()
    findings = extract_report_findings(typed_report, default_name=ICF_TARGET_NAME)
    return ChecksAnalyzerResult(
        key=ICF_ANALYZER_KEY,
        name=str(getattr(spec, "name", ICF_ANALYZER_KEY)),
        status="completed",
        summary=summary_text,
        report_kind=type(report).__name__,
        issue_count=_issue_count_for_report(report),
        findings=findings,
        duration_ms=round((perf_counter() - started_at) * 1000, 3),
    )


def _target_is_library(cfg: ConfigDict, project_bp: BasePicture, graph: ProjectGraph) -> bool:
    return project_application.target_is_library(cfg, project_bp, graph)


def _rewrite_typedef_issue_paths(report: object, base_picture: BasePicture, graph: ProjectGraph) -> None:
    issues = getattr(report, "issues", None)
    if isinstance(issues, list):
        rewrite_typedef_paths(cast(list[object], issues), base_picture, graph)


def collect_run_checks_result(  # noqa: PLR0915
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    selected_issue_kinds: Set[str] | None = None,
    *,
    use_cache: bool = True,
    persist_run: bool = False,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    get_enabled_analyzers_fn: Callable[[], list[Any]] | None = None,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] | None = None,
) -> ChecksRunResult:
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = _iter_loaded_projects
    if get_enabled_analyzers_fn is None:
        get_enabled_analyzers_fn = _get_enabled_analyzers
    if target_is_library_fn is None:
        target_is_library_fn = _target_is_library

    run_started_at = _utc_now_iso()
    output_lines: list[str] = []
    target_results: list[ChecksTargetResult] = []

    def emit_line(message: str) -> None:
        output_lines.append(message)

    analyzers = list(
        analysis_dispatch_module.get_cli_dispatch_analyzers(
            selected_keys=selected_keys,
            get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        )
    )
    normalized_selected_issue_kinds = normalize_selected_issue_kind_values(selected_issue_kinds)
    selected_analyzer_keys = tuple(spec.key for spec in analyzers)
    selected_issue_kind_tuple_result = selected_issue_kind_tuple(normalized_selected_issue_kinds)

    if not analyzers:
        emit_line("❌ No matching checks found")
        return ChecksRunResult(
            output_lines=tuple(output_lines),
            selected_analyzers=selected_analyzer_keys,
            selected_issue_kinds=selected_issue_kind_tuple_result,
        )

    batch_analyzers = [spec for spec in analyzers if getattr(spec, "key", None) != ICF_ANALYZER_KEY]
    whole_run_analyzers = [spec for spec in analyzers if getattr(spec, "key", None) == ICF_ANALYZER_KEY]

    emit_line("\n--- Running checks ---")
    flush_stdout()
    report_cache = report_cache_module.create_analysis_report_cache(
        cfg,
        use_cache=use_cache,
        debug_enabled_fn=debug_enabled,
        analysis_report_cache_cls=AnalysisReportCache,
        get_cache_dir_fn=get_cache_dir,
    )
    profiler = profiling_module.create_profiler()
    try:
        for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
            target_analyzers: list[ChecksAnalyzerResult] = []
            target_started_at = perf_counter()
            analyzer_timings_ms: dict[str, float] = {}
            analyzer_phase_timings_ms: dict[str, list[dict[str, object]]] = {}
            stage_timings_ms = profiling_module.normalize_named_timings_ms(
                getattr(graph, "load_stage_timings", None), scale=1000.0
            )
            graphics_timings_ms = profiling_module.normalize_named_timings_ms(
                getattr(graph, "graphics_load_timings", None),
                scale=1000.0,
            )
            is_library = target_is_library_fn(cfg, project_bp, graph)
            context = build_analysis_context(
                project_bp,
                graph=graph,
                debug=debug_enabled(cfg),
                target_is_library=is_library,
                selected_issue_kinds=normalized_selected_issue_kinds,
                config=cfg,
                create_shared_artifacts=True,
            )
            emit_line(f"\n=== Target: {target_name} ===")
            flush_stdout()
            for spec in batch_analyzers:
                if is_library and spec.key in LIBRARY_SUPPRESSED_ANALYZER_KEYS:
                    target_analyzers.append(
                        ChecksAnalyzerResult(
                            key=spec.key,
                            name=str(spec.name),
                            status="skipped",
                            skip_reason="suppressed for library targets",
                        )
                    )
                    continue
                emit_line(f"\n=== {spec.name} ({spec.key}) ===")
                flush_stdout()
                analyzer_selected_issue_kinds = (
                    selected_issue_kind_tuple_result
                    if spec.key == "variables" or getattr(spec, "supports_selected_issue_kinds", False)
                    else None
                )
                if spec.key == "variables" or getattr(spec, "supports_selected_issue_kinds", False):
                    selected_issue_kind_values = format_selected_issue_kind_values(normalized_selected_issue_kinds)
                    if selected_issue_kind_values is not None:
                        emit_line(f"Running {spec.key} analyzer for issue kinds: {selected_issue_kind_values}")
                        flush_stdout()
                analyzer_started_at = perf_counter()
                try:
                    report = output_module.run_with_live_status(
                        _analysis_status_text(target_name, spec),
                        lambda spec=spec, context=context, graph=graph: (
                            report_cache_module.run_with_analysis_report_cache(
                                graph,
                                report_cache=report_cache,
                                analyzer_cache_key=spec.key,
                                run_fn=lambda spec=spec, context=context: (
                                    analysis_dispatch_module.run_registry_analyzer(spec, context)
                                ),
                                compute_analysis_report_cache_key_fn=compute_analysis_report_cache_key,
                            )
                        ),
                    )
                except KeyboardInterrupt:
                    analyzer_timings_ms[spec.key] = round((perf_counter() - analyzer_started_at) * 1000, 3)
                    target_analyzers.append(
                        ChecksAnalyzerResult(
                            key=spec.key,
                            name=str(spec.name),
                            status="cancelled",
                            duration_ms=analyzer_timings_ms[spec.key],
                            selected_issue_kinds=analyzer_selected_issue_kinds,
                        )
                    )
                    profiler.emit(
                        operation="checks",
                        target_name=target_name,
                        duration_ms=(perf_counter() - target_started_at) * 1000,
                        cancelled=True,
                        payload={
                            "selected_analyzers": [selected.key for selected in analyzers],
                            "analyzer_timings_ms": dict(analyzer_timings_ms),
                        },
                    )
                    target_results.append(
                        ChecksTargetResult(
                            target_name=target_name,
                            is_library=is_library,
                            analyzers=tuple(target_analyzers),
                            stage_timings_ms=stage_timings_ms or None,
                            graphics_timings_ms=graphics_timings_ms or None,
                        )
                    )
                    return ChecksRunResult(
                        output_lines=tuple(output_lines),
                        targets=tuple(target_results),
                        selected_analyzers=selected_analyzer_keys,
                        selected_issue_kinds=selected_issue_kind_tuple_result,
                        cancelled=True,
                    )
                analyzer_timings_ms[spec.key] = round((perf_counter() - analyzer_started_at) * 1000, 3)
                _rewrite_typedef_issue_paths(report, context.base_picture, graph)
                if context.shared_artifacts is not None:
                    context.shared_artifacts.derived_reports[spec.key] = report
                phase_timings_ms = profiling_module.normalize_phase_timings_ms(getattr(report, "phase_timings", None))
                if phase_timings_ms:
                    analyzer_phase_timings_ms[spec.key] = phase_timings_ms
                report = apply_rule_profile_to_report(spec.key, report, cfg)
                report = _filter_report_for_selected_issue_kinds(report, normalized_selected_issue_kinds)
                report = normalize_report_target_name(report, target_name)
                summary_text = report.summary()
                findings = extract_report_findings(report, default_name=target_name)
                emit_line(summary_text)
                target_analyzers.append(
                    ChecksAnalyzerResult(
                        key=spec.key,
                        name=str(spec.name),
                        status="completed",
                        summary=summary_text,
                        report_kind=type(report).__name__,
                        issue_count=_issue_count_for_report(report),
                        findings=findings,
                        duration_ms=analyzer_timings_ms[spec.key],
                        phase_timings_ms=tuple(analyzer_phase_timings_ms.get(spec.key, [])),
                        selected_issue_kinds=analyzer_selected_issue_kinds,
                    )
                )
            analyzer_bottleneck = profiling_module.bottleneck_from_named_timings(analyzer_timings_ms, kind="analyzer")
            analyzer_phase_bottleneck: dict[str, object] | None = None
            for analyzer_key, phase_timings in analyzer_phase_timings_ms.items():
                candidate = profiling_module.bottleneck_from_phase_timings(
                    phase_timings,
                    kind="analyzer-phase",
                    extra_fields={"analyzer_key": analyzer_key},
                )
                if candidate is None:
                    continue
                if analyzer_phase_bottleneck is None or (
                    cast(float, candidate["duration_ms"]) > cast(float, analyzer_phase_bottleneck["duration_ms"])
                ):
                    analyzer_phase_bottleneck = candidate
            payload: dict[str, object] = {
                "selected_analyzers": [spec.key for spec in analyzers],
                "analyzer_timings_ms": dict(analyzer_timings_ms),
            }
            if stage_timings_ms:
                payload["stage_timings_ms"] = stage_timings_ms
            if graphics_timings_ms:
                payload["graphics_timings_ms"] = graphics_timings_ms
            if analyzer_phase_timings_ms:
                payload["analyzer_phase_timings_ms"] = dict(analyzer_phase_timings_ms)
            if analyzer_bottleneck is not None:
                payload["analyzer_bottleneck"] = analyzer_bottleneck
                payload["bottleneck_kind"] = "analyzer"
                payload["bottleneck"] = analyzer_bottleneck
            if analyzer_phase_bottleneck is not None:
                payload["analyzer_phase_bottleneck"] = analyzer_phase_bottleneck
                payload["bottleneck_kind"] = "analyzer-phase"
                payload["bottleneck"] = analyzer_phase_bottleneck
            profiler.emit(
                operation="checks",
                target_name=target_name,
                duration_ms=(perf_counter() - target_started_at) * 1000,
                success=True,
                payload=payload,
            )
            shared_artifact_profile: str | None = None
            if _profile_analyzers_enabled() and context.shared_artifacts is not None:
                shared_artifact_profile = _shared_artifact_profile_text(target_name, context.shared_artifacts)
                emit_line(shared_artifact_profile)
            target_results.append(
                ChecksTargetResult(
                    target_name=target_name,
                    is_library=is_library,
                    analyzers=tuple(target_analyzers),
                    stage_timings_ms=stage_timings_ms or None,
                    graphics_timings_ms=graphics_timings_ms or None,
                    analyzer_bottleneck=analyzer_bottleneck,
                    analyzer_phase_bottleneck=analyzer_phase_bottleneck,
                    shared_artifact_profile=shared_artifact_profile,
                )
            )
        for whole_run_spec in whole_run_analyzers:
            whole_run_result = _run_whole_run_analyzer(whole_run_spec, cfg, normalized_selected_issue_kinds)
            if whole_run_result is None:
                continue
            emit_line(f"\n=== {whole_run_result.name} ({whole_run_result.key}) ===")
            if whole_run_result.summary:
                emit_line(whole_run_result.summary)
            target_results.append(
                ChecksTargetResult(
                    target_name=ICF_TARGET_NAME,
                    is_library=False,
                    analyzers=(whole_run_result,),
                )
            )
    except KeyboardInterrupt:
        return ChecksRunResult(
            output_lines=tuple(output_lines),
            targets=tuple(target_results),
            selected_analyzers=selected_analyzer_keys,
            selected_issue_kinds=selected_issue_kind_tuple_result,
            cancelled=True,
        )

    result = ChecksRunResult(
        output_lines=tuple(output_lines),
        targets=tuple(target_results),
        selected_analyzers=selected_analyzer_keys,
        selected_issue_kinds=selected_issue_kind_tuple_result,
    )
    if persist_run:
        _persist_run_result(result, cfg, started_at=run_started_at)
    return result


def run_checks_result(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    selected_issue_kinds: Set[str] | None = None,
    *,
    use_cache: bool = True,
    persist_run: bool = True,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    get_enabled_analyzers_fn: Callable[[], list[Any]] | None = None,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] | None = None,
) -> ChecksRunResult:
    result = collect_run_checks_result(
        cfg,
        selected_keys,
        selected_issue_kinds,
        use_cache=use_cache,
        persist_run=persist_run,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        target_is_library_fn=target_is_library_fn,
    )
    for line in result.output_lines:
        output_module.emit_output(line)
    return result


def run_checks(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    selected_issue_kinds: Set[str] | None = None,
    *,
    use_cache: bool = True,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    get_enabled_analyzers_fn: Callable[[], list[Any]] | None = None,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] | None = None,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    result = run_checks_result(
        cfg,
        selected_keys,
        selected_issue_kinds,
        use_cache=use_cache,
        persist_run=True,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        target_is_library_fn=target_is_library_fn,
    )
    if result.cancelled:
        output_module.handle_analysis_cancellation(pause_fn=pause_fn)
        return
    if pause_fn is not None:
        pause_fn()


def run_checks_menu(cfg: ConfigDict, *, run_checks_fn: Callable[[ConfigDict, list[str] | None], None]) -> None:
    run_checks_fn(cfg, None)
