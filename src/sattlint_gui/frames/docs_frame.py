from __future__ import annotations

import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, ttk

from ..binding import SattLintBinding
from ..widgets.console import ConsoleView
from ..widgets.report_view import ReportView


class DocsFrame(ttk.Frame):
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
        self.output_dir_var = tk.StringVar(value=str(Path.cwd() / "docs-out"))

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.rowconfigure(3, weight=1)

        toolbar = ttk.Frame(self, style="Content.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        toolbar.columnconfigure(1, weight=1)

        ttk.Button(toolbar, text="Reload Config", style="Accent.TButton", command=self.reload_config).grid(
            row=0,
            column=0,
            padx=(0, 8),
        )
        ttk.Entry(toolbar, textvariable=self.output_dir_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(toolbar, text="Browse", command=self._browse_output_dir).grid(row=0, column=2, padx=(8, 8))
        ttk.Button(toolbar, text="Generate DOCX", command=self.generate_docs).grid(row=0, column=3)

        self.summary = ReportView(self, title="Documentation Scope")
        self.summary.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self.preview = ReportView(self, title="Planned Outputs")
        self.preview.grid(row=2, column=0, sticky="nsew", pady=(0, 12))

        self.console = ConsoleView(self, title="Documentation Output")
        self.console.grid(row=3, column=0, sticky="nsew")

        self.reload_config()

    def _browse_output_dir(self) -> None:
        directory = filedialog.askdirectory(parent=self, initialdir=self.output_dir_var.get().strip() or None)
        if not directory:
            return
        self.output_dir_var.set(directory)
        self._refresh_preview()

    def reload_config(self) -> None:
        self.cfg = self.binding.load_config()
        self._refresh_summary()
        self._refresh_preview()
        self.console.set_text(f"Loaded config from {self.binding.config_path}")
        self.on_status("Documentation view loaded config")

    def _configured_targets(self) -> list[str]:
        raw_targets = self.cfg.get("analyzed_programs_and_libraries", [])
        return [str(target).strip() for target in raw_targets if str(target).strip()]

    def _refresh_summary(self) -> None:
        targets = self._configured_targets()
        output_dir = self.output_dir_var.get().strip() or "(not set)"
        mode = str(self.cfg.get("mode") or "official")
        self.summary.set_text(
            "\n".join(
                [
                    f"Mode: {mode}",
                    f"Configured targets: {len(targets)}",
                    f"Output directory: {output_dir}",
                ]
            )
        )

    def _refresh_preview(self) -> None:
        targets = self._configured_targets()
        output_dir = Path(self.output_dir_var.get().strip() or Path.cwd())
        if not targets:
            self.preview.set_text("No analyzed targets configured.")
            return
        lines = [str(output_dir / f"{target}_FS.docx") for target in targets]
        self.preview.set_text("\n".join(lines))

    def generate_docs(self) -> None:
        self._refresh_summary()
        self._refresh_preview()
        self.console.set_text("Documentation generation running...")
        self.on_status("Documentation generation running...")

        def worker() -> None:
            result = self.binding.run_docgen(self.cfg, output_dir=self.output_dir_var.get().strip())
            self.after(0, lambda: self._finish_generation(result.output))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_generation(self, output: str) -> None:
        self.console.set_text(output)
        self.on_result("Documentation", output)
        self.on_status("Documentation generation finished")


__all__ = ["DocsFrame"]
