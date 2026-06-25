from __future__ import annotations

import importlib
import logging
import os
import sys
from collections.abc import Callable, Iterator, Mapping, Set
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import _app_analysis_loading as analysis_loading_module
from . import _app_analysis_menus as analysis_menus_module
from . import _app_analysis_reporting as analysis_reporting_module
from . import _app_analysis_variable_analyses as analysis_variable_analyses_module
from . import analysis_catalog as analysis_catalog_module
from . import analysis_dispatch as analysis_dispatch_module
from . import app_support as app_support_module
from . import app_telemetry as telemetry_module
from . import cache as cache_module
from . import console as console_module
from . import engine as engine_module
from ._app_debug import debug_enabled, log_debug_exception
from .analyzers import variable_usage_reporting as variables_reporting_module
from .analyzers.comment_code import analyze_comment_code_files
from .analyzers.framework import AnalysisSharedArtifacts, Issue, SimpleReport
from .analyzers.icf import parse_icf_file, validate_icf_entries_against_program
from .analyzers.mms import analyze_mms_interface_variables
from .analyzers.modules import analyze_module_duplicates, compare_modules, debug_module_structure, find_modules_by_name
from .analyzers.shadowing import analyze_shadowing
from .analyzers.variables import IssueKind, analyze_variables, filter_variable_report
from .app_interaction import MenuInteraction
from .cache import AnalysisReportCache, ASTCache
from .casefolding import casefold_equal, casefold_key
from .config_types import ConfigDict
from .models.project_graph import ProjectGraph
from .reporting.variables_report import VariablesReport

get_default_cli_analyzers = analysis_catalog_module.get_default_cli_analyzers
get_cli_dispatch_analyzers = analysis_dispatch_module.get_cli_dispatch_analyzers
run_registry_analyzer = analysis_dispatch_module.run_registry_analyzer

LoadedProject = tuple[str, BasePicture, ProjectGraph]


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


VariableAnalysisSelection = analysis_variable_analyses_module.VariableAnalysisSelection
VariableAnalysisMap = analysis_variable_analyses_module.VariableAnalysisMap
VARIABLE_ANALYSES = analysis_variable_analyses_module.VARIABLE_ANALYSES
HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS = analysis_variable_analyses_module.HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS
LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS = analysis_variable_analyses_module.LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS
app_support: Any = app_support_module
cache: Any = cache_module
engine: Any = engine_module
emit_output: Callable[..., None] = console_module.print_output  # type: ignore[assignment]
compute_cache_key: Callable[[Mapping[str, object]], str] = cache.compute_cache_key
compute_analysis_report_cache_key: Callable[[str, str], str] = cache.compute_analysis_report_cache_key
get_cache_dir: Callable[[], Path] = cache.get_cache_dir
log = logging.getLogger("SattLint")

analysis_reporting_module = analysis_reporting_module
telemetry_module = telemetry_module
variables_reporting_module = variables_reporting_module
AnalysisReportCache = AnalysisReportCache
analyze_variables = analyze_variables
filter_variable_report = filter_variable_report
analyze_shadowing = analyze_shadowing
analyze_mms_interface_variables = analyze_mms_interface_variables
parse_icf_file = parse_icf_file
analyze_comment_code_files = analyze_comment_code_files
debug_module_structure = debug_module_structure


def debug_variable_usage(base_picture: BasePicture, var_name: str, debug: bool = False) -> str:
    return variables_reporting_module.debug_variable_usage(base_picture, var_name, debug=debug)


_DRAFT_SOURCE_SUFFIXES = frozenset({".s", ".l"})
_OFFICIAL_SOURCE_SUFFIXES = frozenset({".x", ".z"})
_LIBRARY_SUPPRESSED_ANALYZER_KEYS = frozenset({"picture-display-paths"})

DRAFT_SOURCE_SUFFIXES = _DRAFT_SOURCE_SUFFIXES
OFFICIAL_SOURCE_SUFFIXES = _OFFICIAL_SOURCE_SUFFIXES


def _commands_module() -> Any:
    return importlib.import_module("sattlint._app_analysis_commands")


def _checks_module() -> Any:
    return importlib.import_module("sattlint._app_analysis_checks")


