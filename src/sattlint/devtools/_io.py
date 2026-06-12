"""Shared stderr progress and path display helpers for devtools commands."""

from __future__ import annotations

import sys
from pathlib import Path

from sattlint.path_sanitizer import sanitize_path_for_report


def emit_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def sanitize_repo_path(path: Path, *, workspace_root: Path) -> str:
    return sanitize_path_for_report(path, repo_root=workspace_root) or path.as_posix()


__all__ = ["emit_progress", "sanitize_repo_path"]
