# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportOptionalCall=false

from __future__ import annotations

import asyncio
import contextlib
import os
import pty
import select
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from rich.rule import Rule
from rich.text import Text

from sattlint import app
from sattlint import ui as app_textual
from sattlint.application.findings import AnalysisFinding
from sattlint.config.types import ConfigDict
from sattlint.project.io import init_project, load_project
from sattlint.runs import RunAnalyzerRecord, RunRecord, RunSummary, RunTargetRecord
from sattlint.ui import _app_textual_actions as app_textual_actions_module
from sattlint.ui import _app_textual_app as app_textual_module
from sattlint.ui import _app_textual_results as app_textual_results_module
from sattlint.ui import _app_textual_settings as app_textual_settings_module
from sattlint.ui import _app_textual_setup as app_textual_setup_module
from sattlint.ui import _app_textual_shared as app_textual_shared_module
from sattlint.ui import _app_textual_widgets as app_textual_widgets_module


def _typed_cfg(value: dict[str, Any]) -> ConfigDict:
    return cast(ConfigDict, value)


def _query_any_screen(app_instance: Any, selector: str) -> Any:
    try:
        return app_instance.query_one(selector)
    except app_textual_shared_module._TEXTUAL_QUERY_ERRORS as exc:
        last_error: BaseException = exc

    screen_stack = getattr(app_instance, "screen_stack", None)
    if screen_stack is None:
        screen_stack = getattr(app_instance, "_screen_stack", ())

    for screen in reversed(tuple(screen_stack)):
        query_one = getattr(screen, "query_one", None)
        if not callable(query_one):
            continue
        try:
            return query_one(selector)
        except app_textual_shared_module._TEXTUAL_QUERY_ERRORS as exc:
            last_error = exc

    raise last_error


def _screen_row_bgcolors(app_instance: Any, row: int) -> list[Any]:
    screen = app_instance.screen
    chops = screen._compositor._render_chops(screen.size.region, lambda y: True)
    colors: list[Any] = []
    for strip in chops[row].values():
        if strip is None:
            continue
        for segment in strip:
            if segment.style is not None and segment.style.bgcolor is not None:
                colors.append(segment.style.bgcolor)
    return colors


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

    app.set_interactive_ui_mode("textual")
    app.set_textual_menu_interaction(interaction)
    try:
        app.pause()
        assert app.prompt("Name", "default") == "value"
        assert app.confirm("Continue?") is True
    finally:
        app.reset_interactive_ui_mode()

    assert calls == [
        ("pause", None, None),
        ("prompt", "Name", "default"),
        ("confirm", "Continue?", None),
    ]


def test_app_clear_screen_is_noop_with_textual_interaction(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_calls: list[str] = []

    monkeypatch.setattr("sattlint.core.terminal.clear_screen", lambda **_kwargs: clear_calls.append("clear"))

    app.set_interactive_ui_mode("textual")
    app.set_textual_menu_interaction(SimpleNamespace())
    try:
        app.clear_screen()
    finally:
        app.reset_interactive_ui_mode()

    assert clear_calls == []


def test_run_interactive_session_dispatches_to_textual_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    app.set_interactive_ui_mode("textual")

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
        app.run_interactive_session(_typed_cfg({"debug": False}), summarize_targets_fn=_summarize_targets)
    finally:
        app.reset_interactive_ui_mode()

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
        _typed_cfg({"debug": False}),
        ensure_ast_cache_fn=_ensure_ast_cache,
        set_textual_menu_interaction_fn=lambda interaction: events.append(("set-interaction", interaction is not None)),
        clear_textual_menu_interaction_fn=lambda: events.append(("clear-interaction", True)),
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=Path("config.toml"),
        quit_app_error=RuntimeError,
    )

    assert seen["ensure_ast_cache_fn"] is _ensure_ast_cache
    assert seen["main-run"] is True
    assert any(event == "set-interaction" for event, _value in events)
    assert events[-1] == ("clear-interaction", True)


def test_textual_ast_refresh_modal_records_exception_and_dismisses(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    status_updates: list[str] = []
    dismissed: list[object] = []

    modal = app_textual_widgets_module._AstRefreshModalScreen(
        refresh_fn=lambda _emit_status: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    monkeypatch.setattr(
        modal,
        "query_one",
        lambda *_args, **_kwargs: SimpleNamespace(update=lambda text: status_updates.append(str(text))),
    )
    monkeypatch.setattr(modal, "dismiss", lambda result: dismissed.append(result))

    modal._run_refresh()

    assert len(dismissed) == 1
    result = dismissed[0]
    assert getattr(result, "ok", True) is False
    assert "AST cache refresh failed: boom" in getattr(result, "output", "")
    assert modal._refresh_failed is True
    assert isinstance(modal._refresh_exception, RuntimeError)


def test_textual_ast_refresh_modal_propagates_type_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    modal = app_textual_widgets_module._AstRefreshModalScreen(
        refresh_fn=lambda _emit_status: (_ for _ in ()).throw(TypeError("bad refresh wiring"))
    )

    monkeypatch.setattr(
        modal,
        "query_one",
        lambda *_args, **_kwargs: SimpleNamespace(update=lambda _text: None),
    )
    monkeypatch.setattr(modal, "dismiss", lambda _result: None)

    with pytest.raises(TypeError, match="bad refresh wiring"):
        modal._run_refresh()

    assert modal._refresh_failed is True
    assert modal._refresh_exception is None


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
        _typed_cfg({"debug": False}),
        ensure_ast_cache_fn=lambda _cfg, *, emit_output_fn=None: False,
        set_textual_menu_interaction_fn=lambda _interaction: None,
        clear_textual_menu_interaction_fn=lambda: None,
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
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
        app.resolve_interactive_ui_mode(_typed_cfg({}), "textual")


def test_resolve_interactive_ui_mode_rejects_non_textual_override() -> None:
    with pytest.raises(ValueError, match="Textual-only"):
        app.resolve_interactive_ui_mode(_typed_cfg({}), "rich")


def test_resolve_interactive_ui_mode_defaults_to_textual_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SATTLINT_UI", raising=False)
    monkeypatch.setattr(app_textual, "has_textual", lambda: True)

    assert app.resolve_interactive_ui_mode(_typed_cfg({}), None) == "textual"


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


def test_discover_setup_target_candidates_collects_preview_files(tmp_path: Path) -> None:
    program_dir = tmp_path / "programs"
    abb_dir = tmp_path / "abb"
    program_dir.mkdir()
    abb_dir.mkdir()
    (program_dir / "TargetA.s").write_text("draft")
    (program_dir / "TargetA.l").write_text("deps")
    (abb_dir / "TargetA.x").write_text("official")
    (abb_dir / "TargetB.s").write_text("draft-only")

    candidates = app_textual.discover_setup_target_candidates(
        _typed_cfg(
            {
                "program_dir": str(program_dir),
                "ABB_lib_dir": str(abb_dir),
                "other_lib_dirs": [],
                "mode": "official",
            }
        )
    )

    assert [candidate.name for candidate in candidates] == ["TargetA", "TargetB"]
    assert [path.name for path in candidates[0].files] == ["TargetA.l", "TargetA.s", "TargetA.x"]
    assert candidates[0].available is True
    assert candidates[1].available is False


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


def test_textual_top_chrome_removes_banner_and_summary_boxes() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            assert len(list(app_instance.query("#shell-banner"))) == 0
            assert len(list(app_instance.query("#summary"))) == 0
            assert app_instance.query_one("#nav-tab-analyze") is not None

    asyncio.run(_run())


def test_textual_toolbar_is_available_without_summary_box() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={"analyzed_programs_and_libraries": ["Target1", "Target2"]},
            summarize_targets_fn=lambda _cfg: "targets",
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            assert len(list(app_instance.query("#summary"))) == 0
            assert app_instance.query_one("#nav-tabs") is not None
            assert app_instance.query_one("#nav-tab-analyze") is not None
            output_pane = app_instance.query_one("#output-pane")

            assert output_pane.size.width > 0

    asyncio.run(_run())


def test_textual_quit_keybinding_does_not_crash() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+q")
            await pilot.pause()

    asyncio.run(_run())


def test_textual_ctrl_c_copy_binding_copies_session_output() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        copied: list[str] = []
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )
        app_instance.copy_to_clipboard = lambda text: copied.append(text)

        async with app_instance.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+c")
            await pilot.pause()

            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert copied
            assert "Welcome to SattLint." in copied[-1]
            assert copied[-1] in getattr(app_instance.query_one("#output"), "text", "")
            assert "Copied all Session output because no text was selected." in output_text

    asyncio.run(_run())


def test_textual_ctrl_l_clear_binding_clears_session_output() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance._write_output("Extra output")
            await pilot.pause()
            assert "Extra output" in getattr(app_instance.query_one("#output"), "text", "")

            await pilot.press("ctrl+l")
            await pilot.pause()

            assert getattr(app_instance.query_one("#output"), "text", "") == ""
            assert app_instance._session_output_lines == []

    asyncio.run(_run())


def test_textual_question_mark_binding_opens_help() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            await pilot.press("?")
            await pilot.pause()

            help_dialog = _query_any_screen(app_instance, "#help-dialog")
            help_body = str(_query_any_screen(app_instance, "#help-dialog-body").renderable)
            assert "Keyboard shortcuts" in help_body
            assert "/ filters Analyze and Setup lists" in help_body
            assert "Ctrl+L clears Session output" in help_body
            assert "Ctrl+G cancels a running analysis" in help_body
            assert help_dialog.region.x > 0
            assert help_dialog.region.y > 0
            assert help_dialog.size.width < app_instance.size.width
            assert help_dialog.size.height < app_instance.size.height

            help_screen = app_instance.screen
            assert help_screen.styles.background.a < 1
            menubar_colors = _screen_row_bgcolors(app_instance, 0)
            assert menubar_colors
            menubar_triplets = [(c.triplet.red, c.triplet.green, c.triplet.blue) for c in menubar_colors]
            assert all(t != (18, 18, 18) for t in menubar_triplets), "app must be visible behind the popup, not black"
            assert all(t != (230, 222, 203) for t in menubar_triplets), "app behind the popup should be dimmed"

    asyncio.run(_run())


def test_textual_pause_requests_are_noop() -> None:
    seen_kinds: list[str] = []

    def _submit(request: app_textual_shared_module.InteractionRequest) -> None:
        seen_kinds.append(request.kind)
        request.result_future.set_result(None)

    bridge = app_textual.TextualInteractionBridge(submit_request_fn=_submit)

    bridge.pause()
    asyncio.run(bridge.pause_async())

    assert seen_kinds == []


def test_textual_slash_binding_filters_analyze_planner() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["TargetA"]},
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="comment-code",
                    name="Commented out code",
                    description="Detect commented-out code.",
                    category="code-quality",
                ),
                SimpleNamespace(
                    key="timing",
                    name="Timing",
                    description="Scan-cycle timing hazards.",
                    category="correctness",
                ),
            ],
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            await pilot.press("/")
            await pilot.pause()

            assert app_instance.query_one("#interaction-host").has_class("active") is True

            await pilot.press("c", "o", "m", "m", "e", "n", "t", "enter")
            await pilot.pause()

            assert app_instance.query_one("#interaction-host").has_class("active") is False
            assert app_instance._analyze_filter_text == "comment"
            assert app_instance._planner_entry_ids() == ("comment-code",)
            assert 'Filter: "comment"' not in str(app_instance.query_one("#view-note").renderable)

    asyncio.run(_run())


