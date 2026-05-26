from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

import context_health

from sattlint.devtools.artifact_readiness import ReadinessError, assert_artifact_dir_ready

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_DIR = REPO_ROOT / "artifacts" / "audit"
DEFAULT_COVERAGE_RATCHET = REPO_ROOT / "artifacts" / "analysis" / "coverage_ratchet.json"
DEFAULT_STRUCTURAL_RATCHET = REPO_ROOT / "artifacts" / "analysis" / "structural_budget_ratchet.json"
DEFAULT_FILE_DEBT_RATCHET = REPO_ROOT / "artifacts" / "analysis" / "file_debt_ratchet.json"
DEFAULT_HISTORY_DIR = REPO_ROOT / "metrics" / "history"
REFRESH_DASHBOARD_TASK = "Metrics: Refresh Repo Health Dashboard"
ROOT_JUNK_SUFFIXES = frozenset({".txt"})
ROOT_JUNK_PREFIXES = (".tmp",)
LARGEST_FILE_SCOPE_KINDS = {
    "src/": "source",
    "scripts/": "source",
    "tests/": "test",
}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _read_json_optional(path: Path) -> dict[str, Any]:
    try:
        return _read_json(path)
    except FileNotFoundError:
        return {}


def _read_toml_optional(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _typing_debt_allowlist(pyproject_payload: dict[str, Any]) -> list[str]:
    tool = pyproject_payload.get("tool", {}) if isinstance(pyproject_payload.get("tool"), dict) else {}
    sattlint_tool = tool.get("sattlint", {}) if isinstance(tool.get("sattlint"), dict) else {}
    typing_ratchet = (
        sattlint_tool.get("typing_ratchet", {}) if isinstance(sattlint_tool.get("typing_ratchet"), dict) else {}
    )
    raw_allowlist = typing_ratchet.get("debt_allowlist", [])
    if not isinstance(raw_allowlist, list):
        return []
    return sorted(str(path).strip() for path in raw_allowlist if isinstance(path, str) and str(path).strip())


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_basis_points_percent(value: Any) -> str:
    try:
        return f"{float(value) / 100:.2f}%"
    except (TypeError, ValueError):
        return "n/a"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 - fixed git executable and controlled arguments
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _tracked_files() -> list[str]:
    completed = _git("ls-files")
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _root_git_status_map() -> dict[str, str]:
    completed = _git("status", "--porcelain", "--ignored", "--untracked-files=all", "--", ".")
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


def _looks_like_root_junk(name: str) -> bool:
    lowered = name.casefold()
    return lowered.startswith(ROOT_JUNK_PREFIXES) or any(lowered.endswith(suffix) for suffix in ROOT_JUNK_SUFFIXES)


def _root_junk_candidates() -> list[dict[str, str]]:
    tracked = set(_tracked_files())
    root_statuses = _root_git_status_map()
    candidates: list[dict[str, str]] = []

    for path in sorted(REPO_ROOT.iterdir(), key=lambda current: current.name.casefold()):
        if not path.is_file():
            continue

        name = path.name
        if name in tracked or not _looks_like_root_junk(name):
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


def _count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())


def _largest_file_kind(rel_path: str) -> str | None:
    if not rel_path.endswith(".py"):
        return None
    for prefix, kind in LARGEST_FILE_SCOPE_KINDS.items():
        if rel_path.startswith(prefix):
            return kind
    return None


def _largest_files(limit: int = 10) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for rel_path in _tracked_files():
        path = REPO_ROOT / rel_path
        if not path.is_file():
            continue
        kind = _largest_file_kind(rel_path)
        if kind is None:
            continue
        entries.append(
            {
                "path": rel_path,
                "lines": _count_lines(path),
                "kind": kind,
            }
        )
    entries.sort(key=lambda item: (-int(item["lines"]), str(item["path"])))
    return entries[:limit]


def _slowest_tests(pytest_report: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
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
                "time_seconds": _safe_float(testcase.get("time")),
                "outcome": testcase.get("outcome", "unknown"),
            }
        )
    entries.sort(key=lambda item: (-float(item["time_seconds"]), str(item["name"])))
    return entries[:limit]


def _branch_health() -> dict[str, Any]:
    branch_completed = _git("rev-parse", "--abbrev-ref", "HEAD")
    branch_name = branch_completed.stdout.strip() if branch_completed.returncode == 0 else "unknown"
    status_completed = _git("status", "--porcelain")
    dirty_files = (
        len([line for line in status_completed.stdout.splitlines() if line.strip()])
        if status_completed.returncode == 0
        else None
    )

    ahead_by: int | None = None
    behind_by: int | None = None
    default_ref = "origin/main"
    ahead_behind_completed = _git("rev-list", "--left-right", "--count", f"{default_ref}...HEAD")
    if ahead_behind_completed.returncode == 0:
        parts = ahead_behind_completed.stdout.split()
        if len(parts) == 2:
            behind_by = int(parts[0])
            ahead_by = int(parts[1])

    worktree_completed = _git("worktree", "list", "--porcelain")
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


def _handoff_files() -> list[Path]:
    handoff_dir = REPO_ROOT / ".ai" / "handoffs"
    if not handoff_dir.exists():
        return []
    return [
        path
        for path in sorted(handoff_dir.glob("*.json"))
        if path.name != "handoff.schema.json" and not path.name.endswith(".example.json")
    ]


def _handoff_metrics() -> dict[str, Any]:
    statuses: dict[str, int] = {}
    validation_states: dict[str, int] = {}
    for path in _handoff_files():
        payload = _read_json(path)
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
        "handoff_count": len(_handoff_files()),
        "statuses": statuses,
        "validation_states": validation_states,
        "ai_task_throughput": len(_handoff_files()),
        "merge_success_rate": merge_success_rate,
    }


def _history_snapshots(limit: int = 20) -> list[dict[str, Any]]:
    if not DEFAULT_HISTORY_DIR.exists():
        return []
    snapshots: list[dict[str, Any]] = []
    for path in sorted(DEFAULT_HISTORY_DIR.glob("*.json"))[-limit:]:
        try:
            payload = _read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        payload["_path"] = path.relative_to(REPO_ROOT).as_posix()
        snapshots.append(payload)
    return snapshots


