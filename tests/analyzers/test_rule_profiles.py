from __future__ import annotations

from sattlint.analyzers import rule_profiles as rule_profiles_module
from sattlint.analyzers.sattline_semantics import SemanticRule
from sattlint.reporting.variables_report import IssueKind, VariableIssue, VariablesReport


def test_apply_rule_profile_to_report_handles_variable_issue_without_rule_metadata() -> None:
    issue = VariableIssue(kind=IssueKind.UNUSED, module_path=["BasePicture"], variable=None)
    report = VariablesReport(basepicture_name="Dummy", issues=[issue])

    updated = rule_profiles_module.apply_rule_profile_to_report(
        analyzer_key="variables",
        report=report,
        config={"analysis": {"rule_profiles": {"active": "legacy-plant"}}},
    )

    assert updated is report
    assert report.issues == [issue]


def test_apply_rule_profile_to_issue_can_disable_variable_issue_by_derived_rule_id(monkeypatch) -> None:
    def _resolve(issue_kind: str) -> SemanticRule | None:
        if issue_kind != "fake-kind":
            return None
        return SemanticRule(
            id="semantic.fake-rule",
            source="test",
            category="module-structure",
            severity="warning",
            applies_to="source-file",
            description="Synthetic rule for profile filter tests.",
        )

    monkeypatch.setattr(rule_profiles_module, "_resolve_issue_rule", _resolve)

    issue = VariableIssue(kind="fake-kind", module_path=["BasePicture"], variable=None)  # type: ignore[arg-type]
    profile = rule_profiles_module.RuleProfile(
        name="test",
        description="test",
        disabled_rules=("semantic.fake-rule",),
    )

    assert rule_profiles_module.apply_rule_profile_to_issue(issue, profile) is None


def test_variables_report_coerces_mutable_visible_kinds_to_frozenset() -> None:
    report = VariablesReport(
        basepicture_name="Dummy",
        issues=[],
        visible_kinds=[IssueKind.UNUSED],
    )

    assert report.visible_kinds == frozenset({IssueKind.UNUSED})
