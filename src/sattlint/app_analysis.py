from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable, Iterator, Set
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import _app_analysis_loading as analysis_loading_module
from . import _app_analysis_menus as analysis_menus_module
from . import _app_analysis_reporting as analysis_reporting_module
from . import _app_analysis_variable_analyses as analysis_variable_analyses_module
from . import app_support as app_support_module
from . import app_telemetry as telemetry_module
from . import cache as cache_module
from . import console as console_module
from . import engine as engine_module
from ._app_debug import debug_enabled, log_debug_exception
from .analyzers import variable_usage_reporting as variables_reporting_module
from .analyzers.comment_code import analyze_comment_code_files
from .analyzers.framework import AnalysisContext, AnalysisSharedArtifacts
from .analyzers.icf import parse_icf_file, validate_icf_entries_against_program
from .analyzers.mms import analyze_mms_interface_variables
from .analyzers.modules import analyze_module_duplicates, compare_modules, debug_module_structure, find_modules_by_name
from .analyzers.registry import (
    SEMANTIC_LAYER_ANALYZER_KEY,
    canonicalize_analyzer_key,
    get_default_cli_analyzers,
)
from .analyzers.rule_profiles import apply_rule_profile_to_report
from .analyzers.shadowing import analyze_shadowing
from .analyzers.variable_usage_reporting import debug_variable_usage
from .analyzers.variables import IssueKind, analyze_variables, filter_variable_report
from .app_interaction import MenuInteraction
from .cache import AnalysisReportCache, ASTCache
from .casefolding import casefold_equal, casefold_key
from .models.project_graph import ProjectGraph
from .reporting.variables_report import DEFAULT_VARIABLE_ANALYSIS_KINDS, VariablesReport

ConfigDict = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]
VariableAnalysisSelection = analysis_variable_analyses_module.VariableAnalysisSelection
VariableAnalysisMap = analysis_variable_analyses_module.VariableAnalysisMap
VARIABLE_ANALYSES = analysis_variable_analyses_module.VARIABLE_ANALYSES
HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS = analysis_variable_analyses_module.HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS
LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS = analysis_variable_analyses_module.LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS
app_support = cast(Any, app_support_module)
cache = cast(Any, cache_module)
engine = cast(Any, engine_module)
emit_output: Callable[..., None] = console_module.print_output  # type: ignore[assignment]
compute_cache_key: Callable[[ConfigDict], str] = cache.compute_cache_key
compute_analysis_report_cache_key: Callable[[str, str], str] = cache.compute_analysis_report_cache_key
get_cache_dir: Callable[[], Path] = cache.get_cache_dir
log = logging.getLogger("SattLint")

_DRAFT_SOURCE_SUFFIXES = frozenset({".s", ".l"})
_OFFICIAL_SOURCE_SUFFIXES = frozenset({".x", ".z"})


def _target_validation_warnings(target_name: str, warnings: list[str]) -> list[str]:
    return cast(list[str], app_support.target_validation_warnings(target_name, warnings))


def _print_validation_warnings(warnings: list[str], *, limit: int = 12) -> None:
    app_support.print_validation_warnings(warnings, print_fn=emit_output, limit=limit)


def _flush_stdout() -> None:
    flush = getattr(sys.stdout, "flush", None)
    if callable(flush):
        flush()


def _format_selected_issue_kind_values(selected_issue_kinds: Set[IssueKind] | None) -> str | None:
    if not selected_issue_kinds:
        return None
    return ", ".join(kind.value for kind in sorted(selected_issue_kinds, key=lambda item: item.value))


def _get_analyzed_targets(cfg: ConfigDict) -> list[str]:
    return analysis_loading_module.get_analyzed_targets(cfg, app_support=app_support)


def _require_analyzed_targets(cfg: ConfigDict) -> list[str]:
    return analysis_loading_module.require_analyzed_targets(cfg, app_support=app_support)


def _cache_key_for_target(cfg: ConfigDict, target_name: str) -> str:
    return analysis_loading_module.cache_key_for_target(
        cfg,
        target_name,
        compute_cache_key_fn=compute_cache_key,
    )


def _iter_loaded_projects(
    cfg: ConfigDict,
    *,
    use_cache: bool = True,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _require_analyzed_targets,
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]] | None = None,
) -> Iterator[LoadedProject]:
    return analysis_loading_module.iter_loaded_projects(
        cfg,
        use_cache=use_cache,
        require_analyzed_targets_fn=require_analyzed_targets_fn,
        load_project_fn=load_project if load_project_fn is None else load_project_fn,
        emit_output_fn=emit_output,
    )


def iter_loaded_projects(
    cfg: ConfigDict,
    *,
    use_cache: bool = True,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _require_analyzed_targets,
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]] | None = None,
) -> Iterator[LoadedProject]:
    return _iter_loaded_projects(
        cfg,
        use_cache=use_cache,
        require_analyzed_targets_fn=require_analyzed_targets_fn,
        load_project_fn=load_project_fn,
    )


def _source_paths_for_current_target(project_bp: BasePicture, graph: ProjectGraph) -> set[Path]:
    return analysis_loading_module.source_paths_for_current_target(
        project_bp,
        graph,
        casefold_equal_fn=casefold_equal,
        casefold_key_fn=casefold_key,
    )


def source_paths_for_current_target(project_bp: BasePicture, graph: ProjectGraph) -> set[Path]:
    return _source_paths_for_current_target(project_bp, graph)


def _target_is_library(cfg: ConfigDict, project_bp: BasePicture, graph: ProjectGraph) -> bool:
    return analysis_loading_module.target_is_library(
        cfg,
        project_bp,
        graph,
        source_paths_for_current_target_fn=_source_paths_for_current_target,
        is_within_directory_fn=engine.is_within_directory,
    )


def target_is_library(cfg: ConfigDict, project_bp: BasePicture, graph: ProjectGraph) -> bool:
    return _target_is_library(cfg, project_bp, graph)


