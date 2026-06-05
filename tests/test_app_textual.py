from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sattlint import app, app_textual


def test_textual_interaction_bridge_returns_responses() -> None:
    def _submit(request: app_textual.InteractionRequest) -> None:
        if request.kind == "menu":
            request.response = "2"
        elif request.kind == "prompt":
            request.response = "value"
        elif request.kind == "confirm":
            request.response = True
        else:
            request.response = None
        request.completed.set()

    bridge = app_textual.TextualInteractionBridge(submit_request_fn=_submit)

    assert bridge.choose_menu_option("Menu", []) == "2"
    assert bridge.prompt("Name") == "value"
    assert bridge.confirm("Confirm?") is True
    bridge.pause()


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


def test_run_interactive_session_dispatches_to_textual_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    app.set_interactive_ui_mode("textual")

    def _fake_run_textual_shell(cfg: dict[str, Any], *, app_module: Any, **kwargs: Any) -> None:
        seen.update({"cfg": cfg, "app_module": app_module, **kwargs})

    def _summarize_targets(_cfg: dict[str, Any]) -> str:
        return "targets"

    monkeypatch.setattr(
        app_textual,
        "run_textual_shell",
        _fake_run_textual_shell,
    )

    try:
        app.run_interactive_session({"debug": False}, summarize_targets_fn=_summarize_targets)
    finally:
        app.reset_interactive_ui_mode()

    assert seen["cfg"] == {"debug": False}
    assert seen["app_module"] is app


def test_resolve_interactive_ui_mode_falls_back_without_textual(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_textual, "has_textual", lambda: False)

    assert app.resolve_interactive_ui_mode({}, "textual") == "classic"


def test_resolve_interactive_ui_mode_defaults_to_textual_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SATTLINT_UI", raising=False)
    monkeypatch.setattr(app_textual, "has_textual", lambda: True)

    assert app.resolve_interactive_ui_mode({}, None) == "textual"


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
        {
            "program_dir": str(program_dir),
            "ABB_lib_dir": str(abb_dir),
            "other_lib_dirs": [],
            "mode": "official",
        }
    )

    assert [candidate.name for candidate in candidates] == ["TargetA", "TargetB"]
    assert [path.name for path in candidates[0].files] == ["TargetA.l", "TargetA.s", "TargetA.x"]
    assert candidates[0].available is True
    assert candidates[1].available is False


