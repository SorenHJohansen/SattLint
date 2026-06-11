"""Focused coverage tests for reset contamination ratchet repayment."""

from __future__ import annotations

import logging
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    Sequence,
    SFCAlternative,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.reporting.variables_report import VariableIssue
from tests._reset_contamination_test_api import reset_contamination_module


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def _reset_equation(run_target: str, reset_target: str) -> Equation:
    return Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            (
                const.GRAMMAR_VALUE_IF,
                [
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OpSeq.Reset")),
                        [(const.KEY_ASSIGN, _varref(run_target), _varref("ResetValue"))],
                    ),
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("SeqResetOld")),
                        [(const.KEY_ASSIGN, _varref(reset_target), _varref("ResetValue"))],
                    ),
                ],
                [],
            ),
            (const.KEY_ASSIGN, _varref("SeqResetOld"), _varref("OpSeq.Reset")),
        ],
    )


def _reset_modulecode(run_target: str = "Counter", reset_target: str = "Other") -> ModuleCode:
    return ModuleCode(
        sequences=[Sequence(name="OpSeq", type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=[])],
        equations=[_reset_equation(run_target, reset_target)],
    )


def _typedef_with_latch(name: str) -> ModuleTypeDef:
    return ModuleTypeDef(
        name=name,
        moduleparameters=[],
        localvariables=[
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="AlarmLatched", datatype=Simple_DataType.BOOLEAN),
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="LatchEq",
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
    )


def test_state_integrity_top_level_detection_covers_typedef_origin_limit_and_root() -> None:
    typedef_reset = ModuleTypeDef(
        name="ResetType",
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="Other", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="SeqResetOld", datatype=Simple_DataType.BOOLEAN),
        ],
        moduledef=None,
        modulecode=_reset_modulecode(),
    )
    typedef_reset.origin_file = "root.s"

    typedef_skipped = ModuleTypeDef(
        name="SkippedType",
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="Other", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="SeqResetOld", datatype=Simple_DataType.BOOLEAN),
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
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="RootLatched", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="RootEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [(_varref("Start"), [(const.KEY_ASSIGN, _varref("RootLatched"), True)])],
                            [],
                        )
                    ],
                )
            ]
        ),
        moduledef=None,
    )
    bp.origin_file = "root.s"

    reset_issues: list[VariableIssue] = []
    trace_events: list[tuple[str, dict[str, Any]]] = []
    reset_contamination_module.detect_reset_contamination(
        bp,
        reset_issues,
        debug=True,
        trace_fn=lambda action, **data: trace_events.append((action, data)),
    )

    assert [(issue.module_path, issue.variable.name) for issue in reset_issues if issue.variable is not None] == [
        (["Root", "TypeDef:ResetType"], "Counter")
    ]
    assert any(action == "reset-contamination-modulecode-path-summary" for action, _data in trace_events)

    limited_reset_issues: list[VariableIssue] = []
    reset_contamination_module.detect_reset_contamination(
        bp,
        limited_reset_issues,
        limit_to_module_path=["Root", "NoMatch"],
    )
    assert limited_reset_issues == []

    latch_issues: list[VariableIssue] = []
    reset_contamination_module.detect_implicit_latching(bp, latch_issues)
    assert sorted((issue.module_path, issue.variable.name) for issue in latch_issues if issue.variable is not None) == [
        (["Root"], "RootLatched"),
        (["Root", "TypeDef:LatchType"], "AlarmLatched"),
    ]

    limited_latch_issues: list[VariableIssue] = []
    reset_contamination_module.detect_implicit_latching(
        bp,
        limited_latch_issues,
        limit_to_module_path=["Root", "NoMatch"],
    )
    assert [
        (issue.module_path, issue.variable.name) for issue in limited_latch_issues if issue.variable is not None
    ] == [(["Root"], "RootLatched")]


