# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnusedImport=false
"""Dialogs, error modals, and the AST refresh modal."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattlint import ui as app_textual
from sattlint.ui import _app_textual_actions as app_textual_actions_module
from sattlint.ui import _app_textual_shared as app_textual_shared_module
from sattlint.ui import _app_textual_widgets as app_textual_widgets_module
from tests.helpers.app_textual_support import (  # noqa: F401  (autouse fixtures)
    isolate_app_config_path,
    isolate_textual_projects,
    make_textual_app,
    query_any_screen,
)


def test_textual_ast_refresh_modal_renders_only_the_status_tail() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    modal = app_textual_widgets_module._AstRefreshModalScreen(refresh_fn=lambda _emit_status: True)
    modal._status_lines = [f"line {index}" for index in range(modal._RENDERED_STATUS_TAIL + 25)]

    rendered = modal._render_status_text()

    assert "25 earlier line(s) hidden" in rendered
    assert rendered.endswith(f"line {modal._RENDERED_STATUS_TAIL + 24}")
    assert "line 0\n" not in rendered


def test_textual_ast_refresh_modal_keeps_a_large_failure_report_on_screen() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    release_refresh = threading.Event()
    results: list[object] = []

    def _refresh(emit_status: Callable[..., None]) -> bool:
        emit_status("Checking AST cache for Demo... (1/1)")
        emit_status("\n".join(f"  - dependency{index}" for index in range(300)))
        release_refresh.wait(timeout=10)
        return False

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )
        modal = app_textual_widgets_module._AstRefreshModalScreen(refresh_fn=_refresh)

        try:
            async with app_instance.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                app_instance.push_screen(modal, callback=results.append)
                for _ in range(20):
                    await pilot.pause()
                    if "dependency299" in str(modal._render_status_text()):
                        break

                dialog = modal.query_one("#ast-refresh-dialog")
                log_region = modal.query_one("#ast-refresh-log")
                assert dialog.region.height <= app_instance.size.height
                assert dialog.region.width <= app_instance.size.width
                # The oversized report scrolls inside the dialog instead of
                # pushing the dialog past the bottom of the terminal.
                assert log_region.virtual_size.height > log_region.region.height
                assert app_instance.focused is modal.query_one("#ast-refresh-close")

                # The report is reachable with the keyboard, not just clipped.
                log_region.focus()
                await pilot.pause()
                await pilot.press("pagedown")
                await pilot.pause()
                assert log_region.scroll_offset.y > 0

                await pilot.press("escape")
                for _ in range(10):
                    await pilot.pause()
                    if results:
                        break
                assert results == [None]
        finally:
            release_refresh.set()

    asyncio.run(_run())


def test_textual_ast_refresh_modal_ignores_a_result_after_close() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    dismissed: list[object] = []
    modal = app_textual_widgets_module._AstRefreshModalScreen(refresh_fn=lambda _emit_status: True)
    modal.query_one = lambda *_args, **_kwargs: SimpleNamespace(update=lambda _text: None)
    modal.dismiss = lambda result: dismissed.append(result)

    modal.action_close()
    modal._update_status("late line")
    modal._finish_refresh(ok=False, exc=None)

    assert dismissed == [None]
    assert modal._refresh_failed is True
    assert modal._render_status_text() == "Starting cached AST refresh..."


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
    # Run the UI hop inline: this test covers the refresh failure path, and the
    # worker thread has no running app to marshal onto.
    monkeypatch.setattr(modal, "_call_on_ui", lambda callback, *args, **kwargs: callback(*args, **kwargs))

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
    # Run the UI hop inline so the recorded failure reaches this assertion.
    monkeypatch.setattr(modal, "_call_on_ui", lambda callback, *args, **kwargs: callback(*args, **kwargs))

    modal._run_refresh()

    assert modal._refresh_failed is True
    assert isinstance(modal._refresh_exception, TypeError)


def test_textual_ast_refresh_modal_skips_ui_callback_without_running_app(
    caplog: pytest.LogCaptureFixture,
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    class _NoRunningApp:
        def call_from_thread(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("no running app")

    invoked: list[str] = []

    with caplog.at_level(logging.DEBUG, logger=app_textual_widgets_module.__name__):
        app_textual_widgets_module._AstRefreshModalScreen._call_on_ui(
            SimpleNamespace(app=_NoRunningApp()),
            invoked.append,
            "ignored",
        )

    assert invoked == []
    assert any("Skipping UI callback" in record.getMessage() for record in caplog.records)


def test_textual_open_help_popup_propagates_type_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app()
    app_instance._get_help_text_fn = lambda _cfg: (_ for _ in ()).throw(TypeError("bad help wiring"))
    shown_help: list[str] = []

    monkeypatch.setattr(app_instance, "_show_help_modal", lambda text: shown_help.append(text))

    with pytest.raises(TypeError, match="bad help wiring"):
        app_instance._open_help_popup()

    assert shown_help == []


def test_textual_show_error_modal_pushes_error_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    pushed: list[tuple[Any, Any]] = []
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append((screen, callback)))

    app_instance._show_error_modal("Unable to load target", "Target 'X' failed to load.")

    assert len(pushed) == 1
    screen, _callback = pushed[0]
    assert isinstance(screen, app_textual_widgets_module._ErrorScreen)
    assert screen._error_title == "Unable to load target"
    assert screen._error_message == "Target 'X' failed to load."


def test_textual_error_modal_renders_and_dismisses() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance._show_error_modal("Failed to load target", "Target 'EveryIssueMain' failed to load.")

            await pilot.pause()

            error_dialog = query_any_screen(app_instance, "#error-dialog")
            error_title = str(query_any_screen(app_instance, "#error-dialog-title").renderable)
            error_body = str(query_any_screen(app_instance, "#error-dialog-body-text").renderable)
            assert error_title == "Failed to load target"
            assert "Target 'EveryIssueMain' failed to load." in error_body
            assert error_dialog.region.x > 0
            assert error_dialog.region.y > 0
            assert error_dialog.size.width < app_instance.size.width
            assert error_dialog.size.height < app_instance.size.height

            await pilot.press("escape")
            await pilot.pause()

            with pytest.raises(app_textual_shared_module._TEXTUAL_QUERY_ERRORS):
                query_any_screen(app_instance, "#error-dialog")

    asyncio.run(_run())


def test_textual_report_error_writes_output_and_shows_modal(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    app_instance = make_textual_app()
    written: list[str] = []
    pushed: list[tuple[Any, Any]] = []
    monkeypatch.setattr(app_instance, "_write_output", lambda text: written.append(str(text)))
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append((screen, callback)))

    app_instance._report_error("Save failed", "Save failed: disk full")

    assert written == ["Save failed: disk full"]
    assert len(pushed) == 1
    screen, _callback = pushed[0]
    assert isinstance(screen, app_textual_widgets_module._ErrorScreen)
    assert screen._error_title == "Save failed"
    assert screen._error_message == "Save failed: disk full"


def test_textual_save_settings_failure_shows_error_modal(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    app_instance = make_textual_app()
    app_instance._active_view = "settings"
    messages: list[str] = []
    popups: list[tuple[str, str]] = []
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(str(text)))
    monkeypatch.setattr(app_instance, "_show_error_modal", lambda title, message: popups.append((title, message)))
    monkeypatch.setattr(
        "sattlint.config.save_app_settings",
        lambda _path, _cfg: (_ for _ in ()).throw(ValueError("bad config")),
    )

    app_instance.action_save_config()

    assert messages == ["Save failed: bad config"]
    assert popups == [("Save failed", "Save failed: bad config")]


def test_textual_new_project_failure_shows_error_modal(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    app_instance = make_textual_app(project=False)
    captured: dict[str, object] = {}
    messages: list[str] = []
    popups: list[tuple[str, str]] = []
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_clear_session_output", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(str(text)))
    monkeypatch.setattr(app_instance, "_show_error_modal", lambda title, message: popups.append((title, message)))
    monkeypatch.setattr(
        app_instance,
        "present_request",
        lambda request, on_response_fn=None: captured.update(callback=on_response_fn),
    )
    monkeypatch.setattr(
        app_textual_actions_module,
        "_init_project",
        lambda _path: (_ for _ in ()).throw(OSError("no space")),
    )

    app_instance._new_project()

    callback = captured["callback"]
    assert callable(callback)
    callback("BrokenProject")

    assert messages == ["Failed to create configuration: no space"]
    assert popups == [("Failed to create configuration", "Failed to create configuration: no space")]


def test_textual_second_error_modal_does_not_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app()
    pushed: list[object] = []
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append(screen))

    app_instance._show_error_modal("First", "first failure")
    app_instance._show_error_modal("Second", "second failure")

    assert len(pushed) == 1


def test_textual_failed_ui_task_reports_instead_of_dropping(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app()
    reported: list[tuple[str, str]] = []

    class FailingTask:
        def __init__(self) -> None:
            self._callbacks: list[Any] = []

        def add_done_callback(self, callback: Any) -> None:
            self._callbacks.append(callback)

        def cancelled(self) -> bool:
            return False

        def exception(self) -> BaseException | None:
            return RuntimeError("prompt wiring failed")

        def finish(self) -> None:
            for callback in tuple(self._callbacks):
                callback(self)

    task = FailingTask()
    monkeypatch.setattr(app_instance, "_report_error", lambda title, message: reported.append((title, message)))

    app_textual_actions_module._track_ui_task(app_instance, cast(Any, task))
    task.finish()

    assert reported == [("Action failed", "Action failed: prompt wiring failed")]


def test_textual_dialog_close_restores_the_previous_focus() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(key="a", name="A", description="", category="correctness")
            ]
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()
            analyzers = app_instance.query_one("#analyze-section-analyzers")
            analyzers.focus()
            await pilot.pause()

            app_instance.present_request(
                app_textual_shared_module.InteractionRequest(kind="confirm", message="Continue?")
            )
            await pilot.pause()

            app_instance._resolve_request(app_instance._active_request, True)
            await pilot.pause()

            assert app_instance._active_request is None
            assert app_instance.focused is not None
            assert app_instance.focused.id == "analyze-section-analyzers"

    asyncio.run(_run())
