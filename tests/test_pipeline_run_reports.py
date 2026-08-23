# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false
import json
from types import SimpleNamespace

import pytest
from sattline_parser.models.ast_model import BasePicture, ModuleHeader

from sattlint.devtools import pipeline
from sattlint.devtools.artifact_registry import ArtifactDefinition
from sattlint.devtools.shared import pipeline_artifacts
from sattlint.devtools.shared.pipeline_artifacts import (
    PipelineArtifactContext,
    PipelineArtifactProducer,
    write_pipeline_artifacts,
)
from sattlint.devtools.status_reports import overall_status
from sattlint.models.project_graph import ProjectGraph

from .test_pipeline_run import _minimal_structural_bundle, _patch_skipped_coverage_summary, _patched_run_command


def test_run_pipeline_emits_incremental_analysis_artifact(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(pipeline, "_run_command", _patched_run_command)
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0}, "testcases": []},
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="quick",
        changed_files=["tests/fixtures/sample_sattline_files/LinterTestProgram.s"],
    )

    report_path = tmp_path / "incremental_analysis.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report_path.exists()
    assert report["kind"] == "sattlint.incremental_analysis"
    assert report["mode"] == "mixed"
    assert report["summary"]["changed_file_count"] == 1
    assert report["summary"]["impacted_analyzer_count"] >= 1
    assert report["summary"]["fallback_analyzer_count"] >= 1
    assert summary["counts"]["incremental_changed_file_count"] == 1
    assert summary["reports"]["incremental_analysis"] == "incremental_analysis.json"


def test_run_pipeline_emits_profiling_and_budget_reports(monkeypatch, tmp_path):
    trace_target = tmp_path / "TraceTarget.s"
    trace_target.write_text("dummy", encoding="utf-8")

    _patch_skipped_coverage_summary(monkeypatch)
    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(pipeline, "_run_command", _patched_run_command)
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0}, "testcases": []},
    )
    monkeypatch.setattr(
        pipeline, "_collect_structural_report_bundle", lambda progress_callback=None: _minimal_structural_bundle()
    )
    monkeypatch.setattr(
        pipeline,
        "_collect_trace_report",
        lambda target: {
            "source_file": "tests/fixtures/sample_sattline_files/LinterTestProgram.s",
            "basepicture_name": "LinterTestProgram",
            "events": [
                {"phase": "variables", "action": "start", "time_offset_ms": 0.0},
                {"phase": "variables", "action": "done", "time_offset_ms": 60.0},
                {"phase": "dataflow", "action": "done", "time_offset_ms": 12.0},
            ],
            "timing_summary": {
                "variables": {"event_count": 2, "span_ms": 60.0},
                "dataflow": {"event_count": 1, "span_ms": 12.0},
            },
            "dataflow_analysis": {"issue_count": 0},
            "heuristics": {"unreachable_logic": [], "transform_invariant_violations": []},
        },
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=trace_target,
        profile="full",
        slow_phase_threshold_ms=20.0,
        phase_budget_ms=50.0,
        total_budget_ms=100.0,
    )

    profiling_report = json.loads((tmp_path / "profiling_summary.json").read_text(encoding="utf-8"))
    budget_report = json.loads((tmp_path / "performance_budget.json").read_text(encoding="utf-8"))

    assert profiling_report["kind"] == "sattlint.profiling_summary"
    assert profiling_report["summary"]["phase_count"] == 2
    assert profiling_report["summary"]["slow_phase_count"] == 1
    assert profiling_report["slow_phases"][0]["phase"] == "variables"
    assert budget_report["kind"] == "sattlint.performance_budget"
    assert budget_report["status"] == "fail"
    assert budget_report["violation_count"] == 1
    assert summary["status"]["tool_statuses"]["performance_budget"]["status"] == "pass_with_notes"
    assert summary["counts"]["profiling_slow_phase_count"] == 1
    assert summary["counts"]["performance_budget_violation_count"] == 1


def test_main_fail_on_budget_exits_nonzero(monkeypatch, tmp_path):
    trace_target = tmp_path / "TraceTarget.s"
    trace_target.write_text("dummy", encoding="utf-8")

    _patch_skipped_coverage_summary(monkeypatch)
    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(pipeline, "_run_command", _patched_run_command)
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0}, "testcases": []},
    )
    monkeypatch.setattr(
        pipeline, "_collect_structural_report_bundle", lambda progress_callback=None: _minimal_structural_bundle()
    )
    monkeypatch.setattr(
        pipeline,
        "_collect_trace_report",
        lambda target: {
            "source_file": "tests/fixtures/sample_sattline_files/LinterTestProgram.s",
            "basepicture_name": "LinterTestProgram",
            "events": [{"phase": "variables", "action": "done", "time_offset_ms": 80.0}],
            "timing_summary": {"variables": {"event_count": 1, "span_ms": 80.0}},
            "dataflow_analysis": {"issue_count": 0},
            "heuristics": {"unreachable_logic": [], "transform_invariant_violations": []},
        },
    )

    exit_code = pipeline.main(
        [
            "--output-dir",
            str(tmp_path),
            "--profile",
            "full",
            "--trace-target",
            str(trace_target),
            "--phase-budget-ms",
            "50",
            "--total-budget-ms",
            "70",
            "--fail-on-budget",
        ]
    )

    assert exit_code == 1


