# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportPrivateUsage=false, reportArgumentType=false, reportGeneralTypeIssues=false
from __future__ import annotations

from types import SimpleNamespace

from sattlint.analyzers import _sattline_semantic_issue_metadata as issue_metadata_module
from sattlint.analyzers.framework import Issue, SimpleReport


def test_materialize_issue_metadata_covers_fallbacks() -> None:
    issue = Issue(kind="comment_code", message="Commented code")
    materialized = issue_metadata_module.materialize_issue_metadata(issue)

    assert materialized.rule_id == "semantic.commented-code"
    assert materialized.explanation is not None
    assert materialized.suggestion is not None

    unknown_issue = Issue(kind="unknown-kind", message="Unknown")
    assert issue_metadata_module.materialize_issue_metadata(unknown_issue) is unknown_issue
    none_kind_issue = SimpleNamespace(
        kind=None,
        rule_id=None,
        explanation=None,
        suggestion=None,
    )
    assert issue_metadata_module.materialize_issue_metadata(none_kind_issue) is none_kind_issue
    no_metadata_issue = SimpleNamespace(kind="comment_code", message="Commented code")
    assert issue_metadata_module.materialize_issue_metadata(no_metadata_issue) is no_metadata_issue


def test_simple_report_summary_uses_registered_issue_metadata_materializer() -> None:
    summary = SimpleReport(name="Dummy", issues=[Issue(kind="comment_code", message="Commented code")]).summary()

    assert "semantic.commented-code" in summary
    assert "Commented-out code" in summary
