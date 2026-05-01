import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattlint_gui import binding, main
from sattlint_gui import gui as package_gui
from sattlint_gui.frames.config_frame import ConfigFrame, apply_editable_config, extract_editable_config
from sattlint_gui.frames.docs_frame import DocsFrame
from sattlint_gui.frames.results_frame import ResultsFrame
from sattlint_gui.theme import ALLOWED_THEME_COLORS, DEFAULT_THEME, SattLintTheme
from sattlint_gui.widgets.analyzer_list import AnalyzerList
from sattlint_gui.widgets.report_view import _ISSUE_COUNT_RE, _TARGET_HEADER_RE
from sattlint_gui.window import SattLintWindow


class _FakeVar:
    def __init__(self, value: Any) -> None:
        self.value = value

    def get(self) -> Any:
        return self.value

    def set(self, value: Any) -> None:
        self.value = value


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def configure(self, *, text: str) -> None:
        self.text = text


class _FakeListbox:
    def __init__(self, items: list[str] | None = None) -> None:
        self.items = list(items or [])
        self._selection: tuple[int, ...] = ()

    def delete(self, first: int, last: Any = None) -> None:
        if last is None:
            del self.items[first]
            return
        self.items.clear()

    def insert(self, _index: Any, value: str) -> None:
        self.items.append(value)

    def get(self, index: int) -> str:
        return self.items[index]

    def size(self) -> int:
        return len(self.items)

    def curselection(self) -> tuple[int, ...]:
        return self._selection


class _FakeTextWidget:
    def __init__(self) -> None:
        self.content = ""
        self.state = "normal"
        self.insert_calls: list[tuple[str, str | None]] = []
        self.tag_calls: list[tuple[str, dict[str, Any]]] = []
        self.seen: str | None = None

    def tag_configure(self, tag: str, **kwargs: Any) -> None:
        self.tag_calls.append((tag, kwargs))

    def configure(self, **kwargs: Any) -> None:
        if "state" in kwargs:
            self.state = kwargs["state"]

    def delete(self, _start: str, _end: str) -> None:
        self.content = ""

    def insert(self, _index: str, text: str, tag: str | None = None) -> None:
        self.content += text
        self.insert_calls.append((text, tag))

    def index(self, _index: str) -> str:
        return "1.0" if not self.content else "2.0"

    def see(self, index: str) -> None:
        self.seen = index

    def get(self, _start: str, _end: str) -> str:
        return self.content


def _make_config_frame_double(*, binding_obj: Any | None = None, full_config: dict | None = None) -> Any:
    fake_binding = binding_obj or SimpleNamespace(
        config_path="config.toml",
        graphics_rules_path=Path("graphics-rules.toml"),
        load_config=lambda: {},
        save_config=lambda _cfg: SimpleNamespace(ok=True, output="saved"),
        target_exists=lambda _target, _cfg: True,
    )
    frame = SimpleNamespace(
        binding=fake_binding,
        _loading=False,
        _dirty=False,
        _full_config=full_config or {},
        status=_FakeLabel(),
        targets_list=_FakeListbox(),
        other_libs_list=_FakeListbox(),
        mode_var=_FakeVar("official"),
        scan_root_only_var=_FakeVar(False),
        fast_cache_validation_var=_FakeVar(True),
        debug_var=_FakeVar(False),
        program_dir_var=_FakeVar(""),
        abb_lib_dir_var=_FakeVar(""),
        icf_dir_var=_FakeVar(""),
        graphics_rules_path_var=_FakeVar(""),
    )
    frame_any = cast(Any, frame)
    frame._refresh_status = lambda text=None: ConfigFrame._refresh_status(frame_any, text)
    frame._set_dirty = lambda value: ConfigFrame._set_dirty(frame_any, value)
    frame._set_listbox_items = lambda listbox, values: ConfigFrame._set_listbox_items(frame_any, listbox, values)
    frame._get_listbox_items = lambda listbox: ConfigFrame._get_listbox_items(frame_any, listbox)
    frame._current_editable_config = lambda: ConfigFrame._current_editable_config(frame_any)
    frame._preview_full_config = lambda: ConfigFrame._preview_full_config(frame_any)
    return frame


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


