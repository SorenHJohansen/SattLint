# pyright: reportPrivateUsage=false
"""Wiring tests: TUI action, handler registration, and no CLI command."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattlint import app as app_module
from sattlint import ui as app_textual
from sattlint.application import change_review as change_review_application
from sattlint.cli.startup import analysis_handler_fns
from sattlint.config.types import ConfigDict

pytestmark = pytest.mark.unit


def _noop_cfg(_cfg: ConfigDict) -> str:
    return "targets"


def _noop_save(_path: object, _cfg: ConfigDict) -> None:
    return None


def _help_text(_cfg: ConfigDict) -> str:
    return "Help text"


def _make_textual_app(analysis_handlers: dict[str, Any] | None = None) -> Any:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")
    return app_textual.SattLintTextualApp(
        cfg={
            "analyzed_programs_and_libraries": ["TargetA"],
            "mode": "draft",
            "debug": False,
            "review": {"output_dir": ""},
        },
        summarize_targets_fn=_noop_cfg,
        show_help_fn=_noop_cfg,
        get_help_text_fn=_help_text,
        save_config_fn=_noop_save,
        config_path=None,
        quit_app_error=RuntimeError,
        analysis_handlers=analysis_handlers,
        get_enabled_analyzers_fn=None,
        ensure_ast_cache_fn=None,
    )


def test_generate_change_review_handler_is_registered_for_tui() -> None:
    handlers = analysis_handler_fns()
    assert callable(handlers["generate_change_review"])


def test_generate_change_review_handler_requires_targets(tmp_path: Path) -> None:
    cfg = cast(
        ConfigDict,
        {
            "analyzed_programs_and_libraries": [],
            "program_dir": str(tmp_path),
            "mode": "draft",
            "debug": False,
            "review": {"output_dir": ""},
        },
    )
    with pytest.raises(RuntimeError):
        change_review_application.generate_change_review(cfg, [])


def _allow_action(_kind: str) -> bool:
    return True


def _setup_has_targets() -> bool:
    return True


def test_change_review_action_invokes_handler_with_cfg_and_targets() -> None:
    captured: dict[str, Any] = {}

    def fake_handler(cfg: ConfigDict, target_names: list[str]) -> str:
        captured["cfg"] = cfg
        captured["targets"] = target_names
        return "generated"

    app_instance = _make_textual_app(analysis_handlers={"generate_change_review": fake_handler})
    started: dict[str, Any] = {}

    def start_action(label: str, fn: Callable[[], Any], *, action_id: str) -> None:
        started.update(label=label, fn=fn, action_id=action_id)

    app_instance._start_action = start_action
    app_instance._setup_has_targets = _setup_has_targets
    app_instance._targets_action_allowed = _allow_action
    emitted: list[str] = []

    def emit_output(text: str) -> None:
        emitted.append(text)

    app_instance._emit_output_from_thread = emit_output

    app_instance._run_generate_change_review()

    assert started["label"] == "Generate Change Review"
    started["fn"]()
    assert captured["targets"] == ["TargetA"]
    assert any("generated" in line for line in emitted)


def test_change_review_button_dispatch() -> None:
    app_instance = _make_textual_app()
    calls: list[str] = []
    app_instance._run_generate_change_review = lambda: calls.append("pressed")

    app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="analyze-generate-change-review")))
    assert calls == ["pressed"]


def test_change_review_ui_controls_present() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = _make_textual_app()
        async with app_instance.run_test() as pilot:
            await pilot.pause()
            assert app_instance.query_one("#analyze-generate-change-review") is not None
            assert app_instance.query_one("#settings-edit-review-output-dir") is not None
            assert app_instance.query_one("#settings-label-review-output-dir") is not None

    asyncio.run(_run())


def test_no_cli_command_introduced_for_change_review() -> None:
    parser = app_module.build_cli_parser()
    commands: set[str] = set()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if choices:
            commands.update(str(choice) for choice in choices)
    assert "change-review" not in commands
    assert "change_review" not in commands
