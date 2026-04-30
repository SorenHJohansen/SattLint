"""Tests for state-integrity analyzers.

Covers reset contamination, implicit latch, SFC step contract,
write-without-effect, hidden global coupling, global scope minimization,
high fan-in/out, and variables report summary.
"""

from types import SimpleNamespace

from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ParameterMapping,
    Sequence,
    SFCAlternative,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers import reset_contamination as reset_contamination_module
from sattlint.analyzers._variables_effect_flow import EffectFlowTracker
from sattlint.analyzers.sfc import analyze_sfc
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.reporting.variables_report import (
    ALL_VARIABLE_ANALYSIS_KINDS,
    VariableIssue,
    VariablesReport,
)
from sattlint.resolution.scope import ScopeContext


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(s: str) -> dict:
    return {const.KEY_VAR_NAME: s}


def _state_ref(name: str, state: str) -> dict:
    return {const.KEY_VAR_NAME: name, "state": state}


def _issue_kinds(report) -> set[str]:
    return {issue.kind for issue in report.issues}


def _status_bridge_typedef() -> ModuleTypeDef:
    return ModuleTypeDef(
        name="StatusBridge",
        moduleparameters=[Variable(name="OperationStatus", datatype=Simple_DataType.INTEGER)],
        localvariables=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Destination", datatype=Simple_DataType.INTEGER),
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="BridgeEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [_varref("Source"), _varref("Destination"), _varref("OperationStatus")],
                        )
                    ],
                )
            ]
        ),
    )


def test_reset_contamination_detected_for_missing_reset_write():
    seq = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[],
    )

    eq = Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            (
                const.GRAMMAR_VALUE_IF,
                [
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OperationSequence.Reset")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Counter"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OprSeqResetOld")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Other"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                ],
                [],
            ),
            (
                const.KEY_ASSIGN,
                _varref("OprSeqResetOld"),
                _varref("OperationSequence.Reset"),
            ),
        ],
    )

    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="Other", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="OprSeqResetOld", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(sequences=[seq], equations=[eq]),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [i for i in analyzer.issues if i.kind is IssueKind.RESET_CONTAMINATION]
    assert any(i.variable and i.variable.name == "Counter" for i in issues)


def test_reset_contamination_cleared_when_reset_writes_present():
    seq = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[],
    )

    eq = Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            (
                const.GRAMMAR_VALUE_IF,
                [
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OperationSequence.Reset")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Counter"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OprSeqResetOld")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Counter"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                ],
                [],
            ),
            (
                const.KEY_ASSIGN,
                _varref("OprSeqResetOld"),
                _varref("OperationSequence.Reset"),
            ),
        ],
    )

    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="OprSeqResetOld", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(sequences=[seq], equations=[eq]),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(i.kind is IssueKind.RESET_CONTAMINATION for i in analyzer.issues)


def test_reset_contamination_helpers_collect_refs_and_reset_old_vars_from_nested_nodes():
    modulecode = ModuleCode(
        sequences=[
            Sequence(
                name="OpSeq",
                type="sequence",
                position=(0.0, 0.0),
                size=(1.0, 1.0),
                code=[
                    SFCStep(
                        kind="step",
                        name="Start",
                        code=SFCCodeBlocks(enter=[(const.KEY_ASSIGN, _varref("SeqResetOld"), _varref("OpSeq.Reset"))]),
                    ),
                    SFCTransition(name="Gate", condition=(const.GRAMMAR_VALUE_NOT, _varref("OpSeq.Reset"))),
                    SFCAlternative(
                        branches=[
                            [(const.KEY_ASSIGN, _varref("AltResetOld"), _varref("OpSeq.Reset"))],
                            [
                                SFCSubsequence(
                                    name="Nested",
                                    body=[(const.KEY_ASSIGN, _varref("SubResetOld"), _varref("OpSeq.Reset"))],
                                )
                            ],
                        ]
                    ),
                    SFCParallel(
                        branches=[
                            [(const.KEY_ASSIGN, _varref("ParallelResetOld"), _varref("OpSeq.Reset"))],
                            [
                                SFCTransitionSub(
                                    name="NestedTransition",
                                    body=[(const.KEY_ASSIGN, _varref("TransResetOld"), _varref("OpSeq.Reset"))],
                                )
                            ],
                        ]
                    ),
                ],
            )
        ],
        equations=[
            Equation(
                name="Main",
                position=(0.0, 0.0),
                size=(1.0, 1.0),
                code=[(const.KEY_ASSIGN, _varref("EqResetOld"), _varref("OpSeq.Reset"))],
            )
        ],
    )

    refs = reset_contamination_module._collect_var_refs(modulecode)
    reset_old_vars = reset_contamination_module._collect_reset_old_vars(modulecode, "opseq.reset")

    assert "opseq.reset" in refs
    assert reset_old_vars == {
        "AltResetOld",
        "EqResetOld",
        "ParallelResetOld",
        "SeqResetOld",
        "SubResetOld",
        "TransResetOld",
    }


