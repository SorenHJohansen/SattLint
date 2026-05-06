from __future__ import annotations

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleCode,
    ModuleHeader,
    Sequence,
    SFCBreak,
    SFCCodeBlocks,
    SFCFork,
    SFCStep,
    SFCSubsequence,
    SFCTransitionSub,
)
from sattlint.analyzers.dataflow import analyze_dataflow


def test_sequence_nodes_after_break_are_reported_unreachable():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCBreak(),
            SFCStep(kind="step", name="AfterBreak", code=SFCCodeBlocks()),
        ],
    )
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_dataflow(bp)

    assert any(issue.kind == "dataflow.unreachable_sequence_node" for issue in report.issues)


def test_sequence_nodes_after_fork_are_reported_unreachable_with_target_metadata():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCFork(target="Done"),
            SFCStep(kind="step", name="AfterFork", code=SFCCodeBlocks()),
        ],
    )
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_dataflow(bp)

    issues = [issue for issue in report.issues if issue.kind == "dataflow.unreachable_sequence_node"]
    assert len(issues) == 1
    assert issues[0].data == {
        "sequence": "SeqMain",
        "branch_path": [],
        "node_index": 1,
        "node_label": "SFCStep:AfterFork",
        "terminated_by": {"kind": "SFCFork", "target": "Done"},
        "site": "SEQ:SeqMain",
    }


def test_break_inside_nested_sequence_nodes_marks_inner_followups_unreachable():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCSubsequence(
                name="Prepare",
                body=[
                    SFCBreak(),
                    SFCStep(kind="step", name="AfterBreakInSubsequence", code=SFCCodeBlocks()),
                ],
            ),
            SFCTransitionSub(
                name="Gate",
                body=[
                    SFCBreak(),
                    SFCStep(kind="step", name="AfterBreakInTransitionSub", code=SFCCodeBlocks()),
                ],
            ),
        ],
    )
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_dataflow(bp)

    unreachable = [issue for issue in report.issues if issue.kind == "dataflow.unreachable_sequence_node"]
    assert len(unreachable) == 2
    assert unreachable[0].data == {
        "sequence": "SeqMain",
        "branch_path": [],
        "node_index": 1,
        "node_label": "SFCStep:AfterBreakInSubsequence",
        "terminated_by": {"kind": "SFCBreak"},
        "site": "SEQ:SeqMain > SUBSEQ:Prepare",
    }
    assert unreachable[1].data == {
        "sequence": "SeqMain",
        "branch_path": [],
        "node_index": 1,
        "node_label": "SFCStep:AfterBreakInTransitionSub",
        "terminated_by": {"kind": "SFCBreak"},
        "site": "SEQ:SeqMain > TRANS-SUB:Gate",
    }
