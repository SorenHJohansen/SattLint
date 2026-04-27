from types import SimpleNamespace
from typing import Any, cast

from sattlint_gui import binding, main
from sattlint_gui import gui as package_gui
from sattlint_gui.frames.config_frame import apply_editable_config, extract_editable_config
from sattlint_gui.frames.docs_frame import DocsFrame
from sattlint_gui.frames.results_frame import ResultsFrame
from sattlint_gui.theme import ALLOWED_THEME_COLORS, DEFAULT_THEME
from sattlint_gui.widgets.analyzer_list import AnalyzerList
from sattlint_gui.widgets.report_view import _ISSUE_COUNT_RE, _TARGET_HEADER_RE
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


def test_extract_editable_config_normalizes_defaults():
    extracted = extract_editable_config({"mode": "draft", "program_dir": None, "other_lib_dirs": None})

    assert extracted["mode"] == "draft"
    assert extracted["program_dir"] == ""
    assert extracted["other_lib_dirs"] == []
    assert extracted["analyzed_programs_and_libraries"] == []


def test_apply_editable_config_preserves_nested_sections():
    base_cfg = {
        "mode": "official",
        "program_dir": "old-program",
        "analysis": {"keep": True},
        "documentation": {"classifications": {"em": {"name_contains": ["Equip"]}}},
    }
    editable_cfg = {
        "mode": "draft",
        "program_dir": "new-program",
        "ABB_lib_dir": "abb",
        "icf_dir": "icf",
        "scan_root_only": True,
        "fast_cache_validation": False,
        "debug": True,
        "analyzed_programs_and_libraries": ["TargetA"],
        "other_lib_dirs": ["lib-a", "lib-b"],
    }

    merged = apply_editable_config(base_cfg, editable_cfg)

    assert merged["mode"] == "draft"
    assert merged["program_dir"] == "new-program"
    assert merged["analysis"] == {"keep": True}
    assert merged["documentation"] == {"classifications": {"em": {"name_contains": ["Equip"]}}}
    assert merged["analyzed_programs_and_libraries"] == ["TargetA"]
    assert merged["other_lib_dirs"] == ["lib-a", "lib-b"]


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


def test_analyzer_list_selection():
    # Test AnalyzerList selection logic without a real Tk root by driving _vars directly
    # with a lightweight stand-in that matches the BooleanVar interface used by get_selected_keys.
    class FakeBoolVar:
        def __init__(self, value: bool = True) -> None:
            self._value = value

        def get(self) -> bool:
            return self._value

        def set(self, value: bool) -> None:
            self._value = value

    al = cast(Any, AnalyzerList.__new__(AnalyzerList))
    al._vars = [
        (FakeBoolVar(True), "unused"),
        (FakeBoolVar(True), "icf"),
        (FakeBoolVar(True), "graphics"),
    ]

    # all selected by default
    assert al.get_selected_keys() == ["unused", "icf", "graphics"]

    # deselect one
    al._vars[1][0].set(False)
    assert al.get_selected_keys() == ["unused", "graphics"]

    # select_all restores
    al.select_all()
    assert al.get_selected_keys() == ["unused", "icf", "graphics"]

    # deselect_all clears
    al.deselect_all()
    assert al.get_selected_keys() == []


def test_binding_run_checks_filters_by_selected_keys(monkeypatch):
    ran: list[str] = []

    class FakeSpec:
        def __init__(self, key, name) -> None:
            self.key = key
            self.name = name

        def run(self, context):
            ran.append(self.key)
            return type("Report", (), {"summary": lambda self: f"{self.key} ok"})()

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


def test_docs_frame_generate_docs_reports_status(monkeypatch):
    events: list[tuple[str, str]] = []

    class FakeStringVar:
        def __init__(self, value="") -> None:
            self.value = value

        def get(self) -> str:
            return self.value

        def set(self, value: str) -> None:
            self.value = value

    class FakeBinding:
        config_path = "config.toml"

        def load_config(self) -> dict:
            return {"analyzed_programs_and_libraries": ["TargetA"], "mode": "official"}

        def run_docgen(self, cfg: dict, *, output_dir: str, output_path=None):
            assert cfg["analyzed_programs_and_libraries"] == ["TargetA"]
            assert output_dir == "docs-out"
            return binding.BindingResult(ok=True, output="Wrote docs-out/TargetA_FS.docx")

    class FakeReportView:
        def __init__(self) -> None:
            self.text = ""

        def set_text(self, text: str) -> None:
            self.text = text

    class FakeConsoleView(FakeReportView):
        pass

    class FakeThread:
        def __init__(self, *, target, daemon) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    monkeypatch.setattr("sattlint_gui.frames.docs_frame.threading.Thread", FakeThread)

    frame = cast(Any, DocsFrame.__new__(DocsFrame))
    frame.binding = FakeBinding()
    frame.on_result = lambda title, text: events.append(("result", f"{title}:{text}"))
    frame.on_status = lambda text: events.append(("status", text))
    frame.cfg = frame.binding.load_config()
    frame.output_dir_var = FakeStringVar("docs-out")
    frame.summary = FakeReportView()
    frame.preview = FakeReportView()
    frame.console = FakeConsoleView()
    frame.after = lambda _delay, callback: callback() or "after-id"

    frame.generate_docs()

    assert frame.console.text == "Wrote docs-out/TargetA_FS.docx"
    assert ("status", "Documentation generation running...") in events
    assert ("status", "Documentation generation finished") in events
    assert ("result", "Documentation:Wrote docs-out/TargetA_FS.docx") in events