def test_reset_contamination_helpers_classify_conditions_and_infer_alternatives():
    reset_ref_cf = "opseq.reset"
    reset_old_vars_cf = {"opseqresetold"}

    run_flags = reset_contamination_module._classify_reset_condition(
        (const.GRAMMAR_VALUE_NOT, _varref("OpSeq.Reset")),
        reset_ref_cf,
        reset_old_vars_cf,
    )
    reset_flags = reset_contamination_module._classify_reset_condition(
        (const.GRAMMAR_VALUE_NOT, _varref("OpSeqResetOld")),
        reset_ref_cf,
        reset_old_vars_cf,
    )
    mixed_flags = reset_contamination_module._classify_reset_condition(
        [_varref("OpSeq.Reset"), (const.GRAMMAR_VALUE_NOT, _varref("OpSeq.Reset"))],
        reset_ref_cf,
        reset_old_vars_cf,
    )

    assert run_flags == {
        "run": True,
        "reset": False,
        "exact_run": True,
        "exact_reset": False,
    }
    assert reset_flags == {
        "run": False,
        "reset": True,
        "exact_run": False,
        "exact_reset": True,
    }
    assert mixed_flags["run"] is True
    assert mixed_flags["reset"] is True

    assert [
        state.reset_state
        for state in reset_contamination_module._take_condition_branch(
            reset_contamination_module._PathState(),
            run_flags,
        )
    ] == ["run"]
    assert [
        state.reset_state
        for state in reset_contamination_module._infer_alternative_states(
            reset_contamination_module._PathState(),
            saw_run=True,
            saw_reset=False,
            saw_exact_run=True,
            saw_exact_reset=False,
        )
    ] == ["reset"]
    assert [
        state.reset_state
        for state in reset_contamination_module._infer_alternative_states(
            reset_contamination_module._PathState(),
            saw_run=False,
            saw_reset=True,
            saw_exact_run=False,
            saw_exact_reset=True,
        )
    ] == ["run"]
    assert [
        state.reset_state
        for state in reset_contamination_module._infer_alternative_states(
            reset_contamination_module._PathState(),
            saw_run=True,
            saw_reset=False,
            saw_exact_run=False,
            saw_exact_reset=False,
        )
    ] == ["run", "reset"]
    assert (
        reset_contamination_module._infer_alternative_states(
            reset_contamination_module._PathState(),
            saw_run=True,
            saw_reset=True,
            saw_exact_run=True,
            saw_exact_reset=True,
        )
        == []
    )
    assert (
        reset_contamination_module._clone_with_reset_state(
            reset_contamination_module._PathState(reset_state="run"),
            "reset",
        )
        == []
    )


def test_reset_contamination_helpers_merge_parallel_paths_and_record_writes():
    counter = Variable(name="Counter", datatype=Simple_DataType.INTEGER)
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    destination = Variable(name="Destination", datatype=Simple_DataType.INTEGER)
    status = Variable(name="Status", datatype=Simple_DataType.INTEGER)
    flag = Variable(name="Flag", datatype=Simple_DataType.BOOLEAN)
    env = {
        "counter": counter,
        "source": source,
        "destination": destination,
        "status": status,
        "flag": flag,
    }

    run_state = reset_contamination_module._PathState(reset_state="run")
    reset_state = reset_contamination_module._PathState(reset_state="reset")
    unknown_state = reset_contamination_module._PathState(reset_state="unknown")
    reset_contamination_module._record_mode_write(_varref("Counter.Member"), env, run_state)
    reset_contamination_module._record_mode_write(_varref("Counter"), env, reset_state)
    reset_contamination_module._record_mode_function_call_writes(
        "CopyVariable",
        [_varref("Source"), _varref("Destination"), _varref("Status")],
        env,
        unknown_state,
    )

    merged = reset_contamination_module._merge_parallel_branch_results([[run_state], [unknown_state]])

    assert len(merged) == 1
    assert merged[0].reset_state == "run"
    assert set(merged[0].run_writes) == {
        ("counter", "member"),
        ("destination", ""),
        ("status", ""),
    }
    assert reset_contamination_module._merge_parallel_branch_results([[run_state], [reset_state]]) == []
    assert reset_contamination_module._path_covers_write(reset_state.reset_writes, ("counter", "member")) is True

    boolean_state = reset_contamination_module._BooleanPathState()
    reset_contamination_module._record_boolean_assignment(_varref("Flag"), True, env, boolean_state)
    reset_contamination_module._record_boolean_function_call(
        "SetBooleanValue",
        [_varref("Flag"), False],
        env,
        boolean_state,
    )
    reset_contamination_module._record_boolean_function_call(
        "SetBooleanValue",
        [_varref("Flag.Member"), True],
        env,
        boolean_state,
    )

    assert set(boolean_state.true_writes) == {("flag", "")}
    assert set(boolean_state.false_writes) == {("flag", "")}


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


def test_implicit_latch_detected_when_if_branch_sets_true_without_else_clear():
    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="AlarmLatched", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [
                                (
                                    _varref("Start"),
                                    [
                                        (
                                            const.KEY_ASSIGN,
                                            _varref("AlarmLatched"),
                                            True,
                                        )
                                    ],
                                )
                            ],
                            [],
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [i for i in analyzer.issues if i.kind is IssueKind.IMPLICIT_LATCH]
    assert len(issues) == 1
    assert issues[0].variable is not None
    assert issues[0].variable.name == "AlarmLatched"
    assert issues[0].site == "EQ:Main > IF"


def test_implicit_latch_not_reported_when_else_branch_clears_false():
    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="AlarmLatched", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [
                                (
                                    _varref("Start"),
                                    [
                                        (
                                            const.KEY_ASSIGN,
                                            _varref("AlarmLatched"),
                                            True,
                                        )
                                    ],
                                )
                            ],
                            [
                                (
                                    const.KEY_ASSIGN,
                                    _varref("AlarmLatched"),
                                    False,
                                )
                            ],
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(i.kind is IssueKind.IMPLICIT_LATCH for i in analyzer.issues)


