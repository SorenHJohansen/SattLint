from __future__ import annotations

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleCode,
    ModuleHeader,
    Sequence,
    SFCBodyItem,
    SFCBreak,
    SFCCodeBlocks,
    SFCFork,
    SFCStep,
    SFCSubsequence,
    SFCTransitionSub,
)

from sattlint.analyzers.dataflow import analyze_dataflow
from sattlint.analyzers.sfc import collect_sfc_reachability_findings


def _make_sequence(code: list[SFCBodyItem]) -> BasePicture:
    return BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        modulecode=ModuleCode(
            sequences=[Sequence(name="SeqMain", type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=code)],
            equations=[],
        ),
    )


def _unreachable_labels(bp: BasePicture) -> list[str]:
    return [
        f"{finding.node_label}:{finding.terminated_by.get('kind')}" for finding in collect_sfc_reachability_findings(bp)
    ]


def test_sequence_nodes_after_break_are_owned_by_sfc_not_dataflow():
    bp = _make_sequence(
        [
            SFCBreak(),
            SFCStep(kind="step", name="AfterBreak", code=SFCCodeBlocks()),
        ]
    )

    report = analyze_dataflow(bp)

    assert not any(issue.kind == "dataflow.unreachable_sequence_node" for issue in report.issues)
    assert _unreachable_labels(bp) == ["SFCStep:AfterBreak:SFCBreak"]


def test_sequence_nodes_after_fork_are_owned_by_sfc_not_dataflow():
    bp = _make_sequence(
        [
            SFCFork(targets=("Done",)),
            SFCStep(kind="step", name="AfterFork", code=SFCCodeBlocks()),
        ]
    )

    report = analyze_dataflow(bp)

    assert not any(issue.kind == "dataflow.unreachable_sequence_node" for issue in report.issues)
    assert _unreachable_labels(bp) == ["SFCStep:AfterFork:SFCFork"]


def test_break_inside_nested_sequence_nodes_is_owned_by_sfc_not_dataflow():
    bp = _make_sequence(
        [
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
        ]
    )

    report = analyze_dataflow(bp)

    assert not any(issue.kind == "dataflow.unreachable_sequence_node" for issue in report.issues)
    assert _unreachable_labels(bp) == [
        "SFCStep:AfterBreakInSubsequence:SFCBreak",
        "SFCStep:AfterBreakInTransitionSub:SFCBreak",
    ]
