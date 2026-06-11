from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sattline_parser.models.ast_model import (
    ModuleCode,
    Sequence,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
)

from ..grammar import constants as const
from ..resolution.common import varname_full
from .shared.ast_node_helpers import (
    iter_branch_pairs,
    object_dict_values,
    object_list,
    object_sequence,
    object_tuple,
    statement_children,
    string_key_dict,
)


@dataclass(frozen=True)
class StatementSite:
    label: str
    statement: Any


@dataclass(frozen=True)
class AssignmentEvent:
    target_name: str
    expr: Any


def _iter_sequence_values(node: object) -> Iterator[object]:
    items = object_sequence(node)
    if items is None:
        return
    yield from items


def iter_statement_sites(modulecode: ModuleCode) -> list[StatementSite]:
    sites: list[StatementSite] = []
    for equation in modulecode.equations or []:
        label = f"equation block {equation.name!r}"
        for statement in equation.code or []:
            sites.append(StatementSite(label=label, statement=statement))
    for sequence in modulecode.sequences or []:
        sites.extend(_iter_sequence_statement_sites(sequence))
    return sites


def _iter_sequence_statement_sites(sequence: Sequence) -> list[StatementSite]:
    sites: list[StatementSite] = []
    for node in sequence.code or []:
        sites.extend(_iter_sequence_node_statement_sites(sequence.name, node))
    return sites


def _iter_sequence_node_statement_sites(sequence_name: str, node: Any) -> list[StatementSite]:
    if isinstance(node, SFCStep):
        sites: list[StatementSite] = []
        if node.code.enter:
            label = f"sequence {sequence_name!r} step {node.name!r} ENTER"
            for statement in node.code.enter:
                sites.append(StatementSite(label=label, statement=statement))
        if node.code.active:
            label = f"sequence {sequence_name!r} step {node.name!r} ACTIVE"
            for statement in node.code.active:
                sites.append(StatementSite(label=label, statement=statement))
        if node.code.exit:
            label = f"sequence {sequence_name!r} step {node.name!r} EXIT"
            for statement in node.code.exit:
                sites.append(StatementSite(label=label, statement=statement))
        return sites

    if isinstance(node, SFCTransition):
        if node.condition is None:
            return []
        return [
            StatementSite(
                label=f"sequence {sequence_name!r} transition {node.name!r} condition",
                statement=node.condition,
            )
        ]

    if isinstance(node, SFCAlternative | SFCParallel):
        sites: list[StatementSite] = []
        for branch in node.branches or []:
            for child in branch:
                sites.extend(_iter_sequence_node_statement_sites(sequence_name, child))
        return sites

    if isinstance(node, SFCSubsequence | SFCTransitionSub):
        sites: list[StatementSite] = []
        for child in node.body or []:
            sites.extend(_iter_sequence_node_statement_sites(sequence_name, child))
        return sites

    return []


def root_variable_name(node: object) -> str | None:
    full_name = varname_full(node)
    node_dict = string_key_dict(node)
    if not full_name and node_dict is not None:
        raw_name = node_dict.get(const.KEY_VAR_NAME)
        if isinstance(raw_name, str):
            full_name = raw_name
    if not full_name:
        return None
    return full_name.split(":", 1)[0].split(".", 1)[0]


