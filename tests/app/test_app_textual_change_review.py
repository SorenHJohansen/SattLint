# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnusedImport=false
"""Wiring tests: TUI action, handler registration, and no CLI command."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattlint import ui as app_textual
from sattlint.application import change_review as change_review_application
from sattlint.cli import startup as app_module
from sattlint.cli._output import CliError
from sattlint.cli.startup import analysis_handler_fns
from sattlint.config.types import ConfigDict
from tests.helpers.app_textual_support import (  # noqa: F401  (autouse fixtures)
    isolate_app_config_path,
    isolate_textual_projects,
    make_textual_app,
)

pytestmark = pytest.mark.unit

_CHANGE_REVIEW_CFG: dict[str, Any] = {
    "analyzed_programs_and_libraries": ["TargetA"],
    "mode": "draft",
    "debug": False,
    "review": {"output_dir": ""},
}


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


def test_generate_change_review_continues_past_a_failed_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = cast(
        ConfigDict,
        {
            "analyzed_programs_and_libraries": ["Bad", "Good"],
            "program_dir": str(tmp_path),
            "mode": "draft",
            "debug": False,
            "review": {"output_dir": ""},
        },
    )

    def fake_run_review(_cfg: ConfigDict, target: str, *, output_dir: Path) -> Any:
        if target == "Bad":
            raise ValueError("target is stale")
        return SimpleNamespace(json_path=output_dir / "Good.json", markdown_path=output_dir / "Good.md")

    monkeypatch.setattr(change_review_application, "run_review", fake_run_review)

    summary = change_review_application.generate_change_review(cfg, ["Bad", "Good"], output_dir=tmp_path)

    assert "generated for 1 target(s)" in summary
    assert "Good: Good.md" in summary
    assert "failed for 1 target(s)" in summary
    assert "Bad: target is stale" in summary


def test_generate_change_review_reports_when_every_target_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = cast(
        ConfigDict,
        {
            "analyzed_programs_and_libraries": ["Bad", "Worse"],
            "program_dir": str(tmp_path),
            "mode": "draft",
            "debug": False,
            "review": {"output_dir": ""},
        },
    )

    def fake_run_review(_cfg: ConfigDict, target: str, *, output_dir: Path) -> Any:
        raise ValueError(f"{target} is stale")

    monkeypatch.setattr(change_review_application, "run_review", fake_run_review)

    with pytest.raises(RuntimeError) as exc_info:
        change_review_application.generate_change_review(cfg, ["Bad", "Worse"], output_dir=tmp_path)

    message = str(exc_info.value)
    assert "failed for every target" in message
    assert "Bad: Bad is stale" in message
    assert "Worse: Worse is stale" in message


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

    app_instance = make_textual_app(
        cfg=_CHANGE_REVIEW_CFG,
        project=False,
        analysis_handlers={"generate_change_review": fake_handler},
    )
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
    app_instance = make_textual_app(cfg=_CHANGE_REVIEW_CFG, project=False)
    calls: list[str] = []
    app_instance._run_generate_change_review = lambda: calls.append("pressed")

    app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="output-generate-change-review")))
    assert calls == ["pressed"]


def test_change_review_ui_controls_present() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(cfg=_CHANGE_REVIEW_CFG, project=False)
        async with app_instance.run_test() as pilot:
            await pilot.pause()
            assert app_instance.query_one("#output-generate-change-review") is not None
            assert app_instance.query_one("#settings-edit-review-output-dir") is not None
            assert app_instance.query_one("#settings-label-review-output-dir") is not None

    asyncio.run(_run())


def test_no_cli_command_introduced_for_change_review() -> None:
    parser = app_module.build_cli_parser()
    assert parser is not None
    # Change Review stays TUI-only; the headless CLI does not expose it yet.
    with pytest.raises(CliError):
        parser.parse_args(["review"])


def test_textual_change_review_uses_its_own_action_id(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app()
    launched: list[tuple[str, str]] = []
    monkeypatch.setattr(
        app_instance,
        "_start_action",
        lambda label, action_fn, *, action_id, marks_dirty=False, clear_dirty_on_success=False: launched.append(
            (label, action_id)
        ),
    )

    app_instance._run_generate_change_review()

    assert launched == [("Generate Change Review", "action-change-review")]
