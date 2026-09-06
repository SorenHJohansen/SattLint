# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportArgumentType=false
"""Tests for the typed application service API (Phase 5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sattline_parser import parse_source_text as parser_core_parse_source_text

from sattlint.application import project as project_application
from sattlint.application import service as service_module
from sattlint.application.service import (
    AnalysisOptions,
    Project,
    ProjectAnalysisResult,
    analyze_project,
)
from sattlint.models.project_graph import ProjectGraph
from tests.helpers.app_menus_support import VALID_SINGLE_FILE


@pytest.fixture()
def project() -> Project:
    base_picture = parser_core_parse_source_text(VALID_SINGLE_FILE)
    graph = ProjectGraph()
    entry_file = Path("/tmp/programs/Invocation.s")
    graph.index_from_basepic(
        base_picture,
        source_path=entry_file,
        library_name="programs",
    )
    return Project(
        name="Invocation",
        base_picture=base_picture,
        graph=graph,
        config={
            "program_dir": "/tmp/programs",
            "other_lib_dirs": [],
            "ABB_lib_dir": "/tmp/abb",
            "mode": "draft",
            "debug": False,
            "analyzed_programs_and_libraries": ["Invocation"],
        },
        entry_file=entry_file,
        workspace_root=Path("/tmp/programs"),
    )


def test_analyze_project_builds_snapshot_and_runs_default_analyzers(project: Project) -> None:
    result = analyze_project(project, AnalysisOptions())

    assert isinstance(result, ProjectAnalysisResult)
    assert result.project is project
    assert result.snapshot.workspace_root == Path("/tmp/programs")
    assert result.snapshot.base_picture is project.base_picture
    assert result.selected_analyzer_keys
    assert result.analyzer_reports


def test_analyze_project_respects_selected_analyzer_keys(project: Project) -> None:
    result = analyze_project(
        project,
        AnalysisOptions(selected_analyzer_keys=("naming",)),
    )

    assert set(result.selected_analyzer_keys) <= {"naming"}
    assert all(report.analyzer_key == "naming" for report in result.analyzer_reports)


def test_analyze_project_selected_issue_kinds_are_honored(project: Project) -> None:
    result = analyze_project(
        project,
        AnalysisOptions(
            selected_analyzer_keys=("variables",),
            selected_issue_kinds=frozenset({"naming"}),
            collect_variable_diagnostics=True,
        ),
    )

    assert result.selected_analyzer_keys == ("variables",)
    assert result.analyzer_reports


def test_load_project_handle_builds_typed_project(monkeypatch) -> None:
    base_picture = parser_core_parse_source_text(VALID_SINGLE_FILE)
    graph = ProjectGraph()
    entry_file = Path("/tmp/programs/Invocation.s")
    graph.index_from_basepic(base_picture, source_path=entry_file, library_name="programs")

    monkeypatch.setattr(
        project_application,
        "load_project",
        lambda _cfg, _target_name, **kwargs: (base_picture, graph),
    )
    cfg = {
        "program_dir": "/tmp/programs",
        "other_lib_dirs": [],
        "ABB_lib_dir": "/tmp/abb",
        "mode": "draft",
        "debug": False,
        "analyzed_programs_and_libraries": ["Invocation"],
    }

    loaded = service_module.load_project_handle(cfg, "Invocation")

    assert isinstance(loaded, Project)
    assert loaded.name == "Invocation"
    assert loaded.base_picture is base_picture
    assert loaded.graph is graph
    assert loaded.entry_file.resolve() == entry_file.resolve()
    assert loaded.workspace_root == Path("/tmp/programs").resolve()
