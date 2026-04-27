#!/usr/bin/env python3
"""Base config, CLI, and console helpers for the SattLint app facade."""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
from typing import Any, ClassVar

from . import config as config_module
from . import engine as engine_module
from .__version__ import __version__

CONFIG_PATH = config_module.get_config_path()
DEFAULT_CONFIG = config_module.DEFAULT_CONFIG
EXIT_SUCCESS = 0
EXIT_USAGE_ERROR = 1

# Configure logging so normal runs stay quiet unless debug mode is enabled.
logging.basicConfig(format="%(message)s", level=logging.INFO)
logging.getLogger().setLevel(logging.INFO)

log = logging.getLogger("SattLint")


def load_config(path: Path):
    return config_module.load_config(path)


def save_config(path: Path, cfg: dict) -> None:
    config_module.save_config(path, cfg)
    print("Config saved")


def self_check(cfg: dict) -> bool:
    return config_module.self_check(cfg)


def target_exists(target: str, cfg: dict) -> bool:
    return config_module.target_exists(target, cfg)


def apply_debug(cfg: dict):
    level = logging.DEBUG if cfg.get("debug") else logging.INFO
    logging.getLogger().setLevel(level)
    log.setLevel(level)


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


def _format_syntax_error(result: engine_module.SyntaxValidationResult) -> str:
    location = ""
    if result.line is not None and result.column is not None:
        location = f":{result.line}:{result.column}"
    elif result.line is not None:
        location = f":{result.line}"

    detail = result.message or "Unknown error"
    return f"ERROR [{result.stage}] {result.file_path}{location}: {detail}"


def _format_syntax_warning(file_path: Path, message: str) -> str:
    return f"WARNING [validation] {file_path}: {message}"


def run_syntax_check_command(file_path: str) -> int:
    target_path = Path(file_path)
    if not target_path.exists() or not target_path.is_file():
        print(f"ERROR [io] {target_path}: File not found", file=sys.stderr)
        return EXIT_USAGE_ERROR

    result = engine_module.validate_single_file_syntax(target_path)
    if result.ok:
        for warning in result.warnings:
            print(_format_syntax_warning(result.file_path, warning), file=sys.stderr)
        print("OK")
        return EXIT_SUCCESS

    print(_format_syntax_error(result), file=sys.stderr)
    return EXIT_USAGE_ERROR


def run_cli(
    argv: list[str],
    *,
    config_path: Path,
    repo_audit_module=None,
    build_cli_parser_fn=None,
    run_syntax_check_command_fn=None,
    load_config_fn=None,
    apply_debug_fn=None,
    run_validate_config_command_fn=None,
    run_analyze_command_fn=None,
    run_docgen_command_fn=None,
    run_format_icf_command_fn=None,
    exit_success: int = EXIT_SUCCESS,
    exit_usage_error: int = EXIT_USAGE_ERROR,
) -> int:
    if build_cli_parser_fn is None:
        build_cli_parser_fn = build_cli_parser
    if run_syntax_check_command_fn is None:
        run_syntax_check_command_fn = run_syntax_check_command

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
        context = redirect_stdout(io.StringIO()) if quiet else nullcontext()
        with context:
            return run_syntax_check_command_fn(args.file)

    if args.command == "repo-audit":
        if repo_audit_module is None:
            raise RuntimeError("repo_audit_module is required for repo-audit CLI dispatch")
        try:
            idx = next(i for i, arg in enumerate(argv) if arg == "repo-audit")
            remaining = list(argv[idx + 1 :])
        except StopIteration:
            remaining = []
        return repo_audit_module.main(remaining) or exit_success

    if leftover:
        print(f"sattlint: error: unrecognized arguments: {' '.join(leftover)}", file=sys.stderr)
        return exit_usage_error

    if args.command in ("validate-config", "analyze", "docgen", "format-icf"):
        try:
            if load_config_fn is None or apply_debug_fn is None:
                raise RuntimeError("CLI config handlers are required for this command")
            cfg, default_used = load_config_fn(resolved_config_path)
            apply_debug_fn(cfg)
        except Exception as exc:
            print(f"ERROR [config] {exc}", file=sys.stderr)
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

        if args.command == "docgen":
            if run_docgen_command_fn is None:
                raise RuntimeError("docgen handler is required")
            return run_docgen_command_fn(cfg, use_cache=use_cache) or exit_success

        if run_format_icf_command_fn is None:
            raise RuntimeError("format-icf handler is required")
        return run_format_icf_command_fn(cfg, check=getattr(args, "check", False))

    parser.print_usage(sys.stderr)
    return exit_usage_error


