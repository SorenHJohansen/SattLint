# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false
"""Corpus differential reporting tests (Phase 21).

Corpus runs are reviewable as before/after diffs: added findings, removed
findings, changed counts, changed rules — based on stable finding identity.
"""

from __future__ import annotations

from collections import Counter

from sattline_parser import parse_source_text as parser_core_parse_source_text

from sattlint.analyzers.sattline_semantics import (
    SattLineSemanticsReport,
    analyze_sattline_semantics,
)
from sattlint.reporting.corpus_diff import CountChange, diff_corpus_findings
from tests.helpers.app_menus_support import VALID_SINGLE_FILE


def _report_for_source(source: str) -> SattLineSemanticsReport:
    base_picture = parser_core_parse_source_text(source)
    return analyze_sattline_semantics(base_picture, debug=True)


def _finding_ids(report: SattLineSemanticsReport) -> list[str]:
    return [issue.rule.id for issue in report.issues]


def test_diff_between_identical_runs_is_empty() -> None:
    report = _report_for_source(VALID_SINGLE_FILE)
    baseline_ids = _finding_ids(report)
    current_ids = _finding_ids(report)

    diff = diff_corpus_findings(baseline_ids, current_ids)

    assert diff.added == ()
    assert diff.removed == ()
    assert diff.count_changes == ()


def test_diff_reports_added_and_removed_findings() -> None:
    baseline = ["semantic.a", "semantic.b"]
    current = ["semantic.b", "semantic.c"]

    diff = diff_corpus_findings(baseline, current)

    assert diff.added == ("semantic.c",)
    assert diff.removed == ("semantic.a",)
    assert diff.count_changes == ()


def test_diff_reports_count_changes() -> None:
    baseline = ["semantic.a", "semantic.a", "semantic.b"]
    current = ["semantic.a", "semantic.b", "semantic.b"]

    diff = diff_corpus_findings(baseline, current)

    assert diff.added == ()
    assert diff.removed == ()
    assert {change.finding_id: change.before for change in diff.count_changes} == {
        "semantic.a": 2,
        "semantic.b": 1,
    }
    assert {change.finding_id: change.after for change in diff.count_changes} == {
        "semantic.a": 1,
        "semantic.b": 2,
    }


def test_diff_ignores_unrelated_rules() -> None:
    baseline = ["semantic.a", "semantic.x"]
    current = ["semantic.a", "semantic.y"]

    diff = diff_corpus_findings(baseline, current)

    assert diff.added == ("semantic.y",)
    assert diff.removed == ("semantic.x",)
    assert diff.count_changes == ()


def test_diff_counts_use_stable_identity() -> None:
    baseline = Counter({"semantic.a": 3})
    current = Counter({"semantic.a": 1})

    diff = diff_corpus_findings(baseline, current)

    assert diff.added == ()
    assert diff.removed == ()
    assert diff.count_changes == (CountChange("semantic.a", 3, 1),)