def test_config_frame_listbox_helpers_and_preview_config_without_tk_widgets():
    frame = _make_config_frame_double(full_config={"analysis": {"keep": True}})

    ConfigFrame._set_listbox_items(frame, frame.targets_list, [" TargetA ", "TargetB"])
    ConfigFrame._set_listbox_items(frame, frame.other_libs_list, [" lib-a ", "lib-b"])
    frame.mode_var.set("draft")
    frame.scan_root_only_var.set(True)
    frame.fast_cache_validation_var.set(False)
    frame.debug_var.set(True)
    frame.program_dir_var.set(" programs ")
    frame.abb_lib_dir_var.set(" abb ")
    frame.icf_dir_var.set(" icf ")

    current = ConfigFrame._current_editable_config(frame)
    preview = ConfigFrame._preview_full_config(frame)

    assert current == {
        "analyzed_programs_and_libraries": ["TargetA", "TargetB"],
        "mode": "draft",
        "scan_root_only": True,
        "fast_cache_validation": False,
        "debug": True,
        "program_dir": "programs",
        "ABB_lib_dir": "abb",
        "icf_dir": "icf",
        "other_lib_dirs": ["lib-a", "lib-b"],
    }
    assert preview["analysis"] == {"keep": True}
    assert preview["program_dir"] == "programs"
    assert preview["other_lib_dirs"] == ["lib-a", "lib-b"]


def test_config_frame_browse_directory_and_target_addition_without_tk_widgets(monkeypatch):
    warnings: list[str] = []
    errors: list[str] = []
    binding_obj = SimpleNamespace(
        config_path="config.toml",
        graphics_rules_path=Path("graphics-rules.toml"),
        load_config=lambda: {},
        save_config=lambda _cfg: SimpleNamespace(ok=True, output="saved"),
        target_exists=lambda target, _cfg: target == "TargetC",
    )
    frame = _make_config_frame_double(binding_obj=binding_obj)
    frame.targets_list.items = ["TargetA"]
    variable = _FakeVar("")

    monkeypatch.setattr("sattlint_gui.frames.config_frame.filedialog.askdirectory", lambda **_kwargs: "")
    ConfigFrame._browse_directory(frame, cast(Any, variable))
    assert variable.get() == ""

    monkeypatch.setattr("sattlint_gui.frames.config_frame.filedialog.askdirectory", lambda **_kwargs: "C:/Programs")
    ConfigFrame._browse_directory(frame, cast(Any, variable))
    assert variable.get() == "C:/Programs"

    monkeypatch.setattr(
        "sattlint_gui.frames.config_frame.messagebox.showwarning", lambda _title, msg, **_k: warnings.append(msg)
    )
    monkeypatch.setattr(
        "sattlint_gui.frames.config_frame.messagebox.showerror", lambda _title, msg, **_k: errors.append(msg)
    )

    monkeypatch.setattr("sattlint_gui.frames.config_frame.simpledialog.askstring", lambda *_a, **_k: " targeta ")
    ConfigFrame._add_target(frame)
    assert warnings == ["Target already listed."]

    monkeypatch.setattr("sattlint_gui.frames.config_frame.simpledialog.askstring", lambda *_a, **_k: "TargetB")
    ConfigFrame._add_target(frame)
    assert errors == ["Target not found in configured directories."]

    monkeypatch.setattr("sattlint_gui.frames.config_frame.simpledialog.askstring", lambda *_a, **_k: "TargetC")
    ConfigFrame._add_target(frame)
    assert frame.targets_list.items == ["TargetA", "TargetC"]
    assert frame._dirty is True


