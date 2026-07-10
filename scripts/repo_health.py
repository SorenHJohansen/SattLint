from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import context_health

try:
    from scripts import _repo_health_html_pages as repo_health_html_pages
    from scripts import _repo_health_markdown as repo_health_markdown
    from scripts import _repo_health_metrics as repo_health_metrics
    from scripts._repo_paths import repo_root_from
except ModuleNotFoundError:  # pragma: no cover - direct script execution resolves from scripts/
    import _repo_health_html_pages as repo_health_html_pages
    import _repo_health_markdown as repo_health_markdown
    import _repo_health_metrics as repo_health_metrics
    from _repo_paths import repo_root_from

from sattlint.devtools.artifact_readiness import ReadinessError, assert_artifact_dir_ready

REPO_ROOT = repo_root_from(Path(__file__))
DEFAULT_AUDIT_DIR = REPO_ROOT / "artifacts" / "audit"
DEFAULT_COVERAGE_RATCHET = REPO_ROOT / "artifacts" / "analysis" / "coverage_ratchet.json"
DEFAULT_STRUCTURAL_RATCHET = REPO_ROOT / "artifacts" / "analysis" / "structural_budget_ratchet.json"
DEFAULT_FILE_DEBT_RATCHET = REPO_ROOT / "artifacts" / "analysis" / "file_debt_ratchet.json"
DEFAULT_HISTORY_DIR = REPO_ROOT / "metrics" / "history"
REFRESH_DASHBOARD_TASK = "Metrics: Refresh Repo Health Dashboard"
_read_json = repo_health_metrics.read_json
_read_json_optional = repo_health_metrics.read_json_optional
_read_toml_optional = repo_health_metrics.read_toml_optional
_build_ratchet_status = repo_health_metrics.build_ratchet_status
_build_ratchet_inventory = repo_health_metrics.build_ratchet_inventory
_render_markdown = repo_health_markdown.render_markdown
_write_text = repo_health_metrics.write_text


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
    return repo_health_metrics.root_git_status_map(REPO_ROOT, _git)


def _looks_like_root_junk(name: str) -> bool:
    return repo_health_metrics.looks_like_root_junk(name)


def _root_junk_candidates() -> list[dict[str, str]]:
    return repo_health_metrics.build_root_junk_candidates(REPO_ROOT, _tracked_files(), _git)


def _count_lines(path: Path) -> int:
    return repo_health_metrics.count_lines(path)


def _largest_file_kind(rel_path: str) -> str | None:
    return repo_health_metrics.largest_file_kind(rel_path)


def _largest_files(limit: int = 10) -> list[dict[str, Any]]:
    return repo_health_metrics.largest_files(REPO_ROOT, _tracked_files(), limit=limit)


def _slowest_tests(pytest_report: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    return repo_health_metrics.slowest_tests(pytest_report, limit=limit)


def _branch_health() -> dict[str, Any]:
    return repo_health_metrics.branch_health(REPO_ROOT, _git)


def _handoff_files() -> list[Path]:
    return repo_health_metrics.handoff_files(REPO_ROOT)


def _handoff_metrics() -> dict[str, Any]:
    return repo_health_metrics.handoff_metrics(REPO_ROOT)


def _history_snapshots(limit: int = 20) -> list[dict[str, Any]]:
    return repo_health_metrics.history_snapshots(REPO_ROOT, DEFAULT_HISTORY_DIR, limit=limit)


def _trend_metrics(current_metrics: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    return repo_health_metrics.trend_metrics(current_metrics, history)


def build_report(audit_dir: Path) -> dict[str, Any]:
    assert_artifact_dir_ready(audit_dir)
    audit_status = _read_json(audit_dir / "status.json")
    audit_summary = _read_json(audit_dir / "summary.json")
    ruff_report = _read_json_optional(audit_dir / "pipeline" / "ruff.json") or {}
    pyright_report = _read_json_optional(audit_dir / "pipeline" / "pyright.json") or {}
    pytest_report = _read_json_optional(audit_dir / "pipeline" / "pytest.json") or {}
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
        "coverage_total_line_rate": round(repo_health_metrics.safe_float(coverage_summary.get("total_line_rate")), 4),
        "coverage_min_line_rate": round(
            repo_health_metrics.safe_float(coverage_ratchet.get("metrics", {}).get("min_line_rate_basis_points", 0))
            / 10000,
            4,
        ),
        "ruff_issue_count": int(ruff_report.get("finding_count", 0)),
        "pyright_error_count": int(pyright_report.get("error_count", 0)),
        "pyright_warning_count": int(pyright_report.get("warning_count", 0)),
        "test_runtime_seconds": round(repo_health_metrics.safe_float(pytest_report.get("duration_seconds")), 3),
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


def _ratchet_inventory_path(main_html_path: Path) -> Path:
    return repo_health_html_pages.ratchet_inventory_path(main_html_path)


def _render_html(
    report: dict[str, Any], *, current_page_path: str = "repo-health.html", ratchet_page_path: str | None = None
) -> str:
    return repo_health_html_pages.render_html(
        report,
        current_page_path=current_page_path,
        ratchet_page_path=ratchet_page_path,
        refresh_dashboard_task=REFRESH_DASHBOARD_TASK,
    )


def _render_ratchet_html(
    report: dict[str, Any], *, current_page_path: str = "repo-health-ratchets.html", main_page_path: str
) -> str:
    return repo_health_html_pages.render_ratchet_html(
        report,
        current_page_path=current_page_path,
        main_page_path=main_page_path,
        refresh_dashboard_task=REFRESH_DASHBOARD_TASK,
    )


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

    output_error: OSError | None = None
    try:
        if args.json_output is not None:
            json_path = args.json_output if args.json_output.is_absolute() else REPO_ROOT / args.json_output
            _write_text(json_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        if args.markdown_output is not None:
            markdown_path = (
                args.markdown_output if args.markdown_output.is_absolute() else REPO_ROOT / args.markdown_output
            )
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
    except OSError as error:
        output_error = error

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

    if output_error is not None:
        print(f"repo health output error: {output_error}", file=sys.stderr, flush=True)
        return 1

    return 1 if args.check and report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
