"""Headless CLI parser and dispatch.

``sattlint`` with no arguments launches the Textual shell when stdin and stdout
are terminals; otherwise it prints the usage and exits 2. Every subcommand here
is non-interactive, writes machine-readable data to stdout, and never prompts.
The parser is intentionally small: project inspection, analysis, and querying
stored runs.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys
from collections.abc import Callable
from typing import NoReturn, Protocol, cast

from ..__version__ import __version__
from ..utils.terminal_text import sanitize_terminal_text
from . import commands
from ._output import CliError, emit_error
from ._project import drain_config_warnings

EXIT_SUCCESS = 0
EXIT_USAGE_ERROR = 2

_MACHINE_OUTPUT_FORMATS = frozenset({"json", "ndjson", "sarif"})

AppCommandFn = Callable[[argparse.Namespace], int | None]

_machine_logging_suppressed = False


def _suppress_last_resort_logging() -> None:
    """Keep machine-readable stderr free of log records.

    Python's logging last-resort handler writes WARNING and ERROR records to
    stderr when no handler is configured. Headless JSON and NDJSON commands
    need stderr to carry only their error envelope, so a no-op root handler is
    installed once for those formats.
    """
    global _machine_logging_suppressed
    if _machine_logging_suppressed:
        return
    logging.getLogger().addHandler(logging.NullHandler())
    _machine_logging_suppressed = True


class _SubParserAction(Protocol):
    def add_parser(self, name: str, /, *, help: str | None = None) -> argparse.ArgumentParser: ...


class _UsageError(CliError):
    """A usage failure raised by the parser before a namespace exists."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _UsageError(message, code="usage_error", exit_code=EXIT_USAGE_ERROR)


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


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid integer value: {value!r}") from None
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def _build_project_parser(subparsers: _SubParserAction) -> None:
    project_parser = subparsers.add_parser("project", help="Inspect a .slproj project.")
    project_sub = project_parser.add_subparsers(dest="project_command", required=True)
    show = project_sub.add_parser("show", help="Show the resolved project.")
    _add_project_arg(show)
    _add_output_args(show)
    targets = project_sub.add_parser("targets", help="List configured targets with their kind and resolved path.")
    _add_project_arg(targets)
    _add_output_args(targets)
    check = project_sub.add_parser("check", help="Validate the project schema, roots, and targets without analysis.")
    _add_project_arg(check)
    _add_output_args(check)
    init = project_sub.add_parser("init", help="Create a minimal version 2 project file.")
    init.add_argument(
        "path",
        nargs="?",
        default=None,
        metavar="PATH",
        help="Directory or .slproj path; default is the current directory.",
    )
    _add_output_args(init)


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
        help="Analyzer key to run; repeatable. Overrides the project's analyzers list.",
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
    parser.add_argument("--no-cache", action="store_true", help="Ignore stored analyzer reports for this run.")
    parser.add_argument(
        "--refresh-ast",
        action="store_true",
        help="Rebuild each target's parsed project graph instead of reusing the cached one.",
    )
    parser.add_argument("--no-save", action="store_true", help="Do not save the run to run history.")
    parser.add_argument(
        "--jobs",
        type=_non_negative_int,
        default=1,
        metavar="N",
        help=(
            "Run per-target analyzers in N forked worker processes; 1 runs them in order, "
            "0 picks a count from the CPU count."
        ),
    )
    parser.add_argument(
        "--fail-on",
        choices=("error", "warning", "any", "none"),
        default="any",
        help=("Exit 1 at or above this severity: error, warning, or any finding; none always exits 0."),
    )
    parser.add_argument(
        "--baseline",
        metavar="PATH",
        help=(
            "Compare filtered findings with a checked-in baseline and fail only on new or more severe "
            "findings at the --fail-on threshold."
        ),
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Emit machine-readable progress records on stderr while the run is in progress.",
    )
    _add_output_args(parser, formats=("json", "ndjson", "sarif", "text"))