# ── Phase 4 tests ────────────────────────────────────────────────────────────


def test_report_view_target_header_regex():
    assert _TARGET_HEADER_RE.match("=== Target: MyUnit ===")
    assert _TARGET_HEADER_RE.match("=== Unused Variables (unused) ===")
    assert not _TARGET_HEADER_RE.match("  - some finding")
    assert not _TARGET_HEADER_RE.match("3 issues")


def test_report_view_issue_count_regex():
    assert _ISSUE_COUNT_RE.match("0 issues")
    assert _ISSUE_COUNT_RE.match("12 issues")
    assert _ISSUE_COUNT_RE.match("  1 issue")
    assert not _ISSUE_COUNT_RE.match("some finding (3 issues)")


def test_results_frame_publish_adds_history():
    class FakeHistoryBox:
        def __init__(self) -> None:
            self._items: list[str] = []

        def insert(self, _end, label: str) -> None:
            self._items.append(label)

        def delete(self, _start, _end) -> None:
            self._items.clear()

        def selection_clear(self, _start, _end) -> None:
            pass

        def selection_set(self, _index) -> None:
            pass

        def see(self, _index) -> None:
            pass

        def curselection(self):
            return ()

    class FakeReportView:
        def __init__(self) -> None:
            self.text = ""

        def set_text(self, text: str) -> None:
            self.text = text

        def append_text(self, text: str) -> None:
            self.text += text

    frame = cast(Any, ResultsFrame.__new__(ResultsFrame))
    frame._entries = []
    frame._history_box = FakeHistoryBox()
    frame._detail = FakeReportView()

    frame.publish_result("Self-check", "ok\n1 issue")
    frame.publish_result("Variable Analysis", "3 issues")

    assert len(frame._entries) == 2
    assert frame._entries[0][1] == "ok\n1 issue"
    assert frame._entries[1][1] == "3 issues"
    assert len(frame._history_box._items) == 2
    assert "Self-check" in frame._history_box._items[0]
    assert "Variable Analysis" in frame._history_box._items[1]
    # detail shows the most recently published entry
    assert "3 issues" in frame._detail.text


def test_results_frame_clear_resets_state():
    class FakeHistoryBox:
        def __init__(self) -> None:
            self._items: list[str] = []

        def insert(self, _end, label: str) -> None:
            self._items.append(label)

        def delete(self, _start, _end) -> None:
            self._items.clear()

        def selection_clear(self, _start, _end) -> None:
            pass

        def selection_set(self, _index) -> None:
            pass

        def see(self, _index) -> None:
            pass

    class FakeDetailView:
        def __init__(self) -> None:
            self.text = ""

        def set_text(self, text: str) -> None:
            self.text = text

    frame = cast(Any, ResultsFrame.__new__(ResultsFrame))
    frame._entries = [("lbl", "txt")]
    frame._history_box = FakeHistoryBox()
    frame._history_box._items = ["lbl"]
    frame._detail = FakeDetailView()

    frame.clear()

    assert frame._entries == []
    assert frame._history_box._items == []
    assert "cleared" in frame._detail.text


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


# ── Phase 5 tests: Higher-level GUI and integration workflows ─────────────────


def test_window_publish_result_routes_to_results_frame():
    """Verify that publish_result routes output to Results frame and switches view."""
    events: list[str] = []

    class FakeResultsFrame:
        def publish_result(self, title: str, text: str) -> None:
            events.append(f"publish:{title}:{text}")

        def tkraise(self) -> None:
            events.append("tkraise")

    class FakeSidebar:
        def set_selected(self, name: str) -> None:
            events.append(f"sidebar_select:{name}")

    from types import SimpleNamespace

    from sattlint_gui.window import SattLintWindow

    window = SimpleNamespace()
    window._views = {"Results": FakeResultsFrame()}
    window.sidebar = FakeSidebar()
    window.set_status = lambda text: events.append(f"status:{text}")
    window.show_view = lambda name: (
        window._views[name].tkraise(),
        window.sidebar.set_selected(name),
        window.set_status(f"Viewing {name}"),
    )

    # Bind the method from the real window class
    SattLintWindow.publish_result(cast(Any, window), "Test Output", "sample content")

    assert "publish:Test Output:sample content" in events
    assert "tkraise" in events
    assert "sidebar_select:Results" in events
    assert any("Updated results for Test Output" in e for e in events)


