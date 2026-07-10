from __future__ import annotations

import json
import subprocess
import tomllib
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


def read_toml_optional(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def typing_debt_allowlist(pyproject_payload: dict[str, Any]) -> list[str]:
    tool = pyproject_payload.get("tool", {}) if isinstance(pyproject_payload.get("tool"), dict) else {}
    sattlint_tool = tool.get("sattlint", {}) if isinstance(tool.get("sattlint"), dict) else {}
    typing_ratchet = (
        sattlint_tool.get("typing_ratchet", {}) if isinstance(sattlint_tool.get("typing_ratchet"), dict) else {}
    )
    raw_allowlist = typing_ratchet.get("debt_allowlist", [])
    if not isinstance(raw_allowlist, list):
        return []
    return sorted(str(path).strip() for path in raw_allowlist if isinstance(path, str) and str(path).strip())


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def format_basis_points_percent(value: Any) -> str:
    try:
        return f"{float(value) / 100:.2f}%"
    except (TypeError, ValueError):
        return "n/a"


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


def build_ratchet_status(
    *,
    coverage_ratchet: dict[str, Any],
    structural_ratchet: dict[str, Any],
    audit_summary: dict[str, Any],
) -> dict[str, Any]:
    coverage_metrics = coverage_ratchet.get("metrics", {}) if isinstance(coverage_ratchet.get("metrics"), dict) else {}
    coverage_summary = coverage_ratchet.get("summary", {}) if isinstance(coverage_ratchet.get("summary"), dict) else {}
    structural_metrics = (
        structural_ratchet.get("metrics", {}) if isinstance(structural_ratchet.get("metrics"), dict) else {}
    )
    findings = audit_summary.get("findings", []) if isinstance(audit_summary.get("findings"), list) else []

    current_line_rate = round(safe_float(coverage_summary.get("total_line_rate")), 4)
    minimum_line_rate = round(safe_float(coverage_metrics.get("min_line_rate_basis_points", 0)) / 10000, 4)
    coverage_status = "pass" if current_line_rate >= minimum_line_rate else "fail"

    function_over_budget_count = int(structural_metrics.get("function_over_budget_count", 0))
    class_over_budget_count = int(structural_metrics.get("class_over_budget_count", 0))
    file_exception_count = len(structural_ratchet.get("file_line_exceptions", {}))
    structural_budget_regression = any(
        isinstance(finding, dict) and finding.get("id") == "structural-budget-ratchet-regression"
        for finding in findings
    )

    if structural_budget_regression:
        structural_status = "fail"
    elif function_over_budget_count or class_over_budget_count or file_exception_count:
        structural_status = "pass_with_findings"
    else:
        structural_status = "pass"

    if coverage_status == "fail" or structural_status == "fail":
        overall_status = "fail"
    elif structural_status == "pass_with_findings":
        overall_status = "pass_with_findings"
    else:
        overall_status = "pass"

    return {
        "overall_status": overall_status,
        "coverage": {
            "status": coverage_status,
            "current_line_rate": current_line_rate,
            "minimum_line_rate": minimum_line_rate,
            "minimum_changed_line_rate": round(
                safe_float(coverage_metrics.get("min_changed_line_rate_basis_points", 0)) / 10000,
                4,
            ),
            "minimum_touched_file_line_rate": round(
                safe_float(coverage_metrics.get("min_touched_file_line_rate_basis_points", 0)) / 10000,
                4,
            ),
        },
        "structural": {
            "status": structural_status,
            "structural_budget_regression": structural_budget_regression,
            "function_over_budget_count": function_over_budget_count,
            "class_over_budget_count": class_over_budget_count,
            "file_exception_count": file_exception_count,
        },
    }


def build_ratchet_inventory(
    *,
    file_debt_ratchet: dict[str, Any],
    structural_ratchet: dict[str, Any],
    pyproject_payload: dict[str, Any],
) -> dict[str, Any]:
    typing_paths = set(typing_debt_allowlist(pyproject_payload))
    structural_exceptions_raw = (
        structural_ratchet.get("file_line_exceptions", {})
        if isinstance(structural_ratchet.get("file_line_exceptions"), dict)
        else {}
    )
    structural_file_exceptions = [
        {
            "path": path,
            "max_lines": int(payload.get("max_lines", 0)) if isinstance(payload, dict) else 0,
            "reason": str(payload.get("reason", "")) if isinstance(payload, dict) else "",
        }
        for path, payload in sorted(structural_exceptions_raw.items())
        if isinstance(path, str) and path.strip()
    ]

    ratcheted_file_statuses: list[dict[str, Any]] = []
    files_payload = file_debt_ratchet.get("files", {}) if isinstance(file_debt_ratchet.get("files"), dict) else {}
    for path, file_payload in sorted(files_payload.items()):
        if not isinstance(path, str) or not isinstance(file_payload, dict):
            continue
        for kind in ("coverage", "structural", "typing"):
            ratchet_payload = file_payload.get(kind)
            if not isinstance(ratchet_payload, dict):
                continue
            row: dict[str, Any] = {
                "path": path,
                "kind": kind,
                "touch_rule": str(ratchet_payload.get("touch_rule", "n/a")),
                "allow_rebaseline": bool(ratchet_payload.get("allow_rebaseline", False)),
                "reason": str(ratchet_payload.get("reason", "")),
            }
            if kind == "coverage":
                current_baseline = int(ratchet_payload.get("current_baseline", 0))
                target = int(ratchet_payload.get("target", 0))
                gap = max(target - current_baseline, 0)
                row.update(
                    {
                        "status": "at_target" if gap == 0 else "below_target",
                        "current_baseline": current_baseline,
                        "target": target,
                        "current_display": format_basis_points_percent(current_baseline),
                        "target_display": format_basis_points_percent(target),
                        "gap_display": "at target" if gap == 0 else f"{gap / 100:.2f} pp short",
                    }
                )
            elif kind == "structural":
                current_baseline = int(ratchet_payload.get("current_baseline", 0))
                target = int(ratchet_payload.get("target", 0))
                gap = max(current_baseline - target, 0)
                row.update(
                    {
                        "status": "at_target" if gap == 0 else "over_target",
                        "current_baseline": current_baseline,
                        "target": target,
                        "current_display": str(current_baseline),
                        "target_display": str(target),
                        "gap_display": "at target" if gap == 0 else f"{gap} over target",
                    }
                )
            else:
                row.update(
                    {
                        "status": "allowlisted" if path in typing_paths else "tracked",
                        "current_baseline": None,
                        "target": None,
                        "current_display": "n/a",
                        "target_display": "n/a",
                        "gap_display": "allowlisted typing debt" if path in typing_paths else "tracked typing debt",
                    }
                )
            ratcheted_file_statuses.append(row)

    return {
        "allow_lists": {
            "typing_debt_allowlist": [{"path": path} for path in sorted(typing_paths)],
            "structural_file_exceptions": structural_file_exceptions,
        },
        "ratcheted_file_statuses": ratcheted_file_statuses,
    }


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
