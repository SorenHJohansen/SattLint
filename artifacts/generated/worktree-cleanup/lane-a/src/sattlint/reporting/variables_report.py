from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sattline_parser.models.ast_model import Simple_DataType, SourceSpan, Variable

from ._variables_report_rendering import (
    append_datatype_duplication,
    append_magic_numbers,
    append_min_max_mapping_mismatch,
    append_string_mapping_mismatch,
    append_unused_datatype_fields,
    append_variable_issue_list,
)


def _format_report_header(report_type: str, target: str, status: str | None = None) -> list[str]:
    lines = [f"Report: {report_type}", f"Target: {target}"]
    if status:
        lines.append(f"Status: {status}")
    return lines


class IssueKind(Enum):
    UNUSED = "unused"
    UNUSED_DATATYPE_FIELD = "unused_datatype_field"
    READ_ONLY_NON_CONST = "read_only_non_const"
    NAMING_ROLE_MISMATCH = "naming_role_mismatch"
    UI_ONLY = "ui_only"
    PROCEDURE_STATUS = "procedure_status"
    NEVER_READ = "never_read"
    WRITE_WITHOUT_EFFECT = "write_without_effect"
    GLOBAL_SCOPE_MINIMIZATION = "global_scope_minimization"
    HIDDEN_GLOBAL_COUPLING = "hidden_global_coupling"
    HIGH_FAN_IN_OUT = "high_fan_in_out"
    UNKNOWN_PARAMETER_TARGET = "unknown_parameter_target"
    REQUIRED_PARAMETER_CONNECTION = "required_parameter_connection"
    CONTRACT_MISMATCH = "contract_mismatch"
    STRING_MAPPING_MISMATCH = "string_mapping_mismatch"
    DATATYPE_DUPLICATION = "datatype_duplication"
    NAME_COLLISION = "name_collision"
    LAYOUT_OVERLAP = "layout_overlap"
    MIN_MAX_MAPPING_MISMATCH = "min_max_mapping_mismatch"
    MAGIC_NUMBER = "magic_number"
    SHADOWING = "shadowing"
    RESET_CONTAMINATION = "reset_contamination"
    IMPLICIT_LATCH = "implicit_latch"


DEFAULT_VARIABLE_ANALYSIS_KINDS: tuple[IssueKind, ...] = (
    IssueKind.UNUSED,
    IssueKind.UNUSED_DATATYPE_FIELD,
    IssueKind.READ_ONLY_NON_CONST,
    IssueKind.NEVER_READ,
    IssueKind.UNKNOWN_PARAMETER_TARGET,
    IssueKind.REQUIRED_PARAMETER_CONNECTION,
    IssueKind.STRING_MAPPING_MISMATCH,
    IssueKind.DATATYPE_DUPLICATION,
    IssueKind.MIN_MAX_MAPPING_MISMATCH,
    IssueKind.MAGIC_NUMBER,
    IssueKind.NAME_COLLISION,
    IssueKind.LAYOUT_OVERLAP,
    IssueKind.RESET_CONTAMINATION,
)

LOW_CONFIDENCE_VARIABLE_ANALYSIS_KINDS: tuple[IssueKind, ...] = (
    IssueKind.NAMING_ROLE_MISMATCH,
    IssueKind.UI_ONLY,
    IssueKind.PROCEDURE_STATUS,
    IssueKind.WRITE_WITHOUT_EFFECT,
    IssueKind.GLOBAL_SCOPE_MINIMIZATION,
    IssueKind.HIDDEN_GLOBAL_COUPLING,
    IssueKind.HIGH_FAN_IN_OUT,
    IssueKind.CONTRACT_MISMATCH,
    IssueKind.IMPLICIT_LATCH,
)

ALL_VARIABLE_ANALYSIS_KINDS: tuple[IssueKind, ...] = (
    *DEFAULT_VARIABLE_ANALYSIS_KINDS,
    *LOW_CONFIDENCE_VARIABLE_ANALYSIS_KINDS,
)

SUMMARY_SECTION_ORDER: tuple[IssueKind, ...] = (
    *ALL_VARIABLE_ANALYSIS_KINDS,
    IssueKind.SHADOWING,
)

