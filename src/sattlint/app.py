#!/usr/bin/env python3
"""CLI entry points and interactive helpers for SattLint."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import _app_analysis_checks as app_analysis_checks_module
from . import _app_analysis_commands as app_analysis_commands_module
from . import _app_facade_analysis as app_facade_analysis_module
from . import _app_facade_commands as app_facade_commands_module
from . import _app_facade_project as app_facade_project_module
from . import _app_startup_from_app as app_startup_module
from . import analysis_catalog as analysis_catalog_module
from . import app_analysis as app_analysis_module
from . import app_base as app_base_module
from . import app_cli_commands as app_cli_commands_module
from . import app_docs as app_docs_module
from . import app_graphics as app_graphics_module
from . import app_interaction as app_interaction_module
from . import app_menus as app_menus_module
from . import app_support as app_support_module
from . import app_telemetry as app_telemetry_module
from . import cache as cache_module
from . import config as _config_module
from . import console as console_module
from . import engine as engine_module_impl
from . import telemetry_summary as telemetry_summary_module
from .analyzers.variables import (
    IssueKind,
)
from .models.project_graph import ProjectGraph

ConfigDict = _config_module.ConfigDict
LoadedProject = tuple[str, BasePicture, ProjectGraph]
VariableAnalysisSelection = set[IssueKind] | None
VariableAnalysisMap = dict[str, tuple[str, VariableAnalysisSelection]]
GraphicsRulesConfig = dict[str, Any]
GraphicsRulesLoadResult = tuple[GraphicsRulesConfig, bool]
DocumentationSelection = dict[str, Any]
LoadedConfig = tuple[ConfigDict, bool]
ConfigValidationResult = _config_module.ConfigValidationResult

app_analysis: Any = app_analysis_module
app_analysis_checks: Any = app_analysis_checks_module
app_analysis_commands: Any = app_analysis_commands_module
app_base: Any = app_base_module
app_cli_commands: Any = app_cli_commands_module
app_docs: Any = app_docs_module
app_graphics: Any = app_graphics_module
app_menus: Any = app_menus_module
app_support: Any = app_support_module
app_telemetry: Any = app_telemetry_module
cache: Any = cache_module
engine_module: Any = engine_module_impl
telemetry_summary: Any = telemetry_summary_module
source_diff_report_module: Any = importlib.import_module("sattlint.devtools.source_diff_report")
get_default_cli_analyzers = analysis_catalog_module.get_default_cli_analyzers
get_selectable_analyzers = analysis_catalog_module.get_selectable_analyzers

_APP_MODULE: Any = sys.modules[__name__]
_interactive_ui_mode = "textual"
_textual_menu_interaction: Any | None = None

VARIABLE_ANALYSES: VariableAnalysisMap = app_analysis.VARIABLE_ANALYSES
HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS: tuple[str, ...] = app_analysis.HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS
LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS: tuple[str, ...] = app_analysis.LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS
emit_output: Callable[..., None] = console_module.print_output  # type: ignore[assignment]

EXIT_SUCCESS: int = app_base.EXIT_SUCCESS
EXIT_FAILURE: int = app_base.EXIT_FAILURE
EXIT_USAGE_ERROR: int = app_base.EXIT_USAGE_ERROR

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
    if _interactive_ui_mode == "textual" and _textual_menu_interaction is not None:
        return
    app_base.clear_screen(os_module=os, sys_module=sys, clear_windows_console=_clear_windows_console)


def pause() -> None:
    if _interactive_ui_mode == "textual" and _textual_menu_interaction is not None:
        _textual_menu_interaction.pause()
        return
    app_base.pause()


QuitAppError = app_base.QuitAppError


def quit_app() -> None:
    app_base.quit_app(clear_screen_fn=clear_screen)


def confirm(msg: str) -> bool:
    if _interactive_ui_mode == "textual" and _textual_menu_interaction is not None:
        return bool(_textual_menu_interaction.confirm(msg))
    return cast(bool, app_base.confirm(msg))


def prompt(msg: str, default: str | None = None) -> str:
    if _interactive_ui_mode == "textual" and _textual_menu_interaction is not None:
        return str(_textual_menu_interaction.prompt(msg, default))
    return cast(str, app_base.prompt(msg, default))


def target_exists(target: str, cfg: ConfigDict) -> bool:
    return cast(bool, app_base.target_exists(target, cfg))


def apply_debug(cfg: ConfigDict) -> None:
    app_base.apply_debug(cfg)


def build_cli_parser() -> argparse.ArgumentParser:
    return cast(argparse.ArgumentParser, app_base.build_cli_parser())


def run_syntax_check_command(file_path: str, *, output_format: str = "text") -> int:
    return cast(int, app_base.run_syntax_check_command(file_path, output_format=output_format))


run_cli = app_facade_commands_module.run_cli
run_validate_config_command = app_facade_commands_module.run_validate_config_command
run_analyze_command = app_facade_commands_module.run_analyze_command
_simulate_target = app_facade_commands_module._simulate_target
run_simulate_command = app_facade_commands_module.run_simulate_command
run_docgen_command = app_facade_commands_module.run_docgen_command
run_cache_prune_command = app_facade_commands_module.run_cache_prune_command
run_telemetry_summary_command = app_facade_commands_module.run_telemetry_summary_command
_configured_icf_files = app_facade_commands_module._configured_icf_files
run_format_icf_command = app_facade_commands_module.run_format_icf_command
run_trace_command = app_facade_commands_module.run_trace_command
run_icf_formatter = app_facade_commands_module.run_icf_formatter
show_config = app_facade_commands_module.show_config


def _print_menu(
    title: str,
    options: Sequence[MenuOption],
    *,
    intro: str | None = None,
    note: str | None = None,
) -> None:
    app_startup_module.print_menu_from_app(title, options, intro=intro, note=note, app_module=_APP_MODULE)


def set_interactive_ui_mode(ui_mode: str | None) -> None:
    global _interactive_ui_mode
    if ui_mode == "textual":
        _interactive_ui_mode = ui_mode
        return
    _interactive_ui_mode = "textual"


def reset_interactive_ui_mode() -> None:
    set_interactive_ui_mode("textual")
    clear_textual_menu_interaction()


def get_interactive_ui_mode() -> str:
    return _interactive_ui_mode


def set_textual_menu_interaction(interaction: Any) -> None:
    global _textual_menu_interaction
    _textual_menu_interaction = interaction


def clear_textual_menu_interaction() -> None:
    global _textual_menu_interaction
    _textual_menu_interaction = None


def choose_menu_option(
    title: str,
    options: Sequence[MenuOption],
    *,
    intro: str | None = None,
    note: str | None = None,
) -> str:
    return cast(
        str,
        app_base.choose_menu_option(
            title,
            options,
            print_menu_fn=_print_menu,
            intro=intro,
            note=note,
        ),
    )


def build_menu_interaction() -> Any:
    if _textual_menu_interaction is not None:
        return _textual_menu_interaction
    return app_interaction_module.build_menu_interaction(
        print_menu_fn=_print_menu,
        choose_menu_option_fn=choose_menu_option,
        prompt_fn=prompt,
        confirm_fn=confirm,
        pause_fn=pause,
    )


def resolve_interactive_ui_mode(cfg: ConfigDict, override_ui_mode: str | None = None) -> str:
    del cfg
    requested_ui = override_ui_mode or os.environ.get("SATTLINT_UI")
    if requested_ui is not None and requested_ui.strip().casefold() not in {"", "textual"}:
        raise ValueError("SattLint interactive mode is Textual-only; --ui must be 'textual'.")

    from . import app_textual as app_textual_module  # noqa: PLC0415

    if app_textual_module.has_textual():
        return "textual"
    raise RuntimeError("Textual is required for interactive startup, but it is unavailable in this environment.")


def run_interactive_session(cfg: ConfigDict, **kwargs: Any) -> None:
    from . import app_textual as app_textual_module  # noqa: PLC0415

    kwargs.setdefault("get_help_text_fn", get_help_text)
    app_textual_module.run_textual_shell(cfg, app_module=_APP_MODULE, **kwargs)


def _menu_option(key: str, label: str, description: str) -> MenuOption:
    return MenuOption(key, label, description)


_summarize_targets = app_facade_project_module._summarize_targets
show_help = app_facade_project_module.show_help
get_help_text = app_facade_project_module.get_help_text
_get_analyzed_targets = app_facade_project_module._get_analyzed_targets
_require_analyzed_targets = app_facade_project_module._require_analyzed_targets
_has_analyzed_targets = app_facade_project_module._has_analyzed_targets
_require_targets_for_menu_action = app_facade_project_module._require_targets_for_menu_action
_cache_key_for_target = app_facade_project_module._cache_key_for_target
_split_csv_values = app_facade_project_module._split_csv_values


_graphics_rule_label: Callable[[dict[str, Any]], str] = app_graphics.graphics_rule_label
_graphics_rule_config_line: Callable[[dict[str, Any]], str] = app_graphics.graphics_rule_config_line
_print_graphics_rules_summary: Callable[..., None] = app_graphics.print_graphics_rules_summary
config_module = _config_module
classify_documentation_structure: Callable[..., Any] = app_docs.classify_documentation_structure
discover_documentation_unit_candidates: Callable[..., list[Any]] = app_docs.discover_documentation_unit_candidates
validate_icf_entries_against_program: Callable[..., Any] = app_analysis.validate_icf_entries_against_program


_discover_graphics_rule_selector_options = app_facade_project_module._discover_graphics_rule_selector_options
_pick_or_prompt_graphics_rule_selector_value = app_facade_project_module._pick_or_prompt_graphics_rule_selector_value
_annotate_graphics_entries_with_structure_paths = (
    app_facade_project_module._annotate_graphics_entries_with_structure_paths
)
graphics_rules_menu = app_facade_project_module.graphics_rules_menu
_prompt_graphics_rule_definition_with_config = app_facade_project_module._prompt_graphics_rule_definition_with_config
_collect_graphics_layout_entries_for_target = app_facade_project_module._collect_graphics_layout_entries_for_target
run_graphics_rules_validation = app_facade_project_module.run_graphics_rules_validation
_get_documentation_unit_selection = app_facade_project_module._get_documentation_unit_selection
preview_documentation_unit_candidates = app_facade_project_module.preview_documentation_unit_candidates
configure_documentation_scope_by_moduletype = app_facade_project_module.configure_documentation_scope_by_moduletype
configure_documentation_scope_by_instance_path = (
    app_facade_project_module.configure_documentation_scope_by_instance_path
)
reset_documentation_scope = app_facade_project_module.reset_documentation_scope
run_generate_documentation = app_facade_project_module.run_generate_documentation
documentation_menu = app_facade_project_module.documentation_menu
_iter_loaded_projects = app_facade_project_module._iter_loaded_projects
_source_paths_for_current_target = app_facade_project_module._source_paths_for_current_target
_target_is_library = app_facade_project_module._target_is_library
load_project = app_facade_project_module.load_project
load_program_ast = app_facade_project_module.load_program_ast
force_refresh_ast = app_facade_project_module.force_refresh_ast
ensure_ast_cache = app_facade_project_module.ensure_ast_cache
refresh_analysis_caches = app_facade_project_module.refresh_analysis_caches
run_variable_analysis = app_facade_analysis_module.run_variable_analysis
run_datatype_usage_analysis = app_facade_analysis_module.run_datatype_usage_analysis
variable_usage_submenu = app_facade_analysis_module.variable_usage_submenu
module_analysis_submenu = app_facade_analysis_module.module_analysis_submenu
interface_communication_submenu = app_facade_analysis_module.interface_communication_submenu
code_quality_submenu = app_facade_analysis_module.code_quality_submenu
analyzer_catalog_menu = app_facade_analysis_module.analyzer_catalog_menu
advanced_analysis_menu = app_facade_analysis_module.advanced_analysis_menu
analysis_menu = app_facade_analysis_module.analysis_menu
run_module_duplicates_analysis = app_facade_analysis_module.run_module_duplicates_analysis
run_module_find_by_name = app_facade_analysis_module.run_module_find_by_name
run_module_tree_debug = app_facade_analysis_module.run_module_tree_debug
run_analysis_menu = app_facade_analysis_module.run_analysis_menu
variable_analysis_menu = app_facade_analysis_module.variable_analysis_menu
run_module_localvar_analysis = app_facade_analysis_module.run_module_localvar_analysis
_get_enabled_analyzers = app_facade_analysis_module._get_enabled_analyzers
_get_selectable_analyzers = app_facade_analysis_module._get_selectable_analyzers
_run_checks = app_facade_analysis_module._run_checks
run_checks_menu = app_facade_analysis_module.run_checks_menu
run_mms_interface_analysis = app_facade_analysis_module.run_mms_interface_analysis
run_icf_validation = app_facade_analysis_module.run_icf_validation
run_debug_variable_usage = app_facade_analysis_module.run_debug_variable_usage
run_comment_code_analysis = app_facade_analysis_module.run_comment_code_analysis
run_advanced_datatype_analysis = app_facade_analysis_module.run_advanced_datatype_analysis
dump_menu = app_facade_analysis_module.dump_menu
run_source_diff_report = app_facade_analysis_module.run_source_diff_report
config_menu = app_facade_analysis_module.config_menu
tools_menu = app_facade_analysis_module.tools_menu


# ----------------------------
# Main loop
# ----------------------------
_COMPATIBILITY_HELPERS = (
    _print_menu,
    _menu_option,
    _summarize_targets,
    _graphics_rule_label,
    _simulate_target,
    _require_targets_for_menu_action,
    _split_csv_values,
    _discover_graphics_rule_selector_options,
    _pick_or_prompt_graphics_rule_selector_value,
    _annotate_graphics_entries_with_structure_paths,
    _prompt_graphics_rule_definition_with_config,
    _collect_graphics_layout_entries_for_target,
    _get_documentation_unit_selection,
)


def main(argv: list[str] | None = None) -> int:
    return app_startup_module.main_from_app(argv, app_module=_APP_MODULE)


cli = cast(Callable[[], int], partial(app_startup_module.cli_from_app, app_module=_APP_MODULE))


if __name__ == "__main__":
    raise SystemExit(cli())
