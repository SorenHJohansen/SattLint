from pathlib import Path

from sattlint.contracts import FindingCollection, FindingRecord
from sattlint.devtools.artifact_registry import PIPELINE_ARTIFACTS, build_artifact_registry_report
from sattlint.devtools.baselines import build_analysis_diff_report
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
        pytest_report={"summary": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0}},
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
            "mypy.error.assignment",
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
        disabled_artifact_ids=("environment", "ruff", "mypy", "pytest"),
    )
    assert_matches_golden(payload, GOLDEN_DIR / "artifact_registry_quick.json")


def test_corpus_results_payload_matches_golden():
    payload = _build_sample_corpus_results_payload()

    assert_corpus_results_report(payload, case_count=1, failed_case_ids=())
    assert_matches_golden(payload, GOLDEN_DIR / "corpus_results.json")
