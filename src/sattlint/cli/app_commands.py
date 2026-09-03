# pyright: reportUnusedFunction=false
"""Command-line command implementations for the CLI layer.

Direct replacement for the old ``application.commands`` surface, relocated
from ``application/`` to ``cli/`` as part of Phase 6 (application-layer
refactor).  Each command binds the owning implementations
(:mod:`sattlint.app_base`, :mod:`sattlint.app_cli_commands`,
:mod:`sattlint.app_support`, :mod:`sattlint.cache`) directly, with no
dependency on the legacy ``app`` module.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from .. import _app_analysis_checks as app_analysis_checks_module
from .. import _app_startup as startup_core
from .. import app_base
from .. import cache as cache_module
from ..application import analyze as analyze_application
from ..application import project as project_application
from ..config_types import ConfigDict
from . import app_cli_commands
from . import entry as cli_entry
from .entry import CommandHandlers, RunSyntaxCheckCommandFn


def _build_command_handlers() -> CommandHandlers:
    return cast(
        CommandHandlers,
        {
            "syntax_check": cast(RunSyntaxCheckCommandFn, app_base.run_syntax_check_command),
            "validate_config": run_validate_config_command,
            "analyze": run_analyze_command,
            "cache_prune": run_cache_prune_command,
        },
    )


def run_cli(argv: list[str]) -> int:
    return cli_entry.run_cli(
        argv,
        config_path=app_base.CONFIG_PATH,
        build_cli_parser_fn=app_base.build_cli_parser,
        load_config_fn=app_base.load_config,
        apply_debug_fn=app_base.apply_debug,
        command_handlers=_build_command_handlers(),
        exit_success=app_base.EXIT_SUCCESS,
        exit_usage_error=app_base.EXIT_USAGE_ERROR,
    )


def run_validate_config_command(
    cfg: ConfigDict,
    *,
    config_path: Path,
    default_used: bool,
    output_format: str = "text",
) -> int:
    from ..config_validation import validate_effective_config  # noqa: PLC0415

    return startup_core.run_validate_config_command(
        cfg,
        config_path=config_path,
        default_used=default_used,
        validate_config_fn=validate_effective_config,
        output_format=output_format,
        exit_success=app_base.EXIT_SUCCESS,
        exit_usage_error=app_base.EXIT_USAGE_ERROR,
    )


def run_analyze_command(
    cfg: ConfigDict,
    *,
    selected_keys: list[str] | None,
    selected_issue_kinds: frozenset[str] | None = None,
    use_cache: bool,
    output_format: str = "text",
) -> int:
    return startup_core.run_analyze_command(
        cfg,
        selected_keys=selected_keys,
        selected_issue_kinds=selected_issue_kinds,
        use_cache=use_cache,
        output_format=output_format,
        run_analyze_command_fn=app_cli_commands.run_analyze_command,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        collect_run_checks_result_fn=app_analysis_checks_module.collect_run_checks_result,
        get_selectable_analyzers_fn=analyze_application.get_selectable_analyzers,
        get_enabled_analyzers_fn=analyze_application.get_enabled_analyzers,
        target_is_library_fn=project_application.target_is_library,
        exit_success=app_base.EXIT_SUCCESS,
    )


def run_cache_prune_command(*, cache_dir: str | None = None, output_format: str = "text") -> int:
    return startup_core.run_cache_prune_command(
        cache_dir=cache_dir,
        output_format=output_format,
        run_cache_prune_command_fn=app_cli_commands.run_cache_prune_command,
        prune_cache_dir_fn=cache_module.prune_cache_dir,
        get_cache_dir_fn=cache_module.get_cache_dir,
        exit_success=app_base.EXIT_SUCCESS,
        exit_usage_error=app_base.EXIT_USAGE_ERROR,
    )


def show_config(cfg: ConfigDict) -> None:
    from .. import _config_display  # noqa: PLC0415
    from .._app_interactive_menus import show_config as _show_config  # noqa: PLC0415

    _show_config(
        cfg,
        show_config_fn=_config_display.show_config,
    )
