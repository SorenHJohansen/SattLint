from __future__ import annotations

import threading
from collections.abc import Callable
from tkinter import ttk

from ..binding import SattLintBinding
from ..widgets.analyzer_list import AnalyzerList
from ..widgets.console import ConsoleView
from ..widgets.target_list import TargetList


class AnalyzeFrame(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        binding: SattLintBinding,
        on_result: Callable[[str, str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent, style="Content.TFrame")
        self.binding = binding
        self.on_result = on_result or (lambda _title, _text: None)
        self.on_status = on_status or (lambda _text: None)
        self.cfg = self.binding.load_config()

        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)

        toolbar = ttk.Frame(self, style="Content.TFrame")
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        toolbar.columnconfigure(5, weight=1)

        ttk.Button(toolbar, text="Reload Config", style="Accent.TButton", command=self.reload_config).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(toolbar, text="Self-check", command=self.run_self_check).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(toolbar, text="Ensure AST Cache", command=self.ensure_ast_cache).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(toolbar, text="Variable Analysis", command=self.run_variable_analysis).grid(
            row=0, column=3, padx=(0, 8)
        )
        ttk.Button(toolbar, text="Run Checks", command=self.run_checks).grid(row=0, column=4, padx=(0, 8))
        ttk.Button(toolbar, text="Run Bundle", style="Accent.TButton", command=self.run_bundle).grid(
            row=0, column=5, padx=(0, 8)
        )

        self.targets = TargetList(self, title="Configured Targets")
        self.targets.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))

        self.analyzer_list = AnalyzerList(self, title="Analyzers")
        self.analyzer_list.grid(row=1, column=1, sticky="nsew", pady=(0, 12))

        self.console = ConsoleView(self, title="Output")
        self.console.grid(row=2, column=0, columnspan=2, sticky="nsew")

        self.reload_config()

    def reload_config(self) -> None:
        self.cfg = self.binding.load_config()
        targets = self.cfg.get("analyzed_programs_and_libraries", [])
        self.targets.set_targets(targets)
        analyzers = self.binding.list_enabled_analyzers()
        self.analyzer_list.set_analyzers(analyzers)
        self.console.set_text(f"Loaded config from {self.binding.config_path}")
        self.on_status("Analyze view loaded config")

    def run_self_check(self) -> None:
        self._run_task("Self-check", lambda: self.binding.run_self_check(self.cfg))

    def ensure_ast_cache(self) -> None:
        self._run_task("Ensure AST Cache", lambda: self.binding.ensure_ast_cache(self.cfg))

    def run_variable_analysis(self) -> None:
        self._run_task("Variable Analysis", lambda: self.binding.run_variable_analysis(self.cfg))

    def run_checks(self) -> None:
        selected = self.analyzer_list.get_selected_keys()
        self._run_task("Run Checks", lambda: self.binding.run_checks(self.cfg, selected or None))

    def run_bundle(self) -> None:
        selected = self.analyzer_list.get_selected_keys()
        self._run_task("Run Bundle", lambda: self.binding.run_bundle(self.cfg, selected or None))

    def _run_task(self, title: str, action) -> None:
        self.console.set_text(f"{title} running...")
        self.on_status(f"{title} running...")

        def worker() -> None:
            result = action()
            self.after(0, lambda: self._finish_task(title, result.output))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_task(self, title: str, output: str) -> None:
        self.console.set_text(output)
        self.on_result(title, output)
        self.on_status(f"{title} finished")


__all__ = ["AnalyzeFrame"]
