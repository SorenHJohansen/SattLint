"""Minimal CLI entry — no-args TUI launch only.

All CLI subcommands and flags have been removed. ``run_cli`` returns a usage
error for any supplied arguments.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from ..__version__ import __version__
from ..config.types import ConfigDict
from ..console import print_output

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_USAGE_ERROR = 2

BuildCliParserFn = Callable[[], object]
LoadConfigFn = Callable[[Path], tuple[ConfigDict, bool]]
ApplyDebugFn = Callable[[ConfigDict], None]
AppCommandFn = Callable[..., int | None]


class CommandHandlers(dict):  # type: ignore[type-arg]
    """Stub kept for startup.main type signature compatibility."""


def build_cli_parser(*, version: str = __version__) -> object:
    """No-op parser — no CLI subcommands or flags are supported."""
    return None


def run_cli(
    argv: list[str],
    *,
    config_path: Path,
    build_cli_parser_fn: BuildCliParserFn | None = None,
    load_config_fn: LoadConfigFn | None = None,
    apply_debug_fn: ApplyDebugFn | None = None,
    command_handlers: CommandHandlers | None = None,
    exit_success: int = EXIT_SUCCESS,
    exit_usage_error: int = EXIT_USAGE_ERROR,
) -> int:
    del build_cli_parser_fn, load_config_fn, apply_debug_fn, command_handlers
    if argv:
        print_output(f"sattlint: unrecognized arguments: {' '.join(argv)}", file=sys.stderr)
        return exit_usage_error
    return exit_success
