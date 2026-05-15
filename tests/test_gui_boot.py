import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

pytest.importorskip("tkinter", exc_type=ImportError)

from sattlint_gui import binding, main
from sattlint_gui import gui as package_gui
from sattlint_gui.theme import ALLOWED_THEME_COLORS, DEFAULT_THEME, SattLintTheme
from sattlint_gui.window import SattLintWindow


def test_package_exports_gui_callable():
    assert callable(package_gui)


def test_binding_load_config_uses_first_tuple_item(monkeypatch, tmp_path):
    fake_app = SimpleNamespace(CONFIG_PATH="config.json", load_config=lambda path: ({"mode": "draft"}, True))
    monkeypatch.setattr(binding, "_APP_MODULE", fake_app)
    monkeypatch.setattr(binding, "_workspace_root", lambda: tmp_path)

    gui_binding = binding.SattLintBinding()
    loaded = gui_binding.load_config()

    assert loaded["mode"] == "draft"
    assert loaded["other_lib_dirs"] == []
    assert "program_dir" not in loaded


def test_gui_entrypoint_creates_window_and_runs_mainloop(monkeypatch):
    events: list[str] = []

    class FakeWindow:
        def mainloop(self) -> None:
            events.append("mainloop")

    monkeypatch.setattr(main, "create_window", lambda theme=None: FakeWindow())

    assert main.gui() == 0
    assert events == ["mainloop"]


def test_default_theme_uses_only_allowed_palette():
    colors = {
        DEFAULT_THEME.bg_main,
        DEFAULT_THEME.bg_panel,
        DEFAULT_THEME.btn_bg,
        DEFAULT_THEME.btn_active,
        DEFAULT_THEME.accent,
        DEFAULT_THEME.input_bg,
        DEFAULT_THEME.text,
        DEFAULT_THEME.console_bg,
        DEFAULT_THEME.console_text,
    }

    assert colors <= ALLOWED_THEME_COLORS


def test_binding_run_docgen_delegates_to_app(monkeypatch):
    captured = {}

    fake_app = SimpleNamespace(
        run_docgen_command=lambda cfg, *, output_dir, output_path, use_cache: (
            captured.update(
                {
                    "cfg": cfg,
                    "output_dir": output_dir,
                    "output_path": output_path,
                    "use_cache": use_cache,
                }
            )
            or 0
        ),
    )
    monkeypatch.setattr(binding, "_APP_MODULE", fake_app)

    gui_binding = binding.SattLintBinding()
    result = gui_binding.run_docgen({"mode": "draft"}, output_dir="docs-out")

    assert result.ok is True
    assert captured == {
        "cfg": {"mode": "draft"},
        "output_dir": "docs-out",
        "output_path": None,
        "use_cache": True,
    }


def test_suggest_workspace_ha_config_fills_missing_paths(monkeypatch, tmp_path):
    libs_root = tmp_path / "Libs" / "HA"
    for relative in ("UnitLib", "ABBLib", "ICF", "ProjectLib", "NNELib", "PPLib"):
        (libs_root / relative).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(binding, "_workspace_root", lambda: tmp_path)

    suggested = binding.suggest_workspace_ha_config({"mode": "draft", "other_lib_dirs": []})

    assert suggested["program_dir"].endswith("UnitLib")
    assert suggested["ABB_lib_dir"].endswith("ABBLib")
    assert suggested["icf_dir"].endswith("ICF")
    assert len(suggested["other_lib_dirs"]) == 3


def test_binding_run_checks_filters_by_selected_keys(monkeypatch):
    class FakeSpec:
        def __init__(self, key, name) -> None:
            self.key = key
            self.name = name

        def run(self, context):
            return type("Report", (), {"summary": lambda self: "ok"})()

    fake_app = SimpleNamespace(
        _get_enabled_analyzers=lambda: [
            FakeSpec("unused", "Unused Variables"),
            FakeSpec("icf", "ICF Validation"),
            FakeSpec("graphics", "Graphics Layout"),
        ],
        _iter_loaded_projects=lambda cfg: [],
        AnalysisContext=None,
        _target_is_library=lambda cfg, bp, graph: False,
        apply_rule_profile_to_report=lambda key, report, cfg: report,
    )
    monkeypatch.setattr(binding, "_APP_MODULE", fake_app)

    gui_binding = binding.SattLintBinding()
    result = gui_binding.run_checks({"mode": "draft"}, selected_keys=["unused", "graphics"])

    assert result.ok is True
    assert "No matching checks found" not in result.output


