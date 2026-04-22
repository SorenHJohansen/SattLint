"""Helpers for building pipeline status and summary reports."""

from __future__ import annotations

from typing import Any


def build_tool_status(
    *,
    status: str,
    report: str | None,
    raw_exit_code: int | None,
    normalized_exit_code: int | None,
    finding_count: int = 0,
    note_count: int = 0,
    detail: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "report": report,
        "raw_exit_code": raw_exit_code,
        "normalized_exit_code": normalized_exit_code,
        "finding_count": finding_count,
    }
    if note_count:
        payload["note_count"] = note_count
    if detail:
        payload["detail"] = detail
    return payload


def overall_status(tool_statuses: dict[str, dict[str, Any]]) -> str:
    statuses = [payload["status"] for payload in tool_statuses.values()]
    if any(status == "fail" for status in statuses):
        return "fail"
    if any(status == "pass_with_notes" for status in statuses):
        return "pass_with_notes"
    return "pass"


def build_pipeline_status_report(
    *,
    profile: str,
    sanitized_output_dir: str,
    overall_status_value: str,
    tool_statuses: dict[str, dict[str, Any]],
    failing_tools: list[str],
    non_blocking_tools: list[str],
    progress_report: str | None = None,
    findings_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical_command = (
        f"sattlint-analysis-pipeline --profile {profile} --output-dir {sanitized_output_dir}"
    )
    payload = {
        "kind": "sattlint.pipeline.status",
        "profile": profile,
        "overall_status": overall_status_value,
        "canonical_command": canonical_command,
        "status_report": f"{sanitized_output_dir}/status.json",
        "summary_report": f"{sanitized_output_dir}/summary.json",
        "tool_statuses": tool_statuses,
        "failing_tools": failing_tools,
        "non_blocking_tools": non_blocking_tools,
    }
    if progress_report is not None:
        payload["progress_report"] = progress_report
    if findings_schema is not None:
        payload["findings_schema"] = findings_schema
    return payload


def build_pipeline_summary_report(
    *,
    profile: str,
    sanitized_output_dir: str,
    reports: dict[str, str | None],
    overall_status_value: str,
    tool_statuses: dict[str, dict[str, Any]],
    failing_tools: list[str],
    non_blocking_tools: list[str],
    tool_exit_codes: dict[str, int | None],
    artifact_registry_report: dict[str, Any],
    counts: dict[str, Any],
    progress_report: str | None = None,
    findings_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical_command = (
        f"sattlint-analysis-pipeline --profile {profile} --output-dir {sanitized_output_dir}"
    )
    status_payload: dict[str, Any] = {
        "overall_status": overall_status_value,
        "tool_statuses": tool_statuses,
        "failing_tools": failing_tools,
        "non_blocking_tools": non_blocking_tools,
    }
    for tool_name, exit_code in tool_exit_codes.items():
        status_payload[f"{tool_name}_exit_code"] = exit_code

    payload = {
        "output_dir": sanitized_output_dir,
        "profile": profile,
        "entry_report": "status.json",
        "canonical_command": canonical_command,
        "reports": reports,
        "status": status_payload,
        "artifact_registry": artifact_registry_report,
        "counts": counts,
    }
    if progress_report is not None:
        payload["progress_report"] = progress_report
    if findings_schema is not None:
        payload["findings_schema"] = findings_schema
    return payload


__all__ = [
    "build_pipeline_status_report",
    "build_pipeline_summary_report",
    "build_tool_status",
    "overall_status",
]