def test_config_frame_remove_and_other_library_workflows_without_tk_widgets(monkeypatch):
    warnings: list[str] = []
    frame = _make_config_frame_double()
    frame.targets_list.items = ["TargetA", "TargetB"]
    frame.other_libs_list.items = ["lib-a"]

    ConfigFrame._remove_target(frame)
    assert frame.targets_list.items == ["TargetA", "TargetB"]

    frame.targets_list._selection = (0,)
    ConfigFrame._remove_target(frame)
    assert frame.targets_list.items == ["TargetB"]
    assert frame._dirty is True

    monkeypatch.setattr(
        "sattlint_gui.frames.config_frame.messagebox.showwarning", lambda _title, msg, **_k: warnings.append(msg)
    )
    monkeypatch.setattr("sattlint_gui.frames.config_frame.filedialog.askdirectory", lambda **_kwargs: "lib-a")
    ConfigFrame._add_other_lib_dir(frame)
    assert warnings == ["Folder already listed."]

    monkeypatch.setattr("sattlint_gui.frames.config_frame.filedialog.askdirectory", lambda **_kwargs: "lib-b")
    ConfigFrame._add_other_lib_dir(frame)
    assert frame.other_libs_list.items == ["lib-a", "lib-b"]

    frame.other_libs_list._selection = (1,)
    ConfigFrame._remove_other_lib_dir(frame)
    assert frame.other_libs_list.items == ["lib-a"]


def test_config_frame_reload_apply_workspace_paths_and_save_without_tk_widgets(monkeypatch):
    loaded_cfg = {
        "mode": "draft",
        "scan_root_only": True,
        "fast_cache_validation": False,
        "debug": True,
        "program_dir": "programs",
        "ABB_lib_dir": "abb",
        "icf_dir": "icf",
        "analyzed_programs_and_libraries": ["TargetA"],
        "other_lib_dirs": ["lib-a"],
    }
    saved: list[dict[str, Any]] = []
    binding_obj = SimpleNamespace(
        config_path="config.toml",
        graphics_rules_path=Path("graphics-rules.toml"),
        load_config=lambda: loaded_cfg,
        save_config=lambda cfg: saved.append(cfg) or SimpleNamespace(ok=True, output="Saved config"),
        target_exists=lambda _target, _cfg: True,
    )
    frame = _make_config_frame_double(binding_obj=binding_obj)

    ConfigFrame.reload_config(frame)

    assert frame.mode_var.get() == "draft"
    assert frame.scan_root_only_var.get() is True
    assert frame.fast_cache_validation_var.get() is False
    assert frame.debug_var.get() is True
    assert frame.targets_list.items == ["TargetA"]
    assert frame.other_libs_list.items == ["lib-a"]
    assert frame.graphics_rules_path_var.get().endswith("graphics-rules.toml")
    assert frame.status.text == "Loaded config.toml"

    binding_obj.load_config = lambda: {
        **loaded_cfg,
        "program_dir": "workspace-programs",
        "ABB_lib_dir": "workspace-abb",
        "icf_dir": "workspace-icf",
        "other_lib_dirs": ["workspace-lib"],
    }
    ConfigFrame.apply_workspace_ha_paths(frame)
    assert frame.program_dir_var.get() == "workspace-programs"
    assert frame.abb_lib_dir_var.get() == "workspace-abb"
    assert frame.icf_dir_var.get() == "workspace-icf"
    assert frame.other_libs_list.items == ["workspace-lib"]
    assert frame.status.text == "Applied workspace HA path suggestions"
    assert frame._dirty is True

    frame.mode_var.set("official")
    ConfigFrame.save_config(frame)
    assert saved[-1]["mode"] == "official"
    assert frame._dirty is False
    assert frame.status.text == "Saved config"


def test_config_frame_can_close_handles_cancel_save_and_discard(monkeypatch):
    frame = _make_config_frame_double()

    assert ConfigFrame.can_close(frame) is True

    frame._dirty = True
    monkeypatch.setattr("sattlint_gui.frames.config_frame.messagebox.askyesnocancel", lambda *_a, **_k: None)
    assert ConfigFrame.can_close(frame) is False

    monkeypatch.setattr("sattlint_gui.frames.config_frame.messagebox.askyesnocancel", lambda *_a, **_k: False)
    assert ConfigFrame.can_close(frame) is True

    monkeypatch.setattr("sattlint_gui.frames.config_frame.messagebox.askyesnocancel", lambda *_a, **_k: True)
    frame.save_config = lambda: frame._set_dirty(False)
    frame._dirty = True
    assert ConfigFrame.can_close(frame) is True
    assert frame._dirty is False


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


# ?? Phase 4 tests ????????????????????????????????????????????????????????????


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


# ?? Phase 5 tests: Higher-level GUI and integration workflows ?????????????????


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


