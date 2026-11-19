from sattline_parser.models.expressions import Assignment, FuncCall, FuncCallStmt, NotOp

from sattlint.analyzers.reset_contamination._reset_latching import (
    BooleanPathState,
    collect_boolean_seq_node_paths,
    merge_boolean_parallel_branch_results,
    scan_seq_nodes_for_latching,
)
from sattlint.analyzers.reset_contamination._reset_path_collection import (
    collect_if_stmt_paths,
    collect_seq_node_paths,
)
from sattlint.analyzers.reset_contamination._reset_path_state import (
    PathState,
)
from tests.helpers.analyzers_state_support import *


def test_reset_contamination_helpers_collect_if_and_nested_sequence_paths():
    counter = Variable(name="Counter", datatype=ScalarDatatype.INTEGER)
    source = Variable(name="Source", datatype=ScalarDatatype.INTEGER)
    env = {
        "counter": counter,
        "source": source,
    }

    if_states = collect_if_stmt_paths(
        [
            (
                NotOp(operand=_varref("OpSeq.Reset")),
                [Assignment(target=_varref("Counter.Member"), value=_varref("Source"))],
            ),
            (
                NotOp(operand=_varref("OpSeqResetOld")),
                [Assignment(target=_varref("Counter"), value=_varref("Source"))],
            ),
        ],
        None,
        env,
        "opseq.reset",
        {"opseqresetold"},
        [PathState()],
    )

    assert {state.reset_state for state in if_states} == {"run", "reset"}
    run_state = next(state for state in if_states if state.reset_state == "run")
    reset_state = next(state for state in if_states if state.reset_state == "reset")
    assert ("counter", "member") in run_state.run_writes
    assert ("counter", "") in reset_state.reset_writes

    subsequence_states = collect_seq_node_paths(
        SFCSubsequence(
            name="Nested",
            body=[
                SFCStep(
                    kind="step",
                    name="NestedStep",
                    code=SFCCodeBlocks(active=[Assignment(target=_varref("Counter.Nested"), value=_varref("Source"))]),
                )
            ],
        ),
        env,
        "opseq.reset",
        {"opseqresetold"},
        [PathState(reset_state="run")],
    )
    transition_sub_states = collect_seq_node_paths(
        SFCTransitionSub(
            name="Gate",
            body=[
                SFCStep(
                    kind="step",
                    name="OtherStep",
                    code=SFCCodeBlocks(active=[Assignment(target=_varref("Counter.Other"), value=_varref("Source"))]),
                )
            ],
        ),
        env,
        "opseq.reset",
        {"opseqresetold"},
        [PathState(reset_state="run")],
    )

    assert ("counter", "nested") in subsequence_states[0].run_writes
    assert ("counter", "other") in transition_sub_states[0].run_writes


def test_implicit_latch_helpers_collect_boolean_statement_and_sequence_paths():
    env = {
        "flag": Variable(name="Flag", datatype=ScalarDatatype.BOOLEAN),
        "wrappedflag": Variable(name="WrappedFlag", datatype=ScalarDatatype.BOOLEAN),
        "stepflag": Variable(name="StepFlag", datatype=ScalarDatatype.BOOLEAN),
        "alarmlatched": Variable(name="AlarmLatched", datatype=ScalarDatatype.BOOLEAN),
        "otherflag": Variable(name="OtherFlag", datatype=ScalarDatatype.BOOLEAN),
        "branchflag": Variable(name="BranchFlag", datatype=ScalarDatatype.BOOLEAN),
        "parallela": Variable(name="ParallelA", datatype=ScalarDatatype.BOOLEAN),
        "parallelb": Variable(name="ParallelB", datatype=ScalarDatatype.BOOLEAN),
        "nestedflag": Variable(name="NestedFlag", datatype=ScalarDatatype.BOOLEAN),
        "gateflag": Variable(name="GateFlag", datatype=ScalarDatatype.BOOLEAN),
    }

    step_states = collect_boolean_seq_node_paths(
        SFCStep(
            kind="step",
            name="BooleanStep",
            code=SFCCodeBlocks(
                enter=[Assignment(target=_varref("StepFlag"), value=True)],
                active=[FuncCallStmt(call=FuncCall(name="SetBooleanValue", args=(_varref("AlarmLatched"), False)))],
                exit=[Assignment(target=_varref("OtherFlag"), value=True)],
            ),
        ),
        env,
        [BooleanPathState()],
    )

    assert len(step_states) == 1
    assert set(step_states[0].true_writes) == {("stepflag", ""), ("otherflag", "")}
    assert set(step_states[0].false_writes) == {("alarmlatched", "")}

    transition_states = collect_boolean_seq_node_paths(
        SFCTransition(name="Gate", condition=True),
        env,
        step_states,
    )
    assert transition_states == step_states

    alternative_states = collect_boolean_seq_node_paths(
        SFCAlternative(
            branches=[
                [
                    SFCStep(
                        kind="step",
                        name="AltTrue",
                        code=SFCCodeBlocks(active=[Assignment(target=_varref("BranchFlag"), value=True)]),
                    )
                ],
                [
                    SFCStep(
                        kind="step",
                        name="AltFalse",
                        code=SFCCodeBlocks(
                            active=[
                                FuncCallStmt(call=FuncCall(name="SetBooleanValue", args=(_varref("BranchFlag"), False)))
                            ]
                        ),
                    )
                ],
            ]
        ),
        env,
        [BooleanPathState()],
    )

    assert len(alternative_states) == 2
    assert any(("branchflag", "") in state.true_writes for state in alternative_states)
    assert any(("branchflag", "") in state.false_writes for state in alternative_states)

    parallel_states = collect_boolean_seq_node_paths(
        SFCParallel(
            branches=[
                [
                    SFCStep(
                        kind="step",
                        name="Left",
                        code=SFCCodeBlocks(active=[Assignment(target=_varref("ParallelA"), value=True)]),
                    )
                ],
                [
                    SFCStep(
                        kind="step",
                        name="Right",
                        code=SFCCodeBlocks(
                            active=[
                                FuncCallStmt(call=FuncCall(name="SetBooleanValue", args=(_varref("ParallelB"), False)))
                            ]
                        ),
                    )
                ],
            ]
        ),
        env,
        [BooleanPathState()],
    )

    assert len(parallel_states) == 1
    assert set(parallel_states[0].true_writes) == {("parallela", "")}
    assert set(parallel_states[0].false_writes) == {("parallelb", "")}
    assert merge_boolean_parallel_branch_results([]) == []

    subsequence_states = collect_boolean_seq_node_paths(
        SFCSubsequence(
            name="Nested",
            body=[
                SFCStep(
                    kind="step",
                    name="NestedStep",
                    code=SFCCodeBlocks(active=[Assignment(target=_varref("NestedFlag"), value=True)]),
                )
            ],
        ),
        env,
        [BooleanPathState()],
    )
    transition_sub_states = collect_boolean_seq_node_paths(
        SFCTransitionSub(
            name="NestedGate",
            body=[
                SFCStep(
                    kind="step",
                    name="GateStep",
                    code=SFCCodeBlocks(
                        active=[FuncCallStmt(call=FuncCall(name="SetBooleanValue", args=(_varref("GateFlag"), False)))]
                    ),
                )
            ],
        ),
        env,
        [BooleanPathState()],
    )

    assert set(subsequence_states[0].true_writes) == {("nestedflag", "")}
    assert set(transition_sub_states[0].false_writes) == {("gateflag", "")}


