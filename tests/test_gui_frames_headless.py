from types import SimpleNamespace
from typing import Any, cast

import pytest

pytest.importorskip("tkinter", exc_type=ImportError)

from sattlint_gui import binding
from sattlint_gui.frames.analyze_frame import AnalyzeFrame
from sattlint_gui.frames.docs_frame import DocsFrame
from sattlint_gui.frames.results_frame import ResultsFrame
from sattlint_gui.frames.sidebar import SidebarFrame
from sattlint_gui.frames.tools_frame import ToolsFrame
from sattlint_gui.theme import DEFAULT_THEME


def test_tools_frame_list_and_run_self_check_without_tk_widgets(monkeypatch):
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


def test_analyze_frame_headless_init(monkeypatch):
    import tkinter.ttk as real_ttk

    class FakeWidget:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs
            self.grid_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
            self.columnconfigure_calls: list[tuple[int, int]] = []
            self.rowconfigure_calls: list[tuple[int, int]] = []

        def grid(self, *args, **kwargs) -> None:
            self.grid_calls.append((args, kwargs))

        def columnconfigure(self, index: int, weight: int) -> None:
            self.columnconfigure_calls.append((index, weight))

        def rowconfigure(self, index: int, weight: int) -> None:
            self.rowconfigure_calls.append((index, weight))

    class FakeTargetList(FakeWidget):
        def set_targets(self, targets: list[str]) -> None:
            self.targets = targets

    class FakeAnalyzerList(FakeWidget):
        def set_analyzers(self, analyzers: list[Any]) -> None:
            self.analyzers = analyzers

    class FakeConsole(FakeWidget):
        def set_text(self, text: str) -> None:
            self.text = text

    def fake_frame_init(self, parent=None, **kwargs) -> None:
        self._frame_init = (parent, kwargs)
        self._columnconfigure_calls = []
        self._rowconfigure_calls = []

    def fake_frame_columnconfigure(self, index: int, weight: int) -> None:
        self._columnconfigure_calls.append((index, weight))

    def fake_frame_rowconfigure(self, index: int, weight: int) -> None:
        self._rowconfigure_calls.append((index, weight))

    monkeypatch.setattr(real_ttk.Frame, "__init__", fake_frame_init)
    monkeypatch.setattr(real_ttk.Frame, "columnconfigure", fake_frame_columnconfigure)
    monkeypatch.setattr(real_ttk.Frame, "rowconfigure", fake_frame_rowconfigure)
    monkeypatch.setattr("sattlint_gui.frames.analyze_frame.ttk.Frame", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.analyze_frame.ttk.Button", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.analyze_frame.TargetList", FakeTargetList)
    monkeypatch.setattr("sattlint_gui.frames.analyze_frame.AnalyzerList", FakeAnalyzerList)
    monkeypatch.setattr("sattlint_gui.frames.analyze_frame.ConsoleView", FakeConsole)

    parent = SimpleNamespace()
    binding_obj = SimpleNamespace(
        config_path="config.toml",
        load_config=lambda: {"analyzed_programs_and_libraries": ["TargetA"]},
        list_enabled_analyzers=lambda: [binding.AnalyzerDescriptor("unused", "Unused Variables")],
    )
    statuses: list[str] = []
    frame = cast(Any, AnalyzeFrame(parent, binding=cast(Any, binding_obj), on_status=statuses.append))

    assert frame._frame_init == (parent, {"style": "Content.TFrame"})
    assert frame._columnconfigure_calls == [(1, 1)]
    assert frame._rowconfigure_calls == [(1, 1), (2, 1)]
    assert frame.targets.targets == ["TargetA"]
    assert frame.analyzer_list.analyzers == [binding.AnalyzerDescriptor("unused", "Unused Variables")]
    assert frame.console.text == "Loaded config from config.toml"
    assert statuses == ["Analyze view loaded config"]


