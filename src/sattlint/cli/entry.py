from __future__ import annotations

import argparse
import importlib
import io
import sys
import traceback
from collections.abc import Callable
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
from typing import Any, Protocol, TypedDict, cast

from .. import cli_output
from ..__version__ import __version__
from .._exit_codes import EXIT_SUCCESS, EXIT_USAGE_ERROR
from ..cli_output import add_output_format_argument
from ..config_types import ConfigDict
from ..console import print_output

_CONFIG_LOAD_EXCEPTIONS = (OSError, ValueError)

BuildCliParserFn = Callable[[], argparse.ArgumentParser]
LoadConfigFn = Callable[[Path], tuple[ConfigDict, bool]]
ApplyDebugFn = Callable[[ConfigDict], None]
AppCommandFn = Callable[..., int | None]
RunParsedArgsCommandFn = Callable[[argparse.Namespace], int | None]


class RunSyntaxCheckCommandFn(Protocol):
    def __call__(self, file: str, *, output_format: str = "text") -> int: ...


class CommandHandlers(TypedDict, total=False):
    syntax_check: RunSyntaxCheckCommandFn
    validate_config: AppCommandFn
    analyze: AppCommandFn
    simulate: AppCommandFn
    docgen: AppCommandFn
    cache_prune: AppCommandFn
    telemetry_summary: AppCommandFn
    format_icf: AppCommandFn
    repo_audit: RunParsedArgsCommandFn
    source_diff: RunParsedArgsCommandFn
    trace: RunParsedArgsCommandFn


def _load_devtools_module(module_name: str) -> Any:
    return importlib.import_module(f"sattlint.devtools.{module_name}")


def _build_devtools_parent_parser(module_name: str, *, prog: str) -> argparse.ArgumentParser:
    cli_module = _load_devtools_module(module_name)
    return cast(argparse.ArgumentParser, cli_module.build_cli_parser(prog=prog, add_help=False))


def _load_trace_module() -> Any:
    return importlib.import_module("sattlint.tracing")


class _ParsedCliArgs(Protocol):
    config: str | None
    cache_dir: str | None
    no_cache: bool
    quiet: bool
    debug: bool
    ui: str | None
    command: str | None
    file: str
    checks: list[str]
    list_checks: bool
    issue_kinds: list[str]
    list_issue_kinds: bool
    target_path: str
    module: str
    mode: str
    max_scans: int
    format: str
    output: str | None
    output_dir: str | None
    output_path: str | None
    check: bool


def _exit_code(result: int | None, *, fallback: int) -> int:
    return fallback if result is None else result


def _collect_analyzer_keys() -> tuple[str, ...]:
    from ..analyzers.registry import get_selectable_analyzers  # noqa: PLC0415

    return tuple(spec.key for spec in get_selectable_analyzers())


def _issue_kind_values() -> tuple[str, ...]:
    from ..models import IssueKind  # noqa: PLC0415

    return tuple(issue_kind.value for issue_kind in IssueKind)


def _collect_issue_kind_values() -> tuple[str, ...]:
    return _issue_kind_values()


def _emit_value_list(*, values: tuple[str, ...], payload_key: str, output_format: str) -> None:
    if output_format == "text" and not values:
        return
    cli_output.emit_text_or_json(
        text="\n".join(values),
        json_payload={payload_key: list(values)},
        output_format="json" if output_format == "json" else "text",
        emit_text_fn=print_output,
    )


