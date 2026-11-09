# pyright: reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportMissingTypeArgument=false
from __future__ import annotations

from typing import Any

import pytest
from sattline_parser.models.ast_model import (
    BasePicture,
    CodeItem,
    DataType,
    Equation,
    FrameModule,
    IntLiteral,
    ModuleCode,
    ModuleHeader,
    Sequence,
    SFCBodyItem,
    SFCCodeBlocks,
    SFCStep,
    SFCTransition,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import Assignment, FuncCall, FuncCallStmt, IfStmt, NotOp, VarRef

from sattlint.analyzers.dataflow import analyze_dataflow


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def _report(code: list[CodeItem], variables: tuple[str, ...] = ("X", "Y", "Cond")):
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name=name, datatype=Simple_DataType.INTEGER) for name in variables],
        modulecode=ModuleCode(
            sequences=[],
            equations=[Equation(name="Main", position=(0.0, 0.0), size=(1.0, 1.0), code=code)],
        ),
        moduledef=None,
    )
    return analyze_dataflow(bp)


def _record_report(code: list[CodeItem]):
    record_type = DataType(
        name="RecordType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="First", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Second", datatype=Simple_DataType.BOOLEAN),
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[record_type],
        localvariables=[
            Variable(name="Rec", datatype="RecordType"),
            Variable(name="Snapshot", datatype="RecordType"),
            Variable(name="Sink", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            sequences=[],
            equations=[Equation(name="Main", position=(0.0, 0.0), size=(1.0, 1.0), code=code)],
        ),
        moduledef=None,
    )
    return analyze_dataflow(bp)


def _conflicting_kinds(report: Any) -> set[str]:
    return {issue.kind for issue in report.issues if hasattr(issue, "kind")}


