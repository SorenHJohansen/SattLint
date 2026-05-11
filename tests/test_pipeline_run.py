import json
from types import SimpleNamespace

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleHeader,
)
from sattlint.devtools import _portable_command_text as portable_command_text
from sattlint.devtools import corpus, mutation_engine, pipeline
from sattlint.devtools.artifact_registry import ArtifactDefinition
from sattlint.devtools.pipeline_artifacts import (
    PipelineArtifactContext,
    PipelineArtifactProducer,
    write_pipeline_artifacts,
)
from sattlint.devtools.status_reports import overall_status
from sattlint.models.project_graph import ProjectGraph

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
    assert (tmp_path / "recommendation_drift.json").exists()
    assert summary["profile"] == "full"
    assert summary["entry_report"] == "status.json"
    assert summary["reports"]["findings"] == "findings.json"
    assert summary["reports"]["artifact_registry"] == "artifact_registry.json"
    assert summary["reports"]["dependency_graph"] == "dependency_graph.json"
    assert summary["reports"]["call_graph"] == "call_graph.json"
    assert summary["reports"]["graphics_layout"] == "graphics_layout.json"
    assert summary["reports"]["impact_analysis"] == "impact_analysis.json"
    assert summary["reports"]["recommendation_drift"] == "recommendation_drift.json"
    assert_findings_schema(summary)
    assert_findings_collection(findings_report, finding_count=0, rule_ids=())
    assert_artifact_registry_report(
        artifact_registry,
        generated_by="sattlint.devtools.pipeline",
        profile="full",
        enabled_artifact_ids=("findings", "artifact_registry", "dependency_graph", "recommendation_drift"),
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
            structural_budget_report={
                "source_files_over_budget": [],
                "test_files_over_budget": [],
                "functions_over_budget": [],
                "classes_over_budget": [],
                "repeated_private_names": [],
                "facade_private_entrypoints": [],
                "summary": {"source_file_max_lines": 0, "test_file_max_lines": 0},
            },
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


def test_run_pipeline_writes_mutation_and_differential_artifacts_when_requested(monkeypatch, tmp_path):
    baseline_findings_path = tmp_path / "baseline-findings.json"
    baseline_findings_path.write_text(
        json.dumps(
            {
                "kind": "sattlint.findings",
                "schema_version": 1,
                "finding_count": 0,
                "findings": [],
            }
        ),
        encoding="utf-8",
    )
    mutation_target = tmp_path / "MutationTarget.s"
    mutation_target.write_text("TRUE\n", encoding="utf-8")

    _patch_skipped_coverage_summary(monkeypatch)
    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(pipeline, "_run_command", _patched_run_command)
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}, "testcases": []},
    )
    monkeypatch.setattr(
        pipeline, "_collect_structural_report_bundle", lambda progress_callback=None: _minimal_structural_bundle()
    )
    monkeypatch.setattr(
        mutation_engine,
        "run_mutation_analysis",
        lambda source_file, finding_collection: mutation_engine.MutationResults(
            [mutation_engine.MutationRecord("bool-flip", source_file.as_posix(), "TRUE", "FALSE", False)]
        ),
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="full",
        include_vulture=False,
        include_bandit=False,
        baseline_findings=baseline_findings_path,
        run_mutation_analysis=True,
        mutation_target=mutation_target,
    )

    mutation_results = json.loads((tmp_path / "mutation_results.json").read_text(encoding="utf-8"))
    differential_report = json.loads((tmp_path / "differential.json").read_text(encoding="utf-8"))
    artifact_registry = json.loads((tmp_path / "artifact_registry.json").read_text(encoding="utf-8"))

    assert summary["reports"]["mutation_results"] == "mutation_results.json"
    assert summary["reports"]["differential"] == "differential.json"
    assert mutation_results["kind"] == "sattlint.mutation_results"
    assert mutation_results["summary"] == {"total_mutations": 1, "killed": 0, "alive": 1}
    assert differential_report["kind"] == "sattlint.differential"
    assert differential_report["summary"]["baseline"] == "<external>/baseline-findings.json"
    assert differential_report["summary"]["current"] == "findings.json"
    assert_artifact_registry_report(
        artifact_registry,
        profile="full",
        enabled_artifact_ids=("analysis_diff", "mutation_results", "differential"),
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


def test_build_pipeline_check_catalog_lists_full_checks_and_commands(tmp_path):
    catalog = pipeline.build_pipeline_check_catalog(profile="full", output_dir=tmp_path)

    assert catalog["kind"] == "sattlint.pipeline.check_catalog"
    assert catalog["profile"] == "full"
    check_ids = {entry["id"] for entry in catalog["checks"]}
    assert {"ruff", "pyright", "pytest", "vulture", "bandit", "structural-reports", "trace", "corpus"} <= check_ids
    ruff_entry = next(entry for entry in catalog["checks"] if entry["id"] == "ruff")
    assert "--check ruff" in ruff_entry["command"]
    assert ruff_entry["owner_surface"] == "python-style"
    assert "src/**/*.py" in ruff_entry["path_globs"]


def test_portable_command_text_builds_expected_repo_commands():
    assert portable_command_text.repo_python_command() == "python scripts/run_repo_python.py"
    assert (
        portable_command_text.repo_python_command("", "-m", "pytest", "tests/test_pipeline_run.py")
        == "python scripts/run_repo_python.py -m pytest tests/test_pipeline_run.py"
    )
    assert (
        portable_command_text.pytest_command("--no-cov", "tests/test_pipeline_run.py")
        == "python scripts/run_repo_python.py -m pytest --no-cov tests/test_pipeline_run.py"
    )
    assert (
        portable_command_text.pyright_command("src/sattlint/devtools/_portable_command_text.py")
        == "python scripts/run_repo_python.py -m pyright src/sattlint/devtools/_portable_command_text.py"
    )
    assert (
        portable_command_text.ruff_command("check", "tests/test_pipeline_run.py")
        == "python scripts/run_repo_python.py -m ruff check tests/test_pipeline_run.py"
    )
    assert (
        portable_command_text.sattlint_command("syntax-check", "sample.s")
        == "python scripts/run_repo_python.py -m sattlint syntax-check sample.s"
    )
    assert (
        portable_command_text.repo_audit_command("--profile", "quick")
        == "python scripts/run_repo_python.py -m sattlint.devtools.repo_audit --profile quick"
    )


def test_run_pytest_stage_uses_isolated_coverage_file_and_restores_environment(monkeypatch, tmp_path):
    observed_coverage_files: list[str | None] = []

    monkeypatch.setenv("COVERAGE_FILE", "stale.coverage")

    def write_json(path, payload) -> None:
        path.write_text(json.dumps(payload), encoding="utf-8")

    def fake_run_command(name, command, cwd=pipeline.REPO_ROOT):
        observed_coverage_files.append(pipeline.os.environ.get("COVERAGE_FILE"))
        return pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=0,
            duration_seconds=0.0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(pipeline, "_run_command", fake_run_command)
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {
            "summary": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0},
            "testcases": [],
        },
    )

    report = pipeline._run_pytest_stage(
        pipeline.ProgressReporter(
            kind="sattlint.pipeline.progress",
            title="Pipeline",
            output_dir=tmp_path,
            write_json=write_json,
            stages=[("pytest", "Run pytest")],
            emit_stdout=False,
        ),
        output_dir=tmp_path,
        python_cmd=["python"],
        profile="full",
    )

    assert observed_coverage_files == [str(tmp_path / ".coverage.pytest")]
    assert pipeline.os.environ.get("COVERAGE_FILE") == "stale.coverage"
    assert report["summary"] == {"tests": 1, "failures": 0, "errors": 0, "skipped": 0}


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


