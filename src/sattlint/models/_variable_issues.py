"""Pure model types for variable analysis issues."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sattline_parser.models.ast_model import Simple_DataType, SourceSpan, Variable

from ..types import VariableId

__all__ = ["IssueKind", "VariableIssue"]


class IssueKind(Enum):
    UNUSED = "unused"
    UNUSED_DATATYPE_FIELD = "unused_datatype_field"
    READ_ONLY_NON_CONST = "read_only_non_const"
    NAMING_ROLE_MISMATCH = "naming_role_mismatch"
    UI_ONLY = "ui_only"
    PROCEDURE_STATUS = "procedure_status"
    NEVER_READ = "never_read"
    RECORD_COMPONENT_ORDER_DEPENDENCE = "record_component_order_dependence"
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


@dataclass
class VariableIssue:
    kind: IssueKind
    module_path: list[str]
    variable: Variable | None
    datatype_name: str | None = None
    role: str | None = None
    source_variable: Variable | None = None
    duplicate_count: int | None = None
    duplicate_locations: list[tuple[list[str], str, VariableId]] | None = None
    literal_value: int | float | None = None
    literal_span: SourceSpan | None = None
    site: str | None = None
    field_path: str | None = None
    sequence_name: str | None = None
    reset_variable: VariableId | None = None
    source_decl_module_path: list[str] | None = None
    source_role: str | None = None
    source_display_name: str | None = None
    target_display_name: str | None = None

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
