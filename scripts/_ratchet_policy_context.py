from __future__ import annotations

import json
import os
import re
import subprocess
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STRUCTURAL_RATCHET_PATH = "artifacts/analysis/structural_budget_ratchet.json"
COVERAGE_RATCHET_PATH = "artifacts/analysis/coverage_ratchet.json"
FILE_DEBT_RATCHET_PATH = "artifacts/analysis/file_debt_ratchet.json"
PYPROJECT_PATH = "pyproject.toml"
PROTECTED_PATHS = frozenset({STRUCTURAL_RATCHET_PATH, COVERAGE_RATCHET_PATH, FILE_DEBT_RATCHET_PATH, PYPROJECT_PATH})
APPROVAL_RECORD_PREFIX = ".github/approvals/ratchet-rebaseline"
APPROVAL_RECORD_HINT = ".github/approvals/ratchet-rebaseline-<date>.md"
APPROVAL_BY_RE = re.compile(r"^Approved-by:\s+.+$", re.MULTILINE)
APPROVAL_REASON_RE = re.compile(r"^Reason:\s+.+$", re.MULTILINE)
NEW_PYTHON_FILE_LINE_LIMIT = 500
NEW_MARKDOWN_FILE_LINE_LIMIT = 500
NEW_SOURCE_FILE_COVERAGE_BASIS_POINTS = 10000
COVERAGE_FLOOR_BUFFER_BASIS_POINTS = 100
FILE_DEBT_RATCHET_SCHEMA_KIND = "sattlint.file_debt_ratchet"
FILE_DEBT_RATCHET_SCHEMA_VERSION = 1
FILE_DEBT_ALLOWED_PREFIXES = ("src/", "tests/", "docs/", "scripts/")
LEGACY_MARKDOWN_STRUCTURAL_METRICS = frozenset({"markdown_file_max_lines", "markdown_file_over_budget_count"})
FILE_DEBT_TOUCH_RULES = {
    "coverage": frozenset({"must_not_drop", "must_reach_target_on_touch"}),
    "structural": frozenset({"must_meet_target", "must_not_grow", "must_shrink"}),
    "typing": frozenset({"must_exit_on_touch"}),
}
FILE_DEBT_TOUCH_RULE_RANKS = {
    "coverage": {"must_reach_target_on_touch": 0, "must_not_drop": 1},
    "structural": {"must_meet_target": 0, "must_shrink": 1, "must_not_grow": 2},
    "typing": {"must_exit_on_touch": 0},
}
FIRST_STRUCTURAL_DEBT_PROOF_COMMAND = (
    "python scripts/run_repo_python.py -m pytest --no-cov tests/test_ratchet_policy.py -x -q --tb=short"
)


@dataclass(frozen=True, slots=True)
class ChangeContext:
    changed_files: tuple[str, ...]
    added_files: tuple[str, ...]
    base_ref: str | None
    source: str


@dataclass(frozen=True, slots=True)
class TypingRatchetState:
    strict_paths: tuple[str, ...]
    strict_roots: tuple[str, ...]
    debt_allowlist: tuple[str, ...]
    global_strict: bool = False


def git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 - fixed git executable and controlled arguments
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def normalize_changed_files(raw: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in raw.splitlines() if line.strip())


def normalize_added_files(raw: str) -> tuple[str, ...]:
    added: list[str] = []
    for line in raw.splitlines():
        parts = line.strip().split("\t", 1)
        if len(parts) != 2 or parts[0] != "A":
            continue
        path = parts[1].strip()
        if path:
            added.append(path)
    return tuple(added)


def normalize_rel_path(path: str) -> str:
    return path.replace("\\", "/").strip().strip("/")


