# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false
"""Managed actions, view activation, and session output retention."""

from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest
from rich.rule import Rule
from rich.text import Text

from sattlint import ui as app_textual
from tests.helpers.app_textual_support import (
    isolate_app_config_path,
    isolate_textual_projects,
    make_textual_app,
)

# Re-export the autouse fixtures so pytest registers them for this module.
__all__ = [
    "isolate_app_config_path",
    "isolate_textual_projects",
]


def test_textual_start_action_starts_a_daemon_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    created_threads: list[object] = []

    class FakeThread:
        def start(self) -> None:
            return None

    class FakeTextualApp(app_textual.SattLintTextualApp):
        def _start_action_thread(self, _work: Any, *, label: str, action_id: str) -> object:
            assert label == "Run selected analyses"
            assert action_id == "action-analyze"
            thread = FakeThread()
            created_threads.append(thread)
            return thread

    app_instance = FakeTextualApp(
        cfg={"analyzed_programs_and_libraries": ["TargetA"]},
        summarize_targets_fn=lambda _cfg: "targets",
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

    assert len(created_threads) == 1
    assert app_instance._busy is True
    assert app_instance._active_cancellation is None


def test_textual_schedule_ui_coroutine_tracks_pending_task(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTask:
        def __init__(self) -> None:
            self._callbacks: list[Any] = []

        def add_done_callback(self, callback: Any) -> None:
            self._callbacks.append(callback)

        def cancelled(self) -> bool:
            return False

        def exception(self) -> BaseException | None:
            return None

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
    app_instance = make_textual_app()

    monkeypatch.setattr(asyncio, "get_running_loop", lambda: fake_loop)

    app_instance._schedule_ui_coroutine(lambda: "scheduled work")

    assert fake_loop.created == ["scheduled work"]
    assert fake_task in app_instance._pending_ui_tasks

    fake_task.finish()

    assert fake_task not in app_instance._pending_ui_tasks


def test_textual_start_action_reports_type_errors_from_action(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTextualApp(app_textual.SattLintTextualApp):
        def _start_action_thread(self, work: Any, *, label: str, action_id: str) -> object:
            assert label == "Run selected analyses"
            assert action_id == "action-analyze"
            work()
            return SimpleNamespace(start=lambda: None)

    app_instance = FakeTextualApp(
        cfg={"analyzed_programs_and_libraries": ["TargetA"]},
        summarize_targets_fn=lambda _cfg: "targets",
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
    popups: list[tuple[str, str]] = []
    monkeypatch.setattr(app_instance, "_show_error_modal", lambda title, message: popups.append((title, message)))
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
    assert popups == [("Run selected analyses failed", "Run selected analyses failed: bad action wiring")]


def test_textual_activate_view_leaves_dirty_setup_changes_unsaved(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app()
    app_instance._active_view = "setup"
    app_instance._dirty = True
    started: list[str] = []

    monkeypatch.setattr(app_instance, "_start_action", lambda *args, **kwargs: started.append("save"))
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)

    app_instance._activate_view("settings")

    assert started == []
    assert app_instance._active_view == "settings"
    assert app_instance._dirty is True


def test_textual_finish_action_clears_dirty_after_success() -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    app_instance._dirty = True
    app_instance._set_active_action = lambda _action_id: None  # type: ignore[method-assign]
    app_instance._refresh_summary = lambda: None  # type: ignore[method-assign]

    app_instance._finish_action(clear_dirty_on_success=True)

    assert app_instance._dirty is False


def test_textual_quit_action_leaves_while_an_action_is_running(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    exited: list[str] = []
    app_instance._busy = True

    monkeypatch.setattr(app_instance, "exit", lambda: exited.append("exit"))

    app_instance._handle_toolbar_action("action-quit")

    assert exited == ["exit"]
    assert app_instance._quitting is True


def test_textual_quit_action_forces_cancellation_before_exiting(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    cancelled: list[dict[str, object]] = []
    exited: list[str] = []
    app_instance._busy = True
    app_instance._active_cancellation = SimpleNamespace(cancel=lambda **kwargs: cancelled.append(kwargs))

    monkeypatch.setattr(app_instance, "exit", lambda: exited.append("exit"))

    app_instance._handle_toolbar_action("action-quit")

    assert cancelled == [{"force": True}]
    assert exited == ["exit"]


def test_textual_call_on_ui_drops_callbacks_after_quitting(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app()
    app_instance._quitting = True
    called: list[str] = []

    monkeypatch.setattr(app_instance, "call_from_thread", lambda *_args, **_kwargs: called.append("called"))

    app_instance._call_on_ui(lambda: None)

    assert called == []


def test_textual_call_on_ui_ignores_a_stopped_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app()

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("App is not running")

    monkeypatch.setattr(app_instance, "call_from_thread", _raise)

    # The worker must keep unwinding instead of propagating the shutdown error.
    app_instance._call_on_ui(lambda: None)


def test_textual_action_thread_is_a_daemon_the_app_never_joins() -> None:
    app_instance = make_textual_app()
    release = threading.Event()

    thread = app_instance._start_action_thread(
        lambda: release.wait(5),
        label="Run selected analyzers",
        action_id="action-analyze",
    )

    assert thread.daemon is True
    release.set()
    thread.join(2)
    assert not thread.is_alive()


def test_textual_action_thread_streams_output_to_the_ui() -> None:
    async def _run() -> None:
        app_instance = make_textual_app()
        done = threading.Event()

        def work() -> None:
            app_instance._emit_output_from_thread("streamed from the action thread")
            done.set()

        async with app_instance.run_test() as pilot:
            await pilot.pause()
            app_instance._start_action("Streaming action", work, action_id="action-change-review")
            assert await asyncio.to_thread(done.wait, 5)
            await pilot.pause()
            output_text = str(getattr(app_instance.query_one("#output"), "text", ""))
            assert "streamed from the action thread" in output_text

    asyncio.run(_run())


def test_textual_action_quit_routes_through_the_cancelling_quit(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app()
    calls: list[str] = []

    monkeypatch.setattr(app_instance, "_request_quit_shell", lambda: calls.append("quit"))

    app_instance.action_quit()

    assert calls == ["quit"]


def test_textual_ctrl_q_uses_the_cancelling_quit() -> None:
    async def _run() -> None:
        app_instance = make_textual_app()
        calls: list[str] = []
        app_instance._request_quit_shell = lambda: calls.append("quit")  # type: ignore[method-assign]

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+q")
            await pilot.pause()

        assert calls == ["quit"]

    asyncio.run(_run())


def test_textual_quit_does_not_wait_for_a_running_action() -> None:
    async def _run() -> None:
        app_instance = make_textual_app()
        started = threading.Event()
        release = threading.Event()

        def work(_cancellation: object) -> None:
            started.set()
            release.wait(30)

        began = 0.0
        async with app_instance.run_test() as pilot:
            await pilot.pause()
            app_instance._start_action(
                "Blocking action",
                work,
                action_id="action-analyze",
                cancellable=True,
            )
            assert await asyncio.to_thread(started.wait, 5)
            began = time.monotonic()
            app_instance.action_quit()

        release.set()
        assert time.monotonic() - began < 5

    asyncio.run(_run())


def test_textual_write_output_preserves_blank_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
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

    app_instance._write_output("Analyze output")
    app_instance._write_output("=== Target: DemoLib ===")

    assert fake_widget.text == "Analyze output\n=== Target: DemoLib ===\n"
    assert isinstance(written[0], Text)
    assert str(written[0]) == "Analyze output"
    assert written[1] == ""
    assert isinstance(written[2], Rule)


def test_textual_write_output_caps_retained_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
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

    app_instance._write_output("\n".join(f"line {index}" for index in range(6005)))

    assert len(app_instance._session_output_lines) == 4000
    assert app_instance._session_output_lines[0] == "line 2005"
    assert app_instance._session_output_dropped_line_count == 2005
    assert app_instance._output_title_text() == "Session output - retaining last 4000 lines"
    assert fake_widget.text.startswith("line 2005\n")
    assert "line 2004\n" not in fake_widget.text


def test_textual_write_output_rebuilds_in_batches_after_retention(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app(
        cfg={"analyzed_programs_and_libraries": ["TargetA"], "output": {"retention_lines": 100}}
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
    retained_sizes_at_rebuild: list[int] = []
    original_rebuild = app_instance._rebuild_output_widget

    def _rebuild_and_record(widget: Any) -> None:
        retained_sizes_at_rebuild.append(len(app_instance._session_output_lines))
        original_rebuild(widget)

    monkeypatch.setattr(app_instance, "query_one", lambda *_args, **_kwargs: fake_widget)
    monkeypatch.setattr(app_instance, "_rebuild_output_widget", _rebuild_and_record)

    for index in range(1000):
        app_instance._write_output(f"line {index}")

    assert len(app_instance._session_output_lines) == 100
    assert retained_sizes_at_rebuild
    assert set(retained_sizes_at_rebuild) == {100}
    assert len(retained_sizes_at_rebuild) <= 20


def test_textual_write_output_promotes_target_load_error_to_popup(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )

    class FakeRichOutput:
        def __init__(self) -> None:
            self.text = ""
            self._plain_text_parts: list[str] = []

        def append_plain_text(self, text: str) -> None:
            self._plain_text_parts.append(text)
            self.text += text

        def write(self, _renderable: object, **_kwargs: Any) -> None:
            return None

        def scroll_end(self, animate: bool = False) -> None:
            return None

    fake_widget = FakeRichOutput()
    monkeypatch.setattr(app_instance, "query_one", lambda *_args, **_kwargs: fake_widget)

    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(app_instance, "_show_error_modal", lambda title, message: shown.append((title, message)))

    app_instance._write_output("=== Target: EveryIssueMain ===")
    app_instance._write_output("? Failed to load target:")
    app_instance._write_output("Target 'EveryIssueMain' was not parsed.\nMissing/failed targets: none")

    assert len(shown) == 1
    title, message = shown[0]
    assert title == "Failed to load target"
    assert "EveryIssueMain" in message
    assert "was not parsed" in message
    assert "Missing/failed targets" in message
    assert fake_widget.text.endswith("Missing/failed targets: none\n")


def test_textual_write_output_ignores_plain_target_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )

    class FakeRichOutput:
        def __init__(self) -> None:
            self.text = ""
            self._plain_text_parts: list[str] = []

        def append_plain_text(self, text: str) -> None:
            self._plain_text_parts.append(text)
            self.text += text

        def write(self, _renderable: object, **_kwargs: Any) -> None:
            return None

        def scroll_end(self, animate: bool = False) -> None:
            return None

    fake_widget = FakeRichOutput()
    monkeypatch.setattr(app_instance, "query_one", lambda *_args, **_kwargs: fake_widget)

    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(app_instance, "_show_error_modal", lambda title, message: shown.append((title, message)))

    app_instance._write_output("=== Target: DemoLib ===")
    app_instance._write_output("Report: Variable issues")
    app_instance._write_output("Status: ok")

    assert shown == []
    assert fake_widget.text == "=== Target: DemoLib ===\nReport: Variable issues\nStatus: ok\n"


def test_textual_output_trim_keeps_the_readers_scroll_position() -> None:
    app_instance = make_textual_app(
        cfg={"analyzed_programs_and_libraries": ["TargetA"], "output": {"retention_lines": 100}}
    )

    class ScrollableOutput:
        is_vertical_scroll_end = False
        scroll_y = 120.0

        def __init__(self) -> None:
            self.scroll_targets: list[float] = []

        def clear(self) -> None:
            return None

        def write(self, _renderable: object, **_kwargs: Any) -> None:
            return None

        def scroll_to(self, y: float | None = None, **_kwargs: Any) -> None:
            if y is not None:
                self.scroll_targets.append(y)

        def scroll_end(self, animate: bool = False) -> None:
            return None

        def append_plain_text(self, _text: str) -> None:
            return None

    output = ScrollableOutput()
    app_instance.query_one = lambda *_args, **_kwargs: output  # type: ignore[method-assign]

    app_instance._write_output("\n".join(f"line {index}" for index in range(200)))

    assert len(app_instance._session_output_lines) == 100
    # 100 lines left the top of the log, so the same text now sits 100 lines
    # higher in the rebuilt widget.
    assert output.scroll_targets == [20.0]


def test_textual_lowering_output_retention_trims_the_live_log_immediately() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["TargetA"], "output": {"retention_lines": 4000}}
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance._session_output_lines = [f"line {index}" for index in range(300)]
            app_instance._cfg["output"] = {"retention_lines": 100}

            app_instance._mark_settings_changed("Updated session output retention.")

            # The trim runs before the confirmation line is written.
            assert app_instance._session_output_lines[0] == "line 200"
            assert app_instance._session_output_dropped_line_count == 200
            assert len(app_instance._session_output_lines) <= 101

    asyncio.run(_run())
