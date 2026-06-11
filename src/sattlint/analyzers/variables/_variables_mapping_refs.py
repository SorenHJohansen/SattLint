"""Helpers for extracting variable references from parameter mappings."""

from __future__ import annotations

from typing import Protocol, cast

from sattline_parser.models.ast_model import ParameterMapping

from ...grammar import constants as const


class _ParameterMappingPayloads(Protocol):
    source: object
    target: object


def var_ref_text(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        value_dict = cast(dict[str, object], value)
        ref_text = value_dict.get(const.KEY_VAR_NAME)
        if isinstance(ref_text, str):
            return ref_text
    return None


def mapping_source_ref(pm: ParameterMapping) -> str | None:
    typed_pm = cast(_ParameterMappingPayloads, pm)
    return var_ref_text(typed_pm.source)


def mapping_target_ref(pm: ParameterMapping) -> str | None:
    typed_pm = cast(_ParameterMappingPayloads, pm)
    return var_ref_text(typed_pm.target)
