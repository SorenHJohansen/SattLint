# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
"""Config-loading warnings for keys that would otherwise be silently stripped."""

from __future__ import annotations

from pathlib import Path

import pytest

from sattlint import config as config_module


def test_load_config_warns_on_misspelled_top_level_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('program_dirr = "programs"\n', encoding="utf-8")

    loaded, created = config_module.load_config(config_path)

    out = capsys.readouterr().out
    assert created is False
    assert "Config warning [program_dirr]" in out
    assert "program_dirr" not in loaded
    assert loaded["program_dir"] == ""


def test_load_config_warns_on_unknown_section_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[run_history]\nenabled = true\npath = "legacy.jsonl"\n', encoding="utf-8")

    loaded, created = config_module.load_config(config_path)

    out = capsys.readouterr().out
    assert created is False
    assert "Config warning [run_history.path]" in out
    assert loaded["run_history"] == {"enabled": True, "limit": 50}


def test_config_warning_keeps_a_bracketed_message_intact(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "programs ] draft"
    config_path = tmp_path / "config.toml"
    config_path.write_text(f'program_dir = "{missing}"\n', encoding="utf-8")

    config_module.load_config(config_path)

    out = capsys.readouterr().out
    assert f"Config warning [program_dir]: program_dir does not exist: {missing}" in out