SECTION_TITLES: dict[IssueKind, str] = {
    IssueKind.UNUSED: "Unused variables",
    IssueKind.UNUSED_DATATYPE_FIELD: "Unused fields in datatypes",
    IssueKind.READ_ONLY_NON_CONST: "Read-only but not Const variables",
    IssueKind.NAMING_ROLE_MISMATCH: "Naming-to-behavior mismatches",
    IssueKind.UI_ONLY: "UI/display-only variables",
    IssueKind.PROCEDURE_STATUS: "Procedure status handling",
    IssueKind.NEVER_READ: "Written but never read variables",
    IssueKind.WRITE_WITHOUT_EFFECT: "Write-without-effect variables",
    IssueKind.GLOBAL_SCOPE_MINIMIZATION: "Global scope minimization candidates",
    IssueKind.HIDDEN_GLOBAL_COUPLING: "Hidden global coupling",
    IssueKind.HIGH_FAN_IN_OUT: "High fan-in or fan-out variables",
    IssueKind.UNKNOWN_PARAMETER_TARGET: "Unknown parameter mapping targets",
    IssueKind.REQUIRED_PARAMETER_CONNECTION: "Missing required parameter connections",
    IssueKind.CONTRACT_MISMATCH: "Cross-module contract mismatches",
    IssueKind.STRING_MAPPING_MISMATCH: "String mapping type mismatches",
    IssueKind.DATATYPE_DUPLICATION: "Duplicated complex datatypes (should be RECORD)",
    IssueKind.MIN_MAX_MAPPING_MISMATCH: "Min/Max mapping name mismatches",
    IssueKind.MAGIC_NUMBER: "Magic numbers in code",
    IssueKind.NAME_COLLISION: "Name collisions",
    IssueKind.LAYOUT_OVERLAP: "Overlapping layout elements",
    IssueKind.SHADOWING: "Variable shadowing",
    IssueKind.RESET_CONTAMINATION: "Reset contamination (missing reset writes)",
    IssueKind.IMPLICIT_LATCH: "Implicit latching (missing matching False writes)",
}


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
        reset_txt = f" reset={self.reset_variable!r}" if self.reset_variable else ""
        return f"[{mp}] {role_txt} {self.variable.name!r}{field_txt} ({dt}){seq_txt}{reset_txt}"


