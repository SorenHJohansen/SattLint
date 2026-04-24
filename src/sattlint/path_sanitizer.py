"""Helpers for removing workstation-specific paths from generated reports."""

from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath

_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_OPTION_PATH_PREFIXES = (
    "--junitxml=",
    "--output-dir=",
    "--trace-target=",
    "--output=",
)


def _is_windows_absolute(raw_path: str) -> bool:
    return bool(_WINDOWS_ABSOLUTE_RE.match(raw_path))


def _looks_absolute(raw_path: str) -> bool:
    if not raw_path:
        return False
    return raw_path.startswith("/") or _is_windows_absolute(raw_path)


def _display_name(raw_path: str) -> str:
    if _is_windows_absolute(raw_path):
        return PureWindowsPath(raw_path).name
    return Path(raw_path).name


def sanitize_path_for_report(
    path: Path | str | None,
    *,
    repo_root: Path,
    external_prefix: str = "<external>",
) -> str | None:
    if path is None:
        return None

    raw_path = str(path)
    if not raw_path:
        return raw_path

    try:
        resolved_repo_root = repo_root.resolve()
    except OSError:
        resolved_repo_root = repo_root

    candidate = Path(raw_path)
    try:
        resolved_candidate = candidate.resolve(strict=False)
    except OSError:
        resolved_candidate = candidate

    try:
        return resolved_candidate.relative_to(resolved_repo_root).as_posix()
    except ValueError:
        pass

    if _looks_absolute(raw_path):
        name = _display_name(raw_path)
        return external_prefix if not name else f"{external_prefix}/{name}"

    return Path(raw_path).as_posix()


def sanitize_command_for_report(command: list[str], *, repo_root: Path) -> list[str]:
    sanitized: list[str] = []
    for arg in command:
        updated = arg
        for prefix in _OPTION_PATH_PREFIXES:
            if arg.startswith(prefix):
                suffix = arg[len(prefix) :]
                sanitized_suffix = sanitize_path_for_report(suffix, repo_root=repo_root)
                updated = prefix + (sanitized_suffix or "")
                break
        else:
            if _looks_absolute(arg):
                updated = sanitize_path_for_report(arg, repo_root=repo_root) or arg
        sanitized.append(updated)
    return sanitized
