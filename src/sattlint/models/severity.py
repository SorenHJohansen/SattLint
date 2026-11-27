"""Shared finding severity type."""

from __future__ import annotations

from typing import Literal

type Severity = Literal["error", "warning", "info"]

SEVERITIES: frozenset[str] = frozenset({"error", "warning", "info"})

__all__ = [
    "SEVERITIES",
    "Severity",
]