def _trend_metrics(current_metrics: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
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
    current_coverage = _safe_float(current_metrics.get("coverage_total_line_rate"))
    previous_coverage = _safe_float(previous_metrics.get("coverage_total_line_rate"))
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


def _build_ratchet_status(
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

    current_line_rate = round(_safe_float(coverage_summary.get("total_line_rate")), 4)
    minimum_line_rate = round(_safe_float(coverage_metrics.get("min_line_rate_basis_points", 0)) / 10000, 4)
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
                _safe_float(coverage_metrics.get("min_changed_line_rate_basis_points", 0)) / 10000,
                4,
            ),
            "minimum_touched_file_line_rate": round(
                _safe_float(coverage_metrics.get("min_touched_file_line_rate_basis_points", 0)) / 10000,
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


def _build_ratchet_inventory(
    *,
    file_debt_ratchet: dict[str, Any],
    structural_ratchet: dict[str, Any],
    pyproject_payload: dict[str, Any],
) -> dict[str, Any]:
    typing_debt_allowlist = _typing_debt_allowlist(pyproject_payload)
    typing_debt_paths = set(typing_debt_allowlist)
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
                        "current_display": _format_basis_points_percent(current_baseline),
                        "target_display": _format_basis_points_percent(target),
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
                        "status": "allowlisted" if path in typing_debt_paths else "tracked",
                        "current_baseline": None,
                        "target": None,
                        "current_display": "n/a",
                        "target_display": "n/a",
                        "gap_display": "allowlisted typing debt"
                        if path in typing_debt_paths
                        else "tracked typing debt",
                    }
                )
            ratcheted_file_statuses.append(row)

    return {
        "allow_lists": {
            "typing_debt_allowlist": [{"path": path} for path in typing_debt_allowlist],
            "structural_file_exceptions": structural_file_exceptions,
        },
        "ratcheted_file_statuses": ratcheted_file_statuses,
    }


def build_report(audit_dir: Path) -> dict[str, Any]:
    assert_artifact_dir_ready(audit_dir)
    audit_status = _read_json(audit_dir / "status.json")
    audit_summary = _read_json(audit_dir / "summary.json")
    ruff_report = _read_json(audit_dir / "pipeline" / "ruff.json")
    pyright_report = _read_json(audit_dir / "pipeline" / "pyright.json")
    pytest_report = _read_json(audit_dir / "pipeline" / "pytest.json")
    coverage_ratchet = _read_json_optional(DEFAULT_COVERAGE_RATCHET)
    structural_ratchet = _read_json_optional(DEFAULT_STRUCTURAL_RATCHET)
    file_debt_ratchet = _read_json_optional(DEFAULT_FILE_DEBT_RATCHET)
    pyproject_payload = _read_toml_optional(REPO_ROOT / "pyproject.toml")
    context_report = context_health.build_report()

    largest_files = _largest_files()
    slowest_tests = _slowest_tests(pytest_report)
    branch_health = _branch_health()
    root_junk_candidates = _root_junk_candidates()
    handoffs = _handoff_metrics()

    audit_overall_status = str(audit_status.get("overall_status", "unknown"))
    context_status = str(context_report.get("status", "fail"))
    status = "pass" if audit_overall_status == "pass" and context_status == "pass" else "fail"
    warnings: list[dict[str, Any]] = []
    if root_junk_candidates:
        warnings.append(
            {
                "id": "ignored-root-junk",
                "severity": "low",
                "message": "Repo root contains ignored or untracked scratch files.",
                "paths": [candidate["path"] for candidate in root_junk_candidates],
                "candidates": root_junk_candidates,
                "suggestion": "Delete the files or move durable outputs under artifacts/, dumps/, or a test fixture directory.",
            }
        )
    if status == "pass" and (int(audit_status.get("finding_count", 0)) > 0 or warnings):
        status = "pass_with_findings"

    coverage_summary = coverage_ratchet.get("summary", {})
    structural_metrics = structural_ratchet.get("metrics", {})
    metrics = {
        "finding_count": int(audit_status.get("finding_count", 0)),
        "blocking_finding_count": int(audit_status.get("blocking_finding_count", 0)),
        "coverage_total_line_rate": round(_safe_float(coverage_summary.get("total_line_rate")), 4),
        "coverage_min_line_rate": round(
            _safe_float(coverage_ratchet.get("metrics", {}).get("min_line_rate_basis_points", 0)) / 10000,
            4,
        ),
        "ruff_issue_count": int(ruff_report.get("finding_count", 0)),
        "pyright_error_count": int(pyright_report.get("error_count", 0)),
        "pyright_warning_count": int(pyright_report.get("warning_count", 0)),
        "test_runtime_seconds": round(_safe_float(pytest_report.get("duration_seconds")), 3),
        "pre_commit_runtime_seconds": None,
        "context_auto_loaded_budget": int(context_report.get("metrics", {}).get("auto_loaded_context_budget", 0)),
        "auto_loaded_context_lines": int(context_report.get("metrics", {}).get("auto_loaded_context_lines", 0)),
        "scoped_context_file_count": int(context_report.get("metrics", {}).get("scoped_context_file_count", 0)),
        "function_over_budget_count": int(structural_metrics.get("function_over_budget_count", 0)),
        "class_over_budget_count": int(structural_metrics.get("class_over_budget_count", 0)),
        "source_file_max_lines": int(structural_metrics.get("source_file_max_lines", 0)),
        "largest_file_lines": int(largest_files[0]["lines"]) if largest_files else 0,
        "largest_file_path": str(largest_files[0]["path"]) if largest_files else None,
        "ai_task_throughput": int(handoffs.get("ai_task_throughput", 0)),
        "merge_success_rate": handoffs.get("merge_success_rate"),
        "dirty_files": branch_health.get("dirty_files"),
        "root_junk_file_count": len(root_junk_candidates),
    }

    history = _history_snapshots()
    trend_summary = _trend_metrics(metrics, history)
    ratchet_status = _build_ratchet_status(
        coverage_ratchet=coverage_ratchet,
        structural_ratchet=structural_ratchet,
        audit_summary=audit_summary,
    )
    ratchet_inventory = _build_ratchet_inventory(
        file_debt_ratchet=file_debt_ratchet,
        structural_ratchet=structural_ratchet,
        pyproject_payload=pyproject_payload,
    )

    return {
        "kind": "sattlint.repo_health",
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "audit_dir": audit_dir.relative_to(REPO_ROOT).as_posix(),
        "audit_status": {
            "overall_status": audit_overall_status,
            "max_severity": audit_status.get("max_severity"),
            "finding_count": audit_status.get("finding_count"),
            "severity_counts": audit_status.get("severity_counts", {}),
        },
        "context_status": {
            "status": context_status,
            "issue_count": len(context_report.get("issues", [])),
        },
        "metrics": metrics,
        "branch_health": branch_health,
        "handoffs": handoffs,
        "trend_summary": trend_summary,
        "ratchet_status": ratchet_status,
        "ratchet_inventory": ratchet_inventory,
        "warnings": warnings,
        "top_findings": audit_summary.get("findings", [])[:10],
        "largest_files": largest_files,
        "slowest_tests": slowest_tests,
        "technical_debt_indicators": {
            "structural_budget_regression": ratchet_status["structural"]["structural_budget_regression"],
            "medium_or_higher_findings": int(audit_status.get("finding_count", 0)),
            "file_exception_count": ratchet_status["structural"]["file_exception_count"],
        },
    }


