"""Compatibility wrapper for the moved repo-audit check catalog."""

from __future__ import annotations

from typing import Any

from .audit import _repo_audit_check_catalog as _owner


def __getattr__(name: str) -> Any:
    return getattr(_owner, name)


def __dir__() -> list[str]:
    return sorted(set(dir(_owner)))