def test_interaction_ledger_text_mentions_multi_digit_entry() -> None:
    request = app_textual.InteractionRequest(
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


def test_textual_shell_css_mentions_banner_and_full_width_menu_buttons() -> None:
    assert "#shell-top" in app_textual.TEXTUAL_SHELL_CSS
    assert "#shell-banner" in app_textual.TEXTUAL_SHELL_CSS
    assert "#shell-banner-title" in app_textual.TEXTUAL_SHELL_CSS
    assert "#shell-banner-subtitle" in app_textual.TEXTUAL_SHELL_CSS
    assert "#summary" in app_textual.TEXTUAL_SHELL_CSS
    assert "overflow-y: auto;" in app_textual.TEXTUAL_SHELL_CSS
    assert "#content-host" in app_textual.TEXTUAL_SHELL_CSS
    assert "#view-host" in app_textual.TEXTUAL_SHELL_CSS
    assert "#analyze-browser" in app_textual.TEXTUAL_SHELL_CSS
    assert "#analyze-actions-primary" in app_textual.TEXTUAL_SHELL_CSS
    assert "#documentation-actions" in app_textual.TEXTUAL_SHELL_CSS
    assert "#setup-browser" in app_textual.TEXTUAL_SHELL_CSS
    assert "#interaction-host" in app_textual.TEXTUAL_SHELL_CSS
    assert "#interaction-screen" in app_textual.TEXTUAL_SHELL_CSS
    assert "Button.raised-button" in app_textual.TEXTUAL_SHELL_CSS
    assert "#interaction-options Button.raised-button" in app_textual.TEXTUAL_SHELL_CSS
    assert "#actions Button.toolbar-button" in app_textual.TEXTUAL_SHELL_CSS
    assert "outline: none;" in app_textual.TEXTUAL_SHELL_CSS
    assert "width: 100%;" in app_textual.TEXTUAL_SHELL_CSS


def test_textual_app_title_defaults_to_banner_title() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    assert app_textual.SattLintTextualApp.TITLE == app_textual.DEFAULT_SHELL_TITLE


def test_textual_banner_shows_title_and_subtitle() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            assert str(app_instance.query_one("#shell-banner-title").renderable) == app_textual.DEFAULT_SHELL_TITLE
            assert "Analysis, docs, setup, and tools" in str(
                app_instance.query_one("#shell-banner-subtitle").renderable
            )

    asyncio.run(_run())


def test_textual_summary_lists_all_configured_targets() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        targets = [f"Target{i}" for i in range(1, 11)]
        app_instance = app_textual.SattLintTextualApp(
            cfg={"analyzed_programs_and_libraries": targets},
            summarize_targets_fn=lambda _cfg: "10 targets configured: Target1, Target2, Target3, ...",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            summary_text = str(app_instance.query_one("#summary").renderable)
            assert "10 targets configured" in summary_text
            assert "Target1, Target2" in summary_text
            assert "Target10" in summary_text
            assert "Target1, Target2, Target3, ..." not in summary_text

    asyncio.run(_run())


def test_textual_quit_keybinding_does_not_crash() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("q")
            await pilot.pause()

    asyncio.run(_run())


def test_textual_present_request_uses_inline_host_and_preserves_shell_chrome() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )
        request = app_textual.InteractionRequest(
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

            assert len(list(app_instance.query("#shell-banner"))) == 1
            assert app_instance.query_one("#interaction-host").has_class("active")
            assert app_instance.query_one("#output").has_class("interaction-active")
            assert getattr(app_instance.query_one("#action-analyze"), "disabled", False) is True

            await pilot.press("escape")
            await pilot.pause()

            assert request.completed.is_set() is True
            assert request.response == "b"
            assert app_instance.query_one("#interaction-host").has_class("active") is False
            assert app_instance.query_one("#output").has_class("interaction-active") is False
            assert getattr(app_instance.query_one("#action-analyze"), "disabled", True) is False

    asyncio.run(_run())


def test_textual_toolbar_navigation_switches_view_without_starting_action(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
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
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
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


def _make_textual_app(*, cfg: dict[str, Any] | None = None, app_module: Any | None = None) -> Any:
    return app_textual.SattLintTextualApp(
        cfg=cfg or {"analyzed_programs_and_libraries": ["TargetA"]},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
        app_module=app_module,
    )


def test_textual_analyze_view_shows_planner_controls() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(cfg={"analyzed_programs_and_libraries": []})

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            assert app_instance._active_view == "analyze"
            assert app_instance.query_one("#output").size.height > 0
            assert app_instance.query_one("#view-actions").has_class("is-hidden") is True
            assert app_instance.query_one("#analyze-actions-primary").has_class("is-hidden") is False
            assert app_instance.query_one("#analyze-browser").has_class("is-hidden") is False
            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", False) is True
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", False) is True
            assert "No analysis targets are configured yet" in str(app_instance.query_one("#view-note").renderable)
            assert app_instance.query_one("#analyze-planner-section-top-level") is not None
            assert str(app_instance.query_one("#output-title").renderable) == "Session output"

            detail_text = str(app_instance.query_one("#analyze-browser-right").renderable)
            assert "Analyze planner" in detail_text
            assert "Status: Configure a target in Setup to enable the planner runner." in detail_text
            assert "No analyses selected." in detail_text

    asyncio.run(_run())


def test_textual_analyze_planner_renders_grouped_sections_and_detail() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            app_module=SimpleNamespace(
                _get_enabled_analyzers=lambda: [
                    SimpleNamespace(
                        key="comment-code",
                        name="Commented-out code",
                        description="Scan comments for code-like content",
                    )
                ],
                _run_checks=lambda _cfg, _selected_keys: None,
            )
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            assert app_instance.query_one("#analyze-planner-section-top-level") is not None
            assert app_instance.query_one("#analyze-planner-section-variable-suite") is not None
            assert app_instance.query_one("#analyze-planner-section-catalog-analyzers") is not None

            detail_text = str(app_instance.query_one("#analyze-browser-right").renderable)
            assert "Focused entry: Full analyzer suite" in detail_text
            assert "Queue summary" in detail_text

    asyncio.run(_run())


def test_textual_analyze_planner_selection_updates_summary_and_normalizes_suite_overlap() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            app_module=SimpleNamespace(
                run_variable_analysis=lambda _cfg, _kinds: None,
            )
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            suite_list = app_instance.query_one("#analyze-planner-section-variable-suite")
            high_list = app_instance.query_one("#analyze-planner-section-variable-high-confidence")

            suite_list.select(app_textual.analysis_catalog.ENTRY_VARIABLE_HIGH_CONFIDENCE_SUITE)
            app_instance._sync_analyze_selection_from_selection_list(suite_list)
            await pilot.pause()
            high_list.select("variables.issue.6")
            app_instance._sync_analyze_selection_from_selection_list(high_list)
            app_instance._refresh_analyze_planner_summary_widgets()
            app_instance._refresh_shell_state()
            await pilot.pause()

            detail_text = str(app_instance.query_one("#analyze-browser-right").renderable)
            assert "Selected entries: 2" in detail_text
            assert "Planned steps: 1" in detail_text
            assert "Normalized overlaps" in detail_text
            assert "Covered by All variable analyses (high confidence)." in detail_text
            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", True) is False

    asyncio.run(_run())


def test_textual_analyze_run_selected_executes_planned_steps_in_catalog_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    launched: list[tuple[str, str]] = []

    app_instance = _make_textual_app(
        app_module=SimpleNamespace(
            _run_checks=lambda _cfg, selected_keys: calls.append(
                ("checks", None if selected_keys is None else tuple(selected_keys))
            ),
            run_debug_variable_usage=lambda _cfg: calls.append(("debug", None)),
            run_comment_code_analysis=lambda _cfg: calls.append(("comment-code", None)),
        )
    )
    app_instance._analyze_selected_entry_ids = {
        app_textual.analysis_catalog.ENTRY_ANALYZE_FULL_SUITE,
        app_textual.analysis_catalog.ENTRY_VARIABLE_USAGE_TRACE,
        app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE,
    }
    app_instance._analyze_focused_entry_id = app_textual.analysis_catalog.ENTRY_ANALYZE_FULL_SUITE

    monkeypatch.setattr(
        app_instance,
        "_start_action",
        lambda label, action_fn, *, action_id, marks_dirty=False, clear_dirty_on_success=False: (
            launched.append((label, action_id)),
            action_fn(),
        ),
    )

    app_instance._run_selected_analysis_plan()

    assert launched == [("Run selected analyses", "action-analyze")]
    assert calls == [
        ("checks", None),
        ("debug", None),
        ("comment-code", None),
    ]
    assert app_instance._analyze_selected_entry_ids == {
        app_textual.analysis_catalog.ENTRY_ANALYZE_FULL_SUITE,
        app_textual.analysis_catalog.ENTRY_VARIABLE_USAGE_TRACE,
        app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE,
    }


def test_textual_analyze_running_state_calls_out_output_location() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            app_module=SimpleNamespace(
                run_comment_code_analysis=lambda _cfg: None,
            )
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            quality_list = app_instance.query_one("#analyze-planner-section-code-quality-actions")
            quality_list.select(app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE)
            app_instance._sync_analyze_selection_from_selection_list(quality_list)
            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Run selected analyses"
            app_instance._refresh_summary()
            app_instance._refresh_analyze_planner_summary_widgets()
            app_instance._refresh_shell_state()
            await pilot.pause()

            assert "Selected analyses are running." in str(app_instance.query_one("#view-note").renderable)
            assert str(app_instance.query_one("#output-title").renderable) == (
                "Session output - Run selected analyses in progress"
            )

            detail_text = str(app_instance.query_one("#analyze-browser-right").renderable)
            assert "Status: Running selected analyses." in detail_text
            assert "Live output is shown in Session output below." in detail_text

    asyncio.run(_run())


def test_textual_analyze_buttons_unlock_after_finish_action() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["DemoTarget.s"]},
            app_module=SimpleNamespace(
                run_comment_code_analysis=lambda _cfg: None,
            ),
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            quality_list = app_instance.query_one("#analyze-planner-section-code-quality-actions")
            quality_list.select(app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE)
            app_instance._sync_analyze_selection_from_selection_list(quality_list)
            app_instance._refresh_analyze_planner_summary_widgets()
            app_instance._refresh_shell_state()
            await pilot.pause()

            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", True) is False
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", True) is False

            app_instance._busy = True
            app_instance._active_job_action_id = "action-analyze"
            app_instance._active_job_label = "Run selected analyses"
            app_instance._refresh_summary()
            app_instance._refresh_analyze_planner_summary_widgets()
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


def test_textual_analyze_run_selected_reports_missing_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    lines: list[str] = []

    app_instance = _make_textual_app(app_module=SimpleNamespace())
    app_instance._analyze_selected_entry_ids = {app_textual.analysis_catalog.ENTRY_VARIABLE_USAGE_TRACE}

    monkeypatch.setattr(app_instance, "_write_output", lambda text: lines.extend(text.splitlines()))
    monkeypatch.setattr(app_instance, "_start_action", lambda *_args, **_kwargs: pytest.fail("should not start"))

    app_instance._run_selected_analysis_plan()

    assert any("Missing handlers" in line for line in lines)
    assert any("run_debug_variable_usage" in line for line in lines)


def test_textual_analyze_clear_selection_resets_planner_state() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app(
            app_module=SimpleNamespace(
                run_comment_code_analysis=lambda _cfg: None,
            )
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            quality_list = app_instance.query_one("#analyze-planner-section-code-quality-actions")
            quality_list.select(app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE)
            app_instance._sync_analyze_selection_from_selection_list(quality_list)
            app_instance._refresh_analyze_planner_summary_widgets()
            app_instance._refresh_shell_state()
            await pilot.pause()

            assert app_instance._analyze_selected_entry_ids == {app_textual.analysis_catalog.ENTRY_COMMENTED_OUT_CODE}
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", True) is False

            app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="analyze-clear-selection")))
            await pilot.pause()

            assert app_instance._analyze_selected_entry_ids == set()
            assert getattr(app_instance.query_one("#analyze-clear-selection"), "disabled", False) is True
            detail_text = str(app_instance.query_one("#analyze-browser-right").renderable)
            assert "No analyses selected." in detail_text

    asyncio.run(_run())


