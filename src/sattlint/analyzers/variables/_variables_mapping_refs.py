"""Helpers for extracting variable references from parameter mappings."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Protocol, cast

from sattlint.parser_api import ParameterMapping, Variable, VarRef

type AliasLink = tuple[Variable, Variable, str]


class _ParameterMappingPayloads(Protocol):
    source: object
    target: object


def var_ref_text(value: object) -> str | None:
    if isinstance(value, VarRef):
        return value.name or None
    if isinstance(value, str):
        return value
    return None


def mapping_source_ref(pm: ParameterMapping) -> str | None:
    typed_pm = cast(_ParameterMappingPayloads, pm)
    return var_ref_text(typed_pm.source)


def mapping_target_ref(pm: ParameterMapping) -> str | None:
    typed_pm = cast(_ParameterMappingPayloads, pm)
    return var_ref_text(typed_pm.target)


def ordered_alias_links(links: Sequence[AliasLink]) -> Iterator[AliasLink]:
    """Yield alias links deepest first, so one pass reaches every ancestor.

    A link copies usage from its second variable (the mapped parameter) to its
    first (the mapping source). A link whose source is itself a mapped
    parameter must run after the links that fill that parameter; otherwise the
    outermost variable sees only the usage a shallower hop produced. Links that
    would revisit a variable in the same chain are skipped, which keeps
    recursive mappings finite.
    """

    indexed = list(enumerate(links))
    by_parent: dict[int, list[tuple[int, AliasLink]]] = {}
    for index, link in indexed:
        by_parent.setdefault(id(link[0]), []).append((index, link))

    applied: set[int] = set()
    settled: set[int] = set()
    visiting: set[int] = set()

    def _settle(variable: Variable) -> Iterator[AliasLink]:
        variable_id = id(variable)
        if variable_id in visiting or variable_id in settled:
            return
        visiting.add(variable_id)
        try:
            for index, link in by_parent.get(variable_id, ()):
                if index in applied:
                    continue
                yield from _settle(link[1])
                if index in applied:
                    continue
                applied.add(index)
                yield link
        finally:
            visiting.discard(variable_id)
        settled.add(variable_id)

    for _index, link in indexed:
        yield from _settle(link[0])


__all__ = [
    "AliasLink",
    "mapping_source_ref",
    "mapping_target_ref",
    "ordered_alias_links",
    "var_ref_text",
]
