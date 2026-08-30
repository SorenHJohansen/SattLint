from __future__ import annotations

from collections.abc import Sequence as Seq
from types import SimpleNamespace

from sattline_parser.models.ast_model import (
    BasePicture,
    CodeItem,
    Equation,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    Sequence,
    SFCAlternative,
    SFCBodyItem,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import Assignment, FuncCall, FuncCallStmt, IfStmt, NotOp, VarRef

from sattlint import constants as const
from sattlint.reporting.variables_report import IssueKind, VariableIssue
from tests._reset_contamination_test_api import reset_contamination_module


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def _eq(name: str, code: Seq[CodeItem]) -> Equation:
    return Equation(name=name, position=(0.0, 0.0), size=(1.0, 1.0), code=list(code))


def _seq(name: str, code: Seq[SFCBodyItem]) -> Sequence:
    return Sequence(name=name, type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=list(code))


def _bool_step(name: str, statements: Seq[CodeItem]) -> SFCStep:
    return SFCStep(kind="step", name=name, code=SFCCodeBlocks(active=list(statements)))


def test_detection_walks_frame_submodules_for_reset_and_latching() -> None:
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="Other", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="SeqResetOld", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Latch", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    "ResetEq",
                    [
                        IfStmt(
                            branches=(
                                (
                                    NotOp(operand=_varref("OpSeq.Reset")),
                                    (Assignment(target=_varref("Counter"), value=_varref("ResetValue")),),
                                ),
                                (
                                    NotOp(operand=_varref("SeqResetOld")),
                                    (Assignment(target=_varref("Other"), value=_varref("ResetValue")),),
                                ),
                            ),
                            else_block=None,
                        ),
                        Assignment(target=_varref("SeqResetOld"), value=_varref("OpSeq.Reset")),
                    ],
                ),
                _eq(
                    "LatchEq",
                    [
                        IfStmt(
                            branches=((_varref("Start"), (Assignment(target=_varref("Latch"), value=True),)),),
                            else_block=None,
                        ),
                    ],
                ),
            ],
            sequences=[_seq("OpSeq", [])],
        ),
        parametermappings=[],
    )
    picture = BasePicture(header=_hdr("Root"), submodules=[FrameModule(header=_hdr("Frame"), submodules=[child])])

    reset_issues: list[VariableIssue] = []
    latch_issues: list[VariableIssue] = []

    reset_contamination_module.detect_reset_contamination(
        picture,
        reset_issues,
        limit_to_module_path=["Root", "Frame", "Child"],
    )
    reset_contamination_module.detect_implicit_latching(
        picture,
        latch_issues,
        limit_to_module_path=["Root", "Frame", "Child"],
    )

    assert any(
        issue.module_path == ["Root", "Frame", "Child"]
        and issue.variable is not None
        and issue.variable.name == "Counter"
        for issue in reset_issues
    )
    assert [(issue.module_path, issue.variable.name) for issue in latch_issues if issue.variable is not None] == [
        (["Root", "Frame", "Child"], "Latch")
    ]


def test_reset_helpers_collect_nested_refs_and_skip_fully_reset_paths() -> None:
    env = {
        "counter": Variable(name="Counter", datatype=Simple_DataType.INTEGER),
        "resetvalue": Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
        "seqresetold": Variable(name="SeqResetOld", datatype=Simple_DataType.BOOLEAN),
    }
    modulecode = ModuleCode(
        equations=[
            _eq(
                "CoveredReset",
                [
                    IfStmt(
                        branches=(
                            (
                                NotOp(operand=_varref("OpSeq.Reset")),
                                (Assignment(target=_varref("Counter"), value=_varref("ResetValue")),),
                            ),
                            (
                                NotOp(operand=_varref("SeqResetOld")),
                                (Assignment(target=_varref("Counter"), value=_varref("ResetValue")),),
                            ),
                        ),
                        else_block=None,
                    ),
                    Assignment(target=_varref("SeqResetOld"), value=_varref("OpSeq.Reset")),
                ],
            )
        ],
        sequences=[
            _seq(
                "OpSeq",
                [
                    SFCTransition(name="Gate", condition=_varref("OpSeq.Reset")),
                    SFCAlternative(
                        branches=[
                            [
                                SFCSubsequence(
                                    name="Sub",
                                    body=[Assignment(target=_varref("SeqResetOld"), value=_varref("OpSeq.Reset"))],  # pyright: ignore[reportArgumentType] — runtime accepts Assignment in SFCBodyItem
                                )
                            ]
                        ]
                    ),
                    SFCTransitionSub(
                        name="GateSub",
                        body=[Assignment(target=_varref("Counter"), value=_varref("ResetValue"))],  # pyright: ignore[reportArgumentType]
                    ),
                ],
            )
        ],
    )

    issues: list[VariableIssue] = []
    reset_contamination_module._check_for_modulecode(modulecode, env, ["Root"], issues)

    assert issues == []
    assert "opseq.reset" in reset_contamination_module._collect_var_refs(modulecode)
    assert reset_contamination_module._collect_reset_old_vars(modulecode, "opseq.reset") == {"SeqResetOld"}


