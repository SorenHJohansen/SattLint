# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false
from typing import Any, cast

from sattlint.config import DEFAULT_CONFIG
from sattlint.models.project_graph import ProjectFailure
from sattlint.project.support import TargetLoadError
from tests.helpers import AnalysisGraphStub, named_object
from tests.helpers.app_analysis_support import *


def test_iter_loaded_projects_skips_failed_targets(noop_screen, monkeypatch, capsys):
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg["analyzed_programs_and_libraries"] = ["Broken", "Working"]
    working_graph = AnalysisGraphStub()

    def fake_load_project(_cfg, target_name=None, *, use_cache=True, collect_stage_timings=False):
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
                    "broken": ProjectFailure("Broken", "Broken parse/transform error: root failed", line=7, column=2),
                    "dep_c": ProjectFailure(
                        "dep_c", "dep_c parse/transform error: something bad happened", line=12, column=4, length=3
                    ),
                    "transitive_lib": ProjectFailure(
                        "transitive_lib",
                        "transitive_lib parse/transform error: nested failure",
                        line=20,
                    ),
                },
            )
        return "bp-working", working_graph

    monkeypatch.setattr(project_application, "load_project", fake_load_project)

    projects = list(project_application._iter_loaded_projects(cfg))

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
    assert "Direct dependency warnings (1):" in out
    assert "Transitive dependency failures (1):" in out
    assert "  - transitive_lib: nested failure (line 20)" in out
    assert "Transitive dependency warnings (1):" in out


def test_print_validation_warnings_truncates(monkeypatch):
    lines: list[str] = []
    monkeypatch.setattr(project_application, "emit_output", lambda message: lines.append(message))

    project_application._print_validation_warnings(["TargetA: warn1", "TargetA: warn2", "TargetA: warn3"], limit=2)

    assert lines == [
        "Validation warnings (3):",
        "  - warn1",
        "  - warn2",
        "  - ... (+1 more)",
    ]


def test_print_validation_warnings_formats_picture_display_entries(monkeypatch):
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


def test_cache_key_for_target_passes_analysis_target(monkeypatch):
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        cache_module,
        "compute_cache_key",
        lambda cfg, *, analysis_target=None: (
            captured.update({"cfg": cfg.copy(), "analysis_target": analysis_target}) or "cache-key"
        ),
    )

    cfg = {"mode": "official"}
    result = project_application._cache_key_for_target(cfg, "TargetA")

    assert result == "cache-key"
    assert cfg == {"mode": "official"}
    assert captured["cfg"] == {"mode": "official"}
    assert captured["analysis_target"] == "TargetA"


def test_source_paths_for_current_target_falls_back_to_header_name():
    project_bp = named_object("TargetA")
    graph = AnalysisGraphStub(source_files={Path("libs/Other.s"), Path("programs/TargetA.s")})

    result = project_application.source_paths_for_current_target(cast(Any, project_bp), cast(Any, graph))

    assert result == {Path("programs/TargetA.s")}


def test_source_paths_for_current_target_prefers_graph_root_origin_path():
    project_bp = named_object("TargetA")
    graph = AnalysisGraphStub(source_files={Path("programs/TargetA.s")})
    graph.record_root_origin("TargetA", source_path=Path("libs/TargetA.s"), library_name="Libs")

    result = project_application.source_paths_for_current_target(cast(Any, project_bp), cast(Any, graph))

    assert result == {Path("libs/TargetA.s")}


def test_target_is_library_returns_false_without_matching_source_paths():
    cfg = {"program_dir": "programs"}
    project_bp = named_object("TargetA", origin_file="Missing.s")
    graph = AnalysisGraphStub()

    assert project_application._target_is_library(cfg, cast(Any, project_bp), cast(Any, graph)) is False
