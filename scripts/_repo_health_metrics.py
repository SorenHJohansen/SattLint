from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT_JUNK_SUFFIXES = frozenset({".txt"})
ROOT_JUNK_PREFIXES = (".tmp",)
LARGEST_FILE_SCOPE_KINDS = {
    "src/": "source",
    "scripts/": "source",
    "tests/": "test",
}

type GitRunner = Callable[..., subprocess.CompletedProcess[str]]


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def read_json_optional(path: Path) -> dict[str, Any]:
    try:
        return read_json(path)
    except FileNotFoundError:
        return {}


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def root_git_status_map(repo_root: Path, git: GitRunner) -> dict[str, str]:
    completed = git("status", "--porcelain", "--ignored", "--untracked-files=all", "--", ".")
    if completed.returncode != 0:
        return {}

    statuses: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if len(line) < 4:
            continue
        status = line[:2]
        rel_path = line[3:].strip()
        if not rel_path or "/" in rel_path or " -> " in rel_path:
            continue
        statuses[rel_path] = status
    return statuses


def looks_like_root_junk(name: str) -> bool:
    lowered = name.casefold()
    return lowered.startswith(ROOT_JUNK_PREFIXES) or any(lowered.endswith(suffix) for suffix in ROOT_JUNK_SUFFIXES)


def build_root_junk_candidates(repo_root: Path, tracked_files: list[str], git: GitRunner) -> list[dict[str, str]]:
    tracked = set(tracked_files)
    root_statuses = root_git_status_map(repo_root, git)
    candidates: list[dict[str, str]] = []

    for path in sorted(repo_root.iterdir(), key=lambda current: current.name.casefold()):
        if not path.is_file():
            continue

        name = path.name
        if name in tracked or not looks_like_root_junk(name):
            continue

        git_status = root_statuses.get(name)
        if root_statuses and git_status not in {"!!", "??"}:
            continue

        candidates.append(
            {
                "path": name,
                "kind": "tmp" if name.casefold().startswith(ROOT_JUNK_PREFIXES) else "txt",
                "git_state": "ignored" if git_status == "!!" else "untracked" if git_status == "??" else "present",
            }
        )

    return candidates


def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())


def largest_file_kind(rel_path: str) -> str | None:
    if not rel_path.endswith(".py"):
        return None
    for prefix, kind in LARGEST_FILE_SCOPE_KINDS.items():
        if rel_path.startswith(prefix):
            return kind
    return None


def largest_files(repo_root: Path, tracked_files: list[str], limit: int = 10) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for rel_path in tracked_files:
        path = repo_root / rel_path
        if not path.is_file():
            continue
        kind = largest_file_kind(rel_path)
        if kind is None:
            continue
        entries.append({"path": rel_path, "lines": count_lines(path), "kind": kind})
    entries.sort(key=lambda item: (-int(item["lines"]), str(item["path"])))
    return entries[:limit]


def slowest_tests(pytest_report: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    testcases = pytest_report.get("testcases", [])
    if not isinstance(testcases, list):
        return []
    entries: list[dict[str, Any]] = []
    for testcase in testcases:
        if not isinstance(testcase, dict):
            continue
        entries.append(
            {
                "name": f"{testcase.get('classname', 'unknown')}.{testcase.get('name', 'unknown')}",
                "time_seconds": safe_float(testcase.get("time")),
                "outcome": testcase.get("outcome", "unknown"),
            }
        )
    entries.sort(key=lambda item: (-float(item["time_seconds"]), str(item["name"])))
    return entries[:limit]


def branch_health(repo_root: Path, git: GitRunner, *, default_ref: str = "origin/main") -> dict[str, Any]:
    branch_completed = git("rev-parse", "--abbrev-ref", "HEAD")
    branch_name = branch_completed.stdout.strip() if branch_completed.returncode == 0 else "unknown"
    status_completed = git("status", "--porcelain")
    dirty_files = (
        len([line for line in status_completed.stdout.splitlines() if line.strip()])
        if status_completed.returncode == 0
        else None
    )

    ahead_by: int | None = None
    behind_by: int | None = None
    ahead_behind_completed = git("rev-list", "--left-right", "--count", f"{default_ref}...HEAD")
    if ahead_behind_completed.returncode == 0:
        parts = ahead_behind_completed.stdout.split()
        if len(parts) == 2:
            behind_by = int(parts[0])
            ahead_by = int(parts[1])

    worktree_completed = git("worktree", "list", "--porcelain")
    worktree_count = None
    if worktree_completed.returncode == 0:
        worktree_count = len([line for line in worktree_completed.stdout.splitlines() if line.startswith("worktree ")])

    return {
        "branch": branch_name,
        "dirty_files": dirty_files,
        "ahead_by": ahead_by,
        "behind_by": behind_by,
        "tracked_worktrees": worktree_count,
    }


def handoff_files(repo_root: Path) -> list[Path]:
    handoff_dir = repo_root / ".ai" / "handoffs"
    if not handoff_dir.exists():
        return []
    return [
        path
        for path in sorted(handoff_dir.glob("*.json"))
        if path.name != "handoff.schema.json" and not path.name.endswith(".example.json")
    ]


def handoff_metrics(repo_root: Path) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    validation_states: dict[str, int] = {}
    handoffs = handoff_files(repo_root)
    for path in handoffs:
        payload = read_json(path)
        status = str(payload.get("status", "draft"))
        statuses[status] = statuses.get(status, 0) + 1
        validation = payload.get("validation_status", {})
        if isinstance(validation, dict):
            state = str(validation.get("state", "pending"))
            validation_states[state] = validation_states.get(state, 0) + 1

    merged = statuses.get("merged", 0)
    rejected = statuses.get("rejected", 0)
    decided = merged + rejected
    merge_success_rate = None if decided == 0 else round(merged / decided, 4)

    return {
        "handoff_count": len(handoffs),
        "statuses": statuses,
        "validation_states": validation_states,
        "ai_task_throughput": len(handoffs),
        "merge_success_rate": merge_success_rate,
    }


def history_snapshots(repo_root: Path, history_dir: Path, limit: int = 20) -> list[dict[str, Any]]:
    if not history_dir.exists():
        return []
    snapshots: list[dict[str, Any]] = []
    for path in sorted(history_dir.glob("*.json"))[-limit:]:
        try:
            payload = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        payload["_path"] = path.relative_to(repo_root).as_posix()
        snapshots.append(payload)
    return snapshots


def trend_metrics(current_metrics: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {
            "history_count": 0,
            "coverage_delta": None,
            "finding_delta": None,
            "context_delta": None,
            "largest_file_delta": None,
        }

    previous = history[-1]
    previous_metrics = previous.get("metrics", {}) if isinstance(previous.get("metrics", {}), dict) else {}
    current_coverage = safe_float(current_metrics.get("coverage_total_line_rate"))
    previous_coverage = safe_float(previous_metrics.get("coverage_total_line_rate"))
    current_findings = int(current_metrics.get("finding_count", 0))
    previous_findings = int(previous_metrics.get("finding_count", 0))
    current_context = int(current_metrics.get("auto_loaded_context_lines", 0))
    previous_context = int(previous_metrics.get("auto_loaded_context_lines", 0))
    current_largest = int(current_metrics.get("largest_file_lines", 0))
    previous_largest = int(previous_metrics.get("largest_file_lines", 0))
    return {
        "history_count": len(history),
        "coverage_delta": round(current_coverage - previous_coverage, 4),
        "finding_delta": current_findings - previous_findings,
        "context_delta": current_context - previous_context,
        "largest_file_delta": current_largest - previous_largest,
    }


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
