from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


def _cf(s: str) -> str:
    return s.casefold()


@dataclass(frozen=True, slots=True)
class CanonicalPath:
    """A fully-qualified, addressable symbol path.

    Semantics:
    - Equality / hashing for lookups should be done via `key()` (case-insensitive).
    - `segments` preserves original spelling for display/debug.

    Canonical paths are rooted at the module-instance path, then the root variable,
    then any nested field segments.
    """

    segments: tuple[str, ...]

    def key(self) -> tuple[str, ...]:
        return tuple(_cf(s) for s in self.segments)

    def join(self, *more: str) -> "CanonicalPath":
        if not more:
            return self
        return CanonicalPath(self.segments + tuple(more))

    def __str__(self) -> str:
        return ".".join(self.segments)


ModuleKind = Literal["BP", "SM", "FM", "MT", "TD"]


@dataclass(frozen=True, slots=True)
class ModuleSegment:
    name: str
    kind: ModuleKind
    moduletype_name: str | None = None

    def display(self) -> str:
        if self.kind == "MT" and self.moduletype_name:
            return f"{self.name}<MT:{self.moduletype_name}>"
        if self.kind == "SM":
            return f"{self.name}<SM>"
        if self.kind == "FM":
            return f"{self.name}<FM>"
        if self.kind == "TD":
            return f"{self.name}<TD>"
        if self.kind == "BP":
            return f"{self.name}<BP>"
        return self.name


def decorate_segment(name: str, kind: ModuleKind, moduletype_name: str | None = None) -> str:
    if kind == "MT" and moduletype_name:
        return f"{name}<MT:{moduletype_name}>"
    if kind in ("SM", "FM", "TD", "BP"):
        return f"{name}<{kind}>"
    return name
