from sattline_parser.models.expressions import Assignment, IfStmt, NotOp

from sattlint.analyzers.reset_contamination import ResetContaminationAnalyzer
from sattlint.analyzers.reset_contamination._reset_latching import (
    BooleanPathState,
    record_boolean_assignment,
    record_boolean_function_call,
)
from sattlint.analyzers.reset_contamination._reset_path_collection import (
    classify_reset_condition,
    clone_with_reset_state,
    infer_alternative_states,
    path_covers_write,
    record_mode_function_call_writes,
    record_mode_write,
    take_condition_branch,
)
from sattlint.analyzers.reset_contamination._reset_path_state import (
    PathState,
    merge_parallel_branch_results,
)
from tests.helpers.analyzers_state_support import *


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
            IfStmt(  # pyright: ignore[reportArgumentType]
                branches=(
                    (
                        NotOp(operand=_varref("OperationSequence.Reset")),
                        (Assignment(target=_varref("Counter"), value=_varref("ResetValue")),),
                    ),
                    (
                        NotOp(operand=_varref("OprSeqResetOld")),
                        (Assignment(target=_varref("Other"), value=_varref("ResetValue")),),
                    ),
                ),
                else_block=(),
            ),
            Assignment(  # pyright: ignore[reportArgumentType]
                target=_varref("OprSeqResetOld"),
                value=_varref("OperationSequence.Reset"),
            ),
        ],
    )

    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=ScalarDatatype.INTEGER),
            Variable(name="Other", datatype=ScalarDatatype.INTEGER),
            Variable(name="ResetValue", datatype=ScalarDatatype.INTEGER),
            Variable(name="OprSeqResetOld", datatype=ScalarDatatype.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(sequences=[seq], equationblocks=[eq]),
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
            IfStmt(  # pyright: ignore[reportArgumentType]
                branches=(
                    (
                        NotOp(operand=_varref("OperationSequence.Reset")),
                        (Assignment(target=_varref("Counter"), value=_varref("ResetValue")),),
                    ),
                    (
                        NotOp(operand=_varref("OprSeqResetOld")),
                        (Assignment(target=_varref("Counter"), value=_varref("ResetValue")),),
                    ),
                ),
                else_block=(),
            ),
            Assignment(  # pyright: ignore[reportArgumentType]
                target=_varref("OprSeqResetOld"),
                value=_varref("OperationSequence.Reset"),
            ),
        ],
    )

    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=ScalarDatatype.INTEGER),
            Variable(name="ResetValue", datatype=ScalarDatatype.INTEGER),
            Variable(name="OprSeqResetOld", datatype=ScalarDatatype.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(sequences=[seq], equationblocks=[eq]),
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
                        code=SFCCodeBlocks(
                            enter=[Assignment(target=_varref("SeqResetOld"), value=_varref("OpSeq.Reset"))]
                        ),  # pyright: ignore[reportArgumentType]
                    ),
                    SFCTransition(name="Gate", condition=NotOp(operand=_varref("OpSeq.Reset"))),
                    SFCAlternative(
                        branches=[
                            [Assignment(target=_varref("AltResetOld"), value=_varref("OpSeq.Reset"))],  # pyright: ignore[reportArgumentType]
                            [
                                SFCSubsequence(
                                    name="Nested",
                                    body=[Assignment(target=_varref("SubResetOld"), value=_varref("OpSeq.Reset"))],  # pyright: ignore[reportArgumentType]
                                )
                            ],
                        ]
                    ),
                    SFCParallel(
                        branches=[
                            [Assignment(target=_varref("ParallelResetOld"), value=_varref("OpSeq.Reset"))],  # pyright: ignore[reportArgumentType]
                            [
                                SFCTransitionSub(
                                    name="NestedTransition",
                                    body=[Assignment(target=_varref("TransResetOld"), value=_varref("OpSeq.Reset"))],  # pyright: ignore[reportArgumentType]
                                )
                            ],
                        ]
                    ),
                ],
            )
        ],
        equationblocks=[
            Equation(
                name="Main",
                position=(0.0, 0.0),
                size=(1.0, 1.0),
                code=[Assignment(target=_varref("EqResetOld"), value=_varref("OpSeq.Reset"))],  # pyright: ignore[reportArgumentType]
            )
        ],
    )

    refs = ResetContaminationAnalyzer._collect_var_refs(modulecode)
    reset_old_vars = ResetContaminationAnalyzer._collect_reset_old_vars(modulecode, "opseq.reset")

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

    run_flags = classify_reset_condition(
        NotOp(operand=_varref("OpSeq.Reset")),
        reset_ref_cf,
        reset_old_vars_cf,
    )
    reset_flags = classify_reset_condition(
        NotOp(operand=_varref("OpSeqResetOld")),
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

    assert [
        state.reset_state
        for state in take_condition_branch(
            PathState(),
            run_flags,
        )
    ] == ["run"]
    assert [
        state.reset_state
        for state in infer_alternative_states(
            PathState(),
            saw_run=True,
            saw_reset=False,
            saw_exact_run=True,
            saw_exact_reset=False,
        )
    ] == ["reset"]
    assert [
        state.reset_state
        for state in infer_alternative_states(
            PathState(),
            saw_run=False,
            saw_reset=True,
            saw_exact_run=False,
            saw_exact_reset=True,
        )
    ] == ["run"]
    assert [
        state.reset_state
        for state in infer_alternative_states(
            PathState(),
            saw_run=True,
            saw_reset=False,
            saw_exact_run=False,
            saw_exact_reset=False,
        )
    ] == ["run", "reset"]
    assert (
        infer_alternative_states(
            PathState(),
            saw_run=True,
            saw_reset=True,
            saw_exact_run=True,
            saw_exact_reset=True,
        )
        == []
    )
    assert (
        clone_with_reset_state(
            PathState(reset_state="run"),
            "reset",
        )
        == []
    )


def test_reset_contamination_helpers_merge_parallel_paths_and_record_writes():
    counter = Variable(name="Counter", datatype=ScalarDatatype.INTEGER)
    source = Variable(name="Source", datatype=ScalarDatatype.INTEGER)
    destination = Variable(name="Destination", datatype=ScalarDatatype.INTEGER)
    status = Variable(name="Status", datatype=ScalarDatatype.INTEGER)
    flag = Variable(name="Flag", datatype=ScalarDatatype.BOOLEAN)
    env = {
        "counter": counter,
        "source": source,
        "destination": destination,
        "status": status,
        "flag": flag,
    }

    run_state = PathState(reset_state="run")
    reset_state = PathState(reset_state="reset")
    unknown_state = PathState(reset_state="unknown")
    record_mode_write(_varref("Counter.Member"), env, run_state)
    record_mode_write(_varref("Counter"), env, reset_state)
    record_mode_function_call_writes(
        "CopyVariable",
        [_varref("Source"), _varref("Destination"), _varref("Status")],
        env,
        unknown_state,
    )

    merged = merge_parallel_branch_results([[run_state], [unknown_state]])

    assert len(merged) == 1
    assert merged[0].reset_state == "run"
    assert set(merged[0].run_writes) == {
        ("counter", "member"),
        ("destination", ""),
        ("status", ""),
    }
    assert merge_parallel_branch_results([[run_state], [reset_state]]) == []
    assert path_covers_write(reset_state.reset_writes, ("counter", "member")) is True

    boolean_state = BooleanPathState()
    record_boolean_assignment(_varref("Flag"), True, env, boolean_state)
    record_boolean_function_call(
        "SetBooleanValue",
        [_varref("Flag"), False],
        env,
        boolean_state,
    )
    record_boolean_function_call(
        "SetBooleanValue",
        [_varref("Flag.Member"), True],
        env,
        boolean_state,
    )

    assert set(boolean_state.true_writes) == {("flag", "")}
    assert set(boolean_state.false_writes) == {("flag", "")}
