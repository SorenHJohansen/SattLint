import json
from pathlib import Path

import pytest

from sattlint.contracts import FindingCollection, FindingLocation, FindingRecord
from sattlint.devtools import finding_exports
from sattlint.devtools.artifact_registry import PIPELINE_ARTIFACTS, build_artifact_registry_report
from sattlint.devtools.baselines import build_analysis_diff_report, load_finding_collection
from sattlint.devtools.corpus import (
    CorpusCaseManifest,
    CorpusEvaluation,
    CorpusExpectation,
    CorpusRunResult,
    CorpusSuiteResult,
)
from sattlint.devtools.finding_exports import build_pipeline_finding_collection

from .helpers.artifact_assertions import (
    assert_analysis_diff_report,
    assert_artifact_registry_report,
    assert_corpus_results_report,
    assert_findings_collection,
    assert_matches_golden,
)

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "goldens"


def _build_sample_findings_payload(repo_root: Path) -> dict[str, object]:
    return build_pipeline_finding_collection(
        repo_root=repo_root,
        ruff_findings=[
            {
                "code": "F401",
                "message": "Imported but unused",
                "filename": str(repo_root / "src" / "sample.py"),
                "location": {"row": 4, "column": 8},
            }
        ],
        pyright_findings=[
            {
                "severity": "error",
                "message": "Incompatible types in assignment",
                "file": str(repo_root / "src" / "typed.py"),
                "line": 9,
                "column": 3,
                "errorCode": "assignment",
            }
        ],
        pytest_report={
            "summary": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0},
            "testcases": [
                {
                    "classname": "tests.test_sample",
                    "name": "test_failure",
                    "outcome": "failed",
                    "detail": "tests/test_sample.py:23: AssertionError",
                    "nodeid": "tests/test_sample.py::test_failure",
                }
            ],
        },
        vulture_findings=[
            {
                "file": str(repo_root / "src" / "dead.py"),
                "line": 7,
                "message": "unused function 'helper'",
                "confidence": 95,
            }
        ],
        bandit_findings=[
            {
                "filename": str(repo_root / "src" / "security.py"),
                "line_number": 12,
                "issue_text": "Use of assert detected.",
                "issue_severity": "LOW",
                "issue_confidence": "HIGH",
                "test_id": "B101",
            }
        ],
        architecture_findings=[
            {
                "id": "analyzer-exposure-gap",
                "severity": "medium",
                "message": "Some analyzers are not exposed.",
                "missing_analyzers": ["naming-consistency"],
            }
        ],
    ).to_dict()


def test_finding_export_private_helpers_cover_fallback_paths(tmp_path):
    assert finding_exports._coerce_mapping_list("not-a-list") == []
    assert finding_exports._coerce_mapping_list([1, {"ok": 2}]) == [{"ok": 2}]

    assert finding_exports._ruff_severity("SIM117") == "medium"
    assert finding_exports._ruff_severity("PLR999") == "low"

    assert finding_exports._vulture_confidence("oops") == "medium"
    assert finding_exports._vulture_confidence(85) == "medium"
    assert finding_exports._vulture_confidence(10) == "low"
    assert finding_exports._vulture_severity(85) == "medium"
    assert finding_exports._vulture_severity(10) == "low"
    assert finding_exports._vulture_metadata("not a dead-code message", None) == {}

    assert finding_exports._normalized_severity("warning", default="low") == "medium"
    assert finding_exports._normalized_severity("note", default="medium") == "low"
    assert finding_exports._normalized_severity("unexpected", default="medium") == "medium"
    assert finding_exports._int_or_none("oops") is None

    assert finding_exports._pytest_failure_location(None, repo_root=tmp_path) == (None, None)
    assert finding_exports._pytest_failure_location("no traceback here", repo_root=tmp_path) == (None, None)
    assert finding_exports._pytest_nodeid({"name": "test_case"}, sanitized_file="tests/test_sample.py") == (
        "tests/test_sample.py::test_case"
    )
    assert (
        finding_exports._pytest_nodeid(
            {"classname": "tests.test_sample.TestSuite", "name": "test_case"},
            sanitized_file=None,
        )
        == "tests.test_sample.TestSuite::test_case"
    )
    assert finding_exports._pytest_nodeid({}, sanitized_file=None) is None


