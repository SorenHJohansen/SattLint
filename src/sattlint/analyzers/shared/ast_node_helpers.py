from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from sattlint.parser_api import Assignment, FuncCallStmt, IfStmt, VarRef


def sequence_as_list(node: object) -> list[object]:
    """Return a list for a list or tuple value, or an empty list otherwise."""
    if isinstance(node, list | tuple):
        return list(cast(Sequence[object], node))
    return []


def is_statement_node(node: object) -> bool:
    """True when node is a statement-level AST node."""
    return isinstance(node, Assignment | FuncCallStmt | IfStmt)


def assignment_target(node: object) -> object:
    if isinstance(node, Assignment):
        return node.target
    return None


def assignment_value(node: object) -> object:
    if isinstance(node, Assignment):
        return node.value
    return None


def if_branches(node: object) -> list[tuple[object, list[object]]]:
    if isinstance(node, IfStmt):
        return [(cast(object, cond), list(body)) for cond, body in node.branches]
    return []


def if_else_block(node: object) -> list[object] | None:
    if isinstance(node, IfStmt):
        return list(node.else_block) if node.else_block is not None else None
    return None


def varref_name(node: object) -> str | None:
    if isinstance(node, VarRef):
        return node.name
    return None


def varref_state(node: object) -> str | None:
    if isinstance(node, VarRef):
        return node.state
    return None
