"""Canonical path and module-segment helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


def _cf(s: str) -> str:
    return s.casefold()


type CanonicalPathKey = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CanonicalPath:
    """A fully-qualified, addressable symbol path.

    Semantics:
    - `segments` preserves original spelling for display/debug.
    - `key()` returns the casefolded `CanonicalPathKey` used by resolution and snapshot indexes.
    - Indexes intentionally store `CanonicalPathKey` tuples rather than `CanonicalPath` objects.

    Canonical paths are rooted at the module-instance path, then the root variable,
    then any nested field segments.
    """

    segments: tuple[str, ...]

    def key(self) -> CanonicalPathKey:
        return tuple(_cf(s) for s in self.segments)

    def join(self, *more: str) -> CanonicalPath:
        if not more:
            return self
        return CanonicalPath(self.segments + tuple(more))

    def __str__(self) -> str:
        return ".".join(self.segments)


def path_startswith_casefold(location: list[str], prefix: list[str]) -> bool:
    if len(location) < len(prefix):
        return False
    return all(location[index].casefold() == segment.casefold() for index, segment in enumerate(prefix))


def is_external_to_module(location_path: list[str], module_path: list[str]) -> bool:
    if len(module_path) >= 2 and module_path[-1].startswith("TypeDef:"):
        typedef_segment = module_path[-1]
        return typedef_segment not in location_path
    return not path_startswith_casefold(location_path, module_path)


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