def test_reset_contamination_helper_guard_paths_and_write_filters(monkeypatch: Any) -> None:  # noqa: PLR0915
    env = reset_contamination_module._build_local_env(
        object(),
        [Variable(name="Param", datatype=Simple_DataType.INTEGER)],
        [
            Variable(name="Flag", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="SeqResetOld", datatype=Simple_DataType.BOOLEAN),
        ],
    )
    assert sorted(env) == ["counter", "flag", "param", "resetvalue", "seqresetold"]
    assert reset_contamination_module._should_analyze_path(["Root", "Unit"], ["Other"]) is False
    assert reset_contamination_module.is_from_root_origin(None, "root.s") is True
    assert reset_contamination_module.is_from_root_origin("root.s", None) is False

    class BrokenPath:
        def __init__(self, value: str) -> None:
            self.value = value

        def rsplit(self, sep: str, maxsplit: int) -> list[str]:
            return self.value.rsplit(sep, maxsplit)

    assert reset_contamination_module.is_from_root_origin(cast(Any, BrokenPath("root.s")), "root.s") is True

    calls: list[str] = []
    reset_contamination_module._check_for_single(
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
    reset_contamination_module._check_for_typedef(
        ModuleTypeDef(
            name="NoCodeType",
            moduleparameters=[],
            localvariables=[],
            moduledef=None,
            modulecode=None,
        ),
        ["Root", "TypeDef:NoCodeType"],
        [],
        check_fn=lambda *_args: calls.append("typedef"),
    )
    assert calls == []

    child_module = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="ChildFlag", datatype=Simple_DataType.BOOLEAN)],
        submodules=[],
        modulecode=ModuleCode(equations=[], sequences=[]),
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
    reset_contamination_module._collect_from_module(
        parent_module,
        ["Root"],
        [],
        None,
        check_fn=lambda _modulecode, _env, path, _issues: traversed_paths.append(path.copy()),
    )
    assert traversed_paths == [["Root", "Parent", "Child"]]

    no_sequence_issues: list[VariableIssue] = []
    reset_contamination_module._check_for_modulecode(
        ModuleCode(equations=[], sequences=[]), env, ["Root"], no_sequence_issues
    )
    reset_contamination_module._check_for_modulecode(
        ModuleCode(
            equations=[],
            sequences=[Sequence(name="", type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=[])],
        ),
        env,
        ["Root"],
        no_sequence_issues,
    )
    reset_contamination_module._check_for_modulecode(
        ModuleCode(
            equations=[],
            sequences=[Sequence(name="OpSeq", type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=[])],
        ),
        env,
        ["Root"],
        no_sequence_issues,
    )
    reset_contamination_module._check_for_modulecode(
        ModuleCode(
            equations=[
                Equation(
                    name="GuardOnly",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [((const.GRAMMAR_VALUE_NOT, _varref("OpSeq.Reset")), [])],
                            [],
                        )
                    ],
                )
            ],
            sequences=[Sequence(name="OpSeq", type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=[])],
        ),
        env,
        ["Root"],
        no_sequence_issues,
    )
    reset_contamination_module._check_for_modulecode(
        _reset_modulecode(run_target="SeqResetOld", reset_target="SeqResetOld"),
        env,
        ["Root"],
        no_sequence_issues,
    )
    assert no_sequence_issues == []

    out: reset_contamination_module.WriteMap = {}
    reset_contamination_module._record_write(None, env, out)
    reset_contamination_module._record_write({}, env, out)
    reset_contamination_module._record_write(_varref(""), env, out)
    reset_contamination_module._record_write(_varref(".Field"), env, out)
    reset_contamination_module._record_write(_varref("Missing"), env, out)
    assert out == {}

    bool_out: reset_contamination_module.WriteMap = {}
    reset_contamination_module._record_boolean_write(None, env, bool_out)
    reset_contamination_module._record_boolean_write({}, env, bool_out)
    reset_contamination_module._record_boolean_write(_varref(""), env, bool_out)
    reset_contamination_module._record_boolean_write(_varref("Counter"), env, bool_out)
    reset_contamination_module._record_boolean_write(_varref("Flag.Member"), env, bool_out)
    reset_contamination_module._record_boolean_write(_varref("Flag"), env, bool_out)
    assert set(bool_out) == {("flag", "")}

    call_out: reset_contamination_module.WriteMap = {}
    reset_contamination_module._record_function_call_writes("NoSuchBuiltin", [_varref("Counter")], env, call_out)
    reset_contamination_module._record_function_call_writes(
        "CopyVariable",
        [123, _varref("Counter"), _varref("Flag"), _varref("Counter.Member")],
        env,
        call_out,
    )
    assert set(call_out) == {("counter", ""), ("flag", "")}

    bool_state = reset_contamination_module._BooleanPathState()
    reset_contamination_module._record_boolean_assignment(_varref("Flag"), "True", env, bool_state)
    reset_contamination_module._record_boolean_function_call("Other", [_varref("Flag"), True], env, bool_state)
    reset_contamination_module._record_boolean_function_call("SetBooleanValue", [_varref("Flag")], env, bool_state)
    reset_contamination_module._record_boolean_function_call(
        "SetBooleanValue", [_varref("Flag"), "True"], env, bool_state
    )
    reset_contamination_module._record_boolean_function_call(
        "SetBooleanValue", [_varref("Flag"), True], env, bool_state
    )
    assert set(bool_state.true_writes) == {("flag", "")}
    assert bool_state.false_writes == {}

    assert reset_contamination_module._literal_boolean("True") is None
    assert reset_contamination_module._varref_casefold({}) is None
    assert reset_contamination_module._varref_casefold(_varref("")) is None
    assert reset_contamination_module._split_var_ref("") == ("", "")


