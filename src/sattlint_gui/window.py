from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .binding import SattLintBinding
from .frames.analyze_frame import AnalyzeFrame
from .frames.config_frame import ConfigFrame
from .frames.docs_frame import DocsFrame
from .frames.results_frame import ResultsFrame
from .frames.sidebar import SidebarFrame
from .frames.tools_frame import ToolsFrame
from .theme import DEFAULT_THEME, SattLintTheme
from .widgets.styled_widgets import apply_theme


class SattLintWindow(tk.Tk):
    def __init__(self, *, theme: SattLintTheme | None = None) -> None:
        super().__init__()
        self.theme = theme or DEFAULT_THEME
        self.binding = SattLintBinding()
        self.sidebar: SidebarFrame | None = None
        self.title("SattLint GUI")
        self.geometry("1280x800")
        self.minsize(960, 640)
        self.configure(bg=self.theme.bg_main)
        apply_theme(self, self.theme)
        self.protocol("WM_DELETE_WINDOW", self._handle_close)

        self._views: dict[str, ttk.Frame] = {}
        self._build_layout()
        self.show_view("Analyze")

    def _build_layout(self) -> None:
        paned = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            bg=self.theme.bg_main,
            sashwidth=6,
            relief=tk.FLAT,
            bd=0,
        )
        paned.pack(fill=tk.BOTH, expand=True)

        sidebar_host = tk.Frame(self, width=self.theme.sidebar_width, bg=self.theme.bg_panel)
        sidebar_host.pack_propagate(False)
        content_host = ttk.Frame(self, style="Content.TFrame")
        content_host.columnconfigure(0, weight=1)
        content_host.rowconfigure(1, weight=1)
        content_host.rowconfigure(2, weight=0)

        paned.add(sidebar_host, minsize=self.theme.sidebar_width)
        paned.add(content_host)

        sidebar = SidebarFrame(
            sidebar_host,
            items=("Analyze", "Config", "Docs", "Tools", "Results"),
            on_select=self.show_view,
        )
        sidebar.pack(fill=tk.BOTH, expand=True)
        self.sidebar = sidebar

        title = ttk.Label(content_host, text="SattLint", style="Title.TLabel")
        title.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))

        view_host = ttk.Frame(content_host, style="Content.TFrame")
        view_host.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        view_host.columnconfigure(0, weight=1)
        view_host.rowconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(content_host, textvariable=self.status_var, style="Muted.TLabel")
        status_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 16))

        self._views = {
            "Analyze": AnalyzeFrame(
                view_host,
                binding=self.binding,
                on_result=self.publish_result,
                on_status=self.set_status,
            ),
            "Config": ConfigFrame(view_host, binding=self.binding),
            "Docs": DocsFrame(
                view_host,
                binding=self.binding,
                on_result=self.publish_result,
                on_status=self.set_status,
            ),
            "Tools": ToolsFrame(
                view_host,
                binding=self.binding,
                on_result=self.publish_result,
                on_status=self.set_status,
            ),
            "Results": ResultsFrame(view_host),
        }

        for frame in self._views.values():
            frame.grid(row=0, column=0, sticky="nsew")

    def show_view(self, name: str) -> None:
        view = self._views[name]
        view.tkraise()
        if self.sidebar is not None:
            self.sidebar.set_selected(name)
        self.set_status(f"Viewing {name}")

    def _handle_close(self) -> None:
        for view in self._views.values():
            can_close = getattr(view, "can_close", None)
            if callable(can_close) and not can_close():
                return
        self.destroy()

    def publish_result(self, title: str, text: str) -> None:
        results_view = self._views.get("Results")
        if results_view is None:
            return
        publisher = getattr(results_view, "publish_result", None)
        if callable(publisher):
            publisher(title, text)
        self.show_view("Results")
        self.set_status(f"Updated results for {title}")

    def set_status(self, text: str) -> None:
        self.status_var.set(text)


__all__ = ["SattLintWindow"]