def load_project(
    cfg: ConfigDict,
    target_name: str | None = None,
    *,
    use_cache: bool = True,
    use_file_ast_cache: bool = True,
    refresh_mode: str = "full",
    collect_stage_timings: bool = False,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _require_analyzed_targets,
    cache_key_for_target_fn: Callable[[ConfigDict, str], str] = _cache_key_for_target,
    target_load_error_factory: Callable[..., Exception] | None = None,
    get_cache_dir_fn: Callable[[], Path] = get_cache_dir,
) -> tuple[BasePicture, ProjectGraph]:
    return analysis_loading_module.load_project_with_live_status(
        cfg,
        target_name=target_name,
        use_cache=use_cache,
        use_file_ast_cache=use_file_ast_cache,
        refresh_mode=refresh_mode,
        collect_stage_timings=collect_stage_timings,
        require_analyzed_targets_fn=require_analyzed_targets_fn,
        cache_key_for_target_fn=cache_key_for_target_fn,
        target_load_error_factory=target_load_error_factory,
        get_cache_dir_fn=get_cache_dir_fn,
        ast_cache_cls=ASTCache,
        engine_module=engine,
        live_status_line_factory=console_module.live_status_line,
    )


def load_program_ast(
    cfg: ConfigDict,
    program_name: str,
    *,
    force_dependency_resolution: bool = False,
) -> tuple[BasePicture, ProjectGraph]:
    return analysis_loading_module.load_program_ast_with_live_status(
        cfg,
        program_name,
        force_dependency_resolution=force_dependency_resolution,
        engine_module=engine,
        live_status_line_factory=console_module.live_status_line,
    )


def force_refresh_ast(
    cfg: ConfigDict,
    *,
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _get_analyzed_targets,
    cache_key_for_target_fn: Callable[[ConfigDict, str], str] = _cache_key_for_target,
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]] = load_project,
    ast_cache_cls: type[ASTCache] = ASTCache,
    get_cache_dir_fn: Callable[[], Path] = get_cache_dir,
) -> tuple[BasePicture, ProjectGraph] | None:
    return analysis_loading_module.force_refresh_ast(
        cfg,
        get_analyzed_targets_fn=get_analyzed_targets_fn,
        cache_key_for_target_fn=cache_key_for_target_fn,
        load_project_fn=load_project_fn,
        ast_cache_cls=ast_cache_cls,
        get_cache_dir_fn=get_cache_dir_fn,
        emit_output_fn=emit_output,
    )


def ensure_ast_cache(
    cfg: ConfigDict,
    *,
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _get_analyzed_targets,
    cache_key_for_target_fn: Callable[[ConfigDict, str], str] = _cache_key_for_target,
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]] = load_project,
    ast_cache_cls: type[ASTCache] = ASTCache,
    get_cache_dir_fn: Callable[[], Path] = get_cache_dir,
) -> bool:
    return analysis_loading_module.ensure_ast_cache(
        cfg,
        get_analyzed_targets_fn=get_analyzed_targets_fn,
        cache_key_for_target_fn=cache_key_for_target_fn,
        load_project_fn=load_project_fn,
        ast_cache_cls=ast_cache_cls,
        get_cache_dir_fn=get_cache_dir_fn,
        emit_output_fn=emit_output,
    )


def _use_cache_enabled(cfg: ConfigDict) -> bool:
    return bool(cfg.get("use_cache", True))


def _run_with_live_status(status_text: str, run_fn: Callable[[], Any]) -> Any:
    with console_module.live_status_line() as status_update_fn:
        status_update_fn(status_text)
        return run_fn()