def test_reset_contamination_helpers_bound_duplicate_paths_and_emit_debug(caplog) -> None:
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
    path_debug = reset_contamination_module._PathCollectionDebug(enabled=True)

    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        if_states = reset_contamination_module._collect_if_stmt_paths(
            [
                (
                    (const.GRAMMAR_VALUE_NOT, _varref("OpSeq.Reset")),
                    [(const.KEY_ASSIGN, _varref("Counter.Member"), _varref("Source"))],
                ),
                (
                    (const.GRAMMAR_VALUE_NOT, _varref("OpSeq.Reset")),
                    [(const.KEY_ASSIGN, _varref("Counter.Member"), _varref("Source"))],
                ),
            ],
            None,
            env,
            "opseq.reset",
            {"opseqresetold"},
            [reset_contamination_module._PathState()],
            path_debug=path_debug,
        )
        call_states = reset_contamination_module._collect_function_call_paths(
            "CopyVariable",
            [_varref("Source"), _varref("Destination"), _varref("Status")],
            env,
            "opseq.reset",
            {"opseqresetold"},
            [
                reset_contamination_module._PathState(reset_state="run"),
                reset_contamination_module._PathState(reset_state="run"),
            ],
            path_debug=path_debug,
        )
        parallel_states = reset_contamination_module._collect_seq_node_paths(
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
                                            active=[(const.KEY_ASSIGN, _varref("Counter.Left"), _varref("Source"))]
                                        ),
                                    )
                                ],
                                [
                                    SFCStep(
                                        kind="step",
                                        name="LeftB",
                                        code=SFCCodeBlocks(
                                            active=[(const.KEY_ASSIGN, _varref("Counter.Left"), _varref("Source"))]
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
                                            active=[(const.KEY_ASSIGN, _varref("Counter.Right"), _varref("Source"))]
                                        ),
                                    )
                                ],
                                [
                                    SFCStep(
                                        kind="step",
                                        name="RightB",
                                        code=SFCCodeBlocks(
                                            active=[(const.KEY_ASSIGN, _varref("Counter.Right"), _varref("Source"))]
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
            [reset_contamination_module._PathState(reset_state="run")],
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


def test_reset_contamination_helpers_conservatively_merge_overflowed_path_frontiers(caplog) -> None:
    counter = Variable(name="Counter", datatype=Simple_DataType.INTEGER)
    overflow_states: list[reset_contamination_module._PathState] = []
    for index in range(70):
        state = reset_contamination_module._PathState(reset_state="run")
        state.run_writes[("counter", f"field{index}")] = (counter, f"field{index}")
        overflow_states.append(state)

    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        result = reset_contamination_module._compact_path_states(
            overflow_states,
            debug=reset_contamination_module._PathCollectionDebug(enabled=True),
            site="overflow-test",
        )

    assert len(result) == 1
    assert len(result[0].run_writes) == 70
    assert "overflow_merged=True" in "\n".join(caplog.messages)