def test_finding_export_builders_cover_tool_and_pytest_fallbacks(tmp_path):
    mypy_records = finding_exports._build_mypy_findings(
        [{"message": "Missing type information"}],
        repo_root=tmp_path,
    )
    assert mypy_records[0].rule_id == "mypy.unknown.unknown"
    assert mypy_records[0].minimal_reproducer == "mypy src tests"

    pyright_records = finding_exports._build_pyright_findings(
        [{"severity": "warning", "message": "Type issue", "range": {}, "rule": "reportGeneralTypeIssues"}],
        repo_root=tmp_path,
    )
    assert pyright_records[0].rule_id == "pyright.reportGeneralTypeIssues"
    assert pyright_records[0].minimal_reproducer == "pyright src tests"
    assert pyright_records[0].location.path is None

    bandit_records = finding_exports._build_bandit_findings(
        [{"issue_text": "Use of assert detected.", "issue_severity": "warning", "issue_confidence": "note"}],
        repo_root=tmp_path,
    )
    assert bandit_records[0].severity == "medium"
    assert bandit_records[0].confidence == "low"

    pytest_records = finding_exports._build_pytest_findings(
        {
            "summary": {"failures": 2, "errors": 1},
            "testcases": [
                {
                    "name": "test_parsed",
                    "outcome": "failed",
                    "detail": "tests/test_sample.py:23: AssertionError",
                },
                {
                    "classname": "tests.test_sample.TestSuite",
                    "name": "test_error",
                    "outcome": "error",
                    "detail": "no traceback",
                },
                {
                    "outcome": "failed",
                    "detail": "no traceback",
                },
            ],
        },
        repo_root=tmp_path,
    )

    assert pytest_records[0].location.path == "tests/test_sample.py"
    assert pytest_records[0].location.line == 23
    assert pytest_records[0].location.symbol == "tests/test_sample.py::test_parsed"
    assert pytest_records[1].rule_id == "pytest.errors"
    assert pytest_records[1].location.symbol == "tests.test_sample.TestSuite::test_error"
    assert (
        pytest_records[1].minimal_reproducer
        == "python -m pytest tests.test_sample.TestSuite::test_error -x -q --tb=short"
    )
    assert pytest_records[2].minimal_reproducer == "python -m pytest -x -q --tb=short"

    explicit_pytest_records = finding_exports._build_pytest_findings(
        {
            "summary": {"failures": 1, "errors": 0},
            "testcases": [
                {
                    "file": str(tmp_path / "tests" / "explicit.py"),
                    "line": 11,
                    "name": "test_explicit",
                    "outcome": "failed",
                }
            ],
        },
        repo_root=tmp_path,
    )

    assert explicit_pytest_records[0].location.line == 11
    assert explicit_pytest_records[0].location.symbol == "tests/explicit.py::test_explicit"


def _build_sample_analysis_diff_payload() -> dict[str, object]:
    baseline = FindingCollection(
        (
            FindingRecord(
                id="unchanged",
                rule_id="ruff.f401",
                category="style",
                severity="high",
                confidence="high",
                message="Imported but unused",
                source="ruff",
            ),
            FindingRecord(
                id="changed-old",
                rule_id="pytest.failures",
                category="correctness",
                severity="high",
                confidence="high",
                message="Pytest reported failing tests.",
                source="pytest",
            ),
            FindingRecord(
                id="resolved",
                rule_id="vulture.dead-code",
                category="dead-code",
                severity="medium",
                confidence="medium",
                message="Potential dead code found.",
                source="vulture",
            ),
        )
    )
    current = FindingCollection(
        (
            FindingRecord(
                id="unchanged",
                rule_id="ruff.f401",
                category="style",
                severity="high",
                confidence="high",
                message="Imported but unused",
                source="ruff",
            ),
            FindingRecord(
                id="changed-new",
                rule_id="pytest.failures",
                category="correctness",
                severity="high",
                confidence="high",
                message="Pytest reported failing or erroring tests.",
                source="pytest",
            ),
            FindingRecord(
                id="new",
                rule_id="bandit.b101",
                category="security",
                severity="low",
                confidence="high",
                message="Use of assert detected.",
                source="bandit",
            ),
        )
    )
    return build_analysis_diff_report(
        baseline=baseline,
        current=current,
        baseline_label="baseline.json",
        current_label="current.json",
    )


