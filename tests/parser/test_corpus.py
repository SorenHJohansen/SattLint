import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from sattlint.analyzers.sattline_semantics import SattLineSemanticsReport, SemanticIssue, SemanticRule
from sattlint.devtools import corpus as corpus_module
from sattlint.devtools.corpus import (
    CORPUS_RESULTS_FILENAME,
    evaluate_finding_ids,
    execute_corpus_case,
    load_corpus_manifest,
    run_corpus_case,
    run_corpus_suite,
)

from ..helpers.artifact_assertions import (
    assert_corpus_results_report,
    assert_findings_collection,
    assert_findings_schema,
)


def _patch_workspace_case_loader(monkeypatch) -> None:
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
        "sattlint.devtools.corpus.engine_module.merge_project_basepicture", lambda root_bp, graph: root_bp
    )
    monkeypatch.setattr("sattlint.devtools.corpus.engine_module._is_within_directory", lambda path, directory: True)


def _semantic_read_before_write_report(*, explanation: str | None = None, suggestion: str | None = None):
    return SattLineSemanticsReport(
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
                    explanation=explanation,
                    suggestion=suggestion,
                ),
                message="Variable 'PumpStart' is read before it is written.",
                module_path=["Program", "UnitA"],
            )
        ],
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


def test_discover_corpus_manifests_and_run_corpus_case_missing_findings(tmp_path):
    missing_dir = tmp_path / "missing"
    assert corpus_module.discover_corpus_manifests(missing_dir) == ()

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    nested_dir = manifest_dir / "nested"
    nested_dir.mkdir()
    first_manifest = manifest_dir / "a.json"
    second_manifest = nested_dir / "b.json"
    first_manifest.write_text("{}", encoding="utf-8")
    second_manifest.write_text("{}", encoding="utf-8")
    (manifest_dir / "ignore.txt").write_text("ignore", encoding="utf-8")

    assert corpus_module.discover_corpus_manifests(manifest_dir) == (first_manifest, second_manifest)

    manifest_path = tmp_path / "manifest.json"
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "missing-findings",
                "target_file": "tests/fixtures/corpus/valid/UnusedVariable.s",
                "mode": "workspace",
                "expectation": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="Corpus findings artifact does not exist"):
        run_corpus_case(manifest_path, artifact_dir)


def test_corpus_helper_paths_severity_mode_and_summary(tmp_path):
    manifest_path = tmp_path / "manifests" / "case.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("{}", encoding="utf-8")
    manifest_relative = manifest_path.parent / "relative.s"
    manifest_relative.write_text("relative", encoding="utf-8")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    assert corpus_module._normalize_severity("HIGH") == "high"
    assert corpus_module._normalize_severity("warning") == "medium"
    assert corpus_module._normalize_severity("note") == "low"

    assert (
        corpus_module._resolve_manifest_target_path(manifest_path, str(manifest_relative), repo_root)
        == manifest_relative.resolve()
    )
    assert (
        corpus_module._resolve_manifest_target_path(manifest_path, "fallback.s", repo_root)
        == (repo_root / "fallback.s").resolve()
    )
    assert corpus_module._resolve_optional_directory(None, manifest_path=manifest_path, repo_root=repo_root) is None
    assert (
        corpus_module._resolve_optional_directory("relative.s", manifest_path=manifest_path, repo_root=repo_root)
        == manifest_relative.resolve()
    )
    assert corpus_module._infer_code_mode(Path("demo.x")) == corpus_module.engine_module.CodeMode.OFFICIAL
    assert corpus_module._infer_code_mode(Path("demo.s")) == corpus_module.engine_module.CodeMode.DRAFT

    summary_text = corpus_module.format_cli_summary(
        {
            "case_count": 2,
            "failed_count": 1,
            "findings_schema": {"kind": "sattlint.findings", "schema_version": 1},
            "corpus_results_report": "reports/corpus_results.json",
        }
    )
    assert "Findings schema: sattlint.findings v1" in summary_text
    assert "Corpus cases: 2" in summary_text


