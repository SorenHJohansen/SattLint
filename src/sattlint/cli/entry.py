from __future__ import annotations

import argparse
import io
import sys
from collections.abc import Callable
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
from typing import Any, Protocol, cast

from ..__version__ import __version__
from ..console import print_output

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_USAGE_ERROR = 2

ConfigDict = dict[str, Any]
BuildCliParserFn = Callable[[], argparse.ArgumentParser]
RunSyntaxCheckCommandFn = Callable[[str], int]
LoadConfigFn = Callable[[Path], tuple[ConfigDict, bool]]
ApplyDebugFn = Callable[[ConfigDict], None]
AppCommandFn = Callable[..., int | None]


class _ParsedCliArgs(Protocol):
    config: str | None
    no_cache: bool
    quiet: bool
    command: str | None
    file: str
    checks: list[str]
    list_checks: bool
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


def _list_analyzer_keys() -> None:
    from ..analyzers.registry import get_default_analyzers

    for spec in get_default_analyzers():
        print_output(spec.key)


def build_cli_parser(*, version: str = __version__) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sattlint",
        description="Interactive SattLine analysis app with non-interactive syntax-check, analysis, documentation, simulation, source-diff, and repo-audit commands.",
    )
    parser.add_argument("--version", action="version", version=f"sattlint {version}")
    parser.add_argument("--config", default=None, metavar="PATH", help="Path to a SattLint config file")
    parser.add_argument("--no-cache", action="store_true", dest="no_cache", help="Skip the AST cache")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout output")
    subparsers = parser.add_subparsers(dest="command")

    syntax_parser = subparsers.add_parser(
        "syntax-check",
        help="Validate a single SattLine file with the parser and transformer",
        description="Validate one SattLine source file and report a compact syntax or validation error.",
    )
    syntax_parser.add_argument("file", help="Path to the SattLine source file")

    subparsers.add_parser(
        "validate-config",
        help="Validate the SattLint configuration file",
        description="Validate and report any issues with the current configuration.",
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

    subparsers.add_parser(
        "docgen",
        help="Generate DOCX documentation",
        description="Generate FS-style DOCX documentation for configured targets.",
    ).add_argument(
        "--output-dir",
        default=None,
        help="Directory to write generated DOCX files into",
    )
    subparsers.choices["docgen"].add_argument(
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

    subparsers.add_parser(
        "source-diff",
        help="Build a review-friendly report for draft .s versus official .x source pairs",
        description=(
            "Forward to the source diff reporting tool that compares one explicit draft and official "
            "source pair or discovers same-basename .s/.x pairs under a workspace root."
        ),
    )

    from ..devtools import repo_audit_cli

    repo_audit_parent = repo_audit_cli.build_cli_parser(prog="sattlint repo-audit", add_help=False)
    subparsers.add_parser(
        "repo-audit",
        parents=[repo_audit_parent],
        help="Run repository audit checks",
        description=repo_audit_parent.description,
    )

    return parser


def run_cli(
    argv: list[str],
    *,
    config_path: Path,
    build_cli_parser_fn: BuildCliParserFn | None = None,
    run_syntax_check_command_fn: RunSyntaxCheckCommandFn | None = None,
    load_config_fn: LoadConfigFn | None = None,
    apply_debug_fn: ApplyDebugFn | None = None,
    run_validate_config_command_fn: AppCommandFn | None = None,
    run_analyze_command_fn: AppCommandFn | None = None,
    run_simulate_command_fn: AppCommandFn | None = None,
    run_docgen_command_fn: AppCommandFn | None = None,
    run_telemetry_summary_command_fn: AppCommandFn | None = None,
    run_format_icf_command_fn: AppCommandFn | None = None,
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

    if command == "syntax-check":
        if run_syntax_check_command_fn is None:
            raise RuntimeError("syntax-check handler is required")
        context = redirect_stdout(io.StringIO()) if quiet else nullcontext()
        with context:
            return run_syntax_check_command_fn(args.file)

    if command == "repo-audit":
        from ..devtools import repo_audit

        try:
            idx = next(i for i, arg in enumerate(argv) if arg == "repo-audit")
            remaining = list(argv[idx + 1 :])
        except StopIteration:
            remaining = []
        context = redirect_stdout(io.StringIO()) if quiet else nullcontext()
        with context:
            return repo_audit.main(remaining) or exit_success

    if command == "source-diff":
        from ..devtools import source_diff_report

        try:
            idx = next(i for i, arg in enumerate(argv) if arg == "source-diff")
            remaining = list(argv[idx + 1 :])
        except StopIteration:
            remaining = []
        context = redirect_stdout(io.StringIO()) if quiet else nullcontext()
        with context:
            return source_diff_report.main(remaining) or exit_success

    if leftover:
        print_output(f"sattlint: error: unrecognized arguments: {' '.join(leftover)}", file=sys.stderr)
        return exit_usage_error

    if command == "analyze" and getattr(args, "list_checks", False):
        context = redirect_stdout(io.StringIO()) if quiet else nullcontext()
        with context:
            _list_analyzer_keys()
        return exit_success

    if command in ("validate-config", "analyze", "simulate", "docgen", "telemetry-summary", "format-icf"):
        try:
            if load_config_fn is None or apply_debug_fn is None:
                raise RuntimeError("CLI config handlers are required for this command")
            cfg, default_used = load_config_fn(resolved_config_path)
            apply_debug_fn(cfg)
        except Exception as exc:
            print_output(f"ERROR [config] {exc}", file=sys.stderr)
            return exit_usage_error

        if command == "validate-config":
            if run_validate_config_command_fn is None:
                raise RuntimeError("validate-config handler is required")
            return _exit_code(
                run_validate_config_command_fn(cfg, config_path=resolved_config_path, default_used=default_used),
                fallback=exit_success,
            )

        if command == "analyze":
            if run_analyze_command_fn is None:
                raise RuntimeError("analyze handler is required")
            selected_keys = args.checks or None
            return _exit_code(
                run_analyze_command_fn(cfg, selected_keys=selected_keys, use_cache=use_cache),
                fallback=exit_success,
            )

        if command == "simulate":
            if run_simulate_command_fn is None:
                raise RuntimeError("simulate handler is required")
            return _exit_code(
                run_simulate_command_fn(
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
            if run_docgen_command_fn is None:
                raise RuntimeError("docgen handler is required")
            return _exit_code(
                run_docgen_command_fn(
                    cfg,
                    use_cache=use_cache,
                    output_dir=getattr(args, "output_dir", None),
                    output_path=getattr(args, "output_path", None),
                ),
                fallback=exit_success,
            )

        if command == "telemetry-summary":
            if run_telemetry_summary_command_fn is None:
                raise RuntimeError("telemetry-summary handler is required")
            return _exit_code(
                run_telemetry_summary_command_fn(
                    cfg,
                    config_path=resolved_config_path,
                    output_format=args.format,
                    output_path=args.output,
                ),
                fallback=exit_success,
            )

        if run_format_icf_command_fn is None:
            raise RuntimeError("format-icf handler is required")
        return _exit_code(run_format_icf_command_fn(cfg, check=args.check), fallback=exit_success)

    parser.print_usage(sys.stderr)
    return exit_usage_error
