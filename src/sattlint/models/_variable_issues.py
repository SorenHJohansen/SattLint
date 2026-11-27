"""Pure model types for variable analysis issues."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Literal

from sattlint.parser_api import ScalarDatatype, SourceSpan, Variable

from ..types import VariableId

type DeclarationRole = Literal["localvariable", "moduleparameter"]

DECLARATION_ROLE_LOCAL_VARIABLE: DeclarationRole = "localvariable"
DECLARATION_ROLE_MODULE_PARAMETER: DeclarationRole = "moduleparameter"

__all__ = [
    "DECLARATION_ROLE_LOCAL_VARIABLE",
    "DECLARATION_ROLE_MODULE_PARAMETER",
    "DatatypeDuplicationIssue",
    "DatatypeIssue",
    "DeclarationRole",
    "DuplicateLocation",
    "FieldNeverReadIssue",
    "FieldPathVariableIssue",
    "FieldReadOnlyIssue",
    "GlobalScopeMinimizationIssue",
    "HiddenGlobalCouplingIssue",
    "HighFanInOutIssue",
    "ImplicitLatchIssue",
    "IssueKind",
    "MagicNumberIssue",
    "MinMaxMappingMismatchIssue",
    "NestedRecordCandidateIssue",
    "NeverReadIssue",
    "ProcedureStatusIssue",
    "ReadBeforeWriteIssue",
    "ReadOnlyNonConstIssue",
    "RecordComponentOrderIssue",
    "RelatedVariableIssue",
    "ResetContaminationIssue",
    "SecureCandidateIssue",
    "ShadowingIssue",
    "StringMappingMismatchIssue",
    "UnknownParameterTargetIssue",
    "UnsafeBooleanDefaultIssue",
    "UnusedDatatypeFieldIssue",
    "UnusedDatatypeIssue",
    "UnusedIssue",
    "VariableIssue",
    "VariableIssueBase",
    "VariableIssueMetadata",
    "VariableTargetIssue",
    "WriteWithoutEffectIssue",
    "variable_issue_metadata",
]


class IssueKind(Enum):
    UNUSED = "unused"
    UNUSED_DATATYPE = "unused_datatype"
    UNUSED_DATATYPE_FIELD = "unused_datatype_field"
    FIELD_READ_ONLY = "field_read_only"
    READ_ONLY_NON_CONST = "read_only_non_const"
    PROCEDURE_STATUS = "procedure_status"
    FIELD_NEVER_READ = "field_never_read"
    NEVER_READ = "never_read"
    RECORD_COMPONENT_ORDER_DEPENDENCE = "record_component_order_dependence"
    WRITE_WITHOUT_EFFECT = "write_without_effect"
    GLOBAL_SCOPE_MINIMIZATION = "global_scope_minimization"
    HIDDEN_GLOBAL_COUPLING = "hidden_global_coupling"
    HIGH_FAN_IN_OUT = "high_fan_in_out"
    UNKNOWN_PARAMETER_TARGET = "unknown_parameter_target"
    STRING_MAPPING_MISMATCH = "string_mapping_mismatch"
    DATATYPE_DUPLICATION = "datatype_duplication"
    MIN_MAX_MAPPING_MISMATCH = "min_max_mapping_mismatch"
    MAGIC_NUMBER = "magic_number"
    SHADOWING = "shadowing"
    UNSAFE_BOOLEAN_DEFAULT = "unsafe_boolean_default"
    READ_BEFORE_WRITE = "read_before_write"
    RESET_CONTAMINATION = "reset_contamination"
    IMPLICIT_LATCH = "implicit_latch"
    SECURE_CANDIDATE = "secure_candidate"


@dataclass(frozen=True, slots=True)
class VariableIssueMetadata:
    explanation: str | None = None
    suggestion: str | None = None


_DEFAULT_VARIABLE_ISSUE_METADATA = VariableIssueMetadata()


_VARIABLE_ISSUE_METADATA: dict[IssueKind, VariableIssueMetadata] = {
    IssueKind.UNUSED: VariableIssueMetadata(
        explanation="Stale declarations add noise and make it harder to tell which signals still matter.",
        suggestion="Delete the declaration, or add the missing read/write path if it is still part of the design.",
    ),
    IssueKind.UNUSED_DATATYPE: VariableIssueMetadata(
        explanation=(
            "No loaded unit declares or uses this datatype, so it is either dead "
            "or part of an interface consumed outside the scanned workspace."
        ),
        suggestion=(
            "Add the missing declaration that should use it, or remove the definition "
            "once no consumer in the scanned workspace needs it."
        ),
    ),
    IssueKind.UNUSED_DATATYPE_FIELD: VariableIssueMetadata(
        explanation=(
            "No loaded unit reads or writes this field, so it is either dead or part "
            "of an interface consumed outside the scanned workspace."
        ),
        suggestion=(
            "Add the missing read/write path that should use it, or remove the field "
            "once no consumer in the scanned workspace needs it."
        ),
    ),
    IssueKind.FIELD_READ_ONLY: VariableIssueMetadata(
        explanation="A record field that is only read often points at a sibling-mapping mistake or a missing write path.",
        suggestion="Reconnect the field to the writer that should update it, or remove the dead read path if the field is obsolete.",
    ),
    IssueKind.READ_ONLY_NON_CONST: VariableIssueMetadata(
        explanation="A writable declaration that is only read obscures intent and weakens constant-safety checks.",
        suggestion="Mark the declaration CONST, or add the write path that is supposed to update it.",
    ),
    IssueKind.PROCEDURE_STATUS: VariableIssueMetadata(
        explanation="Procedure status channels are intended to drive control decisions, retries, or escalation paths rather than disappearing into dead storage or UI-only state.",
        suggestion="Read the status in control logic or propagate it to the caller that owns the error path, or remove the unused status output if the contract does not require it.",
    ),
    IssueKind.FIELD_NEVER_READ: VariableIssueMetadata(
        explanation="A record field that is only written is usually dead logic or a sign that the read side is connected to the wrong sibling field.",
        suggestion="Reconnect the consuming read to this field, or remove the dead write if nothing should observe it.",
    ),
    IssueKind.NEVER_READ: VariableIssueMetadata(
        explanation="Writes that are never observed usually mean dead logic or a missing connection to the real output path.",
        suggestion="Remove the dead write, or connect the variable to the code, parameter mapping, or output that should consume it.",
    ),
    IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE: VariableIssueMetadata(
        explanation="These builtins make record field declaration order part of the runtime contract, so reordering datatype fields can silently read from or write to a different field.",
        suggestion="Replace ordinal record-component access with named-field logic, or document and isolate the order-dependent contract if it cannot be removed.",
    ),
    IssueKind.WRITE_WITHOUT_EFFECT: VariableIssueMetadata(
        explanation="The value changes internally but never escapes to a root-visible output or module contract.",
        suggestion="Map the value to an output or parent parameter, or remove the intermediate write chain if it is dead logic.",
    ),
    IssueKind.GLOBAL_SCOPE_MINIMIZATION: VariableIssueMetadata(
        explanation="A root global that is only accessed inside one module subtree widens scope unnecessarily and makes the real owning scope less explicit.",
        suggestion="Move the declaration into the narrowest owning module or moduletype scope, and only expose it upward through explicit parameter mappings when needed.",
    ),
    IssueKind.HIDDEN_GLOBAL_COUPLING: VariableIssueMetadata(
        explanation="When multiple modules share a root global directly, the dependency bypasses the explicit parameter contract and becomes harder to trace safely.",
        suggestion="Replace the shared global access with explicit parameter mappings or local coordination state so the interface stays visible in the module wiring.",
    ),
    IssueKind.HIGH_FAN_IN_OUT: VariableIssueMetadata(
        explanation="Signals with many readers or writers become coordination hubs that are harder to reason about and easier to break accidentally.",
        suggestion="Split separate responsibilities into narrower signals, or introduce explicit interface boundaries around the shared state.",
    ),
    IssueKind.UNKNOWN_PARAMETER_TARGET: VariableIssueMetadata(
        explanation="A mapping that points at a parameter name the target module does not declare leaves the intended interface unresolved.",
        suggestion="Fix the target parameter name, or update the moduletype so the declared contract matches the mapping.",
    ),
    IssueKind.STRING_MAPPING_MISMATCH: VariableIssueMetadata(
        explanation="Mismatched string-like datatypes can truncate values or break parameter expectations between modules.",
        suggestion="Use matching string datatypes on both sides of the mapping, or change the contract to the correct string type.",
    ),
    IssueKind.DATATYPE_DUPLICATION: VariableIssueMetadata(
        explanation="Repeated field groups and duplicate layouts are easy to let drift apart and make structural changes harder to maintain.",
        suggestion="Extract the shared field group into a named RECORD datatype and declare it as one field, or reuse the existing record definition.",
    ),
    IssueKind.MIN_MAX_MAPPING_MISMATCH: VariableIssueMetadata(
        explanation="Mismatched Min_/Max_ mappings suggest the parameter contract no longer describes the same base signal.",
        suggestion="Reconnect the matching Min_/Max_ pair, or rename the parameters so the pair lines up again.",
    ),
    IssueKind.MAGIC_NUMBER: VariableIssueMetadata(
        explanation="Unlabeled literals hide intent and make calibration or recipe changes harder to review safely.",
        suggestion="Extract the literal into a named constant, engineering parameter, or recipe parameter.",
    ),
    IssueKind.SHADOWING: VariableIssueMetadata(
        explanation="Shadowing hides which declaration is actually being referenced and increases the risk of accidental scope capture.",
        suggestion="Rename the inner declaration, or reference the intended outer symbol more explicitly.",
    ),
    IssueKind.UNSAFE_BOOLEAN_DEFAULT: VariableIssueMetadata(
        explanation="A boolean that enables logic or bypasses safeguards from startup can activate equipment without an explicit command.",
        suggestion="Default the flag to False and require an explicit operator or logic path to enable it.",
    ),
    IssueKind.READ_BEFORE_WRITE: VariableIssueMetadata(
        explanation="A local value consumed before any known write in the same scope can depend on undefined startup state or scan order.",
        suggestion="Initialize the value at declaration, or write it before the consuming read.",
    ),
    IssueKind.RESET_CONTAMINATION: VariableIssueMetadata(
        explanation="Partial reset handling can leave stale state behind when the sequence or step is expected to restart cleanly, or a persisted value can be cleared when it should survive.",
        suggestion="Write the reset value on every reset path, or centralize the reset assignment in the step or sequence cleanup path; leave OpSave values out of reset writes.",
    ),
    IssueKind.IMPLICIT_LATCH: VariableIssueMetadata(
        explanation="A one-sided TRUE assignment can leave a boolean latched longer than intended when the complementary path never clears it.",
        suggestion="Add the matching FALSE assignment in the ELSE, alternate branch, or step exit path, or document the intentional latch behavior.",
    ),
    IssueKind.SECURE_CANDIDATE: VariableIssueMetadata(
        explanation="The value is written during the sequence and then read by a transition. A controller restart before that transition fires would lose the value, so the process cannot resume from the same point.",
        suggestion="Review whether the declaration should be Secure so the value survives a controller restart.",
    ),
}


def variable_issue_metadata(kind: IssueKind | str | None) -> VariableIssueMetadata:
    """Metadata for an issue kind, or the empty default for an unknown one."""
    if isinstance(kind, str):
        try:
            kind = IssueKind(kind)
        except ValueError:
            return _DEFAULT_VARIABLE_ISSUE_METADATA
    if isinstance(kind, IssueKind):
        return _VARIABLE_ISSUE_METADATA.get(kind, _DEFAULT_VARIABLE_ISSUE_METADATA)
    return _DEFAULT_VARIABLE_ISSUE_METADATA


def _variable_issue_text(
    module_path: list[str],
    variable: Variable,
    role: str | None,
    *,
    field_path: str | None = None,
    sequence_name: str | None = None,
    reset_variable: VariableId | None = None,
) -> str:
    mp = ".".join(module_path)
    dt = variable.datatype.value if isinstance(variable.datatype, ScalarDatatype) else str(variable.datatype)
    role_txt = f"{role} "
    field_txt = f".{field_path}" if field_path else ""
    seq_txt = f" seq={sequence_name!r}" if sequence_name else ""
    reset_txt = f" reset={reset_variable!r}" if reset_variable else ""
    return f"[{mp}] {role_txt} {variable.name!r}{field_txt} ({dt}){seq_txt}{reset_txt}"


def _datatype_issue_text(module_path: list[str], datatype_name: str, field_path: str | None) -> str:
    mp = ".".join(module_path)
    field_txt = f".{field_path}" if field_path else ""
    return f"[{mp}] datatype {datatype_name!r}{field_txt}"


def _role_issue_text(module_path: list[str], role: str | None) -> str:
    mp = ".".join(module_path)
    return f"[{mp}] {role}" if role is not None else f"[{mp}]"


@dataclass(frozen=True, slots=True, kw_only=True)
class VariableIssueBase:
    """Fields shared by every variable issue record."""

    module_path: list[str]
    role: str | None = None
    declaration_role: DeclarationRole | None = None
    kind: ClassVar[IssueKind]

    def __str__(self) -> str:
        return f"[{'.'.join(self.module_path)}]"


@dataclass(frozen=True, slots=True, kw_only=True)
class VariableTargetIssue(VariableIssueBase):
    """An issue raised about a declared variable."""

    variable: Variable

    def __str__(self) -> str:
        return _variable_issue_text(self.module_path, self.variable, self.role)


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldPathVariableIssue(VariableTargetIssue):
    """A variable issue that can also name the record field it concerns."""

    field_path: str | None = None

    def __str__(self) -> str:
        return _variable_issue_text(self.module_path, self.variable, self.role, field_path=self.field_path)


@dataclass(frozen=True, slots=True, kw_only=True)
class RelatedVariableIssue(VariableTargetIssue):
    """A variable issue that also names the variable it relates to."""

    source_variable: Variable | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DatatypeIssue(VariableIssueBase):
    """An issue raised about a datatype declaration rather than a variable."""

    datatype_name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UnusedIssue(VariableTargetIssue):
    kind: ClassVar[Literal[IssueKind.UNUSED]] = IssueKind.UNUSED


@dataclass(frozen=True, slots=True, kw_only=True)
class UnusedDatatypeIssue(DatatypeIssue):
    kind: ClassVar[Literal[IssueKind.UNUSED_DATATYPE]] = IssueKind.UNUSED_DATATYPE

    def __str__(self) -> str:
        return _datatype_issue_text(self.module_path, self.datatype_name, None)


@dataclass(frozen=True, slots=True, kw_only=True)
class UnusedDatatypeFieldIssue(DatatypeIssue):
    kind: ClassVar[Literal[IssueKind.UNUSED_DATATYPE_FIELD]] = IssueKind.UNUSED_DATATYPE_FIELD
    field_path: str

    def __str__(self) -> str:
        return _datatype_issue_text(self.module_path, self.datatype_name, self.field_path)


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldReadOnlyIssue(FieldPathVariableIssue):
    kind: ClassVar[Literal[IssueKind.FIELD_READ_ONLY]] = IssueKind.FIELD_READ_ONLY


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadOnlyNonConstIssue(VariableTargetIssue):
    kind: ClassVar[Literal[IssueKind.READ_ONLY_NON_CONST]] = IssueKind.READ_ONLY_NON_CONST


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcedureStatusIssue(FieldPathVariableIssue):
    kind: ClassVar[Literal[IssueKind.PROCEDURE_STATUS]] = IssueKind.PROCEDURE_STATUS


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldNeverReadIssue(FieldPathVariableIssue):
    kind: ClassVar[Literal[IssueKind.FIELD_NEVER_READ]] = IssueKind.FIELD_NEVER_READ


@dataclass(frozen=True, slots=True, kw_only=True)
class NeverReadIssue(VariableTargetIssue):
    kind: ClassVar[Literal[IssueKind.NEVER_READ]] = IssueKind.NEVER_READ


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordComponentOrderIssue(FieldPathVariableIssue):
    kind: ClassVar[Literal[IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE]] = IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE
    datatype_name: str
    site: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class WriteWithoutEffectIssue(VariableTargetIssue):
    kind: ClassVar[Literal[IssueKind.WRITE_WITHOUT_EFFECT]] = IssueKind.WRITE_WITHOUT_EFFECT


@dataclass(frozen=True, slots=True, kw_only=True)
class GlobalScopeMinimizationIssue(VariableTargetIssue):
    kind: ClassVar[Literal[IssueKind.GLOBAL_SCOPE_MINIMIZATION]] = IssueKind.GLOBAL_SCOPE_MINIMIZATION


@dataclass(frozen=True, slots=True, kw_only=True)
class HiddenGlobalCouplingIssue(VariableTargetIssue):
    kind: ClassVar[Literal[IssueKind.HIDDEN_GLOBAL_COUPLING]] = IssueKind.HIDDEN_GLOBAL_COUPLING


@dataclass(frozen=True, slots=True, kw_only=True)
class HighFanInOutIssue(VariableTargetIssue):
    kind: ClassVar[Literal[IssueKind.HIGH_FAN_IN_OUT]] = IssueKind.HIGH_FAN_IN_OUT


@dataclass(frozen=True, slots=True, kw_only=True)
class UnknownParameterTargetIssue(VariableIssueBase):
    kind: ClassVar[Literal[IssueKind.UNKNOWN_PARAMETER_TARGET]] = IssueKind.UNKNOWN_PARAMETER_TARGET

    def __str__(self) -> str:
        return _role_issue_text(self.module_path, self.role)


@dataclass(frozen=True, slots=True, kw_only=True)
class StringMappingMismatchIssue(RelatedVariableIssue):
    kind: ClassVar[Literal[IssueKind.STRING_MAPPING_MISMATCH]] = IssueKind.STRING_MAPPING_MISMATCH
    context: str | None = None
    source_decl_module_path: list[str] | None = None
    source_role: str | None = None
    source_display_name: str | None = None
    target_display_name: str | None = None
    validation_source_variable: Variable | None = None
    validation_source_module_path: list[str] | None = None


@dataclass(frozen=True, slots=True)
class DuplicateLocation:
    """One additional declaration that repeats a complex datatype."""

    module_path: list[str]
    role: str
    variable_id: VariableId


@dataclass(frozen=True, slots=True, kw_only=True)
class DatatypeDuplicationIssue(VariableTargetIssue):
    kind: ClassVar[Literal[IssueKind.DATATYPE_DUPLICATION]] = IssueKind.DATATYPE_DUPLICATION
    duplicate_count: int
    duplicate_locations: list[DuplicateLocation]


@dataclass(frozen=True, slots=True, kw_only=True)
class NestedRecordCandidateIssue(VariableIssueBase):
    """A field group repeated by several records that can become a nested record."""

    kind: ClassVar[Literal[IssueKind.DATATYPE_DUPLICATION]] = IssueKind.DATATYPE_DUPLICATION
    field_names: tuple[str, ...]
    record_names: tuple[str, ...]

    def __str__(self) -> str:
        records = ", ".join(self.record_names)
        fields = ", ".join(repr(name) for name in self.field_names)
        return f"[{'.'.join(self.module_path)}] fields {fields} repeat in {records}; extract them into a nested record"


@dataclass(frozen=True, slots=True, kw_only=True)
class MinMaxMappingMismatchIssue(RelatedVariableIssue):
    kind: ClassVar[Literal[IssueKind.MIN_MAX_MAPPING_MISMATCH]] = IssueKind.MIN_MAX_MAPPING_MISMATCH


@dataclass(frozen=True, slots=True, kw_only=True)
class MagicNumberIssue(VariableIssueBase):
    kind: ClassVar[Literal[IssueKind.MAGIC_NUMBER]] = IssueKind.MAGIC_NUMBER
    literal_value: int | float
    literal_span: SourceSpan | None = None
    site: str | None = None
    context: str | None = None

    def __str__(self) -> str:
        return f"[{'.'.join(self.module_path)}] magic number {self.literal_value}"


@dataclass(frozen=True, slots=True, kw_only=True)
class ShadowingIssue(RelatedVariableIssue):
    kind: ClassVar[Literal[IssueKind.SHADOWING]] = IssueKind.SHADOWING


@dataclass(frozen=True, slots=True, kw_only=True)
class UnsafeBooleanDefaultIssue(VariableTargetIssue):
    kind: ClassVar[Literal[IssueKind.UNSAFE_BOOLEAN_DEFAULT]] = IssueKind.UNSAFE_BOOLEAN_DEFAULT
    site: str
    context: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadBeforeWriteIssue(VariableIssueBase):
    kind: ClassVar[Literal[IssueKind.READ_BEFORE_WRITE]] = IssueKind.READ_BEFORE_WRITE
    site: str
    context: str

    def __str__(self) -> str:
        return _role_issue_text(self.module_path, self.role)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResetContaminationIssue(FieldPathVariableIssue):
    kind: ClassVar[Literal[IssueKind.RESET_CONTAMINATION]] = IssueKind.RESET_CONTAMINATION
    sequence_name: str | None = None
    reset_variable: VariableId | None = None
    explanation: str | None = None
    suggestion: str | None = None

    def __str__(self) -> str:
        return _variable_issue_text(
            self.module_path,
            self.variable,
            self.role,
            field_path=self.field_path,
            sequence_name=self.sequence_name,
            reset_variable=self.reset_variable,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SecureCandidateIssue(FieldPathVariableIssue):
    kind: ClassVar[Literal[IssueKind.SECURE_CANDIDATE]] = IssueKind.SECURE_CANDIDATE
    site: str
    write_sites: tuple[str, ...] = ()
    transition_sites: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ImplicitLatchIssue(FieldPathVariableIssue):
    kind: ClassVar[Literal[IssueKind.IMPLICIT_LATCH]] = IssueKind.IMPLICIT_LATCH
    site: str
    sequence_name: str | None = None

    def __str__(self) -> str:
        return _variable_issue_text(
            self.module_path,
            self.variable,
            self.role,
            field_path=self.field_path,
            sequence_name=self.sequence_name,
        )


type VariableIssue = (
    UnusedIssue
    | UnusedDatatypeIssue
    | UnusedDatatypeFieldIssue
    | FieldReadOnlyIssue
    | ReadOnlyNonConstIssue
    | ProcedureStatusIssue
    | FieldNeverReadIssue
    | NeverReadIssue
    | RecordComponentOrderIssue
    | WriteWithoutEffectIssue
    | GlobalScopeMinimizationIssue
    | HiddenGlobalCouplingIssue
    | HighFanInOutIssue
    | UnknownParameterTargetIssue
    | StringMappingMismatchIssue
    | DatatypeDuplicationIssue
    | NestedRecordCandidateIssue
    | MinMaxMappingMismatchIssue
    | MagicNumberIssue
    | ShadowingIssue
    | UnsafeBooleanDefaultIssue
    | ReadBeforeWriteIssue
    | ResetContaminationIssue
    | ImplicitLatchIssue
    | SecureCandidateIssue
)
