"""SFC guard normalization and transition logic analysis."""

from __future__ import annotations

from collections.abc import Sequence as SequenceABC
from typing import Any

from sattline_parser.models.ast_model import (
    BasePicture,
    Sequence,
    SFCAlternative,
    SFCParallel,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
)
from sattline_parser.utils.formatter import format_expr

from ..grammar import constants as const
from ..resolution.paths import CanonicalPath
from ._sfc_module_walk import iter_sfc_modulecodes
from .framework import Issue


def _paths_conflict(a: CanonicalPath, b: CanonicalPath) -> bool:
    a_key = a.key()
    b_key = b.key()
    if len(a_key) <= len(b_key):
        return b_key[: len(a_key)] == a_key
    return a_key[: len(b_key)] == b_key


def _conflict_rep(a: CanonicalPath, b: CanonicalPath) -> CanonicalPath:
    if len(a.segments) <= len(b.segments):
        return a
    return b


def _expr_text(expr: Any) -> str:
    return " ".join(format_expr(expr).split())


def _signature_sort_key(signature: object) -> str:
    return repr(signature)


def _invert_compare_operator(operator: str) -> str:
    return {
        "<": ">",
        ">": "<",
        "<=": ">=",
        ">=": "<=",
    }.get(operator, operator)


def _signature_literal_value(signature: object) -> bool | int | float | str | None:
    if not isinstance(signature, tuple) or len(signature) != 2:
        return None
    tag, value = signature
    if tag in {"bool", "int", "float", "str"}:
        return value
    return None


def _compare_literal_values(
    left: bool | int | float | str,
    operator: str,
    right: bool | int | float | str,
) -> bool | None:
    try:
        if operator == "==":
            return left == right
        if operator == "<>":
            return left != right
        if operator == "<":
            return left < right  # type: ignore[operator]
        if operator == ">":
            return left > right  # type: ignore[operator]
        if operator == "<=":
            return left <= right  # type: ignore[operator]
        if operator == ">=":
            return left >= right  # type: ignore[operator]
    except TypeError:
        return None
    return None


def _complement_signature(signature: object) -> object:
    if signature == ("bool", True):
        return ("bool", False)
    if signature == ("bool", False):
        return ("bool", True)
    if isinstance(signature, tuple) and signature:
        tag = signature[0]
        if tag == "not" and len(signature) == 2:
            return signature[1]
        if tag == "compare" and len(signature) == 4:
            _tag, operator, left, right = signature
            if operator == "==":
                return ("compare", "<>", left, right)
            if operator == "<>":
                return ("compare", "==", left, right)
            if operator == "<":
                return ("compare", ">=", left, right)
            if operator == ">":
                return ("compare", "<=", left, right)
            if operator == "<=":
                return ("compare", ">", left, right)
            if operator == ">=":
                return ("compare", "<", left, right)
    return ("not", signature)


def _normalize_logical_guard(kind: str, parts: list[object]) -> object:
    flattened: list[object] = []
    for part in parts:
        if isinstance(part, tuple) and len(part) == 2 and part[0] == kind:
            flattened.extend(part[1])
        else:
            flattened.append(part)

    if kind == "and":
        if any(part == ("bool", False) for part in flattened):
            return ("bool", False)
        flattened = [part for part in flattened if part != ("bool", True)]
    else:
        if any(part == ("bool", True) for part in flattened):
            return ("bool", True)
        flattened = [part for part in flattened if part != ("bool", False)]

    normalized: list[object] = []
    seen: set[str] = set()
    for part in flattened:
        complement = _complement_signature(part)
        if repr(complement) in seen:
            return ("bool", False) if kind == "and" else ("bool", True)
        part_key = repr(part)
        if part_key in seen:
            continue
        seen.add(part_key)
        normalized.append(part)

    if not normalized:
        return ("bool", True) if kind == "and" else ("bool", False)
    if len(normalized) == 1:
        return normalized[0]

    normalized.sort(key=_signature_sort_key)
    return (kind, tuple(normalized))


def _normalize_compare_guard(left: Any, operator: str, right: Any) -> object:
    left_signature = _normalize_guard_signature(left)
    right_signature = _normalize_guard_signature(right)

    left_literal = _signature_literal_value(left_signature)
    right_literal = _signature_literal_value(right_signature)
    if left_literal is not None and right_literal is not None:
        folded = _compare_literal_values(left_literal, operator, right_literal)
        if folded is not None:
            return ("bool", folded)

    if left_signature == right_signature:
        if operator in {"==", "<=", ">="}:
            return ("bool", True)
        if operator in {"<>", "<", ">"}:
            return ("bool", False)

    normalized_operator = operator
    if operator in {"==", "<>"}:
        ordered = sorted([left_signature, right_signature], key=_signature_sort_key)
        left_signature, right_signature = ordered
    elif _signature_sort_key(left_signature) > _signature_sort_key(right_signature):
        left_signature, right_signature = right_signature, left_signature
        normalized_operator = _invert_compare_operator(operator)

    return ("compare", normalized_operator, left_signature, right_signature)


