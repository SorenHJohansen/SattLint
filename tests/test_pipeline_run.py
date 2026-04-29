import json
import os
from types import SimpleNamespace

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)
from sattlint.analyzers.registry import (
    get_actual_cli_analyzer_keys,
    get_actual_lsp_analyzer_keys,
    get_declared_cli_analyzer_keys,
    get_declared_lsp_analyzer_keys,
)
from sattlint.analyzers.sattline_semantics import (
    SattLineSemanticsReport,
    SemanticIssue,
    SemanticRule,
)
from sattlint.contracts import FindingCollection, FindingRecord
from sattlint.devtools import corpus, pipeline, structural_reports
from sattlint.devtools.artifact_registry import ArtifactDefinition
from sattlint.devtools.baselines import build_analysis_diff_report
from sattlint.devtools.finding_exports import build_pipeline_finding_collection
from sattlint.devtools.pipeline_artifacts import (
    PipelineArtifactContext,
    PipelineArtifactProducer,
    validate_pipeline_artifact_producers,
    write_json_artifact,
    write_pipeline_artifacts,
)
from sattlint.devtools.progress_reporting import ProgressReporter
from sattlint.reporting.variables_report import IssueKind

from .helpers.artifact_assertions import (
    assert_analysis_diff_report,
    assert_artifact_registry_report,
    assert_corpus_results_report,
    assert_findings_collection,
    assert_findings_schema,
)


def test_run_pipeline_serializes_structural_graph_reports(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    _patch_skipped_coverage_summary(monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "_collect_structural_report_bundle",
        lambda workspace_root=pipeline.REPO_ROOT, progress_callback=None: pipeline.StructuralReportsBundle(
            architecture_report={"findings": []},
            analyzer_registry_report={"rules": []},
            graph_inputs=pipeline.WorkspaceGraphInputs(
                discovery=SimpleNamespace(program_files=(), dependency_files=()),
                snapshots=[],
                snapshot_failures=[],
            ),
            dependency_graph_report={"edges": [{"source": "main", "target": "support"}]},
            call_graph_report={"edges": [{"source": "Main", "target": "Main"}]},
            graphics_layout_report={"entries": [{"module_path": "Main.Panel"}], "groups": [], "findings": []},
            impact_analysis_report={
                "library_impacts": [{"id": "support"}],
                "module_impacts": [{"id": "Main"}, {"id": "Main.Guard"}],
            },
        ),
    )
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(
        pipeline,
        "_run_command",
        lambda name, command, cwd=pipeline.REPO_ROOT: pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=0,
            duration_seconds=0.0,
            stdout="[]" if name == "ruff" else "",
            stderr="",
        ),
    )
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {
            "summary": {"tests": 0, "failures": 0, "errors": 0, "skipped": 0},
            "testcases": [],
        },
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="full",
        include_vulture=False,
        include_bandit=False,
    )

    status_report = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    artifact_registry = json.loads((tmp_path / "artifact_registry.json").read_text(encoding="utf-8"))
    findings_report = json.loads((tmp_path / "findings.json").read_text(encoding="utf-8"))

    assert (tmp_path / "status.json").exists()
    assert (tmp_path / "findings.json").exists()
    assert (tmp_path / "artifact_registry.json").exists()
    assert (tmp_path / "dependency_graph.json").exists()
    assert (tmp_path / "call_graph.json").exists()
    assert (tmp_path / "graphics_layout.json").exists()
    assert (tmp_path / "impact_analysis.json").exists()
    assert summary["profile"] == "full"
    assert summary["entry_report"] == "status.json"
    assert summary["reports"]["findings"] == "findings.json"
    assert summary["reports"]["artifact_registry"] == "artifact_registry.json"
    assert summary["reports"]["dependency_graph"] == "dependency_graph.json"
    assert summary["reports"]["call_graph"] == "call_graph.json"
    assert summary["reports"]["graphics_layout"] == "graphics_layout.json"
    assert summary["reports"]["impact_analysis"] == "impact_analysis.json"
    assert_findings_schema(summary)
    assert_findings_collection(findings_report, finding_count=0, rule_ids=())
    assert_artifact_registry_report(
        artifact_registry,
        generated_by="sattlint.devtools.pipeline",
        profile="full",
        enabled_artifact_ids=("findings", "artifact_registry", "dependency_graph"),
        disabled_artifact_ids=("trace",),
    )
    assert status_report["overall_status"] == "pass"
    assert_findings_schema(status_report)
    assert status_report["tool_statuses"]["pyright"]["status"] == "pass"
    assert status_report["tool_statuses"]["rule_metadata"]["status"] == "pass"
    assert summary["counts"]["dependency_graph_edges"] == 1
    assert summary["counts"]["call_graph_edges"] == 1
    assert summary["counts"]["graphics_layout_entries"] == 1
    assert summary["counts"]["impact_analysis_library_nodes"] == 1
    assert summary["counts"]["impact_analysis_module_nodes"] == 2
    assert summary["counts"]["workspace_graph_snapshot_failures"] == 0
    assert summary["counts"]["normalized_findings"] == 0
    assert summary["counts"]["baseline_new_findings"] == 0
    assert summary["counts"]["baseline_resolved_findings"] == 0
    assert summary["counts"]["baseline_changed_findings"] == 0
    assert summary["counts"]["baseline_unchanged_findings"] == 0
    assert summary["counts"]["phase2_rule_metadata_blocking_gaps"] == 0
    assert summary["counts"]["phase2_rule_metadata_advisory_gaps"] == 0