def test_run_pipeline_emits_coverage_summary_when_coverage_xml_exists(monkeypatch, tmp_path):
    fake_root = tmp_path / "repo"
    fake_root.mkdir()
    (fake_root / "coverage.xml").write_text(
        """<coverage>
  <packages><package><classes>
    <class filename="src/sattlint/mod.py" line-rate="0.05" lines-valid="100" />
  </classes></package></packages>
</coverage>""",
        encoding="utf-8",
    )
    monkeypatch.setattr(pipeline, "REPO_ROOT", fake_root)
    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(pipeline, "_run_command", _patched_run_command)
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0}, "testcases": []},
    )
    monkeypatch.setattr(
        pipeline,
        "_collect_structural_report_bundle",
        lambda workspace_root=pipeline.REPO_ROOT, progress_callback=None: pipeline.StructuralReportsBundle(
            structural_budget_report={
                "source_files_over_budget": [],
                "test_files_over_budget": [],
                "functions_over_budget": [],
                "classes_over_budget": [],
                "repeated_private_names": [],
                "facade_private_entrypoints": [],
                "summary": {"source_file_max_lines": 0, "test_file_max_lines": 0},
            },
            architecture_report={"findings": []},
            analyzer_registry_report={"rules": []},
            graph_inputs=pipeline.WorkspaceGraphInputs(
                discovery=SimpleNamespace(program_files=(), dependency_files=()),
                snapshots=[],
                snapshot_failures=[],
            ),
            dependency_graph_report={"edges": []},
            call_graph_report={"edges": []},
            graphics_layout_report={"entries": [], "groups": [], "findings": []},
            impact_analysis_report={"library_impacts": [], "module_impacts": []},
        ),
    )

    output_dir = tmp_path / "out"
    summary = pipeline._run_pipeline(output_dir, trace_target=None, profile="full")

    coverage_artifact = output_dir / "coverage_summary.json"
    assert coverage_artifact.exists()
    report = json.loads(coverage_artifact.read_text(encoding="utf-8"))
    assert report["kind"] == "sattlint.coverage_summary"
    assert report["skipped"] is False
    assert summary["reports"].get("coverage_summary") == "coverage_summary.json"


def test_overall_status_returns_pass_with_notes_when_no_fail_but_some_notes():
    statuses = {
        "tool_a": {"status": "pass_with_notes"},
        "tool_b": {"status": "pass"},
    }

    result = overall_status(statuses)

    assert result == "pass_with_notes"


def test_project_graph_add_library_dependencies_ignores_none_library_name():
    graph = ProjectGraph()

    graph.add_library_dependencies(None, ["dep_a", "dep_b"])

    assert graph.library_dependencies == {}


def test_write_pipeline_artifacts_skips_artifact_with_none_payload(tmp_path):
    written: list[str] = []

    context = PipelineArtifactContext(payloads={})

    artifact_ids = write_pipeline_artifacts(
        tmp_path,
        artifacts=(
            ArtifactDefinition(
                "status",
                "status.json",
                "status_payload",
                "sattlint.pipeline.status",
                1,
                profiles=("quick",),
            ),
        ),
        profile="quick",
        enabled_artifact_ids={"status"},
        context=context,
        write_json=lambda path, payload: written.append(path.name),
        producers=(
            PipelineArtifactProducer(
                "status_payload",
                lambda artifact_context: None,
            ),
        ),
    )

    assert artifact_ids == ()
    assert written == []


def test_pipeline_artifact_helpers_cover_manifest_and_import_fallbacks(tmp_path, monkeypatch):
    assert pipeline_artifacts._build_none_payload(PipelineArtifactContext(payloads={})) is None
    assert pipeline_artifacts.artifact_source_manifest_path(tmp_path / "status") == tmp_path / "status.sources.json"

    monkeypatch.setattr(
        pipeline_artifacts.importlib.util, "find_spec", lambda _name: (_ for _ in ()).throw(ValueError("bad spec"))
    )
    assert pipeline_artifacts._resolve_generated_by_source_path("demo.module") is None

    monkeypatch.setattr(
        pipeline_artifacts.importlib.util, "find_spec", lambda _name: SimpleNamespace(origin="built-in")
    )
    assert pipeline_artifacts._resolve_generated_by_source_path("demo.module") is None

    class _FlakySpec:
        def __init__(self):
            self.calls = 0

        @property
        def origin(self):
            self.calls += 1
            return "demo.py" if self.calls == 1 else None

    monkeypatch.setattr(pipeline_artifacts.importlib.util, "find_spec", lambda _name: _FlakySpec())
    assert pipeline_artifacts._resolve_generated_by_source_path("demo.module") is None


