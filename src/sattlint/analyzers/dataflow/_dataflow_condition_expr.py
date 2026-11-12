# pyright: reportUnusedFunction=false
from __future__ import annotations

from typing import Any

from sattlint.parser_api import BinOp, BoolOp, Compare, NotOp, TernaryOp, UnaryOp, VarRef

type ExprNode = Any
type ComparePair = tuple[str, ExprNode]
type TernaryBranch = tuple[ExprNode, ExprNode]
type BinaryOpPart = tuple[str, ExprNode]


def is_var_ref(node: object) -> bool:
    return isinstance(node, VarRef)


def var_ref_name(node: object) -> str | None:
    if isinstance(node, VarRef):
        return node.name
    return None


def is_bool_op(node: object) -> bool:
    return isinstance(node, BoolOp)


def bool_op_operator(node: object) -> str | None:
    if isinstance(node, BoolOp):
        return node.op
    return None


def bool_op_operands(node: object) -> list[object]:
    if isinstance(node, BoolOp):
        return list(node.operands)
    return []


def is_not_op(node: object) -> bool:
    return isinstance(node, NotOp)


def not_op_operand(node: object) -> object | None:
    if isinstance(node, NotOp):
        return node.operand
    return None


def is_compare(node: object) -> bool:
    return isinstance(node, Compare)


def compare_parts(node: object) -> list[ComparePair] | None:
    """Return [(operator, right_expr), ...] for a (possibly chained) Compare."""
    parts: list[ComparePair] = []
    current = node
    while isinstance(current, Compare):
        parts.append((current.op, current.right))
        current = current.left
    return parts or None


def compare_left(node: object) -> object | None:
    if isinstance(node, Compare):
        return node.left
    return None


def is_bin_op(node: object) -> bool:
    return isinstance(node, BinOp)


def bin_op_parts(node: object) -> list[BinaryOpPart] | None:
    """Return [(operator, right_expr), ...] for a (possibly chained) BinOp."""
    parts: list[BinaryOpPart] = []
    current = node
    while isinstance(current, BinOp):
        parts.append((current.op, current.right))
        current = current.left
    return parts or None


def bin_op_left(node: object) -> object | None:
    if isinstance(node, BinOp):
        return node.left
    return None


def is_unary_op(node: object) -> bool:
    return isinstance(node, UnaryOp)


def unary_op_operator(node: object) -> str | None:
    if isinstance(node, UnaryOp):
        return node.op
    return None


def unary_op_operand(node: object) -> object | None:
    if isinstance(node, UnaryOp):
        return node.operand
    return None


def is_ternary(node: object) -> bool:
    return isinstance(node, TernaryOp)


def ternary_parts(node: object) -> tuple[list[TernaryBranch], ExprNode | None] | None:
    if isinstance(node, TernaryOp):
        return list(node.branches), node.else_expr
    return None
