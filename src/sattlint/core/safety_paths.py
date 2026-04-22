from __future__ import annotations

import re
from dataclasses import dataclass

from ..resolution.access_graph import AccessEvent

DEFAULT_SAFETY_SIGNAL_KEYWORDS: tuple[str, ...] = (
    "emergency",
    "shutdown",
    "estop",
)

_NON_ALNUM_RE = re.compile(r"[^0-9a-z]+")


def _normalize_token(value: str) -> str:
    return _NON_ALNUM_RE.sub("", value.casefold())


def is_safety_critical_path(
    canonical_path: str,
    *,
    keywords: tuple[str, ...] = DEFAULT_SAFETY_SIGNAL_KEYWORDS,
) -> bool:
    normalized_keywords = tuple(_normalize_token(keyword) for keyword in keywords)
    for segment in canonical_path.split("."):
        normalized_segment = _normalize_token(segment)
        if not normalized_segment:
            continue
        if any(keyword and keyword in normalized_segment for keyword in normalized_keywords):
            return True
    return False


@dataclass(frozen=True, slots=True)
class SymbolAccess:
    canonical_path: str
    kind: str
    use_module_path: tuple[str, ...]
    use_display_path: tuple[str, ...]
    syntactic_ref: str


@dataclass(frozen=True, slots=True)
class SafetyPathTrace:
    canonical_path: str
    accesses: tuple[SymbolAccess, ...]
    writer_count: int
    reader_count: int
    writer_module_paths: tuple[tuple[str, ...], ...]
    reader_module_paths: tuple[tuple[str, ...], ...]
    spans_multiple_modules: bool


def build_symbol_accesses(events: tuple[AccessEvent, ...] | list[AccessEvent]) -> tuple[SymbolAccess, ...]:
    ordered = sorted(
        events,
        key=lambda event: (
            tuple(part.casefold() for part in event.use_module_path),
            event.kind.value,
            event.syntactic_ref.casefold(),
        ),
    )
    return tuple(
        SymbolAccess(
            canonical_path=str(event.canonical_path),
            kind=event.kind.value,
            use_module_path=event.use_module_path,
            use_display_path=event.use_display_path,
            syntactic_ref=event.syntactic_ref,
        )
        for event in ordered
    )


def build_safety_path_traces(
    accesses_by_key: dict[tuple[str, ...], tuple[AccessEvent, ...]],
    *,
    query: str = "",
    limit: int | None = None,
    keywords: tuple[str, ...] = DEFAULT_SAFETY_SIGNAL_KEYWORDS,
) -> list[SafetyPathTrace]:
    needle = query.strip().casefold()
    traces: list[SafetyPathTrace] = []

    for events in accesses_by_key.values():
        if not events:
            continue

        canonical_path = str(events[0].canonical_path)
        if needle and needle not in canonical_path.casefold():
            continue
        if not is_safety_critical_path(canonical_path, keywords=keywords):
            continue

        accesses = build_symbol_accesses(events)
        writer_module_paths = tuple(
            dict.fromkeys(access.use_module_path for access in accesses if access.kind == "write")
        )
        reader_module_paths = tuple(
            dict.fromkeys(access.use_module_path for access in accesses if access.kind == "read")
        )
        module_paths = tuple(dict.fromkeys(access.use_module_path for access in accesses))

        traces.append(
            SafetyPathTrace(
                canonical_path=canonical_path,
                accesses=accesses,
                writer_count=sum(1 for access in accesses if access.kind == "write"),
                reader_count=sum(1 for access in accesses if access.kind == "read"),
                writer_module_paths=writer_module_paths,
                reader_module_paths=reader_module_paths,
                spans_multiple_modules=len(module_paths) > 1,
            )
        )

    traces.sort(key=lambda trace: trace.canonical_path.casefold())
    if limit is not None:
        return traces[:limit]
    return traces


__all__ = [
    "DEFAULT_SAFETY_SIGNAL_KEYWORDS",
    "SafetyPathTrace",
    "SymbolAccess",
    "build_safety_path_traces",
    "build_symbol_accesses",
    "is_safety_critical_path",
]
