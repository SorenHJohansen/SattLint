# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
"""Late helper coverage tests split from test_reset_contamination_ratchet.py."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

from sattline_parser.models.ast_model import ScalarDatatype, SFCAlternative, SFCParallel, Variable

from sattlint.analyzers.reset_contamination import _reset_path_state as reset_path_state_module
from sattlint.analyzers.reset_contamination._reset_latching import (
    BooleanPathState,
    all_boolean_paths_cover_false,
    boolean_path_covers_false,
    collect_boolean_seq_node_paths,
    collect_boolean_stmt_paths,
    emit_branch_latch_issues,
)
from sattlint.analyzers.reset_contamination._reset_path_state import (
    PathCollectionDebug,
    merge_parallel_branch_results,
)
from sattlint.analyzers.reset_contamination._reset_path_writes import (
    path_covers_write,
    split_var_ref,
)
from sattlint.reporting.variables_report import VariableIssue


def test_reset_contamination_helpers_cover_debug_and_parallel_edge_cases(caplog) -> None:
    debug = PathCollectionDebug(enabled=True)
    trace_events: list[tuple[str, dict[str, Any]]] = []

    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        PathCollectionDebug(enabled=False).emit("suppressed")
        PathCollectionDebug(
            enabled=True,
            trace_fn=lambda action, **data: trace_events.append((action, data)),
        ).emit("empty-detail")

    assert "reset-contamination empty-detail" in "\n".join(caplog.messages)
    assert trace_events == [("reset-contamination-empty-detail", {})]
    assert reset_path_state_module._merge_reset_states("run", "run") == "run"
    assert reset_path_state_module._merge_reset_states("run", "unknown") == "run"
    assert merge_parallel_branch_results([], debug=debug) == []
    assert split_var_ref("Counter") == ("Counter", "")
    assert path_covers_write({}, ("flag", "member")) is False


def test_implicit_latch_helper_guard_paths_and_issue_suppression() -> None:
    env = {
        "flag": Variable(name="Flag", datatype=ScalarDatatype.BOOLEAN),
        "other": Variable(name="Other", datatype=ScalarDatatype.INTEGER),
    }
    base_states = [BooleanPathState()]

    assert collect_boolean_stmt_paths(None, env, base_states) == base_states
    assert collect_boolean_stmt_paths(("unknown",), env, base_states) == base_states

    assert (
        collect_boolean_seq_node_paths(
            SFCAlternative(branches=[]),
            env,
            base_states,
        )
        == base_states
    )
    assert (
        collect_boolean_seq_node_paths(
            SFCParallel(branches=[]),
            env,
            base_states,
        )
        == base_states
    )
    assert collect_boolean_seq_node_paths(SimpleNamespace(), env, base_states) == base_states

    issues: list[VariableIssue] = []
    seen: set[tuple[tuple[str, ...], str, str]] = set()
    branch_state = BooleanPathState(true_writes={("flag", ""): (env["flag"], "")})
    false_cover = BooleanPathState(false_writes={("flag", ""): (env["flag"], "")})
    emit_branch_latch_issues(
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

    emit_branch_latch_issues(
        [branch_state],
        [BooleanPathState()],
        ["Root"],
        issues,
        seen,
        site="SITE",
        role_prefix="branch latch",
        sequence_name="Seq",
    )
    emit_branch_latch_issues(
        [branch_state],
        [BooleanPathState()],
        ["Root"],
        issues,
        seen,
        site="SITE",
        role_prefix="branch latch",
        sequence_name="Seq",
    )
    assert len(issues) == 1
    assert issues[0].role == "branch latch at SITE"
    assert all_boolean_paths_cover_false([], ("flag", "")) is False
    assert boolean_path_covers_false({}, ("flag", "")) is False


def test_reset_path_state_helper_covers_unknown_merge_branch() -> None:
    assert reset_path_state_module._merge_reset_states("unknown", "run") == "run"