def run_variable_analysis(
    cfg: ConfigDict,
    kinds: set[IssueKind] | None,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] | None = None,
    analyze_variables_fn: Callable[..., VariablesReport] | None = None,
    analyze_shadowing_fn: Callable[..., VariablesReport] | None = None,
    filter_variable_report_fn: Callable[[VariablesReport, set[IssueKind]], VariablesReport] | None = None,
    print_validation_warnings_fn: Callable[[list[str]], None] | None = None,
    target_validation_warnings_fn: Callable[[str, list[str]], list[str]] | None = None,
    pause_fn: Callable[[], None] | None = None,
):
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = _iter_loaded_projects
    if target_is_library_fn is None:
        target_is_library_fn = _target_is_library
    if analyze_variables_fn is None:
        analyze_variables_fn = analyze_variables
    if analyze_shadowing_fn is None:
        analyze_shadowing_fn = analyze_shadowing
    if filter_variable_report_fn is None:
        filter_variable_report_fn = filter_variable_report
    if print_validation_warnings_fn is None:
        print_validation_warnings_fn = _print_validation_warnings
    if target_validation_warnings_fn is None:
        target_validation_warnings_fn = _target_validation_warnings

    def _merge_reports(*reports: VariablesReport) -> VariablesReport:
        basepicture_name = reports[0].basepicture_name
        issues: list[Any] = []
        visible_kinds: set[IssueKind] = set()
        include_empty_sections = False
        phase_timings: list[dict[str, str | float]] = []

        for report in reports:
            issues.extend(report.issues)
            if report.visible_kinds is not None:
                visible_kinds.update(report.visible_kinds)
            include_empty_sections = include_empty_sections or report.include_empty_sections
            phase_timings.extend(getattr(report, "phase_timings", []))

        return VariablesReport(
            basepicture_name=basepicture_name,
            issues=issues,
            selected_issue_kinds=(frozenset(visible_kinds) if kinds is not None and visible_kinds else None),
            visible_kinds=frozenset(visible_kinds) if visible_kinds else None,
            include_empty_sections=include_empty_sections,
            phase_timings=phase_timings,
        )

    requested_kinds = set(DEFAULT_VARIABLE_ANALYSIS_KINDS) | {IssueKind.SHADOWING} if kinds is None else set(kinds)
    cfg = cfg | {"include_reverse_library_consumers": IssueKind.UNUSED_DATATYPE_FIELD in requested_kinds}
    report_cache = analysis_reporting_module.create_analysis_report_cache(
        cfg,
        use_cache_enabled_fn=_use_cache_enabled,
        debug_enabled_fn=debug_enabled,
        analysis_report_cache_cls=AnalysisReportCache,
        get_cache_dir_fn=get_cache_dir,
    )
    telemetry = telemetry_module.create_app_telemetry(cfg)

    produced_output = False
    try:
        for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
            produced_output = True
            started_at = perf_counter()
            target_is_library = target_is_library_fn(cfg, project_bp, graph)
            include_shadowing = IssueKind.SHADOWING in requested_kinds
            standard_kinds = requested_kinds - {IssueKind.SHADOWING}

            if standard_kinds:
                with console_module.live_status_line() as status_update_fn:
                    status_update_fn(f"Analyzing variable issues for {target_name}")
                    report = analysis_reporting_module.run_with_analysis_report_cache(
                        graph,
                        report_cache=report_cache,
                        analyzer_cache_key=(
                            f"variables:{analysis_reporting_module.variable_issue_kinds_cache_key(standard_kinds)}"
                        ),
                        run_fn=lambda project_bp=project_bp, graph=graph, status_update_fn=status_update_fn, target_is_library=target_is_library, standard_kinds=standard_kinds: (
                            analyze_variables_fn(
                                project_bp,
                                debug=debug_enabled(cfg),
                                unavailable_libraries=analysis_reporting_module.unavailable_libraries(graph),
                                analyzed_target_is_library=target_is_library,
                                selected_issue_kinds=standard_kinds,
                                config=cfg,
                                status_update_fn=status_update_fn,
                            )
                        ),
                        compute_analysis_report_cache_key_fn=compute_analysis_report_cache_key,
                    )
            else:
                report = VariablesReport(
                    basepicture_name=getattr(getattr(project_bp, "header", None), "name", target_name),
                    issues=[],
                    selected_issue_kinds=frozenset(standard_kinds) if kinds is not None else None,
                    visible_kinds=frozenset(),
                    include_empty_sections=False,
                )

            if standard_kinds:
                report = filter_variable_report_fn(report, standard_kinds)

            if include_shadowing:
                shadowing_report = _run_with_live_status(
                    f"Analyzing variable shadowing for {target_name}",
                    lambda project_bp=project_bp, graph=graph: analysis_reporting_module.run_with_analysis_report_cache(
                        graph,
                        report_cache=report_cache,
                        analyzer_cache_key="variables:shadowing",
                        run_fn=lambda project_bp=project_bp, graph=graph: analyze_shadowing_fn(
                            project_bp,
                            debug=debug_enabled(cfg),
                            unavailable_libraries=analysis_reporting_module.unavailable_libraries(graph),
                        ),
                        compute_analysis_report_cache_key_fn=compute_analysis_report_cache_key,
                    ),
                )
                if requested_kinds == {IssueKind.SHADOWING}:
                    report = shadowing_report
                elif standard_kinds:
                    report = _merge_reports(report, shadowing_report)

            report = analysis_reporting_module.normalize_report_target_name(report, target_name)
            report = analysis_reporting_module.attach_variable_report_metadata(
                report,
                project_bp,
                graph,
                select_report_source_path_fn=lambda project_bp, graph: (
                    analysis_reporting_module.select_report_source_path(
                        project_bp,
                        graph,
                        source_paths_for_current_target_fn=_source_paths_for_current_target,
                        casefold_equal_fn=casefold_equal,
                    )
                ),
                source_version_label_fn=lambda project_bp, source_path: analysis_reporting_module.source_version_label(
                    project_bp,
                    source_path,
                    draft_source_suffixes=_DRAFT_SOURCE_SUFFIXES,
                    official_source_suffixes=_OFFICIAL_SOURCE_SUFFIXES,
                ),
                source_last_changed_fn=analysis_reporting_module.source_last_changed,
            )
            emit_output(f"\n=== Target: {target_name} ===")
            print_validation_warnings_fn(target_validation_warnings_fn(target_name, getattr(graph, "warnings", [])))
            emit_output(report.summary())
            phase_timings_ms = telemetry_module.normalize_phase_timings_ms(getattr(report, "phase_timings", None))
            phase_bottleneck = telemetry_module.bottleneck_from_phase_timings(phase_timings_ms, kind="phase")
            stage_timings_ms = telemetry_module.normalize_named_timings_ms(
                getattr(graph, "load_stage_timings", None), scale=1000.0
            )
            graphics_timings_ms = telemetry_module.normalize_named_timings_ms(
                getattr(graph, "graphics_load_timings", None),
                scale=1000.0,
            )
            payload: dict[str, object] = {
                "requested_issue_kinds": sorted(kind.value for kind in requested_kinds),
                "issue_count": len(getattr(report, "issues", [])),
                "shadowing_requested": include_shadowing,
            }
            if stage_timings_ms:
                payload["stage_timings_ms"] = stage_timings_ms
            if graphics_timings_ms:
                payload["graphics_timings_ms"] = graphics_timings_ms
            if phase_timings_ms:
                payload["phase_timings_ms"] = phase_timings_ms
            if phase_bottleneck is not None:
                payload["phase_bottleneck"] = phase_bottleneck
                payload["bottleneck_kind"] = "phase"
                payload["bottleneck"] = phase_bottleneck
            telemetry.emit(
                operation="variable-analysis",
                target_name=target_name,
                duration_ms=(perf_counter() - started_at) * 1000,
                success=True,
                payload=payload,
            )
    except KeyboardInterrupt:
        _handle_analysis_cancellation(pause_fn=pause_fn)
        return
    if not produced_output:
        emit_output("\nNo variable analysis output was produced because no target loaded successfully.")

    if pause_fn is not None:
        pause_fn()