def _build_sample_artifact_registry_payload() -> dict[str, object]:
    return build_artifact_registry_report(
        PIPELINE_ARTIFACTS,
        generated_by="sattlint.devtools.pipeline",
        profile="quick",
        enabled_artifact_ids={
            "status",
            "summary",
            "findings",
            "analysis_diff",
            "corpus_results",
            "artifact_registry",
        },
    )


def _build_sample_corpus_results_payload() -> dict[str, object]:
    return CorpusSuiteResult(
        cases=(
            CorpusRunResult(
                manifest=CorpusCaseManifest(
                    case_id="workspace-semantic",
                    target_file="tests/fixtures/corpus/valid/Program.s",
                    mode="workspace",
                    expectation=CorpusExpectation(
                        expected_finding_ids=("semantic.read-before-write",),
                    ),
                ),
                evaluation=CorpusEvaluation(
                    case_id="workspace-semantic",
                    passed=True,
                ),
                findings_report="findings.json",
                findings_schema={"kind": "sattlint.findings", "schema_version": 1},
                artifact_dir="corpus_cases/workspace-semantic",
            ),
        ),
        output_dir="artifacts/analysis",
        manifest_root="tests/fixtures/corpus/manifests",
    ).to_dict()


def test_pipeline_findings_payload_matches_golden(tmp_path):
    payload = _build_sample_findings_payload(tmp_path)

    assert_findings_collection(
        payload,
        finding_count=6,
        rule_ids=(
            "ruff.f401",
            "pyright.assignment",
            "pytest.failures",
            "vulture.dead-code",
            "bandit.b101",
            "analyzer-exposure-gap",
        ),
    )
    assert_matches_golden(payload, GOLDEN_DIR / "pipeline_findings.json")


def test_analysis_diff_payload_matches_golden():
    payload = _build_sample_analysis_diff_payload()

    assert_analysis_diff_report(
        payload,
        summary={
            "new_count": 1,
            "resolved_count": 1,
            "changed_count": 1,
            "unchanged_count": 1,
        },
        baseline_label="baseline.json",
        current_label="current.json",
        new_rule_ids=("bandit.b101",),
        resolved_rule_ids=("vulture.dead-code",),
        unchanged_rule_ids=("ruff.f401",),
        changed_rule_ids=("pytest.failures",),
        changed_fields_by_rule_id={
            "pytest.failures": ("id", "message"),
        },
    )
    assert_matches_golden(payload, GOLDEN_DIR / "analysis_diff.json")


def test_load_finding_collection_round_trips_payload(tmp_path: Path):
    payload = FindingCollection(
        (
            FindingRecord(
                id="demo-id",
                rule_id="demo.rule",
                category="demo",
                severity="medium",
                confidence="high",
                message="Demo finding",
                source="tests",
            ),
        )
    ).to_dict()
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_finding_collection(findings_path)

    assert loaded.to_dict() == payload


