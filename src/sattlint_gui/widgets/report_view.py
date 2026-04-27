from __future__ import annotations

import re
import tkinter as tk
from tkinter import scrolledtext, ttk

from ..theme import resolve_theme

# Matches lines like "=== Target: FooBar ===" produced by run_checks / variable analysis
_TARGET_HEADER_RE = re.compile(r"^=== .+ ===$")
# Matches issue-count summary lines: "  12 issues" or "0 issues"
_ISSUE_COUNT_RE = re.compile(r"^\s*\d+ issues?\b")


class ReportView(ttk.Frame):
    def __init__(self, parent, *, title: str) -> None:
        super().__init__(parent, style="Panel.TFrame", padding=12)
        self._theme = resolve_theme(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, text=title, style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self._text = scrolledtext.ScrolledText(
            self,
            wrap=tk.WORD,
            relief=tk.FLAT,
            bg=self._theme.input_bg,
            fg=self._theme.text,
            insertbackground=self._theme.text,
        )
        self._text.grid(row=1, column=0, sticky="nsew")
        self._text.configure(state=tk.DISABLED)
        self._configure_tags()

    def _configure_tags(self) -> None:
        self._text.tag_configure(
            "section_header",
            foreground=self._theme.accent,
            font=("Segoe UI", 10, "bold"),
        )
        self._text.tag_configure(
            "count_line",
            foreground=self._theme.btn_active,
            font=("Segoe UI", 9, "bold"),
        )
        self._text.tag_configure(
            "muted",
            foreground=self._theme.text,
        )

    def _insert_tagged(self, text: str) -> None:
        """Insert text with automatic tag detection for structured output."""
        for line in text.splitlines(keepends=True):
            stripped = line.rstrip("\n")
            if _TARGET_HEADER_RE.match(stripped):
                self._text.insert(tk.END, line, "section_header")
            elif _ISSUE_COUNT_RE.match(stripped):
                self._text.insert(tk.END, line, "count_line")
            else:
                self._text.insert(tk.END, line)

    def set_text(self, text: str) -> None:
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._insert_tagged(text)
        self._text.configure(state=tk.DISABLED)

    def append_text(self, text: str) -> None:
        self._text.configure(state=tk.NORMAL)
        if self._text.index("end-1c") != "1.0":
            self._text.insert(tk.END, "\n\n")
        self._insert_tagged(text)
        self._text.see(tk.END)
        self._text.configure(state=tk.DISABLED)


__all__ = ["ReportView"]
