# pyright: reportUnusedFunction=false
"""Interactive startup and menu composition for the CLI layer.

Direct replacement for the old ``application.startup`` surface, relocated
from ``application/`` to ``cli/`` as part of Phase 6 (application-layer
refactor).  This module owns the interactive startup orchestration (``main``)
and the menu composition helpers (:mod:`sattlint.cli.menu`,
:mod:`sattlint._config_display`), keeping the interactive loop independent of
the legacy ``app`` module.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import config as config_module
from .. import console as console_module
from ..application import analyze as analyze_application
from ..application import checks as checks_application
from ..application import project as project_application
from ..config_types import ConfigDict
from ..core.interaction import (
    QuitAppError,
)
from ..core.interaction import (
    choose_menu_option as core_choose_menu_option,
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
from ..core.interaction import (
    quit_app as core_quit_app,
)
from ..core.logging import apply_debug
from ..core.terminal import clear_screen as core_clear_screen
from ..core.terminal import clear_windows_console as core_clear_windows_console
from ..project import discover_project, load_project, project_status
from ..project import support as support_module
from . import app_commands as commands_application
from . import config as cli_config
from . import menu as cli_menu
from ._interaction import (
    clear_textual_menu_interaction as _ui_clear_textual_menu_interaction,
)
from ._interaction import get_interactive_ui_mode as _ui_get_interactive_ui_mode
from ._interaction import reset_interactive_ui_mode as _ui_reset_interactive_ui_mode
from ._interaction import set_interactive_ui_mode as _ui_set_interactive_ui_mode
from ._interaction import set_textual_menu_interaction as _ui_set_textual_menu_interaction
from ._interaction import textual_menu_interaction as _ui_textual_menu_interaction


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


def quit_app() -> None:
    core_quit_app(clear_screen_fn=clear_screen)


def print_menu(
    title: str,
    options: Sequence[Any],
    *,
    intro: str | None = None,
    note: str | None = None,
) -> None:
    cli_menu.print_menu(
        title,
        options,
        print_fn=print,
        intro=intro,
        note=note,
    )


def _choose_menu_option(
    title: str,
    options: Sequence[Any],
    *,
    intro: str | None = None,
    note: str | None = None,
) -> str:
    return core_choose_menu_option(
        title,
        options,
        print_menu_fn=print_menu,
        intro=intro,
        note=note,
    )


def require_targets_for_menu_action(cfg: ConfigDict, action: str) -> bool:
    return support_module.require_targets_for_menu_action(
        cfg,
        action,
        has_analyzed_targets_fn=support_module.has_analyzed_targets,
        print_fn=print,
        pause_fn=pause,
    )


def build_menu_interaction() -> Any:
    from .interaction import build_menu_interaction as _build_menu_interaction  # noqa: PLC0415

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

    from ..ui import has_textual  # noqa: PLC0415

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
    from ..ui._app_textual_app import run_textual_shell  # noqa: PLC0415

    kwargs.setdefault("get_help_text_fn", get_help_text)
    kwargs.setdefault("self_check_fn", config_module.self_check)
    kwargs.setdefault("force_refresh_ast_fn", project_application.refresh_analysis_caches)
    kwargs.setdefault("has_analyzed_targets_fn", support_module.has_analyzed_targets)
    kwargs.setdefault("ensure_ast_cache_fn", project_application.ensure_ast_cache)
    kwargs.setdefault("set_textual_menu_interaction_fn", set_textual_menu_interaction)
    kwargs.setdefault("clear_textual_menu_interaction_fn", clear_textual_menu_interaction)
    kwargs.setdefault("analysis_handler_fns", analysis_handler_fns())
    kwargs.setdefault("get_enabled_analyzers_fn", analyze_application.get_enabled_analyzers)
    run_textual_shell(cfg, **kwargs)


def summarize_targets(cfg: ConfigDict) -> str:
    return cli_menu.summarize_targets(
        cfg,
        get_analyzed_targets_fn=support_module.get_analyzed_targets,
    )


def show_help(cfg: ConfigDict) -> None:
    cli_menu.show_help(
        cfg,
        clear_screen_fn=clear_screen,
        get_analyzed_targets_fn=support_module.get_analyzed_targets,
        summarize_targets_fn=summarize_targets,
        print_fn=print,
        pause_fn=pause,
    )


def get_help_text(cfg: ConfigDict) -> str:
    return cli_menu.get_help_text(
        cfg,
        get_analyzed_targets_fn=support_module.get_analyzed_targets,
        summarize_targets_fn=summarize_targets,
    )


def run_checks_menu(cfg: ConfigDict) -> None:
    checks_application.run_checks_menu(cfg, run_checks_fn=analyze_application.run_checks)


def build_cli_parser() -> argparse.ArgumentParser:
    from .entry import build_cli_parser as _build_cli_parser  # noqa: PLC0415

    return _build_cli_parser()


@dataclass(frozen=True)
class InteractiveCliOverrides:
    config_path: Path
    debug: bool
    ui_mode: str | None = None


def _build_interactive_override_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--config", default=None)
    parser.add_argument("--no-cache", action="store_true", dest="no_cache")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--ui", default=None)
    return parser


def resolve_interactive_cli_overrides(
    argv: list[str],
    *,
    default_config_path: Path,
) -> InteractiveCliOverrides | None:
    if not argv:
        return None

    try:
        parser = _build_interactive_override_parser()
        parsed_namespace, leftover = parser.parse_known_args(argv)
    except SystemExit:
        return None

    if leftover:
        return None

    command = getattr(parsed_namespace, "command", None)
    if command is not None:
        return None

    quiet = bool(getattr(parsed_namespace, "quiet", False))
    no_cache = bool(getattr(parsed_namespace, "no_cache", False))
    if quiet or no_cache:
        return None

    debug = bool(getattr(parsed_namespace, "debug", False))
    ui_mode = getattr(parsed_namespace, "ui", None)
    config_path_text = getattr(parsed_namespace, "config", None)
    if not debug and config_path_text is None and ui_mode is None:
        return None

    config_path = Path(config_path_text) if config_path_text else default_config_path
    return InteractiveCliOverrides(config_path=config_path, debug=debug, ui_mode=ui_mode)


def main(
    argv: list[str] | None = None,
    *,
    run_cli_fn: Callable[[list[str]], int] = commands_application.run_cli,
    build_cli_parser_fn: Callable[[], Any] | None = build_cli_parser,
    load_config_fn: Callable[[Path], tuple[ConfigDict, bool]] = config_module.load_config,
    config_path: Path | None = None,
    apply_debug_fn: Callable[[ConfigDict], None] = apply_debug,
    resolve_interactive_ui_mode_fn: Callable[[ConfigDict, str | None], str] | None = resolve_interactive_ui_mode,
    set_interactive_ui_mode_fn: Callable[[str | None], None] | None = set_interactive_ui_mode,
    reset_interactive_ui_mode_fn: Callable[[], None] | None = reset_interactive_ui_mode,
    emit_output_fn: Callable[..., None] = console_module.print_output,
    pause_fn: Callable[[], None] = pause,
    self_check_fn: Callable[[ConfigDict], bool] = config_module.self_check,
    confirm_fn: Callable[[str], bool] = confirm,
    has_analyzed_targets_fn: Callable[[ConfigDict], bool] = support_module.has_analyzed_targets,
    ensure_ast_cache_fn: Callable[[ConfigDict], bool] = project_application.ensure_ast_cache,
    run_main_loop_fn: Callable[..., None] | None = None,
    clear_screen_fn: Callable[[], None] = clear_screen,
    print_menu_fn: Callable[..., None] = print_menu,
    choose_menu_option_fn: Callable[..., str] | None = _choose_menu_option,
    interaction: Any | None = None,
    menu_option_factory: Callable[[str, str, str], Any] = menu_option,
    summarize_targets_fn: Callable[[ConfigDict], str] = summarize_targets,
    require_targets_for_menu_action_fn: Callable[[ConfigDict, str], bool] = require_targets_for_menu_action,
    show_help_fn: Callable[[ConfigDict], None] = show_help,
    save_config_fn: Callable[[Path, ConfigDict], None] = cli_config.save_config,
    quit_app_fn: Callable[[], None] = quit_app,
    quit_app_error: type[BaseException] = QuitAppError,
) -> int:
    if config_path is None:
        config_path = config_module.get_config_path()
    if run_main_loop_fn is None:
        run_main_loop_fn = run_interactive_session

    cli_args = [] if argv is None else argv
    interactive_cli_overrides = resolve_interactive_cli_overrides(
        cli_args,
        default_config_path=config_path,
    )
    if cli_args and interactive_cli_overrides is None:
        return run_cli_fn(cli_args)

    try:
        effective_config_path = config_path
        if interactive_cli_overrides is not None:
            effective_config_path = interactive_cli_overrides.config_path

        # Try to discover a .slproj project; if found, use it as the config source.
        active_project: object = None
        project_config_override: ConfigDict | None = None

        # Only auto-discover when using the default config path (not an explicit --config).
        if effective_config_path == config_path:
            discovered_slproj = discover_project()
            if discovered_slproj is not None:
                try:
                    active_project = load_project(discovered_slproj)
                    project_config_override = active_project.to_default_merged_config_dict()
                    effective_config_path = discovered_slproj
                    emit_output_fn(f"Using project: {project_status(active_project)}")
                except (FileNotFoundError, ValueError) as exc:
                    emit_output_fn(f"Warning: Could not load project: {exc}")

        if project_config_override is not None:
            cfg = project_config_override
            default_used = False
        else:
            cfg, default_used = load_config_fn(effective_config_path)

        if interactive_cli_overrides is not None and interactive_cli_overrides.debug:
            cfg["debug"] = True
        apply_debug_fn(cfg)
        resolved_ui_mode = "textual"
        if resolve_interactive_ui_mode_fn is not None:
            resolved_ui_mode = resolve_interactive_ui_mode_fn(
                cfg,
                interactive_cli_overrides.ui_mode if interactive_cli_overrides is not None else None,
            )
        if default_used:
            emit_output_fn("Warning: Default config created. Open Setup before running analysis.")
            pause_fn()
        if set_interactive_ui_mode_fn is not None:
            set_interactive_ui_mode_fn(resolved_ui_mode)
        try:
            run_main_loop_kwargs: dict[str, Any] = {
                "summarize_targets_fn": summarize_targets_fn,
                "show_help_fn": show_help_fn,
                "save_config_fn": save_config_fn,
                "config_path": effective_config_path,
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
