# pyright: reportUnusedFunction=false
"""CLI-level console interaction bridge for the Textual shell.

The interactive shell is Textual-only. This module holds the registered
Textual menu-interaction bridge, which the shell installs while it is running
so the CLI helpers can route prompts through the active app.
"""

from __future__ import annotations

from typing import Any

_textual_menu_interaction: Any | None = None


def set_textual_menu_interaction(interaction: Any | None) -> None:
    global _textual_menu_interaction
    _textual_menu_interaction = interaction


def clear_textual_menu_interaction() -> None:
    global _textual_menu_interaction
    _textual_menu_interaction = None


def textual_menu_interaction() -> Any | None:
    return _textual_menu_interaction