def run_datatype_usage_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = _iter_loaded_projects

    emit_output("\n--- Datatype Usage Analysis ---")
    emit_output("Enter the variable name to analyze:")
    var_name = interaction.prompt("Variable name", None).strip() if interaction is not None else input("> ").strip()

    if not var_name:
        emit_output("❌ No variable name provided")
        if pause_fn is not None:
            pause_fn()
        return

    for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
        try:
            report = _run_with_live_status(
                f"Analyzing datatype usage for {target_name}: {var_name}",
                lambda project_bp=project_bp, graph=graph: variables_reporting_module.report_datatype_usage(
                    project_bp,
                    var_name,
                    debug=debug_enabled(cfg),
                    unavailable_libraries=analysis_reporting_module.unavailable_libraries(graph),
                ),
            )
            emit_output(f"\n=== Target: {target_name} ===")
            emit_output(report)
        except Exception as exc:
            log_debug_exception(
                cfg,
                f"Datatype usage analysis failed for target {target_name!r} and variable {var_name!r}",
                logger=log,
            )
            emit_output(f"❌ Error during analysis for {target_name}: {exc}")

    if pause_fn is not None:
        pause_fn()


def variable_usage_submenu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    quit_app_fn: Callable[[], None],
    run_variable_analysis_fn: Callable[[ConfigDict, set[IssueKind] | None], None],
    run_datatype_usage_analysis_fn: Callable[[ConfigDict], None],
    run_debug_variable_usage_fn: Callable[[ConfigDict], None],
    run_module_localvar_analysis_fn: Callable[[ConfigDict], None],
    pause_fn: Callable[[], None],
) -> None:
    analysis_menus_module.variable_usage_submenu(
        cfg,
        clear_screen_fn=clear_screen_fn,
        quit_app_fn=quit_app_fn,
        run_variable_analysis_fn=run_variable_analysis_fn,
        run_datatype_usage_analysis_fn=run_datatype_usage_analysis_fn,
        run_debug_variable_usage_fn=run_debug_variable_usage_fn,
        run_module_localvar_analysis_fn=run_module_localvar_analysis_fn,
        pause_fn=pause_fn,
        emit_output_fn=emit_output,
    )


def module_analysis_submenu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    run_module_duplicates_analysis_fn: Callable[[ConfigDict], None],
    run_module_find_by_name_fn: Callable[[ConfigDict], None],
    run_module_tree_debug_fn: Callable[[ConfigDict], None],
    run_graphics_rules_validation_fn: Callable[[ConfigDict], None],
    pause_fn: Callable[[], None],
) -> None:
    analysis_menus_module.module_analysis_submenu(
        cfg,
        clear_screen_fn=clear_screen_fn,
        print_menu_fn=print_menu_fn,
        menu_option_factory=menu_option_factory,
        quit_app_fn=quit_app_fn,
        run_module_duplicates_analysis_fn=run_module_duplicates_analysis_fn,
        run_module_find_by_name_fn=run_module_find_by_name_fn,
        run_module_tree_debug_fn=run_module_tree_debug_fn,
        run_graphics_rules_validation_fn=run_graphics_rules_validation_fn,
        pause_fn=pause_fn,
        emit_output_fn=emit_output,
    )


def interface_communication_submenu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    run_mms_interface_analysis_fn: Callable[[ConfigDict], None],
    run_icf_validation_fn: Callable[[ConfigDict], None],
    run_icf_formatter_fn: Callable[[ConfigDict], None],
    pause_fn: Callable[[], None],
) -> None:
    analysis_menus_module.interface_communication_submenu(
        cfg,
        clear_screen_fn=clear_screen_fn,
        print_menu_fn=print_menu_fn,
        menu_option_factory=menu_option_factory,
        quit_app_fn=quit_app_fn,
        run_mms_interface_analysis_fn=run_mms_interface_analysis_fn,
        run_icf_validation_fn=run_icf_validation_fn,
        run_icf_formatter_fn=run_icf_formatter_fn,
        pause_fn=pause_fn,
        emit_output_fn=emit_output,
    )


def code_quality_submenu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    run_comment_code_analysis_fn: Callable[[ConfigDict], None],
    pause_fn: Callable[[], None],
) -> None:
    analysis_menus_module.code_quality_submenu(
        cfg,
        clear_screen_fn=clear_screen_fn,
        print_menu_fn=print_menu_fn,
        menu_option_factory=menu_option_factory,
        quit_app_fn=quit_app_fn,
        run_comment_code_analysis_fn=run_comment_code_analysis_fn,
        pause_fn=pause_fn,
        emit_output_fn=emit_output,
    )


def analyzer_catalog_menu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    get_enabled_analyzers_fn: Callable[[], list[Any]],
    run_checks_fn: Callable[[ConfigDict, list[str] | None], None],
    pause_fn: Callable[[], None],
) -> None:
    analysis_menus_module.analyzer_catalog_menu(
        cfg,
        clear_screen_fn=clear_screen_fn,
        print_menu_fn=print_menu_fn,
        menu_option_factory=menu_option_factory,
        quit_app_fn=quit_app_fn,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        run_checks_fn=run_checks_fn,
        pause_fn=pause_fn,
        emit_output_fn=emit_output,
    )


def advanced_analysis_menu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    run_datatype_usage_analysis_fn: Callable[[ConfigDict], None],
    run_debug_variable_usage_fn: Callable[[ConfigDict], None],
    run_module_localvar_analysis_fn: Callable[[ConfigDict], None],
    pause_fn: Callable[[], None],
) -> None:
    analysis_menus_module.advanced_analysis_menu(
        cfg,
        clear_screen_fn=clear_screen_fn,
        print_menu_fn=print_menu_fn,
        menu_option_factory=menu_option_factory,
        quit_app_fn=quit_app_fn,
        run_datatype_usage_analysis_fn=run_datatype_usage_analysis_fn,
        run_debug_variable_usage_fn=run_debug_variable_usage_fn,
        run_module_localvar_analysis_fn=run_module_localvar_analysis_fn,
        pause_fn=pause_fn,
        emit_output_fn=emit_output,
    )


