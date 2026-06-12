from __future__ import annotations

import os
import sys
from collections.abc import Callable, Sequence
from types import ModuleType
from typing import Any

ClearScreenFn = Callable[[], None]


def clear_screen(
    *,
    os_module: ModuleType = os,
    sys_module: ModuleType = sys,
    clear_windows_console: ClearScreenFn,
) -> None:
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


def quit_app(*, clear_screen_fn: ClearScreenFn) -> None:
    clear_screen_fn()
    raise QuitAppError()


def confirm(msg: str) -> bool:
    return input(f"{msg} [y/N]: ").strip().lower() in ("y", "yes")


def prompt(msg: str, default: str | None = None) -> str:
    if default is not None:
        return input(f"{msg} [{default}]: ").strip() or default
    return input(f"{msg}: ").strip()


def choose_menu_option(
    title: str,
    options: Sequence[Any],
    *,
    print_menu_fn: Callable[..., None],
    intro: str | None = None,
    note: str | None = None,
    input_fn: Callable[[str], str] | None = None,
) -> str:
    if input_fn is None:
        input_fn = input

    print_menu_fn(title, options, intro=intro, note=note)
    return input_fn("> ").strip().lower()