def test_textual_slash_binding_filters_setup_targets() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": ["Alpha", "Beta", "Gamma"]})

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+4")
            await pilot.pause()

            await pilot.press("/")
            await pilot.pause()

            assert app_instance.query_one("#interaction-host").has_class("active") is True

            await pilot.press("b", "e", "t", "a", "enter")
            await pilot.pause()

            assert app_instance.query_one("#interaction-host").has_class("active") is False
            assert app_instance._setup_filter_text == "beta"
            assert app_instance._setup_target_names_list == ["Beta"]

    asyncio.run(_run())


def test_textual_session_output_preserves_manual_scroll_position_on_new_output() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            output = app_instance.query_one("#output")
            for index in range(40):
                app_instance._write_output(f"line {index}")
            await pilot.pause()

            output.scroll_to(y=0, animate=False, force=True)
            await pilot.pause()
            scrolled_y = output.scroll_y

            app_instance._write_output("line after manual scroll")
            await pilot.pause()

            assert output.scroll_y == scrolled_y
            assert output.max_scroll_y > output.scroll_y

    asyncio.run(_run())


def test_textual_session_output_keeps_following_when_already_at_bottom() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            output = app_instance.query_one("#output")
            for index in range(40):
                app_instance._write_output(f"line {index}")
            await pilot.pause()

            output.scroll_end(animate=False)
            await pilot.pause()

            app_instance._write_output("line at bottom")
            await pilot.pause()

            assert output.scroll_y == output.max_scroll_y

    asyncio.run(_run())


def test_textual_present_request_uses_inline_host_and_preserves_shell_chrome() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )
        request = app_textual_shared_module.InteractionRequest(
            kind="menu",
            title="Analyze",
            options=(
                SimpleNamespace(key="1", label="Run analysis", description=""),
                SimpleNamespace(key="b", label="Back", description=""),
            ),
        )

        async with app_instance.run_test() as pilot:
            app_instance.present_request(request)
            await pilot.pause()

            assert len(list(app_instance.query("#shell-banner"))) == 0
            assert len(list(app_instance.query("#summary"))) == 0
            assert app_instance.query_one("#interaction-host").has_class("active")
            assert app_instance.query_one("#output").has_class("interaction-active")
            assert getattr(app_instance.query_one("#view-primary-action"), "disabled", False) is True

            await pilot.press("escape")
            await pilot.pause()

            assert request.result_future.done() is True
            assert request.result_future.result() == "b"
            assert request.response == "b"
            assert app_instance.query_one("#interaction-host").has_class("active") is False
            assert app_instance.query_one("#output").has_class("interaction-active") is False
            assert getattr(app_instance.query_one("#view-primary-action"), "disabled", True) is False

    asyncio.run(_run())


def test_textual_toolbar_navigation_switches_view_without_starting_action(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    started: list[str] = []

    monkeypatch.setattr(app_instance, "_start_action", lambda *args, **kwargs: started.append("started"))

    app_instance._handle_toolbar_action("action-setup")

    assert app_instance._active_view == "setup"
    assert app_instance._busy is False
    assert started == []


def test_textual_view_primary_action_launches_active_view(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    launched: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(
        app_instance,
        "_start_action",
        lambda label, _action_fn, *, action_id, marks_dirty=False, clear_dirty_on_success=False: launched.append(
            (label, action_id, marks_dirty or clear_dirty_on_success)
        ),
    )
    popups: list[str] = []
    monkeypatch.setattr(app_instance, "_open_help_popup", lambda: popups.append("help"))

    app_instance._handle_toolbar_action("action-help")

    assert popups == ["help"]
    assert launched == []


def _make_textual_app(
    *,
    cfg: dict[str, Any] | None = None,
    analysis_handlers: dict[str, Any] | None = None,
    get_enabled_analyzers_fn: Any | None = None,
    ensure_ast_cache_fn: Any | None = None,
    save_config_fn: Callable[[Any, Any], None] | None = None,
    project: bool = True,
) -> Any:
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg or {"analyzed_programs_and_libraries": ["TargetA"]},
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        get_help_text_fn=lambda _cfg: "Help text",
        save_config_fn=save_config_fn or (lambda _path, _cfg: None),
        config_path=None,
        quit_app_error=RuntimeError,
        analysis_handlers=analysis_handlers,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        ensure_ast_cache_fn=ensure_ast_cache_fn,
    )
    if project:
        _attach_test_project(app_instance)
    return app_instance


def _attach_test_project(app_instance: Any) -> None:
    project_dir = Path(tempfile.mkdtemp(prefix="sattlint-test-project-"))
    app_instance._project = init_project(project_dir / ".slproj", name="TestProject")


def test_textual_shell_defaults_to_truecolor_console() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": []})

    assert app_instance.console.color_system == "truecolor"


def test_textual_analyze_view_shows_planner_controls() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": []})

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            workspace_host = app_instance.query_one("#workspace-host")
            view_title = app_instance.query_one("#view-title")
            view_host = app_instance.query_one("#view-host")
            output_pane = app_instance.query_one("#output-pane")
            output_widget = app_instance.query_one("#output")
            analyze_left = app_instance.query_one("#analyze-browser-left")

            assert app_instance._active_view == "analyze"
            assert workspace_host.has_class("analyze-split")
            assert workspace_host.has_class("no-output") is False
            assert str(view_title.renderable) == "Analyze"
            assert view_title.region.bottom <= view_host.region.y
            assert view_host.size.height > 0
            assert output_pane.size.height > 0
            assert output_widget.size.height > 0
            assert analyze_left.size.height > 0
            assert output_pane.region.x > app_instance.query_one("#analyze-browser").region.x
            assert output_pane.region.width > 0
            assert getattr(output_widget, "read_only", False) is True
            assert getattr(output_widget, "show_line_numbers", True) is False
            assert "Welcome to SattLint." in getattr(output_widget, "text", "")
            assert app_instance.query_one("#view-actions").has_class("is-hidden") is True
            assert app_instance.query_one("#analyze-actions-primary").has_class("is-hidden") is False
            assert app_instance.query_one("#analyze-browser").has_class("is-hidden") is False
            assert app_instance.query_one("#view-side-actions") is not None
            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", False) is True
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", False) is True
            assert str(app_instance.query_one("#view-note").renderable) == ""
            assert len(list(app_instance.query("#analyze-planner-section-top-level"))) == 0
            assert len(list(app_instance.query("#analyze-planner-section-variable-suite"))) == 0
            assert str(app_instance.query_one("#output-title").renderable) == "Session output"

            assert len(list(app_instance.query("#analyze-planner-detail"))) == 0

    asyncio.run(_run())


def test_textual_analyze_view_keeps_planner_panes_visible_on_small_terminal() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": []})

        async with app_instance.run_test(size=(80, 20)) as pilot:
            await pilot.pause()

            analyze_left = app_instance.query_one("#analyze-browser-left")
            output_widget = app_instance.query_one("#output")

            assert analyze_left.size.height >= 2
            assert output_widget.size.height > 0

    asyncio.run(_run())


def test_textual_analyze_selection_lists_expand_instead_of_scrolling_individually() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["TargetA"]},
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key=f"analyzer-{index}",
                    name=f"Analyzer {index}",
                    description=f"Description {index}",
                    category="correctness",
                )
                for index in range(12)
            ],
        )

        async with app_instance.run_test(size=(80, 18)) as pilot:
            await pilot.pause()

            analyze_left = app_instance.query_one("#analyze-browser-left")
            analyzers_list = app_instance.query_one("#analyze-planner-section-analyzers")

            assert analyze_left.virtual_size.height > analyze_left.size.height
            assert analyzers_list.size.height >= analyzers_list.virtual_size.height

    asyncio.run(_run())


def test_textual_analyze_header_buttons_fit_without_clipping() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})

        async with app_instance.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            run_button = app_instance.query_one("#analyze-run-selected")
            clear_button = app_instance.query_one("#analyze-clear-selection")

            assert run_button.size.width >= run_button.virtual_size.width
            assert clear_button.size.width >= clear_button.virtual_size.width

    asyncio.run(_run())


def test_textual_analyze_selection_styles_hide_unselected_marker_and_highlight_current_row() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["TargetA"]},
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="comment-code",
                    name="Commented-out code",
                    description="Detect commented-out code.",
                    category="code-quality",
                )
            ],
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            selection_list = app_instance.query_one("#analyze-planner-section-analyzers")
            option_style = selection_list.get_component_rich_style("option-list--option")
            option_highlighted_style = selection_list.get_component_rich_style("option-list--option-highlighted")
            unselected_button_style = selection_list.get_component_rich_style("selection-list--button")
            highlighted_button_style = selection_list.get_component_rich_style("selection-list--button-highlighted")
            selected_button_style = selection_list.get_component_rich_style("selection-list--button-selected")
            selected_highlighted_button_style = selection_list.get_component_rich_style(
                "selection-list--button-selected-highlighted"
            )

            assert unselected_button_style.color is not None
            assert unselected_button_style.bgcolor is not None
            assert highlighted_button_style.color is not None
            assert highlighted_button_style.bgcolor is not None
            assert option_style.color is not None
            assert option_style.bgcolor is not None
            assert option_highlighted_style.color is not None
            assert option_highlighted_style.bgcolor is not None
            assert selected_button_style.color is not None
            assert selected_button_style.bgcolor is not None
            assert selected_highlighted_button_style.color is not None
            assert selected_highlighted_button_style.bgcolor is not None

            assert unselected_button_style.color.triplet == option_style.bgcolor.triplet
            assert unselected_button_style.bgcolor.triplet == option_style.bgcolor.triplet
            assert highlighted_button_style.color.triplet == option_highlighted_style.bgcolor.triplet
            assert highlighted_button_style.bgcolor.triplet == option_highlighted_style.bgcolor.triplet
            assert selected_button_style.color.triplet == option_style.color.triplet
            assert selected_button_style.bgcolor.triplet == option_style.bgcolor.triplet
            assert selected_highlighted_button_style.color.triplet == option_style.color.triplet
            assert selected_highlighted_button_style.bgcolor.triplet == option_highlighted_style.bgcolor.triplet
            assert option_highlighted_style.color.triplet == option_style.color.triplet
            assert option_highlighted_style.bgcolor.triplet != option_style.bgcolor.triplet

    asyncio.run(_run())


