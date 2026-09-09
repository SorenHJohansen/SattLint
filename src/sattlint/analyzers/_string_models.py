"""Shared result, state, and slot models for exact string inference.

These pure data containers are used by both `string_inference.py` (the solving
engine) and `_string_operations.py` (cursor-aware builtin semantics) so the
value model can be reasoned about independently of either.
"""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    SingleModule,
    Variable,
)

if TYPE_CHECKING:
    from ..resolution.scope import ScopeContext


_MAX_STRING_CANDIDATES = 24
_MAX_CURSOR_POSITIONS = 24
_MAX_FIXED_POINT_PASSES = 8
_MAX_OVERFLOW_EXAMPLES = 8
_MAX_CONTEXT_BUILD_DEPTH = 64


def _noop_progress(_msg: str) -> None:
    pass


_STRING_LIMITS: dict[Simple_DataType, int] = {
    Simple_DataType.IDENTSTRING: 15,
    Simple_DataType.TAGSTRING: 30,
    Simple_DataType.STRING: 40,
    Simple_DataType.LINESTRING: 80,
    Simple_DataType.MAXSTRING: 140,
}


def _string_capacity_for_datatype(datatype: Simple_DataType | str | None) -> int | None:
    if isinstance(datatype, Simple_DataType):
        return _STRING_LIMITS.get(datatype)
    return None


@dataclass(frozen=True, slots=True)
class StringProvenanceSegment:
    text: str
    source_kind: str
    source_label: str | None = None
    source_module_path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StringCandidate:
    text: str
    segments: tuple[StringProvenanceSegment, ...] = ()


@dataclass(frozen=True, slots=True)
class StringInferenceResult:
    candidates: tuple[StringCandidate, ...] = ()
    cursor_positions: tuple[int, ...] = ()
    max_length: int | None = None
    unknown_text: bool = False
    unknown_cursor: bool = False
    unknown_max_length: bool = False
    overflow_operations: tuple[str, ...] = ()
    overflow_examples: tuple[str, ...] = ()

    @property
    def texts(self) -> tuple[str, ...]:
        return tuple(candidate.text for candidate in self.candidates)

    @property
    def overflowed(self) -> bool:
        return bool(self.overflow_operations or self.overflow_examples)


@dataclass(frozen=True, slots=True)
class _SlotKey:
    module_path: tuple[str, ...]
    variable_name: str
    field_path: str = ""


@dataclass(frozen=True, slots=True)
class _ResolvedSlot:
    key: _SlotKey
    display_name: str
    decl_module_path: tuple[str, ...]
    variable: Variable


@dataclass(frozen=True, slots=True)
class _IntResult:
    values: tuple[int, ...] = ()
    unknown: bool = False


def _string_values_factory() -> dict[_SlotKey, StringInferenceResult]:
    return {}


def _int_values_factory() -> dict[_SlotKey, _IntResult]:
    return {}


@dataclass(slots=True)
class _AbstractState:
    string_values: dict[_SlotKey, StringInferenceResult] = field(default_factory=_string_values_factory)
    int_values: dict[_SlotKey, _IntResult] = field(default_factory=_int_values_factory)

    def clone(self) -> _AbstractState:
        return _AbstractState(string_values=self.string_values.copy(), int_values=self.int_values.copy())


@dataclass(frozen=True, slots=True)
class _LiteralBinding:
    target_ref: str
    source_literal: object
    source_kind: str


@dataclass(slots=True)
class _ModuleContext:
    path: tuple[str, ...]
    scope: ScopeContext
    node: BasePicture | SingleModule | FrameModule | ModuleTypeDef | ModuleTypeInstance
    literal_bindings: tuple[_LiteralBinding, ...]
    children: tuple[_ModuleContext, ...] = ()
