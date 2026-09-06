from __future__ import annotations

from pathlib import Path

_REPO_MARKERS = ("pyproject.toml", "AGENTS.md")


def repo_root_from(anchor: Path | str) -> Path:
    current = Path(anchor).resolve()
    if current.is_file():
        current = current.parent

    while True:
        if all((current / marker).exists() for marker in _REPO_MARKERS):
            return current
        if current.parent == current:
            raise RuntimeError(f"Could not locate repository root from {anchor!s}")
        current = current.parent


def repo_root_from_optional(anchor: Path | str) -> Path | None:
    """Like ``repo_root_from`` but returns *None* instead of raising."""
    try:
        return repo_root_from(anchor)
    except RuntimeError:
        return None