def test_textual_analyze_planner_renders_grouped_sections_and_detail() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="timing",
                    name="Timing",
                    description="Scan-cycle timing hazards",
                    category="correctness",
                ),
            ],
            analysis_handlers={"_run_checks": lambda _cfg, _selected_keys: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            assert len(list(app_instance.query("#analyze-planner-section-top-level"))) == 0
            assert len(list(app_instance.query("#analyze-planner-section-variable-suite"))) == 0
            assert len(list(app_instance.query("#analyze-planner-section-investigation"))) == 0
            assert app_instance.query_one("#analyze-planner-section-analyzers") is not None
            assert len(list(app_instance.query("#analyze-planner-section-catalog-issue-checks"))) == 0
            assert len(list(app_instance.query("#analyze-planner-section-catalog-analyzers"))) == 0
            assert "timing" in app_instance._planner_entry_ids()

            app_instance._analyze_focused_entry_id = "timing"
            app_instance._write_focused_entry_to_output()
            await pilot.pause()
            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert "Analyzer: Timing" in output_text
            assert "Description:" in output_text

    asyncio.run(_run())


def test_textual_analyze_planner_selection_updates_summary_and_enables_run() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="timing",
                    name="Timing",
                    description="Scan-cycle timing hazards",
                    category="correctness",
                ),
                SimpleNamespace(
                    key="state-inference",
                    name="State inference",
                    description="Detect incorrect state inference.",
                    category="correctness",
                ),
            ],
            analysis_handlers={"_run_checks": lambda _cfg, _selected_keys: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-planner-section-analyzers")

            analyzers_list.select("timing")
            analyzers_list.select("state-inference")
            app_instance._sync_analyze_selection_from_selection_list(analyzers_list)
            app_instance._write_focused_entry_to_output()
            app_instance._refresh_shell_state()
            await pilot.pause()

            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert "Analyzer:" in output_text
            assert "Description:" in output_text
            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", True) is False

    asyncio.run(_run())


def test_textual_analyze_run_selected_executes_planned_steps_in_catalog_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    launched: list[tuple[str, str]] = []

    app_instance = _make_textual_app(
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="alpha-analyzer",
                name="Alpha Analyzer",
                description="Alpha description",
                category="correctness",
            ),
            SimpleNamespace(
                key="beta-analyzer",
                name="Beta Analyzer",
                description="Beta description",
                category="correctness",
            ),
        ],
        analysis_handlers={
            "_run_checks": lambda _cfg, selected_keys: calls.append(
                ("checks", None if selected_keys is None else tuple(selected_keys))
            ),
        },
    )
    app_instance._analyze_selected_entry_ids = {"alpha-analyzer", "beta-analyzer"}
    app_instance._analyze_focused_entry_id = "alpha-analyzer"

    monkeypatch.setattr(
        app_instance,
        "_start_action",
        lambda label, action_fn, *, action_id, marks_dirty=False, clear_dirty_on_success=False: (
            launched.append((label, action_id)),
            action_fn(),
        ),
    )
    monkeypatch.setattr(app_instance, "_emit_output_from_thread", lambda _text: None)

    app_instance._run_selected_analysis_plan()

    assert launched == [("Run selected analyzers", "action-analyze")]
    assert calls == [("checks", ("alpha-analyzer", "beta-analyzer"))]
    assert app_instance._analyze_selected_entry_ids == {"alpha-analyzer", "beta-analyzer"}


def test_textual_analyze_run_selected_surfaces_variable_issue_output_from_real_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    seen_keys: list[list[str] | None] = []

    def _fake_checks(app_instance: Any, selected_keys: list[str] | None) -> None:
        app_instance._write_output("=== Target: ProgramA ===")
        app_instance._write_output("Report: Variable issues")
        seen_keys.append(None if selected_keys is None else list(selected_keys))

    async def _run() -> None:
        app_instance = _make_textual_app(
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="state-inference",
                    name="State inference",
                    description="Detect incorrect state inference.",
                    category="correctness",
                ),
            ],
            analysis_handlers={
                "_run_checks": lambda _local_cfg, selected_keys: _fake_checks(app_instance, selected_keys)
            },
        )
        monkeypatch.setattr(
            app_instance,
            "_start_action",
            lambda label, action_fn, *, action_id, marks_dirty=False, clear_dirty_on_success=False: action_fn(),
        )
        monkeypatch.setattr(
            app_instance,
            "_emit_output_from_thread",
            lambda text: app_instance._write_output(text),
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-planner-section-analyzers")
            analyzers_list.select("state-inference")
            app_instance._sync_analyze_selection_from_selection_list(analyzers_list)
            app_instance._write_focused_entry_to_output()
            app_instance._refresh_shell_state()
            await pilot.pause()

            app_instance.on_button_pressed(SimpleNamespace(button=app_instance.query_one("#analyze-run-selected")))
            await pilot.pause()
            await pilot.pause()

            output_text = str(getattr(app_instance.query_one("#output"), "text", ""))
            assert "Running 1 selected analyzer(s)." in output_text
            assert "=== Target: ProgramA ===" in output_text
            assert "Report: Variable issues" in output_text
            assert "Selected analyzers completed." in output_text
            assert app_instance.query_one("#interaction-host").has_class("active") is False
            assert app_instance._busy is False

    asyncio.run(_run())

    assert seen_keys == [["state-inference"]]


def test_textual_analyze_running_state_calls_out_output_location(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    current_time = 100.0
    monkeypatch.setattr(app_textual_setup_module, "_output_title_spinner_timestamp", lambda: current_time)

    async def _run() -> None:
        nonlocal current_time
        app_instance = _make_textual_app(
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="comment-code",
                    name="Commented-out code",
                    description="Detect commented-out code.",
                    category="code-quality",
                ),
            ],
            analysis_handlers={"run_comment_code_analysis": lambda _cfg: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-planner-section-analyzers")
            analyzers_list.select("comment-code")
            app_instance._sync_analyze_selection_from_selection_list(analyzers_list)
            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Run selected analyzers"
            app_instance._refresh_summary()
            app_instance._write_focused_entry_to_output()
            app_instance._refresh_shell_state()

            assert str(app_instance.query_one("#view-note").renderable) == ""
            assert str(app_instance.query_one("#output-title").renderable) == (
                "Session output ⠋ - Run selected analyzers in progress"
            )

            current_time += (1.0 / 60.0) + 0.001
            app_instance._advance_output_title_spinner()
            assert str(app_instance.query_one("#output-title").renderable) == (
                "Session output ⠙ - Run selected analyzers in progress"
            )

            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert "Analyzer:" in output_text
            assert "Description:" in output_text

    asyncio.run(_run())


def test_textual_analyze_running_state_uses_60fps_output_title_spinner(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    captured: dict[str, object] = {}
    timer_calls = {"resume": 0, "pause": 0}
    timer = SimpleNamespace(
        resume=lambda: timer_calls.__setitem__("resume", timer_calls["resume"] + 1),
        pause=lambda: timer_calls.__setitem__("pause", timer_calls["pause"] + 1),
    )
    app_instance = _make_textual_app(analysis_handlers={"run_comment_code_analysis": lambda _cfg: None})
    app_instance._busy = True
    app_instance._active_job_action_id = "action-analyze"
    app_instance._active_job_label = "Run selected analyses"

    monkeypatch.setattr(
        app_instance,
        "set_interval",
        lambda interval, callback, *, pause=False: (
            captured.update({"interval": interval, "callback": callback, "pause": pause}) or timer
        ),
    )

    app_instance._sync_output_title_spinner()

    assert captured["interval"] == pytest.approx(1.0 / 60.0)
    assert captured["callback"] == app_instance._advance_output_title_spinner
    assert captured["pause"] is False
    assert timer_calls == {"resume": 0, "pause": 0}

    app_instance._sync_output_title_spinner()
    assert timer_calls == {"resume": 0, "pause": 0}

    app_instance._busy = False
    app_instance._sync_output_title_spinner()
    assert timer_calls == {"resume": 0, "pause": 1}

    app_instance._busy = True
    app_instance._sync_output_title_spinner()
    assert timer_calls == {"resume": 1, "pause": 1}


def test_textual_analyze_buttons_unlock_after_finish_action() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["DemoTarget.s"]},
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="comment-code",
                    name="Commented-out code",
                    description="Detect commented-out code.",
                    category="code-quality",
                ),
            ],
            analysis_handlers={"run_comment_code_analysis": lambda _cfg: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-planner-section-analyzers")
            analyzers_list.select("comment-code")
            app_instance._sync_analyze_selection_from_selection_list(analyzers_list)
            app_instance._write_focused_entry_to_output()
            app_instance._refresh_shell_state()
            await pilot.pause()

            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", True) is False
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", True) is False

            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Run selected analyzers"
            app_instance._refresh_summary()
            app_instance._write_focused_entry_to_output()
            app_instance._refresh_shell_state()
            await pilot.pause()

            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", False) is True
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", False) is True

            app_instance._finish_action()
            await pilot.pause()

            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", True) is False
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", True) is False
            assert str(app_instance.query_one("#output-title").renderable) == "Session output"
            assert "Selected analyses are running." not in str(app_instance.query_one("#view-note").renderable)

    asyncio.run(_run())


def test_textual_analyze_cancel_button_enables_for_running_queue() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["DemoTarget.s"]},
            analysis_handlers={"run_comment_code_analysis": lambda _cfg: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Run selected analyses"
            app_instance._active_job_cancel_event = threading.Event()
            app_instance._active_job_thread = SimpleNamespace(ident=None, is_alive=lambda: True)
            app_instance._refresh_shell_state()
            await pilot.pause()

            assert getattr(app_instance.query_one("#analyze-cancel-running"), "disabled", True) is False

    asyncio.run(_run())


def test_textual_analyze_run_selected_reports_missing_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    lines: list[str] = []
    started: list[tuple[str, str]] = []

    app_instance = _make_textual_app(
        cfg={"analyzed_programs_and_libraries": ["TargetA"]},
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state-inference",
                name="State inference",
                description="Detect incorrect state inference.",
                category="correctness",
            ),
        ],
        analysis_handlers={},
    )
    app_instance._analyze_selected_entry_ids = {"state-inference"}

    monkeypatch.setattr(app_instance, "_write_output", lambda text: lines.extend(text.splitlines()))
    monkeypatch.setattr(
        app_instance,
        "_start_action",
        lambda label, action_fn, *, action_id, marks_dirty=False, clear_dirty_on_success=False: (
            started.append((label, action_id)),
            action_fn(),
        ),
    )
    monkeypatch.setattr(
        app_instance,
        "_emit_output_from_thread",
        lambda text: lines.extend(text.splitlines()),
    )

    app_instance._run_selected_analysis_plan()

    assert started == [("Run selected analyzers", "action-analyze")]
    assert any("The analyzer runner is unavailable" in line for line in lines)