def test_conflicting_constants_fires_when_constant_read_in_between() -> None:
    report = _report(
        [
            Assignment(target=_varref("X"), value=IntLiteral(1)),
            Assignment(target=_varref("Y"), value=_varref("X")),
            Assignment(target=_varref("X"), value=IntLiteral(2)),
        ]
    )

    issues = [issue for issue in report.issues if issue.kind == "dataflow.conflicting_constants"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["symbol"] == "X"
    assert issues[0].data["previous_value"] == 1
    assert issues[0].data["value"] == 2


def test_conflicting_constants_ignores_reads_of_sibling_record_fields() -> None:
    report = _record_report(
        [
            Assignment(target=_varref("Rec.First"), value=True),
            Assignment(target=_varref("Sink"), value=_varref("Rec.Second")),
            Assignment(target=_varref("Rec.First"), value=False),
        ]
    )

    assert "dataflow.conflicting_constants" not in _conflicting_kinds(report)


def test_conflicting_constants_tracks_whole_record_reads_of_fields() -> None:
    report = _record_report(
        [
            Assignment(target=_varref("Rec.First"), value=True),
            Assignment(target=_varref("Snapshot"), value=_varref("Rec")),
            Assignment(target=_varref("Rec.First"), value=False),
        ]
    )

    assert "dataflow.conflicting_constants" in _conflicting_kinds(report)


def test_dead_overwrite_survives_sibling_record_field_reads() -> None:
    report = _record_report(
        [
            Assignment(target=_varref("Rec.First"), value=True),
            Assignment(target=_varref("Sink"), value=_varref("Rec.Second")),
            Assignment(target=_varref("Rec.First"), value=False),
        ]
    )

    issues = [issue for issue in report.issues if issue.kind == "dataflow.dead_overwrite"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["symbol"] == "Rec.First"


def test_dead_overwrite_is_consumed_by_whole_record_reads() -> None:
    report = _record_report(
        [
            Assignment(target=_varref("Rec.First"), value=True),
            Assignment(target=_varref("Snapshot"), value=_varref("Rec")),
            Assignment(target=_varref("Rec.First"), value=False),
        ]
    )

    assert "dataflow.dead_overwrite" not in _conflicting_kinds(report)


def test_conflicting_constants_does_not_fire_without_read_in_between() -> None:
    report = _report(
        [
            Assignment(target=_varref("X"), value=IntLiteral(1)),
            Assignment(target=_varref("X"), value=IntLiteral(2)),
        ]
    )

    assert "dataflow.conflicting_constants" not in _conflicting_kinds(report)
    assert "dataflow.dead_overwrite" in _conflicting_kinds(report)


@pytest.mark.parametrize("first, second, flagged", [(0, 0, False), (42, 42, False), (0, 1, True)])
def test_identical_known_writes_are_not_value_replacements(first: int, second: int, flagged: bool) -> None:
    report = _report(
        [
            Assignment(target=_varref("X"), value=IntLiteral(first)),
            Assignment(target=_varref("X"), value=IntLiteral(second)),
        ]
    )
    assert ("dataflow.dead_overwrite" in _conflicting_kinds(report)) is flagged


def test_unknown_replacement_still_reports_dead_overwrite() -> None:
    report = _report(
        [
            Assignment(target=_varref("X"), value=IntLiteral(0)),
            Assignment(target=_varref("X"), value=_varref("Cond")),
        ]
    )
    assert "dataflow.dead_overwrite" in _conflicting_kinds(report)


def test_identical_field_resets_are_not_value_replacements() -> None:
    report = _record_report(
        [
            Assignment(target=_varref("Rec.First"), value=False),
            Assignment(target=_varref("Rec.First"), value=False),
        ]
    )
    assert "dataflow.dead_overwrite" not in _conflicting_kinds(report)


def test_sibling_field_write_preserves_known_reset_value() -> None:
    report = _record_report(
        [
            Assignment(target=_varref("Rec.First"), value=False),
            Assignment(target=_varref("Rec.Second"), value=True),
            Assignment(target=_varref("Rec.First"), value=False),
        ]
    )
    assert "dataflow.dead_overwrite" not in _conflicting_kinds(report)


def test_whole_record_write_still_replaces_pending_field_value() -> None:
    report = _record_report(
        [
            Assignment(target=_varref("Rec.First"), value=False),
            Assignment(target=_varref("Rec"), value=_varref("Snapshot")),
        ]
    )
    assert "dataflow.dead_overwrite" in _conflicting_kinds(report)


def test_conditional_replacement_keeps_initial_default_live() -> None:
    report = _report(
        [
            Assignment(target=_varref("X"), value=IntLiteral(0)),
            IfStmt(
                branches=((_varref("Cond"), (Assignment(target=_varref("X"), value=IntLiteral(2)),)),),
                else_block=None,
            ),
            Assignment(target=_varref("Y"), value=_varref("X")),
        ]
    )

    assert "dataflow.dead_overwrite" not in _conflicting_kinds(report)


def test_conditional_branch_still_reports_its_own_dead_write() -> None:
    report = _report(
        [
            Assignment(target=_varref("X"), value=IntLiteral(0)),
            IfStmt(
                branches=(
                    (
                        _varref("Cond"),
                        (
                            Assignment(target=_varref("X"), value=IntLiteral(1)),
                            Assignment(target=_varref("X"), value=IntLiteral(2)),
                        ),
                    ),
                ),
                else_block=None,
            ),
        ]
    )

    issues = [issue for issue in report.issues if issue.kind == "dataflow.dead_overwrite"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert "IF:BRANCH:0" in str(issues[0].data["previous_sites"])


def test_sfc_enter_zero_reset_is_not_a_dead_overwrite() -> None:
    report = _sequence_report(
        [
            SFCStep(
                kind="step",
                name="CalculateAmounts",
                code=SFCCodeBlocks(
                    enter=[
                        Assignment(target=_varref("X"), value=IntLiteral(0)),
                        Assignment(target=_varref("X"), value=IntLiteral(2)),
                    ]
                ),
            )
        ]
    )

    assert "dataflow.dead_overwrite" not in _conflicting_kinds(report)


def test_sfc_enter_nonzero_overwrite_still_reports() -> None:
    report = _sequence_report(
        [
            SFCStep(
                kind="step",
                name="CalculateAmounts",
                code=SFCCodeBlocks(
                    enter=[
                        Assignment(target=_varref("X"), value=IntLiteral(1)),
                        Assignment(target=_varref("X"), value=IntLiteral(2)),
                    ]
                ),
            )
        ]
    )

    assert "dataflow.dead_overwrite" in _conflicting_kinds(report)


def test_equation_zero_overwrite_still_reports() -> None:
    report = _report(
        [
            Assignment(target=_varref("X"), value=IntLiteral(0)),
            Assignment(target=_varref("X"), value=IntLiteral(2)),
        ]
    )

    assert "dataflow.dead_overwrite" in _conflicting_kinds(report)


def test_guaranteed_branch_still_reports_dead_default() -> None:
    report = _report(
        [
            Assignment(target=_varref("X"), value=IntLiteral(0)),
            IfStmt(
                branches=((True, (Assignment(target=_varref("X"), value=IntLiteral(2)),)),),
                else_block=None,
            ),
        ]
    )

    assert "dataflow.dead_overwrite" in _conflicting_kinds(report)


def test_conflicting_constants_is_path_sensitive_for_branch_exclusive_writes() -> None:
    report = _report(
        [
            IfStmt(
                branches=((_varref("Cond"), (Assignment(target=_varref("X"), value=IntLiteral(1)),)),),
                else_block=(Assignment(target=_varref("X"), value=IntLiteral(2)),),
            )
        ]
    )

    assert "dataflow.conflicting_constants" not in _conflicting_kinds(report)


def test_conflicting_constants_does_not_fire_across_branch_then_reassignment() -> None:
    report = _report(
        [
            IfStmt(
                branches=((_varref("Cond"), (Assignment(target=_varref("X"), value=IntLiteral(1)),)),),
                else_block=(),
            ),
            Assignment(target=_varref("X"), value=IntLiteral(2)),
        ]
    )

    assert "dataflow.conflicting_constants" not in _conflicting_kinds(report)


def test_conflicting_constants_fires_after_read_in_branch_merge() -> None:
    report = _report(
        [
            Assignment(target=_varref("X"), value=IntLiteral(1)),
            Assignment(target=_varref("Y"), value=_varref("X")),
            IfStmt(
                branches=((_varref("Cond"), (Assignment(target=_varref("X"), value=IntLiteral(3)),)),),
                else_block=(),
            ),
            Assignment(target=_varref("X"), value=IntLiteral(4)),
        ]
    )

    assert "dataflow.conflicting_constants" in _conflicting_kinds(report)


def _sequence_report(nodes: list[SFCBodyItem]) -> Any:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="X", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Gate", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            sequences=[
                Sequence(
                    name="SeqMain",
                    type="sequence",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=nodes,
                )
            ],
            equations=[],
        ),
        moduledef=None,
    )
    return analyze_dataflow(bp)