def test_implicit_latch_helpers_scan_nested_sfc_nodes_and_dedupe_issues():
    env = {
        "alarmlatched": Variable(name="AlarmLatched", datatype=ScalarDatatype.BOOLEAN),
        "stepflag": Variable(name="StepFlag", datatype=ScalarDatatype.BOOLEAN),
        "nestedflag": Variable(name="NestedFlag", datatype=ScalarDatatype.BOOLEAN),
        "transitionflag": Variable(name="TransitionFlag", datatype=ScalarDatatype.BOOLEAN),
    }
    issues: list[VariableIssue] = []
    seen: set[tuple[tuple[str, ...], str, str]] = set()
    nodes = [
        SFCStep(
            kind="step",
            name="LatchStep",
            code=SFCCodeBlocks(active=[Assignment(target=_varref("AlarmLatched"), value=True)]),
        ),
        SFCAlternative(
            branches=[
                [
                    SFCStep(
                        kind="step",
                        name="AltOne",
                        code=SFCCodeBlocks(active=[Assignment(target=_varref("StepFlag"), value=True)]),
                    )
                ],
                [
                    SFCStep(
                        kind="step",
                        name="AltTwo",
                        code=SFCCodeBlocks(
                            active=[
                                FuncCallStmt(call=FuncCall(name="SetBooleanValue", args=(_varref("StepFlag"), False)))
                            ]
                        ),
                    )
                ],
            ]
        ),
        SFCParallel(
            branches=[
                [
                    SFCSubsequence(
                        name="Nested",
                        body=[
                            SFCStep(
                                kind="step",
                                name="NestedLatch",
                                code=SFCCodeBlocks(active=[Assignment(target=_varref("NestedFlag"), value=True)]),
                            )
                        ],
                    )
                ],
                [
                    SFCTransitionSub(
                        name="NestedGate",
                        body=[
                            SFCStep(
                                kind="step",
                                name="TransitionLatch",
                                code=SFCCodeBlocks(active=[Assignment(target=_varref("TransitionFlag"), value=True)]),
                            )
                        ],
                    )
                ],
            ]
        ),
    ]

    scan_seq_nodes_for_latching(
        nodes,
        env,
        ["BasePicture", "Unit"],
        issues,
        seen,
        site="SEQ:Main",
        sequence_name="Main",
    )
    scan_seq_nodes_for_latching(
        nodes,
        env,
        ["BasePicture", "Unit"],
        issues,
        seen,
        site="SEQ:Main",
        sequence_name="Main",
    )

    assert len(issues) == 4
    assert {issue.site for issue in issues} == {
        "SEQ:Main > STEP:LatchStep",
        "SEQ:Main > ALT:1 > STEP:AltOne",
        "SEQ:Main > PAR:1 > STEP:NestedLatch",
        "SEQ:Main > PAR:2 > STEP:TransitionLatch",
    }
