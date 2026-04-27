from __future__ import annotations

import datetime
import tkinter as tk
from tkinter import ttk

from ..theme import resolve_theme
from ..widgets.report_view import ReportView


class ResultsFrame(ttk.Frame):
    """Two-pane results view: history list on the left, detail on the right."""

    def __init__(self, parent) -> None:
        super().__init__(parent, style="Content.TFrame")
        theme = resolve_theme(parent)
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Left: history list ───────────────────────────────────────────────
        history_host = ttk.Frame(self, style="Panel.TFrame", padding=12)
        history_host.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        history_host.columnconfigure(0, weight=1)
        history_host.rowconfigure(1, weight=1)

        ttk.Label(history_host, text="History", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))

        list_host = ttk.Frame(history_host, style="Panel.TFrame")
        list_host.grid(row=1, column=0, sticky="nsew")
        list_host.columnconfigure(0, weight=1)
        list_host.rowconfigure(0, weight=1)

        self._history_box = tk.Listbox(
            list_host,
            relief=tk.FLAT,
            bg=theme.input_bg,
            fg=theme.text,
            selectbackground=theme.btn_active,
            selectforeground=theme.console_text,
            width=22,
            exportselection=False,
        )
        scrollbar = ttk.Scrollbar(list_host, orient=tk.VERTICAL, command=self._history_box.yview)
        self._history_box.configure(yscrollcommand=scrollbar.set)
        self._history_box.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._history_box.bind("<<ListboxSelect>>", self._on_history_select)

        ttk.Button(history_host, text="Clear", command=self.clear).grid(row=2, column=0, sticky="ew", pady=(8, 0))

        # ── Right: detail view ───────────────────────────────────────────────
        self._detail = ReportView(self, title="Detail")
        self._detail.grid(row=0, column=1, sticky="nsew")

        # ── State ────────────────────────────────────────────────────────────
        self._entries: list[tuple[str, str]] = []  # (label, full_text)
        self._detail.set_text("Run an action from Analyze, Docs, or Tools to collect output here.")

    def publish_result(self, title: str, text: str) -> None:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        label = f"[{timestamp}] {title}"
        self._entries.append((label, text))
        self._history_box.insert(tk.END, label)
        # Auto-select the newest entry
        idx = len(self._entries) - 1
        self._history_box.selection_clear(0, tk.END)
        self._history_box.selection_set(idx)
        self._history_box.see(idx)
        self._show_entry(idx)

    def _on_history_select(self, _event) -> None:
        selection = self._history_box.curselection()
        if not selection:
            return
        self._show_entry(selection[0])

    def _show_entry(self, index: int) -> None:
        if index < 0 or index >= len(self._entries):
            return
        label, text = self._entries[index]
        self._detail.set_text(f"{label}\n{'─' * 40}\n{text}")

    def clear(self) -> None:
        self._entries.clear()
        self._history_box.delete(0, tk.END)
        self._detail.set_text("History cleared.")


__all__ = ["ResultsFrame"]
