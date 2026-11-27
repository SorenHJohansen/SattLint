"""Shared datatype view and finding shape for the string checks."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sattlint.parser_api import ModuleTypeDef, ScalarDatatype, resolve_variable_field_datatype

from ...config.string_capacities import StringCapacities
from ...resolution import AmbiguousRecordError, TypeGraph
from .._string_models import StringSlot
from ..shared._string_capacity import capacity_for_datatype, is_string_datatype
from ..string_contexts import StringModuleContext


@dataclass(frozen=True, slots=True)
class SlotTypes:
    """Resolve a slot's leaf datatype through record fields."""

    capacities: StringCapacities
    type_graph: TypeGraph

    def datatype(self, slot: StringSlot) -> ScalarDatatype | str | None:
        field_path = slot.key.field_path
        if not field_path:
            return slot.variable.datatype
        try:
            return resolve_variable_field_datatype(slot.variable, tuple(field_path.split(".")), self.type_graph)
        except AmbiguousRecordError:
            return None

    def capacity(self, slot: StringSlot) -> int | None:
        return capacity_for_datatype(self.capacities, self.datatype(slot))

    def is_string(self, slot: StringSlot) -> bool:
        return is_string_datatype(self.datatype(slot))


@dataclass(frozen=True, slots=True)
class StringUsageFinding:
    kind: str
    message: str
    module_path: tuple[str, ...]
    site: str
    details: tuple[tuple[str, str | int | None], ...] = ()
    explanation: str | None = None
    suggestion: str | None = None


@dataclass(frozen=True, slots=True)
class OverflowFact:
    """A write whose length is known and exceeds the target's capacity."""

    module_path: tuple[str, ...]
    site: str
    operation: str
    target: str
    capacity: int
    length: int
    source: str | None = None


def statement_path(context: StringModuleContext) -> tuple[str, ...]:
    """The module path a statement in *context* is reported against.

    A module type's declarations are reported once at the declaration path, not
    once per instance, so instance contexts resolve to the same location.
    """
    path = display_path(context.path)
    if isinstance(context.node, ModuleTypeDef):
        return (*path[:1], context.node.name)
    return path


def display_path(path: tuple[str, ...]) -> tuple[str, ...]:
    """Drop the internal module type-root prefix from a user-facing path."""
    return tuple(segment.removeprefix("TypeDef:") for segment in path)


def dedupe_findings(findings: Iterable[StringUsageFinding]) -> list[StringUsageFinding]:
    unique: dict[tuple[object, ...], StringUsageFinding] = {}
    for finding in findings:
        key = (finding.kind, finding.module_path, finding.site, finding.message)
        unique.setdefault(key, finding)
    return sorted(unique.values(), key=lambda item: (item.module_path, item.site, item.kind, item.message))


__all__ = [
    "OverflowFact",
    "SlotTypes",
    "StringUsageFinding",
    "dedupe_findings",
    "display_path",
    "statement_path",
]
