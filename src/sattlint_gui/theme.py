from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass

ALLOWED_THEME_COLORS = frozenset(
    {
        "#b9d9df",
        "#fbfbee",
        "#58787e",
        "#00ad57",
        "#c2c2c2",
        "#001ba3",
        "#cc7700",
        "#7e5858",
        "#001aa0",
        "#ffff00",
    }
)


@dataclass(frozen=True, slots=True)
class SattLintTheme:
    bg_main: str = "#fbfbee"
    bg_panel: str = "#b9d9df"
    btn_bg: str = "#c2c2c2"
    btn_active: str = "#00ad57"
    accent: str = "#001ba3"
    input_bg: str = "#fbfbee"
    text: str = "#58787e"
    console_bg: str = "#58787e"
    console_text: str = "#fbfbee"
    sidebar_width: int = 200


DEFAULT_THEME = SattLintTheme()


def resolve_theme(widget: tk.Misc | None) -> SattLintTheme:
    if widget is None:
        return DEFAULT_THEME
    root = widget.winfo_toplevel()
    theme = getattr(root, "theme", None)
    if isinstance(theme, SattLintTheme):
        return theme
    return DEFAULT_THEME


__all__ = ["ALLOWED_THEME_COLORS", "DEFAULT_THEME", "SattLintTheme", "resolve_theme"]