def test_docs_frame_headless_init(monkeypatch):
    import tkinter.ttk as real_ttk

    class FakeWidget:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs
            self.grid_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
            self.columnconfigure_calls: list[tuple[int, int]] = []
            self.rowconfigure_calls: list[tuple[int, int]] = []

        def grid(self, *args, **kwargs) -> None:
            self.grid_calls.append((args, kwargs))

        def columnconfigure(self, index: int, weight: int) -> None:
            self.columnconfigure_calls.append((index, weight))

        def rowconfigure(self, index: int, weight: int) -> None:
            self.rowconfigure_calls.append((index, weight))

    class FakeStringVar:
        def __init__(self, value: str = "") -> None:
            self.value = value

        def get(self) -> str:
            return self.value

        def set(self, value: str) -> None:
            self.value = value

    class FakeReportView(FakeWidget):
        def __init__(self, *args, title: str, **kwargs) -> None:
            super().__init__(*args, title=title, **kwargs)
            self.title = title
            self.text = ""

        def set_text(self, text: str) -> None:
            self.text = text

    class FakeConsole(FakeWidget):
        def __init__(self, *args, title: str, **kwargs) -> None:
            super().__init__(*args, title=title, **kwargs)
            self.title = title
            self.text = ""

        def set_text(self, text: str) -> None:
            self.text = text

    def fake_frame_init(self, parent=None, **kwargs) -> None:
        self._frame_init = (parent, kwargs)
        self._columnconfigure_calls = []
        self._rowconfigure_calls = []

    def fake_frame_columnconfigure(self, index: int, weight: int) -> None:
        self._columnconfigure_calls.append((index, weight))

    def fake_frame_rowconfigure(self, index: int, weight: int) -> None:
        self._rowconfigure_calls.append((index, weight))

    monkeypatch.setattr(real_ttk.Frame, "__init__", fake_frame_init)
    monkeypatch.setattr(real_ttk.Frame, "columnconfigure", fake_frame_columnconfigure)
    monkeypatch.setattr(real_ttk.Frame, "rowconfigure", fake_frame_rowconfigure)
    monkeypatch.setattr("sattlint_gui.frames.docs_frame.ttk.Frame", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.docs_frame.ttk.Button", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.docs_frame.ttk.Entry", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.docs_frame.tk.StringVar", FakeStringVar)
    monkeypatch.setattr("sattlint_gui.frames.docs_frame.ReportView", FakeReportView)
    monkeypatch.setattr("sattlint_gui.frames.docs_frame.ConsoleView", FakeConsole)

    parent = SimpleNamespace()
    binding_obj = SimpleNamespace(
        config_path="config.toml",
        load_config=lambda: {"mode": "draft", "analyzed_programs_and_libraries": ["TargetA", "TargetB"]},
    )
    statuses: list[str] = []
    frame = cast(Any, DocsFrame(parent, binding=cast(Any, binding_obj), on_status=statuses.append))

    assert frame._frame_init == (parent, {"style": "Content.TFrame"})
    assert frame._columnconfigure_calls == [(0, 1)]
    assert frame._rowconfigure_calls == [(2, 1), (3, 1)]
    assert "Configured targets: 2" in frame.summary.text
    assert "TargetA_FS.docx" in frame.preview.text
    assert frame.console.text == "Loaded config from config.toml"
    assert statuses == ["Documentation view loaded config"]


def test_results_frame_headless_init(monkeypatch):
    import tkinter.ttk as real_ttk

    class FakeWidget:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs
            self.grid_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
            self.columnconfigure_calls: list[tuple[int, int]] = []
            self.rowconfigure_calls: list[tuple[int, int]] = []
            self.bind_calls: list[tuple[str, Any]] = []

        def grid(self, *args, **kwargs) -> None:
            self.grid_calls.append((args, kwargs))

        def columnconfigure(self, index: int, weight: int) -> None:
            self.columnconfigure_calls.append((index, weight))

        def rowconfigure(self, index: int, weight: int) -> None:
            self.rowconfigure_calls.append((index, weight))

        def bind(self, event: str, callback: Any) -> None:
            self.bind_calls.append((event, callback))

    class FakeScrollbar(FakeWidget):
        def set(self, *_args) -> None:
            return None

    class FakeListbox(FakeWidget):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.configure_calls: list[dict[str, Any]] = []

        def yview(self, *_args) -> None:
            return None

        def configure(self, **kwargs) -> None:
            self.configure_calls.append(kwargs)

    class FakeReportView(FakeWidget):
        def __init__(self, *args, title: str, **kwargs) -> None:
            super().__init__(*args, title=title, **kwargs)
            self.text = ""

        def set_text(self, text: str) -> None:
            self.text = text

    def fake_frame_init(self, parent=None, **kwargs) -> None:
        self._frame_init = (parent, kwargs)
        self._columnconfigure_calls = []
        self._rowconfigure_calls = []

    def fake_frame_columnconfigure(self, index: int, weight: int) -> None:
        self._columnconfigure_calls.append((index, weight))

    def fake_frame_rowconfigure(self, index: int, weight: int) -> None:
        self._rowconfigure_calls.append((index, weight))

    monkeypatch.setattr(real_ttk.Frame, "__init__", fake_frame_init)
    monkeypatch.setattr(real_ttk.Frame, "columnconfigure", fake_frame_columnconfigure)
    monkeypatch.setattr(real_ttk.Frame, "rowconfigure", fake_frame_rowconfigure)
    monkeypatch.setattr("sattlint_gui.frames.results_frame.ttk.Frame", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.results_frame.ttk.Label", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.results_frame.ttk.Button", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.results_frame.ttk.Scrollbar", FakeScrollbar)
    monkeypatch.setattr("sattlint_gui.frames.results_frame.tk.Listbox", FakeListbox)
    monkeypatch.setattr("sattlint_gui.frames.results_frame.ReportView", FakeReportView)
    monkeypatch.setattr(
        "sattlint_gui.frames.results_frame.resolve_theme",
        lambda _parent: SimpleNamespace(
            input_bg="#111111", text="#eeeeee", btn_active="#222222", console_text="#ffffff"
        ),
    )

    parent = SimpleNamespace()
    frame = cast(Any, ResultsFrame(parent))

    assert frame._frame_init == (parent, {"style": "Content.TFrame"})
    assert frame._columnconfigure_calls == [(0, 0), (1, 1)]
    assert frame._rowconfigure_calls == [(0, 1)]
    assert frame._history_box.kwargs["exportselection"] is False
    assert frame._detail.text == "Run an action from Analyze, Docs, or Tools to collect output here."
    assert frame._entries == []


def test_sidebar_frame_headless_init(monkeypatch):
    import tkinter.ttk as real_ttk

    class FakeWidget:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs
            self.grid_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

        def grid(self, *args, **kwargs) -> None:
            self.grid_calls.append((args, kwargs))

        def configure(self, **kwargs: Any) -> None:
            self.kwargs.update(kwargs)

    def fake_frame_init(self, parent=None, **kwargs) -> None:
        self._frame_init = (parent, kwargs)
        self._columnconfigure_calls = []

    def fake_frame_columnconfigure(self, index: int, weight: int) -> None:
        self._columnconfigure_calls.append((index, weight))

    monkeypatch.setattr(real_ttk.Frame, "__init__", fake_frame_init)
    monkeypatch.setattr(real_ttk.Frame, "columnconfigure", fake_frame_columnconfigure)
    monkeypatch.setattr("sattlint_gui.frames.sidebar.ttk.Label", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.sidebar.ttk.Button", FakeWidget)

    parent = SimpleNamespace()
    selected: list[str] = []
    frame = cast(Any, SidebarFrame(parent, items=("Analyze", "Results"), on_select=selected.append))

    assert frame._frame_init == (parent, {"style": "Sidebar.TFrame", "padding": 16})
    assert frame._columnconfigure_calls == [(0, 1)]
    assert set(frame._buttons) == {"Analyze", "Results"}
    assert frame._buttons["Analyze"].kwargs["style"] == "Nav.TButton"


def test_tools_frame_headless_init(monkeypatch):
    import tkinter.ttk as real_ttk

    class FakeWidget:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs
            self.grid_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
            self.pack_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
            self.columnconfigure_calls: list[tuple[int, int]] = []
            self.rowconfigure_calls: list[tuple[int, int]] = []

        def grid(self, *args, **kwargs) -> None:
            self.grid_calls.append((args, kwargs))

        def pack(self, *args, **kwargs) -> None:
            self.pack_calls.append((args, kwargs))

        def columnconfigure(self, index: int, weight: int) -> None:
            self.columnconfigure_calls.append((index, weight))

        def rowconfigure(self, index: int, weight: int) -> None:
            self.rowconfigure_calls.append((index, weight))

    class FakeConsole(FakeWidget):
        def __init__(self, *args, title: str, **kwargs) -> None:
            super().__init__(*args, title=title, **kwargs)
            self.text = ""
            self._text = SimpleNamespace(get=lambda _start, _end: self.text)

        def set_text(self, text: str) -> None:
            self.text = text

    def fake_frame_init(self, parent=None, **kwargs) -> None:
        self._frame_init = (parent, kwargs)
        self._columnconfigure_calls = []
        self._rowconfigure_calls = []

    def fake_frame_columnconfigure(self, index: int, weight: int) -> None:
        self._columnconfigure_calls.append((index, weight))

    def fake_frame_rowconfigure(self, index: int, weight: int) -> None:
        self._rowconfigure_calls.append((index, weight))

    monkeypatch.setattr(real_ttk.Frame, "__init__", fake_frame_init)
    monkeypatch.setattr(real_ttk.Frame, "columnconfigure", fake_frame_columnconfigure)
    monkeypatch.setattr(real_ttk.Frame, "rowconfigure", fake_frame_rowconfigure)
    monkeypatch.setattr("sattlint_gui.frames.tools_frame.ttk.Frame", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.tools_frame.ttk.Button", FakeWidget)
    monkeypatch.setattr("sattlint_gui.frames.tools_frame.ConsoleView", FakeConsole)

    parent = SimpleNamespace()
    results: list[tuple[str, str]] = []
    statuses: list[str] = []
    frame = cast(
        Any,
        ToolsFrame(
            parent,
            binding=cast(
                Any,
                SimpleNamespace(
                    load_config=lambda: {"mode": "draft"},
                    list_enabled_analyzers=lambda: [binding.AnalyzerDescriptor("unused", "Unused Variables")],
                ),
            ),
            on_result=lambda title, text: results.append((title, text)),
            on_status=statuses.append,
        ),
    )

    assert frame._frame_init == (parent, {"style": "Content.TFrame"})
    assert frame._columnconfigure_calls == [(0, 1)]
    assert frame._rowconfigure_calls == [(1, 1)]
    assert frame.console.text == "unused: Unused Variables"
    assert results == [("Enabled Analyzers", "unused: Unused Variables")]
    assert statuses == ["Listed enabled analyzers"]
