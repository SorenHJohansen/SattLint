from __future__ import annotations

import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ..binding import SattLintBinding
from ..widgets.console import ConsoleView


def _noop_result(_title: str, _text: str) -> None:
    return None


def _noop_status(_text: str) -> None:
    return None


def _console_text(console: object) -> str:
    get_text = getattr(console, "get_text", None)
    if callable(get_text):
        return str(get_text())
    text_widget = getattr(console, "_text", None)
    getter = getattr(text_widget, "get", None)
    if callable(getter):
        return str(getter("1.0", "end-1c"))
    return ""


class ToolsFrame(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        binding: SattLintBinding,
        on_result: Callable[[str, str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent, style="Content.TFrame")
        self.binding = binding
        self.on_result: Callable[[str, str], None] = on_result or _noop_result
        self.on_status: Callable[[str], None] = on_status or _noop_status
        self.cfg = self.binding.load_config()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, style="Content.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Button(toolbar, text="Self-check", style="Accent.TButton", command=self.run_self_check).pack(side="left")
        ttk.Button(toolbar, text="List Analyzers", command=self.list_analyzers).pack(side="left", padx=(8, 0))

        self.console = ConsoleView(self, title="Tools Output")
        self.console.grid(row=1, column=0, sticky="nsew")
        self.list_analyzers()

    def run_self_check(self) -> None:
        self.console.set_text("Self-check running...")
        self.on_status("Self-check running...")

        def worker() -> None:
            result = self.binding.run_self_check(self.cfg)
            self.after(0, lambda: self._finish_task("Self-check", result.output))

        threading.Thread(target=worker, daemon=True).start()

    def list_analyzers(self) -> None:
        analyzers = self.binding.list_enabled_analyzers()
        lines = [f"{item.key}: {item.name}" for item in analyzers]
        self.console.set_text("\n".join(lines) if lines else "No analyzers configured")
        self.on_result("Enabled Analyzers", _console_text(self.console))
        self.on_status("Listed enabled analyzers")

    def _finish_task(self, title: str, output: str) -> None:
        self.console.set_text(output)
        self.on_result(title, output)
        self.on_status(f"{title} finished")


__all__ = ["ToolsFrame"]