@dataclass
class VariablesReport:
    basepicture_name: str
    issues: list[VariableIssue]
    visible_kinds: frozenset[IssueKind] | None = None
    include_empty_sections: bool = False

    def __post_init__(self) -> None:
        if self.visible_kinds is not None and not isinstance(self.visible_kinds, frozenset):
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
    def naming_role_mismatch(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.NAMING_ROLE_MISMATCH]

    @property
    def ui_only(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.UI_ONLY]

    @property
    def procedure_status(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.PROCEDURE_STATUS]

    @property
    def never_read(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.NEVER_READ]

    @property
    def write_without_effect(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.WRITE_WITHOUT_EFFECT]

    @property
    def global_scope_minimization(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION]

    @property
    def hidden_global_coupling(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.HIDDEN_GLOBAL_COUPLING]

    @property
    def high_fan_in_out(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.HIGH_FAN_IN_OUT]

    @property
    def unknown_parameter_targets(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.UNKNOWN_PARAMETER_TARGET]

    @property
    def required_parameter_connections(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.REQUIRED_PARAMETER_CONNECTION]

    @property
    def contract_mismatches(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.CONTRACT_MISMATCH]

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
    def layout_overlaps(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.LAYOUT_OVERLAP]

    @property
    def shadowing(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.SHADOWING]

    @property
    def reset_contamination(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.RESET_CONTAMINATION]

    @property
    def implicit_latches(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.IMPLICIT_LATCH]

    def _summary_kinds(self) -> tuple[IssueKind, ...]:
        if self.visible_kinds is not None:
            return tuple(kind for kind in SUMMARY_SECTION_ORDER if kind in self.visible_kinds)

        present_kinds = {issue.kind for issue in self.issues}
        return tuple(kind for kind in SUMMARY_SECTION_ORDER if kind in present_kinds)

    def _issues_for_kind(self, kind: IssueKind) -> list[VariableIssue]:
        if kind is IssueKind.UNUSED:
            return self.unused
        if kind is IssueKind.UNUSED_DATATYPE_FIELD:
            return self.unused_datatype_fields
        if kind is IssueKind.READ_ONLY_NON_CONST:
            return self.read_only_non_const
        if kind is IssueKind.NAMING_ROLE_MISMATCH:
            return self.naming_role_mismatch
        if kind is IssueKind.UI_ONLY:
            return self.ui_only
        if kind is IssueKind.PROCEDURE_STATUS:
            return self.procedure_status
        if kind is IssueKind.NEVER_READ:
            return self.never_read
        if kind is IssueKind.WRITE_WITHOUT_EFFECT:
            return self.write_without_effect
        if kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION:
            return self.global_scope_minimization
        if kind is IssueKind.HIDDEN_GLOBAL_COUPLING:
            return self.hidden_global_coupling
        if kind is IssueKind.HIGH_FAN_IN_OUT:
            return self.high_fan_in_out
        if kind is IssueKind.UNKNOWN_PARAMETER_TARGET:
            return self.unknown_parameter_targets
        if kind is IssueKind.REQUIRED_PARAMETER_CONNECTION:
            return self.required_parameter_connections
        if kind is IssueKind.CONTRACT_MISMATCH:
            return self.contract_mismatches
        if kind is IssueKind.STRING_MAPPING_MISMATCH:
            return self.string_mapping_mismatch
        if kind is IssueKind.DATATYPE_DUPLICATION:
            return self.datatype_duplication
        if kind is IssueKind.MIN_MAX_MAPPING_MISMATCH:
            return self.min_max_mapping_mismatch
        if kind is IssueKind.MAGIC_NUMBER:
            return self.magic_numbers
        if kind is IssueKind.NAME_COLLISION:
            return self.name_collisions
        if kind is IssueKind.LAYOUT_OVERLAP:
            return self.layout_overlaps
        if kind is IssueKind.SHADOWING:
            return self.shadowing
        if kind is IssueKind.RESET_CONTAMINATION:
            return self.reset_contamination
        if kind is IssueKind.IMPLICIT_LATCH:
            return self.implicit_latches
        return []

    def _section_counts(self, summary_kinds: tuple[IssueKind, ...]) -> list[str]:
        return [f"  - {SECTION_TITLES[kind]}: {len(self._issues_for_kind(kind))}" for kind in summary_kinds]

    def _append_unknown_parameter_targets(self, lines: list[str]) -> None:
        append_variable_issue_list(
            lines,
            SECTION_TITLES[IssueKind.UNKNOWN_PARAMETER_TARGET],
            self.unknown_parameter_targets,
        )

    def _append_required_parameter_connections(self, lines: list[str]) -> None:
        append_variable_issue_list(
            lines,
            SECTION_TITLES[IssueKind.REQUIRED_PARAMETER_CONNECTION],
            self.required_parameter_connections,
        )

    def _append_procedure_status(self, lines: list[str]) -> None:
        append_variable_issue_list(
            lines,
            SECTION_TITLES[IssueKind.PROCEDURE_STATUS],
            self.procedure_status,
        )

    def _append_contract_mismatches(self, lines: list[str]) -> None:
        append_variable_issue_list(
            lines,
            SECTION_TITLES[IssueKind.CONTRACT_MISMATCH],
            self.contract_mismatches,
        )

    def _append_high_fan_in_out(self, lines: list[str]) -> None:
        append_variable_issue_list(
            lines,
            SECTION_TITLES[IssueKind.HIGH_FAN_IN_OUT],
            self.high_fan_in_out,
        )

    def _append_section(self, lines: list[str], kind: IssueKind) -> None:
        if kind is IssueKind.UNUSED:
            append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.UNUSED],
                self.unused,
            )
            return
        if kind is IssueKind.UNUSED_DATATYPE_FIELD:
            append_unused_datatype_fields(
                lines,
                SECTION_TITLES[IssueKind.UNUSED_DATATYPE_FIELD],
                self.unused_datatype_fields,
            )
            return
        if kind is IssueKind.READ_ONLY_NON_CONST:
            append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.READ_ONLY_NON_CONST],
                self.read_only_non_const,
            )
            return
        if kind is IssueKind.NAMING_ROLE_MISMATCH:
            append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.NAMING_ROLE_MISMATCH],
                self.naming_role_mismatch,
            )
            return
        if kind is IssueKind.UI_ONLY:
            append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.UI_ONLY],
                self.ui_only,
            )
            return
        if kind is IssueKind.PROCEDURE_STATUS:
            self._append_procedure_status(lines)
            return
        if kind is IssueKind.NEVER_READ:
            append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.NEVER_READ],
                self.never_read,
            )
            return
        if kind is IssueKind.WRITE_WITHOUT_EFFECT:
            append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.WRITE_WITHOUT_EFFECT],
                self.write_without_effect,
            )
            return
        if kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION:
            append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.GLOBAL_SCOPE_MINIMIZATION],
                self.global_scope_minimization,
            )
            return
        if kind is IssueKind.HIDDEN_GLOBAL_COUPLING:
            append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.HIDDEN_GLOBAL_COUPLING],
                self.hidden_global_coupling,
            )
            return
        if kind is IssueKind.HIGH_FAN_IN_OUT:
            self._append_high_fan_in_out(lines)
            return
        if kind is IssueKind.UNKNOWN_PARAMETER_TARGET:
            self._append_unknown_parameter_targets(lines)
            return
        if kind is IssueKind.REQUIRED_PARAMETER_CONNECTION:
            self._append_required_parameter_connections(lines)
            return
        if kind is IssueKind.CONTRACT_MISMATCH:
            self._append_contract_mismatches(lines)
            return
        if kind is IssueKind.STRING_MAPPING_MISMATCH:
            append_string_mapping_mismatch(
                lines,
                SECTION_TITLES[IssueKind.STRING_MAPPING_MISMATCH],
                self.string_mapping_mismatch,
            )
            return
        if kind is IssueKind.DATATYPE_DUPLICATION:
            append_datatype_duplication(
                lines,
                SECTION_TITLES[IssueKind.DATATYPE_DUPLICATION],
                self.datatype_duplication,
            )
            return
        if kind is IssueKind.MIN_MAX_MAPPING_MISMATCH:
            append_min_max_mapping_mismatch(
                lines,
                SECTION_TITLES[IssueKind.MIN_MAX_MAPPING_MISMATCH],
                self.min_max_mapping_mismatch,
            )
            return
        if kind is IssueKind.MAGIC_NUMBER:
            append_magic_numbers(
                lines,
                SECTION_TITLES[IssueKind.MAGIC_NUMBER],
                self.magic_numbers,
            )
            return
        if kind is IssueKind.NAME_COLLISION:
            append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.NAME_COLLISION],
                self.name_collisions,
            )
            return
        if kind is IssueKind.LAYOUT_OVERLAP:
            append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.LAYOUT_OVERLAP],
                self.layout_overlaps,
            )
            return
        if kind is IssueKind.SHADOWING:
            append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.SHADOWING],
                self.shadowing,
            )
            return
        if kind is IssueKind.RESET_CONTAMINATION:
            append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.RESET_CONTAMINATION],
                self.reset_contamination,
            )
            return
        if kind is IssueKind.IMPLICIT_LATCH:
            append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.IMPLICIT_LATCH],
                self.implicit_latches,
            )
            return

    def summary(self) -> str:
        summary_kinds = self._summary_kinds()
        if not self.issues and not summary_kinds:
            lines = _format_report_header("Variable issues", self.basepicture_name, status="ok")
            lines.append("No issues found.")
            return "\n".join(lines)

        status = "issues" if self.issues else "ok"
        lines = _format_report_header("Variable issues", self.basepicture_name, status=status)
        lines.append(f"Issues: {len(self.issues)}")
        if summary_kinds:
            lines.append("Sections:")
            lines.extend(self._section_counts(summary_kinds))
        for kind in summary_kinds:
            lines.append("")
            self._append_section(lines, kind)
        return "\n".join(lines)
