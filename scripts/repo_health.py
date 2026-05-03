from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import context_health

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_DIR = REPO_ROOT / "artifacts" / "audit"
DEFAULT_COVERAGE_RATCHET = REPO_ROOT / "artifacts" / "analysis" / "coverage_ratchet.json"
DEFAULT_STRUCTURAL_RATCHET = REPO_ROOT / "artifacts" / "analysis" / "structural_budget_ratchet.json"
DEFAULT_HISTORY_DIR = REPO_ROOT / "metrics" / "history"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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


def _count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())


def _largest_files(limit: int = 10) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for rel_path in _tracked_files():
        path = REPO_ROOT / rel_path
        if not path.is_file():
            continue
        suffix = path.suffix.casefold()
        if suffix not in {".py", ".md", ".json", ".toml", ".yml", ".yaml"}:
            continue
        entries.append(
            {
                "path": rel_path,
                "lines": _count_lines(path),
                "kind": ("test" if rel_path.startswith("tests/") else "markdown" if suffix == ".md" else "source"),
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


def build_report(audit_dir: Path) -> dict[str, Any]:
    audit_status = _read_json(audit_dir / "status.json")
    audit_summary = _read_json(audit_dir / "summary.json")
    ruff_report = _read_json(audit_dir / "pipeline" / "ruff.json")
    pyright_report = _read_json(audit_dir / "pipeline" / "pyright.json")
    pytest_report = _read_json(audit_dir / "pipeline" / "pytest.json")
    coverage_ratchet = _read_json(DEFAULT_COVERAGE_RATCHET)
    structural_ratchet = _read_json(DEFAULT_STRUCTURAL_RATCHET)
    context_report = context_health.build_report()

    largest_files = _largest_files()
    slowest_tests = _slowest_tests(pytest_report)
    branch_health = _branch_health()
    handoffs = _handoff_metrics()

    audit_overall_status = str(audit_status.get("overall_status", "unknown"))
    context_status = str(context_report.get("status", "fail"))
    status = "pass" if audit_overall_status == "pass" and context_status == "pass" else "fail"
    if status == "pass" and int(audit_status.get("finding_count", 0)) > 0:
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
        "markdown_file_max_lines": int(structural_metrics.get("markdown_file_max_lines", 0)),
        "largest_file_lines": int(largest_files[0]["lines"]) if largest_files else 0,
        "largest_file_path": str(largest_files[0]["path"]) if largest_files else None,
        "ai_task_throughput": int(handoffs.get("ai_task_throughput", 0)),
        "merge_success_rate": handoffs.get("merge_success_rate"),
        "dirty_files": branch_health.get("dirty_files"),
    }

    history = _history_snapshots()
    trend_summary = _trend_metrics(metrics, history)

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
        "top_findings": audit_summary.get("findings", [])[:10],
        "largest_files": largest_files,
        "slowest_tests": slowest_tests,
        "technical_debt_indicators": {
            "structural_budget_regression": any(
                isinstance(finding, dict) and finding.get("id") == "structural-budget-ratchet-regression"
                for finding in audit_summary.get("findings", [])
            ),
            "medium_or_higher_findings": int(audit_status.get("finding_count", 0)),
            "file_exception_count": len(structural_ratchet.get("file_line_exceptions", {})),
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
    lines.extend(["", "## Trend Summary", ""])
    trend = report["trend_summary"]
    lines.append(f"- History snapshots: {trend['history_count']}")
    lines.append(f"- Coverage delta: {trend['coverage_delta']}")
    lines.append(f"- Finding delta: {trend['finding_delta']}")
    lines.append(f"- Context delta: {trend['context_delta']}")
    lines.append(f"- Largest file delta: {trend['largest_file_delta']}")
    lines.append("")
    return "\n".join(lines)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build repository health outputs from SattLint audit artifacts.")
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR, help="Audit output directory to read.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero when repo health fails.")
    parser.add_argument("--json-output", type=Path, help="Write the JSON report to a file.")
    parser.add_argument("--markdown-output", type=Path, help="Write the Markdown report to a file.")
    parser.add_argument("--history-output", type=Path, help="Write a snapshot into metrics/history or another file.")
    parser.add_argument("--stdout-json", action="store_true", help="Print the JSON report instead of the text summary.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    audit_dir = args.audit_dir if args.audit_dir.is_absolute() else REPO_ROOT / args.audit_dir
    report = build_report(audit_dir)

    if args.json_output is not None:
        json_path = args.json_output if args.json_output.is_absolute() else REPO_ROOT / args.json_output
        _write_text(json_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.markdown_output is not None:
        markdown_path = args.markdown_output if args.markdown_output.is_absolute() else REPO_ROOT / args.markdown_output
        _write_text(markdown_path, _render_markdown(report))
    if args.history_output is not None:
        history_path = args.history_output if args.history_output.is_absolute() else REPO_ROOT / args.history_output
        _write_text(history_path, json.dumps(report, indent=2, sort_keys=True) + "\n")

    if args.stdout_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        metrics = report["metrics"]
        print(f"Repository health: {report['status']}")
        print(f"Audit findings: {metrics['finding_count']}")
        print(f"Coverage: {metrics['coverage_total_line_rate']:.2%}")
        print(f"Context: {metrics['auto_loaded_context_lines']}/{metrics['context_auto_loaded_budget']} lines")
        print(f"Largest file: {metrics['largest_file_path']} ({metrics['largest_file_lines']} lines)")
        print(f"AI throughput: {metrics['ai_task_throughput']}")

    return 1 if args.check and report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
