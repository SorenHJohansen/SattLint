from __future__ import annotations

from collections.abc import Iterable

from sattlint.parser_api import UnitIdentity

ANYTYPE_NAME = "anytype"
_ANYTYPE_KEY = UnitIdentity.of(ANYTYPE_NAME).key


def casefold_key(value: str) -> str:
    return value.casefold()


def casefold_equal(left: str, right: str) -> bool:
    return casefold_key(left) == casefold_key(right)


def unit_key(name: str) -> str:
    """The language identity key for a unit or module-type name.

    SattLine compares names with its CP1252 name table, not Unicode case
    folding: ``Library`` and ``library`` are one name, while ``Straße`` and
    ``STRASSE`` stay distinct. Use this for names the parser owns; keep
    :func:`casefold_key` for plain text normalization.
    """
    return UnitIdentity.of(name).key


def unit_equal(left: str, right: str) -> bool:
    return unit_key(left) == unit_key(right)


def dedupe_unit_names(values: Iterable[str]) -> list[str]:
    """Drop blank and repeated unit names, keeping the first spelling."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        value = raw.strip()
        if not value:
            continue
        key = unit_key(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def is_anytype_name(value: object) -> bool:
    return isinstance(value, str) and unit_key(value) == _ANYTYPE_KEY