def test_textual_execute_analyze_plan_dispatches_to_run_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[str] = []
    called: list[list[str] | None] = []

    app_instance = _make_textual_app(
        analysis_handlers={
            "_run_checks": lambda _cfg, selected_keys: called.append(
                None if selected_keys is None else list(selected_keys)
            )
        }
    )
    plan = SimpleNamespace(selected_analyzer_keys=("alpha-analyzer", "beta-analyzer"))

    monkeypatch.setattr(app_instance, "_emit_output_from_thread", lambda text: emitted.append(text))

    app_instance._execute_analyze_plan(plan)

    assert emitted == [
        "Running 2 selected analyzer(s).",
        "Selected analyzers completed.",
    ]
    assert called == [["alpha-analyzer", "beta-analyzer"]]


def test_textual_start_action_tracks_active_worker_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    created_workers: list[object] = []

    class FakeWorker:
        def cancel(self) -> None:
            return None

    class FakeTextualApp(app_textual.SattLintTextualApp):
        def _start_managed_action_worker(self, _work: Any, *, label: str, action_id: str) -> object:
            assert label == "Run selected analyses"
            assert action_id == "action-analyze"
            worker = FakeWorker()
            created_workers.append(worker)
            return worker

    app_instance = FakeTextualApp(
        cfg={"analyzed_programs_and_libraries": ["TargetA"]},
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        get_help_text_fn=lambda _cfg: "Help text",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
        analysis_handlers={},
    )

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(
        app_instance, "_set_active_action", lambda action_id: setattr(app_instance, "_active_job_action_id", action_id)
    )
    monkeypatch.setattr(app_instance, "_write_output", lambda _text: None)
    monkeypatch.setattr(app_instance, "_clear_session_output", lambda: None)

    app_instance._start_action("Run selected analyses", lambda: None, action_id="action-analyze")

    assert len(created_workers) == 1
    assert app_instance._active_job_worker is created_workers[0]
    assert app_instance._active_job_thread is None
    assert app_instance._active_job_cancel_event is not None


def test_textual_schedule_ui_coroutine_tracks_pending_task(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTask:
        def __init__(self) -> None:
            self._callbacks: list[Any] = []

        def add_done_callback(self, callback: Any) -> None:
            self._callbacks.append(callback)

        def finish(self) -> None:
            for callback in tuple(self._callbacks):
                callback(self)

    class FakeLoop:
        def __init__(self, task: FakeTask) -> None:
            self.task = task
            self.created: list[object] = []

        def create_task(self, coroutine: object) -> FakeTask:
            self.created.append(coroutine)
            return self.task

    fake_task = FakeTask()
    fake_loop = FakeLoop(fake_task)
    app_instance = _make_textual_app()

    monkeypatch.setattr(asyncio, "get_running_loop", lambda: fake_loop)

    app_instance._schedule_ui_coroutine(lambda: "scheduled work")

    assert fake_loop.created == ["scheduled work"]
    assert fake_task in app_instance._pending_ui_tasks

    fake_task.finish()

    assert fake_task not in app_instance._pending_ui_tasks


def test_textual_start_action_reports_type_errors_from_action(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTextualApp(app_textual.SattLintTextualApp):
        def _start_managed_action_worker(self, work: Any, *, label: str, action_id: str) -> object:
            assert label == "Run selected analyses"
            assert action_id == "action-analyze"
            work()
            return SimpleNamespace(cancel=lambda: None)

    app_instance = FakeTextualApp(
        cfg={"analyzed_programs_and_libraries": ["TargetA"]},
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        get_help_text_fn=lambda _cfg: "Help text",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
        analysis_handlers={},
    )

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(
        app_instance, "_set_active_action", lambda action_id: setattr(app_instance, "_active_job_action_id", action_id)
    )
    emitted: list[str] = []
    monkeypatch.setattr(app_instance, "_write_output", lambda text: emitted.append(str(text)))
    monkeypatch.setattr(app_instance, "_clear_session_output", lambda: None)
    monkeypatch.setattr(app_instance, "call_from_thread", lambda callback, *args, **kwargs: callback(*args, **kwargs))

    app_instance._start_action(
        "Run selected analyses",
        lambda: (_ for _ in ()).throw(TypeError("bad action wiring")),
        action_id="action-analyze",
    )

    assert app_instance._busy is False
    assert emitted == [
        "Starting Run selected analyses... Live output is shown in this panel.",
        "Run selected analyses failed: bad action wiring",
    ]


def test_textual_open_help_popup_propagates_type_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = _make_textual_app()
    app_instance._get_help_text_fn = lambda _cfg: (_ for _ in ()).throw(TypeError("bad help wiring"))
    shown_help: list[str] = []

    monkeypatch.setattr(app_instance, "_show_help_modal", lambda text: shown_help.append(text))

    with pytest.raises(TypeError, match="bad help wiring"):
        app_instance._open_help_popup()

    assert shown_help == []


def test_textual_ctrl_g_cancel_binding_requests_stop_for_running_analysis() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["DemoTarget.s"]},
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="comment-code",
                    name="Commented-out code",
                    description="Detect commented-out code.",
                    category="code-quality",
                ),
            ],
            analysis_handlers={"run_comment_code_analysis": lambda _cfg: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-planner-section-analyzers")
            analyzers_list.select("comment-code")
            app_instance._sync_analyze_selection_from_selection_list(analyzers_list)
            app_instance._write_focused_entry_to_output()
            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Run selected analyzers"
            app_instance._active_job_cancel_event = threading.Event()
            app_instance._active_job_cancel_requested = False
            app_instance._active_job_worker = SimpleNamespace(cancel=lambda: None)
            app_instance._refresh_summary()
            app_instance._refresh_shell_state()
            app_instance._refresh_view()
            await pilot.pause()

            assert ("ctrl+g", "cancel_running_analysis", "Cancel Analysis") in app_textual.SattLintTextualApp.BINDINGS
            app_instance.action_cancel_running_analysis()

            output_text = getattr(app_instance.query_one("#output"), "text", "")

            assert app_instance._active_job_cancel_requested is True
            assert app_instance._active_job_cancel_event is not None
            assert app_instance._active_job_cancel_event.is_set() is True
            assert "Cancellation requested. The running analysis will stop at the next checkpoint." in output_text
            assert str(app_instance.query_one("#view-note").renderable) == ""
            assert "Analyzer:" in output_text

    asyncio.run(_run())


def test_textual_analyze_clear_selection_resets_planner_state() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="comment-code",
                    name="Commented-out code",
                    description="Detect commented-out code.",
                    category="code-quality",
                ),
            ],
            analysis_handlers={"run_comment_code_analysis": lambda _cfg: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-planner-section-analyzers")
            analyzers_list.select("comment-code")
            app_instance._sync_analyze_selection_from_selection_list(analyzers_list)
            app_instance._write_focused_entry_to_output()
            app_instance._refresh_shell_state()
            await pilot.pause()

            assert app_instance._analyze_selected_entry_ids == {"comment-code"}
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", True) is False

            app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="analyze-clear-selection")))
            await pilot.pause()

            assert app_instance._analyze_selected_entry_ids == set()
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", False) is True

    asyncio.run(_run())


def test_textual_analyze_clear_output_clears_session_log_only() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="comment-code",
                    name="Commented-out code",
                    description="Detect commented-out code.",
                    category="code-quality",
                ),
            ],
            analysis_handlers={"run_comment_code_analysis": lambda _cfg: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-planner-section-analyzers")
            analyzers_list.select("comment-code")
            app_instance._sync_analyze_selection_from_selection_list(analyzers_list)
            app_instance._write_focused_entry_to_output()
            app_instance._refresh_shell_state()
            app_instance._write_output("extra output")
            await pilot.pause()

            assert "comment-code" in app_instance._analyze_selected_entry_ids
            assert "Analyzer: Commented-out code" in getattr(app_instance.query_one("#output"), "text", "")

            app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="analyze-clear-output")))
            await pilot.pause()

            assert getattr(app_instance.query_one("#output"), "text", "") == ""
            assert "comment-code" in app_instance._analyze_selected_entry_ids
            assert str(app_instance.query_one("#output-title").renderable) == "Session output"

    asyncio.run(_run())


def test_textual_analyze_clear_selection_also_clears_output() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="comment-code",
                    name="Commented-out code",
                    description="Detect commented-out code.",
                    category="code-quality",
                ),
            ],
            analysis_handlers={"run_comment_code_analysis": lambda _cfg: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-planner-section-analyzers")
            analyzers_list.select("comment-code")
            app_instance._sync_analyze_selection_from_selection_list(analyzers_list)
            app_instance._write_focused_entry_to_output()
            app_instance._refresh_shell_state()
            app_instance._write_output("extra output")
            await pilot.pause()

            assert "comment-code" in app_instance._analyze_selected_entry_ids
            assert getattr(app_instance.query_one("#output"), "text", "") != ""

            app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="analyze-clear-selection")))
            await pilot.pause()

            assert app_instance._analyze_selected_entry_ids == set()
            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert "Analyzer: Commented-out code" not in output_text
            assert "extra output" not in output_text
            assert "Cleared the analyzer selection" in output_text

    asyncio.run(_run())