def analysis_menu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    run_checks_fn: Callable[[ConfigDict, list[str] | None], None],
    variable_usage_submenu_fn: Callable[[ConfigDict], None],
    module_analysis_submenu_fn: Callable[[ConfigDict], None],
    interface_communication_submenu_fn: Callable[[ConfigDict], None],
    code_quality_submenu_fn: Callable[[ConfigDict], None],
    analyzer_catalog_menu_fn: Callable[[ConfigDict], None],
    advanced_analysis_menu_fn: Callable[[ConfigDict], None],
    summarize_targets_fn: Callable[[ConfigDict], str],
    pause_fn: Callable[[], None],
) -> None:
    analysis_menus_module.analysis_menu(
        cfg,
        clear_screen_fn=clear_screen_fn,
        print_menu_fn=print_menu_fn,
        menu_option_factory=menu_option_factory,
        quit_app_fn=quit_app_fn,
        run_checks_fn=run_checks_fn,
        variable_usage_submenu_fn=variable_usage_submenu_fn,
        module_analysis_submenu_fn=module_analysis_submenu_fn,
        interface_communication_submenu_fn=interface_communication_submenu_fn,
        code_quality_submenu_fn=code_quality_submenu_fn,
        analyzer_catalog_menu_fn=analyzer_catalog_menu_fn,
        advanced_analysis_menu_fn=advanced_analysis_menu_fn,
        summarize_targets_fn=summarize_targets_fn,
        pause_fn=pause_fn,
        emit_output_fn=emit_output,
    )


def _parse_index_selection(selection: str, max_index: int) -> list[int]:
    return analysis_menus_module.parse_index_selection(selection, max_index)


def run_module_duplicates_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    emit_output("\n--- Compare Module Variants ---")
    emit_output("Enter module name(s) to compare (comma-separated):")
    raw_names = interaction.prompt("Module name(s)", None).strip() if interaction is not None else input("> ").strip()
    module_names = [name.strip() for name in raw_names.split(",") if name.strip()]

    if not module_names:
        emit_output("❌ No module name provided")
        if pause_fn is not None:
            pause_fn()
        return

    for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
        emit_output(f"\n=== Target: {target_name} ===")
        for module_name in module_names:
            try:
                matches = _run_with_live_status(
                    f"Searching module variants in {target_name}: {module_name}",
                    lambda project_bp=project_bp, module_name=module_name: find_modules_by_name(
                        project_bp,
                        module_name,
                        debug=debug_enabled(cfg),
                    ),
                )
                if not matches:
                    emit_output(f"\n⚠ No modules found with name {module_name!r}.")
                    continue

                emit_output(f"\nFound {len(matches)} instance(s) for {module_name!r}:")
                for idx, (path, module) in enumerate(matches, 1):
                    datecode = getattr(module, "datecode", None)
                    datecode_txt = f" (DateCode: {datecode})" if datecode else ""
                    emit_output(f"  {idx}) {' -> '.join(path)}{datecode_txt}")

                emit_output("\nSelect instances to compare (e.g., 6,7).")
                emit_output("Press Enter to compare all instances.")
                selection = (
                    interaction.prompt("Instances to compare", None).strip()
                    if interaction is not None
                    else input("> ").strip()
                )

                if selection:
                    indices = _parse_index_selection(selection, len(matches))
                    if len(indices) < 2:
                        emit_output("⚠ Need at least two instances to compare; skipping.")
                        continue
                    selected = [matches[i - 1] for i in indices]
                    result = _run_with_live_status(
                        f"Comparing module variants in {target_name}: {module_name}",
                        lambda selected=selected: compare_modules(selected),
                    )
                else:
                    result = _run_with_live_status(
                        f"Comparing module variants in {target_name}: {module_name}",
                        lambda project_bp=project_bp, module_name=module_name: analyze_module_duplicates(
                            project_bp,
                            module_name,
                            debug=debug_enabled(cfg),
                        ),
                    )

                emit_output("\n" + result.summary())
            except Exception as exc:
                log_debug_exception(
                    cfg,
                    f"Module duplicate analysis failed for target {target_name!r} and module {module_name!r}",
                    logger=log,
                )
                emit_output(f"❌ Error during analysis for {module_name!r}: {exc}")

    if pause_fn is not None:
        pause_fn()