def test_binding_run_checks_reports_no_matching(monkeypatch):
    fake_app = SimpleNamespace(
        _get_enabled_analyzers=lambda: [],
        _iter_loaded_projects=lambda cfg: [],
        AnalysisContext=None,
        _target_is_library=lambda cfg, bp, graph: False,
        apply_rule_profile_to_report=lambda key, report, cfg: report,
    )
    monkeypatch.setattr(binding, "_APP_MODULE", fake_app)

    gui_binding = binding.SattLintBinding()
    result = gui_binding.run_checks({"mode": "draft"}, selected_keys=["nonexistent"])

    assert result.ok is True
    assert "No matching checks found" in result.output


def test_binding_run_bundle_combines_variable_analysis_and_checks(monkeypatch):
    gui_binding = binding.SattLintBinding()
    monkeypatch.setattr(
        gui_binding, "run_variable_analysis", lambda cfg: binding.BindingResult(ok=True, output="var ok")
    )
    monkeypatch.setattr(
        gui_binding, "run_checks", lambda cfg, selected_keys=None: binding.BindingResult(ok=True, output="checks ok")
    )

    result = gui_binding.run_bundle({"mode": "draft"})

    assert result.ok is True
    assert "[Variable Analysis]\nvar ok" in result.output
    assert "[Checks]\nchecks ok" in result.output


def test_binding_run_bundle_marks_failed_if_any_step_fails(monkeypatch):
    gui_binding = binding.SattLintBinding()
    monkeypatch.setattr(
        gui_binding, "run_variable_analysis", lambda cfg: binding.BindingResult(ok=False, output="var failed")
    )
    monkeypatch.setattr(
        gui_binding, "run_checks", lambda cfg, selected_keys=None: binding.BindingResult(ok=True, output="checks ok")
    )

    result = gui_binding.run_bundle({"mode": "draft"})

    assert result.ok is False


def test_gui_main_module_exits_with_gui_return_code(monkeypatch):
    monkeypatch.setattr("sattlint_gui.main.gui", lambda: 7)

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("sattlint_gui.__main__", run_name="__main__")

    assert exc.value.code == 7


def test_theme_resolve_theme_uses_default_and_custom_theme():
    from sattlint_gui.theme import resolve_theme

    class FakeWidget:
        def __init__(self, root) -> None:
            self._root = root

        def winfo_toplevel(self):
            return self._root

    assert resolve_theme(None) == DEFAULT_THEME

    custom = SattLintTheme(bg_main="#fbfbee", accent="#001ba3")
    themed_widget = FakeWidget(SimpleNamespace(theme=custom))
    unthemed_widget = FakeWidget(SimpleNamespace(theme="not-a-theme"))

    assert resolve_theme(cast(Any, themed_widget)) == custom
    assert resolve_theme(cast(Any, unthemed_widget)) == DEFAULT_THEME


def test_binding_capture_output_and_fallback_paths(monkeypatch, tmp_path):
    libs_root = tmp_path / "Libs" / "HA"
    for relative in ("UnitLib", "ABBLib", "ICF", "ProjectLib"):
        (libs_root / relative).mkdir(parents=True, exist_ok=True)

    ok_result = binding._capture_output(lambda: 5)
    printed_result = binding._capture_output(lambda: print("hello"))

    assert ok_result == binding.BindingResult(ok=True, output="OK", value=5)
    assert printed_result.ok is True
    assert printed_result.output == "hello"

    def _boom() -> None:
        raise RuntimeError("boom")

    failure = binding._capture_output(_boom)

    assert failure.ok is False
    assert failure.output == "Error: boom"

    monkeypatch.setattr(binding, "_get_app_module", lambda: (_ for _ in ()).throw(RuntimeError("missing app")))
    monkeypatch.setattr(binding, "_workspace_root", lambda: tmp_path)

    gui_binding = binding.SattLintBinding()
    loaded = gui_binding.load_config()

    assert gui_binding.config_path == Path("sattlint.json")
    assert gui_binding.graphics_rules_path == Path("graphics_rules.json")
    assert loaded["mode"] == "draft"
    assert loaded["program_dir"].endswith("UnitLib")
    assert loaded["ABB_lib_dir"].endswith("ABBLib")
    assert loaded["icf_dir"].endswith("ICF")
    assert loaded["other_lib_dirs"] == [str(libs_root / "ProjectLib")]
    assert gui_binding.save_config({}).ok is False
    assert gui_binding.run_self_check({}).ok is False
    assert gui_binding.ensure_ast_cache({}).ok is False
    assert gui_binding.run_variable_analysis({}).ok is False
    assert gui_binding.run_docgen({}, output_dir="docs-out").ok is False
    assert gui_binding.run_checks({}).ok is False
    assert gui_binding.list_enabled_analyzers() == []
    assert gui_binding.target_exists("TargetA", {}) is False