def test_implicit_latch_detected_in_root_modulecode():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="AlarmLatched", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [(_varref("Start"), [(const.KEY_ASSIGN, _varref("AlarmLatched"), True)])],
                            [],
                        )
                    ],
                )
            ]
        ),
        moduledef=None,
    )

    issues = VariablesAnalyzer(bp).run()

    latch_issues = [issue for issue in issues if issue.kind is IssueKind.IMPLICIT_LATCH]
    assert len(latch_issues) == 1
    assert latch_issues[0].module_path == ["Root"]
    assert latch_issues[0].site == "EQ:Main > IF"


def test_limit_to_module_path_restricts_state_integrity_checks_to_matching_subtree():
    def _latching_module(name: str) -> SingleModule:
        return SingleModule(
            header=_hdr(name),
            moduledef=None,
            moduleparameters=[],
            localvariables=[
                Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
                Variable(name="AlarmLatched", datatype=Simple_DataType.BOOLEAN),
            ],
            submodules=[],
            modulecode=ModuleCode(
                equations=[
                    Equation(
                        name="Main",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            (
                                const.GRAMMAR_VALUE_IF,
                                [(_varref("Start"), [(const.KEY_ASSIGN, _varref("AlarmLatched"), True)])],
                                [],
                            )
                        ],
                    )
                ]
            ),
            parametermappings=[],
        )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[_latching_module("UnitA"), _latching_module("UnitB")],
        modulecode=None,
        moduledef=None,
    )

    issues = VariablesAnalyzer(bp).run(limit_to_module_path=["Root", "UnitA"])

    latch_paths = [issue.module_path for issue in issues if issue.kind is IssueKind.IMPLICIT_LATCH]
    assert latch_paths == [["Root", "UnitA"]]


def test_frame_module_children_are_included_in_state_integrity_checks():
    child = SingleModule(
        header=_hdr("Nested"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="AlarmLatched", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [(_varref("Start"), [(const.KEY_ASSIGN, _varref("AlarmLatched"), True)])],
                            [],
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
    )
    frame = FrameModule(
        header=_hdr("Frame"),
        datecode=None,
        submodules=[child],
        modulecode=None,
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[frame],
        modulecode=None,
        moduledef=None,
    )

    issues = VariablesAnalyzer(bp).run()

    latch_issues = [issue for issue in issues if issue.kind is IssueKind.IMPLICIT_LATCH]
    assert len(latch_issues) == 1
    assert latch_issues[0].module_path == ["Root", "Frame", "Nested"]


def test_implicit_latch_detected_for_step_without_exit_clear():
    seq = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Run",
                code=SFCCodeBlocks(
                    active=[
                        (
                            const.KEY_ASSIGN,
                            _varref("StepFlag"),
                            True,
                        )
                    ],
                    exit=[],
                ),
            )
        ],
    )

    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="StepFlag", datatype=Simple_DataType.BOOLEAN)],
        submodules=[],
        modulecode=ModuleCode(sequences=[seq], equations=[]),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [i for i in analyzer.issues if i.kind is IssueKind.IMPLICIT_LATCH]
    assert len(issues) == 1
    assert issues[0].variable is not None
    assert issues[0].variable.name == "StepFlag"
    assert issues[0].site == "SEQ:OperationSequence > STEP:Run"


def test_sfc_step_contract_detects_missing_enter_initialization():
    sequence = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Run",
                code=SFCCodeBlocks(
                    enter=[],
                    active=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Output"),
                            _varref("StepValue"),
                        )
                    ],
                    exit=[],
                ),
            )
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="StepValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(
        bp,
        step_contracts={
            "Run": {"required_enter_writes": ["StepValue"]},
        },
    )

    issues = [issue for issue in report.issues if issue.kind == "sfc_missing_step_enter_contract"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["missing_enter_writes"] == ["StepValue"]


def test_sfc_step_contract_detects_missing_exit_cleanup():
    sequence = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Run",
                code=SFCCodeBlocks(
                    enter=[
                        (
                            const.KEY_ASSIGN,
                            _varref("StepValue"),
                            1,
                        )
                    ],
                    active=[],
                    exit=[],
                ),
            )
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="StepValue", datatype=Simple_DataType.INTEGER)],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(
        bp,
        step_contracts={
            "Run": {"required_exit_writes": ["StepValue"]},
        },
    )

    issues = [issue for issue in report.issues if issue.kind == "sfc_missing_step_exit_contract"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["missing_exit_writes"] == ["StepValue"]


def test_sfc_step_contract_detects_state_leakage_across_steps():
    sequence = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Prime",
                code=SFCCodeBlocks(
                    active=[
                        (
                            const.KEY_ASSIGN,
                            _varref("StepValue"),
                            1,
                        )
                    ]
                ),
            ),
            SFCStep(
                kind="step",
                name="Run",
                code=SFCCodeBlocks(
                    enter=[],
                    active=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Output"),
                            _varref("StepValue"),
                        )
                    ],
                    exit=[],
                ),
            ),
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="StepValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(
        bp,
        step_contracts={
            "Run": {"required_enter_writes": ["StepValue"]},
        },
    )

    issues = [issue for issue in report.issues if issue.kind == "sfc_step_state_leakage"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["leaked_state"] == ["StepValue"]


def test_write_without_effect_detected_for_internal_value_chain():
    child = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Stage1", datatype=Simple_DataType.INTEGER),
            Variable(name="Stage2", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Stage1"), 1),
                        (const.KEY_ASSIGN, _varref("Stage2"), _varref("Stage1")),
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    write_without_effect = [issue for issue in analyzer.issues if issue.kind is IssueKind.WRITE_WITHOUT_EFFECT]
    assert [issue.variable.name for issue in write_without_effect if issue.variable is not None] == ["Stage1"]
    assert any(
        issue.kind is IssueKind.NEVER_READ and issue.variable is not None and issue.variable.name == "Stage2"
        for issue in analyzer.issues
    )


def test_write_without_effect_is_suppressed_for_mapped_output_path():
    child = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[Variable(name="Out", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Internal", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Internal"), 1),
                        (const.KEY_ASSIGN, _varref("Out"), _varref("Internal")),
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("Out"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("FinalOutput"),
                source_literal=None,
            )
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="FinalOutput", datatype=Simple_DataType.INTEGER)],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.WRITE_WITHOUT_EFFECT
        and issue.variable is not None
        and issue.variable.name in {"Internal", "Out"}
        for issue in analyzer.issues
    )