def test_corpus_main_prints_summary_and_returns_failure_for_failed_suite(monkeypatch, tmp_path, capsys):
    suite = SimpleNamespace(
        passed=False,
        to_dict=lambda: {
            "summary": {"case_count": 2, "failed_count": 1},
            "findings_schema": {"kind": "sattlint.findings", "schema_version": 1},
        },
    )
    monkeypatch.setattr(corpus_module, "run_corpus_suite", lambda *args, **kwargs: suite)
    monkeypatch.setattr(corpus_module, "_write_json", lambda *_args, **_kwargs: None)

    exit_code = corpus_module.main(["--output-dir", str(tmp_path)])

    assert exit_code == 1
    assert "Corpus cases: 2" in capsys.readouterr().out

    corpus_module._print_cli_summary(
        {
            "case_count": 1,
            "failed_count": 0,
            "corpus_results_report": "reports/corpus_results.json",
        }
    )
    assert "Corpus results: reports/corpus_results.json" in capsys.readouterr().out


def test_build_strict_finding_collection_returns_empty_when_validation_succeeds():
    findings = corpus_module._build_strict_finding_collection(SimpleNamespace(ok=True), repo_root=Path.cwd())

    assert findings.findings == ()


def test_execute_corpus_case_unsupported_mode_and_workspace_missing_root(tmp_path, monkeypatch):
    target_path = tmp_path / "Program.s"
    target_path.write_text("program", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    artifact_dir = tmp_path / "artifacts"
    unsupported_manifest = corpus_module.CorpusCaseManifest(
        case_id="unsupported",
        target_file=str(target_path),
        mode="unsupported",
        expectation=corpus_module.CorpusExpectation(),
    )

    result = execute_corpus_case(manifest_path, artifact_dir, repo_root=tmp_path, manifest=unsupported_manifest)
    assert result.execution_error is not None
    assert "Unsupported corpus mode" in result.execution_error

    class _FakeLoader:
        def __init__(self, *args, **kwargs):
            pass

        def resolve(self, *_args, **_kwargs):
            return SimpleNamespace(ast_by_name={}, missing=["Dependency"], unavailable_libraries=set())

    monkeypatch.setattr(corpus_module.engine_module, "SattLineProjectLoader", _FakeLoader)

    workspace_manifest = corpus_module.CorpusCaseManifest(
        case_id="workspace",
        target_file=str(target_path),
        mode="workspace",
        expectation=corpus_module.CorpusExpectation(),
    )

    with pytest.raises(RuntimeError, match="was not parsed"):
        corpus_module._execute_workspace_case(
            workspace_manifest,
            manifest_path=manifest_path,
            target_path=target_path,
            repo_root=tmp_path,
        )


def test_execute_corpus_case_strict_writes_case_artifacts(tmp_path, caplog):
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

    with caplog.at_level(logging.ERROR, logger="SattLint"):
        result = execute_corpus_case(manifest_path, artifact_dir, repo_root=tmp_path)

    findings_report = json.loads((artifact_dir / "findings.json").read_text(encoding="utf-8"))
    status_report = json.loads((artifact_dir / "status.json").read_text(encoding="utf-8"))
    summary_report = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))

    assert result.passed is True
    assert result.execution_error is None
    assert_findings_collection(findings_report, finding_count=1)
    assert findings_report["findings"][0]["rule_id"] == "syntax.parse"
    assert findings_report["findings"][0]["file"] == "Broken.s"
    assert findings_report["findings"][0]["owner_surface"] == "syntax-check"
    assert findings_report["findings"][0]["minimal_reproducer"] == "sattlint syntax-check Broken.s"
    assert findings_report["findings"][0]["suggested_next_command"] == "sattlint syntax-check Broken.s"
    assert status_report["execution_status"] == "ok"
    assert status_report["validation_ok"] is False
    assert_findings_schema(status_report)
    assert_findings_schema(summary_report)
    assert summary_report["stage"] == "parse"
    assert not caplog.records


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

    _patch_workspace_case_loader(monkeypatch)
    monkeypatch.setattr(
        "sattlint.devtools.corpus.analyze_sattline_semantics",
        lambda *args, **kwargs: _semantic_read_before_write_report(),
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

    _patch_workspace_case_loader(monkeypatch)
    monkeypatch.setattr(
        "sattlint.devtools.corpus.analyze_sattline_semantics",
        lambda *args, **kwargs: _semantic_read_before_write_report(
            explanation="The read can observe undefined state on some control paths.",
            suggestion="Initialize the variable before the first possible read.",
        ),
    )

    execute_corpus_case(manifest_path, artifact_dir, repo_root=tmp_path)

    findings_report = json.loads((artifact_dir / "findings.json").read_text(encoding="utf-8"))

    assert_findings_collection(findings_report, finding_count=1)
    assert findings_report["findings"][0]["detail"] == "The read can observe undefined state on some control paths."
    assert findings_report["findings"][0]["suggestion"] == "Initialize the variable before the first possible read."


def test_execute_corpus_case_returns_execution_error_when_findings_evaluation_read_fails(tmp_path, monkeypatch):
    manifest_path = tmp_path / "strict-case.json"
    source_path = tmp_path / "Broken.s"
    artifact_dir = tmp_path / "artifacts"
    source_path.write_text("this is not valid sattline", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "strict-evaluation-read-failure",
                "target_file": "Broken.s",
                "mode": "strict",
                "expectation": {
                    "expected_finding_ids": ["syntax.parse"],
                },
                "required_artifacts": ["status.json", "summary.json", "findings.json"],
            }
        ),
        encoding="utf-8",
    )
    manifest = load_corpus_manifest(manifest_path)
    findings_path = artifact_dir / "findings.json"
    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == findings_path:
            raise PermissionError("locked")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    result = execute_corpus_case(manifest_path, artifact_dir, repo_root=tmp_path, manifest=manifest)

    status_report = json.loads(original_read_text(artifact_dir / "status.json", encoding="utf-8"))
    findings_report = json.loads(original_read_text(artifact_dir / "findings.json", encoding="utf-8"))

    assert result.passed is False
    assert result.execution_error == "Failed to evaluate corpus case strict-evaluation-read-failure: locked"
    assert result.evaluation.passed is True
    assert status_report["execution_status"] == "error"
    assert status_report["error"] == "Failed to evaluate corpus case strict-evaluation-read-failure: locked"
    assert_findings_collection(findings_report, finding_count=1)
    assert findings_report["findings"][0]["rule_id"] == "corpus.execution-error"


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


