# pyright: reportAttributeAccessIssue=false
"""Console and terminal primitives for SattLint.

CLI-independent helpers for clearing and inspecting the terminal, elevated
from the old flat ``app_base`` module as part of the Phase 2 layered refactor.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any, ClassVar, cast

ClearScreenFn = Callable[[], None]


def _configure_windows_console_api(kernel32: Any, coord_type: Any, buffer_info_type: Any) -> None:
    import ctypes  # noqa: PLC0415
    from ctypes import wintypes  # noqa: PLC0415

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


def configure_windows_console_api(kernel32: Any, coord_type: Any, buffer_info_type: Any) -> None:
    return _configure_windows_console_api(kernel32, coord_type, buffer_info_type)


def _clear_windows_console() -> None:
    import ctypes  # noqa: PLC0415
    from ctypes import wintypes  # noqa: PLC0415

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

    kernel32 = cast(object, ctypes.WinDLL("kernel32", use_last_error=True))  # type: ignore[reportAttributeAccessIssue]
    kernel32_api: Any = kernel32
    _configure_windows_console_api(kernel32_api, _Coord, _ConsoleScreenBufferInfo)
    get_std_handle = cast(Callable[[object], Any], kernel32_api.GetStdHandle)
    get_console_screen_buffer_info = cast(Callable[[object, object], bool], kernel32_api.GetConsoleScreenBufferInfo)
    fill_console_output_character = cast(
        Callable[[object, object, object, object, object], bool],
        kernel32_api.FillConsoleOutputCharacterW,
    )
    fill_console_output_attribute = cast(
        Callable[[object, object, object, object, object], bool],
        kernel32_api.FillConsoleOutputAttribute,
    )
    set_console_cursor_position = cast(Callable[[object, object], bool], kernel32_api.SetConsoleCursorPosition)

    std_output_handle = wintypes.DWORD(-11).value
    stdout_handle = get_std_handle(std_output_handle)
    invalid_handle = ctypes.c_void_p(-1).value
    if stdout_handle in (None, 0, invalid_handle):
        raise OSError("unable to access stdout console handle")

    buffer_info = _ConsoleScreenBufferInfo()
    if not get_console_screen_buffer_info(stdout_handle, ctypes.byref(buffer_info)):
        raise OSError(ctypes.get_last_error(), "GetConsoleScreenBufferInfo failed")  # type: ignore[reportAttributeAccessIssue]

    cell_count = int(buffer_info.dwSize.X) * int(buffer_info.dwSize.Y)
    written = wintypes.DWORD()
    origin = _Coord(0, 0)

    if not fill_console_output_character(
        stdout_handle,
        " ",
        cell_count,
        origin,
        ctypes.byref(written),
    ):
        raise OSError(ctypes.get_last_error(), "FillConsoleOutputCharacterW failed")  # type: ignore[reportAttributeAccessIssue]
    if not fill_console_output_attribute(
        stdout_handle,
        buffer_info.wAttributes,
        cell_count,
        origin,
        ctypes.byref(written),
    ):
        raise OSError(ctypes.get_last_error(), "FillConsoleOutputAttribute failed")  # type: ignore[reportAttributeAccessIssue]
    if not set_console_cursor_position(stdout_handle, origin):
        raise OSError(ctypes.get_last_error(), "SetConsoleCursorPosition failed")  # type: ignore[reportAttributeAccessIssue]


def clear_windows_console() -> None:
    _clear_windows_console()


def flush_stdout() -> None:
    flush = getattr(sys.stdout, "flush", None)
    if callable(flush):
        flush()


def clear_screen(
    *,
    os_module: ModuleType = os,
    sys_module: ModuleType = sys,
    clear_windows_console: ClearScreenFn | None = None,
) -> None:
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
