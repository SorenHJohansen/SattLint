# pyright: reportUnusedFunction=false
"""Interactive startup and menu composition for the CLI layer.

Direct replacement for the old ``application.startup`` surface, relocated
from ``application/`` to ``cli/`` as part of Phase 6 (application-layer
refactor).  This module owns the interactive startup orchestration (``main``)
and the interactive-shell dispatch helpers (:mod:`sattlint.cli.menu`), keeping
the interactive loop independent of the legacy ``app`` module.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .. import config as config_module
from .. import console as console_module
from ..application import analyze as analyze_application
from ..application import change_review as change_review_application
from ..application import project as project_application
from ..config.types import ConfigDict
from ..core.interaction import (
    QuitAppError,
)
from ..core.interaction import (
    confirm as core_confirm,
)
from ..core.interaction import (
    pause as core_pause,
)
from ..core.interaction import (
    prompt as core_prompt,
)
from ..core.logging import apply_debug
from ..core.terminal import clear_screen as core_clear_screen
from ..core.terminal import clear_windows_console as core_clear_windows_console
from ..project import support as support_module
from . import entry as cli_entry
from . import menu as cli_menu
from ._interaction import (
    clear_textual_menu_interaction as _ui_clear_textual_menu_interaction,
)
from ._interaction import get_interactive_ui_mode as _ui_get_interactive_ui_mode
from ._interaction import reset_interactive_ui_mode as _ui_reset_interactive_ui_mode
from ._interaction import set_interactive_ui_mode as _ui_set_interactive_ui_mode
from ._interaction import set_textual_menu_interaction as _ui_set_textual_menu_interaction
from ._interaction import textual_menu_interaction as _ui_textual_menu_interaction


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
    core_clear_screen(
        os_module=os,
        sys_module=sys,
        clear_windows_console=core_clear_windows_console,
    )


def pause() -> None:
    interaction = _ui_textual_menu_interaction()
    if interaction is not None:
        interaction.pause()
        return
    core_pause()


def confirm(msg: str) -> bool:
    interaction = _ui_textual_menu_interaction()
    if interaction is not None:
        return bool(interaction.confirm(msg))
    return core_confirm(msg)


def prompt(msg: str, default: str | None = None) -> str:
    interaction = _ui_textual_menu_interaction()
    if interaction is not None:
        return str(interaction.prompt(msg, default))
    return core_prompt(msg, default)


def resolve_interactive_ui_mode(cfg: ConfigDict, override_ui_mode: str | None = None) -> str:
    del cfg
    requested_ui = override_ui_mode or os.environ.get("SATTLINT_UI")
    if requested_ui is not None and requested_ui.strip().casefold() not in {"", "textual"}:
        raise ValueError("SattLint interactive mode is Textual-only; --ui must be 'textual'.")

    from ..ui import has_textual  # noqa: PLC0415

    if has_textual():
        return "textual"
    raise RuntimeError("Textual is required for interactive startup, but it is unavailable in this environment.")


def analysis_handler_fns() -> dict[str, Callable[..., Any]]:
    return {
        "_run_checks": analyze_application.run_checks,
        "run_checks_result": analyze_application.run_checks_result,
        "generate_change_review": change_review_application.generate_change_review,
    }


def run_interactive_session(cfg: ConfigDict, **kwargs: Any) -> None:
    # Phase-4 bridge: the Textual shell now binds direct handler functions and
    # interaction state, so the legacy ``app`` module is no longer involved.
    from ..ui._app_textual_app import run_textual_shell  # noqa: PLC0415

    kwargs.setdefault("get_help_text_fn", get_help_text)
    kwargs.setdefault("has_analyzed_targets_fn", support_module.has_analyzed_targets)
    kwargs.setdefault("ensure_ast_cache_fn", project_application.ensure_ast_cache)
    kwargs.setdefault("set_textual_menu_interaction_fn", set_textual_menu_interaction)
    kwargs.setdefault("clear_textual_menu_interaction_fn", clear_textual_menu_interaction)
    kwargs.setdefault("analysis_handler_fns", analysis_handler_fns())
    kwargs.setdefault("get_enabled_analyzers_fn", analyze_application.get_selectable_analyzers)
    run_textual_shell(cfg, **kwargs)


def summarize_targets(cfg: ConfigDict) -> str:
    return cli_menu.summarize_targets(
        cfg,
        get_analyzed_targets_fn=support_module.get_analyzed_targets,
    )


def get_help_text(cfg: ConfigDict) -> str:
    return cli_menu.get_help_text(
        cfg,
        get_analyzed_targets_fn=support_module.get_analyzed_targets,
        summarize_targets_fn=summarize_targets,
    )


def build_cli_parser() -> object:
    from .entry import build_cli_parser as _build_cli_parser  # noqa: PLC0415

    return _build_cli_parser()


def _run_cli(argv: list[str]) -> int:
    return cli_entry.run_cli(argv, config_path=config_module.get_config_path())


def main(
    argv: list[str] | None = None,
    *,
    run_cli_fn: Callable[[list[str]], int] = _run_cli,
    load_config_fn: Callable[[Path], tuple[ConfigDict, bool]] = config_module.load_config,
    config_path: Path | None = None,
    apply_debug_fn: Callable[[ConfigDict], None] = apply_debug,
    resolve_interactive_ui_mode_fn: Callable[[ConfigDict, str | None], str] | None = resolve_interactive_ui_mode,
    set_interactive_ui_mode_fn: Callable[[str | None], None] | None = set_interactive_ui_mode,
    reset_interactive_ui_mode_fn: Callable[[], None] | None = reset_interactive_ui_mode,
    emit_output_fn: Callable[..., None] = console_module.print_output,
    pause_fn: Callable[[], None] = pause,
    run_main_loop_fn: Callable[..., None] | None = None,
    summarize_targets_fn: Callable[[ConfigDict], str] = summarize_targets,
    save_config_fn: Callable[[Path, ConfigDict], None] = config_module.save_config,
    quit_app_error: type[BaseException] = QuitAppError,
) -> int:
    if config_path is None:
        config_path = config_module.get_config_path()
    if run_main_loop_fn is None:
        run_main_loop_fn = run_interactive_session

    cli_args = [] if argv is None else argv
    if cli_args:
        return run_cli_fn(cli_args)

    try:
        # The Textual shell always opens with no project loaded. Projects are
        # opened or created from within the shell via Open Project / New Project.
        cfg, default_used = load_config_fn(config_path)

        apply_debug_fn(cfg)
        resolved_ui_mode = "textual"
        if resolve_interactive_ui_mode_fn is not None:
            resolved_ui_mode = resolve_interactive_ui_mode_fn(cfg, None)
        if default_used:
            emit_output_fn("Warning: Default config created. Open Setup before running analysis.")
            pause_fn()
        if set_interactive_ui_mode_fn is not None:
            set_interactive_ui_mode_fn(resolved_ui_mode)
        try:
            run_main_loop_kwargs: dict[str, Any] = {
                "summarize_targets_fn": summarize_targets_fn,
                "save_config_fn": save_config_fn,
                "config_path": config_path,
                "quit_app_error": quit_app_error,
            }
            run_main_loop_fn(cfg, **run_main_loop_kwargs)
        finally:
            if reset_interactive_ui_mode_fn is not None:
                reset_interactive_ui_mode_fn()
        return 0
    except quit_app_error:
        return 0


def cli(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    return main(list(argv))
