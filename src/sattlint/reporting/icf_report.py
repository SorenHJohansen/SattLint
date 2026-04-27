from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from ..analyzers.framework import format_report_header

_AGGREGATED_REASONS = {
    "missing journal parameter fields",
    "unit structure drift",
}

_SUMMARY_WRAP_WIDTH = 120


def _wrap_text(prefix: str, text: str, subsequent_prefix: str) -> list[str]:
    wrapped = textwrap.wrap(
        text,
        width=_SUMMARY_WRAP_WIDTH,
        initial_indent=prefix,
        subsequent_indent=subsequent_prefix,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return wrapped or [prefix.rstrip()]


def _format_drift_detail(detail: str) -> list[str]:
    lines: list[str] = []
    compared_text = detail
    diff_text = ""
    if ": " in detail:
        compared_text, diff_text = detail.split(": ", 1)
        lines.extend(_wrap_text("      compared: ", compared_text, "                "))
    else:
        diff_text = detail

    for part in (segment.strip() for segment in diff_text.split("; ")):
        if not part:
            continue

        missing_or_extra = re.match(r"^(missing \d+ entries|extra \d+ entries) \((.*)\)$", part)
        if missing_or_extra:
            label, payload = missing_or_extra.groups()
            lines.append(f"      - {label}")
            lines.extend(_wrap_text("        ", payload, "        "))
            continue

        ordering = re.match(r"^entry ordering differs \((.*)\)$", part)
        if ordering:
            lines.append("      - entry ordering differs")
            mismatch = ordering.group(1)
            parsed_mismatch = re.match(
                r"^first mismatch at position (\d+): expected (.*) but found (.*)$",
                mismatch,
            )
            if parsed_mismatch:
                position, expected, found = parsed_mismatch.groups()
                lines.append(f"        first mismatch position: {position}")
                lines.extend(_wrap_text("        expected: ", expected, "                  "))
                lines.extend(_wrap_text("        found: ", found, "               "))
            else:
                lines.extend(_wrap_text("        ", mismatch, "        "))
            continue

        lines.extend(_wrap_text("      - ", part, "        "))

    return lines


def _format_issue_detail(reason: str, detail: str) -> list[str]:
    if reason == "unit structure drift":
        return _format_drift_detail(detail)
    return _wrap_text("      detail: ", detail, "              ")


@dataclass(frozen=True)
class ICFEntry:
    file_path: Path
    line_no: int
    section: str | None
    key: str
    value: str
    unit: str | None = None
    journal: str | None = None
    group: str | None = None


@dataclass(frozen=True)
class ICFValidationIssue:
    entry: ICFEntry
    reason: str
    detail: str | None = None


@dataclass(frozen=True)
class ICFResolvedEntry:
    entry: ICFEntry
    module_path: list[str]
    variable_name: str
    root_datatype: object
    field_path: str | None
    leaf_name: str
    datatype: object


@dataclass
class ICFValidationReport:
    icf_file: Path
    program_name: str
    total_entries: int
    validated_entries: int
    valid_entries: int
    skipped_entries: int
    issues: list[ICFValidationIssue]
    resolved_entries: list[ICFResolvedEntry] = field(default_factory=list)

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
                context_parts: list[str] = []
                if issue.entry.unit:
                    context_parts.append(f"Unit {issue.entry.unit}")
                if issue.entry.journal:
                    context_parts.append(f"Journal {issue.entry.journal}")
                if issue.entry.group:
                    context_parts.append(f"Group {issue.entry.group}")
                if context_parts:
                    section = f" [{' | '.join(context_parts)}]"
                else:
                    section = f" [{issue.entry.section}]" if issue.entry.section else ""
                detail = f" ({issue.detail})" if issue.detail else ""
                if issue.reason in _AGGREGATED_REASONS:
                    lines.append(f"  - {location}{section}: {issue.reason}")
                    if issue.detail:
                        lines.extend(_format_issue_detail(issue.reason, issue.detail))
                else:
                    lines.extend(
                        _wrap_text(
                            "  - ",
                            f"{location}{section} {issue.entry.key} => {issue.entry.value}: {issue.reason}{detail}",
                            "    ",
                        )
                    )

        return "\n".join(lines)
