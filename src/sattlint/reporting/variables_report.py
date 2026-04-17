from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..analyzers.framework import format_report_header
from ..models.ast_model import Simple_DataType, SourceSpan, Variable


class IssueKind(Enum):
    UNUSED = "unused"
    UNUSED_DATATYPE_FIELD = "unused_datatype_field"
    READ_ONLY_NON_CONST = "read_only_non_const"
    NEVER_READ = "never_read"
    UNKNOWN_PARAMETER_TARGET = "unknown_parameter_target"
    STRING_MAPPING_MISMATCH = "string_mapping_mismatch"
    DATATYPE_DUPLICATION = "datatype_duplication"
    NAME_COLLISION = "name_collision"
    MIN_MAX_MAPPING_MISMATCH = "min_max_mapping_mismatch"
    MAGIC_NUMBER = "magic_number"
    SHADOWING = "shadowing"
    RESET_CONTAMINATION = "reset_contamination"


DEFAULT_VARIABLE_ANALYSIS_KINDS: tuple[IssueKind, ...] = (
    IssueKind.UNUSED,
    IssueKind.UNUSED_DATATYPE_FIELD,
    IssueKind.READ_ONLY_NON_CONST,
    IssueKind.NEVER_READ,
    IssueKind.UNKNOWN_PARAMETER_TARGET,
    IssueKind.STRING_MAPPING_MISMATCH,
    IssueKind.DATATYPE_DUPLICATION,
    IssueKind.MIN_MAX_MAPPING_MISMATCH,
    IssueKind.MAGIC_NUMBER,
    IssueKind.NAME_COLLISION,
    IssueKind.RESET_CONTAMINATION,
)

SUMMARY_SECTION_ORDER: tuple[IssueKind, ...] = (
    *DEFAULT_VARIABLE_ANALYSIS_KINDS,
    IssueKind.SHADOWING,
)


@dataclass
class VariableIssue:
    kind: IssueKind
    module_path: list[str]
    variable: Variable | None
    datatype_name: str | None = None
    role: str | None = None
    source_variable: Variable | None = None
    duplicate_count: int | None = None
    duplicate_locations: list[tuple[list[str], str, str]] | None = None
    literal_value: int | float | None = None
    literal_span: SourceSpan | None = None
    site: str | None = None
    field_path: str | None = None
    sequence_name: str | None = None
    reset_variable: str | None = None

    def __str__(self) -> str:
        mp = ".".join(self.module_path)
        if self.variable is None and self.datatype_name is not None:
            field_txt = f".{self.field_path}" if self.field_path else ""
            return f"[{mp}] datatype {self.datatype_name!r}{field_txt}"
        if self.variable is None and self.literal_value is not None:
            return f"[{mp}] magic number {self.literal_value}"
        if self.variable is None and self.role is not None:
            return f"[{mp}] {self.role}"
        if self.variable is None:
            return f"[{mp}]"
        dt = (
            self.variable.datatype.value
            if isinstance(self.variable.datatype, Simple_DataType)
            else str(self.variable.datatype)
        )
        role_txt = f"{self.role} "
        field_txt = f".{self.field_path}" if self.field_path else ""
        seq_txt = f" seq={self.sequence_name!r}" if self.sequence_name else ""
        reset_txt = (
            f" reset={self.reset_variable!r}" if self.reset_variable else ""
        )
        return (
            f"[{mp}] {role_txt} {self.variable.name!r}{field_txt} ({dt})"
            f"{seq_txt}{reset_txt}"
        )


