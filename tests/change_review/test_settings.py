# pyright: reportPrivateUsage=false
"""Tests for the Change Review output-location setting."""

from __future__ import annotations

from pathlib import Path

import pytest

from sattlint.change_review.settings import resolve_review_output_dir
from sattlint.config import defaults as config_defaults_module
from sattlint.config import io as config_io_module
from sattlint.config import validation as config_validation_module
from tests.helpers.change_review_support import build_cfg

pytestmark = pytest.mark.unit


def test_review_output_dir_is_part_of_default_config() -> None:
    assert "review" in config_defaults_module.TOP_LEVEL_CONFIG_FIELDS
    review_default = config_defaults_module.DEFAULT_CONFIG["review"]
    assert review_default["output_dir"] == ""


def test_review_setting_is_app_level_and_persists(tmp_path: Path):
    output_dir = tmp_path / "reviews"
    cfg = build_cfg(tmp_path, review_output_dir=str(output_dir))
    config_path = tmp_path / "config.toml"

    config_io_module.save_app_settings(config_path, cfg)
    loaded, _created = config_io_module.load_config(config_path)

    assert loaded["review"]["output_dir"] == str(output_dir)


def test_review_setting_survives_round_trip_save_config(tmp_path: Path):
    output_dir = tmp_path / "reviews"
    cfg = build_cfg(tmp_path, review_output_dir=str(output_dir))
    config_path = tmp_path / "config.toml"

    config_io_module.save_config(config_path, cfg)
    loaded, _created = config_io_module.load_config(config_path)

    assert loaded["review"]["output_dir"] == str(output_dir)


def test_validate_effective_config_accepts_review_setting(tmp_path: Path):
    cfg = build_cfg(tmp_path, review_output_dir=str(tmp_path / "out"))
    result = config_validation_module.validate_effective_config(cfg)
    assert result.passed


def test_validate_effective_config_rejects_unknown_review_keys(tmp_path: Path):
    cfg = build_cfg(tmp_path)
    cfg["review"]["bogus_key"] = True  # type: ignore[typeddict-item]
    result = config_validation_module.validate_effective_config(cfg)
    assert not result.passed
    assert any("review.bogus_key" in error.key_path for error in result.errors)


def test_resolve_review_output_dir_uses_configured_value(tmp_path: Path):
    output_dir = tmp_path / "configured"
    cfg = build_cfg(tmp_path, review_output_dir=str(output_dir))
    assert resolve_review_output_dir(cfg) == output_dir


def test_resolve_review_output_dir_defaults_when_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    default_dir = tmp_path / "default-review"
    monkeypatch.setattr("sattlint.change_review.settings.get_change_review_dir", lambda: default_dir)
    cfg = build_cfg(tmp_path, review_output_dir="")
    assert resolve_review_output_dir(cfg) == default_dir
