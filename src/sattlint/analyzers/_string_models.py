"""Shared result, state, and slot models for exact string inference.

These pure data containers are used by both `string_inference.py` (the solving
engine) and `_string_operations.py` (cursor-aware builtin semantics) so the
value model can be reasoned about independently of either.
"""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false

from __future__ import annotations

from dataclasses import dataclass, field

from sattlint.parser_api import Variable

_MAX_STRING_CANDIDATES = 24
_MAX_CURSOR_POSITIONS = 24
_MAX_FIXED_POINT_PASSES = 8
_MAX_OVERFLOW_EXAMPLES = 8
_MAX_CONTEXT_BUILD_DEPTH = 64


def _noop_progress(_msg: str) -> None:
    pass


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
class StringSlotKey:
    module_path: tuple[str, ...]
    variable_name: str
    field_path: str = ""


@dataclass(frozen=True, slots=True)
class StringSlot:
    key: StringSlotKey
    display_name: str
    decl_module_path: tuple[str, ...]
    variable: Variable


@dataclass(frozen=True, slots=True)
class _IntResult:
    values: tuple[int, ...] = ()
    unknown: bool = False


def _string_values_factory() -> dict[StringSlotKey, StringInferenceResult]:
    return {}


def _int_values_factory() -> dict[StringSlotKey, _IntResult]:
    return {}


@dataclass(slots=True)
class _AbstractState:
    string_values: dict[StringSlotKey, StringInferenceResult] = field(default_factory=_string_values_factory)
    int_values: dict[StringSlotKey, _IntResult] = field(default_factory=_int_values_factory)

    def clone(self) -> _AbstractState:
        return _AbstractState(string_values=self.string_values.copy(), int_values=self.int_values.copy())
