from __future__ import annotations

from collections.abc import Iterable

ANYTYPE_NAME = "anytype"


def casefold_key(value: object) -> str:
    return str(value).casefold()


def casefold_equal(left: object, right: object) -> bool:
    return casefold_key(left) == casefold_key(right)


def dedupe_casefolded_strings(values: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        value = str(raw).strip()
        if not value:
            continue
        key = casefold_key(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def is_anytype_name(value: object) -> bool:
    return isinstance(value, str) and value.casefold() == ANYTYPE_NAME
