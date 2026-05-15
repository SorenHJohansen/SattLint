#!/usr/bin/env python3
"""CLI entry points and interactive helpers for SattLint."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import app_analysis as app_analysis_module
from . import app_base as app_base_module
from . import app_cli_commands as app_cli_commands_module
from . import app_docs as app_docs_module
from . import app_graphics as app_graphics_module
from . import app_menus as app_menus_module
from . import app_support as app_support_module
from . import cache as cache_module
from . import config as _config_module
from . import console as console_module
from . import engine as engine_module_impl
from .analyzers.registry import get_default_analyzers, get_default_cli_analyzers
from .analyzers.shadowing import analyze_shadowing
from .analyzers.variables import (
    IssueKind,
    analyze_variables,
    filter_variable_report,
)
from .cache import ASTCache
from .core.semantic import load_workspace_snapshot
from .models.project_graph import ProjectGraph

ConfigDict = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]
VariableAnalysisSelection = set[IssueKind] | None
VariableAnalysisMap = dict[str, tuple[str, VariableAnalysisSelection]]
GraphicsRulesConfig = dict[str, Any]
GraphicsRulesLoadResult = tuple[GraphicsRulesConfig, bool]
DocumentationSelection = dict[str, Any]
LoadedConfig = tuple[ConfigDict, bool]
ConfigValidationResult = _config_module.ConfigValidationResult

app_analysis = cast(Any, app_analysis_module)
app_base = cast(Any, app_base_module)
app_cli_commands = cast(Any, app_cli_commands_module)
app_docs = cast(Any, app_docs_module)
app_graphics = cast(Any, app_graphics_module)
app_menus = cast(Any, app_menus_module)
app_support = cast(Any, app_support_module)
cache = cast(Any, cache_module)
engine_module: Any = engine_module_impl

VARIABLE_ANALYSES: VariableAnalysisMap = app_analysis.VARIABLE_ANALYSES
HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS: tuple[str, ...] = app_analysis.HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS
LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS: tuple[str, ...] = app_analysis.LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS
emit_output: Callable[..., None] = console_module.print_output  # type: ignore[assignment]


EXIT_SUCCESS: int = 0
EXIT_USAGE_ERROR: int = 1

CONFIG_PATH: Path = app_base.CONFIG_PATH
DEFAULT_CONFIG: ConfigDict = app_base.DEFAULT_CONFIG


@dataclass(frozen=True)
class MenuOption:
    key: str
    label: str
    description: str = ""


TargetLoadError = app_support.TargetLoadError


def _print_validation_warnings(warnings: list[str], *, limit: int = 12) -> None:
    app_support.print_validation_warnings(warnings, print_fn=print, limit=limit)


def _target_validation_warnings(target_name: str, warnings: list[str]) -> list[str]:
    return cast(list[str], app_support.target_validation_warnings(target_name, warnings))


def load_config(path: Path) -> LoadedConfig:
    return cast(LoadedConfig, app_base.load_config(path))


def get_cache_dir() -> Path:
    return cast(Path, cache.get_cache_dir())


def save_config(path: Path, cfg: ConfigDict) -> None:
    app_base.save_config(path, cfg)


def get_graphics_rules_path() -> Path:
    return cast(Path, app_graphics.get_graphics_rules_path(CONFIG_PATH))


def load_graphics_rules(path: Path | None = None) -> GraphicsRulesLoadResult:
    return cast(GraphicsRulesLoadResult, app_graphics.load_graphics_rules(CONFIG_PATH, path))


def save_graphics_rules(path: Path, rules: dict[str, Any]) -> None:
    app_graphics.save_graphics_rules(path, rules)
    emit_output("Graphics rules saved")


def self_check(cfg: ConfigDict) -> bool:
    return cast(bool, app_base.self_check(cfg))


def validate_effective_config(cfg: ConfigDict) -> ConfigValidationResult:
    return _config_module.validate_effective_config(cfg)


log: Any = app_base.log


# ----------------------------
# Helpers
# ----------------------------
def _clear_windows_console() -> None:
    app_base.clear_windows_console()


def clear_screen() -> None:
    app_base.clear_screen(os_module=os, sys_module=sys, clear_windows_console=_clear_windows_console)


def pause() -> None:
    app_base.pause()


QuitAppError = app_base.QuitAppError


def quit_app() -> None:
    app_base.quit_app(clear_screen_fn=clear_screen)


def confirm(msg: str) -> bool:
    return cast(bool, app_base.confirm(msg))


def prompt(msg: str, default: str | None = None) -> str:
    return cast(str, app_base.prompt(msg, default))


def target_exists(target: str, cfg: ConfigDict) -> bool:
    return cast(bool, app_base.target_exists(target, cfg))


def apply_debug(cfg: ConfigDict) -> None:
    app_base.apply_debug(cfg)


def build_cli_parser() -> argparse.ArgumentParser:
    return cast(argparse.ArgumentParser, app_base.build_cli_parser())


def run_syntax_check_command(file_path: str) -> int:
    return cast(int, app_base.run_syntax_check_command(file_path))


def run_cli(argv: list[str]) -> int:
    return cast(
        int,
        app_base.run_cli(
            argv,
            config_path=CONFIG_PATH,
            build_cli_parser_fn=build_cli_parser,
            run_syntax_check_command_fn=run_syntax_check_command,
            load_config_fn=load_config,
            apply_debug_fn=apply_debug,
            run_validate_config_command_fn=run_validate_config_command,
            run_analyze_command_fn=run_analyze_command,
            run_simulate_command_fn=run_simulate_command,
            run_docgen_command_fn=run_docgen_command,
            run_format_icf_command_fn=run_format_icf_command,
            exit_success=EXIT_SUCCESS,
            exit_usage_error=EXIT_USAGE_ERROR,
        ),
    )


def run_validate_config_command(cfg: ConfigDict, *, config_path: Path, default_used: bool) -> int:
    return cast(
        int,
        app_cli_commands.run_validate_config_command(
            cfg,
            config_path=config_path,
            default_used=default_used,
            validate_config_fn=validate_effective_config,
            exit_success=EXIT_SUCCESS,
            exit_usage_error=EXIT_USAGE_ERROR,
        ),
    )


def run_analyze_command(cfg: ConfigDict, *, selected_keys: list[str] | None, use_cache: bool) -> int:
    def _iter_projects(nested_cfg: ConfigDict) -> Iterator[LoadedProject]:
        return _iter_loaded_projects(nested_cfg, use_cache=use_cache)

    def _run_checks(local_cfg: ConfigDict, local_selected_keys: list[str] | None, local_use_cache: bool) -> None:
        def _iter_nested_projects(nested_cfg: ConfigDict) -> Iterator[LoadedProject]:
            return _iter_loaded_projects(nested_cfg, use_cache=local_use_cache)

        app_analysis.run_checks(
            local_cfg,
            local_selected_keys,
            iter_loaded_projects_fn=_iter_nested_projects,
            get_enabled_analyzers_fn=_get_selectable_analyzers if local_selected_keys else _get_enabled_analyzers,
            target_is_library_fn=_target_is_library,
            pause_fn=None,
        )

    del _iter_projects
    return cast(
        int,
        app_cli_commands.run_analyze_command(
            cfg,
            selected_keys=selected_keys,
            use_cache=use_cache,
            run_checks_fn=_run_checks,
            exit_success=EXIT_SUCCESS,
        ),
    )


def _simulate_target(
    cfg: ConfigDict,
    *,
    target_path: str,
    module_name: str,
    mode: str,
    max_scans: int,
    use_cache: bool,
) -> Any:
    from .simulation import simulate_snapshot_target

    del cfg, use_cache
    snapshot = load_workspace_snapshot(
        Path(target_path),
        collect_variable_diagnostics=False,
    )
    return simulate_snapshot_target(
        snapshot,
        module_name=module_name,
        mode=mode,
        max_scans=max_scans,
    )


def run_simulate_command(
    cfg: ConfigDict,
    *,
    target_path: str,
    module_name: str,
    mode: str,
    max_scans: int,
    output_format: str,
    output_path: str | None,
    use_cache: bool,
) -> int:
    return cast(
        int,
        app_cli_commands.run_simulate_command(
            cfg,
            target_path=target_path,
            module_name=module_name,
            mode=mode,
            max_scans=max_scans,
            output_format=output_format,
            output_path=output_path,
            use_cache=use_cache,
            simulate_fn=_simulate_target,
            exit_success=EXIT_SUCCESS,
            exit_usage_error=EXIT_USAGE_ERROR,
        ),
    )


def run_docgen_command(
    cfg: ConfigDict,
    *,
    use_cache: bool = True,
    output_dir: str | None = None,
    output_path: str | None = None,
) -> int:
    def _iter_projects(local_cfg: ConfigDict, local_use_cache: bool) -> Iterator[LoadedProject]:
        return _iter_loaded_projects(local_cfg, use_cache=local_use_cache)

    return cast(
        int,
        app_cli_commands.run_docgen_command(
            cfg,
            use_cache=use_cache,
            output_dir=output_dir,
            output_path=output_path,
            iter_loaded_projects_fn=_iter_projects,
            documentation_unit_selection_fn=_get_documentation_unit_selection,
            exit_success=EXIT_SUCCESS,
            exit_usage_error=EXIT_USAGE_ERROR,
        ),
    )


def _configured_icf_files(cfg: ConfigDict) -> tuple[Path | None, list[Path]]:
    return cast(tuple[Path | None, list[Path]], app_support.configured_icf_files(cfg))


def run_format_icf_command(cfg: ConfigDict, *, check: bool = False) -> int:
    return cast(
        int,
        app_support.run_format_icf_command(
            cfg,
            check=check,
            print_fn=print,
            exit_success=EXIT_SUCCESS,
            exit_usage_error=EXIT_USAGE_ERROR,
        ),
    )


def run_icf_formatter(cfg: ConfigDict) -> None:
    run_format_icf_command(cfg)
    pause()


def show_config(cfg: ConfigDict) -> None:
    app_graphics.show_config(
        cfg,
        get_graphics_rules_path_fn=get_graphics_rules_path,
        load_graphics_rules_fn=load_graphics_rules,
        graphics_rule_config_line_fn=_graphics_rule_config_line,
    )


def _print_menu(
    title: str,
    options: Sequence[MenuOption],
    *,
    intro: str | None = None,
    note: str | None = None,
) -> None:
    app_support.print_menu(title, options, print_fn=print, intro=intro, note=note)


def _menu_option(key: str, label: str, description: str) -> MenuOption:
    return MenuOption(key, label, description)


def _summarize_targets(cfg: ConfigDict) -> str:
    return cast(str, app_support.summarize_targets(cfg, get_analyzed_targets_fn=_get_analyzed_targets))


def show_help(cfg: ConfigDict) -> None:
    app_support.show_help(
        cfg,
        clear_screen_fn=clear_screen,
        get_analyzed_targets_fn=_get_analyzed_targets,
        summarize_targets_fn=_summarize_targets,
        print_fn=print,
        pause_fn=pause,
    )


def _get_analyzed_targets(cfg: ConfigDict) -> list[str]:
    return cast(list[str], app_support.get_analyzed_targets(cfg))


def _require_analyzed_targets(cfg: ConfigDict) -> list[str]:
    return cast(list[str], app_support.require_analyzed_targets(cfg))


def _has_analyzed_targets(cfg: ConfigDict) -> bool:
    return cast(bool, app_support.has_analyzed_targets(cfg, get_analyzed_targets_fn=_get_analyzed_targets))


def _require_targets_for_menu_action(cfg: ConfigDict, action: str) -> bool:
    return cast(
        bool,
        app_support.require_targets_for_menu_action(
            cfg,
            action,
            has_analyzed_targets_fn=_has_analyzed_targets,
            print_fn=print,
            pause_fn=pause,
        ),
    )


def _cache_key_for_target(cfg: ConfigDict, target_name: str) -> str:
    compute_cache_key_fn = cast(Callable[[ConfigDict], str], cache.compute_cache_key)
    return cast(str, app_support.cache_key_for_target(cfg, target_name, compute_cache_key_fn=compute_cache_key_fn))


def _split_csv_values(raw: str) -> list[str]:
    return cast(list[str], app_support.split_csv_values(raw))


_graphics_rule_label: Callable[[dict[str, Any]], str] = app_graphics.graphics_rule_label
_graphics_rule_config_line: Callable[[dict[str, Any]], str] = app_graphics.graphics_rule_config_line
_print_graphics_rules_summary: Callable[..., None] = app_graphics.print_graphics_rules_summary
config_module = _config_module
classify_documentation_structure: Callable[..., Any] = app_docs.classify_documentation_structure
discover_documentation_unit_candidates: Callable[..., list[Any]] = app_docs.discover_documentation_unit_candidates
validate_icf_entries_against_program: Callable[..., Any] = app_analysis.validate_icf_entries_against_program


def _discover_graphics_rule_selector_options(
    cfg: ConfigDict | None,
    *,
    selector_field: str,
    module_kind: str,
) -> list[dict[str, Any]]:
    def _iter_projects(local_cfg: ConfigDict) -> Iterator[LoadedProject]:
        return _iter_loaded_projects(local_cfg)

    return cast(
        list[dict[str, Any]],
        app_graphics.discover_graphics_rule_selector_options(
            cfg,
            selector_field=selector_field,
            module_kind=module_kind,
            has_analyzed_targets_fn=_has_analyzed_targets,
            iter_loaded_projects_fn=_iter_projects,
            collect_graphics_layout_entries_for_target_fn=_collect_graphics_layout_entries_for_target,
        ),
    )


def _pick_or_prompt_graphics_rule_selector_value(
    selector_field: str,
    module_kind: str,
    *,
    cfg: ConfigDict | None = None,
) -> str:
    return cast(
        str,
        app_graphics.pick_or_prompt_graphics_rule_selector_value(
            selector_field,
            module_kind,
            cfg=cfg,
            discover_graphics_rule_selector_options_fn=_discover_graphics_rule_selector_options,
        ),
    )


def _annotate_graphics_entries_with_structure_paths(
    entries: list[dict[str, Any]],
    project_bp: BasePicture,
    graph: ProjectGraph,
) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]],
        app_graphics.annotate_graphics_entries_with_structure_paths(
            entries,
            project_bp,
            graph,
            classify_documentation_structure_fn=classify_documentation_structure,
            discover_documentation_unit_candidates_fn=discover_documentation_unit_candidates,
        ),
    )


def graphics_rules_menu(cfg: ConfigDict | None = None) -> None:
    app_graphics.graphics_rules_menu(
        cfg,
        get_graphics_rules_path_fn=get_graphics_rules_path,
        load_graphics_rules_fn=load_graphics_rules,
        save_graphics_rules_fn=save_graphics_rules,
        prompt_graphics_rule_definition_with_config_fn=_prompt_graphics_rule_definition_with_config,
        graphics_rule_label_fn=_graphics_rule_label,
        clear_screen_fn=clear_screen,
        print_menu_fn=_print_menu,
        menu_option_factory=_menu_option,
        confirm_fn=confirm,
        prompt_fn=prompt,
        quit_app_fn=quit_app,
        pause_fn=pause,
    )


def _prompt_graphics_rule_definition_with_config(cfg: ConfigDict | None) -> dict[str, Any] | None:
    return cast(
        dict[str, Any] | None,
        app_graphics.prompt_graphics_rule_definition_with_config(
            cfg,
            prompt_fn=prompt,
            pause_fn=pause,
            pick_or_prompt_graphics_rule_selector_value_fn=_pick_or_prompt_graphics_rule_selector_value,
        ),
    )


def _collect_graphics_layout_entries_for_target(
    target_name: str,
    project_bp: BasePicture,
    graph: ProjectGraph,
) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]],
        app_graphics.collect_graphics_layout_entries_for_target(
            target_name,
            project_bp,
            graph,
            annotate_graphics_entries_with_structure_paths_fn=_annotate_graphics_entries_with_structure_paths,
        ),
    )


def run_graphics_rules_validation(cfg: ConfigDict) -> None:
    def _iter_projects(local_cfg: ConfigDict) -> Iterator[LoadedProject]:
        return _iter_loaded_projects(local_cfg)

    app_graphics.run_graphics_rules_validation(
        cfg,
        get_graphics_rules_path_fn=get_graphics_rules_path,
        load_graphics_rules_fn=load_graphics_rules,
        iter_loaded_projects_fn=_iter_projects,
        collect_graphics_layout_entries_for_target_fn=_collect_graphics_layout_entries_for_target,
        pause_fn=pause,
    )


def _get_documentation_unit_selection() -> DocumentationSelection:
    return cast(DocumentationSelection, app_docs.get_documentation_unit_selection())


def preview_documentation_unit_candidates(cfg: ConfigDict) -> None:
    def _iter_projects(local_cfg: ConfigDict) -> Iterator[LoadedProject]:
        return _iter_loaded_projects(local_cfg)

    app_docs.preview_documentation_unit_candidates(
        cfg,
        iter_loaded_projects_fn=_iter_projects,
        pause_fn=pause,
    )


def configure_documentation_scope_by_moduletype(cfg: ConfigDict) -> bool:
    del cfg
    return cast(
        bool,
        app_docs.configure_documentation_scope_by_moduletype(
            split_csv_values_fn=_split_csv_values,
            pause_fn=pause,
        ),
    )


def configure_documentation_scope_by_instance_path(cfg: ConfigDict) -> bool:
    del cfg
    return cast(
        bool,
        app_docs.configure_documentation_scope_by_instance_path(
            split_csv_values_fn=_split_csv_values,
            pause_fn=pause,
        ),
    )


def reset_documentation_scope(cfg: ConfigDict) -> bool:
    del cfg
    return cast(bool, app_docs.reset_documentation_scope(pause_fn=pause))


def run_generate_documentation(cfg: ConfigDict) -> None:
    def _iter_projects(local_cfg: ConfigDict) -> Iterator[LoadedProject]:
        return _iter_loaded_projects(local_cfg)

    app_docs.run_generate_documentation(
        cfg,
        iter_loaded_projects_fn=_iter_projects,
        prompt_fn=prompt,
        pause_fn=pause,
    )


def documentation_menu(cfg: ConfigDict) -> bool:
    def _iter_projects(local_cfg: ConfigDict) -> Iterator[LoadedProject]:
        return _iter_loaded_projects(local_cfg)

    return cast(
        bool,
        app_docs.documentation_menu(
            cfg,
            clear_screen_fn=clear_screen,
            print_menu_fn=_print_menu,
            menu_option_factory=_menu_option,
            quit_app_fn=quit_app,
            pause_fn=pause,
            split_csv_values_fn=_split_csv_values,
            iter_loaded_projects_fn=_iter_projects,
            prompt_fn=prompt,
        ),
    )


def _iter_loaded_projects(
    cfg: ConfigDict,
    *,
    use_cache: bool = True,
) -> Iterator[LoadedProject]:
    return cast(
        Iterator[LoadedProject],
        app_analysis.iter_loaded_projects(
            cfg,
            use_cache=use_cache,
            require_analyzed_targets_fn=_require_analyzed_targets,
            load_project_fn=load_project,
        ),
    )


def _source_paths_for_current_target(project_bp: BasePicture, graph: ProjectGraph) -> set[Path]:
    return cast(set[Path], app_analysis.source_paths_for_current_target(project_bp, graph))


def _target_is_library(cfg: ConfigDict, project_bp: BasePicture, graph: ProjectGraph) -> bool:
    return cast(bool, app_analysis.target_is_library(cfg, project_bp, graph))


def load_project(
    cfg: ConfigDict,
    target_name: str | None = None,
    *,
    use_cache: bool = True,
    use_file_ast_cache: bool = True,
) -> tuple[BasePicture, ProjectGraph]:
    return cast(
        tuple[BasePicture, ProjectGraph],
        app_analysis.load_project(
            cfg,
            target_name=target_name,
            use_cache=use_cache,
            use_file_ast_cache=use_file_ast_cache,
            require_analyzed_targets_fn=_require_analyzed_targets,
            cache_key_for_target_fn=_cache_key_for_target,
            target_load_error_factory=TargetLoadError,
            get_cache_dir_fn=get_cache_dir,
        ),
    )


def load_program_ast(
    cfg: ConfigDict,
    program_name: str,
    *,
    force_dependency_resolution: bool = False,
) -> tuple[BasePicture, ProjectGraph]:
    return cast(
        tuple[BasePicture, ProjectGraph],
        app_analysis.load_program_ast(
            cfg,
            program_name,
            force_dependency_resolution=force_dependency_resolution,
        ),
    )


def force_refresh_ast(cfg: ConfigDict) -> tuple[BasePicture, ProjectGraph] | None:
    return cast(
        tuple[BasePicture, ProjectGraph] | None,
        app_analysis.force_refresh_ast(
            cfg,
            get_analyzed_targets_fn=_get_analyzed_targets,
            cache_key_for_target_fn=_cache_key_for_target,
            load_project_fn=load_project,
            ast_cache_cls=ASTCache,
            get_cache_dir_fn=get_cache_dir,
        ),
    )


def ensure_ast_cache(cfg: ConfigDict) -> bool:
    return cast(
        bool,
        app_analysis.ensure_ast_cache(
            cfg,
            get_analyzed_targets_fn=_get_analyzed_targets,
            cache_key_for_target_fn=_cache_key_for_target,
            load_project_fn=load_project,
            ast_cache_cls=ASTCache,
            get_cache_dir_fn=get_cache_dir,
        ),
    )


def run_variable_analysis(cfg: ConfigDict, kinds: set[IssueKind] | None) -> None:
    app_analysis.run_variable_analysis(
        cfg,
        kinds,
        iter_loaded_projects_fn=_iter_loaded_projects,
        target_is_library_fn=_target_is_library,
        analyze_variables_fn=analyze_variables,
        analyze_shadowing_fn=analyze_shadowing,
        filter_variable_report_fn=filter_variable_report,
        print_validation_warnings_fn=_print_validation_warnings,
        target_validation_warnings_fn=_target_validation_warnings,
        pause_fn=pause,
    )


def run_datatype_usage_analysis(cfg: ConfigDict) -> None:
    app_analysis.run_datatype_usage_analysis(
        cfg,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def variable_usage_submenu(cfg: ConfigDict) -> None:
    app_analysis.variable_usage_submenu(
        cfg,
        clear_screen_fn=clear_screen,
        quit_app_fn=quit_app,
        run_variable_analysis_fn=run_variable_analysis,
        run_datatype_usage_analysis_fn=run_datatype_usage_analysis,
        run_debug_variable_usage_fn=run_debug_variable_usage,
        run_module_localvar_analysis_fn=run_module_localvar_analysis,
        pause_fn=pause,
    )


def module_analysis_submenu(cfg: ConfigDict) -> None:
    app_analysis.module_analysis_submenu(
        cfg,
        clear_screen_fn=clear_screen,
        print_menu_fn=_print_menu,
        menu_option_factory=_menu_option,
        quit_app_fn=quit_app,
        run_module_duplicates_analysis_fn=run_module_duplicates_analysis,
        run_module_find_by_name_fn=run_module_find_by_name,
        run_module_tree_debug_fn=run_module_tree_debug,
        run_graphics_rules_validation_fn=run_graphics_rules_validation,
        pause_fn=pause,
    )


def interface_communication_submenu(cfg: ConfigDict) -> None:
    app_analysis.interface_communication_submenu(
        cfg,
        clear_screen_fn=clear_screen,
        print_menu_fn=_print_menu,
        menu_option_factory=_menu_option,
        quit_app_fn=quit_app,
        run_mms_interface_analysis_fn=run_mms_interface_analysis,
        run_icf_validation_fn=run_icf_validation,
        run_icf_formatter_fn=run_icf_formatter,
        pause_fn=pause,
    )


def code_quality_submenu(cfg: ConfigDict) -> None:
    app_analysis.code_quality_submenu(
        cfg,
        clear_screen_fn=clear_screen,
        print_menu_fn=_print_menu,
        menu_option_factory=_menu_option,
        quit_app_fn=quit_app,
        run_comment_code_analysis_fn=run_comment_code_analysis,
        pause_fn=pause,
    )


def analyzer_catalog_menu(cfg: ConfigDict) -> None:
    app_analysis.analyzer_catalog_menu(
        cfg,
        clear_screen_fn=clear_screen,
        print_menu_fn=_print_menu,
        menu_option_factory=_menu_option,
        quit_app_fn=quit_app,
        get_enabled_analyzers_fn=_get_enabled_analyzers,
        run_checks_fn=_run_checks,
        pause_fn=pause,
    )


def advanced_analysis_menu(cfg: ConfigDict) -> None:
    app_analysis.advanced_analysis_menu(
        cfg,
        clear_screen_fn=clear_screen,
        print_menu_fn=_print_menu,
        menu_option_factory=_menu_option,
        quit_app_fn=quit_app,
        run_datatype_usage_analysis_fn=run_datatype_usage_analysis,
        run_debug_variable_usage_fn=run_debug_variable_usage,
        run_module_localvar_analysis_fn=run_module_localvar_analysis,
        pause_fn=pause,
    )


def analysis_menu(cfg: ConfigDict) -> None:
    app_analysis.analysis_menu(
        cfg,
        clear_screen_fn=clear_screen,
        print_menu_fn=_print_menu,
        menu_option_factory=_menu_option,
        quit_app_fn=quit_app,
        run_checks_fn=_run_checks,
        variable_usage_submenu_fn=variable_usage_submenu,
        module_analysis_submenu_fn=module_analysis_submenu,
        interface_communication_submenu_fn=interface_communication_submenu,
        code_quality_submenu_fn=code_quality_submenu,
        analyzer_catalog_menu_fn=analyzer_catalog_menu,
        advanced_analysis_menu_fn=advanced_analysis_menu,
        summarize_targets_fn=_summarize_targets,
        pause_fn=pause,
    )


def run_module_duplicates_analysis(cfg: ConfigDict) -> None:
    app_analysis.run_module_duplicates_analysis(
        cfg,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def run_module_find_by_name(cfg: ConfigDict) -> None:
    app_analysis.run_module_find_by_name(
        cfg,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def run_module_tree_debug(cfg: ConfigDict) -> None:
    app_analysis.run_module_tree_debug(
        cfg,
        prompt_fn=prompt,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def run_analysis_menu(cfg: ConfigDict) -> None:
    app_analysis.run_analysis_menu(cfg, analysis_menu_fn=analysis_menu)


def variable_analysis_menu(cfg: ConfigDict) -> None:
    app_analysis.variable_analysis_menu(cfg, analysis_menu_fn=analysis_menu)


def run_module_localvar_analysis(cfg: ConfigDict) -> None:
    app_analysis.run_module_localvar_analysis(
        cfg,
        load_project_fn=load_project,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def _get_enabled_analyzers() -> list[Any]:
    return cast(list[Any], get_default_cli_analyzers())


def _get_selectable_analyzers() -> list[Any]:
    return cast(list[Any], get_default_analyzers())


def _run_checks(cfg: ConfigDict, selected_keys: list[str] | None) -> None:
    app_analysis.run_checks(
        cfg,
        selected_keys,
        iter_loaded_projects_fn=_iter_loaded_projects,
        get_enabled_analyzers_fn=_get_selectable_analyzers if selected_keys else _get_enabled_analyzers,
        target_is_library_fn=_target_is_library,
        pause_fn=pause,
    )


def run_checks_menu(cfg: ConfigDict) -> None:
    app_analysis.run_checks_menu(cfg, run_checks_fn=_run_checks)


def run_mms_interface_analysis(cfg: ConfigDict) -> None:
    app_analysis.run_mms_interface_analysis(
        cfg,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def run_icf_validation(cfg: ConfigDict) -> None:
    def _load_program_ast(local_cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
        return load_program_ast(local_cfg, program_name, force_dependency_resolution=True)

    app_analysis.run_icf_validation(
        cfg,
        configured_icf_files_fn=_configured_icf_files,
        load_program_ast_fn=_load_program_ast,
        validate_icf_entries_against_program_fn=validate_icf_entries_against_program,
        pause_fn=pause,
    )


def run_debug_variable_usage(cfg: ConfigDict) -> None:
    app_analysis.run_debug_variable_usage(
        cfg,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def run_comment_code_analysis(cfg: ConfigDict) -> None:
    app_analysis.run_comment_code_analysis(
        cfg,
        iter_loaded_projects_fn=_iter_loaded_projects,
        source_paths_for_current_target_fn=_source_paths_for_current_target,
        pause_fn=pause,
    )


def run_advanced_datatype_analysis(cfg: ConfigDict) -> None:
    app_analysis.run_advanced_datatype_analysis(
        cfg,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def dump_menu(cfg: ConfigDict) -> None:
    app_menus.dump_menu(
        cfg,
        clear_screen_fn=clear_screen,
        print_menu_fn=_print_menu,
        menu_option_factory=_menu_option,
        quit_app_fn=quit_app,
        confirm_fn=confirm,
        iter_loaded_projects_fn=_iter_loaded_projects,
        analyze_variables_fn=analyze_variables,
    )


# ----------------------------
# Config submenu
# ----------------------------


def config_menu(cfg: ConfigDict) -> bool:
    return cast(
        bool,
        app_menus.config_menu(
            cfg,
            config_path=CONFIG_PATH,
            clear_screen_fn=clear_screen,
            show_config_fn=show_config,
            print_menu_fn=_print_menu,
            menu_option_factory=_menu_option,
            prompt_fn=prompt,
            pause_fn=pause,
            confirm_fn=confirm,
            target_exists_fn=target_exists,
            save_config_fn=save_config,
            apply_debug_fn=apply_debug,
            graphics_rules_menu_fn=graphics_rules_menu,
            quit_app_fn=quit_app,
        ),
    )


def tools_menu(cfg: ConfigDict) -> None:
    app_menus.tools_menu(
        cfg,
        clear_screen_fn=clear_screen,
        print_menu_fn=_print_menu,
        menu_option_factory=_menu_option,
        quit_app_fn=quit_app,
        self_check_fn=self_check,
        pause_fn=pause,
        require_targets_for_menu_action_fn=_require_targets_for_menu_action,
        dump_menu_fn=dump_menu,
        confirm_fn=confirm,
        force_refresh_ast_fn=force_refresh_ast,
    )


# ----------------------------
# Main loop
# ----------------------------
def main(argv: list[str] | None = None) -> int:
    cli_args = [] if argv is None else argv
    if cli_args:
        return run_cli(cli_args)

    try:
        cfg, default_used = load_config(CONFIG_PATH)
        apply_debug(cfg)
        if default_used:
            emit_output("Warning: Default config created. Open Setup before running analysis.")
            pause()
        else:
            if not self_check(cfg) and not confirm("Self-check failed. Continue?"):
                return 0
            if _has_analyzed_targets(cfg) and not ensure_ast_cache(cfg):
                pause()
        app_menus.run_main_loop(
            cfg,
            clear_screen_fn=clear_screen,
            print_menu_fn=_print_menu,
            menu_option_factory=_menu_option,
            summarize_targets_fn=_summarize_targets,
            require_targets_for_menu_action_fn=_require_targets_for_menu_action,
            analysis_menu_fn=analysis_menu,
            documentation_menu_fn=documentation_menu,
            config_menu_fn=config_menu,
            tools_menu_fn=tools_menu,
            show_help_fn=show_help,
            confirm_fn=confirm,
            save_config_fn=save_config,
            config_path=CONFIG_PATH,
            quit_app_fn=quit_app,
        )
        return 0
    except QuitAppError:
        return 0


def cli() -> int:
    return main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(cli())
