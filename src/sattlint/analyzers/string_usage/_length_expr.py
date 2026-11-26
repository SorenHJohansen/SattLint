"""Expression evaluation over the length-only abstract state."""

from __future__ import annotations

from sattlint.parser_api import BinOp, FuncCall, TernaryOp, UnaryOp, VarRef

from ...resolution.common import varname_full
from ...resolution.scope import ScopeContext
from .._string_models import StringSlot
from ..string_contexts import resolve_string_slot
from ._length_model import (
    IntValue,
    LengthState,
    LengthValue,
    join_int,
    join_length,
    normalize_int,
    normalize_length,
    unknown_length,
)
from ._model import SlotTypes


def _resolve_reference(scope: ScopeContext, argument: object) -> StringSlot | None:
    ref_name = varname_full(argument)
    if not ref_name:
        return None
    return resolve_string_slot(scope, ref_name)


class LengthExpressionEvaluator:
    """Evaluate the string and integer expressions the writers depend on."""

    _types: SlotTypes

    def _eval_string_expr(
        self,
        expr: object,
        state: LengthState,
        scope: ScopeContext,
    ) -> LengthValue:
        if isinstance(expr, str):
            return normalize_length((len(expr),), (len(expr) + 1,), written=False)
        if isinstance(expr, VarRef):
            target = _resolve_reference(scope, expr)
            if target is None or not self._types.is_string(target):
                return unknown_length()
            return state.strings.get(target.key, unknown_length())
        if isinstance(expr, TernaryOp):
            merged = unknown_length()
            for _condition, branch_expr in expr.branches:
                merged = join_length(merged, self._eval_string_expr(branch_expr, state, scope))
            if expr.else_expr is not None:
                merged = join_length(merged, self._eval_string_expr(expr.else_expr, state, scope))
            return merged
        return unknown_length()

    def _eval_int_expr(
        self,
        expr: object,
        state: LengthState,
        scope: ScopeContext,
    ) -> IntValue:
        if isinstance(expr, bool):
            return IntValue()
        if isinstance(expr, int):
            return normalize_int((expr,))
        if isinstance(expr, VarRef):
            target = _resolve_reference(scope, expr)
            if target is None:
                return IntValue()
            return state.ints.get(target.key, IntValue())
        if isinstance(expr, FuncCall):
            name = expr.name.casefold()
            args = list(expr.args)
            if name == "stringlength" and args:
                source = self._eval_string_expr(args[0], state, scope)
                if not source.known:
                    return IntValue()
                return normalize_int(source.lengths)
            if name == "getstringpos" and args:
                source = self._eval_string_expr(args[0], state, scope)
                if not source.known:
                    return IntValue()
                return normalize_int(source.cursors)
            if name == "maxstringlength" and args:
                target = _resolve_reference(scope, args[0])
                capacity = self._types.capacity(target) if target is not None else None
                return normalize_int((capacity,)) if capacity is not None else IntValue()
        if isinstance(expr, BinOp):
            left = self._eval_int_expr(expr.left, state, scope)
            right = self._eval_int_expr(expr.right, state, scope)
            if not left.known or not right.known:
                return IntValue()
            values: list[int] = []
            for left_value in left.values:
                for right_value in right.values:
                    if expr.op == "+":
                        values.append(left_value + right_value)
                    elif expr.op == "-":
                        values.append(left_value - right_value)
                    else:
                        return IntValue()
            return normalize_int(values)
        if isinstance(expr, UnaryOp):
            if expr.op == "-":
                source = self._eval_int_expr(expr.operand, state, scope)
                if not source.known:
                    return IntValue()
                return normalize_int(-value for value in source.values)
            if expr.op == "+":
                return self._eval_int_expr(expr.operand, state, scope)
        if isinstance(expr, TernaryOp):
            merged = IntValue()
            for _condition, branch_expr in expr.branches:
                merged = join_int(merged, self._eval_int_expr(branch_expr, state, scope))
            if expr.else_expr is not None:
                merged = join_int(merged, self._eval_int_expr(expr.else_expr, state, scope))
            return merged
        return IntValue()


__all__ = ["LengthExpressionEvaluator"]