def test_latching_helpers_cover_boolean_paths_and_sequence_recursion() -> None:
    env = {
        "flag": Variable(name="Flag", datatype=Simple_DataType.BOOLEAN),
        "otherflag": Variable(name="OtherFlag", datatype=Simple_DataType.BOOLEAN),
    }
    states = reset_contamination_module._collect_boolean_stmt_paths(
        SimpleNamespace(
            data=const.KEY_STATEMENT,
            children=[
                (
                    const.GRAMMAR_VALUE_IF,
                    [
                        (True, [(const.KEY_ASSIGN, _varref("Flag"), True)]),
                        (False, [(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("OtherFlag"), True])]),
                    ],
                    [(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("Flag"), False])],
                ),
                [SimpleNamespace(children=[(const.KEY_ASSIGN, _varref("OtherFlag"), False)])],
                SimpleNamespace(children=[(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("Flag"), False])]),
            ],
        ),
        env,
        [reset_contamination_module._BooleanPathState()],
    )
    seq_states = reset_contamination_module._collect_boolean_seq_block_paths(
        [
            SFCStep(
                kind="step",
                name="StepA",
                code=SFCCodeBlocks(
                    enter=[Assignment(target=_varref("Flag"), value=True)],
                    active=[FuncCallStmt(call=FuncCall(name="SetBooleanValue", args=(_varref("OtherFlag"), True)))],
                    exit=[FuncCallStmt(call=FuncCall(name="SetBooleanValue", args=(_varref("Flag"), False)))],
                ),
            ),
            SFCTransition(name="Gate", condition=True),
            SFCAlternative(
                branches=[
                    [_bool_step("AltA", [Assignment(target=_varref("Flag"), value=True)])],
                    [_bool_step("AltB", [Assignment(target=_varref("OtherFlag"), value=True)])],
                ]
            ),
            SFCParallel(
                branches=[
                    [_bool_step("ParA", [Assignment(target=_varref("Flag"), value=True)])],
                    [
                        _bool_step(
                            "ParB",
                            [FuncCallStmt(call=FuncCall(name="SetBooleanValue", args=(_varref("OtherFlag"), False)))],
                        )
                    ],
                ]
            ),
            SFCSubsequence(name="Sub", body=[Assignment(target=_varref("Flag"), value=True)]),  # pyright: ignore[reportArgumentType]
            SFCTransitionSub(name="SubGate", body=[Assignment(target=_varref("OtherFlag"), value=False)]),  # pyright: ignore[reportArgumentType]
        ],
        env,
        [reset_contamination_module._BooleanPathState()],
    )
    merged_states = reset_contamination_module._merge_boolean_parallel_branch_results(
        [
            [reset_contamination_module._BooleanPathState(true_writes={("flag", ""): (env["flag"], "")})],
            [reset_contamination_module._BooleanPathState(false_writes={("otherflag", ""): (env["otherflag"], "")})],
        ]
    )
    assert reset_contamination_module._merge_boolean_parallel_branch_results([]) == []

    issues: list[VariableIssue] = []
    reset_contamination_module._scan_stmt_for_latching(
        IfStmt(
            branches=((True, (Assignment(target=_varref("Flag"), value=True),)),),
            else_block=(FuncCallStmt(call=FuncCall(name="SetBooleanValue", args=(_varref("Flag"), False))),),
        ),
        env,
        ["Root"],
        issues,
        set(),
        site="EQ:Guard",
        sequence_name="SeqA",
    )
    reset_contamination_module._scan_seq_nodes_for_latching(
        [
            _bool_step("LatchStep", [Assignment(target=_varref("Flag"), value=True)]),
            SFCAlternative(
                branches=[
                    [_bool_step("Left", [Assignment(target=_varref("Flag"), value=True)])],
                    [_bool_step("Right", [Assignment(target=_varref("OtherFlag"), value=True)])],
                ]
            ),
            SFCParallel(branches=[[_bool_step("Parallel", [Assignment(target=_varref("Flag"), value=True)])]]),
            SFCSubsequence(
                name="Nested", body=[_bool_step("NestedStep", [Assignment(target=_varref("Flag"), value=True)])]
            ),
            SFCTransitionSub(
                name="NestedGate",
                body=[_bool_step("NestedGateStep", [Assignment(target=_varref("OtherFlag"), value=True)])],
            ),
        ],
        env,
        ["Root"],
        issues,
        set(),
        site="SEQ:Main",
        sequence_name="Main",
    )

    assert any(state.true_writes for state in states)
    assert any(state.false_writes for state in states)
    assert seq_states
    assert merged_states[0].true_writes == {("flag", ""): (env["flag"], "")}
    assert merged_states[0].false_writes == {("otherflag", ""): (env["otherflag"], "")}
    assert any(issue.kind is IssueKind.IMPLICIT_LATCH for issue in issues)
    assert any(issue.sequence_name == "Main" for issue in issues)