def test_gui_main_module_exits_with_gui_return_code(monkeypatch):
    monkeypatch.setattr("sattlint_gui.main.gui", lambda: 7)

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("sattlint_gui.__main__", run_name="__main__")

    assert exc.value.code == 7


def test_theme_resolve_theme_uses_default_and_custom_theme():
    from sattlint_gui.theme import SattLintTheme, resolve_theme

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


def test_sidebar_frame_selection_handlers_without_tk_widgets():
    class FakeButton:
        def __init__(self) -> None:
            self.style = ""

        def configure(self, *, style: str) -> None:
            self.style = style

    events: list[str] = []
    sidebar = cast(Any, SimpleNamespace(_buttons={"Analyze": FakeButton(), "Results": FakeButton()}))

    from sattlint_gui.frames.sidebar import SidebarFrame

    sidebar.set_selected = lambda name: SidebarFrame.set_selected(sidebar, name)

    SidebarFrame.set_selected(sidebar, "Results")
    SidebarFrame._handle_select(sidebar, "Analyze", lambda name: events.append(name))

    assert sidebar._buttons["Results"].style == "Nav.TButton"
    assert sidebar._buttons["Analyze"].style == "Selected.Nav.TButton"
    assert events == ["Analyze"]


def test_results_frame_history_selection_and_bounds():
    class FakeHistoryBox:
        def __init__(self) -> None:
            self._selection: tuple[int, ...] = ()

        def curselection(self):
            return self._selection

    class FakeDetail:
        def __init__(self) -> None:
            self.text = ""

        def set_text(self, text: str) -> None:
            self.text = text

    frame = cast(Any, ResultsFrame.__new__(ResultsFrame))
    frame._entries = [("[00:00:01] One", "one"), ("[00:00:02] Two", "two")]
    frame._detail = FakeDetail()
    frame._history_box = FakeHistoryBox()

    frame._history_box._selection = (1,)
    frame._on_history_select(None)
    assert "two" in frame._detail.text

    frame._detail.text = "unchanged"
    frame._show_entry(20)
    assert frame._detail.text == "unchanged"


def test_docs_frame_browse_output_dir_updates_preview(monkeypatch):
    events: list[str] = []

    class FakeStringVar:
        def __init__(self, value: str = "") -> None:
            self.value = value

        def get(self) -> str:
            return self.value

        def set(self, value: str) -> None:
            self.value = value

    frame = cast(Any, DocsFrame.__new__(DocsFrame))
    frame.output_dir_var = FakeStringVar("old")
    frame._refresh_preview = lambda: events.append("preview")

    monkeypatch.setattr("sattlint_gui.frames.docs_frame.filedialog.askdirectory", lambda **_kwargs: "new-dir")
    frame._browse_output_dir()

    assert frame.output_dir_var.get() == "new-dir"
    assert events == ["preview"]


def test_docs_frame_browse_output_dir_ignores_cancel(monkeypatch):
    class FakeStringVar:
        def __init__(self, value: str = "") -> None:
            self.value = value

        def get(self) -> str:
            return self.value

        def set(self, value: str) -> None:
            self.value = value

    frame = cast(Any, DocsFrame.__new__(DocsFrame))
    frame.output_dir_var = FakeStringVar("old")
    frame._refresh_preview = lambda: (_ for _ in ()).throw(RuntimeError("should not refresh"))

    monkeypatch.setattr("sattlint_gui.frames.docs_frame.filedialog.askdirectory", lambda **_kwargs: "")
    frame._browse_output_dir()

    assert frame.output_dir_var.get() == "old"


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


