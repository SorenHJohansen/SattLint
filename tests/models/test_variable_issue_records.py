"""Payload-shape and narrowing contracts for the variable issue records."""

from __future__ import annotations

import dataclasses

from sattline_parser.models.ast_model import ScalarDatatype, SourceSpan, Variable

from sattlint.models._variable_issues import (
    DatatypeDuplicationIssue,
    DuplicateLocation,
    FieldNeverReadIssue,
    FieldReadOnlyIssue,
    GlobalScopeMinimizationIssue,
    HiddenGlobalCouplingIssue,
    HighFanInOutIssue,
    ImplicitLatchIssue,
    IssueKind,
    MagicNumberIssue,
    MinMaxMappingMismatchIssue,
    NeverReadIssue,
    ProcedureStatusIssue,
    ReadBeforeWriteIssue,
    ReadOnlyNonConstIssue,
    RecordComponentOrderIssue,
    ResetContaminationIssue,
    SecureCandidateIssue,
    ShadowingIssue,
    StringMappingMismatchIssue,
    UnknownParameterTargetIssue,
    UnsafeBooleanDefaultIssue,
    UnusedDatatypeFieldIssue,
    UnusedDatatypeIssue,
    UnusedIssue,
    VariableIssue,
    VariableIssueBase,
    WriteWithoutEffectIssue,
)
from sattlint.types import VariableId

_RECORD_TYPES: tuple[type[VariableIssueBase], ...] = (
    UnusedIssue,
    UnusedDatatypeIssue,
    UnusedDatatypeFieldIssue,
    FieldReadOnlyIssue,
    ReadOnlyNonConstIssue,
    ProcedureStatusIssue,
    FieldNeverReadIssue,
    NeverReadIssue,
    RecordComponentOrderIssue,
    WriteWithoutEffectIssue,
    GlobalScopeMinimizationIssue,
    HiddenGlobalCouplingIssue,
    HighFanInOutIssue,
    UnknownParameterTargetIssue,
    StringMappingMismatchIssue,
    DatatypeDuplicationIssue,
    MinMaxMappingMismatchIssue,
    MagicNumberIssue,
    ShadowingIssue,
    UnsafeBooleanDefaultIssue,
    ReadBeforeWriteIssue,
    ResetContaminationIssue,
    ImplicitLatchIssue,
    SecureCandidateIssue,
)


def _variable(name: str = "Value") -> Variable:
    return Variable(name=name, datatype=ScalarDatatype.INTEGER)


def test_every_issue_kind_has_exactly_one_record_type() -> None:
    assert {record_type.kind for record_type in _RECORD_TYPES} == set(IssueKind)
    assert len(_RECORD_TYPES) == len(IssueKind)


def test_variable_only_records_share_one_payload_shape() -> None:
    variable = _variable()
    issues: list[VariableIssue] = [
        UnusedIssue(module_path=["Root"], variable=variable, role="localvariable"),
        ReadOnlyNonConstIssue(module_path=["Root"], variable=variable, role="localvariable"),
        NeverReadIssue(module_path=["Root"], variable=variable, role="localvariable"),
        WriteWithoutEffectIssue(module_path=["Root"], variable=variable, role="localvariable"),
        GlobalScopeMinimizationIssue(module_path=["Root"], variable=variable),
        HiddenGlobalCouplingIssue(module_path=["Root"], variable=variable),
        HighFanInOutIssue(module_path=["Root"], variable=variable),
    ]

    assert [issue.kind for issue in issues] == [
        IssueKind.UNUSED,
        IssueKind.READ_ONLY_NON_CONST,
        IssueKind.NEVER_READ,
        IssueKind.WRITE_WITHOUT_EFFECT,
        IssueKind.GLOBAL_SCOPE_MINIMIZATION,
        IssueKind.HIDDEN_GLOBAL_COUPLING,
        IssueKind.HIGH_FAN_IN_OUT,
    ]
    assert str(issues[0]) == "[Root] localvariable  'Value' (integer)"


def test_field_records_carry_a_field_path() -> None:
    variable = _variable("Payload")
    issues: list[VariableIssue] = [
        FieldReadOnlyIssue(module_path=["Root"], variable=variable, role="localvariable", field_path="Std"),
        FieldNeverReadIssue(module_path=["Root"], variable=variable, role="localvariable", field_path="Std"),
        ProcedureStatusIssue(module_path=["Root"], variable=variable, field_path=None),
        RecordComponentOrderIssue(
            module_path=["Root"],
            variable=variable,
            datatype_name="Payload",
            field_path="Std",
            site="EquationBlock",
        ),
        ResetContaminationIssue(
            module_path=["Root"],
            variable=variable,
            field_path="Std",
            sequence_name="SeqA",
            reset_variable=VariableId("ResetCmd"),
        ),
        ImplicitLatchIssue(
            module_path=["Root"],
            variable=variable,
            field_path="Std",
            sequence_name="SeqA",
            site="SEQ:SeqA > STEP:One",
        ),
    ]

    assert str(issues[0]) == "[Root] localvariable  'Payload'.Std (integer)"
    assert str(issues[4]) == "[Root] None  'Payload'.Std (integer) seq='SeqA' reset='ResetCmd'"
    assert str(issues[5]) == "[Root] None  'Payload'.Std (integer) seq='SeqA'"


