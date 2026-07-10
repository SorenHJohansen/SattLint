from __future__ import annotations

from typing import Any


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


def render_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# Repository Health",
        "",
        f"- Status: {report['status']}",
        f"- Generated: {report['generated_at']}",
        f"- Audit dir: {report['audit_dir']}",
        f"- Audit findings: {metrics['finding_count']} (blocking: {metrics['blocking_finding_count']})",
        f"- Coverage: {metrics['coverage_total_line_rate']:.2%} minimum {metrics['coverage_min_line_rate']:.2%}",
        f"- Context: {metrics['auto_loaded_context_lines']}/{metrics['context_auto_loaded_budget']} auto-loaded lines",
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
        f"- Pyright: {metrics['pyright_error_count']} errors, {metrics['pyright_warning_count']} warnings",
        f"- Pytest runtime: {metrics['test_runtime_seconds']} seconds",
        "- Structural budget: "
        f"{metrics['function_over_budget_count']} functions, {metrics['class_over_budget_count']} classes over budget",
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