def test_textual_toolbar_key_switches_routed_view() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            assert str(app_instance.query_one("#view-title").renderable) == "Analyze"

            await pilot.press("3")
            await pilot.pause()

            assert app_instance._active_view == "setup"
            assert str(app_instance.query_one("#view-title").renderable) == "Setup"
            assert app_instance.query_one("#view-actions").has_class("is-hidden") is True
            assert getattr(app_instance.query_one("#action-setup"), "disabled", True) is False

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
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("3")
            await pilot.pause()

            browse_button = app_instance.query_one("#setup-target-browse")
            remove_button = app_instance.query_one("#setup-target-remove")
            targets_col = app_instance.query_one("#setup-targets-col")
            settings_col = app_instance.query_one("#setup-settings-col")
            assert app_instance._active_view == "setup"
            assert app_instance.query_one("#setup-browser").has_class("is-hidden") is False
            assert app_instance.query_one("#view-actions").has_class("is-hidden") is True
            assert str(getattr(browse_button, "label", "")) == "Add from file..."
            assert targets_col is not None
            assert settings_col is not None
            # Remove is disabled when nothing is selected
            assert getattr(remove_button, "disabled", False) is True

    asyncio.run(_run())


def test_textual_documentation_view_shows_direct_actions() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={"analyzed_programs_and_libraries": ["TargetA"]},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
            app_module=SimpleNamespace(
                _get_documentation_unit_selection=lambda: {
                    "mode": "moduletype_names",
                    "instance_paths": [],
                    "moduletype_names": ["ApplTank"],
                }
            ),
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("2")
            await pilot.pause()

            assert app_instance._active_view == "documentation"
            assert app_instance.query_one("#view-actions").has_class("is-hidden") is True
            assert app_instance.query_one("#documentation-actions").has_class("is-hidden") is False
            assert getattr(app_instance.query_one("#documentation-generate"), "disabled", True) is False
            assert "Current scope: moduletype: ApplTank" in str(app_instance.query_one("#view-note").renderable)

    asyncio.run(_run())


