# pyright: reportPrivateUsage=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false
"""Shell chrome, keybindings, session output, and navigation."""

from __future__ import annotations

import asyncio
import contextlib
import os
import select
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sattlint import ui as app_textual
from sattlint.ui import _app_textual_actions as app_textual_actions_module
from sattlint.ui import _app_textual_app as app_textual_module
from sattlint.ui import _app_textual_settings as app_textual_settings_module
from sattlint.ui import _app_textual_setup as app_textual_setup_module
from sattlint.ui import _app_textual_shared as app_textual_shared_module
from tests.helpers.app_textual_support import (
    assert_no_content_clipped_outside_visible_area,
    isolate_app_config_path,
    isolate_textual_projects,
    make_textual_app,
    query_any_screen,
    screen_row_bgcolors,
)

# Re-export the autouse fixtures so pytest registers them for this module.
__all__ = [
    "isolate_app_config_path",
    "isolate_textual_projects",
]


def test_textual_top_chrome_removes_banner_and_mounts_summary_strip() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            assert len(list(app_instance.query("#shell-banner"))) == 0
            assert len(list(app_instance.query("#status-summary"))) == 1
            assert app_instance.query_one("#status-project") is not None
            assert app_instance.query_one("#nav-tab-analyze") is not None

    asyncio.run(_run())


def test_textual_toolbar_is_available_with_summary_strip() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={"analyzed_programs_and_libraries": ["Target1", "Target2"]},
            summarize_targets_fn=lambda _cfg: "targets",
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            summary_text = str(app_instance.query_one("#status-summary").renderable)
            assert "No configuration open" in summary_text
            assert str(app_instance.query_one("#status-project").renderable) == "No configuration"
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
        app_instance = make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance._write_output("Extra output")
            await pilot.pause()
            assert "Extra output" in getattr(app_instance.query_one("#output"), "text", "")

            app_instance.action_clear_output()
            await pilot.pause()

            assert getattr(app_instance.query_one("#output"), "text", "") == ""
            assert app_instance._session_output_lines == []

    asyncio.run(_run())


def test_textual_help_menu_opens_help_dialog() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="menu-help")))
            await pilot.pause()

            help_dialog = query_any_screen(app_instance, "#help-dialog")
            help_body = str(query_any_screen(app_instance, "#help-dialog-body-text").renderable)
            assert "Keyboard Shortcuts" in help_body
            assert "Copy Output" in help_body
            assert "About SattLint" in help_body
            assert "█████████" in help_body
            assert help_dialog.region.x > 0
            assert help_dialog.region.y > 0
            assert help_dialog.size.width < app_instance.size.width
            assert help_dialog.size.height < app_instance.size.height

            help_screen = app_instance.screen
            assert help_screen.styles.background.a < 1
            menubar_colors = screen_row_bgcolors(app_instance, 0)
            assert menubar_colors
            menubar_triplets = [(c.triplet.red, c.triplet.green, c.triplet.blue) for c in menubar_colors]
            assert all(t != (18, 18, 18) for t in menubar_triplets), "app must be visible behind the popup, not black"
            assert all(t != (230, 222, 203) for t in menubar_triplets), "app behind the popup should be dimmed"

    asyncio.run(_run())


def test_textual_shell_bindings_exclude_save_and_toggle_hotkeys() -> None:
    keys = {key for key, _action, _desc in app_textual_shared_module.APP_SHELL_BINDINGS}
    assert "ctrl+s" not in keys
    assert "ctrl+o" not in keys


def test_textual_session_output_preserves_manual_scroll_position_on_new_output() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
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


def test_textual_toolbar_navigation_switches_view_without_starting_action(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
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


def test_textual_menu_file_actions_respect_the_busy_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    opened: list[str] = []
    messages: list[str] = []
    app_instance._busy = True
    monkeypatch.setattr(app_instance, "_open_project_browser", lambda: opened.append("open"))
    monkeypatch.setattr(app_instance, "_new_project", lambda: opened.append("new"))
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(str(text)))

    app_instance._handle_toolbar_action("menu-file-open-project")
    app_instance._handle_toolbar_action("menu-file-new-project")

    assert opened == []
    assert messages == ["Another action is still running. Wait for it to finish first."] * 2

    app_instance._busy = False
    app_instance._handle_toolbar_action("menu-file-open-project")
    app_instance._handle_toolbar_action("menu-file-new-project")

    assert opened == ["open", "new"]