def test_write_json_content_retries_permission_errors_then_raises(tmp_path, monkeypatch):
    target_path = tmp_path / "status.json"

    monkeypatch.setattr(
        pipeline_artifacts.os, "replace", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("busy"))
    )
    monkeypatch.setattr(pipeline_artifacts.time, "sleep", lambda _seconds: None)

    with pytest.raises(PermissionError, match="busy"):
        pipeline_artifacts._write_json_content(target_path, "{}")

    assert not target_path.exists()


def test_write_json_content_handles_permission_errors_before_temp_path_assignment(tmp_path, monkeypatch):
    target_path = tmp_path / "status.json"

    monkeypatch.setattr(
        pipeline_artifacts.tempfile,
        "NamedTemporaryFile",
        lambda **_kwargs: (_ for _ in ()).throw(PermissionError("denied before temp")),
    )
    monkeypatch.setattr(pipeline_artifacts.time, "sleep", lambda _seconds: None)

    with pytest.raises(PermissionError, match="denied before temp"):
        pipeline_artifacts._write_json_content(target_path, "{}")


def test_write_json_content_raises_runtime_error_when_retry_loop_never_runs(tmp_path, monkeypatch):
    import builtins  # noqa: PLC0415

    target_path = tmp_path / "status.json"
    original_range = builtins.range

    builtins.range = lambda *args: [] if args == (5,) else original_range(*args)
    try:
        with pytest.raises(RuntimeError, match="Failed to write"):
            pipeline_artifacts._write_json_content(target_path, "{}")
    finally:
        builtins.range = original_range


def test_validate_pipeline_artifact_producers_rejects_duplicates_and_missing_entries():
    artifact = ArtifactDefinition(
        "status",
        "status.json",
        "status_payload",
        "sattlint.pipeline.status",
        1,
        profiles=("quick",),
    )

    with pytest.raises(ValueError, match="Duplicate pipeline artifact producers"):
        pipeline_artifacts.validate_pipeline_artifact_producers(
            (artifact,),
            profile="quick",
            producers=(
                PipelineArtifactProducer("status_payload", lambda _context: {}),
                PipelineArtifactProducer("status_payload", lambda _context: {}),
            ),
        )

    with pytest.raises(ValueError, match="missing producers"):
        pipeline_artifacts.validate_pipeline_artifact_producers(
            (artifact,),
            profile="quick",
            producers=(),
        )


def test_write_pipeline_artifacts_raises_when_validation_is_bypassed_and_producer_missing(tmp_path, monkeypatch):
    artifact = ArtifactDefinition(
        "status",
        "status.json",
        "status_payload",
        "sattlint.pipeline.status",
        1,
        profiles=("quick",),
    )
    monkeypatch.setattr(
        pipeline_artifacts,
        "validate_pipeline_artifact_producers",
        lambda *args, **kwargs: ("status",),
    )

    with pytest.raises(ValueError, match="No pipeline artifact producer registered"):
        pipeline_artifacts.write_pipeline_artifacts(
            tmp_path,
            artifacts=(artifact,),
            profile="quick",
            enabled_artifact_ids={"status"},
            context=PipelineArtifactContext(payloads={}),
            write_json=lambda _path, _payload: None,
            producers=(),
        )


def test_build_tool_status_with_note_count_and_detail():
    from sattlint.devtools.status_reports import build_tool_status  # noqa: PLC0415

    result = build_tool_status(
        status="pass_with_notes",
        report="vars.json",
        raw_exit_code=0,
        normalized_exit_code=0,
        finding_count=0,
        note_count=3,
        detail="3 suggestions",
    )
    assert result["note_count"] == 3
    assert result["detail"] == "3 suggestions"


def test_build_tool_status_without_optional_fields():
    from sattlint.devtools.status_reports import build_tool_status  # noqa: PLC0415

    result = build_tool_status(
        status="pass",
        report=None,
        raw_exit_code=None,
        normalized_exit_code=None,
    )
    assert "note_count" not in result
    assert "detail" not in result


