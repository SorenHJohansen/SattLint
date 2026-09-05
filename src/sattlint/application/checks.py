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
from ..analyzers.rule_profiles import apply_rule_profile_to_report
from ..analyzers.variables import IssueKind
from ..cache import AnalysisReportCache, compute_analysis_report_cache_key, get_cache_dir
from ..config_types import ConfigDict
from ..core import telemetry as telemetry_module
from ..core.debug import debug_enabled
from ..core.terminal import flush_stdout
from ..models.project_graph import ProjectGraph
from ..project import cache as report_cache_module
from ..reporting.target_report import normalize_report_target_name
from ..reporting.variables_report import VariablesReport
from . import output as output_module
from . import project as project_application

LoadedProject = project_application.LoadedProject
LIBRARY_SUPPRESSED_ANALYZER_KEYS = frozenset({"picture-display-paths"})


@dataclass(frozen=True, slots=True)
class ChecksAnalyzerResult:
    key: str
    name: str
    status: str
    summary: str | None = None
    report_kind: str | None = None
    issue_count: int | None = None
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


def use_cache_enabled(cfg: ConfigDict) -> bool:
    return bool(cfg.get("use_cache", True))


def _iter_loaded_projects(cfg: ConfigDict) -> Iterator[LoadedProject]:
    return project_application.iter_loaded_projects(cfg)


def _target_is_library(cfg: ConfigDict, project_bp: BasePicture, graph: ProjectGraph) -> bool:
    return project_application.target_is_library(cfg, project_bp, graph)


def collect_run_checks_result(  # noqa: PLR0915
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    selected_issue_kinds: Set[str] | None = None,
    *,
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

    emit_line("\n--- Running checks ---")
    flush_stdout()
    report_cache = report_cache_module.create_analysis_report_cache(
        cfg,
        use_cache_enabled_fn=use_cache_enabled,
        debug_enabled_fn=debug_enabled,
        analysis_report_cache_cls=AnalysisReportCache,
        get_cache_dir_fn=get_cache_dir,
    )
    telemetry = telemetry_module.create_app_telemetry(cfg)
    try:
        for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
            target_analyzers: list[ChecksAnalyzerResult] = []
            target_started_at = perf_counter()
            analyzer_timings_ms: dict[str, float] = {}
            analyzer_phase_timings_ms: dict[str, list[dict[str, object]]] = {}
            stage_timings_ms = telemetry_module.normalize_named_timings_ms(
                getattr(graph, "load_stage_timings", None), scale=1000.0
            )
            graphics_timings_ms = telemetry_module.normalize_named_timings_ms(
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
            for spec in analyzers:
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
                    telemetry.emit(
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
                if context.shared_artifacts is not None:
                    context.shared_artifacts.reports_by_analyzer_key[spec.key] = report
                phase_timings_ms = telemetry_module.normalize_phase_timings_ms(getattr(report, "phase_timings", None))
                if phase_timings_ms:
                    analyzer_phase_timings_ms[spec.key] = phase_timings_ms
                report = apply_rule_profile_to_report(spec.key, report, cfg)
                report = _filter_report_for_selected_issue_kinds(report, normalized_selected_issue_kinds)
                report = normalize_report_target_name(report, target_name)
                summary_text = report.summary()
                emit_line(summary_text)
                target_analyzers.append(
                    ChecksAnalyzerResult(
                        key=spec.key,
                        name=str(spec.name),
                        status="completed",
                        summary=summary_text,
                        report_kind=type(report).__name__,
                        issue_count=_issue_count_for_report(report),
                        duration_ms=analyzer_timings_ms[spec.key],
                        phase_timings_ms=tuple(analyzer_phase_timings_ms.get(spec.key, [])),
                        selected_issue_kinds=analyzer_selected_issue_kinds,
                    )
                )
            analyzer_bottleneck = telemetry_module.bottleneck_from_named_timings(analyzer_timings_ms, kind="analyzer")
            analyzer_phase_bottleneck: dict[str, object] | None = None
            for analyzer_key, phase_timings in analyzer_phase_timings_ms.items():
                candidate = telemetry_module.bottleneck_from_phase_timings(
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
            telemetry.emit(
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
    except KeyboardInterrupt:
        return ChecksRunResult(
            output_lines=tuple(output_lines),
            targets=tuple(target_results),
            selected_analyzers=selected_analyzer_keys,
            selected_issue_kinds=selected_issue_kind_tuple_result,
            cancelled=True,
        )

    return ChecksRunResult(
        output_lines=tuple(output_lines),
        targets=tuple(target_results),
        selected_analyzers=selected_analyzer_keys,
        selected_issue_kinds=selected_issue_kind_tuple_result,
    )


def run_checks(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    selected_issue_kinds: Set[str] | None = None,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    get_enabled_analyzers_fn: Callable[[], list[Any]] | None = None,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] | None = None,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    result = collect_run_checks_result(
        cfg,
        selected_keys,
        selected_issue_kinds,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        target_is_library_fn=target_is_library_fn,
    )
    for line in result.output_lines:
        output_module.emit_output(line)
    if result.cancelled:
        output_module.handle_analysis_cancellation(pause_fn=pause_fn)
        return
    if pause_fn is not None:
        pause_fn()


def run_checks_menu(cfg: ConfigDict, *, run_checks_fn: Callable[[ConfigDict, list[str] | None], None]) -> None:
    run_checks_fn(cfg, None)
