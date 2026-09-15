from __future__ import annotations

import argparse
import io
import os
import sys
import traceback
from collections.abc import Callable
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
from typing import Protocol, TypedDict, cast

from ..__version__ import __version__
from ..config.types import ConfigDict
from ..console import print_output
from ..project import (
    discover_project,
    project_status,
)
from ..project import (
    load_project as _load_project,
)
from . import cli_output
from ._exit_codes import EXIT_SUCCESS, EXIT_USAGE_ERROR
from .cli_output import add_output_format_argument

_CONFIG_LOAD_EXCEPTIONS = (OSError, ValueError)

BuildCliParserFn = Callable[[], argparse.ArgumentParser]
LoadConfigFn = Callable[[Path], tuple[ConfigDict, bool]]
ApplyDebugFn = Callable[[ConfigDict], None]
AppCommandFn = Callable[..., int | None]


class CommandHandlers(TypedDict, total=False):
    analyze: AppCommandFn
    cache_prune: AppCommandFn


class _ParsedCliArgs(Protocol):
    config: str | None
    project: str | None
    cache_dir: str | None
    no_cache: bool
    quiet: bool
    debug: bool
    ui: str | None
    command: str | None
    file: str
    name: str
    program_dir: str
    abb_lib_dir: str
    icf_dir: str
    other_lib_dirs: list[str]
    checks: list[str]
    list_checks: bool
    mode: str
    format: str
    output: str | None
    profile: bool


def _exit_code(result: int | None, *, fallback: int) -> int:
    return fallback if result is None else result


def _collect_analyzer_keys() -> tuple[str, ...]:
    from ..analyzers.catalog import get_selectable_analyzers  # noqa: PLC0415

    return tuple(spec.key for spec in get_selectable_analyzers())


def _emit_value_list(*, values: tuple[str, ...], payload_key: str, output_format: str) -> None:
    if output_format == "text" and not values:
        return
    cli_output.emit_text_or_json(
        text="\n".join(values),
        json_payload={payload_key: list(values)},
        output_format="json" if output_format == "json" else "text",
        emit_text_fn=print_output,
    )


def _is_version_request(argv: list[str]) -> bool:
    return "--version" in argv


def build_cli_parser(*, version: str = __version__) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sattlint",
        description="Interactive SattLine analysis app with non-interactive analysis commands.",
    )
    parser.add_argument("--version", action="version", version=f"sattlint {version}")
    parser.add_argument("--config", default=None, metavar="PATH", help="Path to a SattLint config file")
    parser.add_argument(
        "--project",
        default=None,
        metavar="PATH",
        help="Path to a .slproj project file (default: auto-discover from CWD)",
    )
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
    add_output_format_argument(cache_prune_parser)

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Run non-interactive analysis checks",
        description="Run explicitly selected analysis checks against configured targets.",
    )
    analyze_parser.add_argument(
        "--check",
        action="append",
        dest="checks",
        default=[],
        metavar="KEY",
        help="Analysis check key to run (repeatable; required unless listing checks or issue kinds)",
    )
    analyze_parser.add_argument(
        "--list-checks",
        action="store_true",
        help="List available analysis check keys and exit",
    )
    add_output_format_argument(
        analyze_parser,
        help_text="Output format for analyze list commands",
    )
    analyze_parser.add_argument(
        "--profile",
        action="store_true",
        help="Record run diagnostics for this invocation (JSONL profile log under the cache dir)",
    )
    analyze_parser.add_argument(
        "--refresh-caches",
        action="store_true",
        dest="refresh_caches",
        help="Force a full rebuild of the AST and report caches for this run",
    )

    return parser