def test_build_pipeline_status_report_with_progress_and_findings():
    from sattlint.devtools.status_reports import build_pipeline_status_report  # noqa: PLC0415

    result = build_pipeline_status_report(
        profile="full",
        sanitized_output_dir="output",
        overall_status_value="pass",
        tool_statuses={},
        failing_tools=[],
        non_blocking_tools=[],
        progress_report="output/progress.json",
        findings_schema={"kind": "sattlint.findings"},
    )
    assert result["profile"] == "full"
    assert result["progress_report"] == "output/progress.json"
    assert result["findings_schema"]["kind"] == "sattlint.findings"


def test_build_pipeline_summary_report_includes_all_fields():
    from sattlint.devtools.status_reports import build_pipeline_summary_report  # noqa: PLC0415

    result = build_pipeline_summary_report(
        profile="quick",
        sanitized_output_dir="out",
        reports={"vars": "out/vars.json"},
        overall_status_value="pass",
        tool_statuses={},
        failing_tools=[],
        non_blocking_tools=[],
        tool_exit_codes={"vars": 0},
        artifact_registry_report={},
        counts={},
        progress_report="out/progress.json",
        findings_schema={"kind": "sattlint.findings"},
    )
    assert result["profile"] == "quick"
    assert result["progress_report"] == "out/progress.json"
    assert result["findings_schema"] is not None


def test_project_graph_add_library_dependencies_adds_deps():
    from sattlint.models.project_graph import ProjectGraph  # noqa: PLC0415

    graph = ProjectGraph()
    graph.add_library_dependencies("MyLib", ["DepA", "DepB", ""])
    assert "deplib" not in graph.library_dependencies
    assert graph.library_dependencies.get("mylib") == {"depa", "depb"}


def test_project_graph_index_from_basepic_sets_origin(tmp_path):
    from sattlint.models.project_graph import ProjectGraph  # noqa: PLC0415

    header = ModuleHeader(name="TestProgram", invoke_coord=(0, 0, 0, 0, 0))
    bp = BasePicture(
        header=header,
        name="TestProgram",
        moduletype_defs=[],
        datatype_defs=[],
    )
    graph = ProjectGraph()
    source = tmp_path / "TestProgram.s"
    source.touch()
    graph.index_from_basepic(bp, source_path=source, library_name="MyLib")
    root_origin = graph.root_origin_for_name("TestProgram")

    assert source in graph.source_files
    assert bp.origin_file is None
    assert bp.origin_lib is None
    assert root_origin is not None
    assert root_origin.source_path == source
    assert root_origin.library_name == "MyLib"


def test_build_incremental_analysis_report_returns_none_for_empty_files(tmp_path):
    from sattlint.devtools.derived_reports import build_incremental_analysis_report  # noqa: PLC0415

    result = build_incremental_analysis_report([], repo_root=tmp_path)
    assert result is None


def test_build_incremental_analysis_report_full_mode_for_core_changes(tmp_path):
    from sattlint.devtools.derived_reports import build_incremental_analysis_report  # noqa: PLC0415

    result = build_incremental_analysis_report(
        ["src/sattlint/engine.py"],
        repo_root=tmp_path,
        analyzer_registry_report={"analyzers": []},
    )
    assert result is not None
    assert result["mode"] == "full"
    assert "shared semantic" in " ".join(result["fallback_reasons"])


def test_build_incremental_analysis_report_mixed_mode_for_program_file(tmp_path):
    from sattlint.devtools.derived_reports import build_incremental_analysis_report  # noqa: PLC0415

    result = build_incremental_analysis_report(
        ["src/programs/Main.s"],
        repo_root=tmp_path,
        analyzer_registry_report={
            "analyzers": [
                {"key": "variables", "supports_incremental": True},
                {"key": "dataflow", "supports_incremental": False},
            ]
        },
    )
    assert result is not None
    assert result["mode"] in {"mixed", "incremental", "none"}


def test_build_profiling_summary_report_returns_none_for_none_input():
    from sattlint.devtools.derived_reports import build_profiling_summary_report  # noqa: PLC0415

    result = build_profiling_summary_report(None, slow_phase_threshold_ms=500.0)
    assert result is None


def test_build_profiling_summary_report_identifies_slow_phases():
    from sattlint.devtools.derived_reports import build_profiling_summary_report  # noqa: PLC0415

    trace = {
        "source_file": "Main.s",
        "basepicture_name": "Main",
        "timing_summary": {
            "variables": {"event_count": 10, "span_ms": 1200.0},
            "syntax": {"event_count": 3, "span_ms": 50.0},
        },
        "events": [{"time_offset_ms": 1200.0}],
    }
    result = build_profiling_summary_report(trace, slow_phase_threshold_ms=500.0)
    assert result is not None
    assert result["summary"]["slow_phase_count"] == 1
