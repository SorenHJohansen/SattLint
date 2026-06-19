"""Pure model types for variable analysis issues."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sattline_parser.models.ast_model import Simple_DataType, SourceSpan, Variable

from ..types import VariableId

__all__ = [
    "IssueKind",
    "VariableIssue",
    "VariableIssueMetadata",
    "materialize_variable_issue_metadata",
]


class IssueKind(Enum):
    UNUSED = "unused"
    UNUSED_DATATYPE_FIELD = "unused_datatype_field"
    FIELD_READ_ONLY = "field_read_only"
    READ_ONLY_NON_CONST = "read_only_non_const"
    NAMING_ROLE_MISMATCH = "naming_role_mismatch"
    UI_ONLY = "ui_only"
    PROCEDURE_STATUS = "procedure_status"
    FIELD_NEVER_READ = "field_never_read"
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


@dataclass(frozen=True, slots=True)
class VariableIssueMetadata:
    label: str
    explanation: str | None = None
    suggestion: str | None = None


_DEFAULT_VARIABLE_ISSUE_METADATA = VariableIssueMetadata(label="SattLint issue")


_VARIABLE_ISSUE_METADATA: dict[IssueKind, VariableIssueMetadata] = {
    IssueKind.UNUSED: VariableIssueMetadata(
        label="Unused variable",
        explanation="Stale declarations add noise and make it harder to tell which signals still matter.",
        suggestion="Delete the declaration, or add the missing read/write path if it is still part of the design.",
    ),
    IssueKind.UNUSED_DATATYPE_FIELD: VariableIssueMetadata(
        label="Unused datatype field",
        explanation="Unused fields make shared datatypes drift away from the actual interface the code relies on.",
        suggestion="Remove the field from the datatype, or add the missing read/write path that should use it.",
    ),
    IssueKind.FIELD_READ_ONLY: VariableIssueMetadata(
        label="Read-only field",
        explanation="A record field that is only read often points at a sibling-mapping mistake or a missing write path.",
        suggestion="Reconnect the field to the writer that should update it, or remove the dead read path if the field is obsolete.",
    ),
    IssueKind.READ_ONLY_NON_CONST: VariableIssueMetadata(
        label="Read-only variable should be CONST",
        explanation="A writable declaration that is only read obscures intent and weakens constant-safety checks.",
        suggestion="Mark the declaration CONST, or add the write path that is supposed to update it.",
    ),
    IssueKind.NAMING_ROLE_MISMATCH: VariableIssueMetadata(
        label="Naming-to-behavior mismatch",
        explanation="A name that suggests one role while the code uses the variable differently makes the control intent harder to trust.",
        suggestion="Rename the variable to match its real behavior, or change the implementation so it matches the intended role.",
    ),
    IssueKind.UI_ONLY: VariableIssueMetadata(
        label="Variable is only used by UI or display wiring",
        explanation="The variable is only consumed through graphics or interact display wiring, not through control logic or module contracts.",
        suggestion="Rename or document it as display-only state, or connect it to the control path that is expected to use it.",
    ),
    IssueKind.PROCEDURE_STATUS: VariableIssueMetadata(
        label="Procedure status output is not handled",
        explanation="Procedure status channels are intended to drive control decisions, retries, or escalation paths rather than disappearing into dead storage or UI-only state.",
        suggestion="Read the status in control logic or propagate it to the caller that owns the error path, or remove the unused status output if the contract does not require it.",
    ),
    IssueKind.FIELD_NEVER_READ: VariableIssueMetadata(
        label="Field is written but never read",
        explanation="A record field that is only written is usually dead logic or a sign that the read side is connected to the wrong sibling field.",
        suggestion="Reconnect the consuming read to this field, or remove the dead write if nothing should observe it.",
    ),
    IssueKind.NEVER_READ: VariableIssueMetadata(
        label="Variable is written but never read",
        explanation="Writes that are never observed usually mean dead logic or a missing connection to the real output path.",
        suggestion="Remove the dead write, or connect the variable to the code, parameter mapping, or output that should consume it.",
    ),
    IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE: VariableIssueMetadata(
        label="Positional record component access",
        explanation="These builtins make record field declaration order part of the runtime contract, so reordering datatype fields can silently read from or write to a different field.",
        suggestion="Replace ordinal record-component access with named-field logic, or document and isolate the order-dependent contract if it cannot be removed.",
    ),
    IssueKind.WRITE_WITHOUT_EFFECT: VariableIssueMetadata(
        label="Variable write has no observable output effect",
        explanation="The value changes internally but never escapes to a root-visible output or module contract.",
        suggestion="Map the value to an output or parent parameter, or remove the intermediate write chain if it is dead logic.",
    ),
    IssueKind.GLOBAL_SCOPE_MINIMIZATION: VariableIssueMetadata(
        label="Root global can be localized",
        explanation="A root global that is only accessed inside one module subtree widens scope unnecessarily and makes the real owning scope less explicit.",
        suggestion="Move the declaration into the narrowest owning module or moduletype scope, and only expose it upward through explicit parameter mappings when needed.",
    ),
    IssueKind.HIDDEN_GLOBAL_COUPLING: VariableIssueMetadata(
        label="Root global creates hidden coupling",
        explanation="When multiple modules share a root global directly, the dependency bypasses the explicit parameter contract and becomes harder to trace safely.",
        suggestion="Replace the shared global access with explicit parameter mappings or local coordination state so the interface stays visible in the module wiring.",
    ),
    IssueKind.HIGH_FAN_IN_OUT: VariableIssueMetadata(
        label="High fan-in or fan-out",
        explanation="Signals with many readers or writers become coordination hubs that are harder to reason about and easier to break accidentally.",
        suggestion="Split separate responsibilities into narrower signals, or introduce explicit interface boundaries around the shared state.",
    ),
    IssueKind.UNKNOWN_PARAMETER_TARGET: VariableIssueMetadata(
        label="Unknown parameter mapping target",
        explanation="A mapping that points at a parameter name the target module does not declare leaves the intended interface unresolved.",
        suggestion="Fix the target parameter name, or update the moduletype so the declared contract matches the mapping.",
    ),
    IssueKind.REQUIRED_PARAMETER_CONNECTION: VariableIssueMetadata(
        label="Required parameter connection missing",
        explanation="A parameter that the moduletype actively reads or writes is part of the module contract and should be wired explicitly by each instance.",
        suggestion="Add a parameter mapping for the required parameter, or make the parameter optional by removing the internal dependency on it.",
    ),
    IssueKind.CONTRACT_MISMATCH: VariableIssueMetadata(
        label="Cross-module contract mismatch",
        explanation="Incompatible parameter datatypes across module boundaries can break the interface contract or force unsafe coercions.",
        suggestion="Align the source and target datatypes, or insert an explicit compatible conversion before the mapping.",
    ),
    IssueKind.STRING_MAPPING_MISMATCH: VariableIssueMetadata(
        label="String mapping datatype mismatch",
        explanation="Mismatched string-like datatypes can truncate values or break parameter expectations between modules.",
        suggestion="Use matching string datatypes on both sides of the mapping, or change the contract to the correct string type.",
    ),
    IssueKind.DATATYPE_DUPLICATION: VariableIssueMetadata(
        label="Datatype duplication",
        explanation="Duplicate datatype layouts are easy to let drift apart and make structural changes harder to maintain.",
        suggestion="Promote the shared layout to one named RECORD datatype and reuse that definition.",
    ),
    IssueKind.NAME_COLLISION: VariableIssueMetadata(
        label="Name collision",
        explanation="Case-insensitive name collisions make the declaration set ambiguous and harder to reason about.",
        suggestion="Rename one of the declarations so the scope has a single canonical name for that concept.",
    ),
    IssueKind.LAYOUT_OVERLAP: VariableIssueMetadata(
        label="Layout elements overlap",
        explanation="Overlapping modules or UI elements make the layout ambiguous and often hide one control or display behind another.",
        suggestion="Move or resize one of the colliding elements so each rectangle occupies its own visible area.",
    ),
    IssueKind.MIN_MAX_MAPPING_MISMATCH: VariableIssueMetadata(
        label="Min/Max mapping name mismatch",
        explanation="Mismatched Min_/Max_ mappings suggest the parameter contract no longer describes the same base signal.",
        suggestion="Reconnect the matching Min_/Max_ pair, or rename the parameters so the pair lines up again.",
    ),
    IssueKind.MAGIC_NUMBER: VariableIssueMetadata(
        label="Magic number",
        explanation="Unlabeled literals hide intent and make calibration or recipe changes harder to review safely.",
        suggestion="Extract the literal into a named constant, engineering parameter, or recipe parameter.",
    ),
    IssueKind.SHADOWING: VariableIssueMetadata(
        label="Variable shadows outer scope",
        explanation="Shadowing hides which declaration is actually being referenced and increases the risk of accidental scope capture.",
        suggestion="Rename the inner declaration, or reference the intended outer symbol more explicitly.",
    ),
    IssueKind.RESET_CONTAMINATION: VariableIssueMetadata(
        label="Variable is contaminated across reset",
        explanation="Partial reset handling can leave stale state behind when the sequence or step is expected to restart cleanly.",
        suggestion="Write the reset value on every reset path, or centralize the reset assignment in the step or sequence cleanup path.",
    ),
    IssueKind.IMPLICIT_LATCH: VariableIssueMetadata(
        label="Boolean value may latch unexpectedly",
        explanation="A one-sided TRUE assignment can leave a boolean latched longer than intended when the complementary path never clears it.",
        suggestion="Add the matching FALSE assignment in the ELSE, alternate branch, or step exit path, or document the intentional latch behavior.",
    ),
}


def materialize_variable_issue_metadata(issue: object) -> VariableIssueMetadata:
    kind = getattr(issue, "kind", None)
    if isinstance(kind, IssueKind):
        return _VARIABLE_ISSUE_METADATA.get(kind, _DEFAULT_VARIABLE_ISSUE_METADATA)
    return _DEFAULT_VARIABLE_ISSUE_METADATA


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
    validation_source_variable: Variable | None = None
    validation_source_module_path: list[str] | None = None

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
