# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
"""Late helper coverage tests split from test_reset_contamination_ratchet.py."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sattlint.analyzers.reset_contamination import _reset_path_state as reset_path_state_module
from tests.analyzers.state_integrity.test_reset_contamination_ratchet import (
    SFCAlternative,
    SFCParallel,
    Simple_DataType,
    Variable,
    VariableIssue,
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


def test_reset_path_state_helper_covers_unknown_merge_branch() -> None:
    assert reset_path_state_module._merge_reset_states("unknown", "run") == "run"
