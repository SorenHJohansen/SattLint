"""Compact prefix index for datatype leaf fields.

The datatype-field passes repeatedly ask "which leaf fields does this accessed
field path cover?". A sorted leaf-key list with binary search answers that in
``O(log L + matches)`` and stores only the leaf strings, instead of comparing
every accessed path against every leaf or materialising a trie.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterable
from dataclasses import dataclass, field


def normalize_field_path(field_path: str) -> str:
    """Drop empty segments so ``A..B`` and ``A.B`` compare the same."""
    return ".".join(segment for segment in field_path.split(".") if segment)


def _empty_mask_cache() -> dict[str, int]:
    return {}


@dataclass(frozen=True, slots=True)
class LeafPathIndex:
    """Leaf paths of one datatype, sortable and mask-addressable.

    A leaf's bit position is stable for the lifetime of the index, so callers
    can aggregate usage in an ``int`` bitmask instead of per-instance sets.
    """

    leaf_keys: tuple[str, ...]
    leaf_paths: tuple[str, ...]
    all_mask: int
    _mask_cache: dict[str, int] = field(default_factory=_empty_mask_cache)

    @classmethod
    def empty(cls) -> LeafPathIndex:
        return cls((), (), 0, {})

    @classmethod
    def from_paths(cls, paths: Iterable[str]) -> LeafPathIndex:
        by_key: dict[str, str] = {}
        for path in paths:
            if path:
                by_key.setdefault(path.casefold(), path)

        ordered = sorted(by_key.items())
        leaf_keys = tuple(key for key, _ in ordered)
        leaf_paths = tuple(path for _, path in ordered)
        return cls(leaf_keys, leaf_paths, (1 << len(leaf_keys)) - 1, {})

    def match(self, field_paths: Iterable[str]) -> tuple[int, bool]:
        """Return the leaf mask for *field_paths*, plus whether one was empty."""
        mask = 0
        has_whole = False
        for raw_path in field_paths:
            normalized = normalize_field_path(raw_path)
            if not normalized:
                has_whole = True
                continue
            mask |= self.mask_for_key(normalized.casefold())
        return mask, has_whole

    def mask_for_prefixes(self, prefixes: Iterable[str]) -> int:
        mask = 0
        for prefix in prefixes:
            normalized = normalize_field_path(prefix)
            if normalized:
                mask |= self.mask_for_key(normalized.casefold())
        return mask

    def mask_for_key(self, key: str) -> int:
        """Return the mask of leaves equal to *key* or nested below it."""
        cached = self._mask_cache.get(key)
        if cached is not None:
            return cached

        start = bisect_left(self.leaf_keys, key)
        prefix = f"{key}."
        mask = 0
        position = start
        while position < len(self.leaf_keys):
            leaf_key = self.leaf_keys[position]
            if leaf_key != key and not leaf_key.startswith(prefix):
                break
            mask |= 1 << position
            position += 1

        self._mask_cache[key] = mask
        return mask