def test_run_pipeline_fails_when_enforced_rule_metadata_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    _patch_skipped_coverage_summary(monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "_collect_structural_report_bundle",
        lambda workspace_root=pipeline.REPO_ROOT, progress_callback=None: pipeline.StructuralReportsBundle(
            architecture_report={
                "findings": [
                    {
                        "id": "rule-acceptance-test-gap",
                        "severity": "medium",
                        "message": "Some semantic rules do not declare acceptance-test coverage.",
                        "missing_rule_ids": ["semantic.read-before-write"],
                    }
                ],
                "phase2_rule_metadata_gate": {
                    "status": "fail",
                    "enforced_fields": ["acceptance_tests", "mutation_applicability"],
                    "advisory_fields": ["corpus_cases"],
                    "blocking_finding_ids": ["rule-acceptance-test-gap"],
                    "advisory_finding_ids": [],
                    "blocking_rule_ids": ["semantic.read-before-write"],
                    "advisory_rule_ids": [],
                },
            },
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
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(
        pipeline,
        "_run_command",
        lambda name, command, cwd=pipeline.REPO_ROOT: pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=0,
            duration_seconds=0.0,
            stdout="[]" if name == "ruff" else "",
            stderr="",
        ),
    )
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {
            "summary": {"tests": 0, "failures": 0, "errors": 0, "skipped": 0},
            "testcases": [],
        },
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="full",
        include_vulture=False,
        include_bandit=False,
    )

    status_report = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))

    assert status_report["overall_status"] == "fail"
    assert status_report["tool_statuses"]["rule_metadata"] == {
        "status": "fail",
        "report": "architecture.json",
        "raw_exit_code": None,
        "normalized_exit_code": 1,
        "finding_count": 1,
        "detail": "1 rules missing enforced metadata",
    }
    assert summary["counts"]["phase2_rule_metadata_blocking_gaps"] == 1
    assert summary["counts"]["phase2_rule_metadata_advisory_gaps"] == 0


