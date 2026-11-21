# pyright: reportPrivateUsage=false
"""The required [string_capacities] table, version 2, and cache invalidation."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from sattlint.analyzers.framework import build_analysis_context
from sattlint.cache import compute_cache_key
from sattlint.config.string_capacities import (
    STANDARD_STRING_CAPACITIES,
    StringCapacities,
    resolve_string_capacities,
)
from sattlint.parser_api import BasePicture
from sattlint.project.io import SLPROJ_FILENAME, SLPROJ_VERSION, load_project
from tests.helpers import named_object

STANDARD_TABLE = (
    "[string_capacities]\nidentstring = 15\ntagstring = 30\nstring = 40\nlinestring = 80\nmaxstring = 140\n"
)
CUSTOM_TABLE = "[string_capacities]\nidentstring = 10\ntagstring = 20\nstring = 25\nlinestring = 60\nmaxstring = 100\n"


def _write(path: Path, *, version: int = SLPROJ_VERSION, table: str = STANDARD_TABLE, body: str = "") -> None:
    path.write_text(f"slproj_version = {version}\n{body}{table}", encoding="utf-8")


def test_version_two_project_loads_and_carries_the_typed_table(tmp_path: Path) -> None:
    path = tmp_path / SLPROJ_FILENAME
    _write(path, table=CUSTOM_TABLE)

    project = load_project(path)

    assert project.data["slproj_version"] == 2
    assert project.data["string_capacities"] == {
        "identstring": 10,
        "tagstring": 20,
        "string": 25,
        "linestring": 60,
        "maxstring": 100,
    }
    assert resolve_string_capacities(project.to_config_dict()) == StringCapacities(
        identstring=10,
        tagstring=20,
        string=25,
        linestring=60,
        maxstring=100,
    )


def test_version_one_project_names_the_required_table_and_its_values(tmp_path: Path) -> None:
    path = tmp_path / SLPROJ_FILENAME
    _write(path, version=1, table="")

    with pytest.raises(
        ValueError,
        match=r"version 1.*\[string_capacities\].*identstring = 15.*tagstring = 30.*string = 40.*linestring = 80.*maxstring = 140",
    ):
        load_project(path)


def test_missing_table_is_a_load_error(tmp_path: Path) -> None:
    path = tmp_path / SLPROJ_FILENAME
    _write(path, table="")

    with pytest.raises(ValueError, match=r"Missing required \[string_capacities\] table"):
        load_project(path)


def test_missing_capacity_is_a_load_error_that_names_the_key(tmp_path: Path) -> None:
    path = tmp_path / SLPROJ_FILENAME
    _write(path, table="[string_capacities]\nidentstring = 15\ntagstring = 30\nlinestring = 80\nmaxstring = 140\n")

    with pytest.raises(ValueError, match=r"Missing required \[string_capacities\] key 'string'"):
        load_project(path)


def test_unknown_capacity_is_a_load_error_that_names_the_key(tmp_path: Path) -> None:
    path = tmp_path / SLPROJ_FILENAME
    _write(
        path,
        table=(
            "[string_capacities]\nidentstring = 15\ntagstring = 30\nstring = 40\n"
            "linestring = 80\nmaxstring = 140\nbytes = 3\n"
        ),
    )

    with pytest.raises(ValueError, match=r"Unknown \[string_capacities\] key 'bytes'"):
        load_project(path)


@pytest.mark.parametrize("value", ["0", "-1"])
def test_non_positive_capacity_is_a_load_error(tmp_path: Path, value: str) -> None:
    path = tmp_path / SLPROJ_FILENAME
    _write(
        path,
        table=(
            "[string_capacities]\nidentstring = 15\ntagstring = 30\n"
            f"string = {value}\nlinestring = 80\nmaxstring = 140\n"
        ),
    )

    with pytest.raises(ValueError, match=r"Invalid \[string_capacities\] value for 'string'.*positive integer"):
        load_project(path)


def test_non_integer_capacity_is_a_load_error(tmp_path: Path) -> None:
    path = tmp_path / SLPROJ_FILENAME
    _write(
        path,
        table=(
            '[string_capacities]\nidentstring = 15\ntagstring = 30\nstring = "40"\nlinestring = 80\nmaxstring = 140\n'
        ),
    )

    with pytest.raises(ValueError, match=r"Invalid \[string_capacities\] value for 'string'.*positive integer"):
        load_project(path)


def test_analysis_context_carries_the_project_capacities(tmp_path: Path) -> None:
    path = tmp_path / SLPROJ_FILENAME
    _write(path, table=CUSTOM_TABLE)
    cfg = load_project(path).to_config_dict()

    context = build_analysis_context(cast(BasePicture, named_object("Target")), config=cfg)

    assert context.string_capacities == StringCapacities(
        identstring=10,
        tagstring=20,
        string=25,
        linestring=60,
        maxstring=100,
    )


def test_analysis_context_uses_standard_values_without_a_project() -> None:
    context = build_analysis_context(cast(BasePicture, named_object("Target")))

    assert context.string_capacities == STANDARD_STRING_CAPACITIES


def test_a_changed_capacity_changes_the_project_cache_key(tmp_path: Path) -> None:
    standard_path = tmp_path / "standard" / SLPROJ_FILENAME
    custom_path = tmp_path / "custom" / SLPROJ_FILENAME
    standard_path.parent.mkdir()
    custom_path.parent.mkdir()
    _write(standard_path)
    _write(custom_path, table=CUSTOM_TABLE)

    standard_cfg = load_project(standard_path).to_config_dict()
    custom_cfg = load_project(custom_path).to_config_dict()

    assert compute_cache_key(standard_cfg, analysis_target="Target") != compute_cache_key(
        custom_cfg, analysis_target="Target"
    )
