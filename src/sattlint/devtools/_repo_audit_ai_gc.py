"""AI garbage-collection reporting helpers for repo audit."""

from __future__ import annotations

from typing import Any, cast

from .json_helpers import json_mapping as _json_mapping


def _repo_audit_ai_gc_module() -> Any:
    from sattlint.devtools import repo_audit as repo_audit_module  # noqa: PLC0415

    return repo_audit_module


def _ai_gc_report_findings(report: dict[str, Any]) -> list[Any]:
    repo_audit = _repo_audit_ai_gc_module()
    findings: list[Any] = []
    candidates = report.get("candidates")
    if not isinstance(candidates, list):
        return findings
    for candidate_obj in cast(list[object], candidates):
        candidate = _json_mapping(candidate_obj)
        if candidate is None:
            continue
        if candidate.get("applied"):
            continue
        candidate_id = str(candidate.get("candidate_id") or "ai-gc")
        path = candidate.get("path")
        age_days = candidate.get("age_days")
        severity = (
            "medium"
            if candidate_id == "stale-generated-output-manifest" or (isinstance(age_days, int) and age_days >= 30)
            else "low"
        )
        if candidate_id == "stale-generated-output-manifest":
            message = "Generated output drifted from its source-digest manifest."
            detail = str(candidate.get("reason") or "")
        else:
            message = "Stale AI-generated artifact can be collected."
            detail = (
                f"age_days={age_days} size_bytes={candidate.get('size_bytes', 0)}"
                if age_days is not None
                else str(candidate.get("reason") or "")
            )
        findings.append(
            repo_audit.Finding(
                id=candidate_id,
                category="maintenance",
                severity=severity,
                confidence="high",
                message=message,
                path=path,
                detail=detail,
                suggestion="Run sattlint-repo-audit --apply-ai-gc to delete safe stale artifacts.",
                source="ai-gc",
            )
        )
    return findings


def _is_active_output_ai_gc_path(path: str | None, *, output_dir_path: str | None) -> bool:
    if not path or not output_dir_path:
        return False
    return path.rstrip("/") == output_dir_path.rstrip("/")


def _filter_ai_gc_report_for_output_dir(report: dict[str, Any], *, output_dir_path: str | None) -> dict[str, Any]:
    candidates = report.get("candidates")
    if not isinstance(candidates, list):
        return report
    candidate_items = cast(list[object], candidates)
    filtered_candidates = [
        candidate_obj
        for candidate_obj in candidate_items
        if not (
            (candidate := _json_mapping(candidate_obj)) is not None
            and str(candidate.get("candidate_id") or "") == "stale-generated-output-manifest"
            and _is_active_output_ai_gc_path(
                str(candidate.get("path") or "") or None,
                output_dir_path=output_dir_path,
            )
        )
    ]
    if len(filtered_candidates) == len(candidate_items):
        return report
    filtered_report = dict(report)
    filtered_report["candidates"] = filtered_candidates
    filtered_summary = dict(_json_mapping(report.get("summary")) or {})
    filtered_summary["candidate_count"] = len(filtered_candidates)
    artifact_candidate_count = 0
    manifest_drift_candidate_count = 0
    for candidate_obj in filtered_candidates:
        candidate = _json_mapping(candidate_obj)
        if candidate is None:
            continue
        candidate_id = str(candidate.get("candidate_id") or "")
        if candidate_id in {"stale-ai-artifact", "stale-generated-output-manifest"}:
            artifact_candidate_count += 1
        if candidate_id == "stale-generated-output-manifest":
            manifest_drift_candidate_count += 1
    filtered_summary["artifact_candidate_count"] = artifact_candidate_count
    filtered_summary["manifest_drift_candidate_count"] = manifest_drift_candidate_count
    filtered_report["summary"] = filtered_summary
    failures = filtered_report.get("failures")
    filtered_report["status"] = (
        "fail"
        if isinstance(failures, list) and failures
        else "needs-attention"
        if filtered_candidates and filtered_report.get("mode") != "apply"
        else "pass"
    )
    return filtered_report


def _filter_ai_gc_findings_for_output_dir(findings: list[Any], *, output_dir_path: str | None) -> list[Any]:
    return [
        finding
        for finding in findings
        if not (
            finding.source == "ai-gc"
            and finding.id == "stale-generated-output-manifest"
            and _is_active_output_ai_gc_path(finding.path, output_dir_path=output_dir_path)
        )
    ]


__all__ = [
    "_ai_gc_report_findings",
    "_filter_ai_gc_findings_for_output_dir",
    "_filter_ai_gc_report_for_output_dir",
    "_is_active_output_ai_gc_path",
]
