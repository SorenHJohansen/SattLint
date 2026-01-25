from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .paths import CanonicalPath


class AccessKind(Enum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True, slots=True)
class AccessEvent:
    kind: AccessKind
    canonical_path: CanonicalPath
    use_module_path: tuple[str, ...]
    use_display_path: tuple[str, ...]
    syntactic_ref: str


@dataclass
class AccessGraph:
    """Tracks resolved reads/writes to canonical fully-qualified paths."""

    events: list[AccessEvent] = field(default_factory=list)
    by_path_key: dict[tuple[str, ...], list[AccessEvent]] = field(default_factory=dict)

    def add(self, event: AccessEvent) -> None:
        self.events.append(event)
        self.by_path_key.setdefault(event.canonical_path.key(), []).append(event)