def _normalize_guard_signature(expr: Any) -> object:
    if hasattr(expr, "data") and expr.data == const.KEY_STATEMENT:
        children = getattr(expr, "children", [])
        if children:
            return _normalize_guard_signature(children[0])
        return ("text", "")

    if isinstance(expr, bool):
        return ("bool", expr)
    if isinstance(expr, int) and not isinstance(expr, bool):
        return ("int", int(expr))
    if isinstance(expr, float):
        return ("float", float(expr))
    if isinstance(expr, str):
        return ("str", expr)

    if isinstance(expr, dict) and const.KEY_VAR_NAME in expr:
        full_name = expr[const.KEY_VAR_NAME]
        state_access = expr.get("state")
        if isinstance(full_name, str) and full_name:
            if isinstance(state_access, str) and state_access:
                return ("var", full_name.casefold(), state_access.casefold())
            return ("var", full_name.casefold())
        return ("text", _expr_text(expr).casefold())

    if isinstance(expr, tuple) and expr:
        operator = expr[0]

        if operator == const.GRAMMAR_VALUE_NOT:
            return _complement_signature(_normalize_guard_signature(expr[1]))

        if operator in (const.GRAMMAR_VALUE_AND, const.GRAMMAR_VALUE_OR):
            logical_kind = "and" if operator == const.GRAMMAR_VALUE_AND else "or"
            return _normalize_logical_guard(
                logical_kind,
                [_normalize_guard_signature(part) for part in expr[1] or []],
            )

        if operator in (const.KEY_COMPARE, "compare"):
            _compare, left, pairs = expr
            comparisons = [_normalize_compare_guard(left, symbol, right) for symbol, right in pairs or []]
            if not comparisons:
                return _normalize_guard_signature(left)
            if len(comparisons) == 1:
                return comparisons[0]
            return _normalize_logical_guard("and", comparisons)

    return ("text", _expr_text(expr).casefold())


def _guard_constant_truth(signature: object) -> bool | None:
    if isinstance(signature, tuple) and len(signature) == 2 and signature[0] == "bool":
        return bool(signature[1])
    return None


def _collect_transition_logic_issues(base_picture: BasePicture) -> list[Issue]:
    issues: list[Issue] = []

    def inspect_nodes(
        nodes: SequenceABC[object] | None,
        module_path: list[str],
        sequence_name: str,
        branch_path: tuple[int, ...] = (),
    ) -> None:
        duplicate_groups: dict[str, list[dict[str, Any]]] = {}

        for index, node in enumerate(nodes or []):
            if isinstance(node, SFCTransition):
                condition_text = _expr_text(node.condition)
                signature = _normalize_guard_signature(node.condition)
                constant_truth = _guard_constant_truth(signature)
                transition_name = node.name or f"<unnamed:{index + 1}>"
                data = {
                    "sequence": sequence_name,
                    "branch_path": list(branch_path),
                    "transition_name": transition_name,
                    "condition": condition_text,
                    "normalized_guard": repr(signature),
                }
                if constant_truth is True:
                    issues.append(
                        Issue(
                            kind="sfc_transition_always_true",
                            message=(
                                f"Transition {transition_name!r} in sequence {sequence_name!r}{_format_branch_path(branch_path)} "
                                f"has a guard that is always true: {condition_text}."
                            ),
                            module_path=module_path.copy(),
                            data=data,
                        )
                    )
                elif constant_truth is False:
                    issues.append(
                        Issue(
                            kind="sfc_transition_always_false",
                            message=(
                                f"Transition {transition_name!r} in sequence {sequence_name!r}{_format_branch_path(branch_path)} "
                                f"has a guard that is always false: {condition_text}."
                            ),
                            module_path=module_path.copy(),
                            data=data,
                        )
                    )

                duplicate_groups.setdefault(repr(signature), []).append(
                    {
                        "name": transition_name,
                        "condition": condition_text,
                        "normalized_guard": repr(signature),
                    }
                )
                continue

            if isinstance(node, SFCAlternative | SFCParallel):
                for branch_index, branch in enumerate(node.branches or []):
                    inspect_nodes(
                        branch,
                        module_path,
                        sequence_name,
                        (*branch_path, branch_index),
                    )
                continue

            if isinstance(node, SFCSubsequence | SFCTransitionSub):
                inspect_nodes(node.body, module_path, sequence_name, branch_path)

        for duplicates in duplicate_groups.values():
            if len(duplicates) < 2:
                continue
            transition_names = [item["name"] for item in duplicates]
            issues.append(
                Issue(
                    kind="sfc_duplicate_transition_guard",
                    message=(
                        f"Sequence {sequence_name!r}{_format_branch_path(branch_path)} contains transitions with equivalent guards: "
                        f"{', '.join(repr(name) for name in transition_names)}."
                    ),
                    module_path=module_path.copy(),
                    data={
                        "sequence": sequence_name,
                        "branch_path": list(branch_path),
                        "transition_names": transition_names,
                        "conditions": [item["condition"] for item in duplicates],
                        "normalized_guard": duplicates[0]["normalized_guard"],
                    },
                )
            )

    for module_path, modulecode in iter_sfc_modulecodes(base_picture):
        if modulecode is None:
            continue
        for sequence in modulecode.sequences or []:
            if isinstance(sequence, Sequence):
                inspect_nodes(sequence.code, module_path, sequence.name)

    return issues


def _format_branch_path(branch_path: tuple[int, ...]) -> str:
    if not branch_path:
        return ""
    return " branch " + ".".join(str(index + 1) for index in branch_path)