def test_textual_toolbar_key_switches_routed_view() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            assert str(app_instance.query_one("#view-title").renderable) == "Analyze"

            await pilot.press("ctrl+4")
            await pilot.pause()

            assert app_instance._active_view == "setup"
            assert str(app_instance.query_one("#view-title").renderable) == "Configuration Settings"
            assert app_instance.query_one("#view-actions").has_class("is-hidden") is True
            assert app_instance.query_one("#nav-tab-setup").has_class("nav-tab-active") is True

    asyncio.run(_run())


def test_textual_toolbar_keys_respect_busy_guard() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )
        opened_help: list[str] = []
        app_instance._open_help_popup = lambda: opened_help.append("help")  # type: ignore[method-assign]

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Analyzer checks"
            app_instance._refresh_shell_state()
            await pilot.pause()

            await pilot.press("ctrl+1")
            await pilot.press("ctrl+4")
            await pilot.pause()

            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert app_instance._active_view == "analyze"
            assert opened_help == []
            assert output_text.count("Another action is still running. Wait for it to finish first.") == 2

    asyncio.run(_run())


def test_textual_analyze_view_does_not_compose_secondary_actions_row() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})

        async with app_instance.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            assert app_instance.query_one("#analyze-actions-primary") is not None
            assert len(list(app_instance.query("#analyze-actions-secondary"))) == 0

    asyncio.run(_run())


def test_textual_setup_view_shows_selected_target_preview(tmp_path: Path) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        program_dir = tmp_path / "programs"
        abb_dir = tmp_path / "abb"
        program_dir.mkdir()
        abb_dir.mkdir()
        (program_dir / "TargetA.s").write_text("draft")
        (program_dir / "TargetA.l").write_text("deps")
        (abb_dir / "TargetA.x").write_text("official")

        cfg = {
            "analyzed_programs_and_libraries": [],
            "program_dir": str(program_dir),
            "ABB_lib_dir": str(abb_dir),
            "other_lib_dirs": [],
            "mode": "draft",
        }
        app_instance = app_textual.SattLintTextualApp(
            cfg=cfg,
            summarize_targets_fn=lambda _cfg: "targets",
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )
        _attach_test_project(app_instance)

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+4")
            await pilot.pause()

            workspace_host = app_instance.query_one("#workspace-host")
            view_title = app_instance.query_one("#view-title")
            output_pane = app_instance.query_one("#output-pane")
            browse_button = app_instance.query_one("#setup-target-browse")
            remove_button = app_instance.query_one("#setup-target-remove")
            program_button = app_instance.query_one("#setup-edit-program-dir")
            targets_col = app_instance.query_one("#setup-targets-col")
            settings_col = app_instance.query_one("#setup-settings-col")
            assert app_instance._active_view == "setup"
            assert workspace_host.has_class("no-output")
            assert str(view_title.renderable) == "Configuration Settings"
            assert output_pane.has_class("is-hidden") is True
            assert app_instance.query_one("#setup-browser").has_class("is-hidden") is False
            assert app_instance.query_one("#view-actions").has_class("is-hidden") is True
            assert str(getattr(browse_button, "label", "")) == "Add from file..."
            assert str(getattr(program_button, "label", "")) == "Program folder"
            assert targets_col is not None
            assert settings_col is not None
            assert str(app_instance.query_one("#setup-label-program-dir").renderable) == (
                f"{program_dir.name}\n{program_dir}"
            )
            assert str(app_instance.query_one("#setup-label-abb-dir").renderable) == f"{abb_dir.name}\n{abb_dir}"
            assert str(app_instance.query_one("#setup-label-other-dirs").renderable) == "No extra libraries"
            assert str(app_instance.query_one("#setup-label-icf-dir").renderable) == "Not configured"
            assert str(app_instance.query_one("#setup-label-mode").renderable) == "Draft mode\n.s and .l files"

            targets_section = app_instance.query_one("#setup-targets-section")
            settings_section = app_instance.query_one("#setup-settings-section")
            assert targets_section.region.x < settings_section.region.x
            assert targets_col.region.width > 0
            assert settings_col.region.width > 0
            assert browse_button.region.x >= targets_col.region.x
            assert browse_button.region.x < settings_col.region.x
            # Remove is disabled when nothing is selected
            assert getattr(remove_button, "disabled", False) is True

    asyncio.run(_run())


def test_textual_setup_shows_empty_dirs_when_no_configuration_is_open() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        cfg = {
            "analyzed_programs_and_libraries": [],
            "program_dir": "/some/program/dir",
            "ABB_lib_dir": "/some/abb",
            "other_lib_dirs": ["/some/lib1"],
            "icf_dir": "/some/icf",
            "mode": "official",
        }
        app_instance = app_textual.SattLintTextualApp(
            cfg=cfg,
            summarize_targets_fn=lambda _cfg: "targets",
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+4")
            await pilot.pause()

            assert app_instance._project_loaded() is False
            for label_id in (
                "setup-label-program-dir",
                "setup-label-abb-dir",
                "setup-label-other-dirs",
                "setup-label-icf-dir",
            ):
                assert str(app_instance.query_one(f"#{label_id}").renderable) == ""

    asyncio.run(_run())


def test_textual_settings_view_shows_app_settings_and_edits_config() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        cfg = {
            "analyzed_programs_and_libraries": ["TargetA"],
            "debug": False,
            "run_history": {"enabled": True, "limit": 50},
            "output": {"retention_lines": 4000},
        }
        app_instance = _make_textual_app(cfg=cfg)

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+2")
            await pilot.pause()

            assert app_instance._active_view == "settings"
            settings_browser = app_instance.query_one("#settings-browser")
            output_pane = app_instance.query_one("#output-pane")
            assert settings_browser.has_class("is-hidden") is False
            assert output_pane.has_class("is-hidden") is True
            assert str(app_instance.query_one("#settings-label-run-history").renderable).startswith("Enabled")
            assert "50" in str(app_instance.query_one("#settings-label-run-history-limit").renderable)
            assert str(app_instance.query_one("#settings-label-debug").renderable).startswith("Disabled")
            assert "4000" in str(app_instance.query_one("#settings-label-output-retention").renderable)

            app_instance._toggle_app_debug()
            await pilot.pause()

            assert cfg["debug"] is True
            assert app_instance._dirty is True
            assert str(app_instance.query_one("#settings-label-debug").renderable).startswith("Enabled")

    asyncio.run(_run())


def test_textual_results_view_lists_runs_and_renders_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    record = RunRecord(
        run_id="run1",
        started_at="2026-09-06T10:00:00Z",
        finished_at="2026-09-06T10:05:00Z",
        project_tag="TargetA",
        selected_analyzers=("variables",),
        targets=(
            RunTargetRecord(
                target_name="TargetA",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(
                            AnalysisFinding(
                                kind="unused",
                                message="declared but never read",
                                module_path=("TargetA",),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        output_lines=("=== Target: TargetA ===", "state inference summary"),
    )
    summary = RunSummary.from_record(record)

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})
        monkeypatch.setattr(app_textual_results_module, "list_runs", lambda: (summary,))
        monkeypatch.setattr(app_textual_results_module, "load_run", lambda run_id: record if run_id == "run1" else None)

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+3")
            await pilot.pause()

            assert app_instance._active_view == "results"
            results_browser = app_instance.query_one("#results-browser")
            assert results_browser.has_class("is-hidden") is False
            assert len(list(app_instance.query_one("#results-tree-host").children)) == 1

            tree = app_instance._results_tree_widget
            assert tree is not None
            assert tree.root.is_expanded is True
            target_node = tree.root.children[0]
            analyzer_node = next(iter(target_node.children))
            assert target_node.is_expanded is False

            app_instance._collapse_all_results()
            await pilot.pause()
            assert tree.root.is_expanded is False

            app_instance._expand_all_results()
            await pilot.pause()
            assert tree.root.is_expanded is True
            assert target_node.is_expanded is True
            assert analyzer_node.is_expanded is True

    asyncio.run(_run())


def test_textual_analysis_completion_switches_to_results_view(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    record = RunRecord(run_id="run9", started_at="s", finished_at="f", project_tag="TargetA")
    summary = RunSummary.from_record(record)

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})
        monkeypatch.setattr(app_textual_results_module, "list_runs", lambda: (summary,))
        monkeypatch.setattr(app_textual_results_module, "load_run", lambda _run_id: record)

        async with app_instance.run_test() as pilot:
            assert app_instance._active_view == "analyze"

            result = SimpleNamespace(
                output_lines=("=== Target: TargetA ===", "state inference summary"),
                targets=(),
                selected_analyzers=("state-inference",),
                selected_issue_kinds=None,
            )
            app_instance._finish_analysis_run(result)
            await pilot.pause()

            assert app_instance._active_view == "results"
            assert app_instance._selected_run_record is not None
            assert app_instance._selected_run_record.run_id == "run9"

    asyncio.run(_run())


def test_textual_setup_browse_shows_discovered_targets_once(tmp_path: Path) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        program_dir = tmp_path / "programs"
        abb_dir = tmp_path / "abb"
        program_dir.mkdir()
        abb_dir.mkdir()
        (program_dir / "TargetA.s").write_text("draft")
        (program_dir / "TargetA.l").write_text("deps")
        (abb_dir / "TargetA.x").write_text("official")

        app_instance = _make_textual_app(
            cfg={
                "analyzed_programs_and_libraries": [],
                "program_dir": str(program_dir),
                "ABB_lib_dir": str(abb_dir),
                "other_lib_dirs": [],
                "mode": "draft",
            }
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+4")
            await pilot.pause()

            browse_button = app_instance.query_one("#setup-target-browse")
            app_instance.on_button_pressed(SimpleNamespace(button=browse_button))
            await pilot.pause()

            target_list = _query_any_screen(app_instance, "#file-browser-targets")
            list_items = list(target_list.query("ListItem"))
            selection_text = str(_query_any_screen(app_instance, "#file-browser-selection").renderable)

            assert _query_any_screen(app_instance, "#file-browser-dialog") is not None
            assert len(list_items) == 1
            assert "TargetA" in str(getattr(list_items[0].query_one("Static"), "renderable", ""))
            assert "TargetA.s" not in selection_text
            assert "TargetA.l" not in selection_text
            assert "TargetA.x" not in selection_text
            assert "TargetA" in selection_text
            assert (
                str(getattr(_query_any_screen(app_instance, "#file-browser-browse-filesystem"), "label", ""))
                == "Browse filesystem"
            )

    asyncio.run(_run())


def test_textual_shell_does_not_write_startup_ast_cache_output() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(project=False)

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert "Initial AST loading log:" not in output_text
            assert "AST cache" not in output_text
            assert "Welcome to SattLint." in output_text

    asyncio.run(_run())


def test_textual_setup_target_button_click_adds_and_removes_target(tmp_path: Path) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        program_dir = tmp_path / "programs"
        program_dir.mkdir()
        (program_dir / "TargetA.s").write_text("draft")

        cfg = {
            "analyzed_programs_and_libraries": [],
            "program_dir": str(program_dir),
            "ABB_lib_dir": "",
            "other_lib_dirs": [],
            "mode": "draft",
        }
        app_instance = app_textual.SattLintTextualApp(
            cfg=cfg,
            summarize_targets_fn=lambda _cfg: "targets",
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+4")
            await pilot.pause()

            # Add target programmatically (file browser not testable in headless mode)
            app_instance._add_selected_setup_target("TargetA")
            await pilot.pause()

            assert cfg["analyzed_programs_and_libraries"] == ["TargetA"]

            # Select target via _selected_configured_target (simulating ListView highlight)
            app_instance._selected_configured_target = "TargetA"
            await pilot.pause()

            assert app_instance._selected_configured_target == "TargetA"

            # Click remove to remove the selected target
            remove_button = app_instance.query_one("#setup-target-remove")
            app_instance.on_button_pressed(SimpleNamespace(button=remove_button))
            await pilot.pause()

            assert cfg["analyzed_programs_and_libraries"] == []
            assert app_instance._selected_configured_target is None

    asyncio.run(_run())


def test_textual_setup_add_selected_target_marks_dirty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    program_dir = tmp_path / "programs"
    program_dir.mkdir()
    (program_dir / "TargetA.s").write_text("draft")

    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": str(program_dir),
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    messages: list[str] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    app_instance._active_view = "setup"
    original_targets = cfg["analyzed_programs_and_libraries"]

    app_instance._add_selected_setup_target()

    assert cfg["analyzed_programs_and_libraries"] == ["TargetA"]
    assert cfg["analyzed_programs_and_libraries"] is not original_targets
    assert app_instance._dirty is True
    assert messages == ["Added analysis target 'TargetA' from the Setup view."]


def test_textual_setup_remove_selected_target_marks_dirty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    program_dir = tmp_path / "programs"
    program_dir.mkdir()
    (program_dir / "TargetA.s").write_text("draft")

    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": ["TargetA"],
        "program_dir": str(program_dir),
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    messages: list[str] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    app_instance._active_view = "setup"
    original_targets = cfg["analyzed_programs_and_libraries"]

    app_instance._remove_selected_setup_target()

    assert cfg["analyzed_programs_and_libraries"] == []
    assert cfg["analyzed_programs_and_libraries"] is not original_targets
    assert app_instance._dirty is True
    assert messages == ["Removed analysis target 'TargetA' from the Setup view."]


def test_textual_setup_remove_other_lib_dir_presents_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "",
        "ABB_lib_dir": "",
        "other_lib_dirs": ["/libs/one", "/libs/two", "/libs/three"],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    captured: dict[str, object] = {}
    messages: list[str] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))

    def _capture_request(
        request: app_textual_shared_module.InteractionRequest, on_response_fn: object | None = None
    ) -> None:
        captured["request"] = request
        captured["callback"] = on_response_fn

    monkeypatch.setattr(app_instance, "present_request", _capture_request)

    app_instance._remove_other_lib_dir()

    request = captured["request"]
    assert isinstance(request, app_textual_shared_module.InteractionRequest)
    assert request.kind == "menu"
    assert [option.label for option in request.options] == ["/libs/one", "/libs/two", "/libs/three"]

    callback = captured["callback"]
    assert callable(callback)
    callback("2")

    assert cfg["other_lib_dirs"] == ["/libs/one", "/libs/three"]
    assert app_instance._dirty is True
    assert messages == ["Removed extra library folder '/libs/two' from the Setup view."]


def test_textual_setup_remove_other_lib_dir_ignores_invalid_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "",
        "ABB_lib_dir": "",
        "other_lib_dirs": ["/libs/one", "/libs/two"],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    captured: dict[str, object] = {}
    messages: list[str] = []
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))

    def _capture_request(
        request: app_textual_shared_module.InteractionRequest, on_response_fn: object | None = None
    ) -> None:
        captured["request"] = request
        captured["callback"] = on_response_fn

    monkeypatch.setattr(app_instance, "present_request", _capture_request)

    app_instance._remove_other_lib_dir()
    callback = captured["callback"]
    assert callable(callback)
    callback("9")
    callback("abc")
    callback(None)

    assert cfg["other_lib_dirs"] == ["/libs/one", "/libs/two"]
    assert messages == []


