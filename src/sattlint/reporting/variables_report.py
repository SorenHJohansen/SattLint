from __future__ import annotations

from dataclasses import dataclass, field

from ..analyzers.framework.issue import Findings
from ..models._variable_issues import IssueKind, VariableIssue
from ..resolution.access_graph import AccessEvent
from ..resolution.paths import CanonicalPathKey
from ._variables_report_rendering import (
    append_datatype_duplication,
    append_magic_numbers,
    append_min_max_mapping_mismatch,
    append_record_component_order_dependence,
    append_string_mapping_mismatch,
    append_unused_datatype_fields,
    append_unused_variable_issue_list,
    append_variable_issue_list,
    count_string_mapping_mismatch_rows,
)

DEFAULT_VARIABLE_ANALYSIS_KINDS: tuple[IssueKind, ...] = (
    IssueKind.UNUSED,
    IssueKind.UNUSED_DATATYPE_FIELD,
    IssueKind.FIELD_READ_ONLY,
    IssueKind.READ_ONLY_NON_CONST,
    IssueKind.FIELD_NEVER_READ,
    IssueKind.NEVER_READ,
    IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE,
    IssueKind.LAYOUT_OVERLAP,
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

AccessesByDefinitionKey = dict[CanonicalPathKey, tuple[AccessEvent, ...]]
EffectFlowEdges = dict[CanonicalPathKey, tuple[CanonicalPathKey, ...]]
EffectFlowDisplayNames = dict[CanonicalPathKey, str]


def _accesses_by_definition_key_factory() -> AccessesByDefinitionKey:
    return {}


def _effect_flow_edges_factory() -> EffectFlowEdges:
    return {}


def _effect_flow_display_names_factory() -> EffectFlowDisplayNames:
    return {}


def _phase_timings_factory() -> list[dict[str, str | float]]:
    return []


SECTION_TITLES: dict[IssueKind, str] = {
    IssueKind.UNUSED: "Unused variables",
    IssueKind.UNUSED_DATATYPE_FIELD: "Unused fields in datatypes",
    IssueKind.FIELD_READ_ONLY: "Read-only fields",
    IssueKind.READ_ONLY_NON_CONST: "Read-only but not Const variables",
    IssueKind.NAMING_ROLE_MISMATCH: "Naming-to-behavior mismatches",
    IssueKind.UI_ONLY: "UI/display-only variables",
    IssueKind.PROCEDURE_STATUS: "Procedure status handling",
    IssueKind.FIELD_NEVER_READ: "Written but never read fields",
    IssueKind.NEVER_READ: "Written but never read variables",
    IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE: "Sorting-sensitive datatypes",
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

_UNUSED_VARIABLE_SECTION_KINDS: frozenset[IssueKind] = frozenset(
    {
        IssueKind.UNUSED,
        IssueKind.FIELD_NEVER_READ,
        IssueKind.NEVER_READ,
    }
)

_VARIABLE_ISSUE_LIST_SECTION_KINDS: frozenset[IssueKind] = frozenset(
    {
        IssueKind.FIELD_READ_ONLY,
        IssueKind.READ_ONLY_NON_CONST,
        IssueKind.NAMING_ROLE_MISMATCH,
        IssueKind.UI_ONLY,
        IssueKind.PROCEDURE_STATUS,
        IssueKind.WRITE_WITHOUT_EFFECT,
        IssueKind.GLOBAL_SCOPE_MINIMIZATION,
        IssueKind.HIDDEN_GLOBAL_COUPLING,
        IssueKind.HIGH_FAN_IN_OUT,
        IssueKind.UNKNOWN_PARAMETER_TARGET,
        IssueKind.REQUIRED_PARAMETER_CONNECTION,
        IssueKind.CONTRACT_MISMATCH,
        IssueKind.NAME_COLLISION,
        IssueKind.LAYOUT_OVERLAP,
        IssueKind.SHADOWING,
        IssueKind.RESET_CONTAMINATION,
        IssueKind.IMPLICIT_LATCH,
    }
)


@dataclass
class VariablesReport:
    basepicture_name: str
    issues: Findings[VariableIssue]
    accesses_by_definition_key: AccessesByDefinitionKey = field(default_factory=_accesses_by_definition_key_factory)
    effect_flow_edges: EffectFlowEdges = field(default_factory=_effect_flow_edges_factory)
    effect_flow_display_names: EffectFlowDisplayNames = field(default_factory=_effect_flow_display_names_factory)
    visible_kinds: frozenset[IssueKind] | set[IssueKind] | tuple[IssueKind, ...] | list[IssueKind] | None = None
    selected_issue_kinds: frozenset[IssueKind] | set[IssueKind] | tuple[IssueKind, ...] | list[IssueKind] | None = None
    include_empty_sections: bool = False
    analyzed_version: str | None = None
    last_changed: str | None = None
    phase_timings: list[dict[str, str | float]] = field(default_factory=_phase_timings_factory)

    def __post_init__(self) -> None:
        if self.visible_kinds is not None and not isinstance(self.visible_kinds, frozenset):
            self.visible_kinds = frozenset(self.visible_kinds)
        if self.selected_issue_kinds is not None and not isinstance(self.selected_issue_kinds, frozenset):
            self.selected_issue_kinds = frozenset(self.selected_issue_kinds)

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
    def field_read_only(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.FIELD_READ_ONLY]

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
    def field_never_read(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.FIELD_NEVER_READ]

    @property
    def never_read(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.NEVER_READ]

    @property
    def record_component_order_dependence(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE]

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
        return tuple(kind for kind in SUMMARY_SECTION_ORDER if kind in {issue.kind for issue in self.issues})

    def _ordered_selected_issue_kinds(self) -> tuple[IssueKind, ...]:
        if not self.selected_issue_kinds:
            return ()
        return tuple(kind for kind in SUMMARY_SECTION_ORDER if kind in self.selected_issue_kinds)

    def _selected_issue_kinds_line(self) -> str | None:
        selected_kinds = self._ordered_selected_issue_kinds()
        if not selected_kinds:
            return None
        return f"Selected issue kinds: {', '.join(kind.value for kind in selected_kinds)}"

    def _selected_no_issues_message(self) -> str:
        selected_kinds = self._ordered_selected_issue_kinds()
        if len(selected_kinds) == 1:
            return f"No {SECTION_TITLES[selected_kinds[0]].lower()} found."
        if selected_kinds:
            joined = ", ".join(kind.value for kind in selected_kinds)
            return f"No issues found for selected issue kinds: {joined}."
        return "No issues found."

    def _issues_for_kind(self, kind: IssueKind) -> list[VariableIssue]:
        if kind is IssueKind.UNUSED:
            return self.unused
        if kind is IssueKind.UNUSED_DATATYPE_FIELD:
            return self.unused_datatype_fields
        if kind is IssueKind.FIELD_READ_ONLY:
            return self.field_read_only
        if kind is IssueKind.READ_ONLY_NON_CONST:
            return self.read_only_non_const
        if kind is IssueKind.NAMING_ROLE_MISMATCH:
            return self.naming_role_mismatch
        if kind is IssueKind.UI_ONLY:
            return self.ui_only
        if kind is IssueKind.PROCEDURE_STATUS:
            return self.procedure_status
        if kind is IssueKind.FIELD_NEVER_READ:
            return self.field_never_read
        if kind is IssueKind.NEVER_READ:
            return self.never_read
        if kind is IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE:
            return self.record_component_order_dependence
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

    def _append_section(self, lines: list[str], kind: IssueKind) -> None:
        title = SECTION_TITLES[kind]
        issues = self._issues_for_kind(kind)
        if kind in _UNUSED_VARIABLE_SECTION_KINDS:
            append_unused_variable_issue_list(lines, title, issues)
            return
        if kind is IssueKind.UNUSED_DATATYPE_FIELD:
            append_unused_datatype_fields(lines, title, issues)
            return
        if kind in _VARIABLE_ISSUE_LIST_SECTION_KINDS:
            append_variable_issue_list(lines, title, issues)
            return
        if kind is IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE:
            append_record_component_order_dependence(lines, title, issues)
            return
        if kind is IssueKind.STRING_MAPPING_MISMATCH:
            append_string_mapping_mismatch(lines, title, issues)
            return
        if kind is IssueKind.DATATYPE_DUPLICATION:
            append_datatype_duplication(lines, title, issues)
            return
        if kind is IssueKind.MIN_MAX_MAPPING_MISMATCH:
            append_min_max_mapping_mismatch(lines, title, issues)
            return
        if kind is IssueKind.MAGIC_NUMBER:
            append_magic_numbers(lines, title, issues)
            return

    def _display_issue_count(self, kind: IssueKind) -> int:
        issues = self._issues_for_kind(kind)
        if kind is IssueKind.STRING_MAPPING_MISMATCH:
            return count_string_mapping_mismatch_rows(issues)
        return len(issues)

    def _display_total_issue_count(self, summary_kinds: tuple[IssueKind, ...]) -> int:
        if summary_kinds:
            return sum(self._display_issue_count(kind) for kind in summary_kinds)
        return len(self.issues)

    def summary(self) -> str:
        summary_kinds = self._summary_kinds()
        selected_issue_kinds_line = self._selected_issue_kinds_line()
        if not self.issues and not summary_kinds:
            lines = [
                "Report: Variable issues",
                f"Target: {self.basepicture_name}",
            ]
            if self.analyzed_version is not None:
                lines.append(f"Version: {self.analyzed_version}")
            if self.last_changed is not None:
                lines.append(f"Last changed: {self.last_changed}")
            if selected_issue_kinds_line is not None:
                lines.append(selected_issue_kinds_line)
            lines.extend(
                [
                    "Status: ok",
                ]
            )
            lines.append(
                self._selected_no_issues_message() if self.selected_issue_kinds is not None else "No issues found."
            )
            return "\n".join(lines)

        status = "issues" if self.issues else "ok"
        lines = [
            "Report: Variable issues",
            f"Target: {self.basepicture_name}",
        ]
        if self.analyzed_version is not None:
            lines.append(f"Version: {self.analyzed_version}")
        if self.last_changed is not None:
            lines.append(f"Last changed: {self.last_changed}")
        if selected_issue_kinds_line is not None:
            lines.append(selected_issue_kinds_line)
        lines.append(f"Status: {status}")
        lines.append(f"Issues: {self._display_total_issue_count(summary_kinds)}")
        show_sections_overview = len(summary_kinds) > 1 or (self.visible_kinds is None and bool(summary_kinds))
        if show_sections_overview:
            lines.append("Sections:")
            lines.extend(f"  - {SECTION_TITLES[kind]}: {self._display_issue_count(kind)}" for kind in summary_kinds)
        for kind in summary_kinds:
            lines.append("")
            self._append_section(lines, kind)
        if not self.issues and self.selected_issue_kinds is not None:
            lines.append("")
            lines.append(self._selected_no_issues_message())
        return "\n".join(lines)
