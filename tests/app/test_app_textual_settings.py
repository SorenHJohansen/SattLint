# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false
"""App settings and review output directory."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from sattlint import config as config_module
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


def test_textual_settings_layout_uses_vertical_cards() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+4")
            await pilot.pause()

            assert app_instance._active_view == "settings"
            assert len(list(app_instance.query("#settings-browser .settings-group-box"))) == 3
            assert len(list(app_instance.query("#settings-browser .settings-card-title"))) == 3
            assert len(list(app_instance.query("#settings-browser .settings-row"))) == 5
            assert app_instance.query_one("#settings-toggle-run-history") is not None
            assert app_instance.query_one("#settings-edit-run-history-limit") is not None
            assert app_instance.query_one("#settings-edit-output-retention") is not None
            assert app_instance.query_one("#settings-edit-review-output-dir") is not None
            assert app_instance.query_one("#settings-label-run-history") is not None

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
        app_instance = make_textual_app(cfg=cfg)

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+4")
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
            assert app_instance._dirty is False
            assert str(app_instance.query_one("#settings-label-debug").renderable).startswith("Enabled")

    asyncio.run(_run())


def test_textual_settings_prompt_buttons_open_dialog_and_apply_values() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        cfg: dict[str, Any] = {
            "analyzed_programs_and_libraries": ["TargetA"],
            "debug": False,
            "run_history": {"enabled": True, "limit": 50},
            "output": {"retention_lines": 4000},
        }
        app_instance = make_textual_app(cfg=cfg)

        async def _edit(button_id: str, input_value: str, section: str, subkey: str, expected: object) -> None:
            app_instance.query_one(f"#{button_id}").press()
            await pilot.pause()
            assert app_instance._active_request is not None
            app_instance.query_one("#interaction-input").value = input_value
            await pilot.click("#submit")
            await pilot.pause()
            assert cfg[section][subkey] == expected  # type: ignore[index]
            assert app_instance._dirty is False

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+4")
            await pilot.pause()

            await _edit("settings-edit-run-history-limit", "80", "run_history", "limit", 80)
            await _edit("settings-edit-output-retention", "2500", "output", "retention_lines", 2500)

    asyncio.run(_run())


def test_textual_review_output_dir_button_opens_folder_picker() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()
        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+4")
            await pilot.pause()
            app_instance.query_one("#settings-edit-review-output-dir").press()
            await pilot.pause()
            assert type(app_instance.screen).__name__ == "_FileBrowserScreenImpl"

    asyncio.run(_run())


def test_textual_settings_change_autosaves_to_app_config(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app()
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: None)

    app_instance._cfg["run_history"] = {"enabled": True, "limit": 80}
    app_instance._mark_settings_changed("updated run history")

    assert app_instance._dirty is False
    saved_cfg, _default_used = config_module.load_config(config_module.get_config_path())
    assert saved_cfg["run_history"]["limit"] == 80
    assert saved_cfg["run_history"]["enabled"] is True
