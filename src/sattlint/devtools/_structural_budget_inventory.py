from __future__ import annotations

import shutil
import subprocess  # nosec
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def count_structural_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if (stripped := line.strip()) and not stripped.startswith("#"))


def iter_structural_python_files(repo_root: Path) -> Iterator[tuple[str, Path]]:
    for path in sorted((repo_root / "src").rglob("*.py")):
        if path.is_file():
            yield "src", path
    for path in sorted((repo_root / "scripts").rglob("*.py")):
        if path.is_file():
            yield "src", path
    for path in sorted((repo_root / "tests").rglob("test_*.py")):
        if path.is_file():
            yield "tests", path


def _tracked_markdown_paths(repo_root: Path) -> tuple[str, ...]:
    git_executable = shutil.which("git")
    if git_executable is None:
        return ()
    try:
        # Fixed local git command for tracked-markdown discovery.
        completed = subprocess.run(  # nosec
            [git_executable, "ls-files", "*.md"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return ()
    if completed.returncode != 0:
        return ()
    return tuple(path.strip().replace("\\", "/") for path in completed.stdout.splitlines() if path.strip())


def iter_structural_markdown_files(repo_root: Path) -> Iterator[tuple[str, Path]]:
    tracked_paths = _tracked_markdown_paths(repo_root)
    if tracked_paths:
        for rel_path in tracked_paths:
            path = repo_root / rel_path
            if path.is_file():
                yield "markdown", path
        return

    for path in sorted(repo_root.rglob("*.md")):
        if path.is_file() and ".git" not in path.parts:
            yield "markdown", path


def read_structural_text(path: Path) -> tuple[str | None, int | None, dict[str, Any] | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        try:
            return None, len(path.read_bytes().splitlines()), {"error": str(exc), "error_type": type(exc).__name__}
        except OSError as read_exc:
            return None, None, {"error": str(read_exc), "error_type": type(read_exc).__name__}
    except OSError as exc:
        return None, None, {"error": str(exc), "error_type": type(exc).__name__}
    line_count = len(text.splitlines()) if path.suffix.casefold() == ".md" else count_structural_lines(text)
    return text, line_count, None


def summarize_structural_budget_metrics(report: dict[str, Any]) -> dict[str, int]:
    summary = report["summary"]
    return {
        "source_file_over_budget_count": len(report["source_files_over_budget"]),
        "source_file_max_lines": summary["source_file_max_lines"],
        "test_file_over_budget_count": len(report["test_files_over_budget"]),
        "test_file_max_lines": summary["test_file_max_lines"],
        "function_over_budget_count": len(report["functions_over_budget"]),
        "function_max_lines": max((item["line_span"] for item in report["functions_over_budget"]), default=0),
        "class_over_budget_count": len(report["classes_over_budget"]),
        "class_max_methods": max((item["method_count"] for item in report["classes_over_budget"]), default=0),
        "repeated_private_name_count": len(report["repeated_private_names"]),
        "repeated_private_name_max_files": max(
            (item["file_count"] for item in report["repeated_private_names"]), default=0
        ),
        "import_max_count": summary["import_max_count"],
        "dependency_max_count": summary["dependency_max_count"],
        "public_symbol_max_count": summary["public_symbol_max_count"],
        "nesting_max_depth": summary["nesting_max_depth"],
        "facade_private_entrypoint_count": len(report["facade_private_entrypoints"]),
    }
