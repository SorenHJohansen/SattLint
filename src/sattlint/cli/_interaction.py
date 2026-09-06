# pyright: reportUnusedFunction=false
"""CLI-level console interaction defaults.

Interactive actions and menus receive a :class:`MenuInteraction` as an
injectable prompt/confirm/pause/choose-menu abstraction.  This module
holds the default interaction built from the standard console helpers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..core.interaction import choose_menu_option, confirm, pause, prompt
from . import menu as menu_module
from .interaction import build_menu_interaction


def print_menu(
    title: str,
    options: Sequence[Any],
    *,
    intro: str | None = None,
    note: str | None = None,
) -> None:
    menu_module.print_menu(title, options, print_fn=print, intro=intro, note=note)


def _choose_menu_option(
    title: str,
    options: Sequence[Any],
    *,
    intro: str | None = None,
    note: str | None = None,
) -> str:
    return choose_menu_option(
        title,
        options,
        print_menu_fn=print_menu,
        intro=intro,
        note=note,
    )


def menu_interaction() -> Any:
    return build_menu_interaction(
        print_menu_fn=print_menu,
        choose_menu_option_fn=_choose_menu_option,
        prompt_fn=prompt,
        confirm_fn=confirm,
        pause_fn=pause,
    )


_interactive_ui_mode: str = "textual"
_textual_menu_interaction: Any | None = None


def interactive_ui_mode() -> str:
    return _interactive_ui_mode


def set_interactive_ui_mode(ui_mode: str | None) -> None:
    global _interactive_ui_mode
    del ui_mode
    _interactive_ui_mode = "textual"


def reset_interactive_ui_mode() -> None:
    set_interactive_ui_mode("textual")
    clear_textual_menu_interaction()


def get_interactive_ui_mode() -> str:
    return interactive_ui_mode()


def set_textual_menu_interaction(interaction: Any | None) -> None:
    global _textual_menu_interaction
    _textual_menu_interaction = interaction


def clear_textual_menu_interaction() -> None:
    global _textual_menu_interaction
    _textual_menu_interaction = None


def textual_menu_interaction() -> Any | None:
    return _textual_menu_interaction


def has_textual_menu_interaction() -> bool:
    return interactive_ui_mode() == "textual" and _textual_menu_interaction is not None
