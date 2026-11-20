"""Text report labels must describe issue kinds in human terms."""

from __future__ import annotations

from sattlint.reporting.variables_report import IssueKind, VariablesReport


def test_selected_issue_kinds_use_section_labels() -> None:
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[],
        selected_issue_kinds=frozenset({IssueKind.RESET_CONTAMINATION, IssueKind.NEVER_READ}),
    )

    summary = report.summary()

    assert (
        "Selected issue kinds: Written but never read variables, Reset contamination (missing reset writes)" in summary
    )
    assert "reset_contamination" not in summary
    assert "never_read" not in summary
    assert (
        "No issues found for selected issue kinds: "
        "Written but never read variables, Reset contamination (missing reset writes)." in summary
    )


def test_rendered_empty_section_does_not_repeat_the_no_issues_message() -> None:
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[],
        selected_issue_kinds=frozenset({IssueKind.RESET_CONTAMINATION}),
        visible_kinds=frozenset({IssueKind.RESET_CONTAMINATION}),
        include_empty_sections=True,
    )

    summary = report.summary()

    assert "Selected issue kinds: Reset contamination (missing reset writes)" in summary
    assert "  - Reset contamination (missing reset writes) (0):" in summary
    assert "      none" in summary
    assert "No reset contamination (missing reset writes) found." not in summary
