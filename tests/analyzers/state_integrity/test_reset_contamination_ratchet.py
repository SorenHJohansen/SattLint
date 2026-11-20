"""Focused coverage tests for reset contamination ratchet repayment."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import logging
from typing import Any, cast

import pytest
from sattline_parser.models.ast_model import (
    BasePicture,
    CodeItem,
    Equation,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ScalarDatatype,
    Sequence,
    SFCAlternative,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import Assignment, IfStmt, NotOp, VarRef

from sattlint.analyzers.reset_contamination import (
    ResetContaminationAnalyzer,
    WriteMap,
    detect_implicit_latching,
    detect_reset_contamination,
    is_from_root_origin,
)
from sattlint.analyzers.reset_contamination._reset_latching import (
    BooleanPathState,
    literal_boolean,
    record_boolean_assignment,
    record_boolean_function_call,
    record_boolean_write,
)
from sattlint.analyzers.reset_contamination._reset_path_collection_sequence import (
    collect_seq_node_paths,
)
from sattlint.analyzers.reset_contamination._reset_path_condition import (
    varref_casefold,
)
from sattlint.analyzers.reset_contamination._reset_path_state import (
    PathCollectionDebug,
    PathState,
    compact_path_states,
)
from sattlint.analyzers.reset_contamination._reset_path_stmt_handlers import (
    collect_function_call_paths,
    collect_if_stmt_paths,
    collect_stmt_block_paths,
)
from sattlint.analyzers.reset_contamination._reset_path_writes import (
    record_function_call_writes,
    record_write,
    split_var_ref,
)
from sattlint.reporting.variables_report import ImplicitLatchIssue, ResetContaminationIssue, VariableIssue


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def _reset_equation(run_target: str, reset_target: str) -> Equation:
    return Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=cast(
            list[CodeItem],
            [
                IfStmt(
                    branches=(
                        (
                            NotOp(operand=_varref("OpSeq.Reset")),
                            (Assignment(target=_varref(run_target), value=_varref("ResetValue")),),
                        ),
                        (
                            NotOp(operand=_varref("SeqResetOld")),
                            (Assignment(target=_varref(reset_target), value=_varref("ResetValue")),),
                        ),
                    ),
                    else_block=(),
                ),
                Assignment(target=_varref("SeqResetOld"), value=_varref("OpSeq.Reset")),
            ],
        ),
    )


def _reset_modulecode(run_target: str = "Counter", reset_target: str = "Other") -> ModuleCode:
    return ModuleCode(
        sequences=[Sequence(name="OpSeq", type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=[])],
        equationblocks=[_reset_equation(run_target, reset_target)],
    )


def _typedef_with_latch(name: str) -> ModuleTypeDef:
    return ModuleTypeDef(
        name=name,
        moduleparameters=[],
        localvariables=[
            Variable(name="Start", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="AlarmLatched", datatype=ScalarDatatype.BOOLEAN),
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="LatchEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=cast(
                        list[CodeItem],
                        [
                            IfStmt(
                                branches=(
                                    (_varref("Start"), (Assignment(target=_varref("AlarmLatched"), value=True),)),
                                ),
                                else_block=(),
                            )
                        ],
                    ),
                )
            ]
        ),
    )


def test_state_integrity_top_level_detection_covers_typedef_origin_limit_and_root() -> None:
    typedef_reset = ModuleTypeDef(
        name="ResetType",
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=ScalarDatatype.INTEGER),
            Variable(name="Other", datatype=ScalarDatatype.INTEGER),
            Variable(name="ResetValue", datatype=ScalarDatatype.INTEGER),
            Variable(name="SeqResetOld", datatype=ScalarDatatype.BOOLEAN),
        ],
        moduledef=None,
        modulecode=_reset_modulecode(),
    )
    typedef_reset.origin_file = "root.s"

    typedef_skipped = ModuleTypeDef(
        name="SkippedType",
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=ScalarDatatype.INTEGER),
            Variable(name="Other", datatype=ScalarDatatype.INTEGER),
            Variable(name="ResetValue", datatype=ScalarDatatype.INTEGER),
            Variable(name="SeqResetOld", datatype=ScalarDatatype.BOOLEAN),
        ],
        moduledef=None,
        modulecode=_reset_modulecode(),
    )
    typedef_skipped.origin_file = "other.s"

    typedef_latch = _typedef_with_latch("LatchType")
    typedef_latch.origin_file = "root.s"

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef_reset, typedef_skipped, typedef_latch],
        localvariables=[
            Variable(name="Start", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="RootLatched", datatype=ScalarDatatype.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="RootEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=cast(
                        list[CodeItem],
                        [
                            IfStmt(
                                branches=(
                                    (_varref("Start"), (Assignment(target=_varref("RootLatched"), value=True),)),
                                ),
                                else_block=(),
                            )
                        ],
                    ),
                )
            ]
        ),
        moduledef=None,
    )
    bp.origin_file = "root.s"

    reset_issues: list[VariableIssue] = []
    trace_events: list[tuple[str, dict[str, Any]]] = []

    def _record_trace(action: str, **data: Any) -> None:
        trace_events.append((action, data))

    detect_reset_contamination(
        bp,
        reset_issues,
        debug=True,
        trace_fn=_record_trace,
    )

    assert [
        (issue.module_path, issue.variable.name) for issue in reset_issues if isinstance(issue, ResetContaminationIssue)
    ] == [(["Root", "TypeDef:ResetType"], "Counter")]
    assert any(action == "reset-contamination-modulecode-path-summary" for action, _data in trace_events)

    limited_reset_issues: list[VariableIssue] = []
    detect_reset_contamination(
        bp,
        limited_reset_issues,
        limit_to_module_path=["Root", "NoMatch"],
    )
    assert limited_reset_issues == []

    latch_issues: list[VariableIssue] = []
    detect_implicit_latching(bp, latch_issues)
    assert sorted(
        (issue.module_path, issue.variable.name) for issue in latch_issues if isinstance(issue, ImplicitLatchIssue)
    ) == [
        (["Root"], "RootLatched"),
        (["Root", "TypeDef:LatchType"], "AlarmLatched"),
    ]

    limited_latch_issues: list[VariableIssue] = []
    detect_implicit_latching(
        bp,
        limited_latch_issues,
        limit_to_module_path=["Root", "NoMatch"],
    )
    assert [
        (issue.module_path, issue.variable.name)
        for issue in limited_latch_issues
        if isinstance(issue, ImplicitLatchIssue)
    ] == [(["Root"], "RootLatched")]


def test_reset_contamination_helper_guard_paths_and_write_filters(monkeypatch: Any) -> None:  # noqa: PLR0915
    env = ResetContaminationAnalyzer._build_local_env(
        object(),
        [Variable(name="Param", datatype=ScalarDatatype.INTEGER)],
        [
            Variable(name="Flag", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="Counter", datatype=ScalarDatatype.INTEGER),
            Variable(name="ResetValue", datatype=ScalarDatatype.INTEGER),
            Variable(name="SeqResetOld", datatype=ScalarDatatype.BOOLEAN),
        ],
    )
    assert sorted(env) == ["counter", "flag", "param", "resetvalue", "seqresetold"]
    assert ResetContaminationAnalyzer._should_analyze_path(["Root", "Unit"], ["Other"]) is False
    assert is_from_root_origin(None, "root.s") is True
    assert is_from_root_origin("root.s", None) is False

    class BrokenPath:
        def __init__(self, value: str) -> None:
            self.value = value

        def rsplit(self, sep: str, maxsplit: int) -> list[str]:
            return self.value.rsplit(sep, maxsplit)

    assert is_from_root_origin(cast(Any, BrokenPath("root.s")), "root.s") is True

    calls: list[str] = []
    ResetContaminationAnalyzer._check_for_single(
        SingleModule(
            header=_hdr("NoCode"),
            moduledef=None,
            moduleparameters=[],
            localvariables=[],
            submodules=[],
            modulecode=None,
            parametermappings=[],
        ),
        ["Root", "NoCode"],
        [],
        check_fn=lambda *_args: calls.append("single"),
    )
    ResetContaminationAnalyzer(cast(Any, None))._check_for_typedef(
        ModuleTypeDef(
            name="NoCodeType",
            moduleparameters=[],
            localvariables=[],
            moduledef=None,
            modulecode=None,
        ),
        ["Root", "TypeDef:NoCodeType"],
        [],
        None,
        check_fn=lambda *_args: calls.append("typedef"),
    )
    assert calls == []

    child_module = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="ChildFlag", datatype=ScalarDatatype.BOOLEAN)],
        submodules=[],
        modulecode=ModuleCode(equationblocks=[], sequences=[]),
        parametermappings=[],
    )
    parent_module = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[child_module],
        modulecode=None,
        parametermappings=[],
    )
    traversed_paths: list[list[str]] = []

    def _record_module_path(
        _modulecode: ModuleCode,
        _env: dict[str, Variable],
        path: list[str],
        _issues: list[VariableIssue],
    ) -> None:
        traversed_paths.append(path.copy())

    ResetContaminationAnalyzer(cast(Any, None))._collect_from_module(
        parent_module,
        ["Root"],
        [],
        None,
        check_fn=_record_module_path,
    )
    assert traversed_paths == [["Root", "Parent", "Child"]]

    no_sequence_issues: list[VariableIssue] = []
    ResetContaminationAnalyzer._check_for_modulecode(
        ModuleCode(equationblocks=[], sequences=[]), env, ["Root"], no_sequence_issues
    )
    ResetContaminationAnalyzer._check_for_modulecode(
        ModuleCode(
            equationblocks=[],
            sequences=[Sequence(name="", type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=[])],
        ),
        env,
        ["Root"],
        no_sequence_issues,
    )
    ResetContaminationAnalyzer._check_for_modulecode(
        ModuleCode(
            equationblocks=[],
            sequences=[Sequence(name="OpSeq", type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=[])],
        ),
        env,
        ["Root"],
        no_sequence_issues,
    )
    ResetContaminationAnalyzer._check_for_modulecode(
        ModuleCode(
            equationblocks=[
                Equation(
                    name="GuardOnly",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=cast(
                        list[CodeItem],
                        [
                            IfStmt(
                                branches=((NotOp(operand=_varref("OpSeq.Reset")), ()),),
                                else_block=(),
                            )
                        ],
                    ),
                )
            ],
            sequences=[Sequence(name="OpSeq", type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=[])],
        ),
        env,
        ["Root"],
        no_sequence_issues,
    )
    ResetContaminationAnalyzer._check_for_modulecode(
        _reset_modulecode(run_target="SeqResetOld", reset_target="SeqResetOld"),
        env,
        ["Root"],
        no_sequence_issues,
    )
    assert no_sequence_issues == []

    out: WriteMap = {}
    record_write(None, env, out)
    record_write({}, env, out)
    record_write(_varref(""), env, out)
    record_write(_varref(".Field"), env, out)
    record_write(_varref("Missing"), env, out)
    assert out == {}

    bool_out: WriteMap = {}
    record_boolean_write(None, env, bool_out)
    record_boolean_write({}, env, bool_out)
    record_boolean_write(_varref(""), env, bool_out)
    record_boolean_write(_varref("Counter"), env, bool_out)
    record_boolean_write(_varref("Flag.Member"), env, bool_out)
    record_boolean_write(_varref("Flag"), env, bool_out)
    assert set(bool_out) == {("flag", "")}

    call_out: WriteMap = {}
    record_function_call_writes("NoSuchBuiltin", [_varref("Counter")], env, call_out)
    record_function_call_writes(
        "CopyVariable",
        [123, _varref("Counter"), _varref("Flag"), _varref("Counter.Member")],
        env,
        call_out,
    )
    assert set(call_out) == {("counter", ""), ("flag", "")}

    bool_state = BooleanPathState()
    record_boolean_assignment(_varref("Flag"), "True", env, bool_state)
    record_boolean_function_call("Other", [_varref("Flag"), True], env, bool_state)
    record_boolean_function_call("SetBooleanValue", [_varref("Flag")], env, bool_state)
    record_boolean_function_call("SetBooleanValue", [_varref("Flag"), "True"], env, bool_state)
    record_boolean_function_call("SetBooleanValue", [_varref("Flag"), True], env, bool_state)
    assert set(bool_state.true_writes) == {("flag", "")}
    assert bool_state.false_writes == {}

    assert literal_boolean("True") is None
    assert varref_casefold({}) is None
    assert varref_casefold(_varref("")) is None
    assert split_var_ref("") == ("", "")


def test_reset_contamination_helpers_bound_duplicate_paths_and_emit_debug(caplog: pytest.LogCaptureFixture) -> None:
    counter = Variable(name="Counter", datatype=ScalarDatatype.INTEGER)
    source = Variable(name="Source", datatype=ScalarDatatype.INTEGER)
    destination = Variable(name="Destination", datatype=ScalarDatatype.INTEGER)
    status = Variable(name="Status", datatype=ScalarDatatype.INTEGER)
    env = {
        "counter": counter,
        "source": source,
        "destination": destination,
        "status": status,
    }
    path_debug = PathCollectionDebug(enabled=True)

    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        if_states = collect_if_stmt_paths(
            [
                (
                    NotOp(operand=_varref("OpSeq.Reset")),
                    [Assignment(target=_varref("Counter.Member"), value=_varref("Source"))],
                ),
                (
                    NotOp(operand=_varref("OpSeq.Reset")),
                    [Assignment(target=_varref("Counter.Member"), value=_varref("Source"))],
                ),
            ],
            None,
            env,
            "opseq.reset",
            {"opseqresetold"},
            [PathState()],
            path_debug=path_debug,
        )
        call_states = collect_function_call_paths(
            "CopyVariable",
            [_varref("Source"), _varref("Destination"), _varref("Status")],
            env,
            "opseq.reset",
            {"opseqresetold"},
            [
                PathState(reset_state="run"),
                PathState(reset_state="run"),
            ],
            path_debug=path_debug,
        )
        parallel_states = collect_seq_node_paths(
            SFCParallel(
                branches=[
                    [
                        SFCAlternative(
                            branches=[
                                [
                                    SFCStep(
                                        kind="step",
                                        name="LeftA",
                                        code=SFCCodeBlocks(
                                            active=[Assignment(target=_varref("Counter.Left"), value=_varref("Source"))]  # pyright: ignore[reportArgumentType]
                                        ),
                                    )
                                ],
                                [
                                    SFCStep(
                                        kind="step",
                                        name="LeftB",
                                        code=SFCCodeBlocks(
                                            active=[Assignment(target=_varref("Counter.Left"), value=_varref("Source"))]  # pyright: ignore[reportArgumentType]
                                        ),
                                    )
                                ],
                            ]
                        )
                    ],
                    [
                        SFCAlternative(
                            branches=[
                                [
                                    SFCStep(
                                        kind="step",
                                        name="RightA",
                                        code=SFCCodeBlocks(
                                            active=[
                                                Assignment(target=_varref("Counter.Right"), value=_varref("Source"))
                                            ]  # pyright: ignore[reportArgumentType]
                                        ),
                                    )
                                ],
                                [
                                    SFCStep(
                                        kind="step",
                                        name="RightB",
                                        code=SFCCodeBlocks(
                                            active=[
                                                Assignment(target=_varref("Counter.Right"), value=_varref("Source"))
                                            ]  # pyright: ignore[reportArgumentType]
                                        ),
                                    )
                                ],
                            ]
                        )
                    ],
                ]
            ),
            env,
            "opseq.reset",
            {"opseqresetold"},
            [PathState(reset_state="run")],
            collect_stmt_block_paths=collect_stmt_block_paths,
            path_debug=path_debug,
        )

    assert len(if_states) == 2
    assert sum(1 for state in if_states if state.reset_state == "run") == 1
    assert sum(1 for state in if_states if state.reset_state == "reset") == 1
    assert len(call_states) == 1
    assert len(parallel_states) == 1
    assert set(parallel_states[0].run_writes) == {("counter", "left"), ("counter", "right")}

    debug_output = "\n".join(caplog.messages)
    assert "collect-if-stmt-paths" in debug_output
    assert "collect-function-call-paths" in debug_output
    assert "collect-seq-node-paths" in debug_output
    assert "parallel-merge-step" in debug_output


def test_reset_contamination_helpers_conservatively_merge_overflowed_path_frontiers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    counter = Variable(name="Counter", datatype=ScalarDatatype.INTEGER)
    overflow_states: list[PathState] = []
    for index in range(70):
        state = PathState(reset_state="run")
        state.run_writes[("counter", f"field{index}")] = (counter, f"field{index}")
        overflow_states.append(state)

    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        result = compact_path_states(
            overflow_states,
            debug=PathCollectionDebug(enabled=True),
            site="overflow-test",
        )

    assert len(result) == 1
    assert len(result[0].run_writes) == 70
    assert "overflow_merged=True" in "\n".join(caplog.messages)
