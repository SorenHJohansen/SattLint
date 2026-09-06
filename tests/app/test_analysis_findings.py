from types import SimpleNamespace

from sattlint.analyzers.framework import Issue
from sattlint.application.findings import AnalysisFinding, extract_report_findings


def test_extract_report_findings_normalizes_framework_issues() -> None:
    report = SimpleNamespace(
        issues=[
            Issue(
                kind="unused",
                message="declared but never read",
                module_path=["Root", "Mod"],
                severity="warning",
                confidence="high",
                rule_id="unused.variable",
                explanation="Stale declarations add noise.",
                suggestion="Delete the declaration.",
            ),
            Issue(kind="shadowing", message="shadows outer scope"),
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert len(findings) == 2
    first, second = findings
    assert first.kind == "unused"
    assert first.message == "declared but never read"
    assert first.module_path == ("Root", "Mod")
    assert first.severity == "warning"
    assert first.confidence == "high"
    assert first.rule_id == "unused.variable"
    assert first.explanation is not None
    assert first.suggestion is not None
    assert second.kind == "shadowing"
    assert second.module_path == ("Root",)


def test_extract_report_findings_handles_enum_kind_and_empty_module_path() -> None:
    class Kind:
        value = "never_read"

    report = SimpleNamespace(issues=[SimpleNamespace(kind=Kind(), message="written but never read", module_path=[])])

    findings = extract_report_findings(report, default_name="Root")

    assert len(findings) == 1
    assert findings[0].kind == "never_read"
    assert findings[0].module_path == ("Root",)


def test_extract_report_findings_handles_rule_based_issues_and_message_fallback() -> None:
    report = SimpleNamespace(
        issues=[
            SimpleNamespace(
                rule=SimpleNamespace(id="spec.sequence_step_prefix"),
                message="step must start with a transition",
                module_path=["Root", "Seq"],
            ),
            SimpleNamespace(kind="unused", module_path=["Root"]),
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert findings[0].kind == "spec.sequence_step_prefix"
    assert findings[0].message == "step must start with a transition"
    assert findings[0].module_path == ("Root", "Seq")
    assert findings[1].kind == "unused"
    assert findings[1].message  # falls back to str(item)


def test_extract_report_findings_returns_empty_for_missing_or_non_list_issues() -> None:
    assert extract_report_findings(SimpleNamespace(), default_name="Root") == ()
    assert extract_report_findings(SimpleNamespace(issues=[]), default_name="Root") == ()
    assert extract_report_findings(SimpleNamespace(issues="not-a-list"), default_name="Root") == ()


def test_analysis_finding_round_trips_through_dict() -> None:
    finding = AnalysisFinding(
        kind="unused",
        message="declared but never read",
        module_path=("Root", "Mod"),
        severity="warning",
        confidence="high",
        rule_id="unused.variable",
        explanation="Explains.",
        suggestion="Fixes.",
    )

    restored = AnalysisFinding.from_dict(finding.to_dict())

    assert restored == finding
