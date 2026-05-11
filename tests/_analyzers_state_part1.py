# ruff: noqa: F403, F405
from ._analyzers_state_test_support import *


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
