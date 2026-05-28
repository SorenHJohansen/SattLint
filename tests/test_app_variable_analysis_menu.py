import builtins
from types import SimpleNamespace

import pytest

from sattlint import app

from ._app_menus_support import make_input


@pytest.fixture
def noop_screen(monkeypatch):
    monkeypatch.setattr(app, "clear_screen", lambda: None)
    monkeypatch.setattr(app, "pause", lambda: None)


def test_variable_analysis_menu_all_options(noop_screen, monkeypatch):
    calls: list[str] = []

    def record(name: str) -> None:
        calls.append(name)

    monkeypatch.setattr(app, "_run_checks", lambda *_: record("checks"))
    monkeypatch.setattr(app, "run_variable_analysis", lambda *_: record("variable"))
    monkeypatch.setattr(app, "run_datatype_usage_analysis", lambda *_: record("datatype"))
    monkeypatch.setattr(app, "run_debug_variable_usage", lambda *_: record("debug"))
    monkeypatch.setattr(app, "run_module_localvar_analysis", lambda *_: record("module"))
    monkeypatch.setattr(app, "run_module_duplicates_analysis", lambda *_: record("module-compare"))
    monkeypatch.setattr(app, "run_module_find_by_name", lambda *_: record("module-find"))
    monkeypatch.setattr(app, "run_module_tree_debug", lambda *_: record("module-tree"))
    monkeypatch.setattr(app, "run_mms_interface_analysis", lambda *_: record("mms"))
    monkeypatch.setattr(app, "run_icf_validation", lambda *_: record("icf"))
    monkeypatch.setattr(app, "run_icf_formatter", lambda *_: record("icf-format"))
    monkeypatch.setattr(app, "run_comment_code_analysis", lambda *_: record("comment"))
    monkeypatch.setattr(
        app,
        "_get_enabled_analyzers",
        lambda: [
            SimpleNamespace(
                key="variables",
                name="Variable issues",
                description="Unused and never-read variables",
            )
        ],
    )

    inputs = [
        "1",
        "2",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
        "17",
        "18",
        "19",
        "20",
        "21",
        "22",
        "23",
        "24",
        "b",
        "3",
        "1",
        "2",
        "3",
        "b",
        "4",
        "1",
        "2",
        "3",
        "b",
        "5",
        "1",
        "b",
        "6",
        "1",
        "2",
        "b",
        "7",
        "1",
        "2",
        "3",
        "b",
        "b",
    ]
    monkeypatch.setattr(builtins, "input", make_input(inputs))

    app.analysis_menu(app.DEFAULT_CONFIG.copy())

    assert calls.count("variable") == 22
    assert calls.count("checks") == 3
    assert "datatype" in calls
    assert "debug" in calls
    assert "module" in calls
    assert "module-compare" in calls
    assert "module-find" in calls
    assert "module-tree" in calls
    assert "mms" in calls
    assert "icf" in calls
    assert "icf-format" in calls
    assert "comment" in calls