def merge_unique_paths(*groups: Sequence[str]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for path in group:
            if path in seen:
                continue
            seen.add(path)
            merged.append(path)
    return tuple(merged)


def is_approval_record_path(path: str) -> bool:
    return path.startswith(APPROVAL_RECORD_PREFIX) and path.endswith(".md")


def detect_untracked_approval_records(repo_root: Path) -> tuple[str, ...]:
    completed = git(repo_root, "ls-files", "--others", "--exclude-standard", ".github/approvals")
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Failed to inspect untracked approval records.")
    return tuple(path for path in normalize_changed_files(completed.stdout) if is_approval_record_path(path))


def detect_change_context(repo_root: Path, env: Mapping[str, str] | None = None) -> ChangeContext:
    effective_env = os.environ if env is None else env
    untracked_approval_records = detect_untracked_approval_records(repo_root)
    base_ref_name = effective_env.get("SATTLINT_RATCHET_BASE_REF")
    if not base_ref_name and effective_env.get("GITHUB_BASE_REF"):
        base_ref_name = f"origin/{effective_env['GITHUB_BASE_REF']}"
    if base_ref_name:
        diff = git(repo_root, "diff", "--name-only", "--diff-filter=ACMR", f"{base_ref_name}...HEAD")
        added = git(repo_root, "diff", "--name-status", "--diff-filter=A", f"{base_ref_name}...HEAD")
        if diff.returncode != 0:
            raise RuntimeError(diff.stderr.strip() or f"Failed to diff against {base_ref_name}.")
        if added.returncode != 0:
            raise RuntimeError(added.stderr.strip() or f"Failed to inspect added files against {base_ref_name}.")
        return ChangeContext(
            normalize_changed_files(diff.stdout),
            normalize_added_files(added.stdout),
            base_ref_name,
            "base-ref",
        )

    staged = git(repo_root, "diff", "--cached", "--name-only", "--diff-filter=ACMR")
    staged_added = git(repo_root, "diff", "--cached", "--name-status", "--diff-filter=A")
    if staged.returncode != 0:
        raise RuntimeError(staged.stderr.strip() or "Failed to inspect staged files.")
    if staged_added.returncode != 0:
        raise RuntimeError(staged_added.stderr.strip() or "Failed to inspect staged added files.")
    staged_files = normalize_changed_files(staged.stdout)
    if staged_files:
        return ChangeContext(staged_files, normalize_added_files(staged_added.stdout), "HEAD", "staged")

    worktree = git(repo_root, "diff", "--name-only", "--diff-filter=ACMR", "HEAD")
    worktree_added = git(repo_root, "diff", "--name-status", "--diff-filter=A", "HEAD")
    if worktree.returncode == 0 and worktree_added.returncode == 0:
        worktree_files = normalize_changed_files(worktree.stdout)
        if worktree_files or untracked_approval_records:
            return ChangeContext(
                merge_unique_paths(worktree_files, untracked_approval_records),
                merge_unique_paths(normalize_added_files(worktree_added.stdout), untracked_approval_records),
                "HEAD",
                "worktree",
            )

    parent = git(repo_root, "rev-parse", "--verify", "HEAD^")
    if parent.returncode == 0:
        diff = git(repo_root, "diff", "--name-only", "--diff-filter=ACMR", "HEAD^..HEAD")
        added = git(repo_root, "diff", "--name-status", "--diff-filter=A", "HEAD^..HEAD")
        if diff.returncode != 0:
            raise RuntimeError(diff.stderr.strip() or "Failed to diff HEAD^..HEAD.")
        if added.returncode != 0:
            raise RuntimeError(added.stderr.strip() or "Failed to inspect added files in HEAD^..HEAD.")
        return ChangeContext(
            normalize_changed_files(diff.stdout),
            normalize_added_files(added.stdout),
            "HEAD^",
            "head-parent",
        )

    return ChangeContext((), (), None, "none")


def load_current_texts(repo_root: Path, rel_paths: Sequence[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for rel_path in rel_paths:
        path = repo_root / rel_path
        if not path.exists():
            continue
        texts[rel_path] = path.read_text(encoding="utf-8")
    return texts


def load_base_texts(repo_root: Path, base_ref: str | None, rel_paths: Sequence[str]) -> dict[str, str | None]:
    texts: dict[str, str | None] = dict.fromkeys(rel_paths)
    if base_ref is None:
        return texts
    for rel_path in rel_paths:
        completed = git(repo_root, "show", f"{base_ref}:{rel_path}")
        if completed.returncode == 0:
            texts[rel_path] = completed.stdout
    return texts


def parse_json_payload(text: str, label: str) -> dict[str, Any]:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object.")
    return payload


def normalized_string_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list.")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label} entries must be non-empty strings.")
        rel_path = normalize_rel_path(item)
        if rel_path in seen:
            raise ValueError(f"{label} contains duplicate path {rel_path!r}.")
        seen.add(rel_path)
        normalized.append(rel_path)
    return tuple(normalized)


def pyproject_payload(text: str, label: str) -> dict[str, Any]:
    payload = tomllib.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must parse to a TOML object.")
    return payload


def explicit_base_ref(repo_root: Path, env: Mapping[str, str] | None = None) -> str | None:
    effective_env = os.environ if env is None else env
    base_ref_name = effective_env.get("SATTLINT_RATCHET_BASE_REF")
    if not base_ref_name and effective_env.get("GITHUB_BASE_REF"):
        base_ref_name = f"origin/{effective_env['GITHUB_BASE_REF']}"
    if base_ref_name:
        return base_ref_name

    head = git(repo_root, "rev-parse", "--verify", "HEAD")
    if head.returncode == 0:
        return "HEAD"
    return None


def visible_approval_record_paths(repo_root: Path) -> tuple[str, ...]:
    tracked = git(repo_root, "diff", "--name-only", "--diff-filter=ACMR", "HEAD", "--", ".github/approvals")
    tracked_paths = normalize_changed_files(tracked.stdout) if tracked.returncode == 0 else ()
    return merge_unique_paths(tracked_paths, detect_untracked_approval_records(repo_root))