def test_textual_setup_remove_other_lib_dir_empty_writes_message(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "",
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    messages: list[str] = []
    captured: dict[str, object] = {}

    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    monkeypatch.setattr(app_instance, "present_request", lambda *args, **kwargs: captured.setdefault("called", True))

    app_instance._remove_other_lib_dir()

    assert "called" not in captured
    assert messages == ["No extra library folders are configured to remove."]


def test_textual_setup_remove_other_lib_dir_button_state() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            cfg={
                "analyzed_programs_and_libraries": [],
                "program_dir": "",
                "ABB_lib_dir": "",
                "other_lib_dirs": [],
                "mode": "draft",
            }
        )
        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+4")
            await pilot.pause()
            assert getattr(app_instance.query_one("#setup-edit-other-lib-dirs-remove"), "disabled", False) is True

    asyncio.run(_run())


def test_textual_setup_remove_other_lib_dir_button_enabled_with_entries() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            cfg={
                "analyzed_programs_and_libraries": [],
                "program_dir": "",
                "ABB_lib_dir": "",
                "other_lib_dirs": ["/libs/one"],
                "mode": "draft",
            }
        )
        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+4")
            await pilot.pause()
            assert getattr(app_instance.query_one("#setup-edit-other-lib-dirs-remove"), "disabled", False) is False

    asyncio.run(_run())


def test_textual_setup_prompt_updates_program_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "/old/programs",
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    captured: dict[str, object] = {}
    messages: list[str] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))

    def _capture_request(
        request: app_textual_shared_module.InteractionRequest, on_response_fn: object | None = None
    ) -> None:
        captured["request"] = request
        captured["callback"] = on_response_fn

    monkeypatch.setattr(app_instance, "present_request", _capture_request)

    app_instance._prompt_setup_value("program_dir", label="program_dir")

    request = captured["request"]
    assert isinstance(request, app_textual_shared_module.InteractionRequest)
    assert request.kind == "prompt"
    assert request.default == "/old/programs"

    callback = captured["callback"]
    assert callable(callback)
    callback("/new/programs")

    assert cfg["program_dir"] == "/new/programs"
    assert app_instance._dirty is True
    assert messages == ["Updated program_dir from the Setup view."]


def test_textual_setup_prompt_replaces_whole_other_lib_dirs_list(monkeypatch: pytest.MonkeyPatch) -> None:
    original_other_dirs = ["/old/lib-a", "/old/lib-b"]
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "/old/programs",
        "ABB_lib_dir": "",
        "other_lib_dirs": original_other_dirs,
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    captured: dict[str, object] = {}
    messages: list[str] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))

    def _capture_request(
        request: app_textual_shared_module.InteractionRequest, on_response_fn: object | None = None
    ) -> None:
        captured["request"] = request
        captured["callback"] = on_response_fn

    monkeypatch.setattr(app_instance, "present_request", _capture_request)

    app_instance._prompt_setup_value("other_lib_dirs", label="other_lib_dirs", is_list=True)

    request = captured["request"]
    assert isinstance(request, app_textual_shared_module.InteractionRequest)
    assert request.kind == "prompt"
    assert request.message == "Enter the full comma-separated list for other_lib_dirs. Leave blank to clear the list."
    assert request.default == "/old/lib-a, /old/lib-b"

    callback = captured["callback"]
    assert callable(callback)
    callback("/new/lib-a, /new/lib-b")

    assert cfg["other_lib_dirs"] == ["/new/lib-a", "/new/lib-b"]
    assert cfg["other_lib_dirs"] is not original_other_dirs
    assert app_instance._dirty is True
    assert messages == ["Updated other_lib_dirs from the Setup view."]


def test_textual_setup_dir_picker_pushes_browser_and_applies_program_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")
    program_dir = tmp_path / "programs"
    program_dir.mkdir()
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "",
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    messages: list[str] = []
    pushed: list[tuple[Any, Any]] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append((screen, callback)))

    app_instance._open_dir_picker("program_dir", label="program_dir")

    assert len(pushed) == 1
    screen, callback = pushed[0]
    assert isinstance(screen, app_textual_widgets_module._FileBrowserScreen)
    assert screen._directory_only is True
    assert callable(callback)

    callback(program_dir)
    assert cfg["program_dir"] == str(program_dir)
    assert app_instance._dirty is True
    assert messages == ["Updated program_dir from the Setup view."]


def test_textual_setup_dir_picker_ignores_non_path_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "/existing",
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    pushed: list[tuple[Any, Any]] = []
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append((screen, callback)))

    app_instance._open_dir_picker("program_dir", label="program_dir")
    _, callback = pushed[0]
    callback("not-a-path")
    assert cfg["program_dir"] == "/existing"


def test_textual_setup_dir_picker_appends_to_other_lib_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")
    extra_dir = tmp_path / "extra"
    extra_dir.mkdir()
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "",
        "ABB_lib_dir": "",
        "other_lib_dirs": ["/old/lib"],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    messages: list[str] = []
    pushed: list[tuple[Any, Any]] = []
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append((screen, callback)))

    app_instance._open_dir_picker("other_lib_dirs", label="other_lib_dirs", is_list=True)
    _, callback = pushed[0]
    callback(extra_dir)
    assert cfg["other_lib_dirs"] == ["/old/lib", str(extra_dir)]
    assert messages == ["Updated other_lib_dirs from the Setup view."]


def test_textual_activate_view_leaves_dirty_setup_changes_unsaved(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = _make_textual_app()
    app_instance._active_view = "setup"
    app_instance._dirty = True
    started: list[str] = []

    monkeypatch.setattr(app_instance, "_start_action", lambda *args, **kwargs: started.append("save"))
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)

    app_instance._activate_view("help")

    assert started == []
    assert app_instance._active_view == "help"
    assert app_instance._dirty is True


def test_textual_finish_action_clears_dirty_after_success() -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    app_instance._dirty = True
    app_instance._set_active_action = lambda _action_id: None  # type: ignore[method-assign]
    app_instance._refresh_summary = lambda: None  # type: ignore[method-assign]

    app_instance._finish_action(clear_dirty_on_success=True)

    assert app_instance._dirty is False


