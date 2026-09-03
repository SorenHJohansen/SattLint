#!/usr/bin/env python3
# pyright: reportPrivateUsage=false, reportUnusedFunction=false
# ruff: noqa: PLC0415
"""CLI entry points and interactive helpers for SattLint."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import _app_analysis_checks as app_analysis_checks_module
from . import _app_analysis_commands as app_analysis_commands_module
from . import analysis_catalog as analysis_catalog_module
from . import app_analysis as app_analysis_module
from . import app_base as app_base_module
from . import app_support as app_support_module
from . import cache as cache_module
from . import config as _config_module
from . import console as console_module
from . import engine as engine_module_impl
from .analyzers.variables import (
    IssueKind,
)
from .application import analyze as analyze_application
from .application import interaction as app_interaction_module
from .application import project as project_application
from .application._interaction import (
    has_textual_menu_interaction,
    textual_menu_interaction,
)
from .cli import app_cli_commands as app_cli_commands_module
from .cli import app_commands as commands_application
from .cli import startup as startup_application
from .core import telemetry as app_telemetry_module
from .core.semantic import load_workspace_snapshot
from .models.project_graph import ProjectGraph

load_workspace_snapshot = load_workspace_snapshot

ConfigDict = _config_module.ConfigDict
LoadedProject = tuple[str, BasePicture, ProjectGraph]
VariableAnalysisSelection = set[IssueKind] | None
VariableAnalysisMap = dict[str, tuple[str, VariableAnalysisSelection]]
LoadedConfig = tuple[ConfigDict, bool]
ConfigValidationResult = _config_module.ConfigValidationResult

app_analysis: Any = app_analysis_module
app_analysis_checks: Any = app_analysis_checks_module
app_analysis_commands: Any = app_analysis_commands_module
app_base: Any = app_base_module
app_cli_commands: Any = app_cli_commands_module
app_support: Any = app_support_module
app_telemetry: Any = app_telemetry_module
cache: Any = cache_module
engine_module: Any = engine_module_impl
get_default_cli_analyzers = analysis_catalog_module.get_default_cli_analyzers
get_selectable_analyzers = analysis_catalog_module.get_selectable_analyzers
analyze_variables = app_analysis_module.analyze_variables
ASTCache = cache_module.ASTCache

VARIABLE_ANALYSES: VariableAnalysisMap = app_analysis.VARIABLE_ANALYSES
HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS: tuple[str, ...] = app_analysis.HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS
LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS: tuple[str, ...] = app_analysis.LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS
emit_output: Callable[..., None] = console_module.print_output  # type: ignore[assignment]

EXIT_SUCCESS: int = app_base.EXIT_SUCCESS
EXIT_FAILURE: int = app_base.EXIT_FAILURE
EXIT_USAGE_ERROR: int = app_base.EXIT_USAGE_ERROR

CONFIG_PATH: Path = app_base.CONFIG_PATH
DEFAULT_CONFIG: ConfigDict = app_base.DEFAULT_CONFIG


MenuOption = startup_application.MenuOption


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


def self_check(cfg: ConfigDict) -> bool:
    return cast(bool, app_base.self_check(cfg))


validate_effective_config = _config_module.validate_effective_config


log: Any = app_base.log


# ----------------------------
# Helpers
# ----------------------------
def _clear_windows_console() -> None:
    app_base.clear_windows_console()


def clear_screen() -> None:
    if has_textual_menu_interaction():
        return
    app_base.clear_screen(os_module=os, sys_module=sys, clear_windows_console=_clear_windows_console)


def pause() -> None:
    interaction = textual_menu_interaction()
    if interaction is not None:
        interaction.pause()
        return
    app_base.pause()


QuitAppError = app_base.QuitAppError


def quit_app() -> None:
    app_base.quit_app(clear_screen_fn=clear_screen)


def confirm(msg: str) -> bool:
    interaction = textual_menu_interaction()
    if interaction is not None:
        return bool(interaction.confirm(msg))
    return cast(bool, app_base.confirm(msg))


def prompt(msg: str, default: str | None = None) -> str:
    interaction = textual_menu_interaction()
    if interaction is not None:
        return str(interaction.prompt(msg, default))
    return cast(str, app_base.prompt(msg, default))


def target_exists(target: str, cfg: ConfigDict) -> bool:
    return cast(bool, app_base.target_exists(target, cfg))


def apply_debug(cfg: ConfigDict) -> None:
    app_base.apply_debug(cfg)


def build_cli_parser() -> argparse.ArgumentParser:
    return cast(argparse.ArgumentParser, app_base.build_cli_parser())


def run_syntax_check_command(file_path: str, *, output_format: str = "text") -> int:
    return cast(int, app_base.run_syntax_check_command(file_path, output_format=output_format))


run_cli = commands_application.run_cli
run_validate_config_command = commands_application.run_validate_config_command
run_analyze_command = commands_application.run_analyze_command
run_cache_prune_command = commands_application.run_cache_prune_command
show_config = commands_application.show_config


def _print_menu(
    title: str,
    options: Sequence[MenuOption],
    *,
    intro: str | None = None,
    note: str | None = None,
) -> None:
    startup_application.print_menu(title, options, intro=intro, note=note)


def set_interactive_ui_mode(ui_mode: str | None) -> None:
    from .application._interaction import set_interactive_ui_mode as _set

    _set(ui_mode)


def reset_interactive_ui_mode() -> None:
    from .application._interaction import reset_interactive_ui_mode as _reset

    _reset()


def get_interactive_ui_mode() -> str:
    from .application._interaction import get_interactive_ui_mode as _get

    return _get()


def set_textual_menu_interaction(interaction: Any) -> None:
    from .application._interaction import set_textual_menu_interaction as _set

    _set(interaction)


def clear_textual_menu_interaction() -> None:
    from .application._interaction import clear_textual_menu_interaction as _clear

    _clear()


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
    interaction = textual_menu_interaction()
    if interaction is not None:
        return interaction
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

    from . import app_textual as app_textual_module

    if app_textual_module.has_textual():
        return "textual"
    raise RuntimeError("Textual is required for interactive startup, but it is unavailable in this environment.")


def run_interactive_session(cfg: ConfigDict, **kwargs: Any) -> None:
    from .cli import startup as cli_startup

    cli_startup.run_interactive_session(cfg, **kwargs)


def _menu_option(key: str, label: str, description: str) -> MenuOption:
    return MenuOption(key, label, description)


_summarize_targets = startup_application.summarize_targets
show_help = startup_application.show_help
get_help_text = startup_application.get_help_text
_get_analyzed_targets = project_application.get_analyzed_targets
_require_analyzed_targets = project_application.require_analyzed_targets
_has_analyzed_targets = project_application.has_analyzed_targets
_require_targets_for_menu_action = project_application.require_targets_for_menu_action
_cache_key_for_target = project_application.cache_key_for_target
_split_csv_values = project_application.split_csv_values


config_module = _config_module
validate_icf_entries_against_program: Callable[..., Any] = app_analysis.validate_icf_entries_against_program


_iter_loaded_projects = project_application.iter_loaded_projects
_source_paths_for_current_target = project_application.source_paths_for_current_target
_target_is_library = project_application.target_is_library
load_project = project_application.load_project
load_program_ast = project_application.load_program_ast
force_refresh_ast = project_application.force_refresh_ast
ensure_ast_cache = project_application.ensure_ast_cache
refresh_analysis_caches = project_application.refresh_analysis_caches
run_variable_analysis = analyze_application.run_variable_analysis
_get_enabled_analyzers = analyze_application._get_enabled_analyzers
_get_selectable_analyzers = analyze_application._get_selectable_analyzers
_run_checks = analyze_application.run_checks
run_checks_menu = startup_application.run_checks_menu
run_mms_interface_analysis = analyze_application.run_mms_interface_analysis
run_icf_validation = analyze_application.run_icf_validation
run_comment_code_analysis = analyze_application.run_comment_code_analysis


# ----------------------------
# Main loop
# ----------------------------
_COMPATIBILITY_HELPERS = (
    _print_menu,
    _menu_option,
    _summarize_targets,
    _require_targets_for_menu_action,
    _split_csv_values,
)


def main(argv: list[str] | None = None) -> int:
    from .cli import startup as cli_startup

    return cli_startup.main(argv, run_interactive_session_fn=run_interactive_session)


def cli(argv: list[str] | None = None) -> int:
    from .cli import startup as cli_startup

    return cli_startup.cli(argv)


if __name__ == "__main__":
    raise SystemExit(cli())
