from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from ..analyzers.framework import format_report_header


@dataclass(frozen=True)
class ICFEntry:
    file_path: Path
    line_no: int
    section: str | None
    key: str
    value: str


@dataclass(frozen=True)
class ICFValidationIssue:
    entry: ICFEntry
    reason: str
    detail: str | None = None


@dataclass
class ICFValidationReport:
    icf_file: Path
    program_name: str
    total_entries: int
    validated_entries: int
    valid_entries: int
    skipped_entries: int
    issues: list[ICFValidationIssue]

    @property
    def name(self) -> str:
        return f"{self.icf_file.name} ({self.program_name})"

    def summary(self) -> str:
        status = "ok" if not self.issues else "issues"
        lines = format_report_header(
            "ICF validation",
            f"{self.icf_file.name} ({self.program_name})",
            status=status,
        )
        lines.extend(
            [
                f"Entries: {self.total_entries}",
                f"Validated: {self.validated_entries}",
                f"Valid: {self.valid_entries}",
                f"Skipped: {self.skipped_entries}",
                f"Invalid: {len(self.issues)}",
            ]
        )

        if self.issues:
            lines.append("")
            lines.append("Invalid entries:")
            for issue in self.issues:
                location = f"{issue.entry.file_path.name}:{issue.entry.line_no}"
                section = f" [{issue.entry.section}]" if issue.entry.section else ""
                detail = f" ({issue.detail})" if issue.detail else ""
                lines.append(
                    f"  - {location}{section} {issue.entry.key} => {issue.entry.value}: {issue.reason}{detail}"
                )

        return "\n".join(lines)
