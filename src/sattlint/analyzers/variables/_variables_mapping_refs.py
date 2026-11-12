"""Helpers for extracting variable references from parameter mappings."""

from __future__ import annotations

from typing import Protocol, cast

from sattlint.parser_api import ParameterMapping, VarRef


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
