"""Migration and validation for the required version 2 [string_capacities] table."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from sattlint.config.string_capacities import (
    STANDARD_STRING_CAPACITIES,
    STRING_CAPACITY_KEYS,
    StringCapacitiesDict,
)
from sattlint.project.io import SLPROJ_FILENAME, SLPROJ_VERSION, init_project, load_project, save_project

PROJECT_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "projects"

STANDARD_TABLE = (
    "[string_capacities]\nidentstring = 15\ntagstring = 30\nstring = 40\nlinestring = 80\nmaxstring = 140\n"
)


def _version_one_project() -> str:
    """A realistic version 1 project: settings only, no capacity table."""
    return "\n".join(
        [
            "slproj_version = 1",
            'analyzed_programs_and_libraries = ["pHByWeight"]',
            'analyzers = ["variables", "sfc"]',
            'mode = "official"',
            'program_dir = "programs"',
            'ABB_lib_dir = "libs"',
            'icf_dir = "icf"',
            "other_lib_dirs = []",
            "",
            "[analysis]",
            "cyclomatic_module_threshold = 30",
            "",
        ]
    )


def _table(**overrides: str) -> str:
    """The standard table with individual values replaced."""
    values: dict[str, object] = dict(STANDARD_STRING_CAPACITIES.as_dict())
    values.update(overrides)
    rows = "\n".join(f"{key} = {values[key]}" for key in STRING_CAPACITY_KEYS)
    return f"[string_capacities]\n{rows}\n"


def test_version_one_project_is_rejected_and_names_the_required_table(tmp_path: Path) -> None:
    path = tmp_path / SLPROJ_FILENAME
    original = _version_one_project()
    path.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        load_project(path)

    message = str(excinfo.value)
    assert "version 1" in message
    assert "[string_capacities]" in message
    for key, value in STANDARD_STRING_CAPACITIES.as_dict().items():
        assert f"{key} = {value}" in message
    # Rejecting is not migrating: the file is left exactly as it was.
    assert path.read_text(encoding="utf-8") == original


def test_migrated_version_one_project_keeps_its_settings(tmp_path: Path) -> None:
    path = tmp_path / SLPROJ_FILENAME
    migrated = _version_one_project().replace("slproj_version = 1", f"slproj_version = {SLPROJ_VERSION}")
    path.write_text(f"{migrated}\n{STANDARD_TABLE}", encoding="utf-8")

    project = load_project(path)

    assert project.data["slproj_version"] == SLPROJ_VERSION
    assert project.data["analyzed_programs_and_libraries"] == ["pHByWeight"]
    assert project.data["analyzers"] == ["variables", "sfc"]
    assert project.data["program_dir"] == "programs"
    assert project.data["analysis"]["cyclomatic_module_threshold"] == 30
    assert project.data["string_capacities"] == STANDARD_STRING_CAPACITIES.as_dict()


def test_missing_table_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / SLPROJ_FILENAME
    path.write_text(f"slproj_version = {SLPROJ_VERSION}\nmode = 'official'\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"Missing required \[string_capacities\] table"):
        load_project(path)


@pytest.mark.parametrize("missing", STRING_CAPACITY_KEYS)
def test_missing_key_is_rejected_and_named(tmp_path: Path, missing: str) -> None:
    path = tmp_path / SLPROJ_FILENAME
    values = {key: value for key, value in STANDARD_STRING_CAPACITIES.as_dict().items() if key != missing}
    rows = "\n".join(f"{key} = {value}" for key, value in values.items())
    path.write_text(f"slproj_version = {SLPROJ_VERSION}\n[string_capacities]\n{rows}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=rf"Missing required \[string_capacities\] key '{missing}'"):
        load_project(path)


def test_unknown_key_is_rejected_and_named(tmp_path: Path) -> None:
    path = tmp_path / SLPROJ_FILENAME
    path.write_text(
        f"slproj_version = {SLPROJ_VERSION}\n{STANDARD_TABLE}bytes = 3\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"Unknown \[string_capacities\] key 'bytes'"):
        load_project(path)


@pytest.mark.parametrize("key", STRING_CAPACITY_KEYS)
@pytest.mark.parametrize("value", ["0", "-1"])
def test_non_positive_value_is_rejected_and_named(tmp_path: Path, key: str, value: str) -> None:
    path = tmp_path / SLPROJ_FILENAME
    path.write_text(f"slproj_version = {SLPROJ_VERSION}\n{_table(**{key: value})}", encoding="utf-8")

    with pytest.raises(ValueError, match=rf"Invalid \[string_capacities\] value for '{key}'.*positive integer"):
        load_project(path)


def test_standard_fixture_loads_with_the_standard_table() -> None:
    project = load_project(PROJECT_FIXTURES / "standard.slproj")

    assert project.data["slproj_version"] == SLPROJ_VERSION
    assert project.data["analyzed_programs_and_libraries"] == ["Demo"]
    assert project.data["analyzers"] == ["variables"]
    assert project.data["string_capacities"] == STANDARD_STRING_CAPACITIES.as_dict()
    assert project.to_config_dict()["string_capacities"] == STANDARD_STRING_CAPACITIES.as_dict()


def test_custom_capacity_fixture_round_trips_through_save_and_load(tmp_path: Path) -> None:
    project = load_project(PROJECT_FIXTURES / "custom-capacities.slproj")
    expected = {"identstring": 10, "tagstring": 20, "string": 25, "linestring": 60, "maxstring": 100}
    assert project.data["slproj_version"] == SLPROJ_VERSION
    assert project.data["string_capacities"] == expected

    copy_path = tmp_path / "custom.slproj"
    save_project(copy_path, project.data)

    assert load_project(copy_path).data["string_capacities"] == expected


def test_valid_table_round_trips_through_save_and_load(tmp_path: Path) -> None:
    path = tmp_path / "proj.slproj"
    custom: StringCapacitiesDict = {
        "identstring": 12,
        "tagstring": 24,
        "string": 36,
        "linestring": 72,
        "maxstring": 120,
    }
    init_project(path)
    data = load_project(path).data
    data["string_capacities"] = custom
    save_project(path, data)

    with path.open("rb") as fh:
        written = tomllib.load(fh)
    assert written["string_capacities"] == custom

    reloaded = load_project(path)
    assert reloaded.data["string_capacities"] == custom
