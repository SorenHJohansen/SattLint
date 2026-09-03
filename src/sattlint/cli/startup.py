# pyright: reportUnusedFunction=false
"""Interactive startup and menu composition for the CLI layer.

Direct replacement for the old ``application.startup`` surface, relocated
from ``application/`` to ``cli/`` as part of Phase 6 (application-layer
refactor).  This module wires the owning implementations
(:mod:`sattlint._app_interactive_menus`, :mod:`sattlint._app_startup`,
:mod:`sattlint._config_display`,
:mod:`sattlint.app_support`) directly, keeping the interactive loop
independent of the legacy ``app`` module.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .. import _app_interactive_menus as interactive_core
from .. import _app_startup as startup_core
from .. import _config_display, app_support
from .. import app_analysis as app_analysis_module
from .. import app_base as app_base_module
from .. import console as console_module
from ..application import analyze as analyze_application
from ..application import project as project_application
from ..application._interaction import (
    clear_textual_menu_interaction as _ui_clear_textual_menu_interaction,
)
from ..application._interaction import get_interactive_ui_mode as _ui_get_interactive_ui_mode
from ..application._interaction import reset_interactive_ui_mode as _ui_reset_interactive_ui_mode
from ..application._interaction import set_interactive_ui_mode as _ui_set_interactive_ui_mode
from ..application._interaction import set_textual_menu_interaction as _ui_set_textual_menu_interaction
from ..application._interaction import textual_menu_interaction as _ui_textual_menu_interaction
from ..config_types import ConfigDict
from . import app_commands as commands_application

QuitAppError = app_base_module.QuitAppError


@dataclass(frozen=True)
class MenuOption:
    key: str
    label: str
    description: str = ""


def menu_option(key: str, label: str, description: str) -> MenuOption:
    return MenuOption(key, label, description)


def get_interactive_ui_mode() -> str:
    return _ui_get_interactive_ui_mode()


def set_interactive_ui_mode(ui_mode: str | None) -> None:
    _ui_set_interactive_ui_mode(ui_mode)


def reset_interactive_ui_mode() -> None:
    _ui_reset_interactive_ui_mode()


def set_textual_menu_interaction(interaction: Any) -> None:
    _ui_set_textual_menu_interaction(interaction)


def clear_textual_menu_interaction() -> None:
    _ui_clear_textual_menu_interaction()


def clear_screen() -> None:
    if _ui_textual_menu_interaction() is not None:
        return
    app_base_module.clear_screen(
        os_module=os,
        sys_module=sys,
        clear_windows_console=app_base_module.clear_windows_console,
    )


def pause() -> None:
    interaction = _ui_textual_menu_interaction()
    if interaction is not None:
        interaction.pause()
        return
    app_base_module.pause()


def confirm(msg: str) -> bool:
    interaction = _ui_textual_menu_interaction()
    if interaction is not None:
        return bool(interaction.confirm(msg))
    return app_base_module.confirm(msg)


def prompt(msg: str, default: str | None = None) -> str:
    interaction = _ui_textual_menu_interaction()
    if interaction is not None:
        return str(interaction.prompt(msg, default))
    return app_base_module.prompt(msg, default)


def quit_app() -> None:
    app_base_module.quit_app(clear_screen_fn=clear_screen)


def print_menu(
    title: str,
    options: Sequence[Any],
    *,
    intro: str | None = None,
    note: str | None = None,
) -> None:
    interactive_core.print_menu(
        title,
        options,
        intro=intro,
        note=note,
        print_menu_owner_fn=app_support.print_menu,
        print_fn=print,
    )


def _choose_menu_option(
    title: str,
    options: Sequence[Any],
    *,
    intro: str | None = None,
    note: str | None = None,
) -> str:
    return app_base_module.choose_menu_option(
        title,
        options,
        print_menu_fn=print_menu,
        intro=intro,
        note=note,
    )


def build_menu_interaction() -> Any:
    from ..application.interaction import build_menu_interaction as _build_menu_interaction  # noqa: PLC0415

    interaction = _ui_textual_menu_interaction()
    if interaction is not None:
        return interaction
    return _build_menu_interaction(
        print_menu_fn=print_menu,
        choose_menu_option_fn=_choose_menu_option,
        prompt_fn=prompt,
        confirm_fn=confirm,
        pause_fn=pause,
    )


def resolve_interactive_ui_mode(cfg: ConfigDict, override_ui_mode: str | None = None) -> str:
    del cfg
    requested_ui = override_ui_mode or os.environ.get("SATTLINT_UI")
    if requested_ui is not None and requested_ui.strip().casefold() not in {"", "textual"}:
        raise ValueError("SattLint interactive mode is Textual-only; --ui must be 'textual'.")

    from ..app_textual import has_textual  # noqa: PLC0415

    if has_textual():
        return "textual"
    raise RuntimeError("Textual is required for interactive startup, but it is unavailable in this environment.")


def analysis_handler_fns() -> dict[str, Callable[..., Any]]:
    return {
        "run_variable_analysis": analyze_application.run_variable_analysis,
        "_run_checks": analyze_application.run_checks,
        "run_checks_menu": run_checks_menu,
        "run_mms_interface_analysis": analyze_application.run_mms_interface_analysis,
        "run_icf_validation": analyze_application.run_icf_validation,
        "run_comment_code_analysis": analyze_application.run_comment_code_analysis,
    }


def run_interactive_session(cfg: ConfigDict, **kwargs: Any) -> None:
    # Phase-4 bridge: the Textual shell now binds direct handler functions and
    # interaction state, so the legacy ``app`` module is no longer involved.
    from .._app_textual_app import run_textual_shell  # noqa: PLC0415

    kwargs.setdefault("get_help_text_fn", get_help_text)
    kwargs.setdefault("self_check_fn", app_base_module.self_check)
    kwargs.setdefault("force_refresh_ast_fn", project_application.refresh_analysis_caches)
    kwargs.setdefault("has_analyzed_targets_fn", project_application.has_analyzed_targets)
    kwargs.setdefault("ensure_ast_cache_fn", project_application.ensure_ast_cache)
    kwargs.setdefault("set_textual_menu_interaction_fn", set_textual_menu_interaction)
    kwargs.setdefault("clear_textual_menu_interaction_fn", clear_textual_menu_interaction)
    kwargs.setdefault("analysis_handler_fns", analysis_handler_fns())
    kwargs.setdefault("get_enabled_analyzers_fn", analyze_application.get_enabled_analyzers)
    run_textual_shell(cfg, **kwargs)


def summarize_targets(cfg: ConfigDict) -> str:
    return interactive_core.summarize_targets(
        cfg,
        summarize_targets_fn=app_support.summarize_targets,
        get_analyzed_targets_fn=project_application.get_analyzed_targets,
    )


def show_help(cfg: ConfigDict) -> None:
    interactive_core.show_help(
        cfg,
        show_help_fn=app_support.show_help,
        clear_screen_fn=clear_screen,
        get_analyzed_targets_fn=project_application.get_analyzed_targets,
        summarize_targets_fn=summarize_targets,
        print_fn=print,
        pause_fn=pause,
    )


def get_help_text(cfg: ConfigDict) -> str:
    return interactive_core.get_help_text(
        cfg,
        get_help_text_fn=app_support.get_help_text,
        get_analyzed_targets_fn=project_application.get_analyzed_targets,
        summarize_targets_fn=summarize_targets,
    )


def build_cli_parser() -> argparse.ArgumentParser:
    return app_base_module.build_cli_parser()


def show_config(cfg: ConfigDict) -> None:
    interactive_core.show_config(
        cfg,
        show_config_fn=_config_display.show_config,
    )


def run_checks_menu(cfg: ConfigDict) -> None:
    app_analysis_module.run_checks_menu(cfg, run_checks_fn=analyze_application.run_checks)


def main(argv: list[str] | None = None, *, run_interactive_session_fn: Callable[..., None] | None = None) -> int:
    interactive_session_runner = run_interactive_session
    if run_interactive_session_fn is not None:
        interactive_session_runner = run_interactive_session_fn

    return startup_core.main(
        argv,
        run_cli_fn=commands_application.run_cli,
        build_cli_parser_fn=build_cli_parser,
        load_config_fn=app_base_module.load_config,
        config_path=app_base_module.CONFIG_PATH,
        apply_debug_fn=app_base_module.apply_debug,
        resolve_interactive_ui_mode_fn=resolve_interactive_ui_mode,
        set_interactive_ui_mode_fn=set_interactive_ui_mode,
        reset_interactive_ui_mode_fn=reset_interactive_ui_mode,
        emit_output_fn=console_module.print_output,
        pause_fn=pause,
        self_check_fn=app_base_module.self_check,
        confirm_fn=confirm,
        has_analyzed_targets_fn=project_application.has_analyzed_targets,
        ensure_ast_cache_fn=project_application.ensure_ast_cache,
        run_main_loop_fn=interactive_session_runner,
        clear_screen_fn=clear_screen,
        print_menu_fn=print_menu,
        choose_menu_option_fn=_choose_menu_option,
        menu_option_factory=menu_option,
        summarize_targets_fn=summarize_targets,
        require_targets_for_menu_action_fn=project_application.require_targets_for_menu_action,
        show_help_fn=show_help,
        save_config_fn=app_base_module.save_config,
        quit_app_fn=quit_app,
        quit_app_error=QuitAppError,
    )


def cli(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    return main(list(argv))
