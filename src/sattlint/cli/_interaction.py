# pyright: reportUnusedFunction=false
"""CLI-level console interaction defaults.

The interactive shell is Textual-only. This module holds the small amount of
interaction *state* the shell needs (current UI mode and the registered
Textual menu-interaction bridge); the terminal-driven ``print_menu`` /
``menu_interaction`` helpers were removed with the legacy terminal menu.
"""

from __future__ import annotations

from typing import Any

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
