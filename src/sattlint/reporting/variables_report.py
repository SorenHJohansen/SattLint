from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..analyzers.framework import format_report_header
from ..models.ast_model import Simple_DataType, SourceSpan, Variable


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
        return f"[{mp}] {role_txt} {self.variable.name!r}{field_txt} ({dt})" f"{seq_txt}{reset_txt}"


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
        if kind is IssueKind.SHADOWING:
            return self.shadowing
        if kind is IssueKind.RESET_CONTAMINATION:
            return self.reset_contamination
        if kind is IssueKind.IMPLICIT_LATCH:
            return self.implicit_latches
        return []

    @staticmethod
    def _section_header(title: str, count: int) -> str:
        return f"  - {title} ({count}):"

    @staticmethod
    def _format_location(module_path: list[str]) -> str:
        return ".".join(module_path) if module_path else "?"

    @staticmethod
    def _variable_datatype_text(variable: Variable) -> str:
        if isinstance(variable.datatype, Simple_DataType):
            return variable.datatype.value
        return str(variable.datatype)

    @classmethod
    def _format_issue(cls, issue: VariableIssue) -> str:
        location = cls._format_location(issue.module_path)

        if issue.variable is None and issue.datatype_name is not None:
            field_name = issue.field_path or "?"
            return f"{location} :: {issue.datatype_name}.{field_name}"

        if issue.variable is None and issue.literal_value is not None:
            site = f" [{issue.site}]" if issue.site else ""
            if issue.literal_span is not None:
                span_text = f"line {issue.literal_span.line}, col {issue.literal_span.column}"
            else:
                span_text = "line ?, col ?"
            return f"{location}{site} :: {issue.literal_value} ({span_text})"

        if issue.variable is None:
            return f"{location} :: {issue.role or 'issue'}"

        variable_name = issue.variable.name
        if issue.field_path:
            variable_name = f"{variable_name}.{issue.field_path}"
        variable_text = f"{variable_name} ({cls._variable_datatype_text(issue.variable)})"

        if issue.role in {"localvariable", "moduleparameter"}:
            detail = f"{issue.role} {variable_text}"
        elif issue.role:
            detail = f"{variable_text} | {issue.role}"
        else:
            detail = variable_text

        extra_parts: list[str] = []
        if issue.sequence_name:
            extra_parts.append(f"sequence={issue.sequence_name}")
        if issue.reset_variable:
            extra_parts.append(f"reset={issue.reset_variable}")
        if extra_parts:
            detail = f"{detail} | {' | '.join(extra_parts)}"

        return f"{location} :: {detail}"

    def _section_counts(self, summary_kinds: tuple[IssueKind, ...]) -> list[str]:
        return [f"  - {SECTION_TITLES[kind]}: {len(self._issues_for_kind(kind))}" for kind in summary_kinds]

    @staticmethod
    def _append_empty_section(lines: list[str], title: str) -> None:
        lines.append(VariablesReport._section_header(title, 0))
        lines.append("      none")

    @classmethod
    def _append_variable_issue_list(cls, lines: list[str], title: str, issues: list[VariableIssue]) -> None:
        if not issues:
            cls._append_empty_section(lines, title)
            return

        lines.append(cls._section_header(title, len(issues)))
        for issue in issues:
            lines.append(f"      * {cls._format_issue(issue)}")

    def _append_unused_datatype_fields(self, lines: list[str]) -> None:
        title = SECTION_TITLES[IssueKind.UNUSED_DATATYPE_FIELD]
        if not self.unused_datatype_fields:
            self._append_empty_section(lines, title)
            return

        lines.append(self._section_header(title, len(self.unused_datatype_fields)))
        for issue in self.unused_datatype_fields:
            location = self._format_location(issue.module_path)
            datatype_name = issue.datatype_name or "?"
            field_name = issue.field_path or "?"
            lines.append(f"      * {location} :: {datatype_name}.{field_name}")

    def _append_unknown_parameter_targets(self, lines: list[str]) -> None:
        self._append_variable_issue_list(
            lines,
            SECTION_TITLES[IssueKind.UNKNOWN_PARAMETER_TARGET],
            self.unknown_parameter_targets,
        )

    def _append_required_parameter_connections(self, lines: list[str]) -> None:
        self._append_variable_issue_list(
            lines,
            SECTION_TITLES[IssueKind.REQUIRED_PARAMETER_CONNECTION],
            self.required_parameter_connections,
        )

    def _append_procedure_status(self, lines: list[str]) -> None:
        self._append_variable_issue_list(
            lines,
            SECTION_TITLES[IssueKind.PROCEDURE_STATUS],
            self.procedure_status,
        )

    def _append_contract_mismatches(self, lines: list[str]) -> None:
        self._append_variable_issue_list(
            lines,
            SECTION_TITLES[IssueKind.CONTRACT_MISMATCH],
            self.contract_mismatches,
        )

    def _append_high_fan_in_out(self, lines: list[str]) -> None:
        self._append_variable_issue_list(
            lines,
            SECTION_TITLES[IssueKind.HIGH_FAN_IN_OUT],
            self.high_fan_in_out,
        )

    def _append_string_mapping_mismatch(self, lines: list[str]) -> None:
        title = SECTION_TITLES[IssueKind.STRING_MAPPING_MISMATCH]
        if not self.string_mapping_mismatch:
            self._append_empty_section(lines, title)
            return

        lines.append(self._section_header(title, len(self.string_mapping_mismatch)))
        location_w = max(len(".".join(issue.module_path)) for issue in self.string_mapping_mismatch)
        src_name_w = max(
            len(issue.source_variable.name) if issue.source_variable else 0 for issue in self.string_mapping_mismatch
        )
        src_type_w = max(
            len(issue.source_variable.datatype_text) if issue.source_variable else 0
            for issue in self.string_mapping_mismatch
        )
        tgt_name_w = max(len(issue.variable.name) if issue.variable else 0 for issue in self.string_mapping_mismatch)
        tgt_type_w = max(
            len(issue.variable.datatype_text) if issue.variable else 0 for issue in self.string_mapping_mismatch
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
            src_type = issue.source_variable.datatype_text if issue.source_variable else "?"
            tgt_name = issue.variable.name if issue.variable else "?"
            tgt_type = issue.variable.datatype_text if issue.variable else "?"
            lines.append(
                f"      {location:<{location_w}}  "
                f"{src_name:<{src_name_w}}  {src_type:<{src_type_w}}  =>  "
                f"{tgt_name:<{tgt_name_w}}  {tgt_type:<{tgt_type_w}}"
            )

    def _append_datatype_duplication(self, lines: list[str]) -> None:
        title = SECTION_TITLES[IssueKind.DATATYPE_DUPLICATION]
        if not self.datatype_duplication:
            self._append_empty_section(lines, title)
            return

        lines.append(self._section_header(title, len(self.datatype_duplication)))
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
            lines.append(f"      Datatype '{datatype_name}' declared {count} times in {location}:")
            lines.append(f"        - {issue.variable.name if issue.variable else '?'} ({issue.role})")

            if issue.duplicate_locations:
                for dup_path, dup_role, dup_name in issue.duplicate_locations:
                    dup_location = ".".join(dup_path)
                    if dup_location == location:
                        lines.append(f"          + {dup_name} ({dup_role})")
                    else:
                        lines.append(f"          + {dup_location}: {dup_name} ({dup_role})")

    def _append_min_max_mapping_mismatch(self, lines: list[str]) -> None:
        title = SECTION_TITLES[IssueKind.MIN_MAX_MAPPING_MISMATCH]
        if not self.min_max_mapping_mismatch:
            self._append_empty_section(lines, title)
            return

        lines.append(self._section_header(title, len(self.min_max_mapping_mismatch)))
        location_w = max(len(".".join(issue.module_path)) for issue in self.min_max_mapping_mismatch)
        src_name_w = max(
            len(issue.source_variable.name) if issue.source_variable else 0 for issue in self.min_max_mapping_mismatch
        )
        tgt_name_w = max(len(issue.variable.name) if issue.variable else 0 for issue in self.min_max_mapping_mismatch)

        header = (
            f"      {'Location':<{location_w}}  " f"{'Source Var':<{src_name_w}}  =>  " f"{'Target Var':<{tgt_name_w}}"
        )
        lines.append(header)
        lines.append("      " + "-" * len(header.strip()))

        for issue in self.min_max_mapping_mismatch:
            location = ".".join(issue.module_path)
            src_name = issue.source_variable.name if issue.source_variable else "?"
            tgt_name = issue.variable.name if issue.variable else "?"
            lines.append(
                f"      {location:<{location_w}}  " f"{src_name:<{src_name_w}}  =>  " f"{tgt_name:<{tgt_name_w}}"
            )

    def _append_magic_numbers(self, lines: list[str]) -> None:
        title = SECTION_TITLES[IssueKind.MAGIC_NUMBER]
        if not self.magic_numbers:
            self._append_empty_section(lines, title)
            return

        lines.append(self._section_header(title, len(self.magic_numbers)))
        for issue in self.magic_numbers:
            lines.append(f"      * {self._format_issue(issue)}")

    def _append_section(self, lines: list[str], kind: IssueKind) -> None:
        if kind is IssueKind.UNUSED:
            self._append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.UNUSED],
                self.unused,
            )
            return
        if kind is IssueKind.UNUSED_DATATYPE_FIELD:
            self._append_unused_datatype_fields(lines)
            return
        if kind is IssueKind.READ_ONLY_NON_CONST:
            self._append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.READ_ONLY_NON_CONST],
                self.read_only_non_const,
            )
            return
        if kind is IssueKind.NAMING_ROLE_MISMATCH:
            self._append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.NAMING_ROLE_MISMATCH],
                self.naming_role_mismatch,
            )
            return
        if kind is IssueKind.UI_ONLY:
            self._append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.UI_ONLY],
                self.ui_only,
            )
            return
        if kind is IssueKind.PROCEDURE_STATUS:
            self._append_procedure_status(lines)
            return
        if kind is IssueKind.NEVER_READ:
            self._append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.NEVER_READ],
                self.never_read,
            )
            return
        if kind is IssueKind.WRITE_WITHOUT_EFFECT:
            self._append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.WRITE_WITHOUT_EFFECT],
                self.write_without_effect,
            )
            return
        if kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION:
            self._append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.GLOBAL_SCOPE_MINIMIZATION],
                self.global_scope_minimization,
            )
            return
        if kind is IssueKind.HIDDEN_GLOBAL_COUPLING:
            self._append_variable_issue_list(
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
                lines,
                SECTION_TITLES[IssueKind.NAME_COLLISION],
                self.name_collisions,
            )
            return
        if kind is IssueKind.SHADOWING:
            self._append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.SHADOWING],
                self.shadowing,
            )
            return
        if kind is IssueKind.RESET_CONTAMINATION:
            self._append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.RESET_CONTAMINATION],
                self.reset_contamination,
            )
            return
        if kind is IssueKind.IMPLICIT_LATCH:
            self._append_variable_issue_list(
                lines,
                SECTION_TITLES[IssueKind.IMPLICIT_LATCH],
                self.implicit_latches,
            )
            return

    def summary(self) -> str:
        summary_kinds = self._summary_kinds()
        if not self.issues and not summary_kinds:
            lines = format_report_header("Variable issues", self.basepicture_name, status="ok")
            lines.append("No issues found.")
            return "\n".join(lines)

        status = "issues" if self.issues else "ok"
        lines = format_report_header("Variable issues", self.basepicture_name, status=status)
        lines.append(f"Issues: {len(self.issues)}")
        if summary_kinds:
            lines.append("Sections:")
            lines.extend(self._section_counts(summary_kinds))
        for kind in summary_kinds:
            lines.append("")
            self._append_section(lines, kind)
        return "\n".join(lines)
