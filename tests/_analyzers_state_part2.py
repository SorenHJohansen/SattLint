# ruff: noqa: F403, F405
from ._analyzers_state_test_support import *


def test_reset_contamination_helpers_collect_if_and_nested_sequence_paths():
    counter = Variable(name="Counter", datatype=Simple_DataType.INTEGER)
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    env = {
        "counter": counter,
        "source": source,
    }

    if_states = reset_contamination_module._collect_if_stmt_paths(
        [
            (
                (const.GRAMMAR_VALUE_NOT, _varref("OpSeq.Reset")),
                [(const.KEY_ASSIGN, _varref("Counter.Member"), _varref("Source"))],
            ),
            (
                (const.GRAMMAR_VALUE_NOT, _varref("OpSeqResetOld")),
                [(const.KEY_ASSIGN, _varref("Counter"), _varref("Source"))],
            ),
        ],
        None,
        env,
        "opseq.reset",
        {"opseqresetold"},
        [reset_contamination_module._PathState()],
    )

    assert {state.reset_state for state in if_states} == {"run", "reset"}
    run_state = next(state for state in if_states if state.reset_state == "run")
    reset_state = next(state for state in if_states if state.reset_state == "reset")
    assert ("counter", "member") in run_state.run_writes
    assert ("counter", "") in reset_state.reset_writes

    subsequence_states = reset_contamination_module._collect_seq_node_paths(
        SFCSubsequence(
            name="Nested",
            body=[
                SFCStep(
                    kind="step",
                    name="NestedStep",
                    code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("Counter.Nested"), _varref("Source"))]),
                )
            ],
        ),
        env,
        "opseq.reset",
        {"opseqresetold"},
        [reset_contamination_module._PathState(reset_state="run")],
    )
    transition_sub_states = reset_contamination_module._collect_seq_node_paths(
        SFCTransitionSub(
            name="Gate",
            body=[
                SFCStep(
                    kind="step",
                    name="OtherStep",
                    code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("Counter.Other"), _varref("Source"))]),
                )
            ],
        ),
        env,
        "opseq.reset",
        {"opseqresetold"},
        [reset_contamination_module._PathState(reset_state="run")],
    )

    assert ("counter", "nested") in subsequence_states[0].run_writes
    assert ("counter", "other") in transition_sub_states[0].run_writes


def test_reset_contamination_helpers_collect_statement_paths_across_expression_wrappers():
    counter = Variable(name="Counter", datatype=Simple_DataType.INTEGER)
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    destination = Variable(name="Destination", datatype=Simple_DataType.INTEGER)
    status = Variable(name="Status", datatype=Simple_DataType.INTEGER)
    env = {
        "counter": counter,
        "source": source,
        "destination": destination,
        "status": status,
    }
    wrapped = SimpleNamespace(
        children=[
            (
                const.KEY_TERNARY,
                [
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OpSeq.Reset")),
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [_varref("Source"), _varref("Destination"), _varref("Status")],
                        ),
                    )
                ],
                (
                    const.KEY_ASSIGN,
                    _varref("Counter"),
                    (const.KEY_COMPARE, _varref("Counter"), [("=", _varref("Source"))]),
                ),
            ),
            (const.KEY_ADD, _varref("Counter"), [("+", _varref("Source"))]),
            (const.KEY_PLUS, _varref("Counter")),
            (const.KEY_MINUS, _varref("Source")),
            (const.GRAMMAR_VALUE_OR, [_varref("OpSeq.Reset"), _varref("OpSeqResetOld")]),
            [(const.KEY_FUNCTION_CALL, "CopyVariable", [_varref("Source"), _varref("Destination"), _varref("Status")])],
        ]
    )

    states = reset_contamination_module._collect_stmt_paths(
        wrapped,
        env,
        "opseq.reset",
        {"opseqresetold"},
        [reset_contamination_module._PathState()],
    )

    assert len(states) == 1
    assert set(states[0].run_writes) == {
        ("counter", ""),
        ("destination", ""),
        ("status", ""),
    }


