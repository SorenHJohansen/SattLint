from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..binding import AnalyzerDescriptor
from ..theme import resolve_theme


class AnalyzerList(ttk.Frame):
    """Scrollable checklist of analyzers with Select All / Deselect All helpers."""

    def __init__(self, parent, *, title: str) -> None:
        super().__init__(parent, style="Panel.TFrame", padding=12)
        theme = resolve_theme(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, style="Panel.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=title, style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="All", command=self.select_all).grid(row=0, column=1, padx=(4, 0))
        ttk.Button(header, text="None", command=self.deselect_all).grid(row=0, column=2, padx=(4, 0))

        canvas_host = ttk.Frame(self, style="Panel.TFrame")
        canvas_host.grid(row=1, column=0, sticky="nsew")
        canvas_host.columnconfigure(0, weight=1)
        canvas_host.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(canvas_host, bg=theme.bg_panel, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_host, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self._inner = ttk.Frame(self._canvas, style="Panel.TFrame")
        self._inner_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._vars: list[tuple[tk.BooleanVar, str]] = []  # (boolvar, key)

    def _on_inner_configure(self, _event) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self._canvas.itemconfigure(self._inner_id, width=event.width)

    def set_analyzers(self, analyzers: list[AnalyzerDescriptor]) -> None:
        for widget in self._inner.winfo_children():
            widget.destroy()
        self._vars.clear()
        for analyzer in analyzers:
            var = tk.BooleanVar(value=True)
            self._vars.append((var, analyzer.key))
            ttk.Checkbutton(
                self._inner,
                text=f"{analyzer.key}: {analyzer.name}",
                variable=var,
                style="TCheckbutton",
            ).pack(anchor="w", pady=2, padx=4)
        self._canvas.update_idletasks()

    def get_selected_keys(self) -> list[str]:
        return [key for var, key in self._vars if var.get()]

    def select_all(self) -> None:
        for var, _ in self._vars:
            var.set(True)

    def deselect_all(self) -> None:
        for var, _ in self._vars:
            var.set(False)


__all__ = ["AnalyzerList"]