def test_textual_toolbar_help_action_opens_help_popup(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
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


def test_textual_shell_defaults_to_truecolor_console() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    app_instance = make_textual_app(cfg={"analyzed_programs_and_libraries": []})

    assert app_instance.console.color_system == "truecolor"


def test_textual_toolbar_key_switches_routed_view() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            assert str(app_instance.query_one("#view-title").renderable) == "Analyze"

            await pilot.press("ctrl+3")
            await pilot.pause()

            assert app_instance._active_view == "setup"
            assert str(app_instance.query_one("#view-title").renderable) == "Configuration Settings"
            assert app_instance.query_one("#nav-tab-setup").has_class("nav-tab-active") is True

    asyncio.run(_run())


def test_textual_toolbar_keys_respect_busy_guard() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = app_textual.SattLintTextualApp(
            cfg={},
            summarize_targets_fn=lambda _cfg: "targets",
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


def test_textual_shell_does_not_write_startup_ast_cache_output() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(project=False)

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert "Initial AST loading log:" not in output_text
            assert "AST cache" not in output_text
            assert "Welcome to SattLint." in output_text

    asyncio.run(_run())


def test_textual_app_uses_explicit_mixins() -> None:
    assert issubclass(app_textual_module.SattLintTextualApp, app_textual_actions_module._TextualActionsMixin)
    assert issubclass(app_textual_module.SattLintTextualApp, app_textual_setup_module._TextualSetupMixin)
    assert issubclass(app_textual_module.SattLintTextualApp, app_textual_module._TextualAnalyzeMixin)
    assert issubclass(app_textual_module.SattLintTextualApp, app_textual_settings_module._TextualSettingsMixin)


def test_textual_toolbar_actions_are_ignored_while_interaction_screen_is_open(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = app_textual.SattLintTextualApp(
        cfg={},
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    started: list[str] = []

    monkeypatch.setattr(app_instance, "_interaction_screen_active", lambda: True)
    monkeypatch.setattr(app_instance, "_start_action", lambda *args, **kwargs: started.append("started"))

    app_instance._handle_toolbar_action("action-analyze")

    assert started == []


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
        app_instance = make_textual_app(project=False)

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            assert app_instance._project_loaded() is False
            analyzer_notice = str(next(iter(app_instance.query_one("#analyze-list-host").children)).renderable)
            assert "No configuration is open" in analyzer_notice
            assert getattr(app_instance.query_one("#analyze-run-selected"), "disabled", False) is True

            await pilot.press("ctrl+3")
            await pilot.pause()
            setup_item = next(iter(app_instance.query_one("#setup-target-listview").children))
            setup_notice = str(next(iter(setup_item.children)).renderable)
            assert "No configuration is open" in setup_notice
            assert getattr(app_instance.query_one("#setup-edit-program-dir"), "disabled", False) is True
            assert getattr(app_instance.query_one("#setup-edit-abb-dir"), "disabled", False) is True
            assert getattr(app_instance.query_one("#setup-edit-other-lib-dirs"), "disabled", False) is True
            assert getattr(app_instance.query_one("#setup-edit-icf-dir"), "disabled", False) is True
            assert getattr(app_instance.query_one("#setup-toggle-mode"), "disabled", False) is True

            await pilot.press("ctrl+2")
            await pilot.pause()
            results_item = next(iter(app_instance.query_one("#results-runs-list").children))
            results_notice = str(next(iter(results_item.children)).renderable)
            assert "No configuration is open" in results_notice

            # Settings stays usable without a project.
            await pilot.press("ctrl+4")
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

    import pty  # noqa: PLC0415 - POSIX-only; guarded by the win32 skip above

    window_seconds = 5

    master, slave = pty.openpty()
    try:
        env = dict(os.environ)
        env["TERM"] = "xterm-256color"
        env["COLUMNS"] = "100"
        env["LINES"] = "30"
        # The child must not read or write the developer's configuration or
        # cache; every per-user location points at this test's temp directory.
        env["HOME"] = str(tmp_path)
        env["USERPROFILE"] = str(tmp_path)
        env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
        env["XDG_CACHE_HOME"] = str(tmp_path / "cache")
        env["APPDATA"] = str(tmp_path / "appdata")
        # The child runs in ``tmp_path``. A relative ``PYTHONPATH=src`` would
        # resolve against that directory and import a stale installed package
        # instead of this checkout.
        python_path_entries = [str(Path(__file__).resolve().parents[2] / "src")]
        for entry in os.environ.get("PYTHONPATH", "").split(os.pathsep):
            if not entry:
                continue
            entry_path = Path(entry)
            if not entry_path.is_absolute():
                entry_path = (Path.cwd() / entry_path).resolve()
            python_path_entries.append(str(entry_path))
        env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(python_path_entries))
        process = subprocess.Popen(
            [sys.executable, "-m", "sattlint"],
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


def test_textual_no_content_clipped_outside_visible_area() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()

        async with app_instance.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            assert_no_content_clipped_outside_visible_area(app_instance)

            for key in ("ctrl+2", "ctrl+3", "ctrl+4", "ctrl+5", "ctrl+1"):
                await pilot.press(key)
                await pilot.pause()
                assert_no_content_clipped_outside_visible_area(app_instance)

            await pilot.press("?")
            await pilot.pause()
            assert_no_content_clipped_outside_visible_area(app_instance)
            await pilot.press("escape")
            await pilot.pause()

            app_instance._show_error_modal("Failed to load target", "\n".join(f"line {i}" for i in range(30)))
            await pilot.pause()
            assert_no_content_clipped_outside_visible_area(app_instance)

    asyncio.run(_run())


def test_ui_static_treats_untrusted_text_as_plain_text() -> None:
    static = app_textual_shared_module._TEXTUAL_STATIC("[bold]not markup[/bold] and [unclosed")

    assert str(static.renderable) == "[bold]not markup[/bold] and [unclosed"


def test_textual_analyzer_focus_keeps_the_session_log() -> None:
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
                )
            ]
        )

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance._write_output("run output that must survive")
            app_instance._analyze_focused_entry_id = "comment-code"
            app_instance._write_focused_entry_to_output()
            await pilot.pause()

            output_text = getattr(app_instance.query_one("#output"), "text", "")
            assert "run output that must survive" in output_text
            assert "Analyzer: Commented-out code" in output_text

    asyncio.run(_run())


def test_textual_shell_uses_the_documented_view_and_setting_labels() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            nav_labels = {str(tab.id): str(getattr(tab, "renderable", "")) for tab in app_instance.query(".nav-tab")}
            assert nav_labels["nav-tab-setup"] == "Configuration Settings"
            assert nav_labels["nav-tab-settings"] == "App Settings"
            assert str(app_instance.query_one("#settings-toggle-run-history").label) == "Run history"
            assert str(app_instance.query_one("#settings-edit-run-history-limit").label) == "Run history limit"

    asyncio.run(_run())


def test_textual_clearing_the_session_log_forgets_pending_target_errors() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            app_instance._pending_error_target_name = "OldTarget"
            app_instance._last_output_target_name = "OldTarget"

            app_instance._clear_session_output()

            assert app_instance._pending_error_target_name is None
            assert app_instance._last_output_target_name is None

    asyncio.run(_run())


def test_textual_chrome_project_label_shows_project_name() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()
            label = str(app_instance.query_one("#status-project").renderable)
            assert "project-1" in label

    asyncio.run(_run())


def test_textual_chrome_project_label_falls_back_without_project() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(project=False)

        async with app_instance.run_test() as pilot:
            await pilot.pause()
            assert str(app_instance.query_one("#status-project").renderable) == "No configuration"

    asyncio.run(_run())


def test_textual_refresh_view_raises_when_required_widget_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()

            def _raise_missing(*_args: Any, **_kwargs: Any) -> object:
                raise app_textual_actions_module._TEXTUAL_QUERY_ERRORS[0]("missing view host")

            monkeypatch.setattr(app_instance, "query_exactly_one", _raise_missing, raising=False)
            monkeypatch.setattr(app_instance, "query_one", _raise_missing)

            with pytest.raises(app_textual_actions_module._TEXTUAL_QUERY_ERRORS[0], match="missing view host"):
                app_instance._refresh_view()

    asyncio.run(_run())
