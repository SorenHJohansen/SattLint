from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sattline_parser.models.ast_model import BasePicture

from .framework import Issue, empty_issues, format_report_header
from .sfc import analyze_sfc, get_configured_mutually_exclusive_step_sets, get_configured_step_contracts

_SCAN_CONCURRENCY_ISSUE_KINDS = frozenset({"sfc_parallel_write_race"})


@dataclass
class ScanConcurrencyReport:
    name: str
    issues: list[Issue] = field(default_factory=empty_issues)

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header("Scan concurrency", self.name, status="ok")
            lines.append("No scan concurrency issues found.")
            return "\n".join(lines)

        lines = format_report_header("Scan concurrency", self.name, status="issues")
        lines.append(f"Issues: {len(self.issues)}")
        lines.append("")
        lines.append("Parallel branch write races:")
        for issue in self.issues:
            location = ".".join(issue.module_path or [self.name])
            lines.append(f"  - [{location}] {issue.message}")
        return "\n".join(lines)


def analyze_scan_concurrency(
    base_picture: BasePicture,
    config: dict[str, Any] | None = None,
) -> ScanConcurrencyReport:
    report = analyze_sfc(
        base_picture,
        mutually_exclusive_steps=get_configured_mutually_exclusive_step_sets(config),
        step_contracts=get_configured_step_contracts(config),
    )
    return ScanConcurrencyReport(
        name=base_picture.header.name,
        issues=[issue for issue in report.issues if issue.kind in _SCAN_CONCURRENCY_ISSUE_KINDS],
    )