def _target_validation_warnings(target_name: str, warnings: list[str]) -> list[str]:
    return cast(list[str], app_support.target_validation_warnings(target_name, warnings))


target_validation_warnings = _target_validation_warnings


def _print_validation_warnings(warnings: list[str], *, limit: int = 12) -> None:
    app_support.print_validation_warnings(warnings, print_fn=emit_output, limit=limit)


print_validation_warnings = _print_validation_warnings


def _flush_stdout() -> None:
    flush = getattr(sys.stdout, "flush", None)
    if callable(flush):
        flush()


flush_stdout = _flush_stdout


def _normalized_issue_kind_value(raw_kind: object) -> str | None:
    if isinstance(raw_kind, IssueKind):
        return raw_kind.value
    value = getattr(raw_kind, "value", raw_kind)
    text = str(value).strip() if value is not None else ""
    return text or None


def _normalize_selected_issue_kind_values(selected_issue_kinds: Set[str] | None) -> frozenset[str] | None:
    if selected_issue_kinds is None:
        return None
    normalized = {
        issue_kind
        for raw_kind in selected_issue_kinds
        if (issue_kind := _normalized_issue_kind_value(raw_kind)) is not None
    }
    return frozenset(normalized)


normalize_selected_issue_kind_values = _normalize_selected_issue_kind_values


def _format_selected_issue_kind_values(selected_issue_kinds: frozenset[str] | None) -> str | None:
    if not selected_issue_kinds:
        return None
    return ", ".join(sorted(selected_issue_kinds))


format_selected_issue_kind_values = _format_selected_issue_kind_values


def _selected_issue_kind_tuple(selected_issue_kinds: frozenset[str] | None) -> tuple[str, ...] | None:
    if not selected_issue_kinds:
        return None
    return tuple(sorted(selected_issue_kinds))


selected_issue_kind_tuple = _selected_issue_kind_tuple


def _issue_count_for_report(report: object) -> int | None:
    issues = getattr(report, "issues", None)
    if not isinstance(issues, list):
        return None
    return len(cast(list[object], issues))


issue_count_for_report = _issue_count_for_report


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


filter_report_for_selected_issue_kinds = _filter_report_for_selected_issue_kinds


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
    status_update_fn: Callable[[str], None] | None = None,
) -> tuple[BasePicture, ProjectGraph]:
    if status_update_fn is not None:
        return analysis_loading_module.load_project(
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
            status_update_fn=status_update_fn,
        )
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
    emit_output_fn: Callable[..., None] | None = None,
) -> bool:
    resolved_emit_output_fn = emit_output if emit_output_fn is None else emit_output_fn
    return analysis_loading_module.ensure_ast_cache(
        cfg,
        get_analyzed_targets_fn=get_analyzed_targets_fn,
        cache_key_for_target_fn=cache_key_for_target_fn,
        load_project_fn=load_project_fn,
        ast_cache_cls=ast_cache_cls,
        get_cache_dir_fn=get_cache_dir_fn,
        emit_output_fn=resolved_emit_output_fn,
    )


def refresh_analysis_caches(
    cfg: ConfigDict,
    *,
    force_refresh_ast_fn: Callable[[ConfigDict], tuple[BasePicture, ProjectGraph] | None] = force_refresh_ast,
    get_cache_dir_fn: Callable[[], Path] = get_cache_dir,
    get_cache_manager_fn: Callable[..., Any] = cache_module.get_cache_manager,
    emit_output_fn: Callable[..., None] | None = None,
) -> tuple[BasePicture, ProjectGraph] | None:
    resolved_emit_output_fn = emit_output if emit_output_fn is None else emit_output_fn
    cache_manager = get_cache_manager_fn(get_cache_dir_fn())
    cleared = cache_manager.clear_all()
    removed_entries = cleared.removed_entries
    if removed_entries == 0:
        resolved_emit_output_fn("All caches already empty.")
    else:
        entry_label = "entry" if removed_entries == 1 else "entries"
        resolved_emit_output_fn(f"Cleared all caches ({removed_entries} {entry_label}).")
    return force_refresh_ast_fn(cfg)


def _use_cache_enabled(cfg: ConfigDict) -> bool:
    return bool(cfg.get("use_cache", True))


use_cache_enabled = _use_cache_enabled