def test_textual_documentation_button_dispatches_direct_action(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={"analyzed_programs_and_libraries": ["TargetA"]},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    seen: list[str] = []

    monkeypatch.setattr(app_instance, "_run_documentation_scope_moduletype", lambda: seen.append("scope-moduletype"))

    app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="documentation-scope-moduletype")))

    assert seen == ["scope-moduletype"]


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
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("3")
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


def test_textual_tools_view_shows_direct_actions() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={"analyzed_programs_and_libraries": []},
            summarize_targets_fn=lambda _cfg: "targets",
            analysis_menu_fn=lambda _cfg: None,
            documentation_menu_fn=lambda _cfg: None,
            config_menu_fn=lambda _cfg: None,
            tools_menu_fn=lambda _cfg: None,
            show_help_fn=lambda _cfg: None,
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("4")
            await pilot.pause()

            assert app_instance._active_view == "tools"
            assert app_instance.query_one("#view-actions").has_class("is-hidden") is True
            assert app_instance.query_one("#tools-actions").has_class("is-hidden") is False
            assert getattr(app_instance.query_one("#tools-self-check"), "disabled", True) is False
            assert getattr(app_instance.query_one("#tools-dumps"), "disabled", False) is True
            assert getattr(app_instance.query_one("#tools-source-diff"), "disabled", False) is True
            assert getattr(app_instance.query_one("#tools-refresh-ast"), "disabled", False) is True

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
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
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

    app_instance._add_selected_setup_target()

    assert cfg["analyzed_programs_and_libraries"] == ["TargetA"]
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
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
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

    app_instance._remove_selected_setup_target()

    assert cfg["analyzed_programs_and_libraries"] == []
    assert app_instance._dirty is True
    assert messages == ["Removed analysis target 'TargetA' from the Setup view."]


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
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
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

    def _capture_request(request: app_textual.InteractionRequest, on_response_fn: object | None = None) -> None:
        captured["request"] = request
        captured["callback"] = on_response_fn

    monkeypatch.setattr(app_instance, "present_request", _capture_request)

    app_instance._prompt_setup_value("program_dir", label="program_dir")

    request = captured["request"]
    assert isinstance(request, app_textual.InteractionRequest)
    assert request.kind == "prompt"
    assert request.default == "/old/programs"

    callback = captured["callback"]
    assert callable(callback)
    callback("/new/programs")

    assert cfg["program_dir"] == "/new/programs"
    assert app_instance._dirty is True
    assert messages == ["Updated program_dir from the Setup view."]


def test_textual_save_action_does_not_clear_dirty_before_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
        show_help_fn=lambda _cfg: None,
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    app_instance._dirty = True
    started: list[str] = []
    refreshed: list[str] = []

    monkeypatch.setattr(app_instance, "_start_action", lambda *args, **kwargs: started.append("save"))
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: refreshed.append("refresh"))

    app_instance._handle_toolbar_action("setup-save")

    assert started == ["save"]
    assert app_instance._dirty is True
    assert refreshed == []


def test_textual_finish_action_clears_dirty_after_success() -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
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
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
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


def test_textual_toolbar_actions_are_ignored_while_interaction_screen_is_open(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        analysis_menu_fn=lambda _cfg: None,
        documentation_menu_fn=lambda _cfg: None,
        config_menu_fn=lambda _cfg: None,
        tools_menu_fn=lambda _cfg: None,
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
