# pyright: reportPrivateUsage=false
from __future__ import annotations

from typing import Any, cast

from sattline_parser.models.ast_model import FloatLiteral, IntLiteral
from sattline_parser.models.expressions import BinOp, FuncCall

from ...grammar import constants as const
from ...resolution.scope import ScopeContext
from ._dataflow_common import (
    UNKNOWN,
    ConditionFact,
    ResolvedRef,
    ScalarValue,
    StateMap,
    invert_compare_operator,
    is_scalar_value,
)
from ._dataflow_condition_expr import (
    BinaryOpTuple,
    CompareTuple,
    FunctionCallTuple,
    LogicalTuple,
    TernaryTuple,
    _expr_items,
    _expr_tuple,
    _statement_children,
    bin_op_parts,
    bool_op_operands,
    bool_op_operator,
    compare_left,
    compare_parts,
    is_bool_op,
    is_compare,
    is_not_op,
    is_ternary,
    is_unary_op,
    is_var_ref,
    not_op_operand,
    ternary_parts,
    unary_op_operand,
    unary_op_operator,
)
from ._dataflow_condition_facts import _DataflowConditionFactsMixin


class _DataflowConditionMixin(_DataflowConditionFactsMixin):
    def _report_condition(
        self: Any,
        condition: Any,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
        *,
        issue_prefix: str = "dataflow",
    ) -> bool | None:
        self._report_expression_temporal_hazards(condition, context, module_path, state)
        result = self._evaluate_condition(condition, context, module_path, state)
        condition_text = self._expr_text(condition)
        if result is True:
            self._add_issue(
                kind=f"{issue_prefix}.condition_always_true",
                message=f"Condition {condition_text!r} is always true at this point.",
                module_path=module_path,
                data={"condition": condition_text, "site": self._site_str()},
            )
        elif result is False:
            self._add_issue(
                kind=f"{issue_prefix}.condition_always_false",
                message=f"Condition {condition_text!r} is always false at this point.",
                module_path=module_path,
                data={"condition": condition_text, "site": self._site_str()},
            )
        return result

    def _evaluate_condition(
        self: Any,
        condition: Any,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> bool | None:
        self_compare = self._self_compare_truth(condition, context)
        if self_compare is not None:
            self._add_issue(
                kind="dataflow.self_compare_condition",
                message=(
                    f"Condition {self._expr_text(condition)!r} compares the same symbol on both sides and collapses to {self_compare}."
                ),
                module_path=module_path,
                data={"condition": self._expr_text(condition), "site": self._site_str()},
            )
            return self_compare

        shortcut = self._logical_shortcut_truth(condition, context)
        if shortcut is not None:
            return shortcut

        value = self._evaluate_expression(condition, context, module_path, state)
        if isinstance(value, bool):
            return value
        return None

    def _logical_shortcut_truth(
        self: Any,
        condition: object,
        context: ScopeContext,
    ) -> bool | None:
        if is_not_op(condition):
            truth = self._logical_shortcut_truth(not_op_operand(condition), context)
            return None if truth is None else not truth

        if is_bool_op(condition):
            operator = bool_op_operator(condition)
            facts = [
                fact
                for fact in (self._condition_fact(part, context) for part in bool_op_operands(condition))
                if fact is not None
            ]
            if operator == "AND":
                return self._facts_contradict(facts)
            return self._facts_form_tautology(facts)

        condition_tuple = _expr_tuple(condition)
        if condition_tuple is not None and condition_tuple:
            operator = condition_tuple[0]
            if operator == const.GRAMMAR_VALUE_NOT:
                truth = self._logical_shortcut_truth(
                    condition_tuple[1] if len(condition_tuple) > 1 else None,
                    context,
                )
                return None if truth is None else not truth

            if operator in (const.GRAMMAR_VALUE_AND, const.GRAMMAR_VALUE_OR):
                parts = _expr_items(condition_tuple[1] if len(condition_tuple) > 1 else None)
                facts = [fact for fact in (self._condition_fact(part, context) for part in parts) if fact is not None]
                if operator == const.GRAMMAR_VALUE_AND:
                    return self._facts_contradict(facts)
                return self._facts_form_tautology(facts)

        return None

    def _condition_fact(
        self: Any,
        expr: object,
        context: ScopeContext,
    ) -> ConditionFact | None:
        if is_var_ref(expr):
            resolved = self._resolve_ref(expr, context)
            if resolved is None:
                return None
            return ("bool", resolved.key, True)

        if isinstance(expr, dict):
            if const.KEY_VAR_NAME not in expr:
                return None
            resolved = self._resolve_ref(expr, context)
            if resolved is None:
                return None
            return ("bool", resolved.key, True)

        if is_not_op(expr):
            inner = self._condition_fact(not_op_operand(expr), context)
            return self._negate_condition_fact(inner)

        if is_compare(expr):
            pairs = compare_parts(expr)
            left_expr = compare_left(expr)
            if pairs is None or len(pairs) != 1 or left_expr is None:
                return None
            comparison_operator, right_expr = pairs[0]
            return self._comparison_fact(left_expr, comparison_operator, right_expr, context)

        expr_tuple = _expr_tuple(expr)
        if expr_tuple is not None and expr_tuple:
            operator = expr_tuple[0]
            if operator == const.GRAMMAR_VALUE_NOT:
                inner = self._condition_fact(expr_tuple[1] if len(expr_tuple) > 1 else None, context)
                return self._negate_condition_fact(inner)

            if operator in (const.KEY_COMPARE, "compare"):
                _, left_expr, pairs = cast(CompareTuple, expr_tuple)
                if pairs is None or len(pairs) != 1:
                    return None
                comparison_operator, right_expr = pairs[0]
                return self._comparison_fact(left_expr, comparison_operator, right_expr, context)

        return None

    def _negate_condition_fact(
        self: Any,
        fact: ConditionFact | None,
    ) -> ConditionFact | None:
        if fact is None:
            return None

        kind = fact[0]
        key = fact[1]
        if kind == "bool":
            return (kind, key, not cast(bool, fact[2]))

        operator, literal = cast(tuple[str, ScalarValue], fact[2])
        if operator == "==":
            return (kind, key, ("<>", literal))
        if operator == "<>":
            return (kind, key, ("==", literal))
        return None

    def _comparison_fact(
        self: Any,
        left_expr: Any,
        operator: str,
        right_expr: Any,
        context: ScopeContext,
    ) -> ConditionFact | None:
        left_ref = self._resolve_ref(left_expr, context)
        right_ref = self._resolve_ref(right_expr, context)
        left_literal = self._static_literal(left_expr)
        right_literal = self._static_literal(right_expr)

        if left_ref is not None and right_ref is None and right_literal is not UNKNOWN:
            return self._fact_from_ref_and_literal(left_ref, operator, right_literal)

        if right_ref is not None and left_literal is not UNKNOWN and left_ref is None:
            return self._fact_from_ref_and_literal(
                right_ref,
                invert_compare_operator(operator),
                left_literal,
            )

        return None

    def _fact_from_ref_and_literal(
        self: Any,
        resolved: ResolvedRef,
        operator: str,
        literal: ScalarValue | object,
    ) -> ConditionFact | None:
        if literal is UNKNOWN:
            return None

        if isinstance(literal, bool) and operator in {"==", "<>"}:
            truth = literal if operator == "==" else not literal
            return ("bool", resolved.key, truth)

        if operator in {"==", "<>"}:
            return ("compare", resolved.key, (operator, cast(ScalarValue, literal)))

        return None

    def _evaluate_expression(  # noqa: PLR0915
        self: Any,
        expr: object,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> ScalarValue | object:
        statement_children = _statement_children(expr)
        if statement_children is not None:
            if statement_children:
                return self._evaluate_expression(statement_children[0], context, module_path, state)
            return UNKNOWN

        if isinstance(expr, IntLiteral):
            return int(expr)
        if isinstance(expr, FloatLiteral):
            return float(expr)
        if isinstance(expr, bool):
            return expr
        if isinstance(expr, int):
            return expr
        if isinstance(expr, float):
            return expr
        if isinstance(expr, str):
            return expr

        if is_var_ref(expr):
            resolved = self._resolve_ref(expr, context)
            if resolved is None:
                return UNKNOWN
            return self._read_resolved_value(resolved, module_path, state)

        if isinstance(expr, dict):
            if const.KEY_VAR_NAME not in expr:
                return UNKNOWN
            resolved = self._resolve_ref(expr, context)
            if resolved is None:
                return UNKNOWN
            return self._read_resolved_value(resolved, module_path, state)

        if is_bool_op(expr):
            operator = bool_op_operator(expr)
            values = [self._evaluate_expression(part, context, module_path, state) for part in bool_op_operands(expr)]
            if operator == "OR":
                if any(value is True for value in values):
                    return True
                if all(value is False for value in values):
                    return False
            else:
                if any(value is False for value in values):
                    return False
                if values and all(value is True for value in values):
                    return True
            return UNKNOWN

        if is_not_op(expr):
            value = self._evaluate_expression(not_op_operand(expr), context, module_path, state)
            return (not value) if isinstance(value, bool) else UNKNOWN

        if is_compare(expr):
            pairs = compare_parts(expr)
            left_expr = compare_left(expr)
            if pairs is None or left_expr is None:
                return UNKNOWN
            left_value = self._evaluate_expression(left_expr, context, module_path, state)
            if not is_scalar_value(left_value):
                return UNKNOWN
            scalar_left = left_value
            results: list[bool] = []
            for operator, right_expr in pairs:
                right_value = self._evaluate_expression(right_expr, context, module_path, state)
                if not is_scalar_value(right_value):
                    return UNKNOWN
                scalar_right = right_value
                comparison = self._compare_values(scalar_left, operator, scalar_right)
                if comparison is None:
                    return UNKNOWN
                results.append(comparison)
            return all(results)

        if isinstance(expr, BinOp):
            left_value = self._evaluate_expression(expr.left, context, module_path, state)
            if not is_scalar_value(left_value):
                return UNKNOWN
            scalar_value = left_value
            for symbol, right_expr in bin_op_parts(expr) or []:
                right_value = self._evaluate_expression(right_expr, context, module_path, state)
                if not is_scalar_value(right_value):
                    return UNKNOWN
                scalar_right = right_value
                value = self._apply_arithmetic(symbol, scalar_value, scalar_right)
                if not is_scalar_value(value):
                    return UNKNOWN
                scalar_value = value
            return scalar_value

        if is_unary_op(expr):
            inner = self._evaluate_expression(unary_op_operand(expr), context, module_path, state)
            operator = unary_op_operator(expr)
            if not isinstance(inner, int | float) or isinstance(inner, bool):
                return UNKNOWN
            return inner if operator == const.KEY_PLUS else -inner

        if isinstance(expr, FuncCall):
            for argument in expr.args:
                self._evaluate_expression(argument, context, module_path, state)
            return UNKNOWN

        if is_ternary(expr):
            _, branches, else_expr = cast(TernaryTuple, ternary_parts(expr))
            branch_values: list[ScalarValue | object] = []
            fallthrough_state = state
            for condition, branch_expr in branches or []:
                condition_value = self._report_condition(condition, context, module_path, fallthrough_state)
                if condition_value is False:
                    fallthrough_state = self._assume(condition, False, fallthrough_state, context, module_path)
                    continue
                true_state = self._assume(condition, True, fallthrough_state, context, module_path)
                branch_values.append(self._evaluate_expression(branch_expr, context, module_path, true_state))
                if condition_value is True:
                    return branch_values[-1]
                fallthrough_state = self._assume(condition, False, fallthrough_state, context, module_path)
            if else_expr is not None:
                branch_values.append(self._evaluate_expression(else_expr, context, module_path, fallthrough_state))
            return self._coalesce_values(branch_values)

        expr_tuple = _expr_tuple(expr)
        if expr_tuple is not None and expr_tuple:
            operator = expr_tuple[0]

            if operator in (const.KEY_TERNARY, "Ternary"):
                _, branches, else_expr = cast(TernaryTuple, expr_tuple)
                branch_values = []
                fallthrough_state = state
                for condition, branch_expr in branches or []:
                    condition_value = self._report_condition(condition, context, module_path, fallthrough_state)
                    if condition_value is False:
                        fallthrough_state = self._assume(condition, False, fallthrough_state, context, module_path)
                        continue
                    true_state = self._assume(condition, True, fallthrough_state, context, module_path)
                    branch_values.append(self._evaluate_expression(branch_expr, context, module_path, true_state))
                    if condition_value is True:
                        return branch_values[-1]
                    fallthrough_state = self._assume(condition, False, fallthrough_state, context, module_path)
                if else_expr is not None:
                    branch_values.append(self._evaluate_expression(else_expr, context, module_path, fallthrough_state))
                return self._coalesce_values(branch_values)

            if operator == const.KEY_FUNCTION_CALL:
                _, _, args = cast(FunctionCallTuple, expr_tuple)
                for argument in args or []:
                    self._evaluate_expression(argument, context, module_path, state)
                return UNKNOWN

            if operator in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND):
                _, parts = cast(LogicalTuple, expr_tuple)
                values = [self._evaluate_expression(item, context, module_path, state) for item in parts or []]
                if operator == const.GRAMMAR_VALUE_OR:
                    if any(value is True for value in values):
                        return True
                    if all(value is False for value in values):
                        return False
                else:
                    if any(value is False for value in values):
                        return False
                    if values and all(value is True for value in values):
                        return True
                return UNKNOWN

            if operator == const.GRAMMAR_VALUE_NOT:
                value = self._evaluate_expression(
                    expr_tuple[1] if len(expr_tuple) > 1 else None, context, module_path, state
                )
                return (not value) if isinstance(value, bool) else UNKNOWN

            if operator in (const.KEY_COMPARE, "compare"):
                _, left, pairs = cast(CompareTuple, expr_tuple)
                left_value = self._evaluate_expression(left, context, module_path, state)
                if not is_scalar_value(left_value):
                    return UNKNOWN
                scalar_left = left_value
                results: list[bool] = []
                for symbol, right_expr in pairs or []:
                    right_value = self._evaluate_expression(right_expr, context, module_path, state)
                    if not is_scalar_value(right_value):
                        return UNKNOWN
                    scalar_right = right_value
                    comparison = self._compare_values(scalar_left, symbol, scalar_right)
                    if comparison is None:
                        return UNKNOWN
                    results.append(comparison)
                return all(results)

            if operator in (const.KEY_ADD, const.KEY_MUL):
                _, left, parts = cast(BinaryOpTuple, expr_tuple)
                value = self._evaluate_expression(left, context, module_path, state)
                if not is_scalar_value(value):
                    return UNKNOWN
                scalar_value = value
                for symbol, right_expr in parts or []:
                    right_value = self._evaluate_expression(right_expr, context, module_path, state)
                    if not is_scalar_value(right_value):
                        return UNKNOWN
                    scalar_right = right_value
                    value = self._apply_arithmetic(symbol, scalar_value, scalar_right)
                    if not is_scalar_value(value):
                        return UNKNOWN
                    scalar_value = value
                return scalar_value

            if operator in (const.KEY_PLUS, const.KEY_MINUS):
                inner = self._evaluate_expression(
                    expr_tuple[1] if len(expr_tuple) > 1 else None, context, module_path, state
                )
                if not isinstance(inner, int | float) or isinstance(inner, bool):
                    return UNKNOWN
                return inner if operator == const.KEY_PLUS else -inner

        return UNKNOWN

    def _assume(
        self: Any,
        condition: object,
        truth: bool,
        state: StateMap,
        context: ScopeContext,
        module_path: list[str],
    ) -> StateMap:
        next_state = state.copy()

        statement_children = _statement_children(condition)
        if statement_children is not None:
            if statement_children:
                return self._assume(statement_children[0], truth, next_state, context, module_path)
            return next_state

        if is_var_ref(condition):
            resolved = self._resolve_ref(condition, context)
            if resolved is not None:
                next_state[resolved.key] = truth
            return next_state

        if isinstance(condition, dict):
            if const.KEY_VAR_NAME not in condition:
                return next_state
            resolved = self._resolve_ref(condition, context)
            if resolved is not None:
                next_state[resolved.key] = truth
            return next_state

        if is_not_op(condition):
            return self._assume(not_op_operand(condition), not truth, next_state, context, module_path)

        if is_bool_op(condition):
            operator = bool_op_operator(condition)
            if operator == "AND" and truth:
                for part in bool_op_operands(condition):
                    next_state = self._assume(part, True, next_state, context, module_path)
                return next_state
            if operator == "OR" and not truth:
                for part in bool_op_operands(condition):
                    next_state = self._assume(part, False, next_state, context, module_path)
                return next_state

        if is_compare(condition):
            pairs = compare_parts(condition)
            left_expr = compare_left(condition)
            if pairs is not None and len(pairs) == 1 and left_expr is not None:
                assumed = self._assume_compare(left_expr, pairs[0], truth, next_state, context, module_path)
                if assumed is not None:
                    return assumed

        condition_tuple = _expr_tuple(condition)
        if condition_tuple is not None and condition_tuple:
            operator = condition_tuple[0]
            if operator == const.GRAMMAR_VALUE_NOT:
                return self._assume(
                    condition_tuple[1] if len(condition_tuple) > 1 else None,
                    not truth,
                    next_state,
                    context,
                    module_path,
                )
            if operator == const.GRAMMAR_VALUE_AND and truth:
                for part in _expr_items(condition_tuple[1] if len(condition_tuple) > 1 else None):
                    next_state = self._assume(part, True, next_state, context, module_path)
                return next_state
            if operator == const.GRAMMAR_VALUE_OR and not truth:
                for part in _expr_items(condition_tuple[1] if len(condition_tuple) > 1 else None):
                    next_state = self._assume(part, False, next_state, context, module_path)
                return next_state
            if operator in (const.KEY_COMPARE, "compare"):
                compare_left_expr = condition_tuple[1] if len(condition_tuple) > 1 else None
                compare_pairs = _expr_items(condition_tuple[2] if len(condition_tuple) > 2 else None)
                for pair in compare_pairs:
                    if isinstance(pair, tuple) and len(cast(tuple[object, ...], pair)) == 2:
                        assumed = self._assume_compare(
                            compare_left_expr,
                            cast(tuple[str, object], pair),
                            truth,
                            next_state,
                            context,
                            module_path,
                        )
                        if assumed is not None:
                            next_state = assumed
                return next_state

        return next_state

    def _assume_compare(
        self: Any,
        left_expr: Any,
        pair: tuple[str, object],
        truth: bool,
        state: StateMap,
        context: ScopeContext,
        module_path: list[str],
    ) -> StateMap | None:
        operator, right_expr = pair

        resolved_left = self._resolve_ref(left_expr, context)
        resolved_right = self._resolve_ref(right_expr, context)
        left_value = self._evaluate_expression(left_expr, context, module_path, state)
        right_value = self._evaluate_expression(right_expr, context, module_path, state)

        if (
            resolved_left is not None
            and right_value is not UNKNOWN
            and ((truth and operator == "==") or (not truth and operator == "<>"))
        ):
            next_state = self._invalidate_symbol(state.copy(), resolved_left.key)
            next_state[resolved_left.key] = right_value
            return next_state

        if (
            resolved_right is not None
            and left_value is not UNKNOWN
            and ((truth and operator == "==") or (not truth and operator == "<>"))
        ):
            next_state = self._invalidate_symbol(state.copy(), resolved_right.key)
            next_state[resolved_right.key] = left_value
            return next_state

        return None

    def _coalesce_values(
        self: Any,
        values: list[ScalarValue | object],
    ) -> ScalarValue | object:
        known = [value for value in values if value is not UNKNOWN]
        if not known:
            return UNKNOWN
        first = known[0]
        if all(value == first for value in known[1:]) and len(known) == len(values):
            return first
        return UNKNOWN


DataflowConditionMixin = _DataflowConditionMixin
