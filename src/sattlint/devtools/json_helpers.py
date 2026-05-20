from __future__ import annotations

from typing import Any, cast


def json_mapping(value: object) -> dict[str, Any] | None:
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def string_entries(value: object, *, include_tuples: bool = False) -> list[str]:
    allowed_types: type[list[Any]] | tuple[type[list[Any]], type[tuple[Any, ...]]] = (
        (list, tuple) if include_tuples else list
    )
    if not isinstance(value, allowed_types):
        return []
    return [str(entry) for entry in cast(list[object] | tuple[object, ...], value)]


def nonempty_string_entries(
    value: object,
    *,
    include_tuples: bool = False,
    strip: bool = False,
) -> list[str]:
    entries: list[str] = []
    for entry in string_entries(value, include_tuples=include_tuples):
        normalized = entry.strip() if strip else entry
        if normalized.strip():
            entries.append(normalized)
    return entries
