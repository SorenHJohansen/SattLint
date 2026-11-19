"""Typed timing payloads shared by analyzers, diagnostics, and run records.

The records keep a stable JSON shape: a phase timing is an object with
``phase`` and ``duration_ms``; named timings are an object of millisecond
values keyed by stage or graphics phase.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass

__all__ = ["NamedTimings", "PhaseTiming", "TimingBottleneck"]


@dataclass(frozen=True, slots=True)
class PhaseTiming:
    """One recorded analyzer phase and its duration in milliseconds."""

    phase: str
    duration_ms: float

    def to_dict(self) -> dict[str, object]:
        return {"phase": self.phase, "duration_ms": self.duration_ms}


@dataclass(frozen=True, slots=True, eq=False)
class NamedTimings(Mapping[str, float]):
    """Immutable millisecond timings keyed by stage or graphics phase name."""

    _entries: tuple[tuple[str, float], ...] = ()

    @classmethod
    def of(cls, values: Mapping[str, float]) -> NamedTimings:
        return cls(tuple(values.items()))

    def __getitem__(self, name: str) -> float:
        for entry_name, duration_ms in self._entries:
            if entry_name == name:
                return duration_ms
        raise KeyError(name)

    def __iter__(self) -> Iterator[str]:
        return (name for name, _duration_ms in self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def to_dict(self) -> dict[str, float]:
        return dict(self._entries)


@dataclass(frozen=True, slots=True)
class TimingBottleneck:
    """The slowest observed analyzer or analyzer phase."""

    kind: str
    name: str
    duration_ms: float
    analyzer_key: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "kind": self.kind,
            "name": self.name,
            "duration_ms": self.duration_ms,
        }
        if self.analyzer_key is not None:
            payload["analyzer_key"] = self.analyzer_key
        return payload
