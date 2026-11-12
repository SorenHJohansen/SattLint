"""Statement handler helpers for reset contamination path collection."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sattlint.parser_api import Assignment, FuncCallStmt, IfStmt, Variable

from ._reset_path_condition import (
    classify_reset_condition as _classify_reset_condition,
)
from ._reset_path_condition import (
    infer_alternative_states as _infer_alternative_states,
)
from ._reset_path_condition import (
    take_condition_branch as _take_condition_branch,
)
from ._reset_path_state import (
    PathCollectionDebug as _PathCollectionDebug,
)
from ._reset_path_state import (
    PathState as _PathState,
)
from ._reset_path_state import (
    compact_path_states as _compact_path_states,
)
from ._reset_path_writes import (
    record_mode_function_call_writes as _record_mode_function_call_writes,
)
from ._reset_path_writes import (
    record_mode_write as _record_mode_write,
)


def _collect_stmt_block_paths(
    stmts: list[Any],
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    return _collect_paths_from_items(
        stmts,
        env,
        reset_ref_cf,
        reset_old_vars_cf,
        states,
        path_debug=path_debug,
    )


def _collect_paths_from_items(
    items: list[Any],
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    next_states = states
    for stmt in items:
        next_states = _collect_stmt_paths(
            stmt,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            next_states,
            path_debug=path_debug,
        )
        next_states = _compact_path_states(next_states, debug=path_debug, site="stmt-items")
    return next_states


def _collect_if_stmt_paths(
    branches: Sequence[tuple[object, Sequence[object]]],
    else_block: Sequence[object] | None,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    branch_outcomes: list[_PathState] = []
    for state in states:
        saw_run = False
        saw_reset = False
        saw_exact_run = False
        saw_exact_reset = False
        branch_matched = False

        for cond, stmts in branches:
            cond_flags = _classify_reset_condition(cond, reset_ref_cf, reset_old_vars_cf)
            saw_run = saw_run or cond_flags["run"]
            saw_reset = saw_reset or cond_flags["reset"]
            saw_exact_run = saw_exact_run or cond_flags["exact_run"]
            saw_exact_reset = saw_exact_reset or cond_flags["exact_reset"]

            branch_states = _take_condition_branch(state, cond_flags)
            if not branch_states:
                continue
            branch_matched = True
            branch_outcomes.extend(
                _collect_stmt_block_paths(
                    list(stmts),
                    env,
                    reset_ref_cf,
                    reset_old_vars_cf,
                    branch_states,
                    path_debug=path_debug,
                )
            )

        fallback_states = _infer_alternative_states(
            state,
            saw_run=saw_run,
            saw_reset=saw_reset,
            saw_exact_run=saw_exact_run,
            saw_exact_reset=saw_exact_reset,
        )
        if else_block:
            if fallback_states:
                branch_outcomes.extend(
                    _collect_stmt_block_paths(
                        list(else_block),
                        env,
                        reset_ref_cf,
                        reset_old_vars_cf,
                        fallback_states,
                        path_debug=path_debug,
                    )
                )
        elif fallback_states or not branch_matched:
            branch_outcomes.extend(fallback_states or [state.clone()])
    result = _compact_path_states(branch_outcomes or states, debug=path_debug, site="if-stmt")
    if path_debug is not None:
        path_debug.emit(
            "collect-if-stmt-paths",
            input_count=len(states),
            branch_count=len(branches),
            output_count=len(result),
            has_else=else_block is not None,
        )
    return result


def _collect_assignment_paths(
    target: object,
    expr: object,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    assigned_states: list[_PathState] = []
    for state in states:
        next_state = state.clone()
        _record_mode_write(target, env, next_state)
        assigned_states.extend(
            _collect_stmt_paths(
                expr,
                env,
                reset_ref_cf,
                reset_old_vars_cf,
                [next_state],
                path_debug=path_debug,
            )
        )
    return _compact_path_states(assigned_states, debug=path_debug, site="assignment")


def _collect_function_call_paths(
    fn_name: str,
    args: list[object] | None,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    call_states: list[_PathState] = []
    for state in states:
        next_state = state.clone()
        _record_mode_function_call_writes(fn_name, args or [], env, next_state)
        arg_states = _collect_paths_from_items(
            list(args or []),
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            [next_state],
            path_debug=path_debug,
        )
        call_states.extend(arg_states)
    result = _compact_path_states(
        call_states,
        debug=path_debug,
        site=f"function-call:{fn_name.casefold()}",
    )
    if path_debug is not None:
        path_debug.emit(
            "collect-function-call-paths",
            function_name=fn_name,
            input_count=len(states),
            arg_count=len(args or []),
            output_count=len(result),
        )
    return result


def _collect_stmt_paths(
    obj: object,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    if obj is None:
        return states

    if isinstance(obj, Assignment):
        return _collect_assignment_paths(
            obj.target,
            obj.value,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, FuncCallStmt):
        return _collect_function_call_paths(
            obj.call.name,
            list(obj.call.args),
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, IfStmt):
        return _collect_if_stmt_paths(
            obj.branches,
            obj.else_block,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    return states


collect_if_stmt_paths = _collect_if_stmt_paths
collect_assignment_paths = _collect_assignment_paths
collect_function_call_paths = _collect_function_call_paths
collect_paths_from_items = _collect_paths_from_items
collect_stmt_block_paths = _collect_stmt_block_paths
collect_stmt_paths = _collect_stmt_paths