@dataclass
class VariablesReport:
    basepicture_name: str
    issues: list[VariableIssue]
    visible_kinds: frozenset[IssueKind] | None = None
    include_empty_sections: bool = False

    def __post_init__(self) -> None:
        if self.visible_kinds is not None and not isinstance(
            self.visible_kinds, frozenset
        ):
            self.visible_kinds = frozenset(self.visible_kinds)

    @property
    def name(self) -> str:
        return self.basepicture_name

    @property
    def unused(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.UNUSED]

    @property
    def unused_datatype_fields(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.UNUSED_DATATYPE_FIELD]

    @property
    def read_only_non_const(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.READ_ONLY_NON_CONST]

    @property
    def never_read(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.NEVER_READ]

    @property
    def unknown_parameter_targets(self) -> list[VariableIssue]:
        return [
            i for i in self.issues if i.kind is IssueKind.UNKNOWN_PARAMETER_TARGET
        ]

    @property
    def string_mapping_mismatch(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.STRING_MAPPING_MISMATCH]

    @property
    def datatype_duplication(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.DATATYPE_DUPLICATION]

    @property
    def min_max_mapping_mismatch(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.MIN_MAX_MAPPING_MISMATCH]

    @property
    def magic_numbers(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.MAGIC_NUMBER]

    @property
    def name_collisions(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.NAME_COLLISION]

    @property
    def shadowing(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.SHADOWING]

    @property
    def reset_contamination(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.RESET_CONTAMINATION]

    def _summary_kinds(self) -> tuple[IssueKind, ...]:
        if self.visible_kinds is not None:
            return tuple(
                kind for kind in SUMMARY_SECTION_ORDER if kind in self.visible_kinds
            )

        present_kinds = {issue.kind for issue in self.issues}
        return tuple(
            kind for kind in SUMMARY_SECTION_ORDER if kind in present_kinds
        )

    @staticmethod
    def _append_empty_section(lines: list[str], title: str) -> None:
        lines.append(title)
        lines.append("      none")

    @staticmethod
    def _append_variable_issue_list(
        lines: list[str], title: str, issues: list[VariableIssue]
    ) -> None:
        if not issues:
            VariablesReport._append_empty_section(lines, title)
            return

        lines.append(title)
        for issue in issues:
            lines.append(f"      * {issue}")

    def _append_unused_datatype_fields(self, lines: list[str]) -> None:
        title = "  - Unused fields in datatypes:"
        if not self.unused_datatype_fields:
            self._append_empty_section(lines, title)
            return

        lines.append(title)
        for issue in self.unused_datatype_fields:
            location = ".".join(issue.module_path)
            datatype_name = issue.datatype_name or "?"
            field_name = issue.field_path or "?"
            lines.append(f"      * [{location}] {datatype_name}.{field_name}")

    def _append_unknown_parameter_targets(self, lines: list[str]) -> None:
        self._append_variable_issue_list(
            lines,
            "  - Unknown parameter mapping targets:",
            self.unknown_parameter_targets,
        )

    def _append_string_mapping_mismatch(self, lines: list[str]) -> None:
        title = "  - String mapping type mismatches:"
        if not self.string_mapping_mismatch:
            self._append_empty_section(lines, title)
            return

        lines.append(title)
        lines.append("")
        location_w = max(
            len(".".join(issue.module_path)) for issue in self.string_mapping_mismatch
        )
        src_name_w = max(
            len(issue.source_variable.name) if issue.source_variable else 0
            for issue in self.string_mapping_mismatch
        )
        src_type_w = max(
            len(issue.source_variable.datatype_text) if issue.source_variable else 0
            for issue in self.string_mapping_mismatch
        )
        tgt_name_w = max(
            len(issue.variable.name) if issue.variable else 0
            for issue in self.string_mapping_mismatch
        )
        tgt_type_w = max(
            len(issue.variable.datatype_text) if issue.variable else 0
            for issue in self.string_mapping_mismatch
        )

        header = (
            f"      {'Location':<{location_w}}  "
            f"{'Source Var':<{src_name_w}}  {'Type':<{src_type_w}}  =>  "
            f"{'Target Var':<{tgt_name_w}}  {'Type':<{tgt_type_w}}"
        )
        lines.append(header)
        lines.append("      " + "-" * len(header.strip()))

        for issue in self.string_mapping_mismatch:
            location = ".".join(issue.module_path)
            src_name = issue.source_variable.name if issue.source_variable else "?"
            src_type = (
                issue.source_variable.datatype_text if issue.source_variable else "?"
            )
            tgt_name = issue.variable.name if issue.variable else "?"
            tgt_type = issue.variable.datatype_text if issue.variable else "?"
            lines.append(
                f"      {location:<{location_w}}  "
                f"{src_name:<{src_name_w}}  {src_type:<{src_type_w}}  =>  "
                f"{tgt_name:<{tgt_name_w}}  {tgt_type:<{tgt_type_w}}"
            )

        lines.append("")

    def _append_datatype_duplication(self, lines: list[str]) -> None:
        title = "  - Duplicated complex datatypes (should be RECORD):"
        if not self.datatype_duplication:
            self._append_empty_section(lines, title)
            return

        lines.append(title)
        lines.append("")
        for issue in sorted(
            self.datatype_duplication,
            key=lambda item: (
                item.variable.datatype_text if item.variable else "?",
                ".".join(item.module_path),
                item.variable.name if item.variable else "?",
            ),
        ):
            datatype_name = issue.variable.datatype_text if issue.variable else "?"
            location = ".".join(issue.module_path)
            count = issue.duplicate_count or 0
            lines.append(
                f"      Datatype '{datatype_name}' declared {count} times in {location}:"
            )
            lines.append(
                f"        - {issue.variable.name if issue.variable else '?'} ({issue.role})"
            )

            if issue.duplicate_locations:
                for dup_path, dup_role, dup_name in issue.duplicate_locations:
                    dup_location = ".".join(dup_path)
                    if dup_location == location:
                        lines.append(f"          + {dup_name} ({dup_role})")
                    else:
                        lines.append(
                            f"          + {dup_location}: {dup_name} ({dup_role})"
                        )

        lines.append("")

    def _append_min_max_mapping_mismatch(self, lines: list[str]) -> None:
        title = "  - Min/Max mapping name mismatches:"
        if not self.min_max_mapping_mismatch:
            self._append_empty_section(lines, title)
            return

        lines.append(title)
        lines.append("")
        location_w = max(
            len(".".join(issue.module_path))
            for issue in self.min_max_mapping_mismatch
        )
        src_name_w = max(
            len(issue.source_variable.name) if issue.source_variable else 0
            for issue in self.min_max_mapping_mismatch
        )
        tgt_name_w = max(
            len(issue.variable.name) if issue.variable else 0
            for issue in self.min_max_mapping_mismatch
        )

        header = (
            f"      {'Location':<{location_w}}  "
            f"{'Source Var':<{src_name_w}}  =>  "
            f"{'Target Var':<{tgt_name_w}}"
        )
        lines.append(header)
        lines.append("      " + "-" * len(header.strip()))

        for issue in self.min_max_mapping_mismatch:
            location = ".".join(issue.module_path)
            src_name = issue.source_variable.name if issue.source_variable else "?"
            tgt_name = issue.variable.name if issue.variable else "?"
            lines.append(
                f"      {location:<{location_w}}  "
                f"{src_name:<{src_name_w}}  =>  "
                f"{tgt_name:<{tgt_name_w}}"
            )

    def _append_magic_numbers(self, lines: list[str]) -> None:
        title = "  - Magic numbers in code:"
        if not self.magic_numbers:
            self._append_empty_section(lines, title)
            return

        lines.append(title)
        for issue in self.magic_numbers:
            location = ".".join(issue.module_path)
            site = f" [{issue.site}]" if issue.site else ""
            if issue.literal_span is not None:
                span_text = (
                    f"line {issue.literal_span.line}, col {issue.literal_span.column}"
                )
            else:
                span_text = "line ?, col ?"
            lines.append(
                f"      * {location}{site}: {issue.literal_value} ({span_text})"
            )

    def _append_section(self, lines: list[str], kind: IssueKind) -> None:
        if kind is IssueKind.UNUSED:
            self._append_variable_issue_list(lines, "  - Unused variables:", self.unused)
            return
        if kind is IssueKind.UNUSED_DATATYPE_FIELD:
            self._append_unused_datatype_fields(lines)
            return
        if kind is IssueKind.READ_ONLY_NON_CONST:
            self._append_variable_issue_list(
                lines,
                "  - Read-only but not Const variables:",
                self.read_only_non_const,
            )
            return
        if kind is IssueKind.NEVER_READ:
            self._append_variable_issue_list(
                lines,
                "  - written, but never read variables:",
                self.never_read,
            )
            return
        if kind is IssueKind.UNKNOWN_PARAMETER_TARGET:
            self._append_unknown_parameter_targets(lines)
            return
        if kind is IssueKind.STRING_MAPPING_MISMATCH:
            self._append_string_mapping_mismatch(lines)
            return
        if kind is IssueKind.DATATYPE_DUPLICATION:
            self._append_datatype_duplication(lines)
            return
        if kind is IssueKind.MIN_MAX_MAPPING_MISMATCH:
            self._append_min_max_mapping_mismatch(lines)
            return
        if kind is IssueKind.MAGIC_NUMBER:
            self._append_magic_numbers(lines)
            return
        if kind is IssueKind.NAME_COLLISION:
            self._append_variable_issue_list(
                lines, "  - Name collisions:", self.name_collisions
            )
            return
        if kind is IssueKind.SHADOWING:
            self._append_variable_issue_list(
                lines, "  - Variable shadowing:", self.shadowing
            )
            return
        if kind is IssueKind.RESET_CONTAMINATION:
            self._append_variable_issue_list(
                lines,
                "  - Reset contamination (missing reset writes):",
                self.reset_contamination,
            )

    def summary(self) -> str:
        summary_kinds = self._summary_kinds()
        if not self.issues and not summary_kinds:
            lines = format_report_header(
                "Variable issues", self.basepicture_name, status="ok"
            )
            lines.append("No issues found.")
            return "\n".join(lines)

        status = "issues" if self.issues else "ok"
        lines = format_report_header("Variable issues", self.basepicture_name, status=status)
        lines.append(f"Issues: {len(self.issues)}")
        for kind in summary_kinds:
            self._append_section(lines, kind)
        return "\n".join(lines)
