"""Shape of a SattLine module tree and the slot keys its references resolve to.

The exact string inference engine and the string checks share this module so a
solved value, a declared variable, and a call site all agree on the same module
path and slot identity.
"""

from __future__ import annotations

from dataclasses import dataclass

from sattlint.parser_api import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    Variable,
)

from ..resolution.common import varname_full
from ..resolution.scope import ScopeContext
from ._string_models import StringSlot, StringSlotKey


@dataclass(frozen=True, slots=True)
class LiteralBinding:
    """A parameter mapping whose source is a literal rather than a variable."""

    target_ref: str
    source_literal: object
    source_kind: str


@dataclass(slots=True)
class StringModuleContext:
    """One module scope plus the literal bindings its mappings introduce."""

    path: tuple[str, ...]
    scope: ScopeContext
    node: BasePicture | SingleModule | FrameModule | ModuleTypeDef | ModuleTypeInstance
    literal_bindings: tuple[LiteralBinding, ...]
    nested: tuple[StringModuleContext, ...] = ()


def module_code(
    node: BasePicture | SingleModule | FrameModule | ModuleTypeDef | ModuleTypeInstance,
) -> ModuleCode | None:
    if isinstance(node, BasePicture | SingleModule | FrameModule | ModuleTypeDef):
        return node.modulecode
    return None


def declared_variables(
    node: BasePicture | SingleModule | FrameModule | ModuleTypeDef | ModuleTypeInstance,
) -> tuple[Variable, ...]:
    if isinstance(node, BasePicture):
        return tuple(node.localvariables or ())
    if isinstance(node, SingleModule | FrameModule | ModuleTypeDef):
        return (*(node.moduleparameters or ()), *(node.localvariables or ()))
    return ()


def resolve_string_slot(scope: ScopeContext, ref_name: str) -> StringSlot | None:
    """Resolve a reference to the declaration slot that stores its value."""
    variable, field_path, decl_path, _decl_display = scope.resolve_variable(ref_name)
    if variable is None:
        return None
    slot_key = StringSlotKey(
        module_path=tuple(segment.casefold() for segment in decl_path),
        variable_name=variable.name.casefold(),
        field_path=field_path.casefold(),
    )
    display_name = variable.name if not field_path else f"{variable.name}.{field_path}"
    return StringSlot(key=slot_key, display_name=display_name, decl_module_path=tuple(decl_path), variable=variable)


def resolve_string_target(scope: ScopeContext, arg: object) -> StringSlot | None:
    """Resolve a call argument or assignment target to its declaration slot."""
    ref_name = varname_full(arg)
    if not ref_name:
        return None
    return resolve_string_slot(scope, ref_name)


__all__ = [
    "LiteralBinding",
    "StringModuleContext",
    "declared_variables",
    "module_code",
    "resolve_string_slot",
    "resolve_string_target",
]