def test_analysis_diff_payload_includes_location_and_data_changes():
    baseline = FindingCollection(
        (
            FindingRecord(
                id="same-id",
                rule_id="demo.rule",
                category="demo",
                severity="medium",
                confidence="high",
                message="Same message",
                source="tests",
                fingerprint="baseline-fp",
                location=FindingLocation(path="src/demo.py", line=4, column=1, symbol="Var"),
                data={"value": "old"},
            ),
        )
    )
    current = FindingCollection(
        (
            FindingRecord(
                id="same-id",
                rule_id="demo.rule",
                category="demo",
                severity="medium",
                confidence="high",
                message="Same message",
                source="tests",
                fingerprint="current-fp",
                location=FindingLocation(path="src/demo.py", line=4, column=2, symbol="Var"),
                data={"value": "new"},
            ),
        )
    )

    payload = build_analysis_diff_report(baseline=baseline, current=current)

    assert payload["summary"]["changed_count"] == 1
    assert payload["findings"]["changed"][0]["change"]["changed_fields"] == ["location", "data"]


def test_artifact_registry_payload_matches_golden():
    payload = _build_sample_artifact_registry_payload()

    assert_artifact_registry_report(
        payload,
        generated_by="sattlint.devtools.pipeline",
        profile="quick",
        enabled_artifact_ids=(
            "status",
            "summary",
            "findings",
            "analysis_diff",
            "corpus_results",
            "artifact_registry",
        ),
        disabled_artifact_ids=("progress", "environment", "ruff", "pyright", "pytest"),
    )
    assert_matches_golden(payload, GOLDEN_DIR / "artifact_registry_quick.json")


def test_corpus_results_payload_matches_golden():
    payload = _build_sample_corpus_results_payload()

    assert_corpus_results_report(payload, case_count=1, failed_case_ids=())
    assert_matches_golden(payload, GOLDEN_DIR / "corpus_results.json")


# ---------------------------------------------------------------------------
# Negative-path / drift detection
# ---------------------------------------------------------------------------


def test_assert_findings_collection_fails_on_wrong_kind():

    bad_payload = {
        "kind": "sattlint.WRONG",
        "schema_version": 1,
        "finding_count": 0,
        "findings": [],
    }

    with pytest.raises(AssertionError):
        assert_findings_collection(bad_payload)


def test_assert_findings_collection_fails_on_wrong_schema_version():

    bad_payload = {
        "kind": "sattlint.findings",
        "schema_version": 99,
        "finding_count": 0,
        "findings": [],
    }

    with pytest.raises(AssertionError):
        assert_findings_collection(bad_payload)


def test_assert_findings_collection_fails_on_wrong_finding_count():

    bad_payload = {
        "kind": "sattlint.findings",
        "schema_version": 1,
        "finding_count": 5,
        "findings": [],
    }

    with pytest.raises(AssertionError):
        assert_findings_collection(bad_payload, finding_count=0)


def test_assert_findings_collection_fails_on_wrong_rule_ids():

    bad_payload = {
        "kind": "sattlint.findings",
        "schema_version": 1,
        "finding_count": 1,
        "findings": [{"rule_id": "ruff.f401"}],
    }

    with pytest.raises(AssertionError):
        assert_findings_collection(bad_payload, rule_ids=("pyright.error",))


def test_assert_corpus_results_report_fails_on_wrong_failed_case_ids():

    payload = _build_sample_corpus_results_payload()

    with pytest.raises(AssertionError):
        assert_corpus_results_report(payload, failed_case_ids=("unexpected-failure",))


def test_assert_matches_golden_fails_on_extra_key(tmp_path):

    golden = tmp_path / "golden.json"
    golden.write_text('{"key": "value"}', encoding="utf-8")

    with pytest.raises(AssertionError):
        assert_matches_golden({"key": "value", "extra": "drift"}, golden)


def test_assert_matches_golden_fails_on_missing_key(tmp_path):

    golden = tmp_path / "golden.json"
    golden.write_text('{"key": "value", "required": true}', encoding="utf-8")

    with pytest.raises(AssertionError):
        assert_matches_golden({"key": "value"}, golden)


def test_assert_analysis_diff_report_fails_on_wrong_new_count():

    payload = _build_sample_analysis_diff_payload()

    with pytest.raises(AssertionError):
        assert_analysis_diff_report(payload, new_rule_ids=("nonexistent.rule",))
