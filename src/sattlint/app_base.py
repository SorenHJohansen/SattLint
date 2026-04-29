#!/usr/bin/env python3
"""Base config, CLI, and console helpers for the SattLint app facade."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, ClassVar

from . import config as config_module
from . import console as console_module
from . import engine as engine_module
from .cli import entry as cli_entry_module

CONFIG_PATH = config_module.get_config_path()
DEFAULT_CONFIG = config_module.DEFAULT_CONFIG
EXIT_SUCCESS = 0
EXIT_USAGE_ERROR = 1

# Configure logging so normal runs stay quiet unless debug mode is enabled.
logging.basicConfig(format="%(message)s", level=logging.INFO)
logging.getLogger().setLevel(logging.INFO)

log = logging.getLogger("SattLint")
print = console_module.print_output  # type: ignore[assignment]


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


def build_cli_parser(*, version: str | None = None) -> argparse.ArgumentParser:
    if version is None:
        return cli_entry_module.build_cli_parser()
    return cli_entry_module.build_cli_parser(version=version)


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

    return cli_entry_module.run_cli(
        argv,
        config_path=config_path,
        build_cli_parser_fn=build_cli_parser_fn,
        run_syntax_check_command_fn=run_syntax_check_command_fn,
        load_config_fn=load_config_fn,
        apply_debug_fn=apply_debug_fn,
        run_validate_config_command_fn=run_validate_config_command_fn,
        run_analyze_command_fn=run_analyze_command_fn,
        run_docgen_command_fn=run_docgen_command_fn,
        run_format_icf_command_fn=run_format_icf_command_fn,
        exit_success=exit_success,
        exit_usage_error=exit_usage_error,
    )


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


def configure_windows_console_api(kernel32, coord_type, buffer_info_type):
    return _configure_windows_console_api(kernel32, coord_type, buffer_info_type)


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


def clear_windows_console() -> None:
    _clear_windows_console()


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