def iter_assignment_events(node: object) -> Iterator[AssignmentEvent]:
    if node is None:
        return

    direct_statement_children = statement_children(node)
    if direct_statement_children is not None:
        for child in direct_statement_children:
            yield from iter_assignment_events(child)
        return

    tuple_node = object_tuple(node)
    if tuple_node is not None and tuple_node:
        tag = tuple_node[0]
        if tag == const.KEY_ASSIGN and len(tuple_node) >= 3:
            target = tuple_node[1]
            expr = tuple_node[2]
            target_name = root_variable_name(target)
            if target_name:
                yield AssignmentEvent(target_name=target_name, expr=expr)
            return
        if tag == const.KEY_FUNCTION_CALL and len(tuple_node) == 3:
            function_name = tuple_node[1]
            args = object_sequence(tuple_node[2])
            function_name_text = function_name if isinstance(function_name, str) else ""
            if function_name_text.casefold() == "setbooleanvalue" and args is not None and len(args) >= 2:
                target_name = root_variable_name(args[0])
                if target_name:
                    yield AssignmentEvent(target_name=target_name, expr=args[1])
                for argument in args[1:]:
                    yield from iter_assignment_events(argument)
                return
            for argument in args or ():
                yield from iter_assignment_events(argument)
            return
        if tag == const.GRAMMAR_VALUE_IF and len(tuple_node) == 3:
            branches = tuple_node[1]
            else_block = tuple_node[2]
            for _condition, branch_statements in iter_branch_pairs(branches):
                for statement in _iter_sequence_values(branch_statements):
                    yield from iter_assignment_events(statement)
            for statement in _iter_sequence_values(else_block):
                yield from iter_assignment_events(statement)
            return
        if tag == const.KEY_TERNARY and len(tuple_node) == 3:
            branches = tuple_node[1]
            else_expr = tuple_node[2]
            for _condition, then_expr in iter_branch_pairs(branches):
                yield from iter_assignment_events(then_expr)
            yield from iter_assignment_events(else_expr)
            return
        for child in tuple_node[1:]:
            yield from iter_assignment_events(child)
        return

    list_node = object_list(node)
    if list_node is not None:
        for item in list_node:
            yield from iter_assignment_events(item)
        return

    children = object_sequence(getattr(node, "children", None))
    if children is not None:
        for child in children:
            yield from iter_assignment_events(child)
        return

    for value in object_dict_values(node):
        yield from iter_assignment_events(value)


def iter_read_variable_names(node: object) -> Iterator[str]:
    if node is None:
        return

    node_dict = string_key_dict(node)
    if node_dict is not None and const.KEY_VAR_NAME in node_dict:
        name = root_variable_name(node_dict)
        if name is not None:
            yield name
        return

    direct_statement_children = statement_children(node)
    if direct_statement_children is not None:
        for child in direct_statement_children:
            yield from iter_read_variable_names(child)
        return

    tuple_node = object_tuple(node)
    if tuple_node is not None and tuple_node:
        tag = tuple_node[0]
        if tag == const.KEY_ASSIGN and len(tuple_node) >= 3:
            yield from iter_read_variable_names(tuple_node[2])
            return
        if tag == const.KEY_FUNCTION_CALL and len(tuple_node) == 3:
            function_name = tuple_node[1]
            args = object_sequence(tuple_node[2])
            function_name_text = function_name if isinstance(function_name, str) else ""
            if function_name_text.casefold() == "setbooleanvalue" and args is not None and len(args) >= 2:
                yield from iter_read_variable_names(args[1])
                return
            for argument in args or ():
                yield from iter_read_variable_names(argument)
            return
        if tag == const.GRAMMAR_VALUE_IF and len(tuple_node) == 3:
            branches = tuple_node[1]
            else_block = tuple_node[2]
            for condition, branch_statements in iter_branch_pairs(branches):
                yield from iter_read_variable_names(condition)
                for statement in _iter_sequence_values(branch_statements):
                    yield from iter_read_variable_names(statement)
            for statement in _iter_sequence_values(else_block):
                yield from iter_read_variable_names(statement)
            return
        for child in tuple_node[1:]:
            yield from iter_read_variable_names(child)
        return

    if node_dict is not None:
        for value in node_dict.values():
            yield from iter_read_variable_names(value)
        return

    list_node = object_list(node)
    if list_node is not None:
        for item in list_node:
            yield from iter_read_variable_names(item)
        return

    children = object_sequence(getattr(node, "children", None))
    if children is not None:
        for child in children:
            yield from iter_read_variable_names(child)
        return

    for value in object_dict_values(node):
        yield from iter_read_variable_names(value)
