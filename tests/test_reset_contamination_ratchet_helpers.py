"""Late helper coverage tests split from test_reset_contamination_ratchet.py."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sattlint.analyzers import _reset_path_state as reset_path_state_module
from tests.test_reset_contamination_ratchet import (
    Equation,
    ModuleCode,
    Sequence,
    SFCAlternative,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    Simple_DataType,
    Variable,
    VariableIssue,
    _varref,
    const,
    logging,
    reset_contamination_module,
)


def test_reset_contamination_helpers_cover_debug_and_parallel_edge_cases(caplog) -> None:
    debug = reset_contamination_module._PathCollectionDebug(enabled=True)
    trace_events: list[tuple[str, dict[str, Any]]] = []

    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        reset_contamination_module._PathCollectionDebug(enabled=False).emit("suppressed")
        reset_contamination_module._PathCollectionDebug(
            enabled=True,
            trace_fn=lambda action, **data: trace_events.append((action, data)),
        ).emit("empty-detail")

    assert "reset-contamination empty-detail" in "\n".join(caplog.messages)
    assert trace_events == [("reset-contamination-empty-detail", {})]
    assert reset_path_state_module._merge_reset_states("run", "run") == "run"
    assert reset_path_state_module._merge_reset_states("run", "unknown") == "run"
    assert reset_contamination_module._merge_parallel_branch_results([], debug=debug) == []
    assert reset_contamination_module._split_var_ref("Counter") == ("Counter", "")
    assert reset_contamination_module._path_covers_write({}, ("flag", "member")) is False


def test_implicit_latch_helper_guard_paths_and_issue_suppression() -> None:
    env = {
        "flag": Variable(name="Flag", datatype=Simple_DataType.BOOLEAN),
        "other": Variable(name="Other", datatype=Simple_DataType.INTEGER),
    }
    base_states = [reset_contamination_module._BooleanPathState()]

    assert reset_contamination_module._collect_boolean_stmt_paths(None, env, base_states) == base_states
    assert reset_contamination_module._collect_boolean_stmt_paths(("unknown",), env, base_states) == base_states
    assert reset_contamination_module._collect_boolean_stmt_paths(
        [SimpleNamespace(children=[(const.KEY_ASSIGN, _varref("Flag"), True)])],
        env,
        base_states,
    )[0].true_writes == {("flag", ""): (env["flag"], "")}

    assert (
        reset_contamination_module._collect_boolean_seq_node_paths(
            SFCAlternative(branches=[]),
            env,
            base_states,
        )
        == base_states
    )
    assert (
        reset_contamination_module._collect_boolean_seq_node_paths(
            SFCParallel(branches=[]),
            env,
            base_states,
        )
        == base_states
    )
    assert (
        reset_contamination_module._collect_boolean_seq_node_paths(SimpleNamespace(), env, base_states) == base_states
    )

    issues: list[VariableIssue] = []
    seen: set[tuple[tuple[str, ...], str, str]] = set()
    branch_state = reset_contamination_module._BooleanPathState(true_writes={("flag", ""): (env["flag"], "")})
    false_cover = reset_contamination_module._BooleanPathState(false_writes={("flag", ""): (env["flag"], "")})
    reset_contamination_module._emit_branch_latch_issues(
        [branch_state],
        [false_cover],
        ["Root"],
        issues,
        seen,
        site="SITE",
        role_prefix="branch latch",
        sequence_name="Seq",
    )
    assert issues == []

    reset_contamination_module._emit_branch_latch_issues(
        [branch_state],
        [reset_contamination_module._BooleanPathState()],
        ["Root"],
        issues,
        seen,
        site="SITE",
        role_prefix="branch latch",
        sequence_name="Seq",
    )
    reset_contamination_module._emit_branch_latch_issues(
        [branch_state],
        [reset_contamination_module._BooleanPathState()],
        ["Root"],
        issues,
        seen,
        site="SITE",
        role_prefix="branch latch",
        sequence_name="Seq",
    )
    assert len(issues) == 1
    assert issues[0].role == "branch latch at SITE"
    assert reset_contamination_module._all_boolean_paths_cover_false([], ("flag", "")) is False
    assert reset_contamination_module._boolean_path_covers_false({}, ("flag", "")) is False


def test_reset_contamination_remaining_branch_coverage(caplog: Any) -> None:
    env = {
        "counter": Variable(name="Counter", datatype=Simple_DataType.INTEGER),
        "source": Variable(name="Source", datatype=Simple_DataType.INTEGER),
        "flag": Variable(name="Flag", datatype=Simple_DataType.BOOLEAN),
        "seqresetold": Variable(name="SeqResetOld", datatype=Simple_DataType.BOOLEAN),
    }

    modulecode = ModuleCode(
        sequences=[
            Sequence(
                name="OpSeq",
                type="sequence",
                position=(0.0, 0.0),
                size=(1.0, 1.0),
                code=[
                    None,
                    SimpleNamespace(
                        data=const.KEY_STATEMENT,
                        children=[(const.KEY_ASSIGN, _varref("SeqResetOld"), _varref("OpSeq.Reset"))],
                    ),
                    [(const.KEY_ASSIGN, _varref("Counter"), _varref("OpSeq.Reset"))],
                    SFCStep(
                        kind="step",
                        name="VisitAll",
                        code=SFCCodeBlocks(
                            enter=[(const.KEY_ASSIGN, _varref("SeqResetOld"), _varref("OpSeq.Reset"))],
                            active=[(const.KEY_ASSIGN, _varref("Counter"), _varref("OpSeq.Reset"))],
                            exit=[(const.KEY_ASSIGN, _varref("SeqResetOld"), _varref("OpSeq.Reset"))],
                        ),
                    ),
                    SFCAlternative(branches=[[(const.KEY_ASSIGN, _varref("Counter"), _varref("OpSeq.Reset"))]]),
                    SFCParallel(branches=[[(const.KEY_ASSIGN, _varref("Counter"), _varref("OpSeq.Reset"))]]),
                ],
            )
        ],
        equations=[
            Equation(
                name="Nested",
                position=(0.0, 0.0),
                size=(1.0, 1.0),
                code=[
                    SimpleNamespace(children=[(const.KEY_ASSIGN, _varref("SeqResetOld"), _varref("OpSeq.Reset"))]),
                    (
                        const.GRAMMAR_VALUE_IF,
                        [
                            (
                                SimpleNamespace(children=[None, [_varref("OpSeq.Reset")]]),
                                [SimpleNamespace(data=const.KEY_STATEMENT, children=[])],
                            )
                        ],
                        [(const.KEY_ASSIGN, _varref("Counter"), _varref("OpSeq.Reset"))],
                    ),
                ],
            )
        ],
    )

    refs = reset_contamination_module._collect_var_refs(modulecode)
    reset_old_vars = reset_contamination_module._collect_reset_old_vars(modulecode, "opseq.reset")
    assert "opseq.reset" in refs
    assert "SeqResetOld" in reset_old_vars

    issues: list[VariableIssue] = []
    seen: set[tuple[tuple[str, ...], str, str]] = set()
    reset_contamination_module._scan_stmt_for_latching(
        None,
        env,
        ["Root"],
        issues,
        seen,
        site="SITE",
    )
    reset_contamination_module._scan_stmt_for_latching(
        SimpleNamespace(data=const.KEY_STATEMENT, children=[None]),
        env,
        ["Root"],
        issues,
        seen,
        site="SITE",
    )
    reset_contamination_module._scan_stmt_for_latching(
        [SimpleNamespace(children=[])],
        env,
        ["Root"],
        issues,
        seen,
        site="SITE",
    )
    reset_contamination_module._scan_stmt_for_latching(
        SimpleNamespace(children=[None]),
        env,
        ["Root"],
        issues,
        seen,
        site="SITE",
    )
    assert issues == []

    boolean_if_states = reset_contamination_module._collect_boolean_stmt_paths(
        (
            const.GRAMMAR_VALUE_IF,
            [(True, [(const.KEY_ASSIGN, _varref("Flag"), True)])],
            None,
        ),
        env,
        [reset_contamination_module._BooleanPathState()],
    )
    assert len(boolean_if_states) == 2

    path_debug = reset_contamination_module._PathCollectionDebug(enabled=True)
    with caplog.at_level("DEBUG", logger="SattLint"):
        assert (
            reset_contamination_module._collect_seq_node_paths(
                SFCAlternative(branches=[]),
                env,
                "opseq.reset",
                {"seqresetold"},
                [reset_contamination_module._PathState()],
                path_debug=path_debug,
            )[0].reset_state
            == "unknown"
        )
        assert (
            reset_contamination_module._collect_seq_node_paths(
                SFCParallel(branches=[]),
                env,
                "opseq.reset",
                {"seqresetold"},
                [reset_contamination_module._PathState()],
                path_debug=path_debug,
            )[0].reset_state
            == "unknown"
        )
        assert (
            reset_contamination_module._collect_seq_node_paths(
                reset_contamination_module.SFCTransition(name="Gate", condition=True),
                env,
                "opseq.reset",
                {"seqresetold"},
                [reset_contamination_module._PathState()],
                path_debug=path_debug,
            )[0].reset_state
            == "unknown"
        )
        reset_contamination_module._collect_seq_node_paths(
            SimpleNamespace(),
            env,
            "opseq.reset",
            {"seqresetold"},
            [reset_contamination_module._PathState()],
            path_debug=path_debug,
        )
        reset_contamination_module._collect_seq_node_paths(
            reset_contamination_module.SFCSubsequence(name="Sub", body=[]),
            env,
            "opseq.reset",
            {"seqresetold"},
            [reset_contamination_module._PathState()],
            path_debug=path_debug,
        )
        reset_contamination_module._collect_seq_node_paths(
            reset_contamination_module.SFCTransitionSub(name="SubGate", body=[]),
            env,
            "opseq.reset",
            {"seqresetold"},
            [reset_contamination_module._PathState()],
            path_debug=path_debug,
        )

    if_states = reset_contamination_module._collect_if_stmt_paths(
        [(_varref("OpSeq.Reset"), [(const.KEY_ASSIGN, _varref("Counter"), _varref("Source"))])],
        [(const.KEY_ASSIGN, _varref("Counter.Else"), _varref("Source"))],
        env,
        "opseq.reset",
        {"seqresetold"},
        [reset_contamination_module._PathState(reset_state="run")],
        path_debug=path_debug,
    )
    assert ("counter", "else") in if_states[0].run_writes

    stmt_states = reset_contamination_module._collect_stmt_paths(
        None,
        env,
        "opseq.reset",
        {"seqresetold"},
        [reset_contamination_module._PathState(reset_state="run")],
        path_debug=path_debug,
    )
    wrapped_stmt_states = reset_contamination_module._collect_stmt_paths(
        SimpleNamespace(data=const.KEY_STATEMENT, children=[]),
        env,
        "opseq.reset",
        {"seqresetold"},
        [reset_contamination_module._PathState(reset_state="run")],
        path_debug=path_debug,
    )
    assert len(stmt_states) == 1
    assert len(wrapped_stmt_states) == 1

    cond_flags = reset_contamination_module._classify_reset_condition(
        SimpleNamespace(
            children=[
                None,
                [
                    (const.GRAMMAR_VALUE_NOT, _varref("OpSeq.Reset")),
                    (const.GRAMMAR_VALUE_NOT, _varref("SeqResetOld")),
                    (const.KEY_COMPARE, _varref("Counter"), [("=", _varref("Counter"))]),
                ],
            ]
        ),
        "opseq.reset",
        {"seqresetold"},
    )
    assert cond_flags["run"] is True
    assert cond_flags["reset"] is True
    assert reset_contamination_module._is_exact_reset_condition(_varref("OpSeq.Reset"), "opseq.reset", {"seqresetold"})
    assert reset_contamination_module._varref_casefold(_varref("OpSeq.Reset")) == "opseq.reset"
    assert (
        reset_contamination_module._take_condition_branch(
            reset_contamination_module._PathState(),
            {"run": True, "reset": True},
        )[0].reset_state
        == "unknown"
    )
    assert (
        reset_contamination_module._infer_alternative_states(
            reset_contamination_module._PathState(reset_state="run"),
            saw_run=True,
            saw_reset=False,
            saw_exact_run=False,
            saw_exact_reset=False,
        )[0].reset_state
        == "run"
    )
    assert (
        reset_contamination_module._infer_alternative_states(
            reset_contamination_module._PathState(reset_state="run"),
            saw_run=False,
            saw_reset=False,
            saw_exact_run=False,
            saw_exact_reset=False,
        )[0].reset_state
        == "run"
    )

    assert "node_type='subsequence'" in "\n".join(caplog.messages)
    assert "node_type='transition-sub'" in "\n".join(caplog.messages)


def test_reset_path_state_helper_covers_unknown_merge_branch() -> None:
    assert reset_path_state_module._merge_reset_states("unknown", "run") == "run"
