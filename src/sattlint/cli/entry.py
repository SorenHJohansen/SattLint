"""Headless CLI parser and dispatch.

``sattlint`` with no arguments still launches the Textual shell. Every subcommand
here is non-interactive, writes machine-readable data to stdout, and never
prompts. The parser is intentionally small: project inspection, analysis, and
querying stored runs.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn, Protocol

from ..__version__ import __version__
from ..config.types import ConfigDict
from . import commands
from ._output import CliError, emit_error

EXIT_SUCCESS = 0
EXIT_FINDINGS = 1
EXIT_FAILURE = 2
EXIT_USAGE_ERROR = 2

BuildCliParserFn = Callable[..., argparse.ArgumentParser]
LoadConfigFn = Callable[[Path], tuple[ConfigDict, bool]]
ApplyDebugFn = Callable[[ConfigDict], None]
AppCommandFn = Callable[..., int | None]


class CommandHandlers(dict[str, AppCommandFn]):
    """Mapping of command names to handlers (used by tests and embedding)."""


class _SubParserAction(Protocol):
    def add_parser(self, name: str, /, *, help: str | None = None) -> argparse.ArgumentParser: ...


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise CliError(message, code="usage_error", exit_code=EXIT_USAGE_ERROR)


def _add_output_args(
    parser: argparse.ArgumentParser,
    *,
    formats: tuple[str, ...] = ("json", "text"),
) -> None:
    parser.add_argument(
        "--format",
        choices=formats,
        default="text",
        help="Output format. Use json for machine-readable data.",
    )
    parser.add_argument("--output", metavar="PATH", help="Write output to PATH instead of stdout.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress and diagnostic output on stderr.")


def _add_project_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", metavar="PATH", help="Path to a .slproj file or a directory containing one.")


def _build_project_parser(subparsers: _SubParserAction) -> None:
    project_parser = subparsers.add_parser("project", help="Inspect a .slproj project.")
    project_sub = project_parser.add_subparsers(dest="project_command", required=True)
    show = project_sub.add_parser("show", help="Show the resolved project.")
    _add_project_arg(show)
    _add_output_args(show)


def _build_analyzers_parser(subparsers: _SubParserAction) -> None:
    analyzers_parser = subparsers.add_parser("analyzers", help="List analyzer metadata.")
    analyzers_sub = analyzers_parser.add_subparsers(dest="analyzers_command", required=True)
    listing = analyzers_sub.add_parser("list", help="List analyzers, keys, categories, and rule IDs.")
    _add_output_args(listing)


def _build_analyze_parser(subparsers: _SubParserAction) -> None:
    parser = subparsers.add_parser("analyze", help="Run analyzers headlessly.")
    _add_project_arg(parser)
    parser.add_argument(
        "--analyzer",
        action="append",
        default=[],
        metavar="KEY",
        help="Analyzer key to run; repeatable. Defaults to all.",
    )
    parser.add_argument(
        "--target", action="append", default=[], metavar="NAME", help="Analyze only this target; repeatable."
    )
    parser.add_argument(
        "--module",
        action="append",
        default=[],
        metavar="PREFIX",
        help="Only report findings at or below this module path; repeatable.",
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable the analysis cache for this run.")
    parser.add_argument("--no-save", action="store_true", help="Do not save the run to run history.")
    parser.add_argument(
        "--fail-on",
        choices=("any", "none"),
        default="any",
        help="Exit 1 when findings are reported (any) or always exit 0 (none).",
    )
    _add_output_args(parser, formats=("json", "ndjson", "text"))


def _build_findings_parser(subparsers: _SubParserAction) -> None:
    parser = subparsers.add_parser("findings", help="Query findings from a stored run.")
    parser.add_argument("--run", default="latest", metavar="ID", help="Run ID, unique prefix, or 'latest'.")
    parser.add_argument(
        "--analyzer", action="append", default=[], metavar="KEY", help="Filter by analyzer key; repeatable."
    )
    parser.add_argument("--target", action="append", default=[], metavar="NAME", help="Filter by target name.")
    parser.add_argument(
        "--module",
        action="append",
        default=[],
        metavar="PREFIX",
        help="Filter by module path prefix, e.g. Root.A (matches descendants).",
    )
    parser.add_argument("--exact-module", action="store_true", help="Require an exact module path match.")
    parser.add_argument("--kind", action="append", default=[], metavar="KIND", help="Filter by finding kind.")
    parser.add_argument("--rule", action="append", default=[], metavar="RULE", help="Filter by rule ID.")
    parser.add_argument(
        "--group-by",
        choices=("none", "module", "analyzer", "kind"),
        default="none",
        help="Also return grouped counts for the selected findings.",
    )
    parser.add_argument("--limit", type=int, metavar="N", help="Return at most N findings after filtering.")
    _add_output_args(parser, formats=("json", "ndjson", "text"))


def _build_show_parser(subparsers: _SubParserAction) -> None:
    parser = subparsers.add_parser("show", help="Show one finding by its stable ID.")
    parser.add_argument("finding_id", metavar="FINDING_ID")
    parser.add_argument("--run", default="latest", metavar="ID", help="Run ID, unique prefix, or 'latest'.")
    _add_output_args(parser, formats=("json", "markdown", "text"))


def build_cli_parser(*, version: str = __version__) -> argparse.ArgumentParser:
    parser = _Parser(prog="sattlint", description="Headless SattLint automation surface.")
    parser.add_argument("--version", action="version", version=f"sattlint {version}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _build_project_parser(subparsers)
    _build_analyzers_parser(subparsers)
    _build_analyze_parser(subparsers)
    _build_findings_parser(subparsers)
    _build_show_parser(subparsers)
    return parser


def _handlers() -> dict[str, AppCommandFn]:
    return {
        "project": _dispatch_project,
        "analyzers": _dispatch_analyzers,
        "analyze": commands.command_analyze,
        "findings": commands.command_findings,
        "show": commands.command_show,
    }


def _dispatch_project(args: argparse.Namespace) -> int:
    return commands.command_project_show(args)


def _dispatch_analyzers(args: argparse.Namespace) -> int:
    if args.analyzers_command == "list":
        return commands.command_analyzers_list(args)
    raise CliError("Unknown analyzers command.", code="usage_error", exit_code=EXIT_USAGE_ERROR)


def _format_from_args(args: argparse.Namespace) -> str:
    return str(getattr(args, "format", "text") or "text")


def _requested_format(argv: list[str]) -> str:
    for index, argument in enumerate(argv):
        if argument == "--format" and index + 1 < len(argv):
            return argv[index + 1]
        if argument.startswith("--format="):
            return argument.split("=", 1)[1]
    return "text"


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
    del config_path, load_config_fn, apply_debug_fn
    builder = build_cli_parser_fn or build_cli_parser
    parser = builder()
    try:
        args = parser.parse_args(argv)
    except CliError as exc:
        exc.exit_code = exit_usage_error
        emit_error(exc, output_format=_requested_format(argv))
        return exit_usage_error
    except SystemExit as exc:
        return int(exc.code or 0)

    handlers = _handlers() if command_handlers is None else command_handlers
    handler = handlers.get(args.command)
    if handler is None:
        emit_error(
            CliError(f"Unknown command: {args.command}", code="usage_error", exit_code=exit_usage_error),
            output_format=_format_from_args(args),
        )
        return exit_usage_error
    try:
        return int(handler(args) or exit_success)
    except CliError as exc:
        emit_error(exc, output_format=_format_from_args(args))
        return exc.exit_code
    except KeyboardInterrupt:
        sys.stderr.write("sattlint: interrupted\n")
        return 130
    except Exception as exc:  # noqa: BLE001 - CLI boundary reports a stable error envelope
        error = CliError(
            f"Unexpected error: {exc}",
            code="internal_error",
            exit_code=3,
            details={"type": type(exc).__name__},
        )
        emit_error(error, output_format=_format_from_args(args))
        return 3


__all__ = [
    "CommandHandlers",
    "build_cli_parser",
    "run_cli",
]
