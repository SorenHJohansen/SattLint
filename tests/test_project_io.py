# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
"""Focused tests for .slproj project file I/O."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from sattlint.project.io import (
    SLPROJ_FILENAME,
    SLPROJ_VERSION,
    _normalize,
    _project_path_hint,
    discover_project,
    init_project,
    load_project,
    project_status,
    save_project,
)
from sattlint.project.models import SattLineProject
from sattlint.project.types import DEFAULT_PROJECT_DICT, ProjectDict


def test_discover_project_walks_upwards(tmp_path: Path) -> None:
    assert discover_project(tmp_path) is None
    (tmp_path / SLPROJ_FILENAME).write_text("slproj_version = 1\n")
    assert discover_project(tmp_path) == (tmp_path / SLPROJ_FILENAME)
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert discover_project(nested) == (tmp_path / SLPROJ_FILENAME)
    found = discover_project(tmp_path / SLPROJ_FILENAME)
    assert found is not None and found.name == SLPROJ_FILENAME


def test_load_project_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "sub" / SLPROJ_FILENAME
    path.parent.mkdir()
    path.write_text("slproj_version = 1\nmode = 'official'\n")
    project = load_project(path)
    assert isinstance(project, SattLineProject)
    assert project.data["mode"] == "official"
    assert project.path == path.resolve()


def test_load_project_missing_and_bad_version(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_project(tmp_path / "missing" / SLPROJ_FILENAME)
    path = tmp_path / SLPROJ_FILENAME
    path.write_text("slproj_version = 2\n")
    with pytest.raises(ValueError, match=r"Unsupported .slproj version"):
        load_project(path)


def test_save_and_reload_preserves_values(tmp_path: Path) -> None:
    path = tmp_path / "proj.slproj"
    data = {
        "slproj_version": 1,
        "mode": "official",
        "program_dir": tmp_path / "src",
        "other_lib_dirs": [tmp_path / "lib1", tmp_path / "lib2"],
        "analysis": {"validate": True},
    }
    save_project(path, cast(ProjectDict, data))
    project = load_project(path)
    assert project.data["mode"] == "official"
    assert project.data["program_dir"] == str(tmp_path / "src")
    assert project.data["other_lib_dirs"] == [str(tmp_path / "lib1"), str(tmp_path / "lib2")]
    assert project.data["analysis"] == {"validate": True}


def test_init_project_scaffolds_defaults(tmp_path: Path) -> None:
    path = tmp_path / "proj.slproj"
    project = init_project(path, name="Demo")
    assert path.exists()
    assert project.data["slproj_version"] == SLPROJ_VERSION
    assert project.data["mode"] == "official"
    assert project.data["analysis"] == DEFAULT_PROJECT_DICT["analysis"]
    with pytest.raises(FileExistsError):
        init_project(path)


def test_init_project_with_dirs(tmp_path: Path) -> None:
    path = tmp_path / "proj.slproj"
    project = init_project(
        path,
        program_dir="/opt/satt/src",
        ABB_lib_dir="/opt/satt/lib",
        icf_dir="/opt/satt/icf",
        other_lib_dirs=["/opt/satt/extra"],
    )
    assert project.data["program_dir"] == "/opt/satt/src"
    assert project.data["ABB_lib_dir"] == "/opt/satt/lib"
    assert project.data["icf_dir"] == "/opt/satt/icf"
    assert project.data["other_lib_dirs"] == ["/opt/satt/extra"]


def test_project_status_summary(tmp_path: Path) -> None:
    path = tmp_path / "proj.slproj"
    init_project(path)
    project = load_project(path)
    status = project_status(project)
    assert "proj.slproj" in status or tmp_path.name in status
    assert "mode=official" in status
    assert "0 targets" in status
    project.data["analyzed_programs_and_libraries"] = ["a", "b", "c", "d"]
    status = project_status(project)
    assert "4 targets" in status
    assert "a, b, c ..." in status
    project.data["analyzed_programs_and_libraries"] = ["solo"]
    assert "1 target" in project_status(project)


def test_normalize_converters() -> None:
    assert _normalize(Path("/x/y")) == "/x/y"
    assert _normalize([Path("a"), "b"]) == ["a", "b"]
    assert _normalize({"k": Path("v")}) == {"k": "v"}
    assert _normalize(5) == 5


def test_project_path_hint(tmp_path: Path) -> None:
    assert _project_path_hint(tmp_path / SLPROJ_FILENAME) == f"{tmp_path.name}/"
    assert _project_path_hint(tmp_path / "other.slproj") == str(tmp_path / "other.slproj")
