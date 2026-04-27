import json
from pathlib import Path

from sattlint.analyzers.sattline_semantics import SattLineSemanticsReport, SemanticIssue, SemanticRule
from sattlint.devtools.corpus import (
    CORPUS_RESULTS_FILENAME,
    evaluate_finding_ids,
    execute_corpus_case,
    load_corpus_manifest,
    run_corpus_case,
    run_corpus_suite,
)

from .helpers.artifact_assertions import (
    assert_corpus_results_report,
    assert_findings_collection,
    assert_findings_schema,
)


def test_load_corpus_manifest_reads_expectations(tmp_path):
    manifest_path = tmp_path / "unused-variable.json"
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "unused-variable",
                "target_file": "tests/fixtures/corpus/valid/UnusedVariable.s",
                "mode": "workspace",
                "expectation": {
                    "expected_finding_ids": ["semantic.read-before-write", "unused"],
                    "forbidden_finding_ids": ["hardcoded-windows-path"],
                    "artifact_fragments": {
                        "status.json": {
                            "execution_status": "ok",
                        },
                    },
                },
                "required_artifacts": ["summary.json", "findings.json"],
            }
        ),
        encoding="utf-8",
    )

    manifest = load_corpus_manifest(manifest_path)

    assert manifest.case_id == "unused-variable"
    assert manifest.target_file == "tests/fixtures/corpus/valid/UnusedVariable.s"
    assert manifest.mode == "workspace"
    assert manifest.expectation.expected_finding_ids == (
        "semantic.read-before-write",
        "unused",
    )
    assert manifest.expectation.forbidden_finding_ids == ("hardcoded-windows-path",)
    assert manifest.expectation.artifact_fragments == {
        "status.json": {
            "execution_status": "ok",
        },
    }
    assert manifest.required_artifacts == ("summary.json", "findings.json")


def test_evaluate_finding_ids_reports_missing_and_forbidden_ids(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "contract-check",
                "target_file": "tests/fixtures/corpus/edge_cases/Contract.s",
                "expectation": {
                    "expected_finding_ids": ["unused", "contract_mismatch"],
                    "forbidden_finding_ids": ["secret-assignment"],
                },
            }
        ),
        encoding="utf-8",
    )

    manifest = load_corpus_manifest(manifest_path)
    evaluation = evaluate_finding_ids(
        manifest,
        ["unused", "secret-assignment"],
    )

    assert evaluation.passed is False
    assert evaluation.missing_finding_ids == ("contract_mismatch",)
    assert evaluation.unexpected_finding_ids == ("secret-assignment",)
    assert evaluation.to_dict() == {
        "case_id": "contract-check",
        "passed": False,
        "missing_finding_ids": ["contract_mismatch"],
        "unexpected_finding_ids": ["secret-assignment"],
        "artifact_fragment_failures": [],
    }


