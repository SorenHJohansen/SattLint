# pyright: reportPrivateUsage=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from sattlint import cache as cache_module
from sattlint import runs as runs_module
from sattlint.application import checks_records, checks_results
from sattlint.application import project as project_application
from sattlint.config import DEFAULT_CONFIG, ConfigDict
from sattlint.models.project_graph import ProjectFailure, ProjectGraph
from sattlint.parser_api import BasePicture
from sattlint.project.support import TargetLoadError
from tests.helpers import AnalysisGraphStub, named_object


def test_iter_loaded_projects_skips_failed_targets(
    noop_screen: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = ["Broken", "Working"]
    working_graph = AnalysisGraphStub()

    def fake_load_project(
        _cfg: ConfigDict,
        target_name: str | None = None,
        *,
        refresh_ast: bool = False,
        collect_stage_timings: bool = False,
    ) -> tuple[object, AnalysisGraphStub]:
        if target_name == "Broken":
            raise TargetLoadError(
                "Broken",
                resolved=["dep_a", "dep_b"],
                missing=[
                    "Broken parse/transform error: root failed",
                    "dep_c parse/transform error: something bad happened",
                    "transitive_lib parse/transform error: nested failure",
                    "Missing code file for 'dep_d' (draft)",
                ],
                warnings=[
                    "dep_c: validation warning one",
                    "transitive_lib: validation warning two",
                ],
                direct_dependencies=["dep_c", "dep_d"],
                failures={
                    "BROKEN": ProjectFailure(
                        "Broken", "Broken parse/transform error: root failed", detail="root failed", line=7, column=2
                    ),
                    "DEP_C": ProjectFailure(
                        "dep_c",
                        "dep_c parse/transform error: something bad happened",
                        detail="something bad happened",
                        line=12,
                        column=4,
                        length=3,
                    ),
                    "TRANSITIVE_LIB": ProjectFailure(
                        "transitive_lib",
                        "transitive_lib parse/transform error: nested failure",
                        detail="nested failure",
                        line=20,
                    ),
                    "dep_d": ProjectFailure(
                        "dep_d",
                        "Missing code file for 'dep_d' (draft)",
                        detail="code file is missing (draft)",
                    ),
                },
            )
        return "bp-working", working_graph

    monkeypatch.setattr(project_application, "load_project", fake_load_project)

    failures: list[tuple[str, str]] = []
    projects = list(
        project_application._iter_loaded_projects(
            cast(ConfigDict, cfg), failure_sink=lambda name, message: failures.append((name, message))
        )
    )

    assert [name for name, _message in failures] == ["Broken"]
    assert "root failed" in failures[0][1]

    out = capsys.readouterr().out
    assert projects == [("Working", "bp-working", working_graph)]
    assert "=== Target: Broken ===" in out
    assert "Failed to load target:" in out
    assert "Target 'Broken' was not parsed." in out
    assert "Direct dependencies from the target file (2):" in out
    assert "Resolved targets (2):" in out
    assert "  - dep_a" in out
    assert "Root target validation errors (1):" in out
    assert "  - Broken: root failed (line 7, column 2)" in out
    assert "Failed direct dependencies (2):" in out
    assert "  - dep_c: something bad happened (line 12, column 4, length 3)" in out
    assert "  - dep_d: code file is missing (draft)" in out
    assert "Direct dependency warnings (1):" in out
    assert "Transitive dependency failures (1):" in out
    assert "  - transitive_lib: nested failure (line 20)" in out
    assert "Transitive dependency warnings (1):" in out


def test_print_validation_warnings_truncates(monkeypatch: pytest.MonkeyPatch):
    lines: list[str] = []
    monkeypatch.setattr(project_application, "emit_output", lambda message: lines.append(message))

    project_application._print_validation_warnings(["TargetA: warn1", "TargetA: warn2", "TargetA: warn3"], limit=2)

    assert lines == [
        "Validation warnings (3):",
        "  - warn1",
        "  - warn2",
        "  - ... (+1 more)",
    ]


def test_print_validation_warnings_formats_picture_display_entries(monkeypatch: pytest.MonkeyPatch):
    lines: list[str] = []
    monkeypatch.setattr(project_application, "emit_output", lambda message: lines.append(message))

    project_application._print_validation_warnings(
        [
            "TargetA: PictureDisplay in module 'Root.L1' path '+MissingPanel' could not be resolved: "
            "module 'MissingPanel' was not found under 'Root.L1'"
        ]
    )

    assert lines == [
        "Validation warnings (1):",
        "  - [Root.L1] '+MissingPanel'",
        "    module 'MissingPanel' was not found under 'Root.L1'",
    ]


def test_cache_key_for_target_passes_analysis_target(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_compute_cache_key(cfg: ConfigDict, *, analysis_target: str | None = None) -> str:
        captured.update({"cfg": cfg.copy(), "analysis_target": analysis_target})
        return "cache-key"

    monkeypatch.setattr(cache_module, "compute_cache_key", fake_compute_cache_key)

    cfg = {"mode": "official"}
    result = project_application._cache_key_for_target(cast(ConfigDict, cfg), "TargetA")

    assert result == "cache-key"
    assert cfg == {"mode": "official"}
    assert captured["cfg"] == {"mode": "official"}
    assert captured["analysis_target"] == "TargetA"


def test_source_paths_for_current_target_falls_back_to_header_name():
    project_bp = named_object("TargetA")
    graph = AnalysisGraphStub(source_files={Path("libs/Other.s"), Path("programs/TargetA.s")})

    result = project_application.source_paths_for_current_target(
        cast(BasePicture, project_bp), cast(ProjectGraph, graph)
    )

    assert result == {Path("programs/TargetA.s")}


def test_source_paths_for_current_target_prefers_graph_root_origin_path():
    project_bp = named_object("TargetA")
    graph = AnalysisGraphStub(source_files={Path("programs/TargetA.s")})
    graph.record_root_origin("TargetA", source_path=Path("libs/TargetA.s"), library_name="Libs")

    result = project_application.source_paths_for_current_target(
        cast(BasePicture, project_bp), cast(ProjectGraph, graph)
    )

    assert result == {Path("libs/TargetA.s")}


def test_target_is_library_returns_false_without_matching_source_paths():
    cfg = {"program_dir": "programs"}
    project_bp = named_object("TargetA", origin_file="Missing.s")
    graph = AnalysisGraphStub()

    assert (
        project_application._target_is_library(
            cast(ConfigDict, cfg), cast(BasePicture, project_bp), cast(ProjectGraph, graph)
        )
        is False
    )


def test_disabled_run_history_still_prunes_stored_runs():
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg["run_history"] = {"enabled": False, "limit": 1}
    runs_dir = cache_module.get_cache_dir() / "runs"
    for index in range(3):
        runs_module.save_run(
            runs_module.RunRecord(
                run_id="",
                started_at=f"2026-09-0{index}T10:00:00Z",
                finished_at=f"2026-09-0{index}T10:05:00Z",
                project_tag="TargetA",
            ),
            runs_dir=runs_dir,
        )

    result = checks_results.ChecksRunResult(output_lines=(), selected_analyzers=("variables",))
    stored = checks_records.persist_run_result(result, cast(ConfigDict, cfg), started_at="2026-09-09T10:00:00Z")

    assert stored is None
    assert len(runs_module.list_runs(runs_dir=runs_dir)) == 1


def test_ambiguous_origin_file_falls_through_to_the_target_name():
    project_bp = named_object("TargetA", origin_file="Dup.s")
    graph = AnalysisGraphStub(source_files={Path("libs/Dup.s"), Path("programs/Dup.s"), Path("programs/TargetA.s")})

    result = project_application.source_paths_for_current_target(
        cast(BasePicture, project_bp), cast(ProjectGraph, graph)
    )

    assert result == {Path("programs/TargetA.s")}
