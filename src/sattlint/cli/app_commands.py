# pyright: reportUnusedFunction=false
"""Command-line command implementations for the CLI layer.

Direct replacement for the old ``application.commands`` surface, relocated
from ``application/`` to ``cli/`` as part of Phase 6 (application-layer
refactor).  Each command binds the owning implementations
(:mod:`sattlint.cli.syntax_check`, :mod:`sattlint.app_cli_commands`,
:mod:`sattlint.cache`) directly, with no dependency on the legacy ``app``
module.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from .. import _config_display as config_display_module
from .. import cache as cache_module
from .. import config as config_module
from .. import console as console_module
from .._exit_codes import EXIT_SUCCESS, EXIT_USAGE_ERROR
from ..application import analyze as analyze_application
from ..application import checks as app_analysis_checks_module
from ..application import project as project_application
from ..cli_output import emit_text_or_json
from ..config_types import ConfigDict
from ..config_validation import validate_effective_config
from ..core.logging import apply_debug
from ..models.project_graph import ProjectGraph
from . import app_cli_commands, syntax_check
from . import entry as cli_entry
from .entry import CommandHandlers, RunSyntaxCheckCommandFn

LoadedProject = tuple[str, BasePicture, ProjectGraph]

syntax_check_command = syntax_check.run_syntax_check_command


def _build_command_handlers() -> CommandHandlers:
    return cast(
        CommandHandlers,
        {
            "syntax_check": cast(RunSyntaxCheckCommandFn, syntax_check_command),
            "validate_config": run_validate_config_command,
            "analyze": run_analyze_command,
            "cache_prune": run_cache_prune_command,
        },
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


def run_validate_config_command(
    cfg: ConfigDict,
    *,
    config_path: Path,
    default_used: bool,
    output_format: str = "text",
) -> int:
    validation = validate_effective_config(cfg)
    if output_format == "json":
        emit_text_or_json(
            text="",
            json_payload={
                "config_path": str(config_path),
                "default_used": default_used,
                **validation.to_dict(),
            },
            output_format="json",
            emit_text_fn=print,
        )
        return EXIT_SUCCESS if validation.passed else EXIT_USAGE_ERROR

    if default_used:
        console_module.print_output(f"Warning: default config loaded from {config_path}")
    for error in validation.errors:
        console_module.print_output(error.message)
    return EXIT_SUCCESS if validation.passed else EXIT_USAGE_ERROR


def run_analyze_command(
    cfg: ConfigDict,
    *,
    selected_keys: list[str] | None,
    selected_issue_kinds: frozenset[str] | None = None,
    use_cache: bool,
    output_format: str = "text",
) -> int:
    def _collect_result(
        local_cfg: ConfigDict,
        *,
        selected_keys: list[str] | None,
        selected_issue_kinds: frozenset[str] | None = None,
    ) -> Any:
        def _iter_nested_projects(nested_cfg: ConfigDict) -> Iterator[LoadedProject]:
            return project_application.iter_loaded_projects(nested_cfg, use_cache=use_cache)

        return app_analysis_checks_module.collect_run_checks_result(
            cast(ConfigDict, local_cfg | {"use_cache": use_cache}),
            selected_keys,
            selected_issue_kinds=selected_issue_kinds,
            iter_loaded_projects_fn=_iter_nested_projects,
            get_enabled_analyzers_fn=(
                analyze_application.get_selectable_analyzers
                if selected_keys
                else analyze_application.get_enabled_analyzers
            ),
            target_is_library_fn=project_application.target_is_library,
        )

    return app_cli_commands.run_analyze_command(
        cfg,
        selected_keys=selected_keys,
        selected_issue_kinds=selected_issue_kinds,
        use_cache=use_cache,
        output_format=output_format,
        collect_analyze_result_fn=_collect_result,
        exit_success=EXIT_SUCCESS,
    )


def run_cache_prune_command(*, cache_dir: str | None = None, output_format: str = "text") -> int:
    return app_cli_commands.run_cache_prune_command(
        cache_dir=cache_dir,
        output_format=output_format,
        prune_cache_dir_fn=cache_module.prune_cache_dir,
        get_cache_dir_fn=cache_module.get_cache_dir,
        exit_success=EXIT_SUCCESS,
        exit_usage_error=EXIT_USAGE_ERROR,
    )


def show_config(cfg: ConfigDict) -> None:
    config_display_module.show_config(cfg, emit_output_fn=console_module.print_output)