def test_textual_quit_action_respects_busy_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    messages: list[str] = []
    exited: list[str] = []
    app_instance._busy = True

    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    monkeypatch.setattr(app_instance, "exit", lambda: exited.append("exit"))

    app_instance._handle_toolbar_action("action-quit")

    assert exited == []
    assert messages == ["An action is still running. Wait for it to finish before quitting."]


def test_textual_write_output_preserves_blank_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    written: list[object] = []
    scrolled: list[bool] = []

    class FakeRichOutput:
        text = ""

        def append_plain_text(self, text: str) -> None:
            self.text += text

        def write(self, renderable: object, **_kwargs: Any) -> None:
            written.append(renderable)

        def scroll_end(self, animate: bool = False) -> None:
            scrolled.append(bool(animate))

    fake_widget = FakeRichOutput()

    monkeypatch.setattr(app_instance, "query_one", lambda *_args, **_kwargs: fake_widget)

    app_instance._write_output("Summary\n\nDetails")

    assert fake_widget.text == "Summary\n\nDetails\n"
    assert scrolled == [False]


def test_textual_write_output_inserts_spacing_before_target_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    written: list[object] = []
    scrolled: list[bool] = []

    class FakeRichOutput:
        def __init__(self) -> None:
            self.text = ""

        def append_plain_text(self, text: str) -> None:
            self.text += text

        def write(self, renderable: object, **_kwargs: Any) -> None:
            written.append(renderable)

        def scroll_end(self, animate: bool = False) -> None:
            scrolled.append(bool(animate))

    fake_widget = FakeRichOutput()

    monkeypatch.setattr(app_instance, "query_one", lambda *_args, **_kwargs: fake_widget)

    app_instance._write_output("Analyze planner queue")
    app_instance._write_output("=== Target: DemoLib ===")

    assert fake_widget.text == "Analyze planner queue\n=== Target: DemoLib ===\n"
    assert isinstance(written[0], Text)
    assert str(written[0]) == "Analyze planner queue"
    assert written[1] == ""
    assert isinstance(written[2], Rule)


def test_textual_write_output_caps_retained_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )

    class FakeRichOutput:
        def __init__(self) -> None:
            self.text = ""
            self._plain_text_parts: list[str] = []

        def clear(self) -> None:
            self.text = ""

        def append_plain_text(self, text: str) -> None:
            self._plain_text_parts.append(text)
            self.text += text

        def write(self, _renderable: object, **_kwargs: Any) -> None:
            return None

        def scroll_end(self, animate: bool = False) -> None:
            return None

    fake_widget = FakeRichOutput()

    monkeypatch.setattr(app_instance, "query_one", lambda *_args, **_kwargs: fake_widget)

    app_instance._write_output("\n".join(f"line {index}" for index in range(4005)))

    assert len(app_instance._session_output_lines) == 4000
    assert app_instance._session_output_lines[0] == "line 5"
    assert app_instance._session_output_dropped_line_count == 5
    assert app_instance._output_title_text() == "Session output - retaining last 4000 lines"
    assert fake_widget.text.startswith("line 5\n")
    assert "line 4\n" not in fake_widget.text


def test_textual_app_uses_explicit_mixins() -> None:
    assert issubclass(app_textual_module.SattLintTextualApp, app_textual_actions_module._TextualActionsMixin)
    assert issubclass(app_textual_module.SattLintTextualApp, app_textual_setup_module._TextualSetupMixin)
    assert issubclass(app_textual_module.SattLintTextualApp, app_textual_module._TextualAnalyzeMixin)
    assert issubclass(app_textual_module.SattLintTextualApp, app_textual_settings_module._TextualSettingsMixin)


def test_textual_refresh_view_raises_when_required_widget_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            def _raise_missing(*_args: Any, **_kwargs: Any) -> object:
                raise app_textual_actions_module._TEXTUAL_QUERY_ERRORS[0]("missing view host")

            monkeypatch.setattr(app_instance, "query_exactly_one", _raise_missing, raising=False)
            monkeypatch.setattr(app_instance, "query_one", _raise_missing)

            with pytest.raises(app_textual_actions_module._TEXTUAL_QUERY_ERRORS[0], match="missing view host"):
                app_instance._refresh_view()

    asyncio.run(_run())


def test_textual_file_browser_selection_raises_when_required_widgets_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    browser = app_textual_widgets_module._FileBrowserScreen(
        start_paths=[Path(".")],
        candidates=(("demo", ("demo.x",)),),
    )

    def _raise_missing(*_args: Any, **_kwargs: Any) -> object:
        raise LookupError("missing file browser widget")

    monkeypatch.setattr(browser, "query_exactly_one", _raise_missing, raising=False)
    monkeypatch.setattr(browser, "query_one", _raise_missing)

    with pytest.raises(LookupError, match="missing file browser widget"):
        browser._set_candidate_selection(None)


def test_textual_file_browser_select_labels_folder_when_filtering_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    browser = app_textual_widgets_module._FileBrowserScreen(start_paths=[tmp_path], file_suffix=".slproj")
    select_button = SimpleNamespace(label="Select", disabled=True)
    widgets: dict[str, object] = {
        "#file-browser-selection": SimpleNamespace(update=lambda text: None),
        "#file-browser-select": select_button,
    }
    monkeypatch.setattr(
        app_textual_widgets_module,
        "_query_required",
        lambda _owner, selector, _expected_type=None: widgets[selector],
    )

    browser._update_selection(tmp_path)

    assert select_button.label == "Open folder"
    assert select_button.disabled is False


def test_textual_file_browser_select_navigates_into_folder_when_filtering_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    folder = tmp_path / "OG-batchrapporter"
    folder.mkdir()
    (folder / ".slproj").write_text("slproj_version = 1\n")

    browser = app_textual_widgets_module._FileBrowserScreen(start_paths=[tmp_path], file_suffix=".slproj")
    dismissed: list[object] = []
    tree = SimpleNamespace(path=None)
    widgets: dict[str, object] = {
        "#file-browser-tree": tree,
        "#file-browser-selection": SimpleNamespace(update=lambda text: None),
        "#file-browser-select": SimpleNamespace(label="Select", disabled=True),
    }
    monkeypatch.setattr(
        app_textual_widgets_module,
        "_query_required",
        lambda _owner, selector, _expected_type=None: widgets[selector],
    )
    browser.dismiss = lambda result: dismissed.append(result)

    browser._current_path = folder
    browser.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="file-browser-select")))

    assert dismissed == []
    assert tree.path == folder
    assert browser._current_path is None


def test_textual_file_browser_select_dismisses_file_when_filtering_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    project_file = tmp_path / "demo.slproj"
    project_file.write_text("slproj_version = 1\n")

    browser = app_textual_widgets_module._FileBrowserScreen(start_paths=[tmp_path], file_suffix=".slproj")
    dismissed: list[object] = []
    widgets: dict[str, object] = {
        "#file-browser-selection": SimpleNamespace(update=lambda text: None),
        "#file-browser-select": SimpleNamespace(label="Select", disabled=True),
    }
    monkeypatch.setattr(
        app_textual_widgets_module,
        "_query_required",
        lambda _owner, selector, _expected_type=None: widgets[selector],
    )
    browser.dismiss = lambda result: dismissed.append(result)

    browser._current_path = project_file
    browser.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="file-browser-select")))

    assert dismissed == [project_file]


def test_textual_file_browser_directory_only_disables_select_for_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    browser = app_textual_widgets_module._FileBrowserScreen(start_paths=[tmp_path], directory_only=True)
    file_path = tmp_path / "Program.s"
    file_path.write_text("draft")
    select_button = SimpleNamespace(label="Select", disabled=True)
    widgets: dict[str, object] = {
        "#file-browser-selection": SimpleNamespace(update=lambda text: None),
        "#file-browser-select": select_button,
    }
    monkeypatch.setattr(
        app_textual_widgets_module,
        "_query_required",
        lambda _owner, selector, _expected_type=None: widgets[selector],
    )

    browser._update_selection(file_path)
    assert select_button.disabled is True

    browser._update_selection(tmp_path)
    assert select_button.label == "Select folder"
    assert select_button.disabled is False


def test_textual_file_browser_directory_only_ignores_file_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    browser = app_textual_widgets_module._FileBrowserScreen(start_paths=[tmp_path], directory_only=True)
    file_path = tmp_path / "Program.s"
    file_path.write_text("draft")
    dismissed: list[object] = []
    browser.dismiss = lambda result: dismissed.append(result)

    browser.on_directory_tree_file_selected(SimpleNamespace(path=file_path))
    assert dismissed == []

    browser.on_directory_tree_file_selected(SimpleNamespace(path=tmp_path))
    assert dismissed == [tmp_path]


def test_textual_file_browser_directory_only_tree_hides_files(tmp_path: Path) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    subdir = tmp_path / "sub"
    subdir.mkdir()
    file_path = tmp_path / "Program.s"
    file_path.write_text("draft")

    class _TreeHost(app_textual_shared_module._TEXTUAL_APP):
        def compose(self) -> Any:
            yield app_textual_widgets_module._FilteredDirectoryTree(
                str(tmp_path), directory_only=True, id="file-browser-tree"
            )

    async def _run() -> None:
        async with _TreeHost().run_test() as pilot:
            await pilot.pause()
            tree = pilot.app.query_one("#file-browser-tree")
            result = list(tree.filter_paths([subdir, file_path]))
            assert result == [subdir]

    asyncio.run(_run())


def test_textual_file_browser_directory_only_go_up_navigates_to_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    browser = app_textual_widgets_module._FileBrowserScreen(start_paths=[Path("/home/sorenhj")], directory_only=True)
    tree = SimpleNamespace(path="/home/sorenhj")
    select_button = SimpleNamespace(label="Select folder", disabled=True)
    up_button = SimpleNamespace(disabled=True)
    widgets: dict[str, object] = {
        "#file-browser-tree": tree,
        "#file-browser-selection": SimpleNamespace(update=lambda text: None),
        "#file-browser-select": select_button,
        "#file-browser-up": up_button,
    }
    monkeypatch.setattr(
        app_textual_widgets_module,
        "_query_required",
        lambda _owner, selector, _expected_type=None: widgets[selector],
    )

    browser.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="file-browser-up")))

    assert str(tree.path) == "/home"
    assert browser._current_path == Path("/home")
    assert select_button.label == "Select folder"
    assert select_button.disabled is False
    assert up_button.disabled is False