def _run_with_live_status(status_text: str, run_fn: Callable[[], Any]) -> Any:
    with console_module.live_status_line() as status_update_fn:
        status_update_fn(status_text)
        return run_fn()


run_with_live_status = _run_with_live_status


def _run_logged_cli_action(
    cfg: ConfigDict,
    *,
    action: Callable[[], Any],
    debug_message: str,
    user_message: str,
) -> tuple[bool, Any | None]:
    try:
        return True, action()
    except Exception as exc:  # noqa: BLE001 - CLI analysis commands should log failures and continue cleanly
        log_debug_exception(cfg, debug_message, logger=log)
        emit_output(user_message.format(error=exc))
        return False, None


run_logged_cli_action = _run_logged_cli_action


def _run_module_duplicates_for_name(
    cfg: ConfigDict,
    *,
    target_name: str,
    project_bp: BasePicture,
    module_name: str,
    interaction: MenuInteraction | None,
) -> Any | None:
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
        return None

    emit_output(f"\nFound {len(matches)} instance(s) for {module_name!r}:")
    for idx, (path, module) in enumerate(matches, 1):
        datecode = getattr(module, "datecode", None)
        datecode_txt = f" (DateCode: {datecode})" if datecode else ""
        emit_output(f"  {idx}) {' -> '.join(path)}{datecode_txt}")

    emit_output("\nSelect instances to compare (e.g., 6,7).")
    emit_output("Press Enter to compare all instances.")
    selection = (
        interaction.prompt("Instances to compare", None).strip() if interaction is not None else input("> ").strip()
    )

    if selection:
        indices = _parse_index_selection(selection, len(matches))
        if len(indices) < 2:
            emit_output("⚠ Need at least two instances to compare; skipping.")
            return None
        selected = [matches[i - 1] for i in indices]
        return _run_with_live_status(
            f"Comparing module variants in {target_name}: {module_name}",
            lambda selected=selected: compare_modules(selected),
        )

    return _run_with_live_status(
        f"Comparing module variants in {target_name}: {module_name}",
        lambda project_bp=project_bp, module_name=module_name: analyze_module_duplicates(
            project_bp,
            module_name,
            debug=debug_enabled(cfg),
        ),
    )


run_module_duplicates_for_name = _run_module_duplicates_for_name


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
    commands_module = _commands_module()

    commands_module.run_variable_analysis(
        cfg,
        kinds,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        target_is_library_fn=target_is_library_fn,
        analyze_variables_fn=analyze_variables_fn,
        analyze_shadowing_fn=analyze_shadowing_fn,
        filter_variable_report_fn=filter_variable_report_fn,
        print_validation_warnings_fn=print_validation_warnings_fn,
        target_validation_warnings_fn=target_validation_warnings_fn,
        pause_fn=pause_fn,
    )


def run_datatype_usage_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    commands_module = _commands_module()

    commands_module.run_datatype_usage_analysis(
        cfg,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        pause_fn=pause_fn,
        interaction=interaction,
    )


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
    commands_module = _commands_module()

    commands_module.run_module_duplicates_analysis(
        cfg,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        pause_fn=pause_fn,
        interaction=interaction,
    )