def _build_review_parser(subparsers: _SubParserAction) -> None:
    parser = subparsers.add_parser(
        "review",
        help="Generate Change Review JSON and Markdown artifacts without the interactive UI.",
    )
    _add_project_arg(parser)
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        metavar="NAME",
        help="Review only this target; repeatable. Defaults to every configured target.",
    )
    parser.add_argument(
        "--output-dir",
        metavar="PATH",
        help="Directory for the review artifacts. Defaults to the configured Change Review directory.",
    )
    _add_output_args(parser)


def _build_findings_parser(subparsers: _SubParserAction) -> None:
    parser = subparsers.add_parser("findings", help="Query findings from a stored run.")
    _add_project_arg(parser)
    parser.add_argument(
        "--run",
        default="latest",
        metavar="ID",
        help="Run ID, unique prefix, or 'latest'. 'latest' resolves within the project.",
    )
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
    parser.add_argument(
        "--kind",
        action="append",
        default=[],
        metavar="KIND",
        help="Filter by finding kind or its documented label; repeatable. An unknown value exits 2.",
    )
    parser.add_argument(
        "--rule",
        action="append",
        default=[],
        metavar="RULE",
        help="Filter by rule ID, finding kind, or documented label; repeatable. An unknown value exits 2.",
    )
    parser.add_argument(
        "--group-by",
        choices=("none", "module", "analyzer", "target", "kind"),
        default="none",
        help="Also return grouped counts for the selected findings.",
    )
    parser.add_argument(
        "--limit", type=_non_negative_int, metavar="N", help="Return at most N findings after filtering."
    )
    _add_output_args(parser, formats=("json", "ndjson", "sarif", "text"))


def _build_show_parser(subparsers: _SubParserAction) -> None:
    parser = subparsers.add_parser("show", help="Show one finding by its stable ID.")
    parser.add_argument("finding_id", metavar="FINDING_ID")
    _add_project_arg(parser)
    parser.add_argument(
        "--run",
        default="latest",
        metavar="ID",
        help="Run ID, unique prefix, or 'latest'. 'latest' resolves within the project.",
    )
    _add_output_args(parser, formats=("json", "markdown", "text"))


def _build_baseline_parser(subparsers: _SubParserAction) -> None:
    parser = subparsers.add_parser(
        "baseline",
        help="Accept known findings in a checked-in baseline and compare a run with it.",
    )
    baseline_sub = parser.add_subparsers(dest="baseline_command", required=True)
    update = baseline_sub.add_parser(
        "update",
        help="Rewrite the baseline from a stored run, accepting its findings and pruning stale entries.",
    )
    _add_project_arg(update)
    update.add_argument(
        "--run",
        default="latest",
        metavar="ID",
        help="Run ID, unique prefix, or 'latest'. 'latest' resolves within the project.",
    )
    update.add_argument(
        "--path",
        metavar="PATH",
        help="Baseline file. Defaults to .sattlint-baseline.json next to the project file.",
    )
    _add_output_args(update)

    difference = baseline_sub.add_parser(
        "diff",
        help="Compare a stored run with the baseline without writing it.",
    )
    _add_project_arg(difference)
    difference.add_argument(
        "--run",
        default="latest",
        metavar="ID",
        help="Run ID, unique prefix, or 'latest'. 'latest' resolves within the project.",
    )
    difference.add_argument(
        "--path",
        metavar="PATH",
        help="Baseline file. Defaults to .sattlint-baseline.json next to the project file.",
    )
    _add_output_args(difference)


