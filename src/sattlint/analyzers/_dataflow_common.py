from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeGuard

ScalarValue = bool | int | float | str
StateMap = dict[tuple[str, ...], ScalarValue | object]
type CompareConditionPayload = tuple[str, ScalarValue]
type BoolConditionFact = tuple[Literal["bool"], tuple[str, ...], bool]
type CompareConditionFact = tuple[Literal["compare"], tuple[str, ...], CompareConditionPayload]
type ConditionFact = BoolConditionFact | CompareConditionFact

UNKNOWN = object()
INITIALIZED = object()
PENDING_PREFIX = ("__pending__",)
OLD_PREFIX = ("__old__",)


def is_scalar_value(value: ScalarValue | object) -> TypeGuard[ScalarValue]:
    return isinstance(value, bool | int | float | str)


def _is_scalar_value(value: ScalarValue | object) -> TypeGuard[ScalarValue]:
    return is_scalar_value(value)


def invert_compare_operator(operator: str) -> str:
    return {
        "<": ">",
        ">": "<",
        "<=": ">=",
        ">=": "<=",
    }.get(operator, operator)


@dataclass(frozen=True)
class ResolvedRef:
    key: tuple[str, ...]
    root_key: tuple[str, ...]
    symbol_key: tuple[str, ...]
    symbol_root_key: tuple[str, ...]
    display_name: str
    base_display_name: str
    state_access: str | None
    is_state_variable: bool


@dataclass(frozen=True)
class PendingWrite:
    key: tuple[str, ...]
    root_key: tuple[str, ...]
    display_name: str
    sites: tuple[str, ...]