def test_datatype_records_carry_a_datatype_name() -> None:
    unused = UnusedDatatypeIssue(module_path=["Root"], datatype_name="Payload", role="datatype")
    unused_field = UnusedDatatypeFieldIssue(
        module_path=["Root"],
        datatype_name="Payload",
        field_path="Value",
        role="datatype field",
    )

    assert str(unused) == "[Root] datatype 'Payload'"
    assert str(unused_field) == "[Root] datatype 'Payload'.Value"


def test_standalone_records_carry_their_own_payload() -> None:
    magic = MagicNumberIssue(
        module_path=["Root"],
        literal_value=42,
        literal_span=SourceSpan(start=0, end=0, line=9, column=4),
        site="EquationBlock",
        context="42",
        role="literal",
    )
    read_before_write = ReadBeforeWriteIssue(
        module_path=["Root"],
        role="Value is read before any write in STEP:One",
        site="STEP:One",
        context="Value",
    )
    unknown_target = UnknownParameterTargetIssue(module_path=["Root"], role="missing target")

    assert str(magic) == "[Root] magic number 42"
    assert magic.literal_span is not None
    assert str(read_before_write) == "[Root] Value is read before any write in STEP:One"
    assert str(unknown_target) == "[Root] missing target"


def test_mapping_records_carry_the_related_variable() -> None:
    string_issue = StringMappingMismatchIssue(
        module_path=["Root"],
        variable=_variable("Target"),
        source_variable=_variable("Source"),
        role="parameter mapping type mismatch",
        context="Target => Source",
    )
    min_max_issue = MinMaxMappingMismatchIssue(
        module_path=["Root"],
        variable=_variable("TargetMax"),
        source_variable=_variable("SourceMin"),
    )
    shadowing_issue = ShadowingIssue(
        module_path=["Root", "Child"],
        variable=_variable("Mode"),
        source_variable=_variable("Mode"),
        role="shadows outer",
    )

    assert string_issue.source_variable is not None
    assert min_max_issue.source_variable is not None
    assert shadowing_issue.source_variable is not None


def test_duplication_record_carries_duplicate_locations() -> None:
    issue = DatatypeDuplicationIssue(
        module_path=["Root", "Panel"],
        variable=_variable("Left"),
        duplicate_count=2,
        duplicate_locations=[
            DuplicateLocation(
                module_path=["Root", "Panel"],
                role="localvariable",
                variable_id=VariableId("Right"),
            )
        ],
    )

    assert issue.duplicate_count == 2
    assert issue.duplicate_locations[0].variable_id == "Right"


def test_unsafe_boolean_record_carries_its_site_and_context() -> None:
    issue = UnsafeBooleanDefaultIssue(
        module_path=["Root"],
        variable=_variable("Enable"),
        role="defaults to True, which can activate equipment from startup",
        site="Root.Child",
        context="Enable = TRUE",
    )

    assert issue.site == "Root.Child"
    assert issue.context == "Enable = TRUE"


def _field_names(record_type: type[VariableIssueBase]) -> set[str]:
    return {field.name for field in dataclasses.fields(record_type)}


def test_a_record_exposes_only_payload_fields_owned_by_its_kind() -> None:
    assert _field_names(UnusedIssue) == {"module_path", "role", "declaration_role", "variable"}
    assert _field_names(FieldReadOnlyIssue) == {
        "module_path",
        "role",
        "declaration_role",
        "variable",
        "field_path",
    }
    assert _field_names(UnusedDatatypeFieldIssue) == {
        "module_path",
        "role",
        "declaration_role",
        "datatype_name",
        "field_path",
    }
    assert "literal_value" in _field_names(MagicNumberIssue)
    assert "literal_value" not in _field_names(UnusedIssue)
    assert "reset_variable" not in _field_names(ImplicitLatchIssue)
    assert "reset_variable" in _field_names(ResetContaminationIssue)

    assert not hasattr(UnusedIssue(module_path=["Root"], variable=_variable()), "literal_value")
    assert not hasattr(
        ImplicitLatchIssue(module_path=["Root"], variable=_variable(), site="SEQ:SeqA > STEP:One"),
        "reset_variable",
    )