def _render_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# Repository Health",
        "",
        f"- Status: {report['status']}",
        f"- Generated: {report['generated_at']}",
        f"- Audit dir: {report['audit_dir']}",
        f"- Audit findings: {metrics['finding_count']} (blocking: {metrics['blocking_finding_count']})",
        (f"- Coverage: {metrics['coverage_total_line_rate']:.2%} minimum {metrics['coverage_min_line_rate']:.2%}"),
        (
            "- Context: "
            f"{metrics['auto_loaded_context_lines']}/{metrics['context_auto_loaded_budget']} auto-loaded lines"
        ),
        f"- AI throughput: {metrics['ai_task_throughput']}",
        (
            f"- Merge success rate: {metrics['merge_success_rate']:.2%}"
            if metrics["merge_success_rate"] is not None
            else "- Merge success rate: n/a"
        ),
        f"- Root junk files: {metrics['root_junk_file_count']}",
        "",
        "## Quality",
        "",
        f"- Ruff issues: {metrics['ruff_issue_count']}",
        (f"- Pyright: {metrics['pyright_error_count']} errors, {metrics['pyright_warning_count']} warnings"),
        f"- Pytest runtime: {metrics['test_runtime_seconds']} seconds",
        (
            "- Structural budget: "
            f"{metrics['function_over_budget_count']} functions, {metrics['class_over_budget_count']} classes over budget"
        ),
        "",
        "## Largest Files",
        "",
    ]
    for item in report["largest_files"][:5]:
        lines.append(f"- {item['path']}: {item['lines']} lines ({item['kind']})")
    lines.extend(["", "## Slowest Tests", ""])
    for item in report["slowest_tests"][:5]:
        lines.append(f"- {item['name']}: {item['time_seconds']:.3f}s ({item['outcome']})")
    if report.get("warnings"):
        lines.extend(["", "## Local Hygiene Warnings", ""])
        for warning in report["warnings"]:
            paths = ", ".join(str(path) for path in warning.get("paths", [])[:5])
            if len(warning.get("paths", [])) > 5:
                paths += ", ..."
            lines.append(f"- {warning['message']} {paths}".rstrip())
    lines.extend(["", "## Trend Summary", ""])
    trend = report["trend_summary"]
    lines.append(f"- History snapshots: {trend['history_count']}")
    lines.append(f"- Coverage delta: {trend['coverage_delta']}")
    lines.append(f"- Finding delta: {trend['finding_delta']}")
    lines.append(f"- Context delta: {trend['context_delta']}")
    lines.append(f"- Largest file delta: {trend['largest_file_delta']}")
    ratchet_status = report.get("ratchet_status", {}) if isinstance(report.get("ratchet_status"), dict) else {}
    coverage_ratchet = ratchet_status.get("coverage", {}) if isinstance(ratchet_status.get("coverage"), dict) else {}
    structural_ratchet = (
        ratchet_status.get("structural", {}) if isinstance(ratchet_status.get("structural"), dict) else {}
    )
    lines.extend(["", "## Ratchets", ""])
    lines.append(f"- Overall: {ratchet_status.get('overall_status', 'unknown')}")
    lines.append(
        "- Coverage ratchet: "
        f"{coverage_ratchet.get('status', 'unknown')} at {_format_percent(coverage_ratchet.get('current_line_rate'))} "
        f"against floor {_format_percent(coverage_ratchet.get('minimum_line_rate'))}"
    )
    lines.append(
        "- Structural ratchet: "
        f"{structural_ratchet.get('status', 'unknown')} with "
        f"{_format_number(structural_ratchet.get('function_over_budget_count'))} functions and "
        f"{_format_number(structural_ratchet.get('class_over_budget_count'))} classes over budget"
    )
    lines.append("")
    return "\n".join(lines)