def test_window_publish_result_routes_to_results_view():
    events: list[str] = []
    published: list[tuple[str, str]] = []

    class FakeResultsView:
        def publish_result(self, title: str, text: str) -> None:
            published.append((title, text))

    window = cast(Any, SattLintWindow.__new__(SattLintWindow))
    window._views = {"Results": FakeResultsView()}
    window.show_view = lambda name: events.append(f"show:{name}")
    window.set_status = lambda text: events.append(f"status:{text}")

    SattLintWindow.publish_result(window, "Self-check", "ok")

    assert published == [("Self-check", "ok")]
    assert events == ["show:Results", "status:Updated results for Self-check"]


def test_window_publish_result_routes_to_results_frame():
    events: list[str] = []

    class FakeResultsFrame:
        def publish_result(self, title: str, text: str) -> None:
            events.append(f"publish:{title}:{text}")

        def tkraise(self) -> None:
            events.append("tkraise")

    class FakeSidebar:
        def set_selected(self, name: str) -> None:
            events.append(f"sidebar_select:{name}")

    window = SimpleNamespace()
    window._views = {"Results": FakeResultsFrame()}
    window.sidebar = FakeSidebar()
    window.set_status = lambda text: events.append(f"status:{text}")
    window.show_view = lambda name: (
        window._views[name].tkraise(),
        window.sidebar.set_selected(name),
        window.set_status(f"Viewing {name}"),
    )

    SattLintWindow.publish_result(cast(Any, window), "Test Output", "sample content")

    assert "publish:Test Output:sample content" in events
    assert "tkraise" in events
    assert "sidebar_select:Results" in events
    assert any("Updated results for Test Output" in event for event in events)


def test_window_set_status_updates_status_var():
    window = SimpleNamespace()
    window.status_var = SimpleNamespace(value="Initial")
    window.status_var.set = lambda text: setattr(window.status_var, "value", text)
    window.status_var.get = lambda: window.status_var.value

    SattLintWindow.set_status(cast(Any, window), "New Status")

    assert window.status_var.get() == "New Status"


def test_window_show_view_and_handle_close_cover_sidebar_and_abort_paths():
    events: list[str] = []

    class FakeView:
        def __init__(self, can_close: bool = True) -> None:
            self._can_close = can_close

        def tkraise(self) -> None:
            events.append("raise")

        def can_close(self) -> bool:
            events.append(f"can_close:{self._can_close}")
            return self._can_close

    window = cast(Any, SattLintWindow.__new__(SattLintWindow))
    window.sidebar = SimpleNamespace(set_selected=lambda name: events.append(f"sidebar:{name}"))
    window.status_var = SimpleNamespace(set=lambda text: events.append(f"status:{text}"))
    window.destroy = lambda: events.append("destroy")
    window._views = {"Analyze": FakeView(), "Config": FakeView(False)}

    SattLintWindow.show_view(window, "Analyze")
    SattLintWindow._handle_close(window)

    assert events[:3] == ["raise", "sidebar:Analyze", "status:Viewing Analyze"]
    assert "destroy" not in events

    events.clear()
    window._views = {"Analyze": FakeView(), "Config": FakeView()}
    SattLintWindow._handle_close(window)
    assert events == ["can_close:True", "can_close:True", "destroy"]


