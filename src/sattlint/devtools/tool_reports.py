"""Helpers for building machine-readable tool reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from sattlint.path_sanitizer import sanitize_command_for_report


class CommandResultLike(Protocol):
    name: str
    command: list[str]
    exit_code: int
    duration_seconds: float
    stdout: str
    stderr: str


def build_command_report(
    result: CommandResultLike,
    *,
    repo_root: Path,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "tool": result.name,
        "command": sanitize_command_for_report(result.command, repo_root=repo_root),
        "exit_code": result.exit_code,
        "duration_seconds": result.duration_seconds,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    payload.update(extra)
    return payload


__all__ = ["build_command_report"]
