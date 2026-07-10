from __future__ import annotations

from typing import Any, cast

from ...grammar import constants as const
from ...resolution.scope import ScopeContext
from ._dataflow_common import ConditionFact, ScalarValue
from ._dataflow_condition_expr import CompareTuple, _expr_tuple


class _DataflowConditionFactsMixin:
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
        condition: object,
        context: ScopeContext,
    ) -> bool | None:
        condition_tuple = _expr_tuple(condition)
        if condition_tuple is None or not condition_tuple or condition_tuple[0] not in (const.KEY_COMPARE, "compare"):
            return None
        _, left, pairs = cast(CompareTuple, condition_tuple)
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