def test_conflicting_constants_do_not_cross_sfc_steps() -> None:
    report = _sequence_report(
        [
            SFCStep(
                kind="step",
                name="First",
                code=SFCCodeBlocks(enter=[Assignment(target=_varref("X"), value=True)]),
            ),
            SFCTransition(name="Next", condition=True),
            SFCStep(
                kind="step",
                name="Second",
                code=SFCCodeBlocks(enter=[Assignment(target=_varref("X"), value=False)]),
            ),
        ]
    )

    assert "dataflow.conflicting_constants" not in _conflicting_kinds(report)
    assert "dataflow.dead_overwrite" not in _conflicting_kinds(report)


def test_conflicting_constants_do_not_cross_sfc_step_phases() -> None:
    report = _sequence_report(
        [
            SFCStep(
                kind="step",
                name="Only",
                code=SFCCodeBlocks(
                    enter=[Assignment(target=_varref("X"), value=True)],
                    exit=[Assignment(target=_varref("X"), value=False)],
                ),
            )
        ]
    )

    assert "dataflow.conflicting_constants" not in _conflicting_kinds(report)
    assert "dataflow.dead_overwrite" not in _conflicting_kinds(report)


def test_sfc_transition_still_sees_values_assigned_in_step_enter() -> None:
    report = _sequence_report(
        [
            SFCStep(
                kind="step",
                name="First",
                code=SFCCodeBlocks(enter=[Assignment(target=_varref("Gate"), value=False)]),
            ),
            SFCTransition(name="Next", condition=_varref("Gate")),
            SFCStep(kind="step", name="Second", code=SFCCodeBlocks()),
        ]
    )

    assert "dataflow.condition_always_false" in _conflicting_kinds(report)


def test_equation_initializer_is_not_a_permanent_fact_across_scans() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="PreviousReset", datatype=Simple_DataType.BOOLEAN, init_value=True),
            Variable(name="Reset", datatype=Simple_DataType.BOOLEAN),
            Variable(name="FixedFalse", datatype=Simple_DataType.BOOLEAN, const=True, init_value=False),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="EdgeDetection",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        IfStmt(
                            branches=(
                                (
                                    NotOp(operand=_varref("PreviousReset")),
                                    (Assignment(target=_varref("Output"), value=True),),
                                ),
                            ),
                            else_block=None,
                        ),
                        Assignment(target=_varref("PreviousReset"), value=_varref("Reset")),
                        IfStmt(
                            branches=((_varref("FixedFalse"), (Assignment(target=_varref("Output"), value=False),)),),
                            else_block=None,
                        ),
                    ],
                )
            ]
        ),
    )
    report = analyze_dataflow(bp)
    conditions = [
        issue.data.get("condition")
        for issue in report.issues
        if issue.kind == "dataflow.condition_always_false" and issue.data is not None
    ]
    assert "FixedFalse" in conditions
    assert not any("PreviousReset" in str(condition) for condition in conditions)


