from __future__ import annotations

from typing import Any, cast

from sattline_parser.models.ast_model import FloatLiteral, IntLiteral

from ..grammar import constants as const
from ..resolution.scope import ScopeContext
from ._dataflow_common import (
    UNKNOWN,
    ConditionFact,
    ResolvedRef,
    ScalarValue,
    StateMap,
    invert_compare_operator,
    is_scalar_value,
)

type ExprNode = Any
type ComparePair = tuple[str, ExprNode]
type CompareTuple = tuple[str, ExprNode, list[ComparePair] | None]
type TernaryBranch = tuple[ExprNode, ExprNode]
type TernaryTuple = tuple[str, list[TernaryBranch] | None, ExprNode | None]
type FunctionCallTuple = tuple[str, str | None, list[ExprNode] | None]
type LogicalTuple = tuple[str, list[ExprNode] | None]
type BinaryOpPart = tuple[str, ExprNode]
type BinaryOpTuple = tuple[str, ExprNode, list[BinaryOpPart] | None]


class _DataflowConditionMixin:
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
        condition: Any,
        context: ScopeContext,
    ) -> bool | None:
        if not (isinstance(condition, tuple) and condition):
            return None

        operator = condition[0]
        if operator == const.GRAMMAR_VALUE_NOT:
            truth = self._logical_shortcut_truth(condition[1], context)
            return None if truth is None else not truth

        if operator in (const.GRAMMAR_VALUE_AND, const.GRAMMAR_VALUE_OR):
            facts = [
                fact
                for fact in (self._condition_fact(part, context) for part in (condition[1] or []))
                if fact is not None
            ]
            if operator == const.GRAMMAR_VALUE_AND:
                return self._facts_contradict(facts)
            return self._facts_form_tautology(facts)

        return None

    def _condition_fact(
        self: Any,
        expr: Any,
        context: ScopeContext,
    ) -> ConditionFact | None:
        if isinstance(expr, dict) and const.KEY_VAR_NAME in expr:
            resolved = self._resolve_ref(expr, context)
            if resolved is None:
                return None
            return ("bool", resolved.key, True)

        if isinstance(expr, tuple) and expr:
            operator = expr[0]
            if operator == const.GRAMMAR_VALUE_NOT:
                inner = self._condition_fact(expr[1], context)
                return self._negate_condition_fact(inner)

            if operator in (const.KEY_COMPARE, "compare"):
                _, left_expr, pairs = cast(CompareTuple, expr)
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

    def _facts_contradict(self: Any, facts: list[ConditionFact]) -> bool | None:
        if not facts:
            return None

        bool_truths: dict[tuple[str, ...], set[bool]] = {}
        equals: dict[tuple[str, ...], set[ScalarValue]] = {}
        not_equals: dict[tuple[str, ...], set[ScalarValue]] = {}

        for fact in facts:
            kind = fact[0]
            key = fact[1]
            if kind == "bool":
                bool_truths.setdefault(key, set()).add(cast(bool, fact[2]))
                continue

            operator, literal = cast(tuple[str, ScalarValue], fact[2])
            if operator == "==":
                equals.setdefault(key, set()).add(literal)
            elif operator == "<>":
                not_equals.setdefault(key, set()).add(literal)

        if any(len(values) > 1 for values in bool_truths.values()):
            return False

        for key, equal_values in equals.items():
            if len(equal_values) > 1:
                return False
            if any(value in not_equals.get(key, set()) for value in equal_values):
                return False

        return None

    def _facts_form_tautology(self: Any, facts: list[ConditionFact]) -> bool | None:
        if not facts:
            return None

        bool_truths: dict[tuple[str, ...], set[bool]] = {}
        equals: dict[tuple[str, ...], set[ScalarValue]] = {}
        not_equals: dict[tuple[str, ...], set[ScalarValue]] = {}

        for fact in facts:
            kind = fact[0]
            key = fact[1]
            if kind == "bool":
                bool_truths.setdefault(key, set()).add(cast(bool, fact[2]))
                continue

            operator, literal = cast(tuple[str, ScalarValue], fact[2])
            if operator == "==":
                equals.setdefault(key, set()).add(literal)
            elif operator == "<>":
                not_equals.setdefault(key, set()).add(literal)

        if any(len(values) > 1 for values in bool_truths.values()):
            return True

        for key, equal_values in equals.items():
            if any(value in not_equals.get(key, set()) for value in equal_values):
                return True

        return None

    def _self_compare_truth(
        self: Any,
        condition: Any,
        context: ScopeContext,
    ) -> bool | None:
        if not (isinstance(condition, tuple) and condition and condition[0] in (const.KEY_COMPARE, "compare")):
            return None
        _, left, pairs = cast(CompareTuple, condition)
        if pairs is None or len(pairs) != 1:
            return None
        operator, right = pairs[0]
        left_ref = self._resolve_ref(left, context)
        right_ref = self._resolve_ref(right, context)
        if left_ref is None or right_ref is None or left_ref.key != right_ref.key:
            return None
        if operator in ("==", "<=", ">="):
            return True
        if operator in ("<>", "<", ">"):
            return False
        return None

    def _evaluate_expression(
        self: Any,
        expr: Any,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> ScalarValue | object:
        if hasattr(expr, "data") and expr.data == const.KEY_STATEMENT:
            children = getattr(expr, "children", [])
            if children:
                return self._evaluate_expression(children[0], context, module_path, state)
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

        if isinstance(expr, dict) and const.KEY_VAR_NAME in expr:
            resolved = self._resolve_ref(expr, context)
            if resolved is None:
                return UNKNOWN
            return self._read_resolved_value(resolved, module_path, state)

        if isinstance(expr, tuple) and expr:
            operator = expr[0]

            if operator in (const.KEY_TERNARY, "Ternary"):
                _, branches, else_expr = cast(TernaryTuple, expr)
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

            if operator == const.KEY_FUNCTION_CALL:
                _, _, args = cast(FunctionCallTuple, expr)
                for argument in args or []:
                    self._evaluate_expression(argument, context, module_path, state)
                return UNKNOWN

            if operator in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND):
                _, parts = cast(LogicalTuple, expr)
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
                value = self._evaluate_expression(expr[1], context, module_path, state)
                return (not value) if isinstance(value, bool) else UNKNOWN

            if operator in (const.KEY_COMPARE, "compare"):
                _, left, pairs = cast(CompareTuple, expr)
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
                _, left, parts = cast(BinaryOpTuple, expr)
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
                inner = self._evaluate_expression(expr[1], context, module_path, state)
                if not isinstance(inner, int | float) or isinstance(inner, bool):
                    return UNKNOWN
                return inner if operator == const.KEY_PLUS else -inner

        return UNKNOWN

    def _assume(
        self: Any,
        condition: Any,
        truth: bool,
        state: StateMap,
        context: ScopeContext,
        module_path: list[str],
    ) -> StateMap:
        next_state = state.copy()

        if hasattr(condition, "data") and condition.data == const.KEY_STATEMENT:
            children = getattr(condition, "children", [])
            if children:
                return self._assume(children[0], truth, next_state, context, module_path)
            return next_state

        if isinstance(condition, dict) and const.KEY_VAR_NAME in condition:
            resolved = self._resolve_ref(condition, context)
            if resolved is not None:
                next_state[resolved.key] = truth
            return next_state

        if isinstance(condition, tuple) and condition:
            operator = condition[0]
            if operator == const.GRAMMAR_VALUE_NOT:
                return self._assume(condition[1], not truth, next_state, context, module_path)
            if operator == const.GRAMMAR_VALUE_AND and truth:
                for part in condition[1] or []:
                    next_state = self._assume(part, True, next_state, context, module_path)
                return next_state
            if operator == const.GRAMMAR_VALUE_OR and not truth:
                for part in condition[1] or []:
                    next_state = self._assume(part, False, next_state, context, module_path)
                return next_state
            if operator in (const.KEY_COMPARE, "compare"):
                assumed = self._assume_compare(condition, truth, next_state, context, module_path)
                if assumed is not None:
                    return assumed

        return next_state

    def _assume_compare(
        self: Any,
        condition: tuple[Any, ...],
        truth: bool,
        state: StateMap,
        context: ScopeContext,
        module_path: list[str],
    ) -> StateMap | None:
        _, left_expr, pairs = cast(CompareTuple, condition)
        if pairs is None or len(pairs) != 1:
            return None
        operator, right_expr = pairs[0]

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