def build_cli_parser(*, version: str = __version__) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sattlint",
        description="Interactive SattLine analysis app with non-interactive syntax-check, analysis, documentation, simulation, source-diff, and repo-audit commands.",
    )
    parser.add_argument("--version", action="version", version=f"sattlint {version}")
    parser.add_argument("--config", default=None, metavar="PATH", help="Path to a SattLint config file")
    parser.add_argument("--no-cache", action="store_true", dest="no_cache", help="Skip the AST cache")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout output")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument(
        "--ui",
        default=None,
        choices=["textual"],
        help="Interactive UI mode to use when no subcommand is selected (Textual only)",
    )
    subparsers = parser.add_subparsers(dest="command")

    syntax_parser = subparsers.add_parser(
        "syntax-check",
        help="Validate a single SattLine file with the parser and transformer",
        description="Validate one SattLine source file and report a compact syntax or validation error.",
    )
    syntax_parser.add_argument("file", help="Path to the SattLine source file")
    add_output_format_argument(syntax_parser)

    validate_config_parser = subparsers.add_parser(
        "validate-config",
        help="Validate the SattLint configuration file",
        description="Validate and report any issues with the current configuration.",
    )
    add_output_format_argument(validate_config_parser)

    cache_prune_parser = subparsers.add_parser(
        "cache-prune",
        help="Remove stale persistent cache artifacts",
        description="Remove stale or unusable persistent cache artifacts from the SattLint cache directory.",
    )
    cache_prune_parser.add_argument(
        "--cache-dir",
        default=None,
        help="Optional cache directory to prune instead of the default SattLint cache location",
    )

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Run non-interactive analysis checks",
        description="Run selected analysis checks against configured targets.",
    )
    analyze_parser.add_argument(
        "--check",
        action="append",
        dest="checks",
        default=[],
        metavar="KEY",
        help="Analysis check key to run (repeatable)",
    )
    analyze_parser.add_argument(
        "--list-checks",
        action="store_true",
        help="List available analysis check keys and exit",
    )
    analyze_parser.add_argument(
        "--issue-kind",
        action="append",
        dest="issue_kinds",
        default=[],
        metavar="KIND",
        choices=_issue_kind_values(),
        help="Filter variable analysis to this issue kind (repeatable; use --list-issue-kinds to see choices)",
    )
    analyze_parser.add_argument(
        "--list-issue-kinds",
        action="store_true",
        help="List available issue kind values for --issue-kind and exit",
    )
    add_output_format_argument(
        analyze_parser,
        help_text="Output format for analyze list commands",
    )

    simulate_parser = subparsers.add_parser(
        "simulate",
        help="Run bounded SFC scan-cycle simulation",
        description="Simulate one SFC-bearing target and report steady state, cycles, or scan-budget exhaustion.",
    )
    simulate_parser.add_argument("target_path", help="Path to the SattLine entry file to load")
    simulate_parser.add_argument("--module", required=True, help="Module or instance path to simulate")
    simulate_parser.add_argument(
        "--mode",
        default="steady-state",
        choices=["steady-state"],
        help="Simulation mode to run",
    )
    simulate_parser.add_argument(
        "--max-scans",
        type=int,
        default=25,
        dest="max_scans",
        help="Maximum number of scans to execute before stopping",
    )
    simulate_parser.add_argument(
        "--format",
        default="text",
        choices=["text", "json"],
        help="Output format",
    )
    simulate_parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write the simulation output",
    )

    docgen_parser = subparsers.add_parser(
        "docgen",
        help="Generate DOCX documentation",
        description="Generate FS-style DOCX documentation for configured targets.",
    )
    docgen_parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write generated DOCX files into",
    )
    docgen_parser.add_argument(
        "--output-path",
        default=None,
        help="Explicit DOCX file path for single-target generation",
    )

    format_icf_parser = subparsers.add_parser(
        "format-icf",
        help="Normalize blank-line spacing in configured ICF files",
        description=(
            "Rewrite configured .icf files so Unit, Journal, Operation, and Group headers use "
            "consistent spacing without changing nonblank content."
        ),
    )
    format_icf_parser.add_argument(
        "--check",
        action="store_true",
        help="Report whether configured .icf files would change without rewriting them.",
    )

    telemetry_summary_parser = subparsers.add_parser(
        "telemetry-summary",
        help="Summarize local app telemetry bottlenecks",
        description="Read local app telemetry and summarize slowest operations, stages, analyzers, and nested phases.",
    )
    telemetry_summary_parser.add_argument(
        "--format",
        default="text",
        choices=["text", "json"],
        help="Output format",
    )
    telemetry_summary_parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write the telemetry summary",
    )

    source_diff_parent = _build_devtools_parent_parser("source_diff_report", prog="sattlint source-diff")
    subparsers.add_parser(
        "source-diff",
        parents=[source_diff_parent],
        help="Build a review-friendly report for draft .s versus official .x source pairs",
        description=source_diff_parent.description,
    )

    repo_audit_parent = _build_devtools_parent_parser("repo_audit_cli", prog="sattlint repo-audit")
    subparsers.add_parser(
        "repo-audit",
        parents=[repo_audit_parent],
        help="Run repository audit checks",
        description=repo_audit_parent.description,
    )

    trace_module = _load_trace_module()
    trace_parent = cast(argparse.ArgumentParser, trace_module.build_cli_parser(prog="sattlint trace", add_help=False))
    subparsers.add_parser(
        "trace",
        parents=[trace_parent],
        help="Trace parser and analyzer execution for one source file",
        description=trace_parent.description,
    )

    return parser