def test_implicit_latch_helpers_collect_boolean_statement_and_sequence_paths():
    env = {
        "flag": Variable(name="Flag", datatype=Simple_DataType.BOOLEAN),
        "wrappedflag": Variable(name="WrappedFlag", datatype=Simple_DataType.BOOLEAN),
        "stepflag": Variable(name="StepFlag", datatype=Simple_DataType.BOOLEAN),
        "alarmlatched": Variable(name="AlarmLatched", datatype=Simple_DataType.BOOLEAN),
        "otherflag": Variable(name="OtherFlag", datatype=Simple_DataType.BOOLEAN),
        "branchflag": Variable(name="BranchFlag", datatype=Simple_DataType.BOOLEAN),
        "parallela": Variable(name="ParallelA", datatype=Simple_DataType.BOOLEAN),
        "parallelb": Variable(name="ParallelB", datatype=Simple_DataType.BOOLEAN),
        "nestedflag": Variable(name="NestedFlag", datatype=Simple_DataType.BOOLEAN),
        "gateflag": Variable(name="GateFlag", datatype=Simple_DataType.BOOLEAN),
    }

    wrapped_states = reset_contamination_module._collect_boolean_stmt_paths(
        SimpleNamespace(
            data=const.KEY_STATEMENT,
            children=[
                (
                    const.GRAMMAR_VALUE_IF,
                    [(True, [(const.KEY_ASSIGN, _varref("Flag"), True)])],
                    [(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("Flag"), False])],
                ),
                SimpleNamespace(children=[(const.KEY_ASSIGN, _varref("WrappedFlag"), True)]),
            ],
        ),
        env,
        [reset_contamination_module._BooleanPathState()],
    )

    assert len(wrapped_states) == 2
    assert all(("wrappedflag", "") in state.true_writes for state in wrapped_states)
    assert any(("flag", "") in state.true_writes for state in wrapped_states)
    assert any(("flag", "") in state.false_writes for state in wrapped_states)

    step_states = reset_contamination_module._collect_boolean_seq_node_paths(
        SFCStep(
            kind="step",
            name="BooleanStep",
            code=SFCCodeBlocks(
                enter=[(const.KEY_ASSIGN, _varref("StepFlag"), True)],
                active=[(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("AlarmLatched"), False])],
                exit=[(const.KEY_ASSIGN, _varref("OtherFlag"), True)],
            ),
        ),
        env,
        [reset_contamination_module._BooleanPathState()],
    )

    assert len(step_states) == 1
    assert set(step_states[0].true_writes) == {("stepflag", ""), ("otherflag", "")}
    assert set(step_states[0].false_writes) == {("alarmlatched", "")}

    transition_states = reset_contamination_module._collect_boolean_seq_node_paths(
        SFCTransition(name="Gate", condition=True),
        env,
        step_states,
    )
    assert transition_states == step_states

    alternative_states = reset_contamination_module._collect_boolean_seq_node_paths(
        SFCAlternative(
            branches=[
                [
                    SFCStep(
                        kind="step",
                        name="AltTrue",
                        code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("BranchFlag"), True)]),
                    )
                ],
                [
                    SFCStep(
                        kind="step",
                        name="AltFalse",
                        code=SFCCodeBlocks(
                            active=[(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("BranchFlag"), False])]
                        ),
                    )
                ],
            ]
        ),
        env,
        [reset_contamination_module._BooleanPathState()],
    )

    assert len(alternative_states) == 2
    assert any(("branchflag", "") in state.true_writes for state in alternative_states)
    assert any(("branchflag", "") in state.false_writes for state in alternative_states)

    parallel_states = reset_contamination_module._collect_boolean_seq_node_paths(
        SFCParallel(
            branches=[
                [
                    SFCStep(
                        kind="step",
                        name="Left",
                        code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("ParallelA"), True)]),
                    )
                ],
                [
                    SFCStep(
                        kind="step",
                        name="Right",
                        code=SFCCodeBlocks(
                            active=[(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("ParallelB"), False])]
                        ),
                    )
                ],
            ]
        ),
        env,
        [reset_contamination_module._BooleanPathState()],
    )

    assert len(parallel_states) == 1
    assert set(parallel_states[0].true_writes) == {("parallela", "")}
    assert set(parallel_states[0].false_writes) == {("parallelb", "")}
    assert reset_contamination_module._merge_boolean_parallel_branch_results([]) == []

    subsequence_states = reset_contamination_module._collect_boolean_seq_node_paths(
        SFCSubsequence(
            name="Nested",
            body=[
                SFCStep(
                    kind="step",
                    name="NestedStep",
                    code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("NestedFlag"), True)]),
                )
            ],
        ),
        env,
        [reset_contamination_module._BooleanPathState()],
    )
    transition_sub_states = reset_contamination_module._collect_boolean_seq_node_paths(
        SFCTransitionSub(
            name="NestedGate",
            body=[
                SFCStep(
                    kind="step",
                    name="GateStep",
                    code=SFCCodeBlocks(
                        active=[(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("GateFlag"), False])]
                    ),
                )
            ],
        ),
        env,
        [reset_contamination_module._BooleanPathState()],
    )

    assert set(subsequence_states[0].true_writes) == {("nestedflag", "")}
    assert set(transition_sub_states[0].false_writes) == {("gateflag", "")}


def test_implicit_latch_helpers_scan_nested_sfc_nodes_and_dedupe_issues():
    env = {
        "alarmlatched": Variable(name="AlarmLatched", datatype=Simple_DataType.BOOLEAN),
        "stepflag": Variable(name="StepFlag", datatype=Simple_DataType.BOOLEAN),
        "nestedflag": Variable(name="NestedFlag", datatype=Simple_DataType.BOOLEAN),
        "transitionflag": Variable(name="TransitionFlag", datatype=Simple_DataType.BOOLEAN),
    }
    issues: list[VariableIssue] = []
    seen: set[tuple[tuple[str, ...], str, str]] = set()
    nodes = [
        SFCStep(
            kind="step",
            name="LatchStep",
            code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("AlarmLatched"), True)]),
        ),
        SFCAlternative(
            branches=[
                [
                    SFCStep(
                        kind="step",
                        name="AltOne",
                        code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("StepFlag"), True)]),
                    )
                ],
                [
                    SFCStep(
                        kind="step",
                        name="AltTwo",
                        code=SFCCodeBlocks(
                            active=[(const.KEY_FUNCTION_CALL, "SetBooleanValue", [_varref("StepFlag"), False])]
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
                                code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("NestedFlag"), True)]),
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
                                code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("TransitionFlag"), True)]),
                            )
                        ],
                    )
                ],
            ]
        ),
    ]

    reset_contamination_module._scan_seq_nodes_for_latching(
        nodes,
        env,
        ["BasePicture", "Unit"],
        issues,
        seen,
        site="SEQ:Main",
        sequence_name="Main",
    )
    reset_contamination_module._scan_seq_nodes_for_latching(
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