def test_run_corpus_case_validates_required_artifacts_and_findings(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "unused-variable",
                "target_file": "tests/fixtures/corpus/valid/UnusedVariable.s",
                "mode": "workspace",
                "expectation": {
                    "expected_finding_ids": ["unused"],
                    "forbidden_finding_ids": ["secret-assignment"],
                },
                "required_artifacts": ["summary.json", "findings.json"],
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "findings.json").write_text(
        json.dumps(
            {
                "kind": "sattlint.findings",
                "schema_version": 1,
                "finding_count": 1,
                "findings": [
                    {
                        "id": "unused",
                        "rule_id": "unused",
                        "category": "style",
                        "severity": "medium",
                        "confidence": "high",
                        "message": "Unused variable.",
                        "source": "pipeline",
                        "analyzer": "demo",
                        "artifact": "findings",
                        "location": {
                            "path": "src/demo.py",
                            "line": 3,
                            "column": 1,
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

    result = run_corpus_case(manifest_path, artifact_dir)

    assert result.passed is False
    assert result.missing_artifacts == ("summary.json",)
    assert result.evaluation.passed is True
    assert result.to_dict() == {
        "case_id": "unused-variable",
        "target_file": "tests/fixtures/corpus/valid/UnusedVariable.s",
        "mode": "workspace",
        "findings_report": "findings.json",
        "findings_schema": {"kind": "sattlint.findings", "schema_version": 1},
        "passed": False,
        "missing_artifacts": ["summary.json"],
        "evaluation": {
            "case_id": "unused-variable",
            "passed": True,
            "missing_finding_ids": [],
            "unexpected_finding_ids": [],
            "artifact_fragment_failures": [],
        },
    }


def test_run_corpus_case_reports_artifact_fragment_failures(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "strict-fragment-check",
                "target_file": "tests/fixtures/corpus/invalid/NotSattLine.s",
                "mode": "strict",
                "expectation": {
                    "expected_finding_ids": ["syntax.parse"],
                    "artifact_fragments": {
                        "status.json": {
                            "execution_status": "ok",
                            "validation_ok": False,
                        },
                        "summary.json": {
                            "stage": "semantic",
                        },
                    },
                },
                "required_artifacts": ["status.json", "summary.json", "findings.json"],
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "findings.json").write_text(
        json.dumps(
            {
                "kind": "sattlint.findings",
                "schema_version": 1,
                "finding_count": 1,
                "findings": [
                    {
                        "id": "syntax.parse",
                        "rule_id": "syntax.parse",
                        "category": "syntax",
                        "severity": "high",
                        "confidence": "high",
                        "message": "Parse failed.",
                        "source": "corpus-runner",
                        "analyzer": "syntax-check",
                        "artifact": "findings",
                        "location": {
                            "path": "tests/fixtures/corpus/invalid/NotSattLine.s",
                            "line": 1,
                            "column": 1,
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
    (artifact_dir / "status.json").write_text(
        json.dumps(
            {
                "execution_status": "ok",
                "validation_ok": False,
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "summary.json").write_text(
        json.dumps(
            {
                "stage": "parse",
            }
        ),
        encoding="utf-8",
    )

    result = run_corpus_case(manifest_path, artifact_dir)

    assert result.passed is False
    assert result.evaluation.passed is False
    assert result.evaluation.artifact_fragment_failures == ("summary.json.stage: expected 'semantic', got 'parse'",)


def test_execute_corpus_case_strict_writes_case_artifacts(tmp_path):
    manifest_path = tmp_path / "strict-case.json"
    source_path = tmp_path / "Broken.s"
    artifact_dir = tmp_path / "artifacts"
    source_path.write_text("this is not valid sattline", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "strict-parse-error",
                "target_file": "Broken.s",
                "mode": "strict",
                "expectation": {
                    "expected_finding_ids": ["syntax.parse"],
                    "artifact_fragments": {
                        "status.json": {
                            "execution_status": "ok",
                            "validation_ok": False,
                            "stage": "parse",
                        },
                        "summary.json": {
                            "stage": "parse",
                            "validation_ok": False,
                        },
                    },
                },
                "required_artifacts": ["status.json", "summary.json", "findings.json"],
            }
        ),
        encoding="utf-8",
    )

    result = execute_corpus_case(manifest_path, artifact_dir, repo_root=tmp_path)

    findings_report = json.loads((artifact_dir / "findings.json").read_text(encoding="utf-8"))
    status_report = json.loads((artifact_dir / "status.json").read_text(encoding="utf-8"))
    summary_report = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))

    assert result.passed is True
    assert result.execution_error is None
    assert_findings_collection(findings_report, finding_count=1)
    assert findings_report["findings"][0]["rule_id"] == "syntax.parse"
    assert status_report["execution_status"] == "ok"
    assert status_report["validation_ok"] is False
    assert_findings_schema(status_report)
    assert_findings_schema(summary_report)
    assert summary_report["stage"] == "parse"


def test_execute_corpus_case_workspace_writes_semantic_findings(monkeypatch, tmp_path):
    manifest_path = tmp_path / "workspace-case.json"
    target_path = tmp_path / "Program.s"
    artifact_dir = tmp_path / "artifacts"
    target_path.write_text("placeholder", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "workspace-semantic",
                "target_file": "Program.s",
                "mode": "workspace",
                "expectation": {
                    "expected_finding_ids": ["semantic.read-before-write"],
                    "artifact_fragments": {
                        "status.json": {
                            "execution_status": "ok",
                            "missing_dependency_count": 0,
                        },
                        "summary.json": {
                            "rule_counts": {
                                "semantic.read-before-write": 1,
                            },
                        },
                    },
                },
                "required_artifacts": ["status.json", "summary.json", "findings.json"],
            }
        ),
        encoding="utf-8",
    )

    class _FakeHeader:
        name = "Program"

    class _FakeBasePicture:
        header = _FakeHeader()

    class _FakeLoader:
        def __init__(self, *args, **kwargs):
            pass

        def resolve(self, target_name, strict=False):
            assert target_name == "Program"
            assert strict is False
            return type(
                "FakeGraph",
                (),
                {
                    "ast_by_name": {"Program": _FakeBasePicture()},
                    "warnings": [],
                    "missing": [],
                    "unavailable_libraries": set(),
                },
            )()

    monkeypatch.setattr("sattlint.devtools.corpus.engine_module.SattLineProjectLoader", _FakeLoader)
    monkeypatch.setattr(
        "sattlint.devtools.corpus.engine_module.merge_project_basepicture",
        lambda root_bp, graph: root_bp,
    )
    monkeypatch.setattr(
        "sattlint.devtools.corpus.engine_module._is_within_directory",
        lambda path, directory: True,
    )
    monkeypatch.setattr(
        "sattlint.devtools.corpus.analyze_sattline_semantics",
        lambda *args, **kwargs: SattLineSemanticsReport(
            basepicture_name="Program",
            issues=[
                SemanticIssue(
                    rule=SemanticRule(
                        id="semantic.read-before-write",
                        source="dataflow",
                        category="variable-lifecycle",
                        severity="warning",
                        applies_to="variable",
                        description="Read before write.",
                    ),
                    message="Variable 'PumpStart' is read before it is written.",
                    module_path=["Program", "UnitA"],
                )
            ],
        ),
    )

    result = execute_corpus_case(manifest_path, artifact_dir, repo_root=tmp_path)

    findings_report = json.loads((artifact_dir / "findings.json").read_text(encoding="utf-8"))
    summary_report = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))

    assert result.passed is True
    assert result.execution_error is None
    assert_findings_collection(findings_report, finding_count=1)
    assert findings_report["findings"][0]["rule_id"] == "semantic.read-before-write"
    assert findings_report["findings"][0]["location"]["module_path"] == ["Program", "UnitA"]
    assert_findings_schema(summary_report)
    assert summary_report["rule_counts"] == {"semantic.read-before-write": 1}


def test_execute_corpus_case_workspace_preserves_guidance_for_semantic_findings(monkeypatch, tmp_path):
    manifest_path = tmp_path / "workspace-case.json"
    target_path = tmp_path / "Program.s"
    artifact_dir = tmp_path / "artifacts"
    target_path.write_text("placeholder", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "workspace-guidance",
                "target_file": "Program.s",
                "mode": "workspace",
                "expectation": {
                    "expected_finding_ids": ["semantic.read-before-write"],
                },
                "required_artifacts": ["status.json", "summary.json", "findings.json"],
            }
        ),
        encoding="utf-8",
    )

    class _FakeHeader:
        name = "Program"

    class _FakeBasePicture:
        header = _FakeHeader()

    class _FakeLoader:
        def __init__(self, *args, **kwargs):
            pass

        def resolve(self, target_name, strict=False):
            assert target_name == "Program"
            assert strict is False
            return type(
                "FakeGraph",
                (),
                {
                    "ast_by_name": {"Program": _FakeBasePicture()},
                    "warnings": [],
                    "missing": [],
                    "unavailable_libraries": set(),
                },
            )()

    monkeypatch.setattr("sattlint.devtools.corpus.engine_module.SattLineProjectLoader", _FakeLoader)
    monkeypatch.setattr(
        "sattlint.devtools.corpus.engine_module.merge_project_basepicture",
        lambda root_bp, graph: root_bp,
    )
    monkeypatch.setattr(
        "sattlint.devtools.corpus.engine_module._is_within_directory",
        lambda path, directory: True,
    )
    monkeypatch.setattr(
        "sattlint.devtools.corpus.analyze_sattline_semantics",
        lambda *args, **kwargs: SattLineSemanticsReport(
            basepicture_name="Program",
            issues=[
                SemanticIssue(
                    rule=SemanticRule(
                        id="semantic.read-before-write",
                        source="dataflow",
                        category="variable-lifecycle",
                        severity="warning",
                        applies_to="variable",
                        description="Read before write.",
                        explanation="The read can observe undefined state on some control paths.",
                        suggestion="Initialize the variable before the first possible read.",
                    ),
                    message="Variable 'PumpStart' is read before it is written.",
                    module_path=["Program", "UnitA"],
                )
            ],
        ),
    )

    execute_corpus_case(manifest_path, artifact_dir, repo_root=tmp_path)

    findings_report = json.loads((artifact_dir / "findings.json").read_text(encoding="utf-8"))

    assert_findings_collection(findings_report, finding_count=1)
    assert findings_report["findings"][0]["detail"] == "The read can observe undefined state on some control paths."
    assert findings_report["findings"][0]["suggestion"] == "Initialize the variable before the first possible read."


def test_run_corpus_suite_aggregates_case_results_and_writes_report(tmp_path):
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    broken_file = tmp_path / "Broken.s"
    broken_file.write_text("still invalid", encoding="utf-8")

    expected_manifest = manifest_dir / "expected.json"
    expected_manifest.write_text(
        json.dumps(
            {
                "case_id": "expected-parse-error",
                "target_file": "../Broken.s",
                "mode": "strict",
                "expectation": {"expected_finding_ids": ["syntax.parse"]},
            }
        ),
        encoding="utf-8",
    )
    failing_manifest = manifest_dir / "failing.json"
    failing_manifest.write_text(
        json.dumps(
            {
                "case_id": "missing-expected-finding",
                "target_file": "../Broken.s",
                "mode": "strict",
                "expectation": {"expected_finding_ids": ["semantic.read-before-write"]},
            }
        ),
        encoding="utf-8",
    )

    suite = run_corpus_suite(
        tmp_path / "out",
        manifest_dir=manifest_dir,
        repo_root=tmp_path,
        write_results=True,
    )

    report = json.loads(((tmp_path / "out") / CORPUS_RESULTS_FILENAME).read_text(encoding="utf-8"))

    assert suite.passed is False
    assert_corpus_results_report(
        report,
        case_count=2,
        failed_case_ids=("missing-expected-finding",),
    )
    assert report["summary"] == {
        "case_count": 2,
        "passed_count": 1,
        "failed_count": 1,
        "execution_error_count": 0,
        "missing_artifact_case_count": 0,
    }


def test_print_cli_summary_includes_findings_schema(capsys):
    from sattlint.devtools import corpus

    corpus._print_cli_summary(
        {
            "case_count": 2,
            "failed_count": 1,
            "findings_schema": {
                "kind": "sattlint.findings",
                "schema_version": 1,
            },
            "corpus_results_report": "<external>/analysis/corpus_results.json",
        }
    )

    output = capsys.readouterr().out

    assert "Findings schema: sattlint.findings v1" in output
    assert "Corpus cases: 2" in output
    assert "Failed cases: 1" in output
    assert "Corpus results: <external>/analysis/corpus_results.json" in output


def test_checked_in_corpus_manifests_pass_against_repo_fixtures(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    manifest_dir = repo_root / "tests" / "fixtures" / "corpus" / "manifests"

    suite = run_corpus_suite(
        tmp_path,
        manifest_dir=manifest_dir,
        repo_root=repo_root,
        write_results=False,
    )

    case_ids = {case.manifest.case_id for case in suite.cases}
    # Original anchor cases always present
    assert "strict-invalid" in case_ids
    assert "workspace-common-quality-issues" in case_ids
    # All manifests should be loaded and all should pass
    assert suite.passed is True, f"Failed cases: {[c.manifest.case_id for c in suite.cases if not c.passed]}"
    assert all(case.execution_error is None for case in suite.cases)
