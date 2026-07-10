from __future__ import annotations

from typing import Any, cast

from ...grammar import constants as const

type ExprNode = Any
type ComparePair = tuple[str, ExprNode]
type CompareTuple = tuple[str, ExprNode, list[ComparePair] | None]
type TernaryBranch = tuple[ExprNode, ExprNode]
type TernaryTuple = tuple[str, list[TernaryBranch] | None, ExprNode | None]
type FunctionCallTuple = tuple[str, str | None, list[ExprNode] | None]
type LogicalTuple = tuple[str, list[ExprNode] | None]
type BinaryOpPart = tuple[str, ExprNode]
type BinaryOpTuple = tuple[str, ExprNode, list[BinaryOpPart] | None]

type ExprTuple = tuple[object, ...]
type ExprList = list[object]


def _expr_tuple(value: object) -> ExprTuple | None:
    return cast(ExprTuple, value) if isinstance(value, tuple) else None


def _expr_list(value: object) -> ExprList | None:
    return cast(ExprList, value) if isinstance(value, list) else None


def _expr_items(value: object) -> list[object]:
    tuple_value = _expr_tuple(value)
    if tuple_value is not None:
        return list(tuple_value)
    list_value = _expr_list(value)
    if list_value is not None:
        return list_value
    return []


def _statement_children(value: object) -> list[object] | None:
    if getattr(value, "data", None) != const.KEY_STATEMENT:
        return None
    return _expr_list(getattr(value, "children", None))