def test_window_init_and_build_layout_cover_real_constructor_paths_with_fake_tk(monkeypatch):
    from sattlint_gui import window as window_module

    events: list[Any] = []
    created_views: dict[str, Any] = {}

    class FakeWidget:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs
            self.pack_calls: list[dict[str, Any]] = []
            self.grid_calls: list[dict[str, Any]] = []
            self.columnconfigure_calls: list[tuple[int, int]] = []
            self.rowconfigure_calls: list[tuple[int, int]] = []
            self.pack_propagate_value: bool | None = None
            self.raised = False

        def pack(self, **kwargs: Any) -> None:
            self.pack_calls.append(kwargs)

        def pack_propagate(self, value: bool) -> None:
            self.pack_propagate_value = value

        def grid(self, **kwargs: Any) -> None:
            self.grid_calls.append(kwargs)

        def columnconfigure(self, index: int, weight: int) -> None:
            self.columnconfigure_calls.append((index, weight))

        def rowconfigure(self, index: int, weight: int) -> None:
            self.rowconfigure_calls.append((index, weight))

        def tkraise(self) -> None:
            self.raised = True

    class FakePanedWindow(FakeWidget):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.add_calls: list[tuple[Any, dict[str, Any]]] = []

        def add(self, child: Any, **kwargs: Any) -> None:
            self.add_calls.append((child, kwargs))

    class FakeStringVar:
        def __init__(self, value: str = "") -> None:
            self.value = value

        def set(self, value: str) -> None:
            self.value = value

        def get(self) -> str:
            return self.value

    class FakeSidebar(FakeWidget):
        def __init__(self, parent: Any, *, items: tuple[str, ...], on_select: Any) -> None:
            super().__init__(parent, items=items, on_select=on_select)
            self.items = items
            self.on_select = on_select
            self.selected: str | None = None

        def set_selected(self, name: str) -> None:
            self.selected = name

    def make_view(name: str):
        def factory(*args: Any, **kwargs: Any) -> Any:
            view = FakeWidget(*args, **kwargs)
            created_views[name] = view
            return view

        return factory

    monkeypatch.setattr(window_module.tk.Tk, "__init__", lambda self: events.append(("tk_init", None)))
    monkeypatch.setattr(window_module.tk.Tk, "title", lambda self, text: events.append(("title", text)))
    monkeypatch.setattr(window_module.tk.Tk, "geometry", lambda self, text: events.append(("geometry", text)))
    monkeypatch.setattr(
        window_module.tk.Tk, "minsize", lambda self, width, height: events.append(("minsize", width, height))
    )
    monkeypatch.setattr(window_module.tk.Tk, "configure", lambda self, **kwargs: events.append(("configure", kwargs)))
    monkeypatch.setattr(
        window_module.tk.Tk,
        "protocol",
        lambda self, name, callback: events.append(("protocol", name, callable(callback))),
    )
    monkeypatch.setattr(window_module.tk, "PanedWindow", FakePanedWindow)
    monkeypatch.setattr(window_module.tk, "Frame", FakeWidget)
    monkeypatch.setattr(window_module.ttk, "Frame", FakeWidget)
    monkeypatch.setattr(window_module.ttk, "Label", FakeWidget)
    monkeypatch.setattr(window_module.tk, "StringVar", FakeStringVar)
    monkeypatch.setattr(window_module, "SidebarFrame", FakeSidebar)
    monkeypatch.setattr(window_module, "AnalyzeFrame", make_view("Analyze"))
    monkeypatch.setattr(window_module, "ConfigFrame", make_view("Config"))
    monkeypatch.setattr(window_module, "DocsFrame", make_view("Docs"))
    monkeypatch.setattr(window_module, "ToolsFrame", make_view("Tools"))
    monkeypatch.setattr(window_module, "ResultsFrame", make_view("Results"))
    monkeypatch.setattr(window_module, "SattLintBinding", lambda: "binding")
    monkeypatch.setattr(window_module, "apply_theme", lambda root, theme: events.append(("apply_theme", theme.accent)))

    theme = SattLintTheme(bg_main="#101010", bg_panel="#202020", sidebar_width=280, accent="#ffaa00")
    window = window_module.SattLintWindow(theme=theme)
    sidebar = cast(Any, window.sidebar)

    assert window.theme is theme
    assert window.binding == "binding"
    assert window.sidebar is not None
    assert sidebar.items == ("Analyze", "Config", "Docs", "Tools", "Results")
    assert sidebar.selected == "Analyze"
    assert window.status_var.get() == "Viewing Analyze"
    assert created_views.keys() == {"Analyze", "Config", "Docs", "Tools", "Results"}
    assert created_views["Analyze"].kwargs["binding"] == "binding"
    assert callable(created_views["Analyze"].kwargs["on_result"])
    assert callable(created_views["Analyze"].kwargs["on_status"])
    assert created_views["Results"].raised is False
    assert all(view.grid_calls for view in created_views.values())
    assert ("title", "SattLint GUI") in events
    assert ("geometry", "1280x800") in events
    assert ("minsize", 960, 640) in events
    assert ("configure", {"bg": "#101010"}) in events
    assert ("protocol", "WM_DELETE_WINDOW", True) in events
    assert ("apply_theme", "#ffaa00") in events


def test_window_publish_result_handles_missing_and_non_callable_results_view():
    events: list[str] = []
    window = cast(Any, SattLintWindow.__new__(SattLintWindow))
    window.show_view = lambda name: events.append(f"show:{name}")
    window.set_status = lambda text: events.append(f"status:{text}")
    window._views = {}

    SattLintWindow.publish_result(window, "Self-check", "ok")
    assert events == []

    window._views = {"Results": object()}
    SattLintWindow.publish_result(window, "Self-check", "ok")
    assert events == ["show:Results", "status:Updated results for Self-check"]
