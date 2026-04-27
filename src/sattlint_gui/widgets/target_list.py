from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..theme import resolve_theme


class TargetList(ttk.Frame):
    def __init__(self, parent, *, title: str) -> None:
        super().__init__(parent, style="Panel.TFrame", padding=12)
        theme = resolve_theme(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, text=title, style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self._list = tk.Listbox(
            self,
            relief=tk.FLAT,
            bg=theme.input_bg,
            fg=theme.text,
            selectbackground=theme.btn_active,
            selectforeground=theme.console_text,
        )
        self._list.grid(row=1, column=0, sticky="nsew")

    def set_targets(self, targets: list[str]) -> None:
        self._list.delete(0, tk.END)
        if not targets:
            self._list.insert(tk.END, "<no configured targets>")
            return
        for item in targets:
            self._list.insert(tk.END, item)


__all__ = ["TargetList"]
