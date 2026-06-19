# pyright: reportArgumentType=false
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from sattlint import app


def test_telemetry_summary_command_logs_debug_traceback_for_summary_errors(
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail_summary(_path: Path) -> dict[str, Any]:
        raise ValueError("bad telemetry")

    with caplog.at_level(logging.ERROR, logger="SattLint"):
        exit_code = app.app_cli_commands_module.run_telemetry_summary_command(
            {"debug": True},
            config_path=Path("config.toml"),
            output_format="text",
            output_path=None,
            telemetry_output_path_fn=lambda config_path: config_path.with_suffix(".telemetry.json"),
            summarize_telemetry_fn=fail_summary,
            render_text_summary_fn=lambda summary: str(summary),
            exit_success=app.EXIT_SUCCESS,
            exit_usage_error=app.EXIT_USAGE_ERROR,
        )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_USAGE_ERROR
    assert "Telemetry summary failed: bad telemetry" in out
    assert any("Telemetry summary failed for config.telemetry.json" in message for message in caplog.messages)
    assert "Traceback (most recent call last)" in caplog.text


def test_simulate_command_logs_debug_traceback_for_unexpected_failures(
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail_simulation(cfg: dict[str, Any], **kwargs: object) -> object:
        del cfg, kwargs
        raise RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="SattLint"):
        exit_code = app.app_cli_commands_module.run_simulate_command(
            {"debug": True},
            target_path="program.s",
            module_name="Main",
            mode="steady-state",
            max_scans=25,
            output_format="text",
            output_path=None,
            use_cache=False,
            simulate_fn=fail_simulation,
            exit_success=app.EXIT_SUCCESS,
            exit_usage_error=app.EXIT_USAGE_ERROR,
        )

    out = capsys.readouterr().out
    assert exit_code == app.EXIT_USAGE_ERROR
    assert "Simulation failed: boom" in out
    assert any("Simulation command failed for module 'Main' from 'program.s'" in message for message in caplog.messages)
    assert "Traceback (most recent call last)" in caplog.text
