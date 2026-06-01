"""Shared source normalization and unified diff helpers for devtools reports."""

from __future__ import annotations

import difflib
from pathlib import Path

from sattlint.path_sanitizer import sanitize_path_for_report


def _diff_render_label(path: Path, *, workspace_root: Path) -> str:
    return sanitize_path_for_report(path, repo_root=workspace_root) or path.as_posix()


def normalize_layout_text(source_text: str) -> str:
    normalized_newlines = source_text.replace("\r\n", "\n").replace("\r", "\n")
    normalized_lines: list[str] = []
    previous_blank = False
    for raw_line in normalized_newlines.split("\n"):
        line = raw_line.rstrip()
        is_blank = line == ""
        if is_blank and previous_blank:
            continue
        normalized_lines.append(line)
        previous_blank = is_blank

    while normalized_lines and normalized_lines[-1] == "":
        normalized_lines.pop()
    return "\n".join(normalized_lines) + "\n"


def build_unified_diff_lines(
    source_file: Path,
    *,
    workspace_root: Path,
    original: str,
    transformed: str,
    to_file: str | None = None,
) -> list[str]:
    from_label = _diff_render_label(source_file, workspace_root=workspace_root)
    to_label = from_label if to_file is None else to_file
    return list(
        difflib.unified_diff(
            original.splitlines(),
            transformed.splitlines(),
            fromfile=from_label,
            tofile=to_label,
            lineterm="",
        )
    )


def summarize_unified_diff_lines(diff_lines: list[str]) -> dict[str, int]:
    additions = 0
    deletions = 0
    for line in diff_lines:
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1
    return {
        "addition_count": additions,
        "deletion_count": deletions,
        "changed_line_count": additions + deletions,
    }


__all__ = [
    "build_unified_diff_lines",
    "normalize_layout_text",
    "summarize_unified_diff_lines",
]
