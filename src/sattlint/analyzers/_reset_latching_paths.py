"""Path-state helpers for boolean latch detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Any, cast

from sattline_parser.models.ast_model import (
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Variable,
)

from ..grammar import constants as const
from ._reset_path_state import WriteKey, WriteMap

type StmtBranch = tuple[Any, list[Any]]
type IfTuple = tuple[str, list[StmtBranch] | None, list[Any] | None]
type AssignTuple = tuple[str, Any, Any]
type FunctionCallTuple = tuple[str, str, list[Any] | None]


def _new_boolean_write_map() -> dict[WriteKey, tuple[Variable, str]]:
    return {}


def _children_of(obj: Any) -> list[Any] | None:
    children = getattr(obj, "children", None)
    return cast(list[Any], children) if isinstance(children, list) else None


@dataclass
class BooleanPathState:
    true_writes: dict[WriteKey, tuple[Variable, str]] = field(default_factory=_new_boolean_write_map)
    false_writes: dict[WriteKey, tuple[Variable, str]] = field(default_factory=_new_boolean_write_map)

    def clone(self) -> BooleanPathState:
        return BooleanPathState(
            true_writes=dict(self.true_writes),
            false_writes=dict(self.false_writes),
        )


def all_boolean_paths_cover_false(states: list[BooleanPathState], key: WriteKey) -> bool:
    return bool(states) and all(boolean_path_covers_false(state.false_writes, key) for state in states)


def boolean_path_covers_false(false_writes: WriteMap, key: WriteKey) -> bool:
    variable_key, _field_key = key
    return key in false_writes or (variable_key, "") in false_writes


def collect_boolean_stmt_block_paths(
    statements: list[Any],
    env: dict[str, Variable],
    states: list[BooleanPathState],
) -> list[BooleanPathState]:
    next_states = states
    for statement in statements:
        next_states = collect_boolean_stmt_paths(statement, env, next_states)
    return next_states


def collect_boolean_stmt_paths(
    obj: Any,
    env: dict[str, Variable],
    states: list[BooleanPathState],
) -> list[BooleanPathState]:
    if obj is None:
        return states
    if hasattr(obj, "data") and obj.data == const.KEY_STATEMENT:
        next_states = states
        for child in _children_of(obj) or []:
            next_states = collect_boolean_stmt_paths(child, env, next_states)
        return next_states

    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
        _, branches, else_block = cast(IfTuple, obj)
        branch_states: list[BooleanPathState] = []
        for state in states:
            for _condition, branch_statements in branches or []:
                branch_states.extend(
                    collect_boolean_stmt_block_paths(
                        branch_statements or [],
                        env,
                        [state.clone()],
                    )
                )
            if else_block:
                branch_states.extend(
                    collect_boolean_stmt_block_paths(
                        else_block or [],
                        env,
                        [state.clone()],
                    )
                )
            else:
                branch_states.append(state.clone())
        return branch_states or states

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
        _, target, expr = cast(AssignTuple, obj)
        assigned_states: list[BooleanPathState] = []
        for state in states:
            next_state = state.clone()
            record_boolean_assignment(target, expr, env, next_state)
            assigned_states.append(next_state)
        return assigned_states or states

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
        _, fn_name, args = cast(FunctionCallTuple, obj)
        call_states: list[BooleanPathState] = []
        for state in states:
            next_state = state.clone()
            record_boolean_function_call(fn_name, args or [], env, next_state)
            call_states.append(next_state)
        return call_states or states

    if isinstance(obj, list):
        next_states = states
        for item in cast(list[Any], obj):
            next_states = collect_boolean_stmt_paths(item, env, next_states)
        return next_states

    children = _children_of(obj)
    if children is not None:
        next_states = states
        for child in children:
            next_states = collect_boolean_stmt_paths(child, env, next_states)
        return next_states

    return states


def collect_boolean_seq_block_paths(
    nodes: list[Any],
    env: dict[str, Variable],
    states: list[BooleanPathState],
) -> list[BooleanPathState]:
    next_states = states
    for node in nodes:
        next_states = collect_boolean_seq_node_paths(node, env, next_states)
    return next_states


def collect_boolean_seq_node_paths(
    node: Any,
    env: dict[str, Variable],
    states: list[BooleanPathState],
) -> list[BooleanPathState]:
    if isinstance(node, SFCStep):
        next_states = collect_boolean_stmt_block_paths(node.code.enter or [], env, states)
        next_states = collect_boolean_stmt_block_paths(node.code.active or [], env, next_states)
        return collect_boolean_stmt_block_paths(node.code.exit or [], env, next_states)

    if isinstance(node, SFCTransition):
        return states

    if isinstance(node, SFCAlternative):
        if not node.branches:
            return states
        alternative_states: list[BooleanPathState] = []
        for state in states:
            for branch in node.branches or []:
                alternative_states.extend(
                    collect_boolean_seq_block_paths(
                        branch or [],
                        env,
                        [state.clone()],
                    )
                )
        return alternative_states or states

    if isinstance(node, SFCParallel):
        if not node.branches:
            return states
        parallel_states: list[BooleanPathState] = []
        for state in states:
            branch_results = [
                collect_boolean_seq_block_paths(
                    branch or [],
                    env,
                    [state.clone()],
                )
                for branch in node.branches or []
            ]
            parallel_states.extend(merge_boolean_parallel_branch_results(branch_results))
        return parallel_states or states

    if isinstance(node, SFCSubsequence | SFCTransitionSub):
        return collect_boolean_seq_block_paths(node.body or [], env, states)

    return states


def merge_boolean_parallel_branch_results(
    branch_results: list[list[BooleanPathState]],
) -> list[BooleanPathState]:
    if not branch_results:
        return []

    merged_states: list[BooleanPathState] = []
    for combo in product(*branch_results):
        merged = combo[0].clone()
        for branch_state in combo[1:]:
            merged.true_writes.update(branch_state.true_writes)
            merged.false_writes.update(branch_state.false_writes)
        merged_states.append(merged)
    return merged_states


def record_boolean_assignment(
    target: Any,
    expr: Any,
    env: dict[str, Variable],
    state: BooleanPathState,
) -> None:
    bool_value = literal_boolean(expr)
    if bool_value is None:
        return
    record_boolean_write(target, env, state.true_writes if bool_value else state.false_writes)


def record_boolean_function_call(
    function_name: str,
    args: list[Any],
    env: dict[str, Variable],
    state: BooleanPathState,
) -> None:
    if function_name.casefold() != "setbooleanvalue" or len(args) < 2:
        return
    bool_value = literal_boolean(args[1])
    if bool_value is None:
        return
    record_boolean_write(args[0], env, state.true_writes if bool_value else state.false_writes)


def literal_boolean(expr: Any) -> bool | None:
    if isinstance(expr, bool):
        return expr
    return None


def record_boolean_write(target: Any, env: dict[str, Variable], out: WriteMap) -> None:
    if not isinstance(target, dict) or const.KEY_VAR_NAME not in target:
        return
    full_ref = cast(dict[str, object], target).get(const.KEY_VAR_NAME)
    if not isinstance(full_ref, str) or not full_ref:
        return
    base, field_path = split_var_ref(full_ref)
    if not base or field_path:
        return
    variable = env.get(base.casefold())
    if variable is None or variable.datatype_text.casefold() != "boolean":
        return
    out[(variable.name.casefold(), "")] = (variable, "")


def split_var_ref(var_ref: str) -> tuple[str, str]:
    if not var_ref:
        return "", ""
    if "." not in var_ref:
        return var_ref, ""
    return tuple(var_ref.split(".", 1))  # type: ignore[return-value]


__all__ = [
    "BooleanPathState",
    "all_boolean_paths_cover_false",
    "boolean_path_covers_false",
    "collect_boolean_seq_block_paths",
    "collect_boolean_seq_node_paths",
    "collect_boolean_stmt_block_paths",
    "collect_boolean_stmt_paths",
    "literal_boolean",
    "merge_boolean_parallel_branch_results",
    "record_boolean_assignment",
    "record_boolean_function_call",
    "record_boolean_write",
]
