import builtins

import pytest

from sattlint import app

from .helpers import make_input


@pytest.fixture
def noop_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app, "clear_screen", lambda: None)
    monkeypatch.setattr(app, "pause", lambda: None)


def test_variable_usage_submenu_exposes_record_component_order_report(
    noop_screen: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[object] = []

    def _capture(_cfg: object, kinds: object) -> None:
        captured.append(kinds)

    monkeypatch.setattr(app, "run_variable_analysis", _capture)
    monkeypatch.setattr(builtins, "input", make_input(["12", "b"]))

    app.variable_usage_submenu(app.DEFAULT_CONFIG.copy())

    assert captured == [{app.IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE}]
