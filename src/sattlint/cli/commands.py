# pyright: reportUnusedFunction=false
"""CLI command handlers for the terminal command surface.

Binds the terminal commands (``analyze``, ``cache-prune``) to their owning
implementations (:mod:`sattlint.cli._command_implementations`,
:mod:`sattlint.cache`) and drives :func:`run_cli`.  The menu-oriented analysis
workflows live in :mod:`sattlint.application.menu_commands`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from .. import cache as cache_module
from .. import config as config_module
from ..application import analyze as analyze_application
from ..application import checks as app_analysis_checks_module
from ..application import project as project_application
from ..config.types import ConfigDict
from ..core.logging import apply_debug
from ..models.project_graph import ProjectGraph
from . import _command_implementations
from . import entry as cli_entry
from ._exit_codes import EXIT_SUCCESS, EXIT_USAGE_ERROR
from .entry import CommandHandlers

LoadedProject = tuple[str, BasePicture, ProjectGraph]


def build_command_handlers(
    *,
    defaults: CommandHandlers | None = None,
    overrides: CommandHandlers | None = None,
) -> CommandHandlers:
    resolved: dict[str, object] = {}
    if defaults is not None:
        resolved.update(defaults)
    if overrides is not None:
        resolved.update(overrides)
    return cast(CommandHandlers, resolved)


def _build_command_handlers() -> CommandHandlers:
    return build_command_handlers(
        overrides=cast(
            CommandHandlers,
            {
                "analyze": run_analyze_command,
                "cache_prune": run_cache_prune_command,
            },
        )
    )


def run_cli(argv: list[str]) -> int:
    return cli_entry.run_cli(
        argv,
        config_path=config_module.get_config_path(),
        build_cli_parser_fn=cli_entry.build_cli_parser,
        load_config_fn=config_module.load_config,
        apply_debug_fn=apply_debug,
        command_handlers=_build_command_handlers(),
        exit_success=EXIT_SUCCESS,
        exit_usage_error=EXIT_USAGE_ERROR,
    )


def run_analyze_command(
    cfg: ConfigDict,
    *,
    selected_keys: list[str] | None,
    selected_issue_kinds: frozenset[str] | None = None,
    use_cache: bool,
    refresh_caches: bool = False,
    output_format: str = "text",
) -> int:
    if refresh_caches:
        project_application.refresh_analysis_caches(cfg)

    def _collect_result(
        local_cfg: ConfigDict,
        *,
        selected_keys: list[str] | None,
        selected_issue_kinds: frozenset[str] | None = None,
    ) -> Any:
        def _iter_nested_projects(nested_cfg: ConfigDict) -> Iterator[LoadedProject]:
            return project_application.iter_loaded_projects(nested_cfg, use_cache=use_cache)

        return app_analysis_checks_module.collect_run_checks_result(
            local_cfg,
            selected_keys,
            selected_issue_kinds=selected_issue_kinds,
            use_cache=use_cache,
            persist_run=True,
            iter_loaded_projects_fn=_iter_nested_projects,
            get_enabled_analyzers_fn=(
                analyze_application.get_selectable_analyzers
                if selected_keys
                else analyze_application.get_enabled_analyzers
            ),
            target_is_library_fn=project_application.target_is_library,
        )

    return _command_implementations.run_analyze_command(
        cfg,
        selected_keys=selected_keys,
        selected_issue_kinds=selected_issue_kinds,
        output_format=output_format,
        collect_analyze_result_fn=_collect_result,
        exit_success=EXIT_SUCCESS,
    )


def run_cache_prune_command(*, cache_dir: str | None = None, output_format: str = "text") -> int:
    return _command_implementations.run_cache_prune_command(
        cache_dir=cache_dir,
        output_format=output_format,
        prune_cache_dir_fn=cache_module.prune_cache_dir,
        get_cache_dir_fn=cache_module.get_cache_dir,
        exit_success=EXIT_SUCCESS,
        exit_usage_error=EXIT_USAGE_ERROR,
    )