def test_run_pipeline_writes_analysis_diff_when_baseline_is_supplied(monkeypatch, tmp_path):
    baseline_findings_path = tmp_path / "baseline-findings.json"
    baseline_findings_path.write_text(
        json.dumps(
            {
                "kind": "sattlint.findings",
                "schema_version": 1,
                "finding_count": 1,
                "findings": [
                    {
                        "id": "pytest-old",
                        "rule_id": "pytest.failures",
                        "category": "correctness",
                        "severity": "high",
                        "confidence": "high",
                        "message": "Pytest reported failing tests.",
                        "source": "pytest",
                        "analyzer": "pytest",
                        "artifact": "findings",
                        "location": {
                            "path": None,
                            "line": None,
                            "column": None,
                            "symbol": None,
                            "module_path": [],
                        },
                        "fingerprint": None,
                        "detail": None,
                        "suggestion": None,
                        "data": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(
        pipeline,
        "_run_command",
        lambda name, command, cwd=pipeline.REPO_ROOT: pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=0,
            duration_seconds=0.0,
            stdout="[]" if name == "ruff" else "",
            stderr="",
        ),
    )
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {
            "summary": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0},
            "testcases": [],
        },
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="quick",
        baseline_findings=baseline_findings_path,
    )

    analysis_diff_report = json.loads((tmp_path / "analysis_diff.json").read_text(encoding="utf-8"))
    artifact_registry = json.loads((tmp_path / "artifact_registry.json").read_text(encoding="utf-8"))

    assert summary["reports"]["analysis_diff"] == "analysis_diff.json"
    assert_analysis_diff_report(
        analysis_diff_report,
        summary={
            "new_count": 0,
            "resolved_count": 0,
            "changed_count": 1,
            "unchanged_count": 0,
        },
        baseline_label="<external>/baseline-findings.json",
        current_label="findings.json",
        changed_rule_ids=("pytest.failures",),
    )
    assert summary["counts"]["baseline_new_findings"] == 0
    assert summary["counts"]["baseline_resolved_findings"] == 0
    assert summary["counts"]["baseline_changed_findings"] == 1
    assert summary["counts"]["baseline_unchanged_findings"] == 0
    assert_artifact_registry_report(
        artifact_registry,
        profile="quick",
        enabled_artifact_ids=("analysis_diff",),
    )


def test_run_pipeline_writes_corpus_results_when_manifest_dir_is_supplied(monkeypatch, tmp_path):
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(
        pipeline,
        "_run_command",
        lambda name, command, cwd=pipeline.REPO_ROOT: pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=0,
            duration_seconds=0.0,
            stdout="[]" if name == "ruff" else "",
            stderr="",
        ),
    )
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {
            "summary": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0},
            "testcases": [],
        },
    )
    monkeypatch.setattr(
        pipeline,
        "run_corpus_suite",
        lambda output_dir, manifest_dir, repo_root, write_results=False: corpus.CorpusSuiteResult(
            cases=(
                corpus.CorpusRunResult(
                    manifest=corpus.CorpusCaseManifest(
                        case_id="workspace-semantic",
                        target_file="tests/fixtures/corpus/valid/Program.s",
                        mode="workspace",
                        expectation=corpus.CorpusExpectation(
                            expected_finding_ids=("semantic.read-before-write",),
                        ),
                    ),
                    evaluation=corpus.CorpusEvaluation(
                        case_id="workspace-semantic",
                        passed=True,
                    ),
                    findings_report="findings.json",
                    artifact_dir="corpus_cases/workspace-semantic",
                ),
            ),
            output_dir="artifacts/analysis",
            manifest_root="tests/fixtures/corpus/manifests",
        ),
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="quick",
        corpus_manifest_dir=manifest_dir,
    )

    corpus_report = json.loads((tmp_path / "corpus_results.json").read_text(encoding="utf-8"))
    artifact_registry = json.loads((tmp_path / "artifact_registry.json").read_text(encoding="utf-8"))

    assert summary["reports"]["corpus_results"] == "corpus_results.json"
    assert summary["status"]["tool_statuses"]["corpus"]["status"] == "pass"
    assert summary["counts"]["corpus_case_count"] == 1
    assert summary["counts"]["corpus_failed_case_count"] == 0
    assert_corpus_results_report(
        corpus_report,
        case_count=1,
        failed_case_ids=(),
        expect_findings_schema=False,
    )
    assert corpus_report["cases"][0]["case_id"] == "workspace-semantic"
    assert_artifact_registry_report(
        artifact_registry,
        profile="quick",
        enabled_artifact_ids=("corpus_results",),
    )


def test_run_pipeline_quick_profile_skips_optional_reports(monkeypatch, tmp_path):
    commands: list[tuple[str, list[str]]] = []

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")

    def fake_run_command(name, command, cwd=pipeline.REPO_ROOT):
        commands.append((name, command))
        stdout = "[]" if name == "ruff" else ""
        return pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=0,
            duration_seconds=0.0,
            stdout=stdout,
            stderr="",
        )

    monkeypatch.setattr(pipeline, "_run_command", fake_run_command)
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {
            "summary": {"tests": 3, "failures": 0, "errors": 0, "skipped": 0},
            "testcases": [],
        },
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="quick",
    )

    status_report = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    artifact_registry = json.loads((tmp_path / "artifact_registry.json").read_text(encoding="utf-8"))
    findings_report = json.loads((tmp_path / "findings.json").read_text(encoding="utf-8"))

    assert [name for name, _command in commands] == ["ruff", "pyright", "pytest"]
    pytest_command = next(command for name, command in commands if name == "pytest")
    assert "-o" in pytest_command
    assert any(part.startswith("addopts=--strict-markers --strict-config") for part in pytest_command)
    assert all(target in pytest_command for target in pipeline.DEFAULT_QUICK_PYTEST_TARGETS)
    assert summary["profile"] == "quick"
    assert summary["reports"]["findings"] == "findings.json"
    assert summary["reports"]["artifact_registry"] == "artifact_registry.json"
    assert summary["reports"]["progress"] == "progress.json"
    assert summary["reports"]["vulture"] is None
    assert summary["reports"]["bandit"] is None
    assert summary["reports"]["architecture"] is None
    assert summary["reports"]["dependency_graph"] is None
    assert_findings_schema(summary)
    assert_findings_collection(findings_report, finding_count=0, rule_ids=())
    assert_artifact_registry_report(
        artifact_registry,
        profile="quick",
        enabled_artifact_ids=("findings", "artifact_registry"),
    )
    assert all(item["artifact_id"] != "architecture" for item in artifact_registry["artifacts"])
    assert summary["counts"]["workspace_graph_snapshot_failures"] == 0
    assert summary["counts"]["normalized_findings"] == 0
    assert summary["counts"]["baseline_changed_findings"] == 0
    assert status_report["overall_status"] == "pass"
    assert status_report["progress_report"] == f"<external>/{tmp_path.name}/progress.json"
    assert_findings_schema(status_report)
    assert status_report["tool_statuses"]["vulture"]["status"] == "skipped"
    assert status_report["tool_statuses"]["bandit"]["status"] == "skipped"
    assert status_report["tool_statuses"]["rule_metadata"]["status"] == "skipped"


