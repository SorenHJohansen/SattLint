from __future__ import annotations

import argparse
import io
import sys
from contextlib import nullcontext, redirect_stdout
from pathlib import Path

from ..__version__ import __version__
from ..console import print_output

EXIT_SUCCESS = 0
EXIT_USAGE_ERROR = 1


def build_cli_parser(*, version: str = __version__) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sattlint",
        description="Interactive SattLine analysis app with a non-interactive syntax-check command.",
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

    repo_audit_parser = subparsers.add_parser(
        "repo-audit",
        help="Run repository audit checks",
        description="Scan the repository for portability and hygiene issues.",
    )
    repo_audit_parser.add_argument(
        "extra",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to repo-audit",
    )

    return parser


def run_cli(
    argv: list[str],
    *,
    config_path: Path,
    build_cli_parser_fn=None,
    run_syntax_check_command_fn=None,
    load_config_fn=None,
    apply_debug_fn=None,
    run_validate_config_command_fn=None,
    run_analyze_command_fn=None,
    run_simulate_command_fn=None,
    run_docgen_command_fn=None,
    run_format_icf_command_fn=None,
    exit_success: int = EXIT_SUCCESS,
    exit_usage_error: int = EXIT_USAGE_ERROR,
) -> int:
    if build_cli_parser_fn is None:
        build_cli_parser_fn = build_cli_parser

    parser = build_cli_parser_fn()
    try:
        args, leftover = parser.parse_known_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else exit_usage_error
        return code

    resolved_config_path = Path(args.config) if args.config else config_path
    use_cache = not getattr(args, "no_cache", False)
    quiet = getattr(args, "quiet", False)

    if args.command == "syntax-check":
        if run_syntax_check_command_fn is None:
            raise RuntimeError("syntax-check handler is required")
        context = redirect_stdout(io.StringIO()) if quiet else nullcontext()
        with context:
            return run_syntax_check_command_fn(args.file)

    if args.command == "repo-audit":
        from ..devtools import repo_audit

        try:
            idx = next(i for i, arg in enumerate(argv) if arg == "repo-audit")
            remaining = list(argv[idx + 1 :])
        except StopIteration:
            remaining = []
        return repo_audit.main(remaining) or exit_success

    if leftover:
        print_output(f"sattlint: error: unrecognized arguments: {' '.join(leftover)}", file=sys.stderr)
        return exit_usage_error

    if args.command in ("validate-config", "analyze", "simulate", "docgen", "format-icf"):
        try:
            if load_config_fn is None or apply_debug_fn is None:
                raise RuntimeError("CLI config handlers are required for this command")
            cfg, default_used = load_config_fn(resolved_config_path)
            apply_debug_fn(cfg)
        except Exception as exc:
            print_output(f"ERROR [config] {exc}", file=sys.stderr)
            return exit_usage_error

        if args.command == "validate-config":
            if run_validate_config_command_fn is None:
                raise RuntimeError("validate-config handler is required")
            return (
                run_validate_config_command_fn(cfg, config_path=resolved_config_path, default_used=default_used)
                or exit_success
            )

        if args.command == "analyze":
            if run_analyze_command_fn is None:
                raise RuntimeError("analyze handler is required")
            selected_keys = getattr(args, "checks", None) or None
            return run_analyze_command_fn(cfg, selected_keys=selected_keys, use_cache=use_cache) or exit_success

        if args.command == "simulate":
            if run_simulate_command_fn is None:
                raise RuntimeError("simulate handler is required")
            return (
                run_simulate_command_fn(
                    cfg,
                    target_path=args.target_path,
                    module_name=args.module,
                    mode=args.mode,
                    max_scans=args.max_scans,
                    output_format=args.format,
                    output_path=args.output,
                    use_cache=use_cache,
                )
                or exit_success
            )

        if args.command == "docgen":
            if run_docgen_command_fn is None:
                raise RuntimeError("docgen handler is required")
            return run_docgen_command_fn(cfg, use_cache=use_cache) or exit_success

        if run_format_icf_command_fn is None:
            raise RuntimeError("format-icf handler is required")
        return run_format_icf_command_fn(cfg, check=getattr(args, "check", False))

    parser.print_usage(sys.stderr)
    return exit_usage_error