def _format_percent(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "n/a"


def _format_number(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "n/a"


def _format_signed(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if number.is_integer():
        whole = int(number)
        return f"+{whole}" if whole > 0 else str(whole)
    return f"{number:+.4f}"


def _metric_card(*, label: str, value: str, detail: str) -> str:
    return (
        '<article class="metric-card">'
        f'<div class="metric-label">{escape(label)}</div>'
        f'<div class="metric-value">{escape(value)}</div>'
        f'<div class="metric-detail">{escape(detail)}</div>'
        "</article>"
    )


def _definition_rows(entries: list[tuple[str, str]]) -> str:
    return "".join(
        (f'<div class="definition-row"><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>')
        for label, value in entries
    )


def _status_tone(status: str | None) -> str:
    if status == "pass":
        return "ok"
    if status in {"pass_with_findings", "pass_with_notes"}:
        return "warn"
    if status == "fail":
        return "error"
    return "neutral"


def _status_pill(label: str, status: str | None, *, detail: str | None = None) -> str:
    detail_markup = "" if not detail else f'<div class="pill-detail">{escape(detail)}</div>'
    return (
        f'<div class="pill {_status_tone(status)}">'
        '<div class="pill-copy">'
        f'<span class="pill-label">{escape(label)}</span>'
        f"{detail_markup}"
        "</div>"
        f'<span class="pill-value">{escape(status or "unknown")}</span>'
        "</div>"
    )


def _render_named_list(
    items: list[dict[str, Any]],
    *,
    empty_message: str,
    title_key: str,
    primary_value_key: str,
    secondary_value_key: str,
    primary_suffix: str = "",
) -> str:
    if not items:
        return f'<div class="empty-inline">{escape(empty_message)}</div>'
    rendered: list[str] = []
    for item in items:
        title = str(item.get(title_key, "Unknown item"))
        primary_raw = item.get(primary_value_key)
        if isinstance(primary_raw, float):
            primary = f"{primary_raw:.3f}{primary_suffix}"
        elif isinstance(primary_raw, int):
            primary = f"{primary_raw:,}{primary_suffix}"
        else:
            primary = str(primary_raw) if primary_raw is not None else "n/a"
        secondary_raw = item.get(secondary_value_key)
        secondary = "" if secondary_raw in {None, ""} else f" | {secondary_raw}"
        rendered.append(
            '<article class="list-card compact">'
            f'<div class="list-card-title">{escape(title)}</div>'
            f'<div class="list-card-meta">{escape(primary)}{escape(secondary)}</div>'
            "</article>"
        )
    return "".join(rendered)


def _render_findings(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return '<div class="empty-inline">No top findings in the current snapshot.</div>'
    rendered: list[str] = []
    for finding in findings:
        message = str(finding.get("message", "Unnamed finding"))
        severity = str(finding.get("severity", "unknown"))
        category = str(finding.get("category", "uncategorized"))
        path_text = str(finding.get("path", "workspace"))
        rendered.append(
            '<article class="list-card">'
            f'<div class="list-card-title">{escape(message)}</div>'
            f'<div class="list-card-meta">{escape(severity)} | {escape(category)} | {escape(path_text)}</div>'
            "</article>"
        )
    return "".join(rendered)


def _render_warnings(warnings: list[dict[str, Any]]) -> str:
    if not warnings:
        return '<div class="empty-inline">No local hygiene warnings in the current snapshot.</div>'
    rendered: list[str] = []
    for warning in warnings:
        message = str(warning.get("message", "Warning"))
        paths = warning.get("paths", [])
        path_text = ", ".join(str(path) for path in paths[:5]) if isinstance(paths, list) else "No paths attached"
        rendered.append(
            '<article class="list-card warning-card">'
            f'<div class="list-card-title">{escape(message)}</div>'
            f'<div class="list-card-meta">{escape(path_text or "No paths attached")}</div>'
            "</article>"
        )
    return "".join(rendered)


def _ratchet_inventory_path(main_html_path: Path) -> Path:
    return main_html_path.with_name(f"{main_html_path.stem}-ratchets{main_html_path.suffix}")


def _render_allow_list_rows(items: list[dict[str, Any]], *, columns: tuple[str, ...], empty_message: str) -> str:
    if not items:
        return f'<tr><td colspan="{len(columns)}">{escape(empty_message)}</td></tr>'
    rendered: list[str] = []
    for item in items:
        rendered.append(
            "<tr>" + "".join(f"<td>{escape(str(item.get(column, 'n/a')))}</td>" for column in columns) + "</tr>"
        )
    return "".join(rendered)


def _render_ratcheted_status_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<tr><td colspan="8">No ratcheted files configured.</td></tr>'
    rendered: list[str] = []
    for item in items:
        current_baseline = item.get("current_baseline")
        target = item.get("target")
        if isinstance(current_baseline, int) and isinstance(target, int):
            gap_sort = (
                max(target - current_baseline, 0)
                if item.get("kind") == "coverage"
                else max(current_baseline - target, 0)
            )
        else:
            gap_sort = 0 if item.get("status") == "tracked" else 1
        filter_text = " ".join(
            str(item.get(key, ""))
            for key in (
                "path",
                "kind",
                "status",
                "current_display",
                "target_display",
                "gap_display",
                "touch_rule",
                "reason",
            )
        ).casefold()
        rendered.append(
            '<tr class="ratchet-row"'
            f' data-path="{escape(str(item.get("path", "n/a")))}"'
            f' data-kind="{escape(str(item.get("kind", "n/a")))}"'
            f' data-status="{escape(str(item.get("status", "n/a")))}"'
            f' data-current-sort="{escape(str(current_baseline if isinstance(current_baseline, int) else -1))}"'
            f' data-target-sort="{escape(str(target if isinstance(target, int) else -1))}"'
            f' data-gap-sort="{escape(str(gap_sort))}"'
            f' data-touch-rule="{escape(str(item.get("touch_rule", "n/a")))}"'
            f' data-filter-text="{escape(filter_text)}"'
            ">"
            f"<td>{escape(str(item.get('path', 'n/a')))}</td>"
            f"<td>{escape(str(item.get('kind', 'n/a')))}</td>"
            f"<td>{escape(str(item.get('status', 'n/a')))}</td>"
            f"<td>{escape(str(item.get('current_display', 'n/a')))}</td>"
            f"<td>{escape(str(item.get('target_display', 'n/a')))}</td>"
            f"<td>{escape(str(item.get('gap_display', 'n/a')))}</td>"
            f"<td>{escape(str(item.get('touch_rule', 'n/a')))}</td>"
            f"<td>{escape(str(item.get('reason', '')))}</td>"
            "</tr>"
        )
    return "".join(rendered)


def _render_ratcheted_table_controls() -> str:
    return """
        <div class="table-toolbar" aria-label="Ratcheted file status table controls">
            <label class="table-control search-control" for="ratchet-filter-query">
                <span>Ratcheted file status filter</span>
                <input id="ratchet-filter-query" type="search" placeholder="Filter ratcheted file status by path, reason, or touch rule" />
            </label>
            <label class="table-control" for="ratchet-filter-kind">
                <span>Kind</span>
                <select id="ratchet-filter-kind">
                    <option value="">All</option>
                    <option value="coverage">Coverage</option>
                    <option value="structural">Structural</option>
                    <option value="typing">Typing</option>
                </select>
            </label>
            <label class="table-control" for="ratchet-filter-status">
                <span>Status</span>
                <select id="ratchet-filter-status">
                    <option value="">All</option>
                    <option value="allowlisted">Allowlisted</option>
                    <option value="at_target">At target</option>
                    <option value="below_target">Below target</option>
                    <option value="over_target">Over target</option>
                    <option value="tracked">Tracked</option>
                </select>
            </label>
            <label class="table-control" for="ratchet-sort-by">
                <span>Sort by</span>
                <select id="ratchet-sort-by">
                    <option value="path">Path</option>
                    <option value="kind">Kind</option>
                    <option value="status">Status</option>
                    <option value="current">Current</option>
                    <option value="target">Target</option>
                    <option value="gap">Gap</option>
                </select>
            </label>
            <label class="table-control" for="ratchet-sort-direction">
                <span>Direction</span>
                <select id="ratchet-sort-direction">
                    <option value="asc">Ascending</option>
                    <option value="desc">Descending</option>
                </select>
            </label>
            <button id="ratchet-reset-filters" class="table-reset" type="button">Reset</button>
            <div id="ratchet-table-summary" class="table-summary" aria-live="polite"></div>
        </div>
    """


def _render_ratcheted_table_script() -> str:
    return """
    <script>
        (() => {
            const tbody = document.querySelector('#ratcheted-status-table tbody');
            if (!tbody) {
                return;
            }
            const rows = Array.from(tbody.querySelectorAll('.ratchet-row'));
            if (!rows.length) {
                return;
            }
            const searchInput = document.getElementById('ratchet-filter-query');
            const kindSelect = document.getElementById('ratchet-filter-kind');
            const statusSelect = document.getElementById('ratchet-filter-status');
            const sortBySelect = document.getElementById('ratchet-sort-by');
            const directionSelect = document.getElementById('ratchet-sort-direction');
            const resetButton = document.getElementById('ratchet-reset-filters');
            const summary = document.getElementById('ratchet-table-summary');
            const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

            const numericFields = new Set(['current', 'target', 'gap']);
            const textValue = (row, field) => row.dataset[field] || '';
            const numericValue = (row, field) => {
                const raw = row.dataset[`${field}Sort`];
                const parsed = Number(raw);
                return Number.isFinite(parsed) ? parsed : -1;
            };

            const applyTableState = () => {
                const query = (searchInput?.value || '').trim().toLowerCase();
                const kind = kindSelect?.value || '';
                const status = statusSelect?.value || '';
                const sortBy = sortBySelect?.value || 'path';
                const direction = directionSelect?.value || 'asc';
                const visibleRows = rows.filter((row) => {
                    const matchesQuery = !query || textValue(row, 'filterText').includes(query);
                    const matchesKind = !kind || textValue(row, 'kind') === kind;
                    const matchesStatus = !status || textValue(row, 'status') === status;
                    const visible = matchesQuery && matchesKind && matchesStatus;
                    row.hidden = !visible;
                    return visible;
                });

                visibleRows.sort((left, right) => {
                    let comparison = 0;
                    if (numericFields.has(sortBy)) {
                        comparison = numericValue(left, sortBy) - numericValue(right, sortBy);
                    } else {
                        comparison = collator.compare(textValue(left, sortBy), textValue(right, sortBy));
                    }
                    if (comparison === 0) {
                        comparison = collator.compare(textValue(left, 'path'), textValue(right, 'path'));
                    }
                    return direction === 'desc' ? -comparison : comparison;
                });

                visibleRows.forEach((row) => tbody.appendChild(row));
                if (summary) {
                    summary.textContent = `${visibleRows.length} of ${rows.length} rows shown`;
                }
            };

            for (const element of [searchInput, kindSelect, statusSelect, sortBySelect, directionSelect]) {
                element?.addEventListener('input', applyTableState);
                element?.addEventListener('change', applyTableState);
            }
            resetButton?.addEventListener('click', () => {
                if (searchInput) {
                    searchInput.value = '';
                }
                if (kindSelect) {
                    kindSelect.value = '';
                }
                if (statusSelect) {
                    statusSelect.value = '';
                }
                if (sortBySelect) {
                    sortBySelect.value = 'path';
                }
                if (directionSelect) {
                    directionSelect.value = 'asc';
                }
                applyTableState();
            });

            applyTableState();
        })();
    </script>
    """


def _vscode_task_command_uri(task_label: str) -> str:
    return f"command:workbench.action.tasks.runTask?{quote(json.dumps([task_label]))}"


def _dashboard_actions(*, current_page_path: str) -> str:
    refresh_href = _vscode_task_command_uri(REFRESH_DASHBOARD_TASK)
    return (
        '<div class="dashboard-actions">'
        f'<a class="dashboard-action primary" href="{escape(refresh_href)}">Refresh dashboard</a>'
        f'<span class="dashboard-action-note">Runs the existing VS Code task to regenerate the dashboard artifacts.</span>'
        "</div>"
    )


def _page_links(*, main_page_path: str, ratchet_page_path: str, current_page: str) -> str:
    links = [
        (main_page_path, "Repo health", current_page == "main"),
        (ratchet_page_path, "Ratchet details", current_page == "ratchets"),
    ]
    rendered: list[str] = []
    for href, label, is_active in links:
        class_name = "page-link active" if is_active else "page-link"
        rendered.append(f'<a class="{class_name}" href="{escape(href)}">{escape(label)}</a>')
    return '<nav class="page-links">' + "".join(rendered) + "</nav>"


def _render_html(
    report: dict[str, Any], *, current_page_path: str = "repo-health.html", ratchet_page_path: str | None = None
) -> str:
    metrics = report.get("metrics", {}) if isinstance(report.get("metrics"), dict) else {}
    audit_status = report.get("audit_status", {}) if isinstance(report.get("audit_status"), dict) else {}
    context_status = report.get("context_status", {}) if isinstance(report.get("context_status"), dict) else {}
    branch_health = report.get("branch_health", {}) if isinstance(report.get("branch_health"), dict) else {}
    trend = report.get("trend_summary", {}) if isinstance(report.get("trend_summary"), dict) else {}
    handoffs = report.get("handoffs", {}) if isinstance(report.get("handoffs"), dict) else {}
    ratchets = report.get("ratchet_status", {}) if isinstance(report.get("ratchet_status"), dict) else {}
    coverage_ratchet = ratchets.get("coverage", {}) if isinstance(ratchets.get("coverage"), dict) else {}
    structural_ratchet = ratchets.get("structural", {}) if isinstance(ratchets.get("structural"), dict) else {}
    generated_at = str(report.get("generated_at", "n/a"))
    page_links = (
        _page_links(main_page_path="#", ratchet_page_path=ratchet_page_path, current_page="main")
        if ratchet_page_path
        else ""
    )
    dashboard_actions = _dashboard_actions(current_page_path=current_page_path)
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>SattLint Repo Health</title>
    <style>
        :root {{
            color-scheme: light dark;
            --bg: #0f1720;
            --panel: #16212e;
            --panel-alt: #1b2937;
            --border: #2a4156;
            --text: #edf4fb;
            --muted: #9fb3c8;
            --accent: #63d2ff;
            --ok: #4ad295;
            --warn: #f1c75b;
            --error: #ff7676;
            --shadow: 0 18px 45px rgba(0, 0, 0, 0.22);
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            min-height: 100vh;
            font-family: \"Segoe UI\", sans-serif;
            background: radial-gradient(circle at top left, rgba(99, 210, 255, 0.18), transparent 32%), linear-gradient(180deg, #0c141d 0%, var(--bg) 100%);
            color: var(--text);
        }}
        .dashboard-shell {{ width: min(1280px, calc(100vw - 32px)); margin: 0 auto; padding: 24px 0 40px; }}
        .card {{ background: linear-gradient(180deg, rgba(22, 33, 46, 0.96), rgba(22, 33, 46, 0.9)); border: 1px solid rgba(159, 179, 200, 0.14); border-radius: 20px; box-shadow: var(--shadow); padding: 22px; }}
        .page-links {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }}
        .page-link {{ display: inline-flex; align-items: center; justify-content: center; padding: 10px 14px; border-radius: 999px; border: 1px solid rgba(159, 179, 200, 0.18); color: var(--text); text-decoration: none; background: rgba(27, 41, 55, 0.82); }}
        .page-link.active {{ border-color: rgba(99, 210, 255, 0.5); color: var(--accent); }}
        .dashboard-actions {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px 12px; margin-bottom: 18px; }}
        .dashboard-action {{ display: inline-flex; align-items: center; justify-content: center; min-height: 42px; padding: 10px 14px; border-radius: 999px; border: 1px solid rgba(159, 179, 200, 0.18); color: var(--text); text-decoration: none; background: rgba(27, 41, 55, 0.82); }}
        .dashboard-action.primary {{ border-color: rgba(99, 210, 255, 0.42); color: var(--accent); }}
        .dashboard-action-note {{ color: var(--muted); font-size: 13px; }}
        .hero {{ display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(260px, 0.9fr); gap: 24px; align-items: start; margin-bottom: 22px; }}
        .eyebrow {{ margin-bottom: 10px; color: var(--accent); text-transform: uppercase; letter-spacing: 0.12em; font-size: 12px; }}
        h1, h2 {{ margin: 0; font-weight: 700; }}
        h1 {{ font-size: clamp(28px, 4vw, 40px); }}
        h2 {{ font-size: 18px; }}
        .hero-copy, .metric-detail, .list-card-meta, .empty-inline, .definitions dt {{ color: var(--muted); }}
        .hero-copy {{ margin: 12px 0 0; line-height: 1.5; }}
        .hero-statuses {{ display: grid; gap: 12px; min-width: 0; }}
        .pill {{ display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px 16px; padding: 12px 14px; border-radius: 14px; background: var(--panel-alt); border: 1px solid rgba(159, 179, 200, 0.12); min-width: 0; }}
        .pill.ok {{ border-color: rgba(74, 210, 149, 0.45); }}
        .pill.warn {{ border-color: rgba(241, 199, 91, 0.45); }}
        .pill.error {{ border-color: rgba(255, 118, 118, 0.45); }}
        .pill-copy {{ display: grid; gap: 4px; min-width: 0; flex: 1 1 180px; }}
        .pill-label, .pill-value, .pill-detail {{ min-width: 0; overflow-wrap: anywhere; word-break: break-word; }}
        .pill-detail {{ color: var(--muted); font-size: 12px; line-height: 1.4; }}
        .pill-value {{ font-weight: 700; text-transform: capitalize; text-align: right; }}
        .metrics-grid, .split-grid {{ display: grid; gap: 16px; margin-bottom: 22px; }}
        .metrics-grid {{ grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }}
        .metric-card {{ background: rgba(27, 41, 55, 0.9); border-radius: 18px; border: 1px solid rgba(159, 179, 200, 0.12); padding: 18px; }}
        .metric-label {{ color: var(--muted); margin-bottom: 10px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; }}
        .metric-value {{ font-size: 26px; font-weight: 700; margin-bottom: 8px; }}
        .split-grid {{ grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
        .section-header {{ margin-bottom: 16px; }}
        .definitions {{ margin: 0; display: grid; gap: 10px; }}
        .definition-row {{ display: grid; grid-template-columns: minmax(110px, 0.8fr) minmax(0, 1.2fr); gap: 12px; }}
        .definitions dt, .definitions dd {{ margin: 0; }}
        .definitions dd {{ text-align: right; }}
        .stack-list {{ display: grid; gap: 12px; }}
        .list-card {{ padding: 14px 16px; border-radius: 16px; background: rgba(27, 41, 55, 0.75); border: 1px solid rgba(159, 179, 200, 0.12); }}
        .list-card.compact {{ padding: 12px 14px; }}
        .warning-card {{ border-color: rgba(241, 199, 91, 0.28); }}
        .list-card-title {{ font-weight: 600; line-height: 1.4; }}
        .list-card-meta {{ margin-top: 6px; font-size: 13px; }}
        @media (max-width: 900px) {{
            .hero {{ grid-template-columns: 1fr; }}
            .definitions dd {{ text-align: left; }}
            .definition-row {{ grid-template-columns: 1fr; gap: 4px; }}
        }}
    </style>
</head>
<body>
    <main class=\"dashboard-shell\">
        {page_links}
        {dashboard_actions}
        <section class=\"hero card\">
            <div>
                <div class=\"eyebrow\">Workspace snapshot</div>
                <h1>SattLint Repo Health</h1>
                <p class=\"hero-copy\">Snapshot-backed view of audit, context, branch, and throughput health for this repository.</p>
                <dl class=\"definitions\">
                    {_definition_rows([("Generated", generated_at), ("Audit dir", str(report.get("audit_dir", "n/a"))), ("Status", str(report.get("status", "unknown")))])}
                </dl>
            </div>
            <div class=\"hero-statuses\">
                {_status_pill("Repo", str(report.get("status", "unknown")))}
                {_status_pill("Audit", str(audit_status.get("overall_status", "unknown")))}
                {_status_pill("Context", str(context_status.get("status", "unknown")))}
                {_status_pill("Coverage Ratchet", str(coverage_ratchet.get("status", "unknown")), detail=f"{_format_percent(coverage_ratchet.get('current_line_rate'))} current vs {_format_percent(coverage_ratchet.get('minimum_line_rate'))} floor")}
                {_status_pill("Structural Ratchet", str(structural_ratchet.get("status", "unknown")), detail=f"{_format_number(structural_ratchet.get('function_over_budget_count'))} functions, {_format_number(structural_ratchet.get('class_over_budget_count'))} classes, {_format_number(structural_ratchet.get('file_exception_count'))} exceptions")}
            </div>
        </section>
        <section class=\"metrics-grid\">
            {_metric_card(label="Audit findings", value=_format_number(metrics.get("finding_count")), detail=f"Blocking {_format_number(metrics.get('blocking_finding_count'))}")}
            {_metric_card(label="Coverage", value=_format_percent(metrics.get("coverage_total_line_rate")), detail=f"Minimum {_format_percent(metrics.get('coverage_min_line_rate'))}")}
            {_metric_card(label="Context budget", value=f"{_format_number(metrics.get('auto_loaded_context_lines'))}/{_format_number(metrics.get('context_auto_loaded_budget'))}", detail=f"{_format_number(metrics.get('scoped_context_file_count'))} scoped files")}
            {_metric_card(label="Quality checks", value=f"Ruff {_format_number(metrics.get('ruff_issue_count'))}", detail=f"Pyright {_format_number(metrics.get('pyright_error_count'))} errors / {_format_number(metrics.get('pyright_warning_count'))} warnings")}
            {_metric_card(label="Pytest runtime", value=(f"{float(metrics.get('test_runtime_seconds', 0.0)):.3f}s" if metrics.get("test_runtime_seconds") is not None else "n/a"), detail="Latest pipeline snapshot")}
            {_metric_card(label="AI throughput", value=_format_number(metrics.get("ai_task_throughput")), detail=("Merge success n/a" if handoffs.get("merge_success_rate") is None else f"Merge success {_format_percent(handoffs.get('merge_success_rate'))}"))}
            {_metric_card(label="Branch state", value=_format_number(metrics.get("dirty_files")), detail=f"Dirty files on {branch_health.get('branch', 'current branch')}")}
            {_metric_card(label="Largest file", value=_format_number(metrics.get("largest_file_lines")), detail=str(metrics.get("largest_file_path", "n/a")))}
            {_metric_card(label="Ratcheting", value=str(ratchets.get("overall_status", "unknown")), detail=f"Coverage {coverage_ratchet.get('status', 'unknown')} / Structural {structural_ratchet.get('status', 'unknown')}")}
        </section>
        <section class=\"split-grid\">
            <article class=\"card\">
                <div class=\"section-header\"><h2>Branch health</h2></div>
                <dl class=\"definitions\">{_definition_rows([("Branch", str(branch_health.get("branch", "n/a"))), ("Dirty files", _format_number(branch_health.get("dirty_files"))), ("Ahead by", _format_signed(branch_health.get("ahead_by"))), ("Behind by", _format_signed(branch_health.get("behind_by"))), ("Tracked worktrees", _format_number(branch_health.get("tracked_worktrees")))])}</dl>
            </article>
            <article class=\"card\">
                <div class=\"section-header\"><h2>Trend summary</h2></div>
                <dl class=\"definitions\">{_definition_rows([("History snapshots", _format_number(trend.get("history_count"))), ("Coverage delta", _format_signed(trend.get("coverage_delta"))), ("Finding delta", _format_signed(trend.get("finding_delta"))), ("Context delta", _format_signed(trend.get("context_delta"))), ("Largest file delta", _format_signed(trend.get("largest_file_delta")))])}</dl>
            </article>
            <article class=\"card\">
                <div class=\"section-header\"><h2>Context and audit</h2></div>
                <dl class=\"definitions\">{_definition_rows([("Audit severity", str(audit_status.get("max_severity", "n/a"))), ("Context issues", _format_number(context_status.get("issue_count"))), ("Root junk files", _format_number(metrics.get("root_junk_file_count"))), ("Structural over budget", f"{_format_number(metrics.get('function_over_budget_count'))} functions / {_format_number(metrics.get('class_over_budget_count'))} classes"), ("Handoffs", _format_number(handoffs.get("handoff_count")))])}</dl>
            </article>
            <article class=\"card\">
                <div class=\"section-header\"><h2>Ratchet status</h2></div>
                <dl class=\"definitions\">{_definition_rows([("Overall", str(ratchets.get("overall_status", "unknown"))), ("Coverage floor", f"{_format_percent(coverage_ratchet.get('current_line_rate'))} against {_format_percent(coverage_ratchet.get('minimum_line_rate'))}"), ("Structural budget", f"{_format_number(structural_ratchet.get('function_over_budget_count'))} functions / {_format_number(structural_ratchet.get('class_over_budget_count'))} classes"), ("Structural regression", "yes" if structural_ratchet.get("structural_budget_regression") else "no"), ("File exceptions", _format_number(structural_ratchet.get("file_exception_count")))])}</dl>
            </article>
            <article class=\"card\">
                <div class=\"section-header\"><h2>Top findings</h2></div>
                <div class=\"stack-list\">{_render_findings(report.get("top_findings", []))}</div>
            </article>
            <article class=\"card\">
                <div class=\"section-header\"><h2>Warnings</h2></div>
                <div class=\"stack-list\">{_render_warnings(report.get("warnings", []))}</div>
            </article>
            <article class=\"card\">
                <div class=\"section-header\"><h2>Largest files</h2></div>
                <div class=\"stack-list\">{_render_named_list(report.get("largest_files", []), empty_message="No largest-file data in the current snapshot.", title_key="path", primary_value_key="lines", secondary_value_key="kind", primary_suffix=" lines")}</div>
            </article>
            <article class=\"card\">
                <div class=\"section-header\"><h2>Slowest tests</h2></div>
                <div class=\"stack-list\">{_render_named_list(report.get("slowest_tests", []), empty_message="No slow-test data in the current snapshot.", title_key="name", primary_value_key="time_seconds", secondary_value_key="outcome", primary_suffix="s")}</div>
            </article>
        </section>
    </main>
</body>
</html>
"""


def _render_ratchet_html(
    report: dict[str, Any], *, current_page_path: str = "repo-health-ratchets.html", main_page_path: str
) -> str:
    ratchet_inventory = report.get("ratchet_inventory", {}) if isinstance(report.get("ratchet_inventory"), dict) else {}
    allow_lists = (
        ratchet_inventory.get("allow_lists", {}) if isinstance(ratchet_inventory.get("allow_lists"), dict) else {}
    )
    typing_allowlist = (
        allow_lists.get("typing_debt_allowlist", [])
        if isinstance(allow_lists.get("typing_debt_allowlist"), list)
        else []
    )
    structural_exceptions = (
        allow_lists.get("structural_file_exceptions", [])
        if isinstance(allow_lists.get("structural_file_exceptions"), list)
        else []
    )
    ratcheted_statuses = (
        ratchet_inventory.get("ratcheted_file_statuses", [])
        if isinstance(ratchet_inventory.get("ratcheted_file_statuses"), list)
        else []
    )
    ratchet_rows_missing_target = sum(
        1 for item in ratcheted_statuses if item.get("status") in {"below_target", "over_target", "allowlisted"}
    )
    page_links = _page_links(main_page_path=main_page_path, ratchet_page_path="#", current_page="ratchets")
    dashboard_actions = _dashboard_actions(current_page_path=current_page_path)
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>SattLint Ratchet Details</title>
    <style>
        :root {{
            color-scheme: light dark;
            --bg: #0f1720;
            --panel: #16212e;
            --panel-alt: #1b2937;
            --border: #2a4156;
            --text: #edf4fb;
            --muted: #9fb3c8;
            --accent: #63d2ff;
            --shadow: 0 18px 45px rgba(0, 0, 0, 0.22);
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            min-height: 100vh;
            font-family: "Segoe UI", sans-serif;
            background: radial-gradient(circle at top left, rgba(99, 210, 255, 0.16), transparent 30%), linear-gradient(180deg, #0c141d 0%, var(--bg) 100%);
            color: var(--text);
        }}
        .dashboard-shell {{ width: min(1380px, calc(100vw - 32px)); margin: 0 auto; padding: 24px 0 40px; }}
        .card {{ background: linear-gradient(180deg, rgba(22, 33, 46, 0.96), rgba(22, 33, 46, 0.9)); border: 1px solid rgba(159, 179, 200, 0.14); border-radius: 20px; box-shadow: var(--shadow); padding: 22px; margin-bottom: 18px; }}
        .page-links {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }}
        .page-link {{ display: inline-flex; align-items: center; justify-content: center; padding: 10px 14px; border-radius: 999px; border: 1px solid rgba(159, 179, 200, 0.18); color: var(--text); text-decoration: none; background: rgba(27, 41, 55, 0.82); }}
        .page-link.active {{ border-color: rgba(99, 210, 255, 0.5); color: var(--accent); }}
        .dashboard-actions {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px 12px; margin-bottom: 18px; }}
        .dashboard-action {{ display: inline-flex; align-items: center; justify-content: center; min-height: 42px; padding: 10px 14px; border-radius: 999px; border: 1px solid rgba(159, 179, 200, 0.18); color: var(--text); text-decoration: none; background: rgba(27, 41, 55, 0.82); }}
        .dashboard-action.primary {{ border-color: rgba(99, 210, 255, 0.42); color: var(--accent); }}
        .dashboard-action-note {{ color: var(--muted); font-size: 13px; }}
        .eyebrow {{ margin-bottom: 10px; color: var(--accent); text-transform: uppercase; letter-spacing: 0.12em; font-size: 12px; }}
        h1, h2 {{ margin: 0; font-weight: 700; }}
        h1 {{ font-size: clamp(28px, 4vw, 40px); }}
        h2 {{ font-size: 18px; margin-bottom: 14px; }}
        .hero-copy, .table-note {{ color: var(--muted); line-height: 1.5; }}
        .summary-grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin-top: 18px; }}
        .metric-card {{ background: rgba(27, 41, 55, 0.9); border-radius: 18px; border: 1px solid rgba(159, 179, 200, 0.12); padding: 18px; }}
        .metric-label {{ color: var(--muted); margin-bottom: 10px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; }}
        .metric-value {{ font-size: 26px; font-weight: 700; margin-bottom: 8px; }}
        .split-grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }}
        .table-toolbar {{ display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); margin-bottom: 16px; align-items: end; }}
        .table-control {{ display: grid; gap: 6px; color: var(--muted); font-size: 13px; }}
        .table-control span {{ text-transform: uppercase; letter-spacing: 0.08em; font-size: 11px; }}
        .search-control {{ min-width: 0; grid-column: span 2; }}
        .table-control input, .table-control select {{ min-height: 42px; border-radius: 12px; border: 1px solid rgba(159, 179, 200, 0.18); background: rgba(15, 23, 32, 0.92); color: var(--text); padding: 10px 12px; width: 100%; }}
        .table-reset {{ min-height: 42px; border-radius: 12px; border: 1px solid rgba(159, 179, 200, 0.18); background: rgba(27, 41, 55, 0.82); color: var(--text); padding: 10px 14px; cursor: pointer; }}
        .table-summary {{ color: var(--muted); font-size: 13px; align-self: center; }}
        .table-wrap {{ overflow-x: auto; border-radius: 16px; border: 1px solid rgba(159, 179, 200, 0.12); }}
        table {{ width: 100%; border-collapse: collapse; min-width: 760px; background: rgba(27, 41, 55, 0.5); }}
        th, td {{ padding: 12px 14px; text-align: left; vertical-align: top; border-bottom: 1px solid rgba(159, 179, 200, 0.08); overflow-wrap: anywhere; }}
        th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; background: rgba(15, 23, 32, 0.92); position: sticky; top: 0; }}
        @media (max-width: 900px) {{
            .dashboard-shell {{ width: min(100vw - 20px, 1380px); }}
            .search-control {{ grid-column: auto; }}
        }}
    </style>
</head>
<body>
    <main class=\"dashboard-shell\">
        {page_links}
        {dashboard_actions}
        <section class=\"card\">
            <div class=\"eyebrow\">Ratchets and allow-lists</div>
            <h1>SattLint Ratchet Details</h1>
            <p class=\"hero-copy\">Checked-in debt inventory from the ratchet artifacts and typing allow-list. This page lists allow-listed files and every per-file ratchet entry that still controls touch behavior.</p>
            <section class=\"summary-grid\">
                {_metric_card(label="Typing allow-list", value=_format_number(len(typing_allowlist)), detail="tool.sattlint.typing_ratchet.debt_allowlist")}
                {_metric_card(label="Structural exceptions", value=_format_number(len(structural_exceptions)), detail="structural_budget_ratchet.json")}
                {_metric_card(label="Ratcheted entries", value=_format_number(len(ratcheted_statuses)), detail="coverage, structural, and typing rows")}
                {_metric_card(label="Still missing target", value=_format_number(ratchet_rows_missing_target), detail="rows not fully cleared")}
            </section>
        </section>
        <section class=\"split-grid\">
            <article class=\"card\">
                <h2>Typing debt allow-list</h2>
                <div class=\"table-wrap\">
                    <table>
                        <thead><tr><th>Path</th></tr></thead>
                        <tbody>{_render_allow_list_rows(typing_allowlist, columns=("path",), empty_message="No typing debt allow-list entries.")}</tbody>
                    </table>
                </div>
            </article>
            <article class=\"card\">
                <h2>Structural file exceptions</h2>
                <div class=\"table-wrap\">
                    <table>
                        <thead><tr><th>Path</th><th>Max lines</th><th>Reason</th></tr></thead>
                        <tbody>{_render_allow_list_rows(structural_exceptions, columns=("path", "max_lines", "reason"), empty_message="No structural file exceptions.")}</tbody>
                    </table>
                </div>
            </article>
        </section>
        <section class=\"card\">
            <h2>Ratcheted file status</h2>
            {_render_ratcheted_table_controls()}
            <p class=\"table-note\">Each row is one per-file ratchet entry from the checked-in debt ledger. These controls apply only to the <strong>Ratcheted file status</strong> table below.</p>
            <div class=\"table-wrap\">
                <table id=\"ratcheted-status-table\">
                    <thead>
                        <tr>
                            <th>Path</th>
                            <th>Kind</th>
                            <th>Status</th>
                            <th>Current</th>
                            <th>Target</th>
                            <th>Gap</th>
                            <th>Touch rule</th>
                            <th>Reason</th>
                        </tr>
                    </thead>
                    <tbody>{_render_ratcheted_status_rows(ratcheted_statuses)}</tbody>
                </table>
            </div>
        </section>
    </main>
    {_render_ratcheted_table_script()}
</body>
</html>
"""


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build repository health outputs from SattLint audit artifacts.")
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR, help="Audit output directory to read.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero when repo health fails.")
    parser.add_argument("--json-output", type=Path, help="Write the JSON report to a file.")
    parser.add_argument("--markdown-output", type=Path, help="Write the Markdown report to a file.")
    parser.add_argument("--html-output", type=Path, help="Write the HTML dashboard to a file.")
    parser.add_argument("--history-output", type=Path, help="Write a snapshot into metrics/history or another file.")
    parser.add_argument("--stdout-json", action="store_true", help="Print the JSON report instead of the text summary.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    audit_dir = args.audit_dir if args.audit_dir.is_absolute() else REPO_ROOT / args.audit_dir
    try:
        report = build_report(audit_dir)
    except ReadinessError as error:
        print(f"Audit directory not ready: {audit_dir}: {error}", file=sys.stderr)
        return 1

    if args.json_output is not None:
        json_path = args.json_output if args.json_output.is_absolute() else REPO_ROOT / args.json_output
        _write_text(json_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.markdown_output is not None:
        markdown_path = args.markdown_output if args.markdown_output.is_absolute() else REPO_ROOT / args.markdown_output
        _write_text(markdown_path, _render_markdown(report))
    if args.html_output is not None:
        html_path = args.html_output if args.html_output.is_absolute() else REPO_ROOT / args.html_output
        ratchet_html_path = _ratchet_inventory_path(html_path)
        _write_text(
            html_path,
            _render_html(report, current_page_path=html_path.name, ratchet_page_path=ratchet_html_path.name),
        )
        _write_text(
            ratchet_html_path,
            _render_ratchet_html(
                report,
                current_page_path=ratchet_html_path.name,
                main_page_path=html_path.name,
            ),
        )
    if args.history_output is not None:
        history_path = args.history_output if args.history_output.is_absolute() else REPO_ROOT / args.history_output
        _write_text(history_path, json.dumps(report, indent=2, sort_keys=True) + "\n")

    if args.stdout_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        metrics = report["metrics"]
        print(f"Repository health: {report['status']}")
        print(f"Audit findings: {metrics['finding_count']}")
        print(f"Root junk files: {metrics['root_junk_file_count']}")
        print(f"Coverage: {metrics['coverage_total_line_rate']:.2%}")
        print(f"Context: {metrics['auto_loaded_context_lines']}/{metrics['context_auto_loaded_budget']} lines")
        print(f"Largest file: {metrics['largest_file_path']} ({metrics['largest_file_lines']} lines)")
        print(f"AI throughput: {metrics['ai_task_throughput']}")
        for warning in report.get("warnings", []):
            paths = ", ".join(str(path) for path in warning.get("paths", [])[:5])
            if len(warning.get("paths", [])) > 5:
                paths += ", ..."
            print(f"Warning: {warning['message']} {paths}".rstrip())

    return 1 if args.check and report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