def test_textual_file_browser_directory_only_up_button_disabled_at_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    browser = app_textual_widgets_module._FileBrowserScreen(start_paths=[Path("/")], directory_only=True)
    tree = SimpleNamespace(path="/")
    up_button = SimpleNamespace(disabled=False)
    widgets: dict[str, object] = {
        "#file-browser-tree": tree,
        "#file-browser-selection": SimpleNamespace(update=lambda text: None),
        "#file-browser-select": SimpleNamespace(label="Select folder", disabled=True),
        "#file-browser-up": up_button,
    }
    monkeypatch.setattr(
        app_textual_widgets_module,
        "_query_required",
        lambda _owner, selector, _expected_type=None: widgets[selector],
    )

    browser._refresh_up_button(Path("/"))
    assert up_button.disabled is True

    browser.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="file-browser-up")))
    assert tree.path == "/"
    assert browser._current_path is None


@pytest.mark.parametrize(
    "button_id, field_key, is_list",
    [
        ("setup-edit-program-dir", "program_dir", False),
        ("setup-edit-abb-dir", "ABB_lib_dir", False),
        ("setup-edit-other-lib-dirs", "other_lib_dirs", True),
        ("setup-edit-icf-dir", "icf_dir", False),
    ],
)
def test_textual_setup_dir_buttons_push_directory_only_picker(
    monkeypatch: pytest.MonkeyPatch, button_id: str, field_key: str, is_list: bool
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "",
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "icf_dir": "",
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    pushed: list[tuple[Any, Any]] = []
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append((screen, callback)))

    app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id=button_id)))

    assert len(pushed) == 1
    screen, _callback = pushed[0]
    assert isinstance(screen, app_textual_widgets_module._FileBrowserScreen)
    assert screen._directory_only is True


def test_textual_toolbar_actions_are_ignored_while_interaction_screen_is_open(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    started: list[str] = []

    monkeypatch.setattr(app_instance, "_interaction_screen_active", lambda: True)
    monkeypatch.setattr(app_instance, "_start_action", lambda *args, **kwargs: started.append("started"))

    app_instance._handle_toolbar_action("action-analyze")

    assert started == []


def test_textual_new_project_creates_project_in_projects_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    projects_dir = Path(tempfile.mkdtemp(prefix="sattlint-projects-"))
    monkeypatch.setattr(
        "sattlint.config.paths.get_projects_dir",
        lambda: projects_dir,
    )

    app_instance = _make_textual_app(project=False)
    captured: dict[str, object] = {}
    messages: list[str] = []
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_clear_session_output", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))

    def _capture_request(
        request: app_textual_shared_module.InteractionRequest, on_response_fn: object | None = None
    ) -> None:
        captured["request"] = request
        captured["callback"] = on_response_fn

    monkeypatch.setattr(app_instance, "present_request", _capture_request)

    app_instance._new_project()

    request = captured["request"]
    assert isinstance(request, app_textual_shared_module.InteractionRequest)
    assert request.kind == "prompt"
    assert "stored in" in (request.note or "")

    callback = captured["callback"]
    assert callable(callback)
    callback("My Demo Project")

    project_file = projects_dir / "My Demo Project.slproj"
    assert project_file.is_file()
    assert not (projects_dir / "My-Demo-Project").exists()
    assert app_instance._project is not None
    assert app_instance._project_loaded() is True
    assert app_instance._config_path == project_file
    assert "Created configuration" in messages[0]

    # Reject duplicate project names.
    callback(None)
    callback("My Demo Project")
    assert any("already exists" in message for message in messages)


def test_textual_setup_change_autosaves_to_slproj(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = _make_textual_app()
    project_path = app_instance._project.path

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: None)
    app_instance._active_view = "setup"

    app_instance._cfg["program_dir"] = "/some/program/dir"
    app_instance._mark_setup_changed("updated")

    assert app_instance._dirty is False
    saved = load_project(project_path)
    assert saved.data["program_dir"] == "/some/program/dir"
    assert "slproj_version" in saved.data


def test_textual_open_project_loads_and_unlocks_views(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = _make_textual_app(project=False)
    assert app_instance._project_loaded() is False

    monkeypatch.setattr(app_instance, "_clear_session_output", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)

    project_dir = Path(tempfile.mkdtemp(prefix="sattlint-open-project-"))
    project = init_project(project_dir / ".slproj", name="OpenedProject")
    project.data["analyzed_programs_and_libraries"] = ["TargetA"]

    app_instance._load_project_object(project)

    assert app_instance._project_loaded() is True
    assert app_instance._config_path == project.path
    assert app_instance._cfg["analyzed_programs_and_libraries"] == ["TargetA"]


def test_textual_open_project_refreshes_ast_cache_before_interaction(monkeypatch: pytest.MonkeyPatch) -> None:
    refreshed_cfgs: list[object] = []
    app_instance = _make_textual_app(
        project=False,
        ensure_ast_cache_fn=lambda _cfg, *, emit_output_fn=None: (
            refreshed_cfgs.append(_cfg),
            emit_output_fn("Checking AST cache for Demo") if emit_output_fn is not None else None,
            True,
        )[2],
    )

    monkeypatch.setattr(app_instance, "_clear_session_output", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda _text: None)
    pushed: list[tuple[Any, Any]] = []
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append((screen, callback)))

    project_dir = Path(tempfile.mkdtemp(prefix="sattlint-open-project-"))
    project = init_project(project_dir / ".slproj", name="OpenedProject")
    project.data["analyzed_programs_and_libraries"] = ["TargetA"]

    app_instance._load_project_object(project)

    assert app_instance._ast_refresh_pending is True
    assert len(pushed) == 1
    screen, callback = pushed[0]
    assert isinstance(screen, app_textual_widgets_module._AstRefreshModalScreen)
    assert callable(callback)

    screen._refresh_fn(lambda _message: None)

    assert refreshed_cfgs == [app_instance._cfg]

    result = app_textual_widgets_module._AstRefreshModalResult(ok=True, output="Checking AST cache for Demo")
    callback(result)

    assert app_instance._ast_refresh_pending is False
    assert app_instance._interaction_locked() is False


def test_textual_open_project_without_targets_skips_ast_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = _make_textual_app(
        project=False,
        ensure_ast_cache_fn=lambda _cfg, *, emit_output_fn=None: True,
    )
    monkeypatch.setattr(app_instance, "_clear_session_output", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    pushed: list[tuple[Any, Any]] = []
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append((screen, callback)))

    project_dir = Path(tempfile.mkdtemp(prefix="sattlint-open-project-"))
    project = init_project(project_dir / ".slproj", name="EmptyProject")

    app_instance._load_project_object(project)

    assert pushed == []
    assert app_instance._ast_refresh_pending is False
    assert app_instance._interaction_locked() is False


def test_sanitize_project_name_preserves_spaces_and_strips_path_separators() -> None:
    assert app_textual_actions_module._sanitize_project_name("OG batchrapporter") == "OG batchrapporter"
    assert app_textual_actions_module._sanitize_project_name("  My   Project  ") == "My   Project"
    assert app_textual_actions_module._sanitize_project_name("a/b\\c") == "a-b-c"
    assert app_textual_actions_module._sanitize_project_name("  ") == "project"


def test_textual_menu_definitions_have_open_and_new_but_not_save() -> None:
    labels = [label for label, _action_id in app_textual_shared_module.MENU_DEFINITIONS]
    assert "Open Configuration" in labels
    assert "New Configuration" in labels
    assert "Save Configuration" not in labels
    action_ids = [action_id for _label, action_id in app_textual_shared_module.MENU_DEFINITIONS]
    assert "menu-file-open-project" in action_ids
    assert "menu-file-new-project" in action_ids
    assert "menu-file-save-project" not in action_ids


def test_textual_no_project_gates_analyze_setup_and_results() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(project=False)

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            assert app_instance._project_loaded() is False
            planner_notice = str(next(iter(app_instance.query_one("#analyze-browser-left").children)).renderable)
            assert "No configuration is open" in planner_notice
            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", False) is True

            await pilot.press("ctrl+4")
            await pilot.pause()
            setup_item = next(iter(app_instance.query_one("#setup-target-listview").children))
            setup_notice = str(next(iter(setup_item.children)).renderable)
            assert "No configuration is open" in setup_notice
            assert getattr(app_instance.query_one("#setup-edit-program-dir"), "disabled", False) is True
            assert getattr(app_instance.query_one("#setup-edit-abb-dir"), "disabled", False) is True
            assert getattr(app_instance.query_one("#setup-edit-other-lib-dirs"), "disabled", False) is True
            assert getattr(app_instance.query_one("#setup-edit-icf-dir"), "disabled", False) is True
            assert getattr(app_instance.query_one("#setup-toggle-mode"), "disabled", False) is True

            await pilot.press("ctrl+3")
            await pilot.pause()
            results_item = next(iter(app_instance.query_one("#results-runs-list").children))
            results_notice = str(next(iter(results_item.children)).renderable)
            assert "No configuration is open" in results_notice

            # Settings stays usable without a project.
            await pilot.press("ctrl+2")
            await pilot.pause()
            assert getattr(app_instance.query_one("#settings-toggle-run-history"), "disabled", False) is False

    asyncio.run(_run())


@pytest.mark.integration
@pytest.mark.slow
def test_textual_shell_does_not_crash_within_window(tmp_path: Path) -> None:
    """End-to-end smoke test: launch the real ``sattlint`` CLI in a pseudo-terminal and assert
    the Textual shell is still alive after a bounded window.

    Guards the on-mount startup path (e.g. the ``_analysis_handlers`` wiring bug that crashed
    ``on_mount`` shortly after launch) which the in-process unit tests do not exercise.
    """
    if sys.platform == "win32":
        pytest.skip("pty-based subprocess smoke test is POSIX-only")
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    window_seconds = 5

    master, slave = pty.openpty()
    try:
        env = dict(os.environ)
        env["TERM"] = "xterm-256color"
        env["COLUMNS"] = "100"
        env["LINES"] = "30"
        process = subprocess.Popen(
            [sys.executable, "-m", "sattlint", "--ui", "textual"],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            cwd=tmp_path,
            close_fds=True,
            start_new_session=True,
        )
    finally:
        os.close(slave)

    try:
        deadline = time.monotonic() + window_seconds
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            readable, _, _ = select.select([master], [], [], 0.25)
            if readable:
                with contextlib.suppress(OSError):
                    os.read(master, 4096)

        assert process.poll() is None, (
            f"sattlint exited with code {process.poll()} within {window_seconds}s (crashed during Textual startup)"
        )
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        os.close(master)
