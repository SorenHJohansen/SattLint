"""Target discovery and identity checks used by the project commands."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import cast

from sattlint.config.defaults import DEFAULT_CONFIG
from sattlint.config.types import ConfigDict
from sattlint.project.targets import scan_project_targets


def _config(program_dir: Path, **overrides: object) -> ConfigDict:
    values: dict[str, object] = {
        **deepcopy(DEFAULT_CONFIG),
        "program_dir": str(program_dir),
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "analyzed_programs_and_libraries": [],
        "mode": "official",
    }
    values.update(overrides)
    return cast(ConfigDict, values)


def _write(root: Path, name: str, suffix: str = ".x") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{name}{suffix}"
    path.write_text("(* module *)\n", encoding="utf-8")
    return path


def test_scan_reports_programs_and_libraries_with_their_paths(tmp_path: Path) -> None:
    programs = tmp_path / "programs"
    libraries = tmp_path / "libraries"
    program_path = _write(programs, "Demo")
    library_path = _write(libraries, "SharedLib")

    scan = scan_project_targets(
        _config(programs, ABB_lib_dir=str(libraries), analyzed_programs_and_libraries=["Demo", "SharedLib"])
    )

    assert not scan.errors
    assert [(target.name, target.kind, target.path) for target in scan.targets] == [
        ("Demo", "program", program_path),
        ("SharedLib", "library", library_path),
    ]


def test_scan_errors_when_two_roots_provide_the_same_target(tmp_path: Path) -> None:
    programs = tmp_path / "programs"
    libraries = tmp_path / "libraries"
    _write(programs, "Demo")
    _write(libraries, "Demo")

    scan = scan_project_targets(_config(programs, ABB_lib_dir=str(libraries)))

    assert any("provided by both" in error for error in scan.errors)


def test_scan_errors_when_a_configured_target_keeps_its_suffix(tmp_path: Path) -> None:
    programs = tmp_path / "programs"
    _write(programs, "Demo")

    scan = scan_project_targets(_config(programs, analyzed_programs_and_libraries=["Demo.x"]))

    assert any("includes the file suffix" in error and "'Demo'" in error for error in scan.errors)


def test_scan_errors_when_a_configured_target_is_missing(tmp_path: Path) -> None:
    programs = tmp_path / "programs"
    programs.mkdir()

    scan = scan_project_targets(_config(programs, analyzed_programs_and_libraries=["Missing"]))

    assert any("was not found" in error for error in scan.errors)


def test_scan_warns_about_a_duplicate_name_in_one_root(tmp_path: Path) -> None:
    programs = tmp_path / "programs"
    _write(programs, "Demo", ".s")
    _write(programs, "Demo", ".x")

    scan = scan_project_targets(_config(programs, mode="draft"))

    assert any("Duplicate target" in warning for warning in scan.warnings)
