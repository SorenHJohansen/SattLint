from types import SimpleNamespace

from sattlint.analyzers.framework import Issue
from sattlint.application.findings import AnalysisFinding, extract_report_findings, kind_human_label
from sattlint.models._variable_issues import IssueKind


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


def test_extract_report_findings_carries_issue_data_and_sanitizes_values() -> None:
    report = SimpleNamespace(
        issues=[
            Issue(
                kind="icf.unresolved_path",
                message="Program.icf:1: unresolved path",
                module_path=["Program"],
                data={"site": "Program.icf:1", "context": "X1 = Program:Path.Var", "nested": {"a": 1}},
            )
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert len(findings) == 1
    assert findings[0].data == {"site": "Program.icf:1", "context": "X1 = Program:Path.Var", "nested": {"a": 1}}


def test_extract_report_findings_synthesizes_site_and_context_from_attributes() -> None:
    variable = SimpleNamespace(name="TargetVal")
    source_variable = SimpleNamespace(name="SourceVal")
    report = SimpleNamespace(
        issues=[
            SimpleNamespace(
                kind="contract_mismatch",
                module_path=["Root", "Child"],
                variable=variable,
                source_variable=source_variable,
                source_display_name="SourceVal",
                target_display_name="TargetVal",
            )
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert len(findings) == 1
    assert findings[0].data == {"context": "TargetVal => SourceVal"}


def test_kind_human_label_returns_short_phrase() -> None:
    assert kind_human_label("magic_number") == "Magic number"
    assert kind_human_label("sfc_parallel_write_race") == "Parallel write race"
    assert kind_human_label("dataflow.condition_always_false") == "Condition always false"
    assert kind_human_label("unknown_custom_kind") == "Unknown Custom Kind"


def test_extract_report_findings_synthesizes_site_from_sequence_name() -> None:
    report = SimpleNamespace(issues=[SimpleNamespace(kind="unused", module_path=["Root"], sequence_name="MainSeq")])

    findings = extract_report_findings(report, default_name="Root")

    assert findings[0].data["site"] == "SQ:MainSeq"
    assert "context" not in findings[0].data


def test_extract_report_findings_sources_explanation_and_suggestion_from_variable_metadata() -> None:
    report = SimpleNamespace(issues=[SimpleNamespace(kind=IssueKind.UNUSED, module_path=["Root"])])

    findings = extract_report_findings(report, default_name="Root")

    assert findings[0].kind == "unused"
    assert findings[0].explanation
    assert findings[0].suggestion


def test_extract_report_findings_uses_explicit_context_attribute() -> None:
    report = SimpleNamespace(
        issues=[
            SimpleNamespace(
                kind=IssueKind.MAGIC_NUMBER,
                module_path=["Root"],
                context="Output = 1",
            )
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert findings[0].data["context"] == "Output = 1"
