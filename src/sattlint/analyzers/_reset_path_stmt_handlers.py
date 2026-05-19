"""Statement handler helpers for reset contamination path collection."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

from sattline_parser.models.ast_model import Variable

from ..grammar import constants as const
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

_NodeTuple = tuple[object, ...]
_NodeList = list[object]
_NodeSequence = _NodeTuple | _NodeList


def _object_tuple(node: object) -> _NodeTuple | None:
    if isinstance(node, tuple):
        return cast(_NodeTuple, node)
    return None


def _object_list(node: object) -> _NodeList | None:
    if isinstance(node, list):
        return cast(_NodeList, node)
    return None


def _object_sequence(node: object) -> _NodeSequence | None:
    tuple_items = _object_tuple(node)
    if tuple_items is not None:
        return tuple_items
    return _object_list(node)


def _statement_children(node: object) -> _NodeSequence | None:
    if getattr(node, "data", None) != const.KEY_STATEMENT:
        return None
    return _object_sequence(getattr(node, "children", None))


def _sequence_as_list(node: object) -> list[object]:
    items = _object_sequence(node)
    if items is None:
        return []
    return list(items)


def _iter_branch_pairs(node: object) -> Iterator[tuple[object, object]]:
    branches = _object_sequence(node)
    if branches is None:
        return
    for branch in branches:
        branch_items = _object_sequence(branch)
        if branch_items is None or len(branch_items) < 2:
            continue
        yield branch_items[0], branch_items[1]


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


def _handle_ternary_stmt(
    obj: _NodeTuple,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    branches = obj[1] if len(obj) > 1 else None
    else_expr = obj[2] if len(obj) > 2 else None
    next_states = states
    for cond, then_expr in _iter_branch_pairs(branches):
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
    obj: _NodeTuple,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    left = obj[1] if len(obj) > 1 else None
    pairs = obj[2] if len(obj) > 2 else None
    next_states = _collect_stmt_paths(
        left,
        env,
        reset_ref_cf,
        reset_old_vars_cf,
        states,
        path_debug=path_debug,
    )
    for _sym, rhs in _iter_branch_pairs(pairs):
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
    obj: _NodeTuple,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    left = obj[1] if len(obj) > 1 else None
    parts = obj[2] if len(obj) > 2 else None
    next_states = _collect_stmt_paths(
        left,
        env,
        reset_ref_cf,
        reset_old_vars_cf,
        states,
        path_debug=path_debug,
    )
    for _opval, rhs in _iter_branch_pairs(parts):
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
    branches: object,
    else_block: object,
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

        for cond, stmts in _iter_branch_pairs(branches):
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
                    _sequence_as_list(stmts),
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
                        _sequence_as_list(else_block),
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
            branch_count=len(_sequence_as_list(branches)),
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
    statement_children = _statement_children(obj)
    if statement_children is not None:
        return _collect_paths_from_items(
            list(statement_children),
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    tuple_node = _object_tuple(obj)
    if tuple_node is not None and tuple_node and tuple_node[0] == const.GRAMMAR_VALUE_IF:
        branches = tuple_node[1] if len(tuple_node) > 1 else None
        else_block = tuple_node[2] if len(tuple_node) > 2 else None
        return _collect_if_stmt_paths(
            branches,
            else_block,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if tuple_node is not None and tuple_node and tuple_node[0] == const.KEY_ASSIGN:
        target = tuple_node[1] if len(tuple_node) > 1 else None
        expr = tuple_node[2] if len(tuple_node) > 2 else None
        return _collect_assignment_paths(
            target,
            expr,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if tuple_node is not None and tuple_node and tuple_node[0] == const.KEY_FUNCTION_CALL:
        fn_name = tuple_node[1] if len(tuple_node) > 1 else None
        args = tuple_node[2] if len(tuple_node) > 2 else None
        if not isinstance(fn_name, str):
            return states
        return _collect_function_call_paths(
            fn_name,
            _sequence_as_list(args),
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if tuple_node is not None and tuple_node and tuple_node[0] in (const.KEY_TERNARY, "Ternary"):
        return _handle_ternary_stmt(tuple_node, env, reset_ref_cf, reset_old_vars_cf, states, path_debug=path_debug)

    if tuple_node is not None and tuple_node and tuple_node[0] in (const.KEY_COMPARE, "compare"):
        return _handle_compare_stmt(tuple_node, env, reset_ref_cf, reset_old_vars_cf, states, path_debug=path_debug)

    if tuple_node is not None and tuple_node and tuple_node[0] in (const.KEY_ADD, const.KEY_MUL):
        return _handle_addmul_stmt(tuple_node, env, reset_ref_cf, reset_old_vars_cf, states, path_debug=path_debug)

    if tuple_node is not None and tuple_node and tuple_node[0] in (const.KEY_PLUS, const.KEY_MINUS):
        return _collect_stmt_paths(
            tuple_node[1] if len(tuple_node) > 1 else None,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if tuple_node is not None and tuple_node and tuple_node[0] in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND):
        return _collect_paths_from_items(
            _sequence_as_list(tuple_node[1] if len(tuple_node) > 1 else None),
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if tuple_node is not None and tuple_node and tuple_node[0] == const.GRAMMAR_VALUE_NOT:
        return _collect_stmt_paths(
            tuple_node[1] if len(tuple_node) > 1 else None,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    list_node = _object_list(obj)
    if list_node is not None:
        return _collect_paths_from_items(
            list_node,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    children = _object_sequence(getattr(obj, "children", None))
    if children is not None:
        return _collect_paths_from_items(
            list(children),
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
