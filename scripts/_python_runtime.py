from __future__ import annotations

import sys
from pathlib import Path


def resolve_repo_python(repo_root: Path) -> Path:
    """Return the repo virtualenv interpreter when present, else the active host Python."""

    windows_python = repo_root / ".venv" / "Scripts" / "python.exe"
    if windows_python.exists():
        return windows_python

    posix_python = repo_root / ".venv" / "bin" / "python"
    if posix_python.exists():
        return posix_python

    return Path(sys.executable)
