"""Alarm-path traversal helpers for boolean write collection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from sattline_parser.models.ast_model import (
    ModuleCode,
    Sequence,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransitionSub,
    Variable,
)

from ..grammar import constants as const
from ..resolution.common import varname_full


def _empty_bool_values() -> set[bool]:
    return set()


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


def _iter_branch_pairs(node: object) -> list[tuple[object, object]]:
    branches = _object_sequence(node)
    if branches is None:
        return []
    pairs: list[tuple[object, object]] = []
    for branch in branches:
        branch_items = _object_sequence(branch)
        if branch_items is None or len(branch_items) < 2:
            continue
        pairs.append((branch_items[0], branch_items[1]))
    return pairs


@dataclass
class AlarmBooleanWriteSummary:
    display: str
    values: set[bool] = field(default_factory=_empty_bool_values)


def collect_alarm_boolean_writes(
    modulecode: ModuleCode,
    env: dict[str, Variable],
) -> dict[str, AlarmBooleanWriteSummary]:
    writes: dict[str, AlarmBooleanWriteSummary] = {}
    for statement in iter_modulecode_statements(modulecode):
        collect_boolean_writes(statement, env, writes)
    return writes


def iter_modulecode_statements(modulecode: ModuleCode) -> list[object]:
    statements: list[object] = []
    for equation in modulecode.equations or []:
        statements.extend(equation.code or [])
    for sequence in modulecode.sequences or []:
        statements.extend(iter_sequence_statements(sequence))
    return statements


def iter_sequence_statements(sequence: Sequence) -> list[object]:
    statements: list[object] = []
    for node in sequence.code or []:
        statements.extend(iter_sequence_node_statements(node))
    return statements


def iter_sequence_node_statements(node: object) -> list[object]:
    if isinstance(node, SFCStep):
        return [*(node.code.enter or []), *(node.code.active or []), *(node.code.exit or [])]
    if isinstance(node, SFCAlternative | SFCParallel):
        branch_statements: list[object] = []
        for branch in node.branches or []:
            for child in branch:
                branch_statements.extend(iter_sequence_node_statements(child))
        return branch_statements
    if isinstance(node, SFCSubsequence | SFCTransitionSub):
        nested_statements: list[object] = []
        for child in node.body or []:
            nested_statements.extend(iter_sequence_node_statements(child))
        return nested_statements
    return []


def collect_boolean_writes(
    obj: object,
    env: dict[str, Variable],
    writes: dict[str, AlarmBooleanWriteSummary],
) -> None:
    if obj is None:
        return

    statement_children = _statement_children(obj)
    if statement_children is not None:
        for child in statement_children:
            collect_boolean_writes(child, env, writes)
        return

    tuple_node = _object_tuple(obj)
    if tuple_node is not None and tuple_node and tuple_node[0] == const.GRAMMAR_VALUE_IF:
        branches = tuple_node[1] if len(tuple_node) > 1 else None
        else_block = tuple_node[2] if len(tuple_node) > 2 else None
        for condition, branch_statements in _iter_branch_pairs(branches):
            collect_boolean_writes(condition, env, writes)
            for statement in _sequence_as_list(branch_statements):
                collect_boolean_writes(statement, env, writes)
        for statement in _sequence_as_list(else_block):
            collect_boolean_writes(statement, env, writes)
        return

    if tuple_node is not None and tuple_node and tuple_node[0] == const.KEY_ASSIGN and len(tuple_node) >= 3:
        target = tuple_node[1]
        expr = tuple_node[2]
        record_boolean_write(target, expr, env, writes)
        collect_boolean_writes(expr, env, writes)
        return

    if tuple_node is not None and tuple_node and tuple_node[0] == const.KEY_FUNCTION_CALL:
        function_name = tuple_node[1] if len(tuple_node) > 1 and isinstance(tuple_node[1], str) else ""
        args = _sequence_as_list(tuple_node[2] if len(tuple_node) > 2 else None)
        if function_name.casefold() == "setbooleanvalue" and len(args) >= 2:
            record_boolean_write(args[0], args[1], env, writes)
        for argument in args:
            collect_boolean_writes(argument, env, writes)
        return

    if tuple_node is not None and tuple_node and tuple_node[0] == const.KEY_TERNARY:
        branches = tuple_node[1] if len(tuple_node) > 1 else None
        else_expr = tuple_node[2] if len(tuple_node) > 2 else None
        for condition, then_expr in _iter_branch_pairs(branches):
            collect_boolean_writes(condition, env, writes)
            collect_boolean_writes(then_expr, env, writes)
        collect_boolean_writes(else_expr, env, writes)
        return

    if tuple_node is not None and tuple_node and tuple_node[0] in (const.KEY_COMPARE, const.KEY_ADD, const.KEY_MUL):
        for child in tuple_node[1:]:
            collect_boolean_writes(child, env, writes)
        return

    if (
        tuple_node is not None
        and tuple_node
        and tuple_node[0] in (const.KEY_PLUS, const.KEY_MINUS, const.GRAMMAR_VALUE_NOT)
    ):
        collect_boolean_writes(tuple_node[1] if len(tuple_node) > 1 else None, env, writes)
        return

    if tuple_node is not None and tuple_node and tuple_node[0] in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND):
        for child in _sequence_as_list(tuple_node[1] if len(tuple_node) > 1 else None):
            collect_boolean_writes(child, env, writes)
        return

    list_node = _object_list(obj)
    if list_node is not None:
        for item in list_node:
            collect_boolean_writes(item, env, writes)
        return

    children = _object_sequence(getattr(obj, "children", None))
    if children is not None:
        for child in children:
            collect_boolean_writes(child, env, writes)


def record_boolean_write(
    target: object,
    expr: object,
    env: dict[str, Variable],
    writes: dict[str, AlarmBooleanWriteSummary],
) -> None:
    target_ref = varname_full(target)
    if not target_ref:
        return
    if not looks_like_alarm_reference(target_ref, env):
        return
    bool_value = as_bool_literal(expr)
    if bool_value is None:
        return

    entry = writes.setdefault(
        target_ref.casefold(),
        AlarmBooleanWriteSummary(display=target_ref),
    )
    entry.values.add(bool_value)


def looks_like_alarm_reference(
    target_ref: str,
    env: dict[str, Variable],
) -> bool:
    base_name = target_ref.split(".", 1)[0]
    variable = env.get(base_name.casefold())
    if variable is None:
        return False
    datatype_text = variable.datatype_text.casefold()
    if datatype_text != "boolean":
        return False
    return "alarm" in target_ref.casefold()


def as_bool_literal(expr: object) -> bool | None:
    if isinstance(expr, bool):
        return expr
    return None


__all__ = [
    "AlarmBooleanWriteSummary",
    "as_bool_literal",
    "collect_alarm_boolean_writes",
    "collect_boolean_writes",
    "iter_modulecode_statements",
    "iter_sequence_node_statements",
    "iter_sequence_statements",
    "looks_like_alarm_reference",
    "record_boolean_write",
]