def test_hidden_global_coupling_is_reported_for_sibling_modules_using_root_global():
    shared_value = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)

    writer = SingleModule(
        header=_hdr("Writer"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="WriteShared",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("SharedValue"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    reader = SingleModule(
        header=_hdr("Reader"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadShared",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[shared_value],
        submodules=[writer, reader],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    hidden_issues = [
        issue
        for issue in analyzer.issues
        if issue.kind is IssueKind.HIDDEN_GLOBAL_COUPLING and issue.variable is shared_value
    ]
    assert len(hidden_issues) == 1
    assert "Writer (write)" in (hidden_issues[0].role or "")
    assert "Reader (read)" in (hidden_issues[0].role or "")


def test_hidden_global_coupling_is_not_reported_for_explicit_parameter_mappings():
    writer = SingleModule(
        header=_hdr("Writer"),
        moduledef=None,
        moduleparameters=[Variable(name="Out", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Produce",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Out"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("Out"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("SharedValue"),
                source_literal=None,
            )
        ],
    )
    reader = SingleModule(
        header=_hdr("Reader"),
        moduledef=None,
        moduleparameters=[Variable(name="In", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Consume",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("In"))],
                )
            ],
            sequences=[],
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("In"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("SharedValue"),
                source_literal=None,
            )
        ],
    )
    coordinator = SingleModule(
        header=_hdr("Coordinator"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)],
        submodules=[writer, reader],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        submodules=[coordinator],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(issue.kind is IssueKind.HIDDEN_GLOBAL_COUPLING for issue in analyzer.issues)


def test_global_scope_minimization_is_reported_for_root_global_confined_to_one_module_subtree():
    confined = Variable(name="ConfinedValue", datatype=Simple_DataType.INTEGER)

    worker = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[
            SingleModule(
                header=_hdr("Nested"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="WriteConfined",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("ConfinedValue"), 1)],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            )
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadConfined",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("ConfinedValue"))],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[confined],
        submodules=[worker],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [
        issue
        for issue in analyzer.issues
        if issue.kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION and issue.variable is confined
    ]

    assert len(issues) == 1
    assert "Worker" in (issues[0].role or "")
    assert "Nested" in (issues[0].role or "")


def test_global_scope_minimization_is_not_reported_for_root_global_used_in_root_scope():
    confined = Variable(name="ConfinedValue", datatype=Simple_DataType.INTEGER)

    worker = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="WriteConfined",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("ConfinedValue"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[confined, Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[worker],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadAtRoot",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("ConfinedValue"))],
                )
            ],
            sequences=[],
        ),
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION and issue.variable is confined for issue in analyzer.issues
    )


def test_global_scope_minimization_is_suppressed_for_library_targets():
    confined = Variable(name="ConfinedValue", datatype=Simple_DataType.INTEGER)

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[confined],
        submodules=[
            SingleModule(
                header=_hdr("Worker"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="UseConfined",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[
                                (const.KEY_ASSIGN, _varref("ConfinedValue"), 1),
                                (const.KEY_ASSIGN, _varref("Observed"), _varref("ConfinedValue")),
                            ],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(issue.kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION for issue in analyzer.issues)
    assert not any(issue.kind is IssueKind.HIDDEN_GLOBAL_COUPLING for issue in analyzer.issues)


def test_high_fan_in_out_is_reported_for_root_global_shared_across_many_modules():
    shared = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)

    writer = SingleModule(
        header=_hdr("Writer"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="WriteShared",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("SharedValue"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    reader_a = SingleModule(
        header=_hdr("ReaderA"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadSharedA",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    reader_b = SingleModule(
        header=_hdr("ReaderB"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadSharedB",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    reader_c = SingleModule(
        header=_hdr("ReaderC"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadSharedC",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[shared],
        submodules=[writer, reader_a, reader_b, reader_c],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [
        issue for issue in analyzer.issues if issue.kind is IssueKind.HIGH_FAN_IN_OUT and issue.variable is shared
    ]

    assert len(issues) == 1
    assert "high fan-in with 3 readers" in (issues[0].role or "")
    assert "ReaderA" in (issues[0].role or "")
    assert "ReaderB" in (issues[0].role or "")
    assert "ReaderC" in (issues[0].role or "")


def test_high_fan_in_out_is_not_reported_below_threshold():
    shared = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[shared],
        submodules=[
            SingleModule(
                header=_hdr("Writer"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="WriteShared",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("SharedValue"), 1)],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            ),
            SingleModule(
                header=_hdr("ReaderA"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="ReadSharedA",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            ),
            SingleModule(
                header=_hdr("ReaderB"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="ReadSharedB",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(issue.kind is IssueKind.HIGH_FAN_IN_OUT and issue.variable is shared for issue in analyzer.issues)


def test_variables_report_summary_includes_name_collisions():
    variable = Variable(name="Value", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.NAME_COLLISION,
        module_path=["BasePicture", "TypeDef:Unit"],
        variable=variable,
        role="name collision with parameter 'Value'",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Sections:" in summary
    assert "  - Name collisions: 1" in summary
    assert "Name collisions" in summary
    assert ("BasePicture.TypeDef:Unit :: Value (integer) | name collision with parameter 'Value'") in summary


def test_variables_report_summary_includes_write_without_effect_section():
    variable = Variable(name="Stage1", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.WRITE_WITHOUT_EFFECT,
        module_path=["BasePicture", "Worker"],
        variable=variable,
        role="localvariable",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Write-without-effect variables" in summary
    assert "  - Write-without-effect variables: 1" in summary
    assert "Stage1" in summary


def test_variables_report_summary_includes_hidden_global_coupling_section():
    variable = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.HIDDEN_GLOBAL_COUPLING,
        module_path=["BasePicture"],
        variable=variable,
        role="hidden global coupling across modules: Writer (write), Reader (read)",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Hidden global coupling" in summary
    assert "SharedValue" in summary


def test_variables_report_summary_includes_high_fan_in_out_section():
    variable = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.HIGH_FAN_IN_OUT,
        module_path=["BasePicture"],
        variable=variable,
        role="high fan-in with 3 readers: ReaderA, ReaderB, ReaderC",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "High fan-in or fan-out variables" in summary
    assert "SharedValue" in summary


def test_variables_report_summary_includes_global_scope_minimization_section():
    variable = Variable(name="ConfinedValue", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.GLOBAL_SCOPE_MINIMIZATION,
        module_path=["BasePicture"],
        variable=variable,
        role="global scope can be reduced to module subtree Worker: Worker, Worker.Nested",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Global scope minimization candidates" in summary
    assert "ConfinedValue" in summary


def test_variables_report_summary_includes_ui_only_section():
    variable = Variable(name="DisplayValue", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.UI_ONLY,
        module_path=["BasePicture", "Panel"],
        variable=variable,
        role="localvariable",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "UI/display-only variables" in summary
    assert "DisplayValue" in summary


def test_variables_report_summary_includes_unknown_parameter_targets():
    issue = VariableIssue(
        kind=IssueKind.UNKNOWN_PARAMETER_TARGET,
        module_path=["BasePicture", "Child"],
        variable=None,
        role="unknown parameter mapping target 'MissingValue'",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Unknown parameter mapping targets" in summary
    assert "BasePicture.Child :: unknown parameter mapping target 'MissingValue'" in summary


def test_variables_report_summary_lists_all_requested_categories_when_empty():
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[],
        visible_kinds=frozenset(ALL_VARIABLE_ANALYSIS_KINDS),
        include_empty_sections=True,
    )

    summary = report.summary()

    assert "Issues: 0" in summary
    assert "Sections:" in summary
    assert "  - Unused variables: 0" in summary
    assert "Unused variables" in summary
    assert "Unused fields in datatypes" in summary
    assert "Read-only but not Const variables" in summary
    assert "UI/display-only variables" in summary
    assert "Procedure status handling" in summary
    assert "Written but never read variables" in summary
    assert "Global scope minimization candidates" in summary
    assert "Hidden global coupling" in summary
    assert "Unknown parameter mapping targets" in summary
    assert "String mapping type mismatches" in summary
    assert "Duplicated complex datatypes (should be RECORD)" in summary
    assert "Min/Max mapping name mismatches" in summary
    assert "Magic numbers in code" in summary
    assert "Name collisions" in summary
    assert "Reset contamination (missing reset writes)" in summary
    assert "Implicit latching (missing matching False writes)" in summary
    assert summary.count("      none") == len(ALL_VARIABLE_ANALYSIS_KINDS)


def test_variables_report_summary_keeps_filtered_empty_output_scoped():
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[],
        visible_kinds=frozenset({IssueKind.RESET_CONTAMINATION}),
        include_empty_sections=True,
    )

    summary = report.summary()

    assert "Issues: 0" in summary
    assert "Sections:" in summary
    assert "  - Reset contamination (missing reset writes): 0" in summary
    assert "Reset contamination (missing reset writes)" in summary
    assert "      none" in summary
    assert "Unused variables" not in summary


def test_variable_issue_str_formats_datatype_literal_and_role_only_variants():
    datatype_issue = VariableIssue(
        kind=IssueKind.UNUSED_DATATYPE_FIELD,
        module_path=["BasePicture", "UnitA"],
        variable=None,
        datatype_name="Payload",
        field_path="Value",
    )
    literal_issue = VariableIssue(
        kind=IssueKind.MAGIC_NUMBER,
        module_path=["BasePicture", "UnitA"],
        variable=None,
        literal_value=42,
        literal_span=SourceSpan(line=9, column=4),
        site="EquationBlock",
    )
    role_issue = VariableIssue(
        kind=IssueKind.UNKNOWN_PARAMETER_TARGET,
        module_path=["BasePicture", "Child"],
        variable=None,
        role="missing target",
    )

    assert str(datatype_issue) == "[BasePicture.UnitA] datatype 'Payload'.Value"
    assert str(literal_issue) == "[BasePicture.UnitA] magic number 42"
    assert str(role_issue) == "[BasePicture.Child] missing target"


def test_variables_report_summary_formats_string_mapping_and_minmax_tables():
    string_source = Variable(name="SourceText", datatype=Simple_DataType.STRING)
    string_target = Variable(name="TargetText", datatype=Simple_DataType.TAGSTRING)
    min_source = Variable(name="SourceMin", datatype=Simple_DataType.REAL)
    min_target = Variable(name="TargetMax", datatype=Simple_DataType.REAL)
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[
            VariableIssue(
                kind=IssueKind.STRING_MAPPING_MISMATCH,
                module_path=["BasePicture", "ChildA"],
                variable=string_target,
                source_variable=string_source,
            ),
            VariableIssue(
                kind=IssueKind.MIN_MAX_MAPPING_MISMATCH,
                module_path=["BasePicture", "ChildB"],
                variable=min_target,
                source_variable=min_source,
            ),
        ],
    )

    summary = report.summary()

    assert "String mapping type mismatches" in summary
    assert "Min/Max mapping name mismatches" in summary
    assert "Source Var" in summary
    assert "Target Var" in summary
    assert "BasePicture.ChildA" in summary
    assert "SourceText" in summary
    assert "TargetText" in summary
    assert "BasePicture.ChildB" in summary
    assert "SourceMin" in summary
    assert "TargetMax" in summary


def test_variables_report_summary_formats_duplication_magic_numbers_and_sequence_context():
    duplicated = Variable(name="ValueA", datatype="SharedRecord")
    implicit = Variable(name="Stage1", datatype=Simple_DataType.BOOLEAN)
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[
            VariableIssue(
                kind=IssueKind.DATATYPE_DUPLICATION,
                module_path=["BasePicture", "UnitA"],
                variable=duplicated,
                role="localvariable",
                duplicate_count=3,
                duplicate_locations=[
                    (["BasePicture", "UnitA"], "moduleparameter", "ValueB"),
                    (["BasePicture", "UnitB"], "localvariable", "ValueC"),
                ],
            ),
            VariableIssue(
                kind=IssueKind.MAGIC_NUMBER,
                module_path=["BasePicture", "UnitA"],
                variable=None,
                literal_value=42,
                literal_span=SourceSpan(line=9, column=4),
                site="EquationBlock",
            ),
            VariableIssue(
                kind=IssueKind.IMPLICIT_LATCH,
                module_path=["BasePicture", "SequenceA"],
                variable=implicit,
                role="localvariable",
                sequence_name="MainSeq",
                reset_variable="ResetCmd",
            ),
        ],
    )

    summary = report.summary()

    assert "Duplicated complex datatypes (should be RECORD)" in summary
    assert "Datatype 'SharedRecord' declared 3 times in BasePicture.UnitA:" in summary
    assert "- ValueA (localvariable)" in summary
    assert "+ ValueB (moduleparameter)" in summary
    assert "+ BasePicture.UnitB: ValueC (localvariable)" in summary
    assert "Magic numbers in code" in summary
    assert "BasePicture.UnitA [EquationBlock] :: 42 (line 9, col 4)" in summary
    assert "Implicit latching (missing matching False writes)" in summary
    assert "BasePicture.SequenceA :: localvariable Stage1 (boolean) | sequence=MainSeq | reset=ResetCmd" in summary


def test_variables_report_summary_includes_required_contract_layout_and_shadowing_sections():
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[
            VariableIssue(
                kind=IssueKind.REQUIRED_PARAMETER_CONNECTION,
                module_path=["BasePicture", "ChildA"],
                variable=None,
                role="required parameter 'Mode' is not connected",
            ),
            VariableIssue(
                kind=IssueKind.CONTRACT_MISMATCH,
                module_path=["BasePicture", "ChildB"],
                variable=Variable(name="TargetValue", datatype=Simple_DataType.INTEGER),
                source_variable=Variable(name="SourceValue", datatype=Simple_DataType.REAL),
                role="source and target types differ",
            ),
            VariableIssue(
                kind=IssueKind.LAYOUT_OVERLAP,
                module_path=["BasePicture", "Panel"],
                variable=None,
                role="TextA overlaps TextB",
            ),
            VariableIssue(
                kind=IssueKind.SHADOWING,
                module_path=["BasePicture", "ChildC"],
                variable=Variable(name="Mode", datatype=Simple_DataType.INTEGER),
                role="local shadows moduleparameter",
            ),
        ],
        visible_kinds=frozenset(
            {
                IssueKind.REQUIRED_PARAMETER_CONNECTION,
                IssueKind.CONTRACT_MISMATCH,
                IssueKind.LAYOUT_OVERLAP,
                IssueKind.SHADOWING,
            }
        ),
    )

    summary = report.summary()

    assert isinstance(report.visible_kinds, frozenset)
    assert "Missing required parameter connections" in summary
    assert "BasePicture.ChildA :: required parameter 'Mode' is not connected" in summary
    assert "Cross-module contract mismatches" in summary
    assert "BasePicture.ChildB :: TargetValue (integer) | source and target types differ" in summary
    assert "Overlapping layout elements" in summary
    assert "BasePicture.Panel :: TextA overlaps TextB" in summary
    assert "Variable shadowing" in summary
    assert "BasePicture.ChildC :: Mode (integer) | local shadows moduleparameter" in summary


def test_variables_report_properties_visible_kinds_and_empty_sections_cover_remaining_branches():
    issues = [
        VariableIssue(kind=IssueKind.UNUSED, module_path=["BasePicture", "Unused"], variable=Variable("A", "integer")),
        VariableIssue(
            kind=IssueKind.UNUSED_DATATYPE_FIELD,
            module_path=["BasePicture", "Datatype"],
            variable=None,
            datatype_name="Payload",
            field_path="FieldA",
        ),
        VariableIssue(
            kind=IssueKind.READ_ONLY_NON_CONST,
            module_path=["BasePicture", "ReadOnly"],
            variable=Variable("B", "integer"),
        ),
        VariableIssue(
            kind=IssueKind.NAMING_ROLE_MISMATCH,
            module_path=["BasePicture", "Naming"],
            variable=Variable("ValveStatus", "boolean"),
            role="name suggests state but only drives command",
        ),
        VariableIssue(
            kind=IssueKind.UI_ONLY,
            module_path=["BasePicture", "Display"],
            variable=Variable("Caption", Simple_DataType.STRING),
        ),
        VariableIssue(
            kind=IssueKind.PROCEDURE_STATUS,
            module_path=["BasePicture", "Procedure"],
            variable=Variable("OperationStatus", "integer"),
        ),
        VariableIssue(
            kind=IssueKind.NEVER_READ,
            module_path=["BasePicture", "NeverRead"],
            variable=Variable("WrittenOnly", "integer"),
        ),
        VariableIssue(
            kind=IssueKind.WRITE_WITHOUT_EFFECT,
            module_path=["BasePicture", "WriteOnly"],
            variable=Variable("NoEffect", "integer"),
        ),
        VariableIssue(
            kind=IssueKind.GLOBAL_SCOPE_MINIMIZATION,
            module_path=["BasePicture", "Global"],
            variable=Variable("GlobalA", "integer"),
        ),
        VariableIssue(
            kind=IssueKind.HIDDEN_GLOBAL_COUPLING,
            module_path=["BasePicture", "Coupling"],
            variable=Variable("SharedState", "integer"),
        ),
        VariableIssue(
            kind=IssueKind.HIGH_FAN_IN_OUT,
            module_path=["BasePicture", "Fan"],
            variable=Variable("Busy", "boolean"),
            role="fan-out exceeds threshold",
        ),
        VariableIssue(
            kind=IssueKind.UNKNOWN_PARAMETER_TARGET,
            module_path=["BasePicture", "Mapping"],
            variable=None,
            role="unknown target parameter 'Mode'",
        ),
        VariableIssue(
            kind=IssueKind.REQUIRED_PARAMETER_CONNECTION,
            module_path=["BasePicture", "Required"],
            variable=None,
            role="required parameter 'Enable' is not connected",
        ),
        VariableIssue(
            kind=IssueKind.CONTRACT_MISMATCH,
            module_path=["BasePicture", "Contract"],
            variable=Variable("Target", Simple_DataType.INTEGER),
            source_variable=Variable("Source", Simple_DataType.REAL),
            role="contract mismatch",
        ),
        VariableIssue(
            kind=IssueKind.STRING_MAPPING_MISMATCH,
            module_path=["BasePicture", "Strings"],
            variable=Variable("TargetText", Simple_DataType.TAGSTRING),
            source_variable=Variable("SourceText", Simple_DataType.STRING),
        ),
        VariableIssue(
            kind=IssueKind.DATATYPE_DUPLICATION,
            module_path=["BasePicture", "Dup"],
            variable=Variable("LocalA", "Payload"),
            role="localvariable",
            duplicate_count=2,
            duplicate_locations=[(["BasePicture", "Dup"], "moduleparameter", "ParamA")],
        ),
        VariableIssue(
            kind=IssueKind.MIN_MAX_MAPPING_MISMATCH,
            module_path=["BasePicture", "MinMax"],
            variable=Variable("TargetMax", Simple_DataType.REAL),
            source_variable=Variable("SourceMin", Simple_DataType.REAL),
        ),
        VariableIssue(
            kind=IssueKind.MAGIC_NUMBER,
            module_path=["BasePicture", "Magic"],
            variable=None,
            literal_value=7,
            literal_span=SourceSpan(12, 8),
            site="EquationBlock",
        ),
        VariableIssue(
            kind=IssueKind.LAYOUT_OVERLAP,
            module_path=["BasePicture", "Layout"],
            variable=None,
            role="LabelA overlaps LabelB",
        ),
        VariableIssue(
            kind=IssueKind.RESET_CONTAMINATION,
            module_path=["BasePicture", "Reset"],
            variable=Variable("Counter", "integer"),
        ),
        VariableIssue(
            kind=IssueKind.IMPLICIT_LATCH,
            module_path=["BasePicture", "Latch"],
            variable=Variable("State", Simple_DataType.BOOLEAN),
            role="localvariable",
            sequence_name="SeqA",
            reset_variable="ResetCmd",
        ),
    ]
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=issues,
        visible_kinds=frozenset((*ALL_VARIABLE_ANALYSIS_KINDS, IssueKind.NAME_COLLISION, IssueKind.SHADOWING)),
    )

    selector_expectations = {
        "unused": 1,
        "unused_datatype_fields": 1,
        "read_only_non_const": 1,
        "naming_role_mismatch": 1,
        "ui_only": 1,
        "procedure_status": 1,
        "never_read": 1,
        "write_without_effect": 1,
        "global_scope_minimization": 1,
        "hidden_global_coupling": 1,
        "high_fan_in_out": 1,
        "unknown_parameter_targets": 1,
        "required_parameter_connections": 1,
        "contract_mismatches": 1,
        "string_mapping_mismatch": 1,
        "datatype_duplication": 1,
        "min_max_mapping_mismatch": 1,
        "magic_numbers": 1,
        "name_collisions": 0,
        "layout_overlaps": 1,
        "shadowing": 0,
        "reset_contamination": 1,
        "implicit_latches": 1,
    }

    for attr_name, expected_count in selector_expectations.items():
        assert len(getattr(report, attr_name)) == expected_count

    summary = report.summary()

    assert report.name == "BasePicture"
    assert summary.startswith("Report: Variable issues")
    assert "Status: issues" in summary
    assert "Name collisions: 0" in summary
    assert "Variable shadowing: 0" in summary
    assert "Read-only but not Const variables" in summary
    assert "Naming-to-behavior mismatches" in summary
    assert "UI/display-only variables" in summary
    assert "Procedure status handling" in summary
    assert "Written but never read variables" in summary
    assert "Write-without-effect variables" in summary
    assert "Global scope minimization candidates" in summary
    assert "Hidden global coupling" in summary
    assert "High fan-in or fan-out variables" in summary
    assert "Reset contamination (missing reset writes)" in summary
    assert "      none" in summary


def test_variables_report_summary_returns_ok_when_no_issues_are_present():
    summary = VariablesReport(basepicture_name="BasePicture", issues=[]).summary()

    assert "Status: ok" in summary
    assert summary.endswith("No issues found.")


def test_effect_flow_tracker_computes_effective_outputs_via_reverse_edges():
    edges = {
        ("root", "source"): {("root", "mid")},
        ("root", "mid"): {("root", "sink")},
    }
    tracker = EffectFlowTracker(
        effect_flow_edges=edges,
        effect_flow_display_names={},
        external_effect_sinks=set(),
        effective_output_keys=set(),
        lookup_global_variable_fn=lambda _name: None,
        get_usage_fn=lambda _var: None,
        canonical_path_fn=lambda _path, _var, _field: None,
        record_access_fn=lambda _kind, _path, _ctx, _ref: None,
    )

    effective = tracker.compute_effective_output_keys({("root", "sink")})

    assert effective == {
        ("root", "source"),
        ("root", "mid"),
        ("root", "sink"),
    }


def test_effect_flow_tracker_copyvariable_inputs_only_include_source():
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    target = Variable(name="Target", datatype=Simple_DataType.INTEGER)
    context = ScopeContext(
        env={"source": source, "target": target},
        param_mappings={},
        module_path=["Root"],
        display_module_path=["Root"],
        parent_context=None,
    )
    tracker = EffectFlowTracker(
        effect_flow_edges={},
        effect_flow_display_names={},
        external_effect_sinks=set(),
        effective_output_keys=set(),
        lookup_global_variable_fn=lambda _name: None,
        get_usage_fn=lambda _var: None,
        canonical_path_fn=lambda _path, _var, _field: None,
        record_access_fn=lambda _kind, _path, _ctx, _ref: None,
    )

    sources = tracker.collect_function_input_effect_keys(
        "CopyVariable",
        [_varref("Source"), _varref("Target")],
        context,
    )
    init_sources = tracker.collect_function_input_effect_keys("InitVariable", [_varref("Source")], context)

    assert sources == {("root", "source")}
    assert init_sources == set()


def test_effect_flow_tracker_global_mapping_uses_lookup_fallback():
    resolved_global = Variable(name="ResolvedGlobal", datatype=Simple_DataType.INTEGER)
    tracker = EffectFlowTracker(
        effect_flow_edges={},
        effect_flow_display_names={},
        external_effect_sinks=set(),
        effective_output_keys=set(),
        lookup_global_variable_fn=lambda name: resolved_global if name == "GlobalSource" else None,
        get_usage_fn=lambda _var: None,
        canonical_path_fn=lambda _path, _var, _field: None,
        record_access_fn=lambda _kind, _path, _ctx, _ref: None,
    )

    key = tracker.mapping_source_effect_key(
        ParameterMapping(
            target=_varref("Input"),
            source_type=const.TREE_TAG_VARIABLE_NAME,
            is_duration=False,
            is_source_global=True,
            source=_varref("GlobalSource"),
            source_literal=None,
        ),
        parent_env={},
        parent_context=None,
    )

    assert key == ("globalsource", "resolvedglobal")


def test_effect_flow_tracker_records_copyvariable_output_edge():
    from collections import defaultdict

    edges = defaultdict(set)
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    target = Variable(name="Target", datatype=Simple_DataType.INTEGER)
    context = ScopeContext(
        env={"source": source, "target": target},
        param_mappings={},
        module_path=["Root"],
        display_module_path=["Root"],
        parent_context=None,
    )
    tracker = EffectFlowTracker(
        effect_flow_edges=edges,
        effect_flow_display_names={},
        external_effect_sinks=set(),
        effective_output_keys=set(),
        lookup_global_variable_fn=lambda _name: None,
        get_usage_fn=lambda _var: None,
        canonical_path_fn=lambda _path, _var, _field: None,
        record_access_fn=lambda _kind, _path, _ctx, _ref: None,
    )

    tracker.record_function_call_effect_flow(
        "CopyVariable",
        [_varref("Source"), _varref("Target")],
        context,
    )

    assert edges == {("root", "source"): {("root", "target")}}