def test_run_pipeline_prints_core_invariant_violations(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        pipeline,
        "_prepare_pipeline_run",
        lambda output_dir, **kwargs: {
            "progress": SimpleNamespace(),
            "python_cmd": "python",
            "output_dir": output_dir,
            "profile": kwargs["profile"],
            "run_vulture": False,
            "run_bandit": False,
        },
    )
    monkeypatch.setattr(pipeline, "_run_environment_stage", lambda progress: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_run_ruff_stage", lambda progress, python_cmd: ({}, []))
    monkeypatch.setattr(pipeline, "_run_pyright_stage", lambda progress, python_cmd: ({}, []))
    monkeypatch.setattr(
        pipeline,
        "_run_pytest_stage",
        lambda progress, output_dir, python_cmd, profile, pytest_workers=None: {},
    )
    monkeypatch.setattr(pipeline, "_run_vulture_stage", lambda progress, python_cmd, run_vulture: ({}, []))
    monkeypatch.setattr(pipeline, "_run_bandit_stage", lambda progress, python_cmd, run_bandit: {})
    monkeypatch.setattr(pipeline, "_collect_optional_reports", lambda context, trace_target=None: {})
    monkeypatch.setattr(
        pipeline,
        "_build_derived_reports",
        lambda context, stage_reports, optional_reports, **kwargs: {
            "finding_collection": SimpleNamespace(
                findings=[
                    SimpleNamespace(fingerprint="dup-a"),
                    SimpleNamespace(id="dup-a"),
                ]
            ),
            "trace_report": {"heuristics": {"transform_invariant_violations": ["v1"]}},
        },
    )
    monkeypatch.setattr(
        pipeline,
        "_finalize_pipeline_outputs",
        lambda context, stage_reports, optional_reports, derived_reports, **kwargs: {"status": "pass"},
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="quick",
        include_vulture=False,
        include_bandit=False,
    )

    captured = capsys.readouterr()

    assert summary == {"status": "pass"}
    assert "INVARIANT VIOLATION: Duplicate finding fingerprint: dup-a" in captured.out
    assert "INVARIANT VIOLATION: Transform invariant violations: 1" in captured.out


def _patch_skipped_coverage_summary(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "build_coverage_summary_report",
        lambda repo_root: {"kind": "sattlint.coverage_summary", "skipped": True},
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
    # Baseline with zero findings - current run also has zero findings.
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
    assert coverage_artifact.exists(), "coverage_summary.json should be written in full profile"
    report = json.loads(coverage_artifact.read_text(encoding="utf-8"))
    assert report["kind"] == "sattlint.coverage_summary"
    assert report["skipped"] is False
    assert summary["reports"].get("coverage_summary") == "coverage_summary.json"


# ---------------------------------------------------------------------------
# ID21: Phase2 rule acceptance gate tests


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


# ---------------------------------------------------------------------------


# --- status_reports.py: build_tool_status, build_pipeline_status_report, build_pipeline_summary_report ---
def test_build_tool_status_with_note_count_and_detail():
    from sattlint.devtools.status_reports import build_tool_status

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
    from sattlint.devtools.status_reports import build_tool_status

    result = build_tool_status(
        status="pass",
        report=None,
        raw_exit_code=None,
        normalized_exit_code=None,
    )
    assert "note_count" not in result
    assert "detail" not in result


def test_build_pipeline_status_report_with_progress_and_findings():
    from sattlint.devtools.status_reports import build_pipeline_status_report

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
    from sattlint.devtools.status_reports import build_pipeline_summary_report

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


# --- models/project_graph.py: add_library_dependencies, index_from_basepic ---
def test_project_graph_add_library_dependencies_adds_deps():
    from sattlint.models.project_graph import ProjectGraph

    graph = ProjectGraph()
    graph.add_library_dependencies("MyLib", ["DepA", "DepB", ""])
    assert "deplib" not in graph.library_dependencies
    assert graph.library_dependencies.get("mylib") == {"depa", "depb"}


def test_project_graph_index_from_basepic_sets_origin(tmp_path):
    from sattlint.models.project_graph import ProjectGraph

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
    assert source in graph.source_files
    assert bp.origin_file == "TestProgram.s"
    assert bp.origin_lib == "MyLib"


# --- devtools/derived_reports.py: build_incremental_analysis_report, build_profiling_summary_report ---
def test_build_incremental_analysis_report_returns_none_for_empty_files(tmp_path):
    from sattlint.devtools.derived_reports import build_incremental_analysis_report

    result = build_incremental_analysis_report([], repo_root=tmp_path)
    assert result is None


def test_build_incremental_analysis_report_full_mode_for_core_changes(tmp_path):
    from sattlint.devtools.derived_reports import build_incremental_analysis_report

    result = build_incremental_analysis_report(
        ["src/sattlint/engine.py"],
        repo_root=tmp_path,
        analyzer_registry_report={"analyzers": []},
    )
    assert result is not None
    assert result["mode"] == "full"
    assert "shared semantic" in " ".join(result["fallback_reasons"])


def test_build_incremental_analysis_report_mixed_mode_for_program_file(tmp_path):
    from sattlint.devtools.derived_reports import build_incremental_analysis_report

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
    from sattlint.devtools.derived_reports import build_profiling_summary_report

    result = build_profiling_summary_report(None, slow_phase_threshold_ms=500.0)
    assert result is None


def test_build_profiling_summary_report_identifies_slow_phases():
    from sattlint.devtools.derived_reports import build_profiling_summary_report

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
