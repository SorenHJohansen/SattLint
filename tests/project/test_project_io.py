# pyright: reportPrivateUsage=false
"""Focused tests for .slproj project file I/O."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from sattlint.config.types import ConfigDict
from sattlint.models.project_graph import ProjectGraph
from sattlint.project.io import (
    SLPROJ_FILENAME,
    SLPROJ_VERSION,
    ProjectAmbiguousError,
    _normalize,
    _project_path_hint,
    discover_project,
    discover_project_result,
    init_project,
    load_project,
    save_project,
)
from sattlint.project.loading import cache_manifest_files
from sattlint.project.models import SattLintProjectFile
from sattlint.project.types import DEFAULT_PROJECT_DICT, ProjectDict

STANDARD_STRING_CAPACITIES_TOML = (
    "[string_capacities]\nidentstring = 15\ntagstring = 30\nstring = 40\nlinestring = 80\nmaxstring = 140\n"
)


def _write_project(path: Path, body: str = "") -> None:
    """Write a valid version 2 project: top-level values, then the required table."""
    path.write_text(f"slproj_version = {SLPROJ_VERSION}\n{body}{STANDARD_STRING_CAPACITIES_TOML}", encoding="utf-8")


def test_discover_project_walks_upwards(tmp_path: Path) -> None:
    assert discover_project(tmp_path) is None
    (tmp_path / SLPROJ_FILENAME).write_text(f"slproj_version = {SLPROJ_VERSION}\n")
    assert discover_project(tmp_path) == (tmp_path / SLPROJ_FILENAME)
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert discover_project(nested) == (tmp_path / SLPROJ_FILENAME)
    found = discover_project(tmp_path / SLPROJ_FILENAME)
    assert found is not None and found.name == SLPROJ_FILENAME


def test_discover_project_prefers_the_literal_file_over_named_files(tmp_path: Path) -> None:
    (tmp_path / "alpha.slproj").write_text(f"slproj_version = {SLPROJ_VERSION}\n")
    (tmp_path / "beta.slproj").write_text(f"slproj_version = {SLPROJ_VERSION}\n")
    literal = tmp_path / SLPROJ_FILENAME
    literal.write_text(f"slproj_version = {SLPROJ_VERSION}\n")

    result = discover_project_result(tmp_path)

    assert result.selected == literal
    assert result.candidates == (literal, tmp_path / "alpha.slproj", tmp_path / "beta.slproj")
    assert not result.is_ambiguous
    assert discover_project(tmp_path) == literal


def test_discover_project_uses_the_only_named_file_in_the_nearest_directory(tmp_path: Path) -> None:
    named = tmp_path / "app.slproj"
    named.write_text(f"slproj_version = {SLPROJ_VERSION}\n")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    assert discover_project(nested) == named
    result = discover_project_result(nested)
    assert result.directory == tmp_path
    assert result.selected == named


def test_discover_project_reports_every_candidate_when_two_named_files_exist(tmp_path: Path) -> None:
    first = tmp_path / "first.slproj"
    second = tmp_path / "second.slproj"
    first.write_text(f"slproj_version = {SLPROJ_VERSION}\n")
    second.write_text(f"slproj_version = {SLPROJ_VERSION}\n")

    result = discover_project_result(tmp_path)

    assert result.is_ambiguous
    assert result.selected is None
    assert result.directory == tmp_path
    assert result.candidates == (first, second)
    with pytest.raises(ProjectAmbiguousError) as raised:
        discover_project(tmp_path)
    message = str(raised.value)
    assert str(first) in message
    assert str(second) in message
    assert "--project" in message


def test_discover_project_stops_before_an_ambiguous_parent(tmp_path: Path) -> None:
    (tmp_path / "one.slproj").write_text(f"slproj_version = {SLPROJ_VERSION}\n")
    (tmp_path / "two.slproj").write_text(f"slproj_version = {SLPROJ_VERSION}\n")
    child = tmp_path / "child"
    child.mkdir()
    child_project = child / "child.slproj"
    child_project.write_text(f"slproj_version = {SLPROJ_VERSION}\n")

    # The walk stops at the child, so the ambiguous parent never matters.
    assert discover_project(child) == child_project


def test_discover_project_matches_the_suffix_case_insensitively_and_ignores_directories(tmp_path: Path) -> None:
    (tmp_path / "not-a-project.slproj").mkdir()

    assert discover_project(tmp_path) is None

    named = tmp_path / "APP.SLPROJ"
    named.write_text(f"slproj_version = {SLPROJ_VERSION}\n")

    assert discover_project(tmp_path) == named


def test_discover_project_result_reports_nothing_found(tmp_path: Path) -> None:
    result = discover_project_result(tmp_path)

    assert result.selected is None
    assert result.directory is None
    assert result.candidates == ()
    assert not result.is_ambiguous
    assert discover_project(tmp_path) is None


def test_load_project_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "sub" / SLPROJ_FILENAME
    path.parent.mkdir()
    _write_project(path, "mode = 'official'\n")
    project = load_project(path)
    assert isinstance(project, SattLintProjectFile)
    assert project.data["mode"] == "official"
    assert project.path == path.resolve()


def test_load_project_missing_and_bad_version(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_project(tmp_path / "missing" / SLPROJ_FILENAME)
    path = tmp_path / SLPROJ_FILENAME
    path.write_text("slproj_version = 1\n")
    with pytest.raises(ValueError, match=r"Unsupported .slproj version 1.*\[string_capacities\]"):
        load_project(path)
    path.write_text("slproj_version = 0\n")
    with pytest.raises(ValueError, match=r"Unsupported .slproj version"):
        load_project(path)
    path.write_text("slproj_version = false\n")
    with pytest.raises(ValueError, match=r"slproj_version"):
        load_project(path)
    _write_project(path)
    assert load_project(path).data["slproj_version"] == SLPROJ_VERSION


def test_load_project_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"directory"):
        load_project(tmp_path)


def test_load_project_fills_defaults_for_missing_keys(tmp_path: Path) -> None:
    path = tmp_path / SLPROJ_FILENAME
    _write_project(path)

    project = load_project(path)

    assert project.data["analyzed_programs_and_libraries"] == []
    assert project.data["analyzers"] == []
    assert project.analyzers == ()
    assert project.data["mode"] == "official"
    assert project.data["analysis"] == DEFAULT_PROJECT_DICT["analysis"]
    assert project.data["string_capacities"] == DEFAULT_PROJECT_DICT["string_capacities"]

    cfg = project.to_config_dict()
    assert cfg["analyzed_programs_and_libraries"] == []
    assert cfg["other_lib_dirs"] == []
    assert cfg["string_capacities"] == DEFAULT_PROJECT_DICT["string_capacities"]


def test_load_project_rejects_wrong_value_types(tmp_path: Path) -> None:
    path = tmp_path / SLPROJ_FILENAME

    _write_project(path, "analyzed_programs_and_libraries = 'Demo'\n")
    with pytest.raises(ValueError, match=r"analyzed_programs_and_libraries"):
        load_project(path)

    _write_project(path, "analyzers = 'variables'\n")
    with pytest.raises(ValueError, match=r"analyzers"):
        load_project(path)

    _write_project(path, "analyzers = [1]\n")
    with pytest.raises(ValueError, match=r"analyzers"):
        load_project(path)

    _write_project(path, "mode = 3\n")
    with pytest.raises(ValueError, match=r"mode"):
        load_project(path)

    _write_project(path, "analysis = 'nope'\n")
    with pytest.raises(ValueError, match=r"analysis"):
        load_project(path)

    path.write_text("slproj_version = 'one'\n")
    with pytest.raises(ValueError, match=r"slproj_version"):
        load_project(path)


def test_load_project_warns_about_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / SLPROJ_FILENAME
    _write_project(path, "run_history = { enabled = false }\n")

    project = load_project(path)

    assert len(project.warnings) == 1
    assert "run_history" in project.warnings[0]
    assert "run_history" not in project.data


def test_save_and_reload_preserves_values(tmp_path: Path) -> None:
    path = tmp_path / "proj.slproj"
    data = {
        "slproj_version": SLPROJ_VERSION,
        "mode": "official",
        "program_dir": tmp_path / "src",
        "other_lib_dirs": [tmp_path / "lib1", tmp_path / "lib2"],
        "string_capacities": {"identstring": 11, "tagstring": 22, "string": 33, "linestring": 44, "maxstring": 55},
        "analysis": {"validate": True},
    }
    save_project(path, cast(ProjectDict, data))
    project = load_project(path)
    assert project.data["mode"] == "official"
    assert project.data["program_dir"] == str(tmp_path / "src")
    assert project.data["other_lib_dirs"] == [str(tmp_path / "lib1"), str(tmp_path / "lib2")]
    assert project.data["string_capacities"] == {
        "identstring": 11,
        "tagstring": 22,
        "string": 33,
        "linestring": 44,
        "maxstring": 55,
    }
    assert project.data["analysis"] == {"validate": True}


def test_project_analysis_survives_effective_config_merge(tmp_path: Path) -> None:
    path = tmp_path / "proj.slproj"
    data: dict[str, object] = {
        "slproj_version": SLPROJ_VERSION,
        "analyzed_programs_and_libraries": [],
        "mode": "official",
        "program_dir": tmp_path / "src",
        "ABB_lib_dir": "",
        "icf_dir": "",
        "analyzers": ["variables", "sfc"],
        "other_lib_dirs": [],
        "string_capacities": {"identstring": 15, "tagstring": 30, "string": 20, "linestring": 80, "maxstring": 140},
        "analysis": {"cyclomatic_module_threshold": 30},
    }
    save_project(path, cast(ProjectDict, data))
    project = load_project(path)

    cfg = project.to_default_merged_config_dict()

    assert cfg["analysis"]["cyclomatic_module_threshold"] == 30
    assert cfg["string_capacities"]["string"] == 20
    assert project.analyzers == ("variables", "sfc")
    # Analyzer selection belongs to the project file, not the merged runtime
    # config that every command and the UI work from.
    assert "analyzers" not in cfg


def test_project_analyzers_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "proj.slproj"
    init_project(path)

    data = load_project(path).data
    data["analyzers"] = ["dataflow", "sfc"]
    save_project(path, data)

    project = load_project(path)

    assert project.data["analyzers"] == ["dataflow", "sfc"]
    assert project.analyzers == ("dataflow", "sfc")


def test_project_merge_preserves_user_app_settings(tmp_path: Path) -> None:
    path = tmp_path / "proj.slproj"
    init_project(path)
    project = load_project(path)

    cfg = project.to_default_merged_config_dict(
        {
            "run_history": {"enabled": False, "limit": 5},
            "output": {"retention_lines": 100},
            "review": {"output_dir": str(tmp_path / "reviews")},
        }
    )

    assert cfg["run_history"] == {"enabled": False, "limit": 5}
    assert cfg["output"]["retention_lines"] == 100
    assert cfg["review"]["output_dir"] == str(tmp_path / "reviews")


def test_init_project_scaffolds_defaults(tmp_path: Path) -> None:
    path = tmp_path / "proj.slproj"
    project = init_project(path)
    assert path.exists()
    assert SLPROJ_VERSION == 2
    assert project.data["slproj_version"] == SLPROJ_VERSION
    assert project.data["mode"] == "official"
    assert project.data["analysis"] == DEFAULT_PROJECT_DICT["analysis"]
    assert project.data["string_capacities"] == {
        "identstring": 15,
        "tagstring": 30,
        "string": 40,
        "linestring": 80,
        "maxstring": 140,
    }
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


def test_init_project_does_not_alias_the_process_defaults(tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj.slproj")

    project.data["analyzed_programs_and_libraries"].append("Demo")
    project.data["other_lib_dirs"].append("libs")
    project.data["string_capacities"]["string"] = 7

    assert DEFAULT_PROJECT_DICT["analyzed_programs_and_libraries"] == []
    assert DEFAULT_PROJECT_DICT["other_lib_dirs"] == []
    assert DEFAULT_PROJECT_DICT["string_capacities"]["string"] == 40


def test_normalize_converters() -> None:
    assert _normalize(Path("/x/y")) == str(Path("/x/y"))
    assert _normalize([Path("a"), "b"]) == ["a", "b"]
    assert _normalize({"k": Path("v")}) == {"k": "v"}
    assert _normalize(5) == 5


def test_project_path_hint(tmp_path: Path) -> None:
    assert _project_path_hint(tmp_path / SLPROJ_FILENAME) == f"{tmp_path.name}/"
    assert _project_path_hint(tmp_path / "other.slproj") == str(tmp_path / "other.slproj")


def test_cache_manifest_tracks_the_icf_directory_for_new_files(tmp_path: Path) -> None:
    icf_dir = tmp_path / "icf"
    icf_dir.mkdir()
    graph = ProjectGraph()
    cfg = cast(ConfigDict, DEFAULT_PROJECT_DICT | {"icf_dir": str(icf_dir)})

    files = cache_manifest_files(
        cfg,
        graph,
        find_dependency_path_fn=lambda _name: None,
        resolve_graphics_companion_path_fn=lambda *_args, **_kwargs: None,
    )

    assert icf_dir in files
    (icf_dir / "new.icf").write_text("x", encoding="utf-8")
    assert icf_dir in files
