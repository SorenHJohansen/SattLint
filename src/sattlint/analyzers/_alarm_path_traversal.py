"""Alarm-path traversal helpers for boolean write collection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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


@dataclass
class AlarmBooleanWriteSummary:
    display: str
    values: set[bool] = field(default_factory=set)


def collect_alarm_boolean_writes(
    modulecode: ModuleCode,
    env: dict[str, Variable],
) -> dict[str, AlarmBooleanWriteSummary]:
    writes: dict[str, AlarmBooleanWriteSummary] = {}
    for statement in iter_modulecode_statements(modulecode):
        collect_boolean_writes(statement, env, writes)
    return writes


def iter_modulecode_statements(modulecode: ModuleCode) -> list[Any]:
    statements: list[Any] = []
    for equation in modulecode.equations or []:
        statements.extend(equation.code or [])
    for sequence in modulecode.sequences or []:
        statements.extend(iter_sequence_statements(sequence))
    return statements


def iter_sequence_statements(sequence: Sequence) -> list[Any]:
    statements: list[Any] = []
    for node in sequence.code or []:
        statements.extend(iter_sequence_node_statements(node))
    return statements


def iter_sequence_node_statements(node: Any) -> list[Any]:
    if isinstance(node, SFCStep):
        return [*(node.code.enter or []), *(node.code.active or []), *(node.code.exit or [])]
    if isinstance(node, SFCAlternative | SFCParallel):
        branch_statements: list[Any] = []
        for branch in node.branches or []:
            for child in branch:
                branch_statements.extend(iter_sequence_node_statements(child))
        return branch_statements
    if isinstance(node, SFCSubsequence | SFCTransitionSub):
        nested_statements: list[Any] = []
        for child in node.body or []:
            nested_statements.extend(iter_sequence_node_statements(child))
        return nested_statements
    return []


def collect_boolean_writes(
    obj: Any,
    env: dict[str, Variable],
    writes: dict[str, AlarmBooleanWriteSummary],
) -> None:
    if obj is None:
        return

    if hasattr(obj, "data") and obj.data == const.KEY_STATEMENT:
        for child in getattr(obj, "children", []):
            collect_boolean_writes(child, env, writes)
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
        _if_tag, branches, else_block = obj
        for condition, branch_statements in branches or []:
            collect_boolean_writes(condition, env, writes)
            for statement in branch_statements or []:
                collect_boolean_writes(statement, env, writes)
        for statement in else_block or []:
            collect_boolean_writes(statement, env, writes)
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
        _assign, target, expr = obj
        record_boolean_write(target, expr, env, writes)
        collect_boolean_writes(expr, env, writes)
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
        _call, function_name, args = obj
        if (function_name or "").casefold() == "setbooleanvalue" and len(args or []) >= 2:
            record_boolean_write(args[0], args[1], env, writes)
        for argument in args or []:
            collect_boolean_writes(argument, env, writes)
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_TERNARY:
        _ternary, branches, else_expr = obj
        for condition, then_expr in branches or []:
            collect_boolean_writes(condition, env, writes)
            collect_boolean_writes(then_expr, env, writes)
        collect_boolean_writes(else_expr, env, writes)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_COMPARE, const.KEY_ADD, const.KEY_MUL):
        for child in obj[1:]:
            collect_boolean_writes(child, env, writes)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_PLUS, const.KEY_MINUS, const.GRAMMAR_VALUE_NOT):
        collect_boolean_writes(obj[1], env, writes)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND):
        for child in obj[1] or []:
            collect_boolean_writes(child, env, writes)
        return

    if isinstance(obj, list):
        for item in obj:
            collect_boolean_writes(item, env, writes)
        return

    if hasattr(obj, "children"):
        for child in getattr(obj, "children", []):
            collect_boolean_writes(child, env, writes)


def record_boolean_write(
    target: Any,
    expr: Any,
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


def as_bool_literal(expr: Any) -> bool | None:
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