def run_module_find_by_name(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    emit_output("\n--- Find Module Instances ---")
    emit_output("Enter module name(s) to search for (comma-separated):")
    raw_names = interaction.prompt("Module name(s)", None).strip() if interaction is not None else input("> ").strip()
    module_names = [name.strip() for name in raw_names.split(",") if name.strip()]

    if not module_names:
        emit_output("❌ No module name provided")
        if pause_fn is not None:
            pause_fn()
        return

    try:
        for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
            emit_output(f"\n=== Target: {target_name} ===")
            for module_name in module_names:
                matches = _run_with_live_status(
                    f"Finding module instances in {target_name}: {module_name}",
                    lambda project_bp=project_bp, module_name=module_name: find_modules_by_name(
                        project_bp,
                        module_name,
                        debug=debug_enabled(cfg),
                    ),
                )
                if not matches:
                    emit_output(f"\nNo modules found with name {module_name!r}.")
                    continue
                emit_output(f"\nFound {len(matches)} module instance(s) for {module_name!r}:")
                for path, module in matches:
                    datecode = getattr(module, "datecode", None)
                    datecode_txt = f" (DateCode: {datecode})" if datecode else ""
                    emit_output(f"  - {' -> '.join(path)}{datecode_txt}")
    except Exception as exc:
        log_debug_exception(cfg, f"Module search failed for names {module_names!r}", logger=log)
        emit_output(f"❌ Error during search: {exc}")

    if pause_fn is not None:
        pause_fn()


def run_module_tree_debug(
    cfg: ConfigDict,
    *,
    prompt_fn: Callable[[str, str | None], str],
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    emit_output("\n--- Debug Module Tree Structure ---")
    max_depth_txt = prompt_fn("Max depth", "10")
    try:
        max_depth = int(max_depth_txt)
    except ValueError:
        emit_output("❌ Invalid depth; using default 10")
        max_depth = 10

    try:
        for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
            emit_output(f"\n=== Target: {target_name} ===")
            _run_with_live_status(
                f"Inspecting module tree for {target_name}",
                lambda project_bp=project_bp: debug_module_structure(project_bp, max_depth=max_depth),
            )
    except Exception as exc:
        log_debug_exception(cfg, f"Module tree debug failed with max_depth={max_depth}", logger=log)
        emit_output(f"❌ Error during debug: {exc}")

    if pause_fn is not None:
        pause_fn()


def run_analysis_menu(cfg: ConfigDict, *, analysis_menu_fn: Callable[[ConfigDict], None]) -> None:
    analysis_menu_fn(cfg)


def variable_analysis_menu(cfg: ConfigDict, *, analysis_menu_fn: Callable[[ConfigDict], None]) -> None:
    analysis_menu_fn(cfg)


def run_module_localvar_analysis(
    cfg: ConfigDict,
    *,
    load_project_fn: Callable[[ConfigDict], tuple[BasePicture, ProjectGraph]],
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    emit_output("\n--- Module Local Variable Analysis ---")
    emit_output("Enter the module path (strict) relative to BasePicture.")
    emit_output("Example: StartMaster.KaHA251A")
    default_bp, _default_graph = load_project_fn(cfg)
    module_path = (
        interaction.prompt(f"{default_bp.header.name}.", None).strip()
        if interaction is not None
        else input(f"{default_bp.header.name}.").strip()
    )

    if not module_path:
        emit_output("❌ No module path provided")
        if pause_fn is not None:
            pause_fn()
        return

    emit_output("Enter the local variable name (e.g., Dv):")
    var_name = interaction.prompt("Variable name", None).strip() if interaction is not None else input("> ").strip()

    if not var_name:
        emit_output("❌ No variable name provided")
        if pause_fn is not None:
            pause_fn()
        return

    from .analyzers.variable_usage_reporting import report_module_localvar_fields

    for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
        try:
            report = _run_with_live_status(
                f"Analyzing module local variable in {target_name}: {module_path}.{var_name}",
                lambda project_bp=project_bp: report_module_localvar_fields(
                    project_bp,
                    module_path,
                    var_name,
                    debug=debug_enabled(cfg),
                ),
            )
            emit_output(f"\n=== Target: {target_name} ===")
            emit_output(report)
        except Exception as exc:
            log_debug_exception(
                cfg,
                (
                    f"Module local variable analysis failed for target {target_name!r}, "
                    f"module {module_path!r}, variable {var_name!r}"
                ),
                logger=log,
            )
            emit_output(f"❌ Error during analysis for {target_name}: {exc}")

    if pause_fn is not None:
        pause_fn()


def _get_enabled_analyzers() -> list[Any]:
    return cast(list[Any], get_default_cli_analyzers())


def _analysis_status_text(target_name: str, spec: Any) -> str:
    return f"Analyzing {target_name}: {spec.name} ({spec.key})"


def _handle_analysis_cancellation(*, pause_fn: Callable[[], None] | None) -> None:
    emit_output("\nOperation canceled. Returning to the menu.")
    if pause_fn is not None:
        pause_fn()


def _profile_analyzers_enabled() -> bool:
    return os.environ.get("SATTLINT_PROFILE_ANALYZERS", "").strip().casefold() in {"1", "true", "yes", "on"}


def _order_analyzers_for_batch(analyzers: list[Any]) -> list[Any]:
    semantic_analyzers = [spec for spec in analyzers if getattr(spec, "key", None) == SEMANTIC_LAYER_ANALYZER_KEY]
    if not semantic_analyzers:
        return analyzers
    return [
        spec for spec in analyzers if getattr(spec, "key", None) != SEMANTIC_LAYER_ANALYZER_KEY
    ] + semantic_analyzers


def _emit_shared_artifact_profile(target_name: str, shared_artifacts: AnalysisSharedArtifacts) -> None:
    counters = shared_artifacts.counters
    emit_output(
        "Analyzer reuse profile for "
        f"{target_name}: shared-artifact-holders={counters.shared_artifact_holders_created}, "
        f"variable-foundation-builds={counters.variable_foundation_builds}, "
        f"semantic-precomputed-reports={counters.semantic_precomputed_reports_used}, "
        f"semantic-reruns={counters.semantic_analyzer_reruns}, "
        f"local-env-builds={counters.local_env_builds}"
    )


def _run_checks(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    selected_issue_kinds: Set[str] | None = None,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    get_enabled_analyzers_fn: Callable[[], list[Any]] = _get_enabled_analyzers,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] = _target_is_library,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    analyzers = get_enabled_analyzers_fn()
    normalized_selected_issue_kinds = (
        frozenset(IssueKind(issue_kind) for issue_kind in selected_issue_kinds)
        if selected_issue_kinds is not None
        else None
    )
    if selected_keys:
        selected = {canonicalize_analyzer_key(key) for key in selected_keys}
        analyzers = [spec for spec in analyzers if spec.key.casefold() in selected]
    analyzers = _order_analyzers_for_batch(analyzers)

    if not analyzers:
        emit_output("❌ No matching checks found")
        if pause_fn is not None:
            pause_fn()
        return

    emit_output("\n--- Running checks ---")
    _flush_stdout()
    report_cache = analysis_reporting_module.create_analysis_report_cache(
        cfg,
        use_cache_enabled_fn=_use_cache_enabled,
        debug_enabled_fn=debug_enabled,
        analysis_report_cache_cls=AnalysisReportCache,
        get_cache_dir_fn=get_cache_dir,
    )
    telemetry = telemetry_module.create_app_telemetry(cfg)
    try:
        for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
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
            shared_artifacts = AnalysisSharedArtifacts()
            shared_artifacts.counters.shared_artifact_holders_created += 1
            context = AnalysisContext(
                base_picture=project_bp,
                graph=graph,
                debug=debug_enabled(cfg),
                target_is_library=target_is_library_fn(cfg, project_bp, graph),
                selected_issue_kinds=normalized_selected_issue_kinds,
                config=cfg,
                shared_artifacts=shared_artifacts,
            )
            emit_output(f"\n=== Target: {target_name} ===")
            _flush_stdout()
            for spec in analyzers:
                emit_output(f"\n=== {spec.name} ({spec.key}) ===")
                _flush_stdout()
                if spec.key == "variables":
                    selected_issue_kind_values = _format_selected_issue_kind_values(normalized_selected_issue_kinds)
                    if selected_issue_kind_values is not None:
                        emit_output(f"Running variables analyzer for issue kinds: {selected_issue_kind_values}")
                        _flush_stdout()
                analyzer_started_at = perf_counter()
                try:
                    report = _run_with_live_status(
                        _analysis_status_text(target_name, spec),
                        lambda spec=spec, context=context, graph=graph: (
                            analysis_reporting_module.run_with_analysis_report_cache(
                                graph,
                                report_cache=report_cache,
                                analyzer_cache_key=spec.key,
                                run_fn=lambda spec=spec, context=context: spec.run(context),
                                compute_analysis_report_cache_key_fn=compute_analysis_report_cache_key,
                            )
                        ),
                    )
                except KeyboardInterrupt:
                    analyzer_timings_ms[spec.key] = round((perf_counter() - analyzer_started_at) * 1000, 3)
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
                    raise
                analyzer_timings_ms[spec.key] = round((perf_counter() - analyzer_started_at) * 1000, 3)
                if context.shared_artifacts is not None:
                    context.shared_artifacts.reports_by_analyzer_key[spec.key] = report
                phase_timings_ms = telemetry_module.normalize_phase_timings_ms(getattr(report, "phase_timings", None))
                if phase_timings_ms:
                    analyzer_phase_timings_ms[spec.key] = phase_timings_ms
                report = apply_rule_profile_to_report(spec.key, report, cfg)
                report = analysis_reporting_module.normalize_report_target_name(report, target_name)
                emit_output(report.summary())
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
            if _profile_analyzers_enabled():
                _emit_shared_artifact_profile(target_name, shared_artifacts)
    except KeyboardInterrupt:
        _handle_analysis_cancellation(pause_fn=pause_fn)
        return

    if pause_fn is not None:
        pause_fn()


def run_checks(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    selected_issue_kinds: Set[str] | None = None,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    get_enabled_analyzers_fn: Callable[[], list[Any]] = _get_enabled_analyzers,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] = _target_is_library,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    _run_checks(
        cfg,
        selected_keys,
        selected_issue_kinds,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        target_is_library_fn=target_is_library_fn,
        pause_fn=pause_fn,
    )


def run_checks_menu(cfg: ConfigDict, *, run_checks_fn: Callable[[ConfigDict, list[str] | None], None]) -> None:
    run_checks_fn(cfg, None)


def parse_index_selection(selection: str, max_index: int) -> list[int]:
    return _parse_index_selection(selection, max_index)


def run_mms_interface_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    emit_output("\n--- MMS Interface Variables ---")

    for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
        try:
            report = _run_with_live_status(
                f"Analyzing MMS interface variables for {target_name}",
                lambda project_bp=project_bp: analyze_mms_interface_variables(
                    project_bp,
                    debug=debug_enabled(cfg),
                    config=cfg,
                ),
            )
            report = analysis_reporting_module.normalize_report_target_name(report, target_name)
            emit_output(f"\n=== Target: {target_name} ===")
            emit_output(report.summary())
        except Exception as exc:
            log_debug_exception(cfg, f"MMS interface analysis failed for target {target_name!r}", logger=log)
            emit_output(f"❌ Error during analysis for {target_name}: {exc}")

    if pause_fn is not None:
        pause_fn()


def run_icf_validation(
    cfg: ConfigDict,
    *,
    configured_icf_files_fn: Callable[[ConfigDict], tuple[Path | None, list[Path]]],
    load_program_ast_fn: Callable[[ConfigDict, str], tuple[BasePicture, ProjectGraph]],
    validate_icf_entries_against_program_fn: Callable[..., Any] = validate_icf_entries_against_program,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    icf_dir, icf_files = configured_icf_files_fn(cfg)
    if icf_dir is None:
        emit_output("❌ icf_dir is not set in the config. Set it before running ICF validation.")
        if pause_fn is not None:
            pause_fn()
        return

    if not icf_dir.exists() or not icf_dir.is_dir():
        emit_output(f"❌ icf_dir does not exist or is not a directory: {icf_dir}")
        if pause_fn is not None:
            pause_fn()
        return

    if not icf_files:
        emit_output(f"⚠ No .icf files found in {icf_dir}")
        if pause_fn is not None:
            pause_fn()
        return

    total_entries = 0
    total_valid = 0
    total_invalid = 0
    total_skipped = 0
    files_failed = 0

    emit_output("\n--- ICF Validation (per program) ---")

    for icf_file in icf_files:
        program_name = icf_file.stem
        entries = parse_icf_file(icf_file)
        if not entries:
            emit_output(f"⚠ {icf_file.name}: no entries found")
            continue

        try:
            program_bp, graph = load_program_ast_fn(cfg, program_name)
            program_bp = engine_module.merge_project_basepicture(program_bp, graph)
        except Exception as exc:
            log_debug_exception(
                cfg,
                f"ICF validation failed while loading program {program_name!r} from {icf_file}",
                logger=log,
            )
            emit_output(f"❌ {icf_file.name}: failed to load program {program_name!r}: {exc}")
            files_failed += 1
            continue

        moduletype_index: dict[str, list[engine_module.ModuleTypeDef]] = {}
        for bp in graph.ast_by_name.values():
            for mt in bp.moduletype_defs or []:
                key = mt.name.casefold()
                moduletype_index.setdefault(key, []).append(mt)

        report = _run_with_live_status(
            f"Validating ICF entries for {program_name}",
            lambda program_bp=program_bp, entries=entries, program_name=program_name, moduletype_index=moduletype_index: (
                validate_icf_entries_against_program_fn(
                    program_bp,
                    entries,
                    expected_program=program_name,
                    debug=cfg.get("debug", False),
                    moduletype_index=moduletype_index,
                )
            ),
        )
        emit_output(report.summary())
        emit_output("")

        total_entries += report.total_entries
        total_valid += report.valid_entries
        total_invalid += len(report.issues)
        total_skipped += report.skipped_entries

    emit_output("Summary:")
    emit_output(f"  Files processed: {len(icf_files)}")
    emit_output(f"  Files failed: {files_failed}")
    emit_output(f"  Entries: {total_entries}")
    emit_output(f"  Valid: {total_valid}")
    emit_output(f"  Invalid: {total_invalid}")
    emit_output(f"  Skipped: {total_skipped}")

    if pause_fn is not None:
        pause_fn()


def run_debug_variable_usage(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    emit_output("\n--- Variable Usage (Fields + Locations) ---")
    emit_output("Enter the variable name to analyze:")
    var_name = interaction.prompt("Variable name", None).strip() if interaction is not None else input("> ").strip()

    if not var_name:
        emit_output("❌ No variable name provided")
        if pause_fn is not None:
            pause_fn()
        return

    for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
        try:
            report = _run_with_live_status(
                f"Tracing variable usage for {target_name}: {var_name}",
                lambda project_bp=project_bp: debug_variable_usage(project_bp, var_name, debug=debug_enabled(cfg)),
            )
            emit_output(f"\n=== Target: {target_name} ===")
            emit_output(report)
        except Exception as exc:
            log_debug_exception(
                cfg,
                f"Variable usage debug failed for target {target_name!r} and variable {var_name!r}",
                logger=log,
            )
            emit_output(f"❌ Error during debug for {target_name}: {exc}")

    if pause_fn is not None:
        pause_fn()


def run_comment_code_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    source_paths_for_current_target_fn: Callable[
        [BasePicture, ProjectGraph], set[Path]
    ] = _source_paths_for_current_target,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    emit_output("\n--- Commented-out Code ---")
    for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
        paths = source_paths_for_current_target_fn(project_bp, graph)
        report = _run_with_live_status(
            f"Analyzing commented-out code for {target_name}",
            lambda paths=paths, target_name=target_name: analyze_comment_code_files(paths, target_name),
        )
        report = analysis_reporting_module.normalize_report_target_name(report, target_name)
        emit_output(f"\n=== Target: {target_name} ===")
        emit_output(report.summary())

    if pause_fn is not None:
        pause_fn()


def run_advanced_datatype_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = _iter_loaded_projects

    if interaction is not None:
        choice = interaction.choose_menu_option(
            "Advanced Datatype Analysis",
            [
                SimpleNamespace(
                    key="1",
                    label="Analyze variable by name",
                    description="Field-level usage",
                ),
                SimpleNamespace(
                    key="2",
                    label="Compare module variants by name",
                    description="",
                ),
                SimpleNamespace(
                    key="3",
                    label="Debug specific variable usage",
                    description="",
                ),
                SimpleNamespace(key="b", label="Back", description=""),
            ],
        )
    else:
        emit_output("\n--- Advanced Datatype Analysis ---")
        emit_output("1) Analyze variable by name (field-level usage)")
        emit_output("2) Compare module variants by name")
        emit_output("3) Debug specific variable usage")
        emit_output("b) Back")

        choice = input("> ").strip()

    if choice == "1":
        var_name = (
            interaction.prompt("Variable name", None).strip()
            if interaction is not None
            else input("Enter variable name: ").strip()
        )
        if var_name:
            for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
                report = _run_with_live_status(
                    f"Analyzing datatype usage for {target_name}: {var_name}",
                    lambda project_bp=project_bp, graph=graph: variables_reporting_module.report_datatype_usage(
                        project_bp,
                        var_name,
                        debug=debug_enabled(cfg),
                        unavailable_libraries=analysis_reporting_module.unavailable_libraries(graph),
                    ),
                )
                emit_output(f"\n=== Target: {target_name} ===")
                emit_output(report)

    elif choice == "2":
        module_name = (
            interaction.prompt("Module name to compare", None).strip()
            if interaction is not None
            else input("Enter module name to compare: ").strip()
        )
        if module_name:
            emit_output("⚠ Module comparison analysis not yet implemented")

    elif choice == "3":
        var_name = (
            interaction.prompt("Variable name to debug", None).strip()
            if interaction is not None
            else input("Enter variable name to debug: ").strip()
        )
        if var_name:
            for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
                report = _run_with_live_status(
                    f"Tracing variable usage for {target_name}: {var_name}",
                    lambda project_bp=project_bp: variables_reporting_module.debug_variable_usage(
                        project_bp,
                        var_name,
                        debug=debug_enabled(cfg),
                    ),
                )
                emit_output(f"\n=== Target: {target_name} ===")
                emit_output(report)

    if pause_fn is not None:
        pause_fn()
