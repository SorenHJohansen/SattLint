from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import ttk

from ..theme import SattLintTheme


def apply_theme(root: tk.Misc, theme: SattLintTheme) -> ttk.Style:
    style = ttk.Style(root)
    with contextlib.suppress(tk.TclError):
        style.theme_use("clam")

    style.configure(".", background=theme.bg_main, foreground=theme.text)
    style.configure("TFrame", background=theme.bg_main)
    style.configure("Content.TFrame", background=theme.bg_main)
    style.configure("Panel.TFrame", background=theme.bg_panel)
    style.configure("Sidebar.TFrame", background=theme.bg_panel)
    style.configure("TLabel", background=theme.bg_main, foreground=theme.text)
    style.configure("Title.TLabel", background=theme.bg_main, foreground=theme.accent, font=("Segoe UI", 20, "bold"))
    style.configure("Section.TLabel", background=theme.bg_panel, foreground=theme.accent, font=("Segoe UI", 11, "bold"))
    style.configure("SidebarTitle.TLabel", background=theme.bg_panel, foreground=theme.accent, font=("Segoe UI", 12, "bold"))
    style.configure("Muted.TLabel", background=theme.bg_main, foreground=theme.text)
    style.configure(
        "TButton",
        background=theme.btn_bg,
        foreground=theme.text,
        borderwidth=0,
        focusthickness=0,
        padding=(10, 8),
    )
    style.map("TButton", background=[("active", theme.btn_active)])
    style.configure("Accent.TButton", background=theme.accent, foreground=theme.console_text)
    style.map("Accent.TButton", background=[("active", theme.btn_active)])
    style.configure("Nav.TButton", background=theme.btn_bg, anchor="w")
    style.map("Nav.TButton", background=[("active", theme.btn_active)])
    return style


__all__ = ["apply_theme"]
