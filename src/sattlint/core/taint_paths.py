from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass

from ..resolution.access_graph import AccessEvent
from .safety_paths import SymbolAccess, build_symbol_accesses

DEFAULT_TAINT_SOURCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "mes": ("mes", "mms", "opc", "batch"),
    "operator": ("operator", "manual", "command", "cmd", "setpoint"),
    "sensor": ("sensor", "measurement", "measured", "feedback", "probe", "transmitter"),
}

DEFAULT_CRITICAL_SINK_KEYWORDS: tuple[str, ...] = (
    "emergency",
    "shutdown",
    "estop",
    "interlock",
    "trip",
)

_NON_ALNUM_RE = re.compile(r"[^0-9a-z]+")


def _normalize_token(value: str) -> str:
    return _NON_ALNUM_RE.sub("", value.casefold())


def _normalized_keyword_sets(
    source_keywords: dict[str, tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    return {
        category: tuple(_normalize_token(keyword) for keyword in keywords if keyword)
        for category, keywords in source_keywords.items()
    }


def classify_taint_source_path(
    canonical_path: str,
    *,
    source_keywords: dict[str, tuple[str, ...]] = DEFAULT_TAINT_SOURCE_KEYWORDS,
) -> str | None:
    normalized_categories = _normalized_keyword_sets(source_keywords)
    for segment in canonical_path.split("."):
        normalized_segment = _normalize_token(segment)
        if not normalized_segment:
            continue
        for category, keywords in normalized_categories.items():
            if any(keyword and keyword in normalized_segment for keyword in keywords):
                return category
    return None


def is_critical_sink_path(
    canonical_path: str,
    *,
    keywords: tuple[str, ...] = DEFAULT_CRITICAL_SINK_KEYWORDS,
) -> bool:
    normalized_keywords = tuple(_normalize_token(keyword) for keyword in keywords if keyword)
    for segment in canonical_path.split("."):
        normalized_segment = _normalize_token(segment)
        if not normalized_segment:
            continue
        if any(keyword and keyword in normalized_segment for keyword in normalized_keywords):
            return True
    return False


@dataclass(frozen=True, slots=True)
class TaintPathTrace:
    source_canonical_path: str
    source_kind: str
    sink_canonical_path: str
    sink_kind: str
    path: tuple[str, ...]
    source_accesses: tuple[SymbolAccess, ...]
    sink_accesses: tuple[SymbolAccess, ...]
    module_paths: tuple[tuple[str, ...], ...]
    spans_multiple_modules: bool


def _display_canonical_path(
    key: tuple[str, ...],
    accesses_by_key: dict[tuple[str, ...], tuple[AccessEvent, ...]],
    display_names_by_key: dict[tuple[str, ...], str] | None = None,
) -> str:
    if display_names_by_key and key in display_names_by_key:
        return display_names_by_key[key]
    events = accesses_by_key.get(key, ())
    if events:
        return str(events[0].canonical_path)
    return ".".join(key)


def _path_matches_query(path: tuple[str, ...], query: str) -> bool:
    needle = query.strip().casefold()
    if not needle:
        return True
    return any(needle in node.casefold() for node in path)


def _is_runtime_canonical_path(canonical_path: str) -> bool:
    return not any(segment.casefold().startswith("typedef:") for segment in canonical_path.split("."))


def build_taint_path_traces(
    effect_flow_edges: dict[tuple[str, ...], tuple[tuple[str, ...], ...]] | dict[tuple[str, ...], set[tuple[str, ...]]],
    accesses_by_key: dict[tuple[str, ...], tuple[AccessEvent, ...]],
    *,
    query: str = "",
    limit: int | None = None,
    source_keywords: dict[str, tuple[str, ...]] = DEFAULT_TAINT_SOURCE_KEYWORDS,
    critical_sink_keywords: tuple[str, ...] = DEFAULT_CRITICAL_SINK_KEYWORDS,
    display_names_by_key: dict[tuple[str, ...], str] | None = None,
) -> list[TaintPathTrace]:
    normalized_edges: dict[tuple[str, ...], tuple[tuple[str, ...], ...]] = {
        source_key: tuple(target_keys)
        for source_key, target_keys in effect_flow_edges.items()
    }
    incoming_keys = {
        target_key
        for target_keys in normalized_edges.values()
        for target_key in target_keys
    }

    all_keys: set[tuple[str, ...]] = set(accesses_by_key)
    for source_key, target_keys in normalized_edges.items():
        all_keys.add(source_key)
        all_keys.update(target_keys)

    display_names = {
        key: _display_canonical_path(key, accesses_by_key, display_names_by_key)
        for key in all_keys
    }
    runtime_keys = {
        key for key, canonical_path in display_names.items() if _is_runtime_canonical_path(canonical_path)
    }
    source_keys = [
        key
        for key in runtime_keys
        if key not in incoming_keys
        if classify_taint_source_path(display_names[key], source_keywords=source_keywords) is not None
    ]
    sink_keys = {
        key
        for key in runtime_keys
        if is_critical_sink_path(display_names[key], keywords=critical_sink_keywords)
    }

    traces: list[TaintPathTrace] = []
    seen_pairs: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()

    for source_key in sorted(source_keys, key=lambda item: display_names[item].casefold()):
        source_kind = classify_taint_source_path(display_names[source_key], source_keywords=source_keywords)
        if source_kind is None:
            continue

        pending: deque[tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]] = deque(
            [(source_key, (source_key,))]
        )
        visited: set[tuple[str, ...]] = {source_key}

        while pending:
            current_key, current_path = pending.popleft()
            for target_key in sorted(
                tuple(
                    target_key
                    for target_key in normalized_edges.get(current_key, ())
                    if target_key in runtime_keys
                ),
                key=lambda item: display_names.get(item, ".".join(item)).casefold(),
            ):
                if target_key in visited:
                    continue
                visited.add(target_key)
                next_path = current_path + (target_key,)

                if target_key in sink_keys and len(next_path) > 1:
                    pair = (source_key, target_key)
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        display_path = tuple(display_names[key] for key in next_path)
                        if _path_matches_query(display_path, query):
                            module_paths = tuple(
                                dict.fromkeys(
                                    access.use_module_path
                                    for key in next_path
                                    for access in build_symbol_accesses(accesses_by_key.get(key, ()))
                                )
                            )
                            traces.append(
                                TaintPathTrace(
                                    source_canonical_path=display_names[source_key],
                                    source_kind=source_kind,
                                    sink_canonical_path=display_names[target_key],
                                    sink_kind="critical",
                                    path=display_path,
                                    source_accesses=build_symbol_accesses(accesses_by_key.get(source_key, ())),
                                    sink_accesses=build_symbol_accesses(accesses_by_key.get(target_key, ())),
                                    module_paths=module_paths,
                                    spans_multiple_modules=len(module_paths) > 1,
                                )
                            )
                            if limit is not None and len(traces) >= limit:
                                return sorted(
                                    traces,
                                    key=lambda trace: (
                                        trace.source_canonical_path.casefold(),
                                        trace.sink_canonical_path.casefold(),
                                    ),
                                )[:limit]

                pending.append((target_key, next_path))

    traces.sort(
        key=lambda trace: (
            trace.source_canonical_path.casefold(),
            trace.sink_canonical_path.casefold(),
        )
    )
    if limit is not None:
        return traces[:limit]
    return traces


__all__ = [
    "DEFAULT_CRITICAL_SINK_KEYWORDS",
    "DEFAULT_TAINT_SOURCE_KEYWORDS",
    "TaintPathTrace",
    "build_taint_path_traces",
    "classify_taint_source_path",
    "is_critical_sink_path",
]
