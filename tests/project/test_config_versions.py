"""Schema-version and unknown-key behavior for the user configuration."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

import pytest

from sattlint import config as config_module
from sattlint.config import io as config_io
from sattlint.config.types import ConfigDict


def _read_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _write_older_config(path: Path) -> str:
    """A pre-versioning config: settings, no version key, plus unknown keys."""
    text = "\n".join(
        [
            'mode = "draft"',
            'program_dir = "programs"',
            'future_setting = "keep-me"',
            "",
            "[analysis]",
            "cyclomatic_module_threshold = 30",
            "future_threshold = 7",
            "",
            "[run_history]",
            "enabled = false",
            "limit = 5",
            'archive_dir = "runs-archive"',
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")
    return text


def test_older_config_migrates_in_memory_and_keeps_unknown_keys_on_save(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    original = _write_older_config(path)

    loaded, created = config_module.load_config(path, emit_fn=lambda _message: None)

    assert created is False
    assert loaded["mode"] == "draft"
    assert loaded["analysis"]["cyclomatic_module_threshold"] == 30
    assert loaded["run_history"] == {"enabled": False, "limit": 5}
    assert "future_setting" not in loaded
    assert "future_threshold" not in loaded["analysis"]
    # Reading migrates in memory only; the file is untouched until a save.
    assert path.read_text(encoding="utf-8") == original

    config_module.save_config(path, loaded)

    written = _read_toml(path)
    assert written["schema_version"] == config_io.CONFIG_SCHEMA_VERSION
    assert written["mode"] == "draft"
    assert written["future_setting"] == "keep-me"
    assert cast(dict[str, object], written["analysis"])["future_threshold"] == 7
    assert written["run_history"] == {
        "enabled": False,
        "limit": 5,
        "archive_dir": "runs-archive",
    }


def test_a_current_config_round_trips_its_version(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    config_module.load_config(path, emit_fn=lambda _message: None)

    assert _read_toml(path)["schema_version"] == config_io.CONFIG_SCHEMA_VERSION

    loaded, created = config_module.load_config(path, emit_fn=lambda _message: None)
    assert created is False
    assert _read_toml(path)["schema_version"] == config_io.CONFIG_SCHEMA_VERSION
    assert loaded["mode"] == "official"


def test_a_newer_config_is_refused_on_load_and_save(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    newer = config_io.CONFIG_SCHEMA_VERSION + 1
    original = f'schema_version = {newer}\nmode = "draft"\n'
    path.write_text(original, encoding="utf-8")

    with pytest.raises(config_io.ConfigVersionError) as load_error:
        config_module.load_config(path)
    load_message = str(load_error.value)
    assert str(path) in load_message
    assert f"schema version {newer}" in load_message
    assert f"supports version {config_io.CONFIG_SCHEMA_VERSION}" in load_message

    with pytest.raises(config_io.ConfigVersionError) as save_error:
        config_module.save_config(path, cast(ConfigDict, {"mode": "official"}))
    save_message = str(save_error.value)
    assert str(path) in save_message
    assert f"schema version {newer}" in save_message
    assert f"supports version {config_io.CONFIG_SCHEMA_VERSION}" in save_message

    # A refused save leaves the newer file exactly as it was.
    assert path.read_text(encoding="utf-8") == original


def test_app_settings_save_preserves_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _write_older_config(path)

    config_module.save_app_settings(path, cast(ConfigDict, {"output": {"retention_lines": 100}}))

    written = _read_toml(path)
    assert written["schema_version"] == config_io.CONFIG_SCHEMA_VERSION
    assert cast(dict[str, object], written["output"])["retention_lines"] == 100
    assert written["future_setting"] == "keep-me"
    assert cast(dict[str, object], written["analysis"])["future_threshold"] == 7


def test_an_invalid_version_is_rejected_and_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('schema_version = "one"\nmode = "draft"\n', encoding="utf-8")

    with pytest.raises(config_io.ConfigVersionError) as raised:
        config_module.load_config(path)

    message = str(raised.value)
    assert str(path) in message
    assert "invalid schema_version" in message
