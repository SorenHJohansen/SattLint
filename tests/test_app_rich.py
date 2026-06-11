# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
from __future__ import annotations

from types import SimpleNamespace

from sattlint import app, app_rich


def test_rich_menu_renderer_uses_console_helpers(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    options = [
        SimpleNamespace(key="1", label="Analyze", description="Run checks"),
        SimpleNamespace(key="q", label="Quit", description=""),
    ]

    monkeypatch.setattr(app_rich.console_module, "has_rich", lambda: True)
    monkeypatch.setattr(
        app_rich.console_module,
        "print_panel",
        lambda title, body, **_kwargs: calls.append(("panel", (title, body))),
    )
    monkeypatch.setattr(
        app_rich.console_module,
        "print_table",
        lambda title, columns, rows: calls.append(("table", (title, tuple(columns), tuple(rows)))),
    )

    app_rich.print_menu("SattLint", options, intro="Intro", note="Note")

    assert calls[0] == ("panel", ("SattLint", "Intro\n\nNote"))
    assert calls[1] == (
        "table",
        (
            "SattLint Options",
            ("Key", "Action", "Description"),
            (("1", "Analyze", "Run checks"), ("q", "Quit", "")),
        ),
    )


def test_app_print_menu_uses_startup_renderer(monkeypatch) -> None:
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        app.app_startup_module,
        "print_menu_from_app",
        lambda *args, **kwargs: seen.update({"startup": (args, kwargs)}),
    )

    previous_mode = app.get_interactive_ui_mode()
    try:
        app.set_interactive_ui_mode("rich")
        assert app.get_interactive_ui_mode() == "textual"

        app._print_menu("Menu", [app.MenuOption("1", "One")], intro="Intro", note="Note")

        assert "startup" in seen
    finally:
        app.set_interactive_ui_mode(previous_mode)
