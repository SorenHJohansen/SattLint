"""Sandbox devtools package."""

from __future__ import annotations

from typing import Any

from . import fuzzer


def __getattr__(name: str) -> Any:
    return getattr(fuzzer, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(fuzzer)))