# --- ID 10: Baseline regression enforcement tests ---


def _make_fake_baseline_findings_file(path, finding_message="Pytest reported failing tests."):
    """Write a minimal baseline findings.json with one finding."""
    path.write_text(
        json.dumps(
            {
                "kind": "sattlint.findings",
                "schema_version": 1,
                "finding_count": 1,
                "findings": [
                    {
                        "id": "pytest-old",
                        "rule_id": "pytest.failures",
                        "category": "correctness",
                        "severity": "high",
                        "confidence": "high",
                        "message": finding_message,
                        "source": "pytest",
                        "analyzer": "pytest",
                        "artifact": "findings",
                        "location": {
                            "path": None,
                            "line": None,
                            "column": None,
                            "symbol": None,
                            "module_path": [],
                        },
                        "fingerprint": None,
                        "detail": None,
                        "suggestion": None,
                        "data": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _patched_run_command(name, command, cwd=pipeline.REPO_ROOT):
    return pipeline.CommandResult(
        name=name,
        command=command,
        exit_code=0,
        duration_seconds=0.0,
        stdout="[]" if name == "ruff" else "",
        stderr="",
    )


def _patch_skipped_coverage_summary(monkeypatch):
    monkeypatch.setattr(
        pipeline, "build_coverage_summary_report", lambda repo_root: {"kind": "sattlint.coverage_summary", "skipped": True}
    )


def test_run_pipeline_baseline_drift_status_skipped_without_baseline(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(pipeline, "_run_command", _patched_run_command)
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0}, "testcases": []},
    )

    summary = pipeline._run_pipeline(tmp_path, trace_target=None, profile="quick")

    assert summary["status"]["tool_statuses"]["baseline_drift"]["status"] == "skipped"
    assert summary["status"]["overall_status"] == "pass"


def test_run_pipeline_fail_on_drift_passes_when_no_new_findings(monkeypatch, tmp_path):
    """fail_on_drift=True should not fail when findings are unchanged."""
    baseline_path = tmp_path / "baseline.json"
    # Baseline with zero findings — current run also has zero findings.
    baseline_path.write_text(
        json.dumps({"kind": "sattlint.findings", "schema_version": 1, "finding_count": 0, "findings": []}),
        encoding="utf-8",
    )

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
        baseline_findings=baseline_path,
        fail_on_drift=True,
    )

    assert summary["status"]["tool_statuses"]["baseline_drift"]["status"] == "pass"
    assert summary["status"]["overall_status"] == "pass"


def test_run_pipeline_fail_on_drift_fails_when_new_findings_present(monkeypatch, tmp_path):
    """fail_on_drift=True should fail when current has new findings relative to baseline."""
    baseline_path = tmp_path / "baseline.json"
    # Baseline with zero findings; current run will have a pytest failure finding.
    baseline_path.write_text(
        json.dumps({"kind": "sattlint.findings", "schema_version": 1, "finding_count": 0, "findings": []}),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(
        pipeline,
        "_run_command",
        lambda name, command, cwd=pipeline.REPO_ROOT: pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=1 if name == "pytest" else 0,
            duration_seconds=0.0,
            stdout="[]" if name == "ruff" else "",
            stderr="",
        ),
    )
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0}, "testcases": []},
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="quick",
        baseline_findings=baseline_path,
        fail_on_drift=True,
    )

    assert summary["status"]["tool_statuses"]["baseline_drift"]["status"] == "fail"
    assert "baseline_drift" in summary["status"]["failing_tools"]
    assert summary["status"]["overall_status"] == "fail"
    assert summary["counts"]["baseline_new_findings"] > 0


