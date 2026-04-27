from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk

from ..theme import resolve_theme


class ConsoleView(ttk.Frame):
    def __init__(self, parent, *, title: str) -> None:
        super().__init__(parent, style="Content.TFrame")
        theme = resolve_theme(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, text=title, style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self._text = scrolledtext.ScrolledText(
            self,
            wrap=tk.WORD,
            relief=tk.FLAT,
            bg=theme.console_bg,
            fg=theme.console_text,
            insertbackground=theme.console_text,
        )
        self._text.grid(row=1, column=0, sticky="nsew")
        self._text.configure(state=tk.DISABLED)

    def set_text(self, text: str) -> None:
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", text)
        self._text.configure(state=tk.DISABLED)

    def append_text(self, text: str) -> None:
        self._text.configure(state=tk.NORMAL)
        self._text.insert(tk.END, text)
        self._text.see(tk.END)
        self._text.configure(state=tk.DISABLED)


__all__ = ["ConsoleView"]
