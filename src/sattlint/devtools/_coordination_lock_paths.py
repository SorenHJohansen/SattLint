"""Path and worktree helpers for coordination lock state."""

from __future__ import annotations

import shutil
import subprocess  # nosec B404
from collections.abc import Mapping
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any


def coordination_dir(repo_root: Path) -> Path:
    return repo_root / ".github" / "coordination"


@cache
def git_common_dir(repo_root: Path) -> Path:
    resolved_repo_root = repo_root.resolve()
    git_executable = shutil.which("git")
    if git_executable is None:
        return (resolved_repo_root / ".git").resolve()
    completed = subprocess.run(
        [git_executable, "rev-parse", "--git-common-dir"],
        cwd=resolved_repo_root,
        check=False,
        capture_output=True,
        text=True,
    )  # nosec B603
    if completed.returncode != 0:
        return (resolved_repo_root / ".git").resolve()

    raw_value = completed.stdout.strip() or ".git"
    path = Path(raw_value)
    if not path.is_absolute():
        path = (resolved_repo_root / path).resolve()
    return path.resolve()


def shared_coordination_dir(repo_root: Path, *, shared_coordination_dir_name: str) -> Path:
    return git_common_dir(repo_root) / shared_coordination_dir_name


def ledger_path(repo_root: Path, *, ledger_file_name: str) -> Path:
    return coordination_dir(repo_root) / ledger_file_name


def template_path(repo_root: Path, *, ledger_template_name: str) -> Path:
    return coordination_dir(repo_root) / ledger_template_name


def legacy_lock_state_path(repo_root: Path, *, lock_state_file_name: str) -> Path:
    return coordination_dir(repo_root) / lock_state_file_name


def lock_state_path(repo_root: Path, *, shared_coordination_dir_name: str, lock_state_file_name: str) -> Path:
    return (
        shared_coordination_dir(repo_root, shared_coordination_dir_name=shared_coordination_dir_name)
        / lock_state_file_name
    )


def summary_path(repo_root: Path, *, summary_file_name: str) -> Path:
    return coordination_dir(repo_root) / summary_file_name


def display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _parse_attached_worktree_branches(output: str) -> set[str]:
    branches: set[str] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("branch refs/heads/"):
            branches.add(line.removeprefix("branch refs/heads/").strip())
    return branches


def _attached_worktree_branches(repo_root: Path) -> set[str]:
    resolved_repo_root = repo_root.resolve()
    git_executable = shutil.which("git")
    if git_executable is None:
        return set()

    completed = subprocess.run(
        [git_executable, "worktree", "list", "--porcelain"],
        cwd=resolved_repo_root,
        check=False,
        capture_output=True,
        text=True,
    )  # nosec B603
    if completed.returncode != 0:
        return set()
    return _parse_attached_worktree_branches(completed.stdout)


def _task_contract_path_for_workstream(repo_root: Path, workstream_id: str, *, task_contracts_dir: Path) -> Path:
    return repo_root / task_contracts_dir / f"{workstream_id}.json"


def _handoff_path_for_workstream(repo_root: Path, workstream_id: str, *, handoffs_dir: Path) -> Path:
    return repo_root / handoffs_dir / f"{workstream_id}.json"


def _expected_workstream_branches(workstream_id: str, *, supported_stage_branch_prefixes: tuple[str, ...]) -> set[str]:
    return {workstream_id, *(f"{prefix}{workstream_id}" for prefix in supported_stage_branch_prefixes)}


def parse_updated_at_timestamp(raw_timestamp: str) -> datetime | None:
    normalized = raw_timestamp.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def entry_has_supporting_artifact(
    repo_root: Path,
    workstream_id: str,
    *,
    task_contract_path_for_workstream: Any,
    handoff_path_for_workstream: Any,
) -> bool:
    return (
        task_contract_path_for_workstream(repo_root, workstream_id).exists()
        or handoff_path_for_workstream(repo_root, workstream_id).exists()
    )


def entry_is_stale(
    entry: Mapping[str, Any],
    *,
    repo_root: Path,
    attached_worktree_branches: set[str],
    now: datetime,
    entry_has_supporting_artifact: Any,
    expected_workstream_branches: Any,
    parse_updated_at_timestamp: Any,
    deprecated_lock_claim_path: str,
    stale_entry_grace_period: Any,
) -> bool:
    if entry_has_supporting_artifact(repo_root, entry["workstream_id"]):
        return False
    if expected_workstream_branches(entry["workstream_id"]) & attached_worktree_branches:
        return False
    if deprecated_lock_claim_path in entry["claimed_paths"]:
        return True

    updated_at = parse_updated_at_timestamp(entry["updated_at"])
    if updated_at is None:
        return True
    return now - updated_at > stale_entry_grace_period


def prune_stale_entries[EntryT: Mapping[str, Any]](
    repo_root: Path,
    entries: list[EntryT],
    *,
    attached_worktree_branches: Any,
    now: datetime,
    active_statuses: set[str] | frozenset[str],
    entry_is_stale: Any,
) -> tuple[list[EntryT], int]:
    kept_entries: list[EntryT] = []
    dropped_entries = 0
    for entry in entries:
        if entry["status"] in active_statuses and entry_is_stale(
            entry,
            repo_root=repo_root,
            attached_worktree_branches=attached_worktree_branches,
            now=now,
        ):
            dropped_entries += 1
            continue
        kept_entries.append(entry)
    return kept_entries, dropped_entries


def normalize_relative_path(raw_path: str) -> str:
    normalized = raw_path.strip().strip("`'\"")
    normalized = normalized.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def normalize_claim_path(raw_path: str, *, repo_root: Path | None = None) -> str:
    normalized = normalize_relative_path(raw_path)
    if not normalized:
        return ""
    is_directory = raw_path.strip().rstrip().endswith(("/", "\\"))
    if not is_directory and repo_root is not None:
        is_directory = (repo_root / normalized).is_dir()
    return f"{normalized}/" if is_directory else normalized


def split_claim_text(raw_claims: str, *, backtick_item_re: Any) -> list[str]:
    backtick_items = backtick_item_re.findall(raw_claims)
    if backtick_items:
        return backtick_items
    return [part.strip() for part in raw_claims.split(",") if part.strip()]


def unique_claim_paths(values: list[str] | tuple[str, ...], *, repo_root: Path | None = None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = normalize_claim_path(raw_value, repo_root=repo_root)
        if not value:
            continue
        seen_key = value.casefold()
        if seen_key in seen:
            continue
        seen.add(seen_key)
        normalized.append(value)
    return normalized


def resolve_workspace_path(raw_path: str, cwd: Path) -> Path:
    path = Path(normalize_relative_path(raw_path))
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def resolve_claim_patterns(claimed_paths: list[str] | tuple[str, ...], cwd: Path) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    for raw_path in claimed_paths:
        normalized = normalize_claim_path(raw_path, repo_root=cwd)
        if not normalized:
            continue
        patterns.append(
            {
                "path": resolve_workspace_path(normalized, cwd),
                "is_directory": normalized.endswith("/"),
            }
        )
    return patterns


def _claim_matches_path(claim: str, rel_path: str) -> bool:
    if claim.endswith("/"):
        return rel_path.startswith(claim)
    return rel_path == claim
