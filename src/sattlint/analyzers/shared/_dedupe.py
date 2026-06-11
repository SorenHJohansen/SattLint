"""Small shared helpers for analyzer deduplication patterns."""

from __future__ import annotations


def remember_once[KeyT](seen: set[KeyT], key: KeyT) -> bool:
    if key in seen:
        return False
    seen.add(key)
    return True


def get_or_register_index[KeyT](indexes: dict[KeyT, int], key: KeyT, next_index: int) -> int | None:
    existing_index = indexes.get(key)
    if existing_index is None:
        indexes[key] = next_index
    return existing_index


__all__ = ["get_or_register_index", "remember_once"]
