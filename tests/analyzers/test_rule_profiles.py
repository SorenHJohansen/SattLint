# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportPrivateUsage=false, reportArgumentType=false, reportGeneralTypeIssues=false
from __future__ import annotations

from types import SimpleNamespace

from sattlint.analyzers import rule_profiles as rule_profiles_module
from sattlint.analyzers.framework import Issue, SimpleReport
from sattlint.analyzers.sattline_semantics import SemanticRule
from sattlint.reporting.variables_report import IssueKind, VariableIssue, VariablesReport


def test_apply_rule_profile_to_report_handles_variable_issue_without_rule_metadata() -> None:
    issue = VariableIssue(kind=IssueKind.UNUSED, module_path=["BasePicture"], variable=None)
    report = VariablesReport(basepicture_name="Dummy", issues=[issue])

    updated = rule_profiles_module.apply_rule_profile_to_report(
        analyzer_key="variables",
        report=report,
        config={
            "analysis": {
                "rule_profiles": {
                    "active": "custom",
                    "profiles": {"custom": {"description": "Custom profile"}},
                }
            }
        },
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


def test_rule_profile_configuration_helpers_normalize_payloads_and_reports() -> None:
    profile = rule_profiles_module.RuleProfile(
        name="custom",
        description="Custom",
        disabled_rules=("semantic.b", "semantic.a"),
        severity_overrides={"semantic.a": "error"},
        confidence_overrides={"semantic.a": "likely"},
    )

    assert profile.to_dict() == {
        "name": "custom",
        "description": "Custom",
        "disabled_rules": ["semantic.b", "semantic.a"],
        "severity_overrides": {"semantic.a": "error"},
        "confidence_overrides": {"semantic.a": "likely"},
    }
    assert rule_profiles_module._normalized_string_tuple([" semantic.b ", "", "semantic.a"]) == (
        "semantic.a",
        "semantic.b",
    )
    assert rule_profiles_module._normalized_string_tuple(("semantic.a",)) == ()
    assert rule_profiles_module._normalized_string_mapping({" semantic.a ": " error ", "": "x", "b": " "}) == {
        "semantic.a": "error"
    }
    assert rule_profiles_module._normalized_string_mapping(["semantic.a"]) == {}

    default_payload = rule_profiles_module._normalize_profile_payload("default", object())
    assert default_payload.name == "default"
    assert default_payload.description == "Balanced default analyzer profile."

    custom_payload = rule_profiles_module._normalize_profile_payload(
        "custom",
        {
            "description": "Custom profile",
            "disabled_rules": [" semantic.b ", "", "semantic.a"],
            "severity_overrides": {" semantic.a ": " error "},
            "confidence_overrides": {" semantic.a ": " likely "},
        },
    )
    assert custom_payload.disabled_rules == ("semantic.a", "semantic.b")
    assert custom_payload.severity_overrides == {"semantic.a": "error"}
    assert custom_payload.confidence_overrides == {"semantic.a": "likely"}

    configured = rule_profiles_module.get_configured_rule_profiles(
        {
            "analysis": {
                "rule_profiles": {
                    "profiles": {
                        " ": {"description": "ignored"},
                        "custom": {
                            "description": "Custom profile",
                            "disabled_rules": ["semantic.a"],
                        },
                    },
                    "active": "missing",
                }
            }
        }
    )
    assert "custom" in configured
    assert " " not in configured
    assert configured["custom"].disabled_rules == ("semantic.a",)

    active = rule_profiles_module.get_active_rule_profile(
        {
            "analysis": {
                "rule_profiles": {
                    "profiles": {"custom": {"description": "Custom profile"}},
                    "active": " missing ",
                }
            }
        }
    )
    assert active.name == "default"

    default_report = rule_profiles_module.get_default_rule_profile_report()
    assert default_report["active"] == "default"
    assert [item["name"] for item in default_report["profiles"]] == ["default"]


def test_rule_profile_metadata_and_override_helpers_cover_fallbacks() -> None:
    issue = Issue(kind="comment_code", message="Commented code")
    materialized = rule_profiles_module.materialize_issue_metadata(issue)

    assert materialized.rule_id == "semantic.commented-code"
    assert materialized.severity == "warning"
    assert materialized.confidence == "style"
    assert materialized.explanation is not None
    assert materialized.suggestion is not None

    unknown_issue = Issue(kind="unknown-kind", message="Unknown")
    assert rule_profiles_module.materialize_issue_metadata(unknown_issue) is unknown_issue
    assert rule_profiles_module._derived_rule_id(SimpleNamespace(kind=None)) is None
    none_kind_issue = SimpleNamespace(
        kind=None,
        rule_id=None,
        severity=None,
        confidence=None,
        explanation=None,
        suggestion=None,
    )
    assert rule_profiles_module.materialize_issue_metadata(none_kind_issue) is none_kind_issue
    no_metadata_issue = SimpleNamespace(kind="comment_code", message="Commented code")
    assert rule_profiles_module.materialize_issue_metadata(no_metadata_issue) is no_metadata_issue

    overridden = rule_profiles_module.apply_rule_profile_to_issue(
        issue,
        rule_profiles_module.RuleProfile(
            name="custom",
            description="Custom",
            severity_overrides={"semantic.commented-code": "error"},
            confidence_overrides={"semantic.commented-code": "definite"},
        ),
    )
    assert overridden is not None
    assert overridden.severity == "error"
    assert overridden.confidence == "definite"


def test_simple_report_summary_uses_registered_issue_metadata_materializer() -> None:
    summary = SimpleReport(name="Dummy", issues=[Issue(kind="comment_code", message="Commented code")]).summary()

    assert "semantic.commented-code" in summary
    assert "warning" in summary


def test_apply_rule_profile_to_report_filters_disabled_rules_and_handles_non_list_issues() -> None:
    non_list_report = SimpleNamespace(issues=(Issue(kind="comment_code", message="Commented code"),))
    assert rule_profiles_module.apply_rule_profile_to_report("comment-code", non_list_report, None) is non_list_report

    report = SimpleNamespace(
        issues=[
            Issue(kind="comment_code", message="Commented code"),
            Issue(kind="mms.dead_tag", message="Dead MMS tag"),
        ]
    )

    updated = rule_profiles_module.apply_rule_profile_to_report(
        "mms-interface",
        report,
        {
            "analysis": {
                "rule_profiles": {
                    "active": "custom",
                    "profiles": {
                        "custom": {
                            "description": "Custom",
                            "disabled_rules": ["semantic.commented-code"],
                            "severity_overrides": {"semantic.mms-dead-tag": "error"},
                            "confidence_overrides": {"semantic.mms-dead-tag": "definite"},
                        }
                    },
                }
            }
        },
    )

    assert updated is report
    assert len(report.issues) == 1
    assert report.issues[0].rule_id == "semantic.mms-dead-tag"
    assert report.issues[0].severity == "error"
    assert report.issues[0].confidence == "definite"