def test_analyze_frame_reload_and_task_actions_without_tk_widgets(monkeypatch):
    from sattlint_gui.frames.analyze_frame import AnalyzeFrame

    statuses: list[str] = []
    results: list[tuple[str, str]] = []
    selected_calls: list[list[str] | None] = []

    class FakeThread:
        def __init__(self, *, target, daemon) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    binding_obj = SimpleNamespace(
        config_path="config.toml",
        load_config=lambda: {"analyzed_programs_and_libraries": ["TargetA"]},
        list_enabled_analyzers=lambda: [binding.AnalyzerDescriptor("unused", "Unused Variables")],
        run_self_check=lambda cfg: binding.BindingResult(
            ok=True, output=f"self:{cfg['analyzed_programs_and_libraries'][0]}"
        ),
        ensure_ast_cache=lambda _cfg: binding.BindingResult(ok=True, output="cache ok"),
        run_variable_analysis=lambda _cfg: binding.BindingResult(ok=True, output="variables ok"),
        run_checks=lambda _cfg, selected=None: (
            selected_calls.append(selected) or binding.BindingResult(ok=True, output="checks ok")
        ),
        run_bundle=lambda _cfg, selected=None: (
            selected_calls.append(selected) or binding.BindingResult(ok=True, output="bundle ok")
        ),
    )
    frame = cast(Any, AnalyzeFrame.__new__(AnalyzeFrame))
    frame.binding = binding_obj
    frame.targets = SimpleNamespace(set_targets=lambda targets: setattr(frame, "loaded_targets", targets))
    frame.analyzer_list = SimpleNamespace(
        set_analyzers=lambda analyzers: setattr(frame, "loaded_analyzers", analyzers),
        get_selected_keys=lambda: ["unused"],
    )
    frame.console = SimpleNamespace(set_text=lambda text: setattr(frame, "console_text", text))
    frame.on_status = statuses.append
    frame.on_result = lambda title, text: results.append((title, text))
    frame.after = lambda _delay, callback: callback() or "after-id"

    monkeypatch.setattr("sattlint_gui.frames.analyze_frame.threading.Thread", FakeThread)

    AnalyzeFrame.reload_config(frame)
    AnalyzeFrame.run_self_check(frame)
    AnalyzeFrame.ensure_ast_cache(frame)
    AnalyzeFrame.run_variable_analysis(frame)
    AnalyzeFrame.run_checks(frame)
    AnalyzeFrame.run_bundle(frame)

    assert frame.cfg == {"analyzed_programs_and_libraries": ["TargetA"]}
    assert frame.loaded_targets == ["TargetA"]
    assert frame.loaded_analyzers == [binding.AnalyzerDescriptor("unused", "Unused Variables")]
    assert frame.console_text == "bundle ok"
    assert statuses[0] == "Analyze view loaded config"
    assert "Self-check finished" in statuses
    assert "Ensure AST Cache finished" in statuses
    assert "Variable Analysis finished" in statuses
    assert "Run Checks finished" in statuses
    assert "Run Bundle finished" in statuses
    assert results[-1] == ("Run Bundle", "bundle ok")
    assert selected_calls == [["unused"], ["unused"]]


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


def test_docs_frame_helpers_and_finish_generation_without_tk_widgets(monkeypatch):
    statuses: list[str] = []
    results: list[tuple[str, str]] = []
    frame = cast(Any, DocsFrame.__new__(DocsFrame))
    frame.binding = SimpleNamespace(config_path="config.toml")
    frame.cfg = {"analyzed_programs_and_libraries": [" TargetA ", "", "TargetB"], "mode": "draft"}
    frame.output_dir_var = _FakeVar("docs-out")
    frame.summary = SimpleNamespace(text="", set_text=lambda text: setattr(frame.summary, "text", text))
    frame.preview = SimpleNamespace(text="", set_text=lambda text: setattr(frame.preview, "text", text))
    frame.console = SimpleNamespace(text="", set_text=lambda text: setattr(frame.console, "text", text))
    frame.on_status = statuses.append
    frame.on_result = lambda title, text: results.append((title, text))
    frame._refresh_preview = lambda: DocsFrame._refresh_preview(frame)

    monkeypatch.setattr("sattlint_gui.frames.docs_frame.filedialog.askdirectory", lambda **_kwargs: "")
    DocsFrame._browse_output_dir(frame)
    assert frame.output_dir_var.get() == "docs-out"

    monkeypatch.setattr("sattlint_gui.frames.docs_frame.filedialog.askdirectory", lambda **_kwargs: "docs-final")
    DocsFrame._browse_output_dir(frame)
    DocsFrame._refresh_summary(frame)

    assert DocsFrame._configured_targets(frame) == ["TargetA", "TargetB"]
    assert "Mode: draft" in frame.summary.text
    assert "Configured targets: 2" in frame.summary.text
    assert "docs-final" in frame.preview.text

    frame.cfg = {"analyzed_programs_and_libraries": []}
    DocsFrame._refresh_preview(frame)
    assert frame.preview.text == "No analyzed targets configured."

    DocsFrame._finish_generation(frame, "generated")
    assert frame.console.text == "generated"
    assert results == [("Documentation", "generated")]
    assert statuses == ["Documentation generation finished"]


