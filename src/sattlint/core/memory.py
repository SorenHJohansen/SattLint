"""Helpers for returning freed heap to the operating system."""

from __future__ import annotations

import ctypes
import gc
import sys
from typing import Any

_trim_function: Any | None = None
_trim_resolved = False


def _malloc_trim_fn() -> Any | None:
    """Resolve ``malloc_trim`` once; it does not exist outside glibc systems."""
    global _trim_function, _trim_resolved
    if _trim_resolved:
        return _trim_function
    _trim_resolved = True
    if not sys.platform.startswith("linux"):
        return None
    try:
        libc = ctypes.CDLL("libc.so.6")
        trim = libc.malloc_trim
    except (OSError, AttributeError):
        return None
    trim.argtypes = [ctypes.c_size_t]
    trim.restype = ctypes.c_int
    _trim_function = trim
    return trim


def release_unused_memory() -> None:
    """Collect cycles and ask the C allocator to return free heap.

    A run holds a parsed project graph and analyzer indexes. Dropping the
    references frees the objects, but CPython's allocator can keep the arenas
    resident; calling this at target boundaries keeps the process close to its
    live set instead of its peak. Platforms without ``malloc_trim`` only pay
    for the collection.
    """
    gc.collect()
    trim = _malloc_trim_fn()
    if trim is not None:
        trim(0)


__all__ = ["release_unused_memory"]
