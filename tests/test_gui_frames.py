from types import SimpleNamespace
from typing import Any, cast

import pytest

pytest.importorskip("tkinter", exc_type=ImportError)

from sattlint_gui import binding
from sattlint_gui.frames.analyze_frame import AnalyzeFrame
from sattlint_gui.frames.docs_frame import DocsFrame
from sattlint_gui.frames.results_frame import ResultsFrame
from sattlint_gui.frames.sidebar import SidebarFrame
from tests._gui_test_support import _FakeVar


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


def test_docs_frame_refresh_preview_shows_output_paths():
    class FakeReportView:
        def __init__(self) -> None:
            self.text = ""

        def set_text(self, text: str) -> None:
            self.text = text

    frame = cast(Any, DocsFrame.__new__(DocsFrame))
    frame.cfg = {"analyzed_programs_and_libraries": ["TargetA", "TargetB"]}
    frame.preview = FakeReportView()
    frame.output_dir_var = SimpleNamespace(get=lambda: "custom-out")

    frame._refresh_preview()

    assert "TargetA_FS.docx" in frame.preview.text
    assert "TargetB_FS.docx" in frame.preview.text
    assert "custom-out" in frame.preview.text


def test_results_frame_publish_result_adds_timestamped_entry():
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
    assert "Test Result" in frame._entries[0][0]
    assert frame._entries[0][1] == "test output content"
    assert len(frame._history_box.items) == 1
    assert "Test Result" in frame._history_box.items[0]


def test_analyze_frame_run_bundle_combines_va_and_checks_output():
    call_args = {}

    class FakeBinding(binding.SattLintBinding):
        def run_bundle(self, cfg, selected_keys=None):
            call_args["cfg"] = cfg
            call_args["selected_keys"] = selected_keys
            return binding.BindingResult(ok=True, output="[Variable Analysis]\nok\n\n[Checks]\nok")

    frame = cast(Any, AnalyzeFrame.__new__(AnalyzeFrame))
    frame.binding = FakeBinding()
    frame.cfg = {"mode": "draft"}

    result = frame.binding.run_bundle(frame.cfg, ["unused", "icf"])

    assert result.ok is True
    assert "[Variable Analysis]" in result.output
    assert "[Checks]" in result.output
    assert call_args == {"cfg": {"mode": "draft"}, "selected_keys": ["unused", "icf"]}


def test_sidebar_frame_selection_handlers_without_tk_widgets():
    class FakeButton:
        def __init__(self) -> None:
            self.style = ""

        def configure(self, *, style: str) -> None:
            self.style = style

    events: list[str] = []
    sidebar = cast(Any, SimpleNamespace(_buttons={"Analyze": FakeButton(), "Results": FakeButton()}))
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


def test_analyze_frame_reload_and_task_actions_without_tk_widgets(monkeypatch):
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
