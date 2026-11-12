from __future__ import annotations

from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ModuleHeader,
    Sequence,
    SFCBodyItem,
    SFCCodeBlocks,
    SFCFork,
    SFCStep,
    SFCSubsequence,
    SFCTransitionSub,
    Simple_DataType,
    Variable,
)
from sattline_parser.models.expressions import Assignment, Compare, FuncCall, FuncCallStmt, IfStmt, VarRef

from sattlint.analyzers.dataflow import analyze_dataflow
from sattlint.analyzers.sfc import collect_sfc_reachability_findings


def _make_sequence(code: list[SFCBodyItem]) -> BasePicture:
    return BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        modulecodes=[
            ModuleCode(
                sequences=[Sequence(name="SeqMain", type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=code)],
                equationblocks=[],
            )
        ],
    )


def _unreachable_labels(bp: BasePicture) -> list[str]:
    return [
        f"{finding.node_label}:{finding.terminated_by.get('kind')}" for finding in collect_sfc_reachability_findings(bp)
    ]


def test_sequence_nodes_after_break_are_owned_by_sfc_not_dataflow():
    bp = _make_sequence(
        [
            SFCStep(
                kind="step",
                name="Break",
                code=SFCCodeBlocks(),
                fork=SFCFork(targets=("Done",), has_break=True),
            ),
            SFCStep(kind="step", name="AfterBreak", code=SFCCodeBlocks()),
        ]
    )

    report = analyze_dataflow(bp)

    assert not any(issue.kind == "dataflow.unreachable_sequence_node" for issue in report.issues)
    assert _unreachable_labels(bp) == ["SFCStep:AfterBreak:SFCFork"]


def test_sequence_nodes_after_fork_are_owned_by_sfc_not_dataflow():
    bp = _make_sequence(
        [
            SFCStep(
                kind="step",
                name="Fork",
                code=SFCCodeBlocks(),
                fork=SFCFork(targets=("Done",)),
            ),
            SFCStep(kind="step", name="AfterFork", code=SFCCodeBlocks()),
        ]
    )

    report = analyze_dataflow(bp)

    assert not any(issue.kind == "dataflow.unreachable_sequence_node" for issue in report.issues)
    assert _unreachable_labels(bp) == ["SFCStep:AfterFork:SFCFork"]


def test_call_output_inside_expression_invalidates_prior_constant():
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        localvariables=[
            Variable(name="Text", datatype=Simple_DataType.STRING),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
            Variable(name="Value", datatype=Simple_DataType.INTEGER),
        ],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="Main",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            Assignment(target=VarRef(name="Status"), value=-1),
                            Assignment(
                                target=VarRef(name="Value"),
                                value=FuncCall(
                                    name="StringToInteger", args=(VarRef(name="Text"), VarRef(name="Status"))
                                ),
                            ),
                            IfStmt(
                                branches=(
                                    (
                                        Compare(left=VarRef(name="Status"), op="==", right=-1),
                                        (),
                                    ),
                                ),
                                else_block=(),
                            ),
                        ],
                    )
                ],
                sequences=[],
            )
        ],
    )

    kinds = {issue.kind for issue in analyze_dataflow(bp).issues}

    assert "dataflow.condition_always_true" not in kinds
    assert "dataflow.condition_always_false" not in kinds


def test_call_statement_output_invalidates_prior_constant():
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        localvariables=[
            Variable(name="Text", datatype=Simple_DataType.STRING),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="Main",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            Assignment(target=VarRef(name="Status"), value=-1),
                            FuncCallStmt(
                                call=FuncCall(
                                    name="StringToInteger",
                                    args=(VarRef(name="Text"), VarRef(name="Status")),
                                )
                            ),
                            IfStmt(
                                branches=(
                                    (
                                        Compare(left=VarRef(name="Status"), op="==", right=-1),
                                        (),
                                    ),
                                ),
                                else_block=(),
                            ),
                        ],
                    )
                ],
                sequences=[],
            )
        ],
    )

    kinds = {issue.kind for issue in analyze_dataflow(bp).issues}

    assert "dataflow.condition_always_true" not in kinds
    assert "dataflow.condition_always_false" not in kinds


def test_break_inside_nested_sequence_nodes_is_owned_by_sfc_not_dataflow():
    bp = _make_sequence(
        [
            SFCSubsequence(
                name="Prepare",
                body=[
                    SFCStep(
                        kind="step",
                        name="Break",
                        code=SFCCodeBlocks(),
                        fork=SFCFork(targets=("Done",), has_break=True),
                    ),
                    SFCStep(kind="step", name="AfterBreakInSubsequence", code=SFCCodeBlocks()),
                ],
            ),
            SFCTransitionSub(
                name="Gate",
                body=[
                    SFCStep(
                        kind="step",
                        name="Break",
                        code=SFCCodeBlocks(),
                        fork=SFCFork(targets=("Done",), has_break=True),
                    ),
                    SFCStep(kind="step", name="AfterBreakInTransitionSub", code=SFCCodeBlocks()),
                ],
            ),
        ]
    )

    report = analyze_dataflow(bp)

    assert not any(issue.kind == "dataflow.unreachable_sequence_node" for issue in report.issues)
    assert _unreachable_labels(bp) == [
        "SFCStep:AfterBreakInSubsequence:SFCFork",
        "SFCStep:AfterBreakInTransitionSub:SFCFork",
    ]
