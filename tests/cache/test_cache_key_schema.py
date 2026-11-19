"""The project cache key is one schema with a version and a stable encoding."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from sattlint import cache as cache_module
from sattlint import parser_api
from sattlint.config import DEFAULT_CONFIG
from sattlint.config.types import ConfigDict


def _cfg(**overrides: object) -> ConfigDict:
    return cast(ConfigDict, {**DEFAULT_CONFIG, **overrides})


def test_cache_key_is_stable_for_equivalent_configuration(tmp_path: Path) -> None:
    program_dir = tmp_path / "program"

    first = cache_module.compute_cache_key(
        _cfg(program_dir=str(program_dir), mode="official", other_lib_dirs=[str(tmp_path / "lib")]),
        analysis_target="Demo",
    )
    second = cache_module.compute_cache_key(
        _cfg(program_dir=str(program_dir), mode=" Official ", other_lib_dirs=[str(tmp_path / "lib")]),
        analysis_target=" Demo ",
    )

    assert first == second


def test_cache_key_folds_repeated_directories_but_keeps_search_order(tmp_path: Path) -> None:
    first_lib = str(tmp_path / "first")
    second_lib = str(tmp_path / "second")
    program_dir = str(tmp_path / "program")

    repeated = cache_module.compute_cache_key(
        _cfg(program_dir=program_dir, other_lib_dirs=[first_lib, second_lib, first_lib])
    )
    deduplicated = cache_module.compute_cache_key(_cfg(program_dir=program_dir, other_lib_dirs=[first_lib, second_lib]))
    reversed_order = cache_module.compute_cache_key(
        _cfg(program_dir=program_dir, other_lib_dirs=[second_lib, first_lib])
    )

    # A repeated root is equivalent, but an earlier root wins lookups, so a
    # different order is a different analysis input.
    assert repeated == deduplicated
    assert reversed_order != deduplicated


def test_cache_key_tracks_the_installed_parser_version(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg()
    baseline = cache_module.compute_cache_key(cfg)

    monkeypatch.setattr(parser_api, "PARSER_VERSION", "0.0.0-test")

    assert cache_module.compute_cache_key(cfg) != baseline


def test_cache_key_tracks_the_analysis_target() -> None:
    cfg = _cfg()

    assert cache_module.compute_cache_key(cfg, analysis_target="One") != cache_module.compute_cache_key(
        cfg, analysis_target="Two"
    )


def test_report_cache_key_carries_the_same_schema_and_parser_version(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = cache_module.compute_analysis_report_cache_key("project", "variables")

    monkeypatch.setattr(parser_api, "PARSER_VERSION", "0.0.0-test")

    assert cache_module.compute_analysis_report_cache_key("project", "variables") != baseline


def test_cache_key_schema_version_is_explicit() -> None:
    assert isinstance(cache_module.CACHE_KEY_SCHEMA_VERSION, int)
    assert cache_module.CACHE_KEY_SCHEMA_VERSION >= 1
