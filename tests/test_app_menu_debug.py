from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import pytest

from sattlint import app_menus


def test_save_configuration_logs_debug_traceback_on_save_error(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg: dict[str, Any] = {"debug": True, "analyzed_programs_and_libraries": ["Demo"], "other_lib_dirs": []}
    config_path = tmp_path / "config.json"

    def fail_save(*_args: object) -> None:
        raise PermissionError("read-only filesystem")

    def confirm(_prompt: str) -> bool:
        return True

    save_configuration = cast(Any, app_menus)._save_configuration

    with caplog.at_level(logging.ERROR, logger="SattLint"):
        dirty = save_configuration(
            cfg,
            dirty=True,
            config_path=config_path,
            save_config_fn=fail_save,
            confirm_fn=confirm,
        )

    assert dirty is True
    assert any(f"Failed to save config to {config_path}" in message for message in caplog.messages)
    assert "Traceback (most recent call last)" in caplog.text
