"""Repo file traversal and scan-context helpers for leak detection."""

from __future__ import annotations

import ast
import os
import shutil
from collections.abc import Callable, Iterable
from pathlib import Path
from subprocess import run as run_subprocess  # nosec B404 - fixed git argv is validated at the call site below
from typing import Any

TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".gitignore",
    ".ini",
    ".js",
    ".json",
    ".l",
    ".md",
    ".p",
    ".ps1",
    ".py",
    ".s",
    ".toml",
    ".txt",
    ".x",
    ".xml",
    ".yaml",
    ".yml",
    ".z",
}
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".nox",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
    "htmlcov",
}


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ValueError("binary")
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def should_skip_dir(dirname: str) -> bool:
    if dirname in SKIP_DIRS:
        return True
    return dirname.startswith(".venv")


def list_tracked_repo_paths(
    root: Path,
    *,
    git_which: Callable[[str], str | None] = shutil.which,
    run_command: Callable[..., Any] = run_subprocess,
) -> tuple[str, ...] | None:
    git_executable = git_which("git")
    if git_executable is None:
        return None
    try:
        completed = run_command([git_executable, "ls-files", "-z"], cwd=root, capture_output=True, check=False)
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return tuple(
        sorted(
            raw_rel_path.strip()
            for raw_rel_path in completed.stdout.decode("utf-8", errors="replace").split("\x00")
            if raw_rel_path.strip()
        )
    )


def iter_repo_file_candidates(
    root: Path,
    *,
    include_generated: bool,
    relative_path: Callable[[Path, Path], str],
    should_skip_dir_fn: Callable[[str], bool] = should_skip_dir,
    text_suffixes: set[str] = TEXT_SUFFIXES,
) -> Iterable[Path]:
    for current_root, dirs, files in os.walk(root, topdown=True):
        current_path = Path(current_root)
        rel_dir = relative_path(current_path, root)
        if rel_dir == ".":
            rel_dir = ""
        filtered_dirs: list[str] = []
        for dirname in dirs:
            if should_skip_dir_fn(dirname):
                if include_generated and dirname in {"artifacts", "build", "htmlcov"}:
                    filtered_dirs.append(dirname)
                    continue
                continue
            filtered_dirs.append(dirname)
        dirs[:] = filtered_dirs

        for filename in files:
            path = current_path / filename
            rel_path = relative_path(path, root)
            if not include_generated and rel_path.startswith("artifacts/"):
                continue
            if path.suffix.lower() not in text_suffixes and filename not in {"README", "LICENSE"}:
                continue
            if path.stat().st_size > 2_000_000:
                continue
            yield path


def iter_tracked_repo_file_candidates(
    root: Path,
    *,
    include_generated: bool,
    list_tracked_repo_paths_fn: Callable[[Path], tuple[str, ...] | None],
    should_skip_dir_fn: Callable[[str], bool] = should_skip_dir,
    text_suffixes: set[str] = TEXT_SUFFIXES,
) -> Iterable[Path]:
    tracked_paths = list_tracked_repo_paths_fn(root)
    if tracked_paths is None:
        yield from iter_repo_file_candidates(
            root,
            include_generated=include_generated,
            relative_path=lambda path, base: path.relative_to(base).as_posix(),
            should_skip_dir_fn=should_skip_dir_fn,
            text_suffixes=text_suffixes,
        )
        return
    for rel_path in tracked_paths:
        if not include_generated and rel_path.startswith("artifacts/"):
            continue
        path = root / Path(rel_path)
        if not path.exists() or path.is_dir():
            continue
        if any(
            should_skip_dir_fn(part) and not (include_generated and part in {"artifacts", "build", "htmlcov"})
            for part in path.parts
        ):
            continue
        if path.suffix.lower() not in text_suffixes and path.name not in {"README", "LICENSE"}:
            continue
        if path.stat().st_size > 2_000_000:
            continue
        yield path


def iter_repo_text_files(
    root: Path,
    *,
    include_generated: bool,
    iter_repo_file_candidates_fn: Callable[[Path, bool], Iterable[Path]],
    read_text_fn: Callable[[Path], str],
) -> Iterable[Path]:
    for path in iter_repo_file_candidates_fn(root, include_generated):
        try:
            read_text_fn(path)
        except ValueError:
            continue
        yield path


def iter_tracked_repo_text_files(
    root: Path,
    *,
    include_generated: bool,
    iter_tracked_repo_file_candidates_fn: Callable[[Path, bool], Iterable[Path]],
    read_text_fn: Callable[[Path], str],
) -> Iterable[Path]:
    for path in iter_tracked_repo_file_candidates_fn(root, include_generated):
        try:
            read_text_fn(path)
        except ValueError:
            continue
        yield path


def iter_repo_text_entries(
    root: Path,
    *,
    include_generated: bool,
    tracked_only: bool,
    iter_repo_file_candidates_fn: Callable[[Path, bool], Iterable[Path]],
    iter_tracked_repo_file_candidates_fn: Callable[[Path, bool], Iterable[Path]],
    read_text_fn: Callable[[Path], str],
) -> Iterable[tuple[Path, str]]:
    candidates = (
        iter_tracked_repo_file_candidates_fn(root, include_generated)
        if tracked_only
        else iter_repo_file_candidates_fn(root, include_generated)
    )
    for path in candidates:
        try:
            text = read_text_fn(path)
        except ValueError:
            continue
        yield path, text


def build_python_source_scan_context(
    source_root: Path,
    *,
    root: Path,
    tracked_paths: tuple[str, ...] | None,
    relative_path: Callable[[Path, Path], str],
    read_text_fn: Callable[[Path], str],
    context_factory: Callable[..., Any],
) -> Any:
    texts: dict[Path, str] = {}
    asts: dict[Path, ast.AST] = {}
    if tracked_paths is None:
        paths = sorted(source_root.rglob("*.py"))
    else:
        source_prefix = relative_path(source_root, root).rstrip("/")
        paths = [
            root / rel_path
            for rel_path in tracked_paths
            if rel_path.endswith(".py") and (rel_path == source_prefix or rel_path.startswith(f"{source_prefix}/"))
        ]
    for path in paths:
        if not path.exists():
            continue
        text = read_text_fn(path)
        texts[path] = text
        try:
            asts[path] = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
    return context_factory(source_root=source_root, texts=texts, asts=asts)


__all__ = [
    "build_python_source_scan_context",
    "iter_repo_file_candidates",
    "iter_repo_text_entries",
    "iter_repo_text_files",
    "iter_tracked_repo_file_candidates",
    "iter_tracked_repo_text_files",
    "list_tracked_repo_paths",
    "read_text",
    "should_skip_dir",
]
