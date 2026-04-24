from __future__ import annotations

from tkinter import ttk

from ..widgets.report_view import ReportView


class ResultsFrame(ttk.Frame):
    def __init__(self, parent) -> None:
        super().__init__(parent, style="Content.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.report = ReportView(self, title="Results")
        self.report.grid(row=0, column=0, sticky="nsew")
        self.report.set_text(
            "Result routing is staged.\n"
            "Analyze and Tools views already expose real output while this shared view is being wired."
        )

    def publish_result(self, title: str, text: str) -> None:
        self.report.append_text(f"[{title}]\n{text}")


__all__ = ["ResultsFrame"]