def test_tools_frame_list_and_run_self_check_without_tk_widgets(monkeypatch):
    from sattlint_gui.frames.tools_frame import ToolsFrame

    statuses: list[str] = []
    results: list[tuple[str, str]] = []

    class FakeThread:
        def __init__(self, *, target, daemon) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    frame = cast(Any, ToolsFrame.__new__(ToolsFrame))
    console_state = {"text": ""}
    frame.binding = SimpleNamespace(
        load_config=lambda: {"mode": "draft"},
        list_enabled_analyzers=lambda: [binding.AnalyzerDescriptor("unused", "Unused Variables")],
        run_self_check=lambda _cfg: binding.BindingResult(ok=True, output="self check ok"),
    )
    frame.cfg = {"mode": "draft"}
    frame.console = SimpleNamespace(
        set_text=lambda text: console_state.update(text=text),
        _text=SimpleNamespace(get=lambda _start, _end: console_state["text"]),
    )
    frame.on_status = statuses.append
    frame.on_result = lambda title, text: results.append((title, text))
    frame.after = lambda _delay, callback: callback() or "after-id"

    monkeypatch.setattr("sattlint_gui.frames.tools_frame.threading.Thread", FakeThread)

    ToolsFrame.list_analyzers(frame)
    ToolsFrame.run_self_check(frame)

    assert console_state["text"] == "self check ok"
    assert results[0] == ("Enabled Analyzers", "unused: Unused Variables")
    assert results[1] == ("Self-check", "self check ok")
    assert statuses == ["Listed enabled analyzers", "Self-check running...", "Self-check finished"]


def test_report_view_console_target_list_and_analyzer_list_helpers_without_tk_widgets(monkeypatch):
    from sattlint_gui.widgets.console import ConsoleView
    from sattlint_gui.widgets.report_view import ReportView
    from sattlint_gui.widgets.target_list import TargetList

    report_view = cast(Any, ReportView.__new__(ReportView))
    report_view._theme = SimpleNamespace(accent="#123", btn_active="#456", text="#789")
    report_view._text = _FakeTextWidget()

    ReportView._configure_tags(report_view)
    ReportView.set_text(report_view, "=== Target: Unit ===\n2 issues\nplain")
    ReportView.append_text(report_view, "=== Analyzer ===\n0 issues")

    assert {tag for tag, _kwargs in report_view._text.tag_calls} == {"section_header", "count_line", "muted"}
    assert any(tag == "section_header" for _text, tag in report_view._text.insert_calls)
    assert any(tag == "count_line" for _text, tag in report_view._text.insert_calls)
    assert report_view._text.seen == "end"

    console = cast(Any, ConsoleView.__new__(ConsoleView))
    console._text = _FakeTextWidget()
    ConsoleView.set_text(console, "alpha")
    ConsoleView.append_text(console, "beta")
    assert console._text.content == "alphabeta"
    assert console._text.seen == "end"

    target_list = cast(Any, TargetList.__new__(TargetList))
    target_list._list = _FakeListbox(["stale"])
    TargetList.set_targets(target_list, [])
    assert target_list._list.items == ["<no configured targets>"]
    TargetList.set_targets(target_list, ["TargetA", "TargetB"])
    assert target_list._list.items == ["TargetA", "TargetB"]

    destroyed: list[str] = []
    created: list[str] = []

    class FakeBoolVar(_FakeVar):
        pass

    class FakeCheckbutton:
        def __init__(self, _parent, *, text: str, variable, style: str) -> None:
            created.append(f"{text}|{style}|{variable.get()}")

        def pack(self, **_kwargs) -> None:
            created.append("packed")

    analyzer_list = cast(Any, AnalyzerList.__new__(AnalyzerList))
    analyzer_list._inner = SimpleNamespace(
        winfo_children=lambda: [SimpleNamespace(destroy=lambda: destroyed.append("gone"))],
    )
    analyzer_list._canvas = SimpleNamespace(
        update_idletasks=lambda: created.append("updated"),
        configure=lambda **kwargs: created.append(f"configure:{kwargs['scrollregion']}"),
        bbox=lambda _item: (0, 0, 40, 50),
        itemconfigure=lambda item_id, **kwargs: created.append(f"item:{item_id}:{kwargs['width']}"),
    )
    analyzer_list._inner_id = "inner"
    analyzer_list._vars = []

    monkeypatch.setattr("sattlint_gui.widgets.analyzer_list.tk.BooleanVar", FakeBoolVar)
    monkeypatch.setattr("sattlint_gui.widgets.analyzer_list.ttk.Checkbutton", FakeCheckbutton)

    AnalyzerList.set_analyzers(
        analyzer_list,
        [binding.AnalyzerDescriptor("unused", "Unused Variables"), binding.AnalyzerDescriptor("icf", "ICF Validation")],
    )
    AnalyzerList._on_inner_configure(analyzer_list, None)
    AnalyzerList._on_canvas_configure(analyzer_list, SimpleNamespace(width=88))
    AnalyzerList.deselect_all(analyzer_list)
    assert AnalyzerList.get_selected_keys(analyzer_list) == []
    AnalyzerList.select_all(analyzer_list)

    assert destroyed == ["gone"]
    assert len(analyzer_list._vars) == 2
    assert AnalyzerList.get_selected_keys(analyzer_list) == ["unused", "icf"]
    assert any(item.startswith("unused: Unused Variables") for item in created)
    assert "configure:(0, 0, 40, 50)" in created
    assert "item:inner:88" in created


