"""AI devtools package."""

from __future__ import annotations

from typing import Any

from . import ai_gc, ai_work_map


def __getattr__(name: str) -> Any:
    return getattr(ai_work_map, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(ai_gc)) | set(dir(ai_work_map)))
