# pyright: reportArgumentType=false, reportMissingParameterType=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnnecessaryCast=false

import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from typing import Any, cast

import pytest

pytest.importorskip("tkinter", exc_type=ImportError)

from sattlint_gui import binding
from sattlint_gui.widgets.analyzer_list import AnalyzerList
from sattlint_gui.widgets.report_view import _ISSUE_COUNT_RE, _TARGET_HEADER_RE, ReportView
from sattlint_gui.widgets.target_list import TargetList
from tests._gui_test_support import _FakeListbox, _FakeTextWidget, _FakeVar


def _real_tk_root() -> tk.Tk:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"real Tk root unavailable: {exc}")
    root.withdraw()
    return root


def test_analyzer_list_selection():
    class FakeBoolVar:
        def __init__(self, value: bool = True) -> None:
            self._value = value

        def get(self) -> bool:
            return self._value

        def set(self, value: bool) -> None:
            self._value = value

    analyzer_list = cast(Any, AnalyzerList.__new__(AnalyzerList))
    analyzer_list._vars = [
        (FakeBoolVar(True), "unused"),
        (FakeBoolVar(True), "icf"),
        (FakeBoolVar(True), "graphics"),
    ]

    assert analyzer_list.get_selected_keys() == ["unused", "icf", "graphics"]

    analyzer_list._vars[1][0].set(False)
    assert analyzer_list.get_selected_keys() == ["unused", "graphics"]

    analyzer_list.select_all()
    assert analyzer_list.get_selected_keys() == ["unused", "icf", "graphics"]

    analyzer_list.deselect_all()
    assert analyzer_list.get_selected_keys() == []


def test_target_and_analyzer_widgets_smoke_with_real_tk() -> None:
    root = _real_tk_root()
    try:
        target_list = TargetList(root, title="Configured Targets")
        target_list.set_targets(["TargetA", "TargetB"])
        analyzer_list = AnalyzerList(root, title="Analyzers")
        analyzer_list.set_analyzers(
            [
                binding.AnalyzerDescriptor("unused", "Unused Variables"),
                binding.AnalyzerDescriptor("icf", "ICF Validation"),
            ]
        )
        root.update_idletasks()

        assert target_list._list.get(0, tk.END) == ("TargetA", "TargetB")
        assert analyzer_list.get_selected_keys() == ["unused", "icf"]

        header = next(child for child in analyzer_list.winfo_children() if isinstance(child, ttk.Frame))
        buttons = [child for child in header.winfo_children() if isinstance(child, ttk.Button)]
        assert len(buttons) == 2

        buttons[1].invoke()
        assert analyzer_list.get_selected_keys() == []

        buttons[0].invoke()
        assert analyzer_list.get_selected_keys() == ["unused", "icf"]
    finally:
        root.destroy()


def test_analyzer_list_headless_init(monkeypatch):
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

    scrollbars: list[Any] = []

    class FakeScrollbar(FakeWidget):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            scrollbars.append(self)

        def set(self, *_args) -> None:
            return None

    class FakeCanvas:
        def __init__(self, parent, **kwargs) -> None:
            self.parent = parent
            self.kwargs = kwargs
            self.configure_calls: list[dict[str, Any]] = []
            self.grid_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
            self.bind_calls: list[tuple[str, Any]] = []
            self.create_window_calls: list[tuple[tuple[int, int], Any, str]] = []

        def yview(self, *_args) -> None:
            return None

        def configure(self, **kwargs) -> None:
            self.configure_calls.append(kwargs)

        def grid(self, *args, **kwargs) -> None:
            self.grid_calls.append((args, kwargs))

        def create_window(self, coords: tuple[int, int], *, window, anchor: str) -> str:
            self.create_window_calls.append((coords, window, anchor))
            return "inner-window"

        def bind(self, event: str, callback: Any) -> None:
            self.bind_calls.append((event, callback))

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
    monkeypatch.setattr("sattlint_gui.widgets.analyzer_list.ttk.Frame", FakeWidget)
    monkeypatch.setattr("sattlint_gui.widgets.analyzer_list.ttk.Label", FakeWidget)
    monkeypatch.setattr("sattlint_gui.widgets.analyzer_list.ttk.Button", FakeWidget)
    monkeypatch.setattr("sattlint_gui.widgets.analyzer_list.ttk.Scrollbar", FakeScrollbar)
    monkeypatch.setattr("sattlint_gui.widgets.analyzer_list.tk.Canvas", FakeCanvas)
    monkeypatch.setattr(
        "sattlint_gui.widgets.analyzer_list.resolve_theme",
        lambda _parent: SimpleNamespace(bg_panel="#123456"),
    )

    parent = SimpleNamespace()
    analyzer_list = cast(Any, AnalyzerList(parent, title="Analyzers"))
    canvas = cast(Any, analyzer_list._canvas)
    inner = cast(Any, analyzer_list._inner)

    assert analyzer_list._frame_init == (parent, {"style": "Panel.TFrame", "padding": 12})
    assert analyzer_list._columnconfigure_calls == [(0, 1)]
    assert analyzer_list._rowconfigure_calls == [(1, 1)]
    assert canvas.kwargs == {"bg": "#123456", "highlightthickness": 0}
    assert canvas.configure_calls == [{"yscrollcommand": scrollbars[0].set}]
    assert analyzer_list._inner_id == "inner-window"
    assert canvas.create_window_calls == [((0, 0), analyzer_list._inner, "nw")]
    assert inner.bind_calls[0][0] == "<Configure>"
    assert canvas.bind_calls[0][0] == "<Configure>"
    assert analyzer_list._vars == []


def test_target_list_headless_init(monkeypatch):
    import tkinter.ttk as real_ttk

    class FakeWidget:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs
            self.grid_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

        def grid(self, *args, **kwargs) -> None:
            self.grid_calls.append((args, kwargs))

    class FakeListboxWidget(_FakeListbox):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__()
            self.args = args
            self.kwargs = kwargs
            self.grid_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

        def grid(self, *args, **kwargs) -> None:
            self.grid_calls.append((args, kwargs))

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
    monkeypatch.setattr("sattlint_gui.widgets.target_list.ttk.Label", FakeWidget)
    monkeypatch.setattr("sattlint_gui.widgets.target_list.tk.Listbox", FakeListboxWidget)
    monkeypatch.setattr(
        "sattlint_gui.widgets.target_list.resolve_theme",
        lambda _parent: SimpleNamespace(
            input_bg="#111111",
            text="#eeeeee",
            btn_active="#222222",
            console_text="#ffffff",
        ),
    )

    parent = SimpleNamespace()
    target_list = cast(Any, TargetList(parent, title="Configured Targets"))

    assert target_list._frame_init == (parent, {"style": "Panel.TFrame", "padding": 12})
    assert target_list._columnconfigure_calls == [(0, 1)]
    assert target_list._rowconfigure_calls == [(1, 1)]
    assert target_list._list.kwargs == {
        "relief": "flat",
        "bg": "#111111",
        "fg": "#eeeeee",
        "selectbackground": "#222222",
        "selectforeground": "#ffffff",
    }


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


def test_report_view_console_target_list_and_analyzer_list_helpers_without_tk_widgets(monkeypatch):
    from sattlint_gui.widgets.console import ConsoleView

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