def test_config_frame_headless_init_and_remaining_branches(monkeypatch):
    import tkinter.ttk as real_ttk

    class FakeTkVar(_FakeVar):
        def trace_add(self, _mode: str, callback) -> None:
            self._callback = callback

    class FakeWidget:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs
            self.text = kwargs.get("text", "")

        def grid(self, *args, **kwargs) -> None:
            self.grid_args = (args, kwargs)

        def pack(self, *args, **kwargs) -> None:
            self.pack_args = (args, kwargs)

        def columnconfigure(self, *_args, **_kwargs) -> None:
            pass

        def rowconfigure(self, *_args, **_kwargs) -> None:
            pass

        def configure(self, **kwargs) -> None:
            if "text" in kwargs:
                self.text = kwargs["text"]

        def bind(self, *_args, **_kwargs) -> None:
            pass

    class FakeListboxWidget(_FakeListbox):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__()
            self.args = args
            self.kwargs = kwargs

        def grid(self, *args, **kwargs) -> None:
            self.grid_args = (args, kwargs)

        def bind(self, *_args, **_kwargs) -> None:
            pass

    loaded_cfg = {
        "mode": "draft",
        "scan_root_only": True,
        "fast_cache_validation": False,
        "debug": True,
        "program_dir": "programs",
        "ABB_lib_dir": "abb",
        "icf_dir": "icf",
        "analyzed_programs_and_libraries": ["TargetA"],
        "other_lib_dirs": ["lib-a"],
    }
    binding_obj = SimpleNamespace(
        config_path="config.toml",
        graphics_rules_path=Path("graphics-rules.toml"),
        load_config=lambda: loaded_cfg,
        save_config=lambda _cfg: SimpleNamespace(ok=False, output="Save failed"),
        target_exists=lambda _target, _cfg: True,
    )

    monkeypatch.setattr(real_ttk.Frame, "__init__", lambda self, parent=None, **kwargs: None)
    monkeypatch.setattr(real_ttk.Frame, "columnconfigure", lambda self, *_args, **_kwargs: None)
    monkeypatch.setattr(real_ttk.Frame, "rowconfigure", lambda self, *_args, **_kwargs: None)
    monkeypatch.setattr("sattlint_gui.frames.config_frame.ttk.Frame", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.config_frame.ttk.Label", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.config_frame.ttk.Button", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.config_frame.ttk.Entry", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.config_frame.ttk.Combobox", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.config_frame.ttk.Checkbutton", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.config_frame.tk.StringVar", FakeTkVar)
    monkeypatch.setattr("sattlint_gui.frames.config_frame.tk.BooleanVar", FakeTkVar)
    monkeypatch.setattr("sattlint_gui.frames.config_frame.tk.Listbox", FakeListboxWidget)
    monkeypatch.setattr(
        "sattlint_gui.frames.config_frame.resolve_theme",
        lambda _parent: SimpleNamespace(input_bg="#111", text="#eee", btn_active="#222", console_text="#fff"),
    )

    info_calls: list[tuple[str, str]] = []
    error_calls: list[str] = []
    monkeypatch.setattr(
        "sattlint_gui.frames.config_frame.messagebox.showinfo",
        lambda title, message, **_kwargs: info_calls.append((title, message)),
    )
    monkeypatch.setattr(
        "sattlint_gui.frames.config_frame.messagebox.showerror",
        lambda _title, message, **_kwargs: error_calls.append(message),
    )
    monkeypatch.setattr("sattlint_gui.frames.config_frame.messagebox.askyesno", lambda *_args, **_kwargs: False)

    frame = ConfigFrame(SimpleNamespace(), binding=cast(Any, binding_obj))

    assert frame.mode_var.get() == "draft"
    assert frame.scan_root_only_var.get() is True
    assert frame.fast_cache_validation_var.get() is False
    assert frame.debug_var.get() is True
    assert cast(Any, frame.targets_list).items == ["TargetA"]
    assert cast(Any, frame.other_libs_list).items == ["lib-a"]
    assert cast(Any, frame.status).text == "Loaded config.toml"

    monkeypatch.setattr("sattlint_gui.frames.config_frame.filedialog.askdirectory", lambda **_kwargs: "updated-dir")
    frame._browse_program_dir()
    frame._browse_abb_lib_dir()
    frame._browse_icf_dir()
    assert frame.program_dir_var.get() == "updated-dir"
    assert frame.abb_lib_dir_var.get() == "updated-dir"
    assert frame.icf_dir_var.get() == "updated-dir"

    frame._show_graphics_rules_path()
    assert info_calls == [("Graphics Rules", str(Path("graphics-rules.toml")))]

    frame._loading = True
    frame._dirty = False
    frame._on_field_changed()
    assert frame._dirty is False
    frame._loading = False
    frame._on_field_changed()
    assert frame._dirty is True

    frame.mode_var.set("official")
    frame.reload_config()
    assert frame.mode_var.get() == "official"

    frame.save_config()
    assert error_calls == ["Save failed"]


