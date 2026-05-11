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


def _empty_resolved_entries() -> list[ICFResolvedEntry]:
    return []


def _empty_skipped_entries() -> list[ICFSkippedEntry]:
    return []


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
        normalized_compared = compared_text
        detailed_compared = re.match(
            r"^current unit (.+?) \(unit type (.+?)\) differs from reference unit (.+)$",
            compared_text,
        )
        if detailed_compared:
            current_unit, unit_type, reference_unit = detailed_compared.groups()
            normalized_compared = f"{current_unit} vs {reference_unit} (unit type {unit_type})"
        lines.extend(_wrap_text("      compared units: ", normalized_compared, "                      "))
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
            if label.startswith("missing"):
                lines.append("        action: add these missing entries to current unit")
            else:
                lines.append("        action: remove these extra entries from current unit")
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
                lines.append("        action: reorder current unit entries to match reference unit order")
            else:
                lines.extend(_wrap_text("        ", mismatch, "        "))
                lines.append("        action: reorder current unit entries to match reference unit order")
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
    operation: str | None = None
    journal: str | None = None
    group: str | None = None


@dataclass(frozen=True)
class ICFValidationIssue:
    entry: ICFEntry
    reason: str
    detail: str | None = None


@dataclass(frozen=True)
class ICFSkippedEntry:
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
    resolved_entries: list[ICFResolvedEntry] = field(default_factory=_empty_resolved_entries)
    skipped_details: list[ICFSkippedEntry] = field(default_factory=_empty_skipped_entries)

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
                # Unit-structure drift is cross-unit and should not be anchored to
                # potentially unrelated first-entry operation/journal/group context.
                if issue.reason != "unit structure drift":
                    if issue.entry.operation:
                        context_parts.append(f"Operation {issue.entry.operation}")
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

        if self.skipped_details:
            lines.append("")
            lines.append("Skipped entries:")
            for skipped in self.skipped_details:
                location = f"{skipped.entry.file_path.name}:{skipped.entry.line_no}"
                context_parts: list[str] = []
                if skipped.entry.unit:
                    context_parts.append(f"Unit {skipped.entry.unit}")
                if skipped.entry.operation:
                    context_parts.append(f"Operation {skipped.entry.operation}")
                if skipped.entry.journal:
                    context_parts.append(f"Journal {skipped.entry.journal}")
                if skipped.entry.group:
                    context_parts.append(f"Group {skipped.entry.group}")
                if context_parts:
                    section = f" [{' | '.join(context_parts)}]"
                else:
                    section = f" [{skipped.entry.section}]" if skipped.entry.section else ""
                detail = f" ({skipped.detail})" if skipped.detail else ""
                lines.extend(
                    _wrap_text(
                        "  - ",
                        f"{location}{section} {skipped.entry.key} => {skipped.entry.value}: {skipped.reason}{detail}",
                        "    ",
                    )
                )

        return "\n".join(lines)
