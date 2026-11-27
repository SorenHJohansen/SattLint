from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ..analyzers.framework import format_report_header

_AGGREGATED_REASONS = {
    "mixed ICF value prefix letters",
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


@dataclass(frozen=True)
class ICFDriftEntry:
    """One unit-signature entry in a structured drift payload."""

    operation: str
    journal: str
    group: str
    key: str
    value: str


@dataclass(frozen=True)
class ICFDriftEntryChange:
    """A missing or extra group of entries, with a bounded preview."""

    kind: Literal["missing", "extra"]
    count: int
    entries: tuple[ICFDriftEntry, ...]


@dataclass(frozen=True)
class ICFDriftCountMismatch:
    current: int
    reference: int


@dataclass(frozen=True)
class ICFDriftOrderingMismatch:
    position: int
    expected: ICFDriftEntry
    found: ICFDriftEntry


@dataclass(frozen=True)
class ICFUnitDrift:
    """The structured comparison behind one "unit structure drift" finding."""

    current_unit: str
    unit_type: str
    reference_unit: str
    entry_changes: tuple[ICFDriftEntryChange, ...] = ()
    count_mismatch: ICFDriftCountMismatch | None = None
    ordering: ICFDriftOrderingMismatch | None = None


def format_icf_drift_entry(entry: ICFDriftEntry) -> str:
    label_parts: list[str] = []
    if entry.operation:
        label_parts.append(f"Operation {entry.operation}")
    if entry.journal:
        label_parts.append(f"Journal {entry.journal}")
    if entry.group:
        label_parts.append(f"Group {entry.group}")
    scope = " | ".join(label_parts)
    scoped_key = entry.key if not scope else f"[{scope}] {entry.key}"
    return f"{scoped_key} => {entry.value}"


def format_icf_drift_entry_list(change: ICFDriftEntryChange) -> str:
    preview = ", ".join(format_icf_drift_entry(entry) for entry in change.entries)
    if change.count > len(change.entries):
        return f"{preview}, ..."
    return preview


def summarize_icf_unit_drift(drift: ICFUnitDrift) -> str:
    """One-line prose summary for messages and run records."""
    parts: list[str] = []
    for change in drift.entry_changes:
        parts.append(f"{change.kind} {change.count} entries ({format_icf_drift_entry_list(change)})")
    if drift.count_mismatch is not None:
        parts.append(f"entry count {drift.count_mismatch.current} != {drift.count_mismatch.reference}")
    if drift.ordering is not None:
        parts.append(
            "entry ordering differs "
            f"(first mismatch at position {drift.ordering.position}: "
            f"expected {format_icf_drift_entry(drift.ordering.expected)} "
            f"but found {format_icf_drift_entry(drift.ordering.found)})"
        )
    if not parts:
        parts.append("entry ordering differs")
    return (
        f"current unit {drift.current_unit} (unit type {drift.unit_type}) "
        f"differs from reference unit {drift.reference_unit}: {'; '.join(parts)}"
    )


def _format_drift_detail(drift: ICFUnitDrift) -> list[str]:
    lines: list[str] = []
    lines.extend(
        _wrap_text(
            "      compared units: ",
            f"{drift.current_unit} vs {drift.reference_unit} (unit type {drift.unit_type})",
            "                      ",
        )
    )

    for change in drift.entry_changes:
        lines.append(f"      - {change.kind} {change.count} entries")
        lines.extend(_wrap_text("        ", format_icf_drift_entry_list(change), "        "))
        if change.kind == "missing":
            lines.append("        action: add these missing entries to current unit")
        else:
            lines.append("        action: remove these extra entries from current unit")

    mismatch = drift.count_mismatch
    if mismatch is not None:
        lines.extend(_wrap_text("      - ", f"entry count {mismatch.current} != {mismatch.reference}", "        "))

    ordering = drift.ordering
    if ordering is not None:
        lines.append("      - entry ordering differs")
        lines.append(f"        first mismatch position: {ordering.position}")
        lines.extend(_wrap_text("        expected: ", format_icf_drift_entry(ordering.expected), "                  "))
        lines.extend(_wrap_text("        found: ", format_icf_drift_entry(ordering.found), "               "))
        lines.append("        action: reorder current unit entries to match reference unit order")

    return lines


def _format_issue_detail(issue: ICFValidationIssue) -> list[str]:
    if issue.reason == "unit structure drift" and issue.drift is not None:
        return _format_drift_detail(issue.drift)
    if not issue.detail:
        return []
    return _wrap_text("      detail: ", issue.detail, "              ")


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
    drift: ICFUnitDrift | None = None


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
    #: Library of the module the entry addresses; selects the record layout when
    #: two libraries declare the same datatype name.
    current_library: str | None = None


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
                    if issue.detail or issue.drift is not None:
                        lines.extend(_format_issue_detail(issue))
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
