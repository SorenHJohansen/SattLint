"""Statement handler helpers for reset contamination path collection."""

from __future__ import annotations

from typing import Any

from ..grammar import constants as const
from ._reset_path_condition import (
    _classify_reset_condition,
    _infer_alternative_states,
    _take_condition_branch,
)
from ._reset_path_state import (
    _compact_path_states,
    _PathCollectionDebug,
    _PathState,
)
from ._reset_path_writes import _record_mode_function_call_writes, _record_mode_write


def _collect_stmt_block_paths(
    stmts: list[Any],
    env: dict[str, Any],
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
    env: dict[str, Any],
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


def _handle_ternary_stmt(
    obj: tuple,
    env: dict[str, Any],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    _, branches, else_expr = obj
    next_states = states
    for cond, then_expr in branches or []:
        next_states = _collect_stmt_paths(
            cond,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            next_states,
            path_debug=path_debug,
        )
        next_states = _collect_stmt_paths(
            then_expr,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            next_states,
            path_debug=path_debug,
        )
    if else_expr is not None:
        next_states = _collect_stmt_paths(
            else_expr,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            next_states,
            path_debug=path_debug,
        )
    return next_states


def _handle_compare_stmt(
    obj: tuple,
    env: dict[str, Any],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    _, left, pairs = obj
    next_states = _collect_stmt_paths(
        left,
        env,
        reset_ref_cf,
        reset_old_vars_cf,
        states,
        path_debug=path_debug,
    )
    for _sym, rhs in pairs or []:
        next_states = _collect_stmt_paths(
            rhs,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            next_states,
            path_debug=path_debug,
        )
    return next_states


def _handle_addmul_stmt(
    obj: tuple,
    env: dict[str, Any],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    _, left, parts = obj
    next_states = _collect_stmt_paths(
        left,
        env,
        reset_ref_cf,
        reset_old_vars_cf,
        states,
        path_debug=path_debug,
    )
    for _opval, rhs in parts or []:
        next_states = _collect_stmt_paths(
            rhs,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            next_states,
            path_debug=path_debug,
        )
    return next_states


def _collect_if_stmt_paths(
    branches: list[tuple[Any, list[Any]]] | None,
    else_block: list[Any] | None,
    env: dict[str, Any],
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

        for cond, stmts in branches or []:
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
                    stmts or [],
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
                        else_block or [],
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
            branch_count=len(branches or []),
            output_count=len(result),
            has_else=else_block is not None,
        )
    return result


def _collect_assignment_paths(
    target: Any,
    expr: Any,
    env: dict[str, Any],
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
    args: list[Any] | None,
    env: dict[str, Any],
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
    obj: Any,
    env: dict[str, Any],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    if obj is None:
        return states
    if hasattr(obj, "data") and obj.data == const.KEY_STATEMENT:
        return _collect_paths_from_items(
            list(getattr(obj, "children", [])),
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
        _, branches, else_block = obj
        return _collect_if_stmt_paths(
            branches,
            else_block,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
        _, target, expr = obj
        return _collect_assignment_paths(
            target,
            expr,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
        _, fn_name, args = obj
        return _collect_function_call_paths(
            fn_name,
            args,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_TERNARY, "Ternary"):
        return _handle_ternary_stmt(obj, env, reset_ref_cf, reset_old_vars_cf, states, path_debug=path_debug)

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_COMPARE, "compare"):
        return _handle_compare_stmt(obj, env, reset_ref_cf, reset_old_vars_cf, states, path_debug=path_debug)

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_ADD, const.KEY_MUL):
        return _handle_addmul_stmt(obj, env, reset_ref_cf, reset_old_vars_cf, states, path_debug=path_debug)

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_PLUS, const.KEY_MINUS):
        return _collect_stmt_paths(
            obj[1],
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, tuple) and obj and obj[0] in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND):
        return _collect_paths_from_items(
            list(obj[1] or []),
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_NOT:
        return _collect_stmt_paths(
            obj[1],
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, list):
        return _collect_paths_from_items(
            obj,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if hasattr(obj, "children"):
        return _collect_paths_from_items(
            list(getattr(obj, "children", [])),
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
