from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeGuard

ScalarValue = bool | int | float | str
StateMap = dict[tuple[str, ...], ScalarValue | object]
ConditionFact = tuple[str, tuple[str, ...], Any]

_UNKNOWN = object()
_INITIALIZED = object()
_PENDING_PREFIX = ("__pending__",)
_OLD_PREFIX = ("__old__",)


def _is_scalar_value(value: ScalarValue | object) -> TypeGuard[ScalarValue]:
    return isinstance(value, bool | int | float | str)


def _invert_compare_operator(operator: str) -> str:
    return {
        "<": ">",
        ">": "<",
        "<=": ">=",
        ">=": "<=",
    }.get(operator, operator)


@dataclass(frozen=True)
class _ResolvedRef:
    key: tuple[str, ...]
    root_key: tuple[str, ...]
    symbol_key: tuple[str, ...]
    symbol_root_key: tuple[str, ...]
    display_name: str
    base_display_name: str
    state_access: str | None
    is_state_variable: bool


@dataclass(frozen=True)
class _PendingWrite:
    key: tuple[str, ...]
    root_key: tuple[str, ...]
    display_name: str
    sites: tuple[str, ...]


UNKNOWN = _UNKNOWN
INITIALIZED = _INITIALIZED
PENDING_PREFIX = _PENDING_PREFIX
OLD_PREFIX = _OLD_PREFIX
ResolvedRef = _ResolvedRef
PendingWrite = _PendingWrite
