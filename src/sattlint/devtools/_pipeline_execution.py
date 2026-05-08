"""Execution and interpreter resolution helpers for the analysis pipeline."""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(slots=True)
class CommandResult:
    name: str
    command: list[str]
    exit_code: int
    duration_seconds: float
    stdout: str
    stderr: str


def _resolve_python_executable() -> str:
    candidates: list[Path] = []

    venv_python = Path(".venv") / "Scripts" / "python.exe" if os.name == "nt" else Path(".venv") / "bin" / "python"
    if venv_python.exists():
        return str(venv_python.resolve())

    override = os.environ.get("SATTLINT_PYTHON")
    if override:
        candidates.append(Path(override))

    if sys.executable:
        candidates.append(Path(sys.executable))

    base_executable = getattr(sys, "_base_executable", "")
    if base_executable:
        candidates.append(Path(base_executable))

    prefix = Path(sys.prefix)
    if os.name == "nt":
        candidates.append(prefix / "Scripts" / "python.exe")
    else:
        candidates.append(prefix / "bin" / "python")

    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())

    fallback = shutil.which("python")
    if fallback:
        return fallback

    return sys.executable


def _resolve_venv_tool(tool_name: str) -> str | None:
    candidates: list[Path]
    if os.name == "nt":
        candidates = [Path(".venv") / "Scripts" / f"{tool_name}.exe"]
    else:
        candidates = [Path(".venv") / "bin" / tool_name]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())

    return shutil.which(tool_name)


def _run_command(name: str, command: list[str], *, cwd: Path = REPO_ROOT) -> CommandResult:
    start = time.perf_counter()
    completed = subprocess.run(  # nosec B603
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    duration = time.perf_counter() - start
    return CommandResult(
        name=name,
        command=command,
        exit_code=completed.returncode,
        duration_seconds=round(duration, 3),
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _detect_changed_files(*, repo_root: Path = REPO_ROOT) -> list[str]:
    try:
        git_executable = shutil.which("git")
        if git_executable is None:
            return []
        completed = subprocess.run(  # nosec B603
            [git_executable, "status", "--porcelain", "--untracked-files=all"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError:
        return []

    if completed.returncode != 0:
        return []

    changed_files: set[str] = set()
    for raw_line in completed.stdout.splitlines():
        if len(raw_line) < 4:
            continue
        path_text = raw_line[3:].strip()
        if not path_text:
            continue
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1].strip()
        changed_files.add(path_text.replace("\\", "/"))
    return sorted(changed_files)


__all__ = [
    "CommandResult",
    "_detect_changed_files",
    "_resolve_python_executable",
    "_resolve_venv_tool",
    "_run_command",
]
