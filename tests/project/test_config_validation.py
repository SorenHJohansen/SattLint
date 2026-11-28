# pyright: reportPrivateUsage=false
"""Conditional directory validation for the merged effective configuration."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import cast

from sattlint.config.defaults import DEFAULT_CONFIG
from sattlint.config.types import ConfigDict
from sattlint.config.validation import validate_loaded_config


def _config(program_dir: Path, **overrides: object) -> ConfigDict:
    values: dict[str, object] = {
        **deepcopy(DEFAULT_CONFIG),
        "program_dir": str(program_dir),
        "ABB_lib_dir": "",
        "icf_dir": "",
        "other_lib_dirs": [],
        "analyzed_programs_and_libraries": [],
        "analyzers": ["variables"],
        "mode": "official",
    }
    values.update(overrides)
    return cast(ConfigDict, values)


def _write_program(root: Path, name: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{name}.x").write_text("(* module *)\n", encoding="utf-8")


def test_an_unselected_icf_analyzer_does_not_require_the_icf_directory(tmp_path: Path) -> None:
    programs = tmp_path / "programs"
    _write_program(programs, "Demo")

    result = validate_loaded_config(
        _config(
            programs,
            analyzed_programs_and_libraries=["Demo"],
            icf_dir=str(tmp_path / "missing-icf"),
        )
    )

    assert result.passed


def test_a_selected_icf_analyzer_requires_the_icf_directory(tmp_path: Path) -> None:
    programs = tmp_path / "programs"
    _write_program(programs, "Demo")

    result = validate_loaded_config(
        _config(
            programs,
            analyzed_programs_and_libraries=["Demo"],
            analyzers=["icf"],
            icf_dir=str(tmp_path / "missing-icf"),
        )
    )

    assert not result.passed
    assert [error.key_path for error in result.errors] == ["icf_dir"]


def test_unused_library_roots_do_not_fail_validation(tmp_path: Path) -> None:
    programs = tmp_path / "programs"
    _write_program(programs, "Demo")

    result = validate_loaded_config(
        _config(
            programs,
            analyzed_programs_and_libraries=["Demo"],
            ABB_lib_dir=str(tmp_path / "missing-abb"),
            other_lib_dirs=[str(tmp_path / "missing-other")],
        )
    )

    assert result.passed


def test_a_target_that_needs_a_library_root_validates_that_root(tmp_path: Path) -> None:
    programs = tmp_path / "programs"
    programs.mkdir()
    abb = tmp_path / "abb"
    _write_program(abb, "LibOnly")

    result = validate_loaded_config(
        _config(
            programs,
            analyzed_programs_and_libraries=["LibOnly"],
            ABB_lib_dir=str(abb),
            other_lib_dirs=[str(tmp_path / "missing-other")],
        )
    )

    assert not result.passed
    assert [error.key_path for error in result.errors] == ["other_lib_dirs[0]"]