def test_wait_condition_can_change_through_external_module_parameter() -> None:
    phase = SingleModule(
        header=_hdr("Phase"),
        moduledef=None,
        moduleparameters=[
            Variable(name="Done", datatype=Simple_DataType.BOOLEAN),
            Variable(name="FixedFalse", datatype=Simple_DataType.BOOLEAN, const=True, init_value=False),
        ],
        localvariables=[Variable(name="LocalDone", datatype=Simple_DataType.BOOLEAN)],
        submodules=[
            FrameModule(
                header=_hdr("Logic"),
                modulecode=ModuleCode(
                    sequences=[
                        Sequence(
                            name="PhaseSequence",
                            type="sequence",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[
                                SFCStep(
                                    kind="step",
                                    name="Start",
                                    code=SFCCodeBlocks(
                                        enter=[
                                            Assignment(target=_varref("Done"), value=False),
                                            Assignment(target=_varref("LocalDone"), value=False),
                                        ]
                                    ),
                                ),
                                SFCTransition(name="ExternallyCompleted", condition=_varref("Done")),
                                SFCTransition(name="LocallyImpossible", condition=_varref("LocalDone")),
                                SFCTransition(name="ConstantImpossible", condition=_varref("FixedFalse")),
                            ],
                        )
                    ]
                ),
            )
        ],
    )
    report = analyze_dataflow(BasePicture(header=_hdr("Root"), submodules=[phase]))
    conditions = [
        issue.data.get("condition")
        for issue in report.issues
        if issue.kind == "dataflow.condition_always_false" and issue.data is not None
    ]
    assert "Done" not in conditions
    assert "LocalDone" in conditions
    assert "FixedFalse" in conditions


def test_sfc_active_condition_can_change_after_enter_on_later_scans() -> None:
    report = _sequence_report(
        [
            SFCStep(
                kind="step",
                name="ST_AlarmOrManual",
                code=SFCCodeBlocks(
                    enter=[Assignment(target=_varref("Gate"), value=False)],
                    active=[
                        IfStmt(
                            branches=((_varref("Gate"), (Assignment(target=_varref("X"), value=True),)),),
                            else_block=None,
                        ),
                        Assignment(target=_varref("Gate"), value=True),
                    ],
                ),
            )
        ]
    )

    assert not any(
        issue.kind == "dataflow.condition_always_false"
        and issue.data is not None
        and "STEP:ST_AlarmOrManual:ACTIVE" in str(issue.data.get("site"))
        for issue in report.issues
    )


def test_sfc_active_condition_stays_false_when_active_never_writes_flag() -> None:
    report = _sequence_report(
        [
            SFCStep(
                kind="step",
                name="Only",
                code=SFCCodeBlocks(
                    enter=[Assignment(target=_varref("Gate"), value=False)],
                    active=[
                        IfStmt(
                            branches=((_varref("Gate"), (Assignment(target=_varref("X"), value=True),)),),
                            else_block=None,
                        )
                    ],
                ),
            )
        ]
    )

    assert any(
        issue.kind == "dataflow.condition_always_false"
        and issue.data is not None
        and "STEP:Only:ACTIVE" in str(issue.data.get("site"))
        for issue in report.issues
    )


def test_literal_transition_conditions_do_not_emit_condition_findings() -> None:
    report = _sequence_report(
        [
            SFCTransition(name="AlwaysOpen", condition=True),
            SFCTransition(name="NeverOpen", condition=False),
        ]
    )

    kinds = _conflicting_kinds(report)
    assert "dataflow.condition_always_true" not in kinds
    assert "dataflow.condition_always_false" not in kinds


def test_procedure_out_field_writes_do_not_overwrite_sibling_fields() -> None:
    record_type = DataType(
        name="RecordType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="First", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Second", datatype=Simple_DataType.BOOLEAN),
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[record_type],
        localvariables=[
            Variable(name="Rec", datatype="RecordType"),
            Variable(name="Source", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Status1", datatype=Simple_DataType.INTEGER),
            Variable(name="Status2", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            sequences=[],
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        FuncCallStmt(
                            call=FuncCall(
                                name="CopyVariable",
                                args=(_varref("Source"), _varref("Rec.First"), _varref("Status1")),
                            )
                        ),
                        FuncCallStmt(
                            call=FuncCall(
                                name="CopyVariable",
                                args=(_varref("Source"), _varref("Rec.Second"), _varref("Status2")),
                            )
                        ),
                    ],
                )
            ],
        ),
        moduledef=None,
    )

    report = analyze_dataflow(bp)
    dead_first = [
        issue
        for issue in report.issues
        if issue.kind == "dataflow.dead_overwrite"
        and issue.data is not None
        and issue.data.get("symbol") == "Rec.First"
    ]

    assert dead_first == []
