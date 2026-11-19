"""Interactive console I/O primitives for SattLint.

Plain ``input``-driven defaults for prompting, confirming, pausing, choosing a
menu option, and quitting the app, elevated from the old flat ``app_base``
module as part of the Phase 2 layered refactor.
"""

from __future__ import annotations

from collections.abc import Callable

from . import terminal as terminal_module


def pause() -> None:
    """Wait for the operator to acknowledge.

    A closed stdin has nobody left to press Enter, so the wait degrades to a
    no-op instead of raising from a shutdown path.
    """
    try:
        input("\nPress Enter to continue...")
    except EOFError:
        return


class QuitAppError(Exception):
    pass


def quit_app(*, clear_screen_fn: Callable[[], None] | None = None) -> None:
    if clear_screen_fn is None:
        clear_screen_fn = terminal_module.clear_screen

    clear_screen_fn()
    raise QuitAppError()


def confirm(msg: str) -> bool:
    return input(f"{msg} [y/N]: ").strip().lower() in ("y", "yes")


def prompt(msg: str, default: str | None = None) -> str:
    if default is not None:
        return input(f"{msg} [{default}]: ").strip() or default
    return input(f"{msg}: ").strip()
