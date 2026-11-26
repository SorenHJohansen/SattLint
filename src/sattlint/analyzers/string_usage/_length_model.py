"""Value and state model for the length-only string analysis."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .._string_models import StringSlotKey

_MAX_VALUES = 8


@dataclass(frozen=True, slots=True)
class LengthValue:
    lengths: tuple[int, ...] = ()
    cursors: tuple[int, ...] = ()
    unknown: bool = True
    written: bool = False

    @property
    def known(self) -> bool:
        return not self.unknown and bool(self.lengths) and bool(self.cursors)

    @property
    def max_length(self) -> int | None:
        return max(self.lengths) if self.known else None


@dataclass(frozen=True, slots=True)
class IntValue:
    values: tuple[int, ...] = ()
    unknown: bool = True

    @property
    def known(self) -> bool:
        return not self.unknown and bool(self.values)


def unknown_length(*, written: bool = False) -> LengthValue:
    return LengthValue(written=written)


def normalize_length(
    lengths: Iterable[int],
    cursors: Iterable[int],
    *,
    unknown: bool = False,
    written: bool = True,
) -> LengthValue:
    unique_lengths = sorted({value for value in lengths if value >= 0})
    unique_cursors = sorted({value for value in cursors if value >= 1})
    overflowed = len(unique_lengths) > _MAX_VALUES or len(unique_cursors) > _MAX_VALUES
    if not unique_lengths or not unique_cursors:
        return LengthValue(unknown=True, written=written)
    return LengthValue(
        lengths=tuple(unique_lengths[:_MAX_VALUES]),
        cursors=tuple(unique_cursors[:_MAX_VALUES]),
        unknown=unknown or overflowed,
        written=written,
    )


def normalize_int(values: Iterable[int], *, unknown: bool = False) -> IntValue:
    unique = sorted(set(values))
    overflowed = len(unique) > _MAX_VALUES
    if not unique:
        return IntValue(unknown=True)
    return IntValue(values=tuple(unique[:_MAX_VALUES]), unknown=unknown or overflowed)


def join_length(left: LengthValue, right: LengthValue) -> LengthValue:
    return normalize_length(
        (*left.lengths, *right.lengths),
        (*left.cursors, *right.cursors),
        unknown=left.unknown or right.unknown,
        written=left.written or right.written,
    )


def join_int(left: IntValue, right: IntValue) -> IntValue:
    return normalize_int((*left.values, *right.values), unknown=left.unknown or right.unknown)


def _length_values_factory() -> dict[StringSlotKey, LengthValue]:
    return {}


def _int_values_factory() -> dict[StringSlotKey, IntValue]:
    return {}


@dataclass(slots=True)
class LengthState:
    strings: dict[StringSlotKey, LengthValue] = field(default_factory=_length_values_factory)
    ints: dict[StringSlotKey, IntValue] = field(default_factory=_int_values_factory)

    def clone(self) -> LengthState:
        return LengthState(strings=self.strings.copy(), ints=self.ints.copy())


@dataclass(frozen=True, slots=True)
class OverflowFact:
    module_path: tuple[str, ...]
    site: str
    operation: str
    target: str
    capacity: int
    length: int
    source: str | None = None


@dataclass(frozen=True, slots=True)
class LengthAnalysisResult:
    state: LengthState
    overflow_facts: tuple[OverflowFact, ...]
    incomplete: bool = False


__all__ = [
    "IntValue",
    "LengthAnalysisResult",
    "LengthState",
    "LengthValue",
    "OverflowFact",
    "join_int",
    "join_length",
    "normalize_int",
    "normalize_length",
    "unknown_length",
]