def test_run_corpus_suite_keeps_running_when_manifest_is_malformed(tmp_path):
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    broken_file = tmp_path / "Broken.s"
    broken_file.write_text("still invalid", encoding="utf-8")

    valid_manifest = manifest_dir / "expected.json"
    valid_manifest.write_text(
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
    broken_manifest = manifest_dir / "broken.json"
    broken_manifest.write_text("{not-json", encoding="utf-8")

    suite = run_corpus_suite(
        tmp_path / "out",
        manifest_dir=manifest_dir,
        repo_root=tmp_path,
        write_results=True,
    )

    report = json.loads(((tmp_path / "out") / CORPUS_RESULTS_FILENAME).read_text(encoding="utf-8"))
    broken_case = next(case for case in report["cases"] if case["case_id"] == "broken")

    assert suite.passed is False
    assert_corpus_results_report(report, case_count=2, failed_case_ids=("broken",))
    assert report["summary"] == {
        "case_count": 2,
        "passed_count": 1,
        "failed_count": 1,
        "execution_error_count": 1,
        "missing_artifact_case_count": 0,
    }
    assert broken_case["execution_error"].startswith("Failed to load corpus manifest")
    assert broken_case["findings_schema"] == {"kind": "sattlint.findings", "schema_version": 1}
    assert ((tmp_path / "out") / "corpus_cases" / "broken" / "status.json").exists()


def test_main_returns_failure_when_results_report_write_fails(tmp_path, monkeypatch, capsys):
    fake_suite = type(
        "FakeSuite",
        (),
        {
            "passed": True,
            "to_dict": lambda self: {
                "summary": {
                    "case_count": 1,
                    "failed_count": 0,
                },
            },
        },
    )()

    monkeypatch.setattr("sattlint.devtools.corpus.run_corpus_suite", lambda *args, **kwargs: fake_suite)
    monkeypatch.setattr(
        "sattlint.devtools.corpus._write_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("locked")),
    )

    exit_code = __import__("sattlint.devtools.corpus", fromlist=["main"]).main(
        [
            "--output-dir",
            str(tmp_path / "out"),
            "--manifest-dir",
            str(tmp_path / "manifests"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Corpus cases: 1" in captured.out
    assert "Failed cases: 0" in captured.out
    assert "Corpus results:" in captured.out
    assert "corpus output error: locked" in captured.err
