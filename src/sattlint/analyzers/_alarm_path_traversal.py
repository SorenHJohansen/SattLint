"""Alarm-path traversal helpers for boolean write collection."""

from __future__ import annotations

from dataclasses import dataclass, field

from sattlint.parser_api import (
    Assignment,
    FuncCallStmt,
    IfStmt,
    ModuleCode,
    Sequence,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransitionSub,
    Variable,
)

from ..resolution.common import varname_full


def _empty_bool_values() -> set[bool]:
    return set()


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
    for equation in modulecode.equationblocks or []:
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

    if isinstance(obj, Assignment):
        record_boolean_write(obj.target, obj.value, env, writes)
        collect_boolean_writes(obj.value, env, writes)
        return

    if isinstance(obj, FuncCallStmt):
        call = obj.call
        if call.name.casefold() == "setbooleanvalue" and len(call.args) >= 2:
            record_boolean_write(call.args[0], call.args[1], env, writes)
        for argument in call.args:
            collect_boolean_writes(argument, env, writes)
        return

    if isinstance(obj, IfStmt):
        for condition, branch_statements in obj.branches:
            collect_boolean_writes(condition, env, writes)
            for statement in branch_statements:
                collect_boolean_writes(statement, env, writes)
        for statement in obj.else_block or ():
            collect_boolean_writes(statement, env, writes)


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