def _build_runs_parser(subparsers: _SubParserAction) -> None:
    parser = subparsers.add_parser("runs", help="Inspect stored run history.")
    runs_sub = parser.add_subparsers(dest="runs_command", required=True)

    listing = runs_sub.add_parser("list", help="List stored runs, newest first, with status and counts.")
    _add_project_arg(listing)
    listing.add_argument("--limit", type=_non_negative_int, metavar="N", help="Show at most N runs.")
    _add_output_args(listing)

    show = runs_sub.add_parser("show", help="Show one stored run, including analyzer and failure detail.")
    show.add_argument(
        "run_id",
        nargs="?",
        default="latest",
        metavar="RUN_ID",
        help="Run ID, unique prefix, or 'latest'; default 'latest'. 'latest' resolves within the project.",
    )
    _add_project_arg(show)
    _add_output_args(show)

    prune = runs_sub.add_parser("prune", help="Remove run records this build cannot read.")
    prune.add_argument(
        "--keep",
        type=_non_negative_int,
        metavar="N",
        help="Also delete readable runs older than the newest N. Without it, readable runs are never deleted.",
    )
    _add_output_args(prune)


def build_cli_parser(*, version: str = __version__) -> argparse.ArgumentParser:
    parser = _Parser(prog="sattlint", description="Headless SattLint automation surface.")
    parser.add_argument("--version", action="version", version=f"sattlint {version}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _build_project_parser(subparsers)
    _build_analyzers_parser(subparsers)
    _build_analyze_parser(subparsers)
    _build_review_parser(subparsers)
    _build_findings_parser(subparsers)
    _build_show_parser(subparsers)
    _build_baseline_parser(subparsers)
    _build_runs_parser(subparsers)
    return parser


def _handlers() -> dict[str, AppCommandFn]:
    return {
        "project": _dispatch_project,
        "analyzers": _dispatch_analyzers,
        "analyze": commands.command_analyze,
        "review": commands.command_review,
        "findings": commands.command_findings,
        "show": commands.command_show,
        "baseline": _dispatch_baseline,
        "runs": _dispatch_runs,
    }


def _dispatch_project(args: argparse.Namespace) -> int:
    if args.project_command == "targets":
        return commands.command_project_targets(args)
    if args.project_command == "check":
        return commands.command_project_check(args)
    if args.project_command == "init":
        return commands.command_project_init(args)
    return commands.command_project_show(args)


def _dispatch_analyzers(args: argparse.Namespace) -> int:
    return commands.command_analyzers_list(args)


def _dispatch_baseline(args: argparse.Namespace) -> int:
    if args.baseline_command == "update":
        return commands.command_baseline_update(args)
    return commands.command_baseline_diff(args)


def _dispatch_runs(args: argparse.Namespace) -> int:
    if args.runs_command == "list":
        return commands.command_runs_list(args)
    if args.runs_command == "show":
        return commands.command_runs_show(args)
    return commands.command_runs_prune(args)


def _format_from_args(args: argparse.Namespace) -> str:
    return str(getattr(args, "format", "text") or "text")


def _quiet_from_args(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "quiet", False))


def _requested_format(argv: list[str]) -> str:
    """Read ``--format`` before parsing fails and no namespace exists.

    argparse keeps the last occurrence of a repeated option, so the fallback
    must do the same or the pre-parse and post-parse error channels disagree.
    """
    requested = "text"
    for index, argument in enumerate(argv):
        if argument == "--format" and index + 1 < len(argv):
            requested = argv[index + 1]
        elif argument.startswith("--format="):
            requested = argument.split("=", 1)[1]
    return requested


_FILTER_ARGUMENTS: dict[str, tuple[str, ...]] = {
    "analyze": ("analyzer", "target", "module"),
    "review": ("target",),
    "findings": ("analyzer", "target", "module", "kind", "rule"),
}


