"""Shared metadata for dynamic ArrayObject builtin procedures."""

from __future__ import annotations

from dataclasses import dataclass

from ...resolution import AccessKind


@dataclass(frozen=True, slots=True)
class ArrayBuiltinSpec:
    array_index: int
    element_index: int
    status_index: int | None
    array_accesses: tuple[AccessKind, ...]
    element_access: AccessKind
    effect_source: str
    dataflow_mutates_array: bool = False


_ARRAY_BUILTIN_SPECS: dict[str, ArrayBuiltinSpec] = {
    "createarray": ArrayBuiltinSpec(
        array_index=0,
        element_index=3,
        status_index=4,
        array_accesses=(AccessKind.WRITE,),
        element_access=AccessKind.READ,
        effect_source="element",
    ),
    "getarray": ArrayBuiltinSpec(
        array_index=0,
        element_index=2,
        status_index=3,
        array_accesses=(AccessKind.READ,),
        element_access=AccessKind.WRITE,
        effect_source="array",
    ),
    "putarray": ArrayBuiltinSpec(
        array_index=0,
        element_index=2,
        status_index=3,
        array_accesses=(AccessKind.READ, AccessKind.WRITE),
        element_access=AccessKind.READ,
        effect_source="element",
        dataflow_mutates_array=True,
    ),
}


def get_dynamic_array_builtin_spec(fn_name: str | None) -> ArrayBuiltinSpec | None:
    if not fn_name:
        return None
    return _ARRAY_BUILTIN_SPECS.get(fn_name.casefold())


__all__ = ["ArrayBuiltinSpec", "get_dynamic_array_builtin_spec"]
