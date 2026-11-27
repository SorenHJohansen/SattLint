# pyright: reportPrivateUsage=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false
"""Running analyzers and streaming their output into the shell."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sattlint import ui as app_textual
from sattlint.core.progress import AnalysisProgressEvent, ProgressPhase
from sattlint.project.io import init_project
from sattlint.ui import _app_textual_setup as app_textual_setup_module
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


def test_textual_analyze_run_selected_executes_planned_steps_in_catalog_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    launched: list[tuple[str, str]] = []

    app_instance = make_textual_app(
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
        lambda label, action_fn, *, action_id, marks_dirty=False, clear_dirty_on_success=False, cancellable=False: (
            launched.append((label, action_id)),
            action_fn(None),
        ),
    )
    monkeypatch.setattr(app_instance, "_emit_output_from_thread", lambda _text: None)

    app_instance._run_selected_analyzers()

    assert launched == [("Run selected analyzers", "action-analyze")]
    assert calls == [("checks", ("alpha-analyzer", "beta-analyzer"))]
    assert app_instance._analyze_selected_entry_ids == {"alpha-analyzer", "beta-analyzer"}


def test_textual_analyze_run_uses_the_open_project_path_not_the_user_config(tmp_path: Path) -> None:
    recorded: list[str] = []

    def _handler(_cfg: object, _keys: object, *, project_path: str = "") -> object:
        recorded.append(project_path)
        return None

    app_instance = make_textual_app(project=False, analysis_handlers={"run_checks_result": _handler})
    app_instance._config_path = Path("/home/user/.config/sattlint/config.toml")
    app_instance._configured_target_names = lambda: ("TargetA",)
    app_instance._emit_output_from_thread = lambda _text: None

    app_instance._execute_analyzers(("alpha-analyzer",))

    assert recorded == [""]

    project = init_project(tmp_path / "project" / ".slproj")
    app_instance._project = project
    app_instance._project_path = project.path

    app_instance._execute_analyzers(("alpha-analyzer",))

    assert recorded[-1] == str(project.path)
    assert recorded[-1] != str(app_instance._config_path)


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
        app_instance = make_textual_app(
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
            lambda label, action_fn, *, action_id, marks_dirty=False, clear_dirty_on_success=False, cancellable=False: (
                action_fn(None)
            ),
        )
        monkeypatch.setattr(
            app_instance,
            "_emit_output_from_thread",
            lambda text: app_instance._write_output(text),
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-section-analyzers")
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


def test_textual_analyze_running_state_calls_out_output_location() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="comment-code",
                    name="Commented-out code",
                    description="Detect commented-out code.",
                    category="code-quality",
                ),
            ],
            analysis_handlers={"run_checks_result": lambda _cfg: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-section-analyzers")
            analyzers_list.select("comment-code")
            app_instance._sync_analyze_selection_from_selection_list(analyzers_list)
            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Run selected analyzers"
            app_instance._refresh_summary()
            app_instance._write_focused_entry_to_output()
            app_instance._refresh_view()
            app_instance._refresh_shell_state()

            assert str(app_instance.query_one("#view-note").renderable) == (
                "Selected analyses are running. Live output is shown in Session output below. "
                "Choose Cancel run (Esc) to stop it, or Quit to stop it and leave."
            )
            assert str(app_instance.query_one("#output-title").renderable) == (
                "Session output ⠋ - Run selected analyzers in progress"
            )

            app_instance._advance_output_title_spinner()
            assert str(app_instance.query_one("#output-title").renderable) == (
                "Session output ⠙ - Run selected analyzers in progress"
            )

            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert "Analyzer:" in output_text
            assert "Description:" in output_text

    asyncio.run(_run())


def test_textual_analyze_running_state_uses_calm_output_title_spinner(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    captured: dict[str, object] = {}
    timer_calls = {"resume": 0, "pause": 0}
    timer = SimpleNamespace(
        resume=lambda: timer_calls.__setitem__("resume", timer_calls["resume"] + 1),
        pause=lambda: timer_calls.__setitem__("pause", timer_calls["pause"] + 1),
    )
    app_instance = make_textual_app(analysis_handlers={"run_checks_result": lambda _cfg: None})
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

    assert captured["interval"] == app_textual_setup_module._OUTPUT_TITLE_SPINNER_INTERVAL_SECONDS
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


def test_textual_analyze_output_title_spinner_advances_one_frame_per_tick() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    frames = app_textual_setup_module._OUTPUT_TITLE_SPINNER_FRAMES

    async def _run() -> None:
        app_instance = make_textual_app(analysis_handlers={"run_checks_result": lambda _cfg: None})
        async with app_instance.run_test() as pilot:
            await pilot.pause()
            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Run selected analyses"
            app_instance.set_interval = lambda *_args, **_kwargs: SimpleNamespace(
                resume=lambda: None, pause=lambda: None
            )
            app_instance._refresh_shell_state()

            assert str(app_instance.query_one("#output-title").renderable).startswith(f"Session output {frames[0]}")
            for expected in (*frames[1:], frames[0]):
                app_instance._advance_output_title_spinner()
                assert str(app_instance.query_one("#output-title").renderable).startswith(f"Session output {expected}")

            app_instance._advance_output_title_spinner()
            assert str(app_instance.query_one("#output-title").renderable).startswith(f"Session output {frames[1]}")

            app_instance._refresh_shell_state()
            assert str(app_instance.query_one("#output-title").renderable).startswith(f"Session output {frames[1]}")

            app_instance._busy = False
            app_instance._refresh_shell_state()
            app_instance._busy = True
            app_instance._refresh_shell_state()
            assert str(app_instance.query_one("#output-title").renderable).startswith(f"Session output {frames[0]}")

    asyncio.run(_run())


def test_textual_analyze_buttons_unlock_after_finish_action() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["DemoTarget.s"]},
            get_enabled_analyzers_fn=lambda: [
                SimpleNamespace(
                    key="comment-code",
                    name="Commented-out code",
                    description="Detect commented-out code.",
                    category="code-quality",
                ),
            ],
            analysis_handlers={"run_checks_result": lambda _cfg: None},
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            analyzers_list = app_instance.query_one("#analyze-section-analyzers")
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


def test_textual_analyze_view_exposes_cancel_for_a_cancellable_run() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(cfg={"analyzed_programs_and_libraries": ["DemoTarget.s"]})

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            cancel_button = app_instance.query_one("#analyze-cancel-run")
            assert cancel_button.disabled is True

            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Run selected analyzers"
            app_instance._active_cancellation = SimpleNamespace(cancel=lambda **_kwargs: None)
            app_instance._refresh_shell_state()
            await pilot.pause()

            assert cancel_button.disabled is False

            app_instance._cancel_requested = True
            app_instance._refresh_shell_state()
            await pilot.pause()

            assert cancel_button.disabled is True

            app_instance._finish_action()
            await pilot.pause()

            assert cancel_button.disabled is True

    asyncio.run(_run())


def test_textual_cancel_run_requests_analysis_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app()
    calls: list[dict[str, object]] = []
    messages: list[str] = []
    app_instance._busy = True
    app_instance._active_job_action_id = "action-analyze"
    app_instance._active_cancellation = SimpleNamespace(cancel=lambda **kwargs: calls.append(kwargs))

    monkeypatch.setattr(app_instance, "_write_output", messages.append)
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)

    app_instance.action_cancel_run()
    # A second press is a no-op; the child is already being stopped.
    app_instance.action_cancel_run()

    assert calls == [{}]
    assert app_instance._cancel_requested is True
    assert messages == ["Cancelling the run. Analyzer workers are being stopped."]


def test_textual_analyze_run_selected_reports_missing_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    lines: list[str] = []
    started: list[tuple[str, str]] = []

    app_instance = make_textual_app(
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

    def record_output(text: str) -> None:
        lines.extend(text.splitlines())

    monkeypatch.setattr(app_instance, "_write_output", record_output)
    monkeypatch.setattr(
        app_instance,
        "_start_action",
        lambda label, action_fn, *, action_id, marks_dirty=False, clear_dirty_on_success=False, cancellable=False: (
            started.append((label, action_id)),
            action_fn(None),
        ),
    )
    monkeypatch.setattr(app_instance, "_emit_output_from_thread", record_output)

    app_instance._run_selected_analyzers()

    assert started == [("Run selected analyzers", "action-analyze")]
    assert any("The analyzer runner is unavailable" in line for line in lines)


def test_textual_analyze_note_text_no_stale_planner_references() -> None:
    app_instance = make_textual_app(
        cfg={"analyzed_programs_and_libraries": ["TargetA"]},
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="comment-code",
                name="Commented-out code",
                description="Detect commented-out code.",
                category="code-quality",
            ),
        ],
    )
    app_instance._analyze_selected_entry_ids = {"comment-code"}
    app_instance._analyze_focused_entry_id = "comment-code"

    note = app_instance._analyze_note_text()

    assert "1 analyzer selected. Use Run selected analyzers." in note

    app_instance._analyze_selected_entry_ids.clear()
    assert "Select one or more analyzers below to run." in app_instance._analyze_note_text()


def test_textual_analyze_note_text_running_state_avoids_stale_plan() -> None:
    app_instance = make_textual_app(
        cfg={"analyzed_programs_and_libraries": ["TargetA"]},
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="comment-code",
                name="Commented-out code",
                description="Detect commented-out code.",
                category="code-quality",
            ),
        ],
    )
    app_instance._analyze_selected_entry_ids = {"comment-code"}
    app_instance._busy = True
    app_instance._active_job_action_id = "action-analyze"

    note = app_instance._analyze_note_text()
    assert "Selected analyses are running." in note


def test_textual_execute_analyzers_dispatches_to_run_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[str] = []
    called: list[list[str] | None] = []

    app_instance = make_textual_app(
        analysis_handlers={
            "_run_checks": lambda _cfg, selected_keys: called.append(
                None if selected_keys is None else list(selected_keys)
            )
        }
    )
    selected_keys = ("alpha-analyzer", "beta-analyzer")

    monkeypatch.setattr(app_instance, "_emit_output_from_thread", lambda text: emitted.append(text))

    app_instance._execute_analyzers(selected_keys)

    assert emitted == [
        "Running 2 selected analyzer(s).",
        "Selected analyzers completed.",
    ]
    assert called == [["alpha-analyzer", "beta-analyzer"]]


def test_textual_execute_analyzers_forwards_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    received: list[object] = []
    emitted: list[str] = []
    finished: list[str] = []

    def _handler(_cfg: object, _keys: object, *, cancellation: object = None) -> SimpleNamespace:
        received.append(cancellation)
        return SimpleNamespace(failures=(), analyzer_failures=(), cancelled=True, run_id=None)

    app_instance = make_textual_app(analysis_handlers={"run_checks_result": _handler})
    token = object()

    monkeypatch.setattr(app_instance, "_emit_output_from_thread", emitted.append)
    monkeypatch.setattr(app_instance, "_call_on_ui", lambda callback, *args, **kwargs: callback(*args, **kwargs))
    monkeypatch.setattr(app_instance, "_finish_analysis_run", lambda _result: finished.append("finished"))

    app_instance._execute_analyzers(("alpha-analyzer",), cancellation=token)

    assert received == [token]
    assert emitted[-1] == "Analysis cancelled."
    assert finished == []


def test_textual_execute_analyzers_streams_runner_output(monkeypatch: pytest.MonkeyPatch) -> None:
    streamed: list[str] = []

    def _handler(_cfg: object, _keys: object, *, emit_output: object = None) -> SimpleNamespace:
        assert callable(emit_output)
        emit_output("target header from the runner")
        return SimpleNamespace(failures=(), analyzer_failures=(), cancelled=False, run_id=None)

    app_instance = make_textual_app(analysis_handlers={"run_checks_result": _handler})
    monkeypatch.setattr(app_instance, "_emit_output_from_thread", lambda text: streamed.append(text))
    monkeypatch.setattr(app_instance, "_finish_analysis_run", lambda _result: None)
    monkeypatch.setattr(app_instance, "call_from_thread", lambda fn, *args: fn(*args))

    app_instance._execute_analyzers(("alpha-analyzer",))

    assert "target header from the runner" in streamed
    assert streamed[-1] == "Selected analyzers completed."


def test_textual_execute_analyzers_forwards_progress_events(monkeypatch: pytest.MonkeyPatch) -> None:
    applied: list[AnalysisProgressEvent] = []

    def _handler(_cfg: object, _keys: object, *, progress: object = None) -> SimpleNamespace:
        assert callable(progress)
        progress(
            AnalysisProgressEvent(
                phase=ProgressPhase.LOADING,
                target_total=1,
                target_index=1,
                target_name="TargetA",
            )
        )
        return SimpleNamespace(failures=(), analyzer_failures=(), cancelled=False, run_id=None)

    app_instance = make_textual_app(analysis_handlers={"run_checks_result": _handler})
    monkeypatch.setattr(app_instance, "_apply_analysis_progress", applied.append)
    monkeypatch.setattr(app_instance, "_emit_output_from_thread", lambda _text: None)
    monkeypatch.setattr(
        app_instance,
        "_call_on_ui",
        lambda callback, *args, **kwargs: callback(*args, **kwargs),
    )
    monkeypatch.setattr(app_instance, "_finish_analysis_run", lambda _result: None)

    app_instance._execute_analyzers(("alpha-analyzer",))

    assert [event.phase for event in applied] == [ProgressPhase.LOADING]
    assert applied[0].target_name == "TargetA"


def test_textual_finish_analysis_run_reports_a_run_without_stored_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_instance = make_textual_app()
    messages: list[str] = []
    activated: list[str] = []

    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    monkeypatch.setattr(app_instance, "_activate_view", lambda view_name: activated.append(view_name))

    app_instance._finish_analysis_run(SimpleNamespace(run_id=None))

    assert activated == []
    assert messages == ["This run was not saved to run history, so the Results view still shows earlier runs."]

    app_instance._finish_analysis_run(SimpleNamespace(run_id="stored-run"))

    assert activated == ["results"]


def test_textual_execute_analyzers_reports_target_load_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[str] = []
    result = SimpleNamespace(failures=(SimpleNamespace(target_name="Broken"),))
    app_instance = make_textual_app(
        analysis_handlers={"run_checks_result": lambda _cfg, _keys: result},
    )

    monkeypatch.setattr(app_instance, "_emit_output_from_thread", lambda text: emitted.append(text))
    monkeypatch.setattr(app_instance, "call_from_thread", lambda *_args: None)

    app_instance._execute_analyzers(("alpha-analyzer",))

    assert emitted == [
        "Running 1 selected analyzer(s).",
        "Analysis finished with problems: 1 target(s) could not be loaded (Broken). Review the output above.",
    ]


def test_textual_analyze_running_note_offers_cancellation() -> None:
    app_instance = make_textual_app(cfg={"analyzed_programs_and_libraries": ["DemoTarget.s"]})

    app_instance._busy = True
    app_instance._active_job_action_id = "action-analyze"

    note = app_instance._analyze_note_text()

    assert "Selected analyses are running." in note
    assert "Cancel run (Esc)" in note

    app_instance._cancel_requested = True

    assert "Cancelling the run." in app_instance._analyze_note_text()