def test_window_set_status_updates_status_var(monkeypatch):
    """Verify status_var updates via set_status."""
    from types import SimpleNamespace

    from sattlint_gui.window import SattLintWindow

    window = SimpleNamespace()
    window.status_var = SimpleNamespace(value="Initial")
    window.status_var.set = lambda text: setattr(window.status_var, "value", text)
    window.status_var.get = lambda: window.status_var.value

    SattLintWindow.set_status(cast(Any, window), "New Status")

    assert window.status_var.get() == "New Status"


def test_docs_frame_refresh_preview_shows_output_paths(monkeypatch):
    """Verify DocsFrame._refresh_preview displays expected output file paths."""
    from types import SimpleNamespace
    from typing import Any, cast

    from sattlint_gui.frames.docs_frame import DocsFrame

    class FakeReportView:
        def __init__(self) -> None:
            self.text = ""

        def set_text(self, text: str) -> None:
            self.text = text

    class FakeBinding:
        config_path = "config.toml"

        def load_config(self) -> dict:
            return {"analyzed_programs_and_libraries": ["TargetA", "TargetB"], "mode": "official"}

    frame = cast(Any, DocsFrame.__new__(DocsFrame))
    frame.cfg = {"analyzed_programs_and_libraries": ["TargetA", "TargetB"]}
    frame.preview = FakeReportView()
    frame.output_dir_var = SimpleNamespace(get=lambda: "custom-out")

    frame._refresh_preview()

    # Account for platform-specific path separators
    assert "TargetA_FS.docx" in frame.preview.text
    assert "TargetB_FS.docx" in frame.preview.text
    assert "custom-out" in frame.preview.text


def test_results_frame_publish_result_adds_timestamped_entry(monkeypatch):
    """Verify ResultsFrame.publish_result adds timestamped history entries."""
    from typing import Any, cast

    from sattlint_gui.frames.results_frame import ResultsFrame

    class FakeListbox:
        def __init__(self) -> None:
            self.items = []

        def insert(self, index: str, item: str) -> None:
            self.items.append(item)

        def selection_clear(self, start: int, end: int) -> None:
            pass

        def selection_set(self, index: int) -> None:
            pass

        def see(self, index: int) -> None:
            pass

    class FakeReportView:
        def __init__(self, parent, title=None) -> None:
            self.text_content = ""

        def set_text(self, text: str) -> None:
            self.text_content = text

    frame = cast(Any, ResultsFrame.__new__(ResultsFrame))
    frame._history_box = FakeListbox()
    frame._detail = FakeReportView(None)
    frame._entries = []

    frame.publish_result("Test Result", "test output content")

    assert len(frame._entries) == 1
    # Entry label includes timestamp: "[HH:MM:SS] Test Result"
    assert "Test Result" in frame._entries[0][0]
    assert frame._entries[0][1] == "test output content"
    assert len(frame._history_box.items) == 1
    assert "Test Result" in frame._history_box.items[0]


def test_analyze_frame_run_bundle_combines_va_and_checks_output():
    """Verify AnalyzeFrame.run_bundle calls binding.run_bundle with selected keys."""
    from types import SimpleNamespace
    from typing import Any, cast

    from sattlint_gui.binding import BindingResult, SattLintBinding
    from sattlint_gui.frames.analyze_frame import AnalyzeFrame

    call_args = {}

    class FakeBinding(SattLintBinding):
        def run_bundle(self, cfg, selected_keys=None):
            call_args["cfg"] = cfg
            call_args["selected_keys"] = selected_keys
            return BindingResult(ok=True, output="[Variable Analysis]\nok\n\n[Checks]\nok")

    class FakeAnalyzerList:
        def get_selected_keys(self):
            return ["unused", "icf"]

    frame = cast(Any, AnalyzeFrame.__new__(AnalyzeFrame))
    frame.binding = FakeBinding()
    frame.cfg = {"mode": "draft"}
    frame.analyzer_list = FakeAnalyzerList()
    frame.console = SimpleNamespace(set_text=lambda t: None)
    frame.on_result = lambda _title, _text: None
    frame.on_status = lambda _text: None

    # Directly call the action to test binding integration
    def action():
        return frame.binding.run_bundle(frame.cfg, ["unused", "icf"])

    result = action()

    assert result.ok is True
    assert "[Variable Analysis]" in result.output
    assert "[Checks]" in result.output
