from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sattline_parser.models.ast_model import BasePicture

from .framework import Issue, empty_issues, format_report_header
from .same_cycle import analyze_same_cycle

_SCAN_SHARED_ACCESS_ISSUE_KINDS = frozenset({"same_cycle_non_state_multi_site_hazard"})


@dataclass
class ScanSharedAccessReport:
    name: str
    issues: list[Issue] = field(default_factory=empty_issues)

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header("Scan shared access", self.name, status="ok")
            lines.append("No scan shared-access issues found.")
            return "\n".join(lines)

        lines = format_report_header("Scan shared access", self.name, status="issues")
        lines.append(f"Issues: {len(self.issues)}")
        lines.append("")
        lines.append("Continuous multi-site shared access hazards:")
        for issue in self.issues:
            location = ".".join(issue.module_path or [self.name])
            lines.append(f"  - [{location}] {issue.message}")
        return "\n".join(lines)


def analyze_scan_shared_access(
    base_picture: BasePicture,
    config: dict[str, Any] | None = None,
) -> ScanSharedAccessReport:
    del config
    report = analyze_same_cycle(base_picture, selected_issue_kinds=_SCAN_SHARED_ACCESS_ISSUE_KINDS)
    return ScanSharedAccessReport(
        name=base_picture.header.name,
        issues=[issue for issue in report.issues if issue.kind in _SCAN_SHARED_ACCESS_ISSUE_KINDS],
    )
