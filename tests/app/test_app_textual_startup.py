# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownVariableType=false, reportUnusedImport=false
"""Startup wiring, interaction bridge, and shell title behavior."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sattlint import ui as app_textual
from sattlint.cli import startup as app
from sattlint.ui import _app_textual_app as app_textual_module
from sattlint.ui import _app_textual_shared as app_textual_shared_module
from tests.helpers.app_textual_support import (  # noqa: F401  (autouse fixtures)
    isolate_app_config_path,
    isolate_textual_projects,
    typed_cfg,
)


def test_textual_interaction_bridge_returns_responses() -> None:
    seen_kinds: list[str] = []

    def _submit(request: app_textual_shared_module.InteractionRequest) -> None:
        seen_kinds.append(request.kind)
        if request.kind == "menu":
            request.result_future.set_result("2")
        elif request.kind == "prompt":
            request.result_future.set_result("value")
        elif request.kind == "confirm":
            request.result_future.set_result(True)
        else:
            request.result_future.set_result(None)

    bridge = app_textual.TextualInteractionBridge(submit_request_fn=_submit)

    assert bridge.choose_menu_option("Menu", []) == "2"
    assert bridge.prompt("Name") == "value"
    assert bridge.confirm("Confirm?") is True
    bridge.pause()
    assert seen_kinds == ["menu", "prompt", "confirm"]


def test_textual_interaction_bridge_async_returns_responses() -> None:
    seen_kinds: list[str] = []

    def _submit(request: app_textual_shared_module.InteractionRequest) -> None:
        seen_kinds.append(request.kind)
        if request.kind == "menu":
            request.result_future.set_result("2")
        elif request.kind == "prompt":
            request.result_future.set_result("value")
        elif request.kind == "confirm":
            request.result_future.set_result(True)
        else:
            request.result_future.set_result(None)

    bridge = app_textual.TextualInteractionBridge(submit_request_fn=_submit)

    async def _run() -> None:
        assert await bridge.choose_menu_option_async("Menu", []) == "2"
        assert await bridge.prompt_async("Name") == "value"
        assert await bridge.confirm_async("Confirm?") is True
        await bridge.pause_async()

    asyncio.run(_run())

    assert seen_kinds == ["menu", "prompt", "confirm"]


def test_app_input_wrappers_use_textual_interaction_bridge() -> None:
    calls: list[tuple[str, object, object]] = []

    interaction = SimpleNamespace(
        pause=lambda: calls.append(("pause", None, None)),
        prompt=lambda message, default=None: calls.append(("prompt", message, default)) or "value",
        confirm=lambda message: calls.append(("confirm", message, None)) or True,
    )

    app.set_textual_menu_interaction(interaction)
    try:
        app.pause()
        assert app.prompt("Name", "default") == "value"
        assert app.confirm("Continue?") is True
    finally:
        app.clear_textual_menu_interaction()

    assert calls == [
        ("pause", None, None),
        ("prompt", "Name", "default"),
        ("confirm", "Continue?", None),
    ]


def test_app_clear_screen_is_noop_with_textual_interaction(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_calls: list[str] = []

    monkeypatch.setattr("sattlint.core.terminal.clear_screen", lambda **_kwargs: clear_calls.append("clear"))

    app.set_textual_menu_interaction(SimpleNamespace())
    try:
        app.clear_screen()
    finally:
        app.clear_textual_menu_interaction()

    assert clear_calls == []


def test_run_interactive_session_dispatches_to_textual_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def _fake_run_textual_shell(cfg: dict[str, Any], **kwargs: Any) -> None:
        seen.update({"cfg": cfg, **kwargs})

    def _summarize_targets(_cfg: dict[str, Any]) -> str:
        return "targets"

    monkeypatch.setattr(
        app_textual_module,
        "run_textual_shell",
        _fake_run_textual_shell,
    )

    try:
        app.run_interactive_session(typed_cfg({"debug": False}), summarize_targets_fn=_summarize_targets)
    finally:
        app.clear_textual_menu_interaction()

    assert seen["cfg"] == {"debug": False}
    assert "analysis_handler_fns" in seen
    assert isinstance(seen["analysis_handler_fns"], dict)
    assert seen["analysis_handler_fns"]
    assert all(callable(fn) for fn in seen["analysis_handler_fns"].values())


def test_run_textual_shell_passes_ensure_ast_cache_fn_to_app(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    seen: dict[str, Any] = {}
    events: list[tuple[str, object]] = []

    class FakeMainApp:
        def __init__(self, **kwargs: Any) -> None:
            seen.update(kwargs)

        def call_from_thread(self, callback: Any, request: Any) -> None:
            callback(request)

        def run(self) -> None:
            seen["main-run"] = True

    monkeypatch.setattr(app_textual_module, "SattLintTextualApp", FakeMainApp)

    def _ensure_ast_cache(_cfg: dict[str, Any], *, emit_output_fn: object | None = None) -> bool:
        return True

    app_textual.run_textual_shell(
        typed_cfg({"debug": False}),
        ensure_ast_cache_fn=_ensure_ast_cache,
        set_textual_menu_interaction_fn=lambda interaction: events.append(("set-interaction", interaction is not None)),
        clear_textual_menu_interaction_fn=lambda: events.append(("clear-interaction", True)),
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=Path("config.toml"),
        quit_app_error=RuntimeError,
    )

    assert seen["ensure_ast_cache_fn"] is _ensure_ast_cache
    assert seen["main-run"] is True
    assert any(event == "set-interaction" for event, _value in events)
    assert events[-1] == ("clear-interaction", True)


def test_run_textual_shell_passes_app_config_without_startup_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    seen: dict[str, Any] = {}

    class FakeMainApp:
        def __init__(self, **kwargs: Any) -> None:
            seen.update(kwargs)

        def call_from_thread(self, callback: Any, request: Any) -> None:
            callback(request)

        def run(self) -> None:
            seen["main_run"] = True

    monkeypatch.setattr(app_textual_module, "SattLintTextualApp", FakeMainApp)

    app_textual.run_textual_shell(
        typed_cfg({"debug": False}),
        ensure_ast_cache_fn=lambda _cfg, *, emit_output_fn=None: False,
        set_textual_menu_interaction_fn=lambda _interaction: None,
        clear_textual_menu_interaction_fn=lambda: None,
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=Path("config.toml"),
        quit_app_error=RuntimeError,
    )

    assert seen["cfg"] == {"debug": False}
    assert seen["main_run"] is True
    assert "ensure_ast_cache_fn" in seen
    assert callable(seen["ensure_ast_cache_fn"])


def test_resolve_interactive_ui_mode_requires_textual(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_textual, "has_textual", lambda: False)

    with pytest.raises(RuntimeError, match="Textual is required"):
        app.resolve_interactive_ui_mode(typed_cfg({}), "textual")


def test_resolve_interactive_ui_mode_rejects_non_textual_override() -> None:
    with pytest.raises(ValueError, match="Textual-only"):
        app.resolve_interactive_ui_mode(typed_cfg({}), "rich")


def test_resolve_interactive_ui_mode_defaults_to_textual_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SATTLINT_UI", raising=False)
    monkeypatch.setattr(app_textual, "has_textual", lambda: True)

    assert app.resolve_interactive_ui_mode(typed_cfg({}), None) == "textual"


def test_advance_menu_choice_buffer_waits_for_enter_on_ambiguous_single_digit() -> None:
    option_keys = ("2", "23", "24", "b")

    choice_buffer, resolved = app_textual.advance_menu_choice_buffer("", "2", option_keys)

    assert choice_buffer == "2"
    assert resolved is None


def test_advance_menu_choice_buffer_resolves_unique_multi_digit_choice() -> None:
    option_keys = ("2", "23", "24", "b")

    choice_buffer, resolved = app_textual.advance_menu_choice_buffer("2", "3", option_keys)

    assert choice_buffer == ""
    assert resolved == "23"


def test_interaction_ledger_text_mentions_multi_digit_entry() -> None:
    request = app_textual_shared_module.InteractionRequest(
        kind="menu",
        title="Variable issues",
        options=(SimpleNamespace(key="23", label="Datatype usage analysis", description=""),),
    )

    ledger = app_textual.interaction_ledger_text(request, "2")

    assert "Type a menu key and press Enter" in ledger
    assert "Current choice: 2" in ledger


def test_resolve_shell_title_prefers_runtime_title() -> None:
    assert app_textual.resolve_shell_title("Custom title") == "Custom title"
    assert app_textual.resolve_shell_title(SimpleNamespace(title="LIRA")) == "LIRA"


def test_resolve_shell_title_falls_back_to_default_banner_title() -> None:
    assert app_textual.resolve_shell_title(None) == app_textual.DEFAULT_SHELL_TITLE
    assert app_textual.resolve_shell_title(SimpleNamespace(title="")) == app_textual.DEFAULT_SHELL_TITLE


def test_textual_app_title_defaults_to_banner_title() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    assert app_textual.SattLintTextualApp.TITLE == app_textual.DEFAULT_SHELL_TITLE


def test_textual_pause_requests_are_noop() -> None:
    seen_kinds: list[str] = []

    def _submit(request: app_textual_shared_module.InteractionRequest) -> None:
        seen_kinds.append(request.kind)
        request.result_future.set_result(None)

    bridge = app_textual.TextualInteractionBridge(submit_request_fn=_submit)

    bridge.pause()
    asyncio.run(bridge.pause_async())

    assert seen_kinds == []
