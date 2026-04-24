from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk


class ReportView(ttk.Frame):
    def __init__(self, parent, *, title: str) -> None:
        super().__init__(parent, style="Panel.TFrame", padding=12)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, text=title, style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self._text = scrolledtext.ScrolledText(self, wrap=tk.WORD, relief=tk.FLAT, bg="#fbf8f2", fg="#1f2722")
        self._text.grid(row=1, column=0, sticky="nsew")
        self._text.configure(state=tk.DISABLED)

    def set_text(self, text: str) -> None:
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", text)
        self._text.configure(state=tk.DISABLED)

    def append_text(self, text: str) -> None:
        self._text.configure(state=tk.NORMAL)
        if self._text.index("end-1c") != "1.0":
            self._text.insert(tk.END, "\n\n")
        self._text.insert(tk.END, text)
        self._text.see(tk.END)
        self._text.configure(state=tk.DISABLED)


__all__ = ["ReportView"]