def test_run_pipeline_fail_on_drift_false_does_not_fail_on_new_findings(monkeypatch, tmp_path):
    """Without fail_on_drift, new findings in the diff do not change overall_status."""
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps({"kind": "sattlint.findings", "schema_version": 1, "finding_count": 0, "findings": []}),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(
        pipeline,
        "_run_command",
        lambda name, command, cwd=pipeline.REPO_ROOT: pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=1 if name == "pytest" else 0,
            duration_seconds=0.0,
            stdout="[]" if name == "ruff" else "",
            stderr="",
        ),
    )
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0}, "testcases": []},
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="quick",
        baseline_findings=baseline_path,
        fail_on_drift=False,
    )

    assert summary["status"]["tool_statuses"]["baseline_drift"]["status"] == "pass"
    # pytest itself still fails, but baseline_drift does not add to failures
    assert "baseline_drift" not in summary["status"]["failing_tools"]


def test_main_save_baseline_copies_findings_json(monkeypatch, tmp_path):
    """--save-baseline copies findings.json to the specified target path."""
    baseline_dest = tmp_path / "saved" / "baseline.json"

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(pipeline, "_run_command", _patched_run_command)
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0}, "testcases": []},
    )

    exit_code = pipeline.main(
        [
            "--output-dir",
            str(tmp_path),
            "--profile",
            "quick",
            "--save-baseline",
            str(baseline_dest),
        ]
    )

    assert exit_code == 0
    assert baseline_dest.exists()
    saved = json.loads(baseline_dest.read_text(encoding="utf-8"))
    assert saved["kind"] == "sattlint.findings"


def test_main_fail_on_drift_exits_nonzero_when_new_findings(monkeypatch, tmp_path):
    """--fail-on-drift should make main() return non-zero when drift is detected."""
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps({"kind": "sattlint.findings", "schema_version": 1, "finding_count": 0, "findings": []}),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(
        pipeline,
        "_run_command",
        lambda name, command, cwd=pipeline.REPO_ROOT: pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=1 if name == "pytest" else 0,
            duration_seconds=0.0,
            stdout="[]" if name == "ruff" else "",
            stderr="",
        ),
    )
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0}, "testcases": []},
    )

    exit_code = pipeline.main(
        [
            "--output-dir",
            str(tmp_path),
            "--profile",
            "quick",
            "--baseline-findings",
            str(baseline_path),
            "--fail-on-drift",
        ]
    )

    assert exit_code == 1


def _minimal_structural_bundle() -> pipeline.StructuralReportsBundle:
    return pipeline.StructuralReportsBundle(
        architecture_report={"findings": []},
        analyzer_registry_report=pipeline._collect_analyzer_registry_report(),
        graph_inputs=pipeline.WorkspaceGraphInputs(
            discovery=SimpleNamespace(program_files=(), dependency_files=()),
            snapshots=[],
            snapshot_failures=[],
        ),
        dependency_graph_report={"edges": []},
        call_graph_report={"edges": []},
        graphics_layout_report={"entries": [], "groups": [], "findings": []},
        impact_analysis_report={"library_impacts": [], "module_impacts": []},
    )


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


# --- ID 19: Coverage summary pipeline artifact tests ---


def test_run_pipeline_emits_coverage_summary_when_coverage_xml_exists(monkeypatch, tmp_path):
    """Full profile should emit coverage_summary.json when coverage.xml is present."""
    coverage_xml = pipeline.REPO_ROOT / "coverage.xml"
    coverage_xml.exists()

    # Patch REPO_ROOT to tmp_path so coverage.xml lookup is local
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
    assert coverage_artifact.exists(), "coverage_summary.json should be written in full profile"
    report = json.loads(coverage_artifact.read_text(encoding="utf-8"))
    assert report["kind"] == "sattlint.coverage_summary"
    assert report["skipped"] is False
    assert summary["reports"].get("coverage_summary") == "coverage_summary.json"


# ---------------------------------------------------------------------------
# ID21: Phase2 rule acceptance gate tests
# ---------------------------------------------------------------------------


