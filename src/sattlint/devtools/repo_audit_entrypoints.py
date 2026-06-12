"""Compatibility wrapper for the moved repo-audit entrypoints."""

from __future__ import annotations

from typing import Any

from .audit import repo_audit_entrypoints as _owner


def __getattr__(name: str) -> Any:
    return getattr(_owner, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_owner)))