def _validate_args(args: argparse.Namespace) -> None:
    """Reject filter values that would otherwise match nothing on purpose.

    An empty filter value is never a meaningful selection: the module matcher
    drops a blank pattern, which hides every finding, and a blank project path
    falls back to discovery. Both silently change what the command queries.
    """
    command = str(args.command)
    for attribute in _FILTER_ARGUMENTS.get(command, ()):
        values = cast(list[str], getattr(args, attribute))
        if any(not value.strip() for value in values):
            raise _UsageError(
                f"--{attribute} must not be empty.",
                code="usage_error",
                exit_code=EXIT_USAGE_ERROR,
            )
    if command == "findings" and bool(args.exact_module) and not cast(list[str], args.module):
        raise _UsageError(
            "--exact-module requires --module.",
            code="usage_error",
            exit_code=EXIT_USAGE_ERROR,
        )
    project = getattr(args, "project", None)
    if project is not None and not str(project).strip():
        raise _UsageError(
            "--project must not be empty.",
            code="usage_error",
            exit_code=EXIT_USAGE_ERROR,
        )
    for attribute in ("baseline", "path", "output_dir"):
        value = getattr(args, attribute, None)
        if value is not None and not str(value).strip():
            raise _UsageError(
                f"--{attribute} must not be empty.",
                code="usage_error",
                exit_code=EXIT_USAGE_ERROR,
            )
    if command == "baseline" and not str(getattr(args, "run", "")).strip():
        raise _UsageError(
            "--run must not be empty.",
            code="usage_error",
            exit_code=EXIT_USAGE_ERROR,
        )
    if command == "runs" and not str(getattr(args, "run_id", "latest")).strip():
        raise _UsageError(
            "RUN_ID must not be empty. Use 'latest', a run id, or a unique run-id prefix.",
            code="usage_error",
            exit_code=EXIT_USAGE_ERROR,
        )


def run_cli(argv: list[str]) -> int:
    parser = build_cli_parser()
    try:
        args = parser.parse_args(argv)
    except _UsageError as exc:
        emit_error(exc, output_format=_requested_format(argv))
        return exc.exit_code
    except SystemExit as exc:
        return int(exc.code or 0)

    if _format_from_args(args) in _MACHINE_OUTPUT_FORMATS:
        _suppress_last_resort_logging()

    try:
        _validate_args(args)
    except _UsageError as exc:
        emit_error(exc, output_format=_format_from_args(args))
        return exc.exit_code

    handler = _handlers().get(args.command)
    if handler is None:
        emit_error(
            CliError(f"Unknown command: {args.command}", code="usage_error", exit_code=EXIT_USAGE_ERROR),
            output_format=_format_from_args(args),
        )
        return EXIT_USAGE_ERROR
    try:
        exit_code = int(handler(args) or EXIT_SUCCESS)
    except CliError as exc:
        warnings = drain_config_warnings()
        if warnings and not _quiet_from_args(args):
            if _format_from_args(args) in _MACHINE_OUTPUT_FORMATS:
                exc.details.setdefault("warnings", list(warnings))
            else:
                for warning in warnings:
                    sys.stderr.write(f"{sanitize_terminal_text(warning)}\n")
        emit_error(exc, output_format=_format_from_args(args))
        return exc.exit_code
    except BrokenPipeError:
        # A consumer such as `head` closed the pipe. That is not an internal
        # error; exit like the tools this output is piped into.
        drain_config_warnings()
        with contextlib.suppress(OSError):
            sys.stdout.close()
        return 141
    except KeyboardInterrupt:
        drain_config_warnings()
        sys.stderr.write("sattlint: interrupted\n")
        return 130
    except Exception as exc:  # noqa: BLE001 - CLI boundary reports a stable error envelope
        error = CliError(
            f"Unexpected error: {exc}",
            code="internal_error",
            exit_code=3,
            details={"type": type(exc).__name__},
        )
        drain_config_warnings()
        emit_error(error, output_format=_format_from_args(args))
        return 3
    warnings = drain_config_warnings()
    if warnings and not _quiet_from_args(args) and _format_from_args(args) not in _MACHINE_OUTPUT_FORMATS:
        for warning in warnings:
            sys.stderr.write(f"{sanitize_terminal_text(warning)}\n")
    return exit_code


__all__ = [
    "build_cli_parser",
    "run_cli",
]