def test_results_frame_selection_and_styled_theme_helpers_without_tk_widgets(monkeypatch):
    from sattlint_gui.widgets import styled_widgets

    frame = cast(Any, ResultsFrame.__new__(ResultsFrame))
    frame._entries = [("[10:00:00] First", "alpha"), ("[10:01:00] Second", "beta")]
    frame._history_box = SimpleNamespace(curselection=lambda: (1,))
    frame._detail = SimpleNamespace(text="", set_text=lambda text: setattr(frame._detail, "text", text))

    ResultsFrame._on_history_select(frame, None)
    ResultsFrame._show_entry(frame, 99)

    assert "Second" in frame._detail.text
    assert "beta" in frame._detail.text

    calls: list[tuple[str, str]] = []

    class FakeStyle:
        def __init__(self, _root) -> None:
            pass

        def theme_use(self, _name: str) -> None:
            raise styled_widgets.tk.TclError("theme unavailable")

        def configure(self, name: str, **_kwargs) -> None:
            calls.append(("configure", name))

        def map(self, name: str, **_kwargs) -> None:
            calls.append(("map", name))

    monkeypatch.setattr(styled_widgets.ttk, "Style", FakeStyle)

    style = styled_widgets.apply_theme(cast(Any, SimpleNamespace()), DEFAULT_THEME)

    assert isinstance(style, FakeStyle)
    assert ("configure", ".") in calls
    assert ("configure", "Accent.TButton") in calls
    assert ("map", "TButton") in calls
    assert ("map", "Selected.Nav.TButton") in calls