def run_cli(  # noqa: PLR0915
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
    if build_cli_parser_fn is None:
        build_cli_parser_fn = build_cli_parser

    parser = build_cli_parser_fn()
    try:
        parsed_namespace, leftover = parser.parse_known_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else exit_usage_error
        return code

    args = cast(_ParsedCliArgs, parsed_namespace)

    resolved_config_path = Path(args.config) if args.config else config_path
    use_cache = not args.no_cache
    quiet = args.quiet
    command = args.command

    if leftover:
        print_output(f"sattlint: error: unrecognized arguments: {' '.join(leftover)}", file=sys.stderr)
        return exit_usage_error

    if command == "syntax-check":
        syntax_check_handler = None if command_handlers is None else command_handlers.get("syntax_check")
        if syntax_check_handler is None:
            raise RuntimeError("syntax-check handler is required")
        context = redirect_stdout(io.StringIO()) if quiet else nullcontext()
        with context:
            if getattr(args, "format", "text") == "json":
                return syntax_check_handler(args.file, output_format="json")
            return syntax_check_handler(args.file)

    if command == "repo-audit":
        repo_audit_handler = None if command_handlers is None else command_handlers.get("repo_audit")
        if repo_audit_handler is None:
            raise RuntimeError("repo-audit handler is required")
        context = redirect_stdout(io.StringIO()) if quiet else nullcontext()
        try:
            with context:
                return _exit_code(
                    repo_audit_handler(parsed_namespace),
                    fallback=exit_success,
                )
        except SystemExit as exc:
            return exc.code if isinstance(exc.code, int) else exit_usage_error

    if command == "source-diff":
        source_diff_handler = None if command_handlers is None else command_handlers.get("source_diff")
        if source_diff_handler is None:
            raise RuntimeError("source-diff handler is required")
        context = redirect_stdout(io.StringIO()) if quiet else nullcontext()
        try:
            with context:
                return _exit_code(
                    source_diff_handler(parsed_namespace),
                    fallback=exit_success,
                )
        except SystemExit as exc:
            return exc.code if isinstance(exc.code, int) else exit_usage_error

    if command == "trace":
        trace_handler = None if command_handlers is None else command_handlers.get("trace")
        if trace_handler is None:
            raise RuntimeError("trace handler is required")
        context = redirect_stdout(io.StringIO()) if quiet else nullcontext()
        try:
            with context:
                return _exit_code(
                    trace_handler(parsed_namespace),
                    fallback=exit_success,
                )
        except SystemExit as exc:
            return exc.code if isinstance(exc.code, int) else exit_usage_error

    if command == "analyze" and getattr(args, "list_checks", False):
        context = redirect_stdout(io.StringIO()) if quiet else nullcontext()
        with context:
            _emit_value_list(
                values=_collect_analyzer_keys(),
                payload_key="checks",
                output_format=cli_output.resolve_output_format(args),
            )
        return exit_success

    if command == "analyze" and getattr(args, "list_issue_kinds", False):
        context = redirect_stdout(io.StringIO()) if quiet else nullcontext()
        with context:
            _emit_value_list(
                values=_collect_issue_kind_values(),
                payload_key="issue_kinds",
                output_format=cli_output.resolve_output_format(args),
            )
        return exit_success

    if command == "telemetry-summary":
        telemetry_summary_handler = None if command_handlers is None else command_handlers.get("telemetry_summary")
        if telemetry_summary_handler is None:
            raise RuntimeError("telemetry-summary handler is required")
        return _exit_code(
            telemetry_summary_handler(
                {},
                config_path=resolved_config_path,
                output_format=getattr(args, "format", "text"),
                output_path=getattr(args, "output", None),
            ),
            fallback=exit_success,
        )

    if command == "cache-prune":
        cache_prune_handler = None if command_handlers is None else command_handlers.get("cache_prune")
        if cache_prune_handler is None:
            raise RuntimeError("cache-prune handler is required")
        return _exit_code(
            cache_prune_handler(cache_dir=getattr(args, "cache_dir", None)),
            fallback=exit_success,
        )

    if command in ("validate-config", "analyze", "simulate", "docgen", "format-icf"):
        debug_requested = bool(getattr(args, "debug", False))
        if load_config_fn is None or apply_debug_fn is None:
            raise RuntimeError("CLI config handlers are required for this command")
        try:
            cfg, default_used = load_config_fn(resolved_config_path)
        except _CONFIG_LOAD_EXCEPTIONS as exc:
            print_output(f"ERROR [config] {exc}", file=sys.stderr)
            if debug_requested:
                traceback.print_exc(file=sys.stderr)
            return exit_usage_error
        debug_requested = debug_requested or bool(cfg.get("debug", False))
        if getattr(args, "debug", False):
            cfg["debug"] = True
        apply_debug_fn(cfg)

        if command == "validate-config":
            validate_config_handler = None if command_handlers is None else command_handlers.get("validate_config")
            if validate_config_handler is None:
                raise RuntimeError("validate-config handler is required")
            validate_config_kwargs: dict[str, Any] = {
                "config_path": resolved_config_path,
                "default_used": default_used,
            }
            if getattr(args, "format", "text") == "json":
                validate_config_kwargs["output_format"] = "json"
            return _exit_code(validate_config_handler(cfg, **validate_config_kwargs), fallback=exit_success)

        if command == "analyze":
            analyze_handler = None if command_handlers is None else command_handlers.get("analyze")
            if analyze_handler is None:
                raise RuntimeError("analyze handler is required")
            selected_keys = args.checks or None
            selected_issue_kinds = frozenset(getattr(args, "issue_kinds", [])) or None
            return _exit_code(
                analyze_handler(
                    cfg,
                    selected_keys=selected_keys,
                    selected_issue_kinds=selected_issue_kinds,
                    use_cache=use_cache,
                    output_format=cli_output.resolve_output_format(args),
                ),
                fallback=exit_success,
            )

        if command == "simulate":
            simulate_handler = None if command_handlers is None else command_handlers.get("simulate")
            if simulate_handler is None:
                raise RuntimeError("simulate handler is required")
            return _exit_code(
                simulate_handler(
                    cfg,
                    target_path=args.target_path,
                    module_name=args.module,
                    mode=args.mode,
                    max_scans=args.max_scans,
                    output_format=args.format,
                    output_path=args.output,
                    use_cache=use_cache,
                ),
                fallback=exit_success,
            )

        if command == "docgen":
            docgen_handler = None if command_handlers is None else command_handlers.get("docgen")
            if docgen_handler is None:
                raise RuntimeError("docgen handler is required")
            return _exit_code(
                docgen_handler(
                    cfg,
                    use_cache=use_cache,
                    output_dir=getattr(args, "output_dir", None),
                    output_path=getattr(args, "output_path", None),
                ),
                fallback=exit_success,
            )

        format_icf_handler = None if command_handlers is None else command_handlers.get("format_icf")
        if format_icf_handler is None:
            raise RuntimeError("format-icf handler is required")
        return _exit_code(format_icf_handler(cfg, check=args.check), fallback=exit_success)

    parser.print_usage(sys.stderr)
    return exit_usage_error