def _resolve_config_and_project(
    args: _ParsedCliArgs,
    *,
    default_config_path: Path,
) -> tuple[Path | None, Path]:
    """Resolve the effective project path and config path from CLI args.

    Returns ``(project_path, config_path)``. When ``--project`` is given or
    a ``.slproj`` is auto-discovered, *project_path* is set and *config_path*
    falls back to the default. When ``--config`` is given explicitly,
    *project_path* is ``None``.
    """
    explicit_config = getattr(args, "config", None)
    explicit_project = getattr(args, "project", None)

    if explicit_config:
        return None, Path(explicit_config)

    if explicit_project:
        return Path(explicit_project).resolve(), default_config_path

    discovered = discover_project()
    if discovered is not None:
        return discovered, default_config_path

    return None, default_config_path


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

    if _is_version_request(argv):
        print_output(f"sattlint {__version__}")
        return exit_success

    parser = build_cli_parser_fn()
    try:
        parsed_namespace, leftover = parser.parse_known_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else exit_usage_error
        return code

    args = cast(_ParsedCliArgs, parsed_namespace)

    use_cache = not args.no_cache
    quiet = args.quiet
    command = args.command

    if leftover:
        print_output(f"sattlint: error: unrecognized arguments: {' '.join(leftover)}", file=sys.stderr)
        return exit_usage_error

    # --- resolve project / config source ---
    project_path, resolved_config_path = _resolve_config_and_project(args, default_config_path=config_path)

    active_project: object = None  # SattLineProject | None
    project_config: ConfigDict | None = None

    if project_path is not None:
        try:
            active_project = _load_project(project_path)
            project_config = active_project.to_default_merged_config_dict()
            if not args.quiet:
                print_output(f"Using project: {project_status(active_project)}")
        except (FileNotFoundError, ValueError) as exc:
            print_output(f"ERROR [project] {exc}", file=sys.stderr)
            return exit_usage_error

    if command == "analyze" and getattr(args, "list_checks", False):
        context = redirect_stdout(io.StringIO()) if quiet else nullcontext()
        with context:
            _emit_value_list(
                values=_collect_analyzer_keys(),
                payload_key="checks",
                output_format=cli_output.resolve_output_format(args),
            )
        return exit_success

    if command == "analyze" and not getattr(args, "checks", []):
        print_output(
            "sattlint analyze: error: at least one --check KEY is required; use --list-checks to see available analyzers",
            file=sys.stderr,
        )
        return exit_usage_error

    if command == "cache-prune":
        cache_prune_handler = None if command_handlers is None else command_handlers.get("cache_prune")
        if cache_prune_handler is None:
            raise RuntimeError("cache-prune handler is required")
        return _exit_code(
            cache_prune_handler(
                cache_dir=getattr(args, "cache_dir", None),
                output_format=cli_output.resolve_output_format(args),
            ),
            fallback=exit_success,
        )

    if command == "analyze":
        context = redirect_stdout(io.StringIO()) if quiet else nullcontext()
        with context:
            debug_requested = bool(getattr(args, "debug", False))

            if project_config is not None:
                cfg = project_config
            else:
                if load_config_fn is None or apply_debug_fn is None:
                    raise RuntimeError("CLI config handlers are required for this command")
                try:
                    cfg, _default_used = load_config_fn(resolved_config_path)
                except _CONFIG_LOAD_EXCEPTIONS as exc:
                    print_output(f"ERROR [config] {exc}", file=sys.stderr)
                    if debug_requested:
                        traceback.print_exc(file=sys.stderr)
                    return exit_usage_error
            debug_requested = debug_requested or bool(cfg.get("debug", False))
            if getattr(args, "debug", False):
                cfg["debug"] = True
            if apply_debug_fn is not None:
                apply_debug_fn(cfg)

            analyze_handler = None if command_handlers is None else command_handlers.get("analyze")
            if analyze_handler is None:
                raise RuntimeError("analyze handler is required")
            if getattr(args, "profile", False):
                os.environ.setdefault("SATTLINT_PROFILE", "1")
            selected_keys = args.checks
            return _exit_code(
                analyze_handler(
                    cfg,
                    selected_keys=selected_keys,
                    use_cache=use_cache,
                    refresh_caches=bool(getattr(args, "refresh_caches", False)),
                    output_format=cli_output.resolve_output_format(args),
                ),
                fallback=exit_success,
            )

    parser.print_usage(sys.stderr)
    return exit_usage_error
