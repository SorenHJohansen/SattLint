from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RATCHET_PATH = REPO_ROOT / "metrics" / "ratchet.json"


def _resolve_python(repo_root: Path) -> Path:
    windows_python = repo_root / ".venv" / "Scripts" / "python.exe"
    if windows_python.exists():
        return windows_python

    posix_python = repo_root / ".venv" / "bin" / "python"
    if posix_python.exists():
        return posix_python

    return Path(sys.executable)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _normalize_paths(path_texts: Sequence[str], repo_root: Path) -> list[str]:
    normalized_paths: list[str] = []
    seen: set[str] = set()
    for raw_path in path_texts:
        path_text = raw_path.strip()
        if not path_text:
            continue
        path = Path(path_text)
        if path.is_absolute():
            try:
                normalized = path.resolve().relative_to(repo_root.resolve()).as_posix()
            except ValueError:
                continue
        else:
            normalized = path.as_posix()
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_paths.append(normalized)
    return normalized_paths


def _git_lines(*args: str) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _collect_candidate_files(argv: Sequence[str]) -> list[str]:
    if argv:
        return _normalize_paths(argv, REPO_ROOT)

    changed_files = _git_lines("diff", "--name-only", "--diff-filter=ACMRTUXB", "HEAD")
    untracked_files = _git_lines("ls-files", "--others", "--exclude-standard")
    return _normalize_paths([*changed_files, *untracked_files], REPO_ROOT)


def _existing_python_files(rel_paths: Sequence[str]) -> list[str]:
    python_files: list[str] = []
    for rel_path in rel_paths:
        path = REPO_ROOT / rel_path
        if path.is_file() and path.suffix == ".py":
            python_files.append(rel_path)
    return python_files


def _flatten_required_paths(raw_groups: Any) -> set[str]:
    required_paths: set[str] = set()
    if not isinstance(raw_groups, dict):
        return required_paths
    for raw_paths in raw_groups.values():
        if not isinstance(raw_paths, list):
            continue
        for path_text in raw_paths:
            if isinstance(path_text, str) and path_text.strip():
                required_paths.add(path_text.replace("\\", "/").strip("/"))
    return required_paths


def _context_health_triggers() -> tuple[set[str], tuple[str, ...]]:
    ratchet = _read_json(RATCHET_PATH)
    explicit_paths = _flatten_required_paths(ratchet.get("required_paths", {}))

    context_files = ratchet.get("context_files", {})
    auto_loaded = context_files.get("auto_loaded", [])
    if isinstance(auto_loaded, list):
        for path_text in auto_loaded:
            if isinstance(path_text, str) and path_text.strip():
                explicit_paths.add(path_text.replace("\\", "/").strip("/"))

    scoped_globs = tuple(
        pattern for pattern in context_files.get("scoped_globs", []) if isinstance(pattern, str) and pattern.strip()
    )
    return explicit_paths, scoped_globs


def _should_run_context_health(rel_paths: Sequence[str]) -> bool:
    explicit_paths, scoped_globs = _context_health_triggers()
    for rel_path in rel_paths:
        normalized = rel_path.replace("\\", "/").strip("/")
        if normalized in explicit_paths:
            return True
        if any(fnmatch(normalized, pattern) for pattern in scoped_globs):
            return True
    return False


def _run_command(command: list[str], *, label: str) -> int:
    print(f"[ai-edit-gate] {label}", flush=True)
    completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
    return completed.returncode


def main(argv: Sequence[str] | None = None) -> int:
    candidate_files = _collect_candidate_files(list(argv) if argv is not None else sys.argv[1:])
    python_files = _existing_python_files(candidate_files)
    run_context_health = _should_run_context_health(candidate_files)
    python_executable = _resolve_python(REPO_ROOT)

    if not python_files and not run_context_health:
        print("[ai-edit-gate] no touched Python or AI-control files detected", flush=True)
        return 0

    if python_files:
        ruff_check_command = [
            str(python_executable),
            "-m",
            "ruff",
            "check",
            "--fix",
            "--select",
            "E,F,W,I",
            "--ignore",
            "E501",
            *python_files,
        ]
        check_exit_code = _run_command(ruff_check_command, label="ruff check --fix on touched Python files")
        if check_exit_code != 0:
            return check_exit_code

        ruff_format_command = [str(python_executable), "-m", "ruff", "format", *python_files]
        format_exit_code = _run_command(ruff_format_command, label="ruff format on touched Python files")
        if format_exit_code != 0:
            return format_exit_code

    if run_context_health:
        context_health_command = [str(python_executable), "scripts/context_health.py", "--check"]
        return _run_command(context_health_command, label="context health on touched AI-control files")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
