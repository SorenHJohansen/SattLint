"""Shared issue model for analyzer findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def format_report_header(report_type: str, target: str, status: str | None = None) -> list[str]:
    lines = [f"Report: {report_type}", f"Target: {target}"]
    if status:
        lines.append(f"Status: {status}")
    return lines


@dataclass(frozen=True)
class Issue:
    kind: str
    message: str
    module_path: list[str] | None = None
    data: dict[str, Any] | None = None
    rule_id: str | None = None
    severity: str | None = None
    confidence: str | None = None
    explanation: str | None = None
    suggestion: str | None = None