def run_module_find_by_name(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    commands_module = _commands_module()

    commands_module.run_module_find_by_name(
        cfg,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        pause_fn=pause_fn,
        interaction=interaction,
    )


def run_module_tree_debug(
    cfg: ConfigDict,
    *,
    prompt_fn: Callable[[str, str | None], str],
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    commands_module = _commands_module()

    commands_module.run_module_tree_debug(
        cfg,
        prompt_fn=prompt_fn,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        pause_fn=pause_fn,
    )


def run_analysis_menu(cfg: ConfigDict, *, analysis_menu_fn: Callable[[ConfigDict], None]) -> None:
    commands_module = _commands_module()

    commands_module.run_analysis_menu(cfg, analysis_menu_fn=analysis_menu_fn)


def variable_analysis_menu(cfg: ConfigDict, *, analysis_menu_fn: Callable[[ConfigDict], None]) -> None:
    commands_module = _commands_module()

    commands_module.variable_analysis_menu(cfg, analysis_menu_fn=analysis_menu_fn)


def run_module_localvar_analysis(
    cfg: ConfigDict,
    *,
    load_project_fn: Callable[[ConfigDict], tuple[BasePicture, ProjectGraph]],
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    commands_module = _commands_module()

    commands_module.run_module_localvar_analysis(
        cfg,
        load_project_fn=load_project_fn,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        pause_fn=pause_fn,
        interaction=interaction,
    )


def _get_enabled_analyzers() -> list[Any]:
    return cast(list[Any], get_default_cli_analyzers())


get_enabled_analyzers = _get_enabled_analyzers


def _analysis_status_text(target_name: str, spec: Any) -> str:
    return f"Analyzing {target_name}: {spec.name} ({spec.key})"


analysis_status_text = _analysis_status_text


def _handle_analysis_cancellation(*, pause_fn: Callable[[], None] | None) -> None:
    emit_output("\nOperation canceled. Returning to the menu.")
    if pause_fn is not None:
        pause_fn()


handle_analysis_cancellation = _handle_analysis_cancellation


def _profile_analyzers_enabled() -> bool:
    return os.environ.get("SATTLINT_PROFILE_ANALYZERS", "").strip().casefold() in {"1", "true", "yes", "on"}


profile_analyzers_enabled = _profile_analyzers_enabled


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


shared_artifact_profile_text = _shared_artifact_profile_text


LIBRARY_SUPPRESSED_ANALYZER_KEYS = _LIBRARY_SUPPRESSED_ANALYZER_KEYS


def collect_run_checks_result(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    selected_issue_kinds: Set[str] | None = None,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    get_enabled_analyzers_fn: Callable[[], list[Any]] = _get_enabled_analyzers,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] = _target_is_library,
) -> ChecksRunResult:
    checks_module = _checks_module()

    return checks_module.collect_run_checks_result(
        cfg,
        selected_keys,
        selected_issue_kinds,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        target_is_library_fn=target_is_library_fn,
    )


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
    checks_module = _checks_module()

    checks_module.run_checks(
        cfg,
        selected_keys,
        selected_issue_kinds,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        target_is_library_fn=target_is_library_fn,
        pause_fn=pause_fn,
    )


def run_checks_menu(cfg: ConfigDict, *, run_checks_fn: Callable[[ConfigDict, list[str] | None], None]) -> None:
    checks_module = _checks_module()

    checks_module.run_checks_menu(cfg, run_checks_fn=run_checks_fn)


def parse_index_selection(selection: str, max_index: int) -> list[int]:
    commands_module = _commands_module()

    return commands_module.parse_index_selection(selection, max_index)


def run_mms_interface_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    commands_module = _commands_module()

    commands_module.run_mms_interface_analysis(
        cfg,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        pause_fn=pause_fn,
    )


def run_icf_validation(
    cfg: ConfigDict,
    *,
    configured_icf_files_fn: Callable[[ConfigDict], tuple[Path | None, list[Path]]],
    load_program_ast_fn: Callable[[ConfigDict, str], tuple[BasePicture, ProjectGraph]],
    validate_icf_entries_against_program_fn: Callable[..., Any] = validate_icf_entries_against_program,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    commands_module = _commands_module()

    commands_module.run_icf_validation(
        cfg,
        configured_icf_files_fn=configured_icf_files_fn,
        load_program_ast_fn=load_program_ast_fn,
        validate_icf_entries_against_program_fn=validate_icf_entries_against_program_fn,
        pause_fn=pause_fn,
    )


def run_debug_variable_usage(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    commands_module = _commands_module()

    commands_module.run_debug_variable_usage(
        cfg,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        pause_fn=pause_fn,
        interaction=interaction,
    )


def run_comment_code_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    source_paths_for_current_target_fn: Callable[
        [BasePicture, ProjectGraph], set[Path]
    ] = _source_paths_for_current_target,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    commands_module = _commands_module()

    commands_module.run_comment_code_analysis(
        cfg,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        source_paths_for_current_target_fn=source_paths_for_current_target_fn,
        pause_fn=pause_fn,
    )


def run_advanced_datatype_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    commands_module = _commands_module()

    commands_module.run_advanced_datatype_analysis(
        cfg,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        pause_fn=pause_fn,
        interaction=interaction,
    )