def _configure_windows_console_api(kernel32, coord_type, buffer_info_type):
    import ctypes
    from ctypes import wintypes

    kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel32.GetStdHandle.restype = wintypes.HANDLE

    kernel32.GetConsoleScreenBufferInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(buffer_info_type),
    ]
    kernel32.GetConsoleScreenBufferInfo.restype = wintypes.BOOL

    kernel32.FillConsoleOutputCharacterW.argtypes = [
        wintypes.HANDLE,
        wintypes.WCHAR,
        wintypes.DWORD,
        coord_type,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.FillConsoleOutputCharacterW.restype = wintypes.BOOL

    kernel32.FillConsoleOutputAttribute.argtypes = [
        wintypes.HANDLE,
        wintypes.WORD,
        wintypes.DWORD,
        coord_type,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.FillConsoleOutputAttribute.restype = wintypes.BOOL

    kernel32.SetConsoleCursorPosition.argtypes = [wintypes.HANDLE, coord_type]
    kernel32.SetConsoleCursorPosition.restype = wintypes.BOOL


def _clear_windows_console() -> None:
    import ctypes
    from ctypes import wintypes

    class _Coord(ctypes.Structure):
        _fields_: ClassVar[Any] = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

    class _SmallRect(ctypes.Structure):
        _fields_: ClassVar[Any] = [
            ("Left", wintypes.SHORT),
            ("Top", wintypes.SHORT),
            ("Right", wintypes.SHORT),
            ("Bottom", wintypes.SHORT),
        ]

    class _ConsoleScreenBufferInfo(ctypes.Structure):
        _fields_: ClassVar[Any] = [
            ("dwSize", _Coord),
            ("dwCursorPosition", _Coord),
            ("wAttributes", wintypes.WORD),
            ("srWindow", _SmallRect),
            ("dwMaximumWindowSize", _Coord),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[reportAttributeAccessIssue]
    _configure_windows_console_api(kernel32, _Coord, _ConsoleScreenBufferInfo)

    std_output_handle = wintypes.DWORD(-11).value
    stdout_handle = kernel32.GetStdHandle(std_output_handle)
    invalid_handle = ctypes.c_void_p(-1).value
    if stdout_handle in (None, 0, invalid_handle):
        raise OSError("unable to access stdout console handle")

    buffer_info = _ConsoleScreenBufferInfo()
    if not kernel32.GetConsoleScreenBufferInfo(stdout_handle, ctypes.byref(buffer_info)):
        raise OSError(ctypes.get_last_error(), "GetConsoleScreenBufferInfo failed")  # type: ignore[reportAttributeAccessIssue]

    cell_count = int(buffer_info.dwSize.X) * int(buffer_info.dwSize.Y)
    written = wintypes.DWORD()
    origin = _Coord(0, 0)

    if not kernel32.FillConsoleOutputCharacterW(
        stdout_handle,
        " ",
        cell_count,
        origin,
        ctypes.byref(written),
    ):
        raise OSError(ctypes.get_last_error(), "FillConsoleOutputCharacterW failed")  # type: ignore[reportAttributeAccessIssue]
    if not kernel32.FillConsoleOutputAttribute(
        stdout_handle,
        buffer_info.wAttributes,
        cell_count,
        origin,
        ctypes.byref(written),
    ):
        raise OSError(ctypes.get_last_error(), "FillConsoleOutputAttribute failed")  # type: ignore[reportAttributeAccessIssue]
    if not kernel32.SetConsoleCursorPosition(stdout_handle, origin):
        raise OSError(ctypes.get_last_error(), "SetConsoleCursorPosition failed")  # type: ignore[reportAttributeAccessIssue]


def clear_screen(*, os_module=os, sys_module=sys, clear_windows_console=None):
    if clear_windows_console is None:
        clear_windows_console = _clear_windows_console

    sys_module.stdout.flush()
    if os_module.name == "nt":
        try:
            clear_windows_console()
            return
        except OSError:
            if os_module.system("cls") == 0:  # nosec B605 B607 - fixed built-in command used as Windows console fallback
                return

    sys_module.stdout.write("\033[2J\033[H")
    sys_module.stdout.flush()


def pause() -> None:
    input("\nPress Enter to continue...")


class QuitAppError(Exception):
    pass


def quit_app(*, clear_screen_fn=None) -> None:
    if clear_screen_fn is None:
        clear_screen_fn = clear_screen

    clear_screen_fn()
    raise QuitAppError()


def confirm(msg: str) -> bool:
    return input(f"{msg} [y/N]: ").strip().lower() in ("y", "yes")


def prompt(msg: str, default: str | None = None) -> str:
    if default is not None:
        return input(f"{msg} [{default}]: ").strip() or default
    return input(f"{msg}: ").strip()