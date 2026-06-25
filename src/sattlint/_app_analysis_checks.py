from __future__ import annotations

from collections.abc import Callable, Iterator, Set
from time import perf_counter
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import _app_analysis_reporting as analysis_reporting_module
from . import app_analysis as shared
from . import app_telemetry as telemetry_module
from .analyzers.framework import build_analysis_context
from .analyzers.rule_profiles import apply_rule_profile_to_report
from .config_types import ConfigDict
from .models.project_graph import ProjectGraph

LoadedProject = shared.LoadedProject
ChecksRunResult = shared.ChecksRunResult


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
        iter_loaded_projects_fn = shared.iter_loaded_projects
    if get_enabled_analyzers_fn is None:
        get_enabled_analyzers_fn = shared.get_enabled_analyzers
    if target_is_library_fn is None:
        target_is_library_fn = shared.target_is_library

    output_lines: list[str] = []
    target_results: list[shared.ChecksTargetResult] = []

    def emit_line(message: str) -> None:
        output_lines.append(message)

    analyzers = list(
        shared.get_cli_dispatch_analyzers(
            selected_keys=selected_keys,
            get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        )
    )
    normalized_selected_issue_kinds = shared.normalize_selected_issue_kind_values(selected_issue_kinds)
    selected_analyzer_keys = tuple(spec.key for spec in analyzers)
    selected_issue_kind_tuple = shared.selected_issue_kind_tuple(normalized_selected_issue_kinds)

    if not analyzers:
        emit_line("❌ No matching checks found")
        return shared.ChecksRunResult(
            output_lines=tuple(output_lines),
            selected_analyzers=selected_analyzer_keys,
            selected_issue_kinds=selected_issue_kind_tuple,
        )

    emit_line("\n--- Running checks ---")
    shared.flush_stdout()
    report_cache = analysis_reporting_module.create_analysis_report_cache(
        cfg,
        use_cache_enabled_fn=shared.use_cache_enabled,
        debug_enabled_fn=shared.debug_enabled,
        analysis_report_cache_cls=shared.AnalysisReportCache,
        get_cache_dir_fn=shared.get_cache_dir,
    )
    telemetry = telemetry_module.create_app_telemetry(cfg)
    try:
        for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
            target_analyzers: list[shared.ChecksAnalyzerResult] = []
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
            target_is_library = target_is_library_fn(cfg, project_bp, graph)
            context = build_analysis_context(
                project_bp,
                graph=graph,
                debug=shared.debug_enabled(cfg),
                target_is_library=target_is_library,
                selected_issue_kinds=normalized_selected_issue_kinds,
                config=cfg,
                create_shared_artifacts=True,
            )
            emit_line(f"\n=== Target: {target_name} ===")
            shared.flush_stdout()
            for spec in analyzers:
                if target_is_library and spec.key in shared.LIBRARY_SUPPRESSED_ANALYZER_KEYS:
                    target_analyzers.append(
                        shared.ChecksAnalyzerResult(
                            key=spec.key,
                            name=str(spec.name),
                            status="skipped",
                            skip_reason="suppressed for library targets",
                        )
                    )
                    continue
                emit_line(f"\n=== {spec.name} ({spec.key}) ===")
                shared.flush_stdout()
                analyzer_selected_issue_kinds = (
                    selected_issue_kind_tuple
                    if spec.key == "variables" or getattr(spec, "supports_selected_issue_kinds", False)
                    else None
                )
                if spec.key == "variables" or getattr(spec, "supports_selected_issue_kinds", False):
                    selected_issue_kind_values = shared.format_selected_issue_kind_values(
                        normalized_selected_issue_kinds
                    )
                    if selected_issue_kind_values is not None:
                        emit_line(f"Running {spec.key} analyzer for issue kinds: {selected_issue_kind_values}")
                        shared.flush_stdout()
                analyzer_started_at = perf_counter()
                try:
                    report = shared.run_with_live_status(
                        shared.analysis_status_text(target_name, spec),
                        lambda spec=spec, context=context, graph=graph: (
                            analysis_reporting_module.run_with_analysis_report_cache(
                                graph,
                                report_cache=report_cache,
                                analyzer_cache_key=spec.key,
                                run_fn=lambda spec=spec, context=context: shared.run_registry_analyzer(spec, context),
                                compute_analysis_report_cache_key_fn=shared.compute_analysis_report_cache_key,
                            )
                        ),
                    )
                except KeyboardInterrupt:
                    analyzer_timings_ms[spec.key] = round((perf_counter() - analyzer_started_at) * 1000, 3)
                    target_analyzers.append(
                        shared.ChecksAnalyzerResult(
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
                        shared.ChecksTargetResult(
                            target_name=target_name,
                            is_library=target_is_library,
                            analyzers=tuple(target_analyzers),
                            stage_timings_ms=stage_timings_ms or None,
                            graphics_timings_ms=graphics_timings_ms or None,
                        )
                    )
                    return shared.ChecksRunResult(
                        output_lines=tuple(output_lines),
                        targets=tuple(target_results),
                        selected_analyzers=selected_analyzer_keys,
                        selected_issue_kinds=selected_issue_kind_tuple,
                        cancelled=True,
                    )
                analyzer_timings_ms[spec.key] = round((perf_counter() - analyzer_started_at) * 1000, 3)
                if context.shared_artifacts is not None:
                    context.shared_artifacts.reports_by_analyzer_key[spec.key] = report
                phase_timings_ms = telemetry_module.normalize_phase_timings_ms(getattr(report, "phase_timings", None))
                if phase_timings_ms:
                    analyzer_phase_timings_ms[spec.key] = phase_timings_ms
                report = apply_rule_profile_to_report(spec.key, report, cfg)
                report = shared.filter_report_for_selected_issue_kinds(report, normalized_selected_issue_kinds)
                report = analysis_reporting_module.normalize_report_target_name(report, target_name)
                summary_text = report.summary()
                emit_line(summary_text)
                target_analyzers.append(
                    shared.ChecksAnalyzerResult(
                        key=spec.key,
                        name=str(spec.name),
                        status="completed",
                        summary=summary_text,
                        report_kind=type(report).__name__,
                        issue_count=shared.issue_count_for_report(report),
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
            if shared.profile_analyzers_enabled() and context.shared_artifacts is not None:
                shared_artifact_profile = shared.shared_artifact_profile_text(target_name, context.shared_artifacts)
                emit_line(shared_artifact_profile)
            target_results.append(
                shared.ChecksTargetResult(
                    target_name=target_name,
                    is_library=target_is_library,
                    analyzers=tuple(target_analyzers),
                    stage_timings_ms=stage_timings_ms or None,
                    graphics_timings_ms=graphics_timings_ms or None,
                    analyzer_bottleneck=analyzer_bottleneck,
                    analyzer_phase_bottleneck=analyzer_phase_bottleneck,
                    shared_artifact_profile=shared_artifact_profile,
                )
            )
    except KeyboardInterrupt:
        return shared.ChecksRunResult(
            output_lines=tuple(output_lines),
            targets=tuple(target_results),
            selected_analyzers=selected_analyzer_keys,
            selected_issue_kinds=selected_issue_kind_tuple,
            cancelled=True,
        )

    return shared.ChecksRunResult(
        output_lines=tuple(output_lines),
        targets=tuple(target_results),
        selected_analyzers=selected_analyzer_keys,
        selected_issue_kinds=selected_issue_kind_tuple,
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
        shared.emit_output(line)
    if result.cancelled:
        shared.handle_analysis_cancellation(pause_fn=pause_fn)
        return
    if pause_fn is not None:
        pause_fn()


def run_checks_menu(cfg: ConfigDict, *, run_checks_fn: Callable[[ConfigDict, list[str] | None], None]) -> None:
    run_checks_fn(cfg, None)
