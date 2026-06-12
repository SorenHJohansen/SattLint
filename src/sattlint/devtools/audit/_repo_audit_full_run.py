"""Repo-audit selected-check execution helpers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from sattlint.contracts import FindingCollection
from sattlint.devtools.artifact_registry import AUDIT_ARTIFACTS, artifact_reports_map
from sattlint.devtools.progress_reporting import ProgressReporter
from sattlint.devtools.shared.pipeline_artifacts import write_json_artifact
from sattlint.path_sanitizer import sanitize_path_for_report


def _entrypoints_module() -> Any:
    from . import repo_audit_entrypoints as entrypoints_module  # noqa: PLC0415

    return entrypoints_module


def _run_repo_audit_findings_checks(
    output_dir: Path,
    *,
    profile: str,
    check_ids: Sequence[str],
    fail_on: str,
    include_generated: bool,
    suspicious_identifiers: Iterable[str],
    latest_output_dir: Path | None = None,
) -> dict[str, Any]:
    entrypoints_module = _entrypoints_module()
    repo_audit = entrypoints_module._repo_audit_module()
    output_dir.mkdir(parents=True, exist_ok=True)
    ai_gc_report = None
    sanitized_output_dir = sanitize_path_for_report(output_dir, repo_root=repo_audit.REPO_ROOT) or output_dir.as_posix()
    sanitized_latest_output_dir = (
        None
        if latest_output_dir is None
        else sanitize_path_for_report(latest_output_dir, repo_root=repo_audit.REPO_ROOT) or latest_output_dir.as_posix()
    )
    selected_checks = list(dict.fromkeys(check_ids))
    progress = ProgressReporter(
        kind="sattlint.repo_audit.progress",
        title="Repository audit",
        output_dir=output_dir,
        write_json=write_json_artifact,
        stages=[
            ("custom_scan", "Run repository-specific checks"),
            ("write_reports", "Write audit reports"),
        ],
        canonical_command=(
            "sattlint-repo-audit "
            f"--profile {profile} "
            f"{' '.join(f'--check {check_id}' for check_id in selected_checks)} "
            f"--skip-pipeline --fail-on {fail_on} --output-dir {sanitized_output_dir}"
        ),
    )
    progress.start_stage("custom_scan")
    findings = entrypoints_module.collect_custom_findings(
        repo_audit.REPO_ROOT,
        include_generated=include_generated,
        tracked_only=True,
        suspicious_identifiers=suspicious_identifiers,
        selected_checks=selected_checks,
    )
    progress.complete_stage("custom_scan", detail=f"{len(findings)} findings")
    blocking_count = entrypoints_module._blocking_finding_count(findings, fail_on)
    enabled_audit_artifact_ids = {"progress", "status", "summary", "findings", "summary_markdown", "run_history"}
    if "ai-gc" in selected_checks:
        ai_gc_report = repo_audit.build_ai_gc_report(repo_audit.REPO_ROOT)
        enabled_audit_artifact_ids.add("ai_gc")
    reports = artifact_reports_map(
        AUDIT_ARTIFACTS,
        profile=profile,
        enabled_artifact_ids=enabled_audit_artifact_ids,
    )
    reports["pipeline_status"] = None
    reports["pipeline_summary"] = None
    finding_collection = FindingCollection(tuple(finding.to_record() for finding in findings))
    overall_status_value = "fail" if blocking_count else "pass"
    summary = {
        "generated_by": "sattlint.devtools.audit.repo_audit_entrypoints",
        "output_dir": sanitized_output_dir,
        "profile": profile,
        "entry_report": "status.json",
        "canonical_command": progress.to_dict()["canonical_command"],
        "pipeline_ran": False,
        "pipeline_summary": None,
        "reports": reports,
        "finding_count": len(findings),
        "severity_counts": entrypoints_module._severity_counts(findings),
        "category_counts": entrypoints_module._category_counts(findings),
        "max_severity": entrypoints_module._max_severity(findings),
        "findings_schema": finding_collection.schema_metadata,
        "history_cleanup_findings": [finding.to_dict() for finding in findings if finding.history_cleanup_recommended],
        "findings": [finding.to_dict() for finding in findings],
        "selected_checks": selected_checks,
    }
    status_report = {
        "kind": "sattlint.repo_audit.status",
        "generated_by": "sattlint.devtools.audit.repo_audit_entrypoints",
        "profile": profile,
        "fail_on": fail_on,
        "overall_status": overall_status_value,
        "canonical_command": summary["canonical_command"],
        "status_report": f"{sanitized_output_dir}/status.json",
        "summary_report": f"{sanitized_output_dir}/summary.json",
        "progress_report": f"{sanitized_output_dir}/progress.json",
        "finding_count": summary["finding_count"],
        "blocking_finding_count": blocking_count,
        "max_severity": summary["max_severity"],
        "severity_counts": summary["severity_counts"],
        "category_counts": summary["category_counts"],
        "findings_schema": summary["findings_schema"],
        "pipeline_status_report": None,
        "latest_status_report": None
        if sanitized_latest_output_dir is None
        else f"{sanitized_latest_output_dir}/status.json",
        "latest_summary_report": None
        if sanitized_latest_output_dir is None
        else f"{sanitized_latest_output_dir}/summary.json",
        "top_findings": [
            {
                "id": finding.id,
                "severity": finding.severity,
                "path": finding.path,
                "line": finding.line,
                "message": finding.message,
            }
            for finding in findings[:5]
        ],
        "selected_checks": selected_checks,
    }
    progress.start_stage("write_reports")
    write_json_artifact(output_dir / "status.json", status_report)
    write_json_artifact(output_dir / "summary.json", summary)
    write_json_artifact(output_dir / "findings.json", finding_collection.to_dict())
    if ai_gc_report is not None:
        write_json_artifact(output_dir / "ai_gc.json", ai_gc_report)
    repo_audit._write_markdown(output_dir / "summary.md", findings, summary)
    repo_audit._write_audit_run_history(
        output_dir,
        latest_output_dir=latest_output_dir,
        report_kind="repo_audit_selected_check",
        primary_payload=summary,
        status_payload=status_report,
        summary_payload=summary,
    )
    progress.complete_stage("write_reports")
    progress.finalize(overall_status=overall_status_value)
    return summary


def _run_repo_audit_cli_consistency_check(
    output_dir: Path,
    *,
    fail_on: str,
    latest_output_dir: Path | None = None,
) -> dict[str, Any]:
    entrypoints_module = _entrypoints_module()
    repo_audit = entrypoints_module._repo_audit_module()
    output_dir.mkdir(parents=True, exist_ok=True)
    sanitized_output_dir = sanitize_path_for_report(output_dir, repo_root=repo_audit.REPO_ROOT) or output_dir.as_posix()
    sanitized_latest_output_dir = (
        None
        if latest_output_dir is None
        else sanitize_path_for_report(latest_output_dir, repo_root=repo_audit.REPO_ROOT) or latest_output_dir.as_posix()
    )
    progress = ProgressReporter(
        kind="sattlint.repo_audit.progress",
        title="Repository audit",
        output_dir=output_dir,
        write_json=write_json_artifact,
        stages=[
            ("custom_scan", "Build CLI consistency report"),
            ("write_reports", "Write audit reports"),
        ],
        canonical_command=(
            f"sattlint-repo-audit --profile full --check cli-consistency --skip-pipeline "
            f"--fail-on {fail_on} --output-dir {sanitized_output_dir}"
        ),
    )
    progress.start_stage("custom_scan")
    cli_consistency_report = repo_audit.build_cli_consistency_report(root=repo_audit.REPO_ROOT)
    findings = entrypoints_module._cli_consistency_findings(cli_consistency_report)
    progress.complete_stage("custom_scan", detail=f"{len(findings)} findings")
    blocking_count = entrypoints_module._blocking_finding_count(findings, fail_on)
    enabled_audit_artifact_ids = {
        "progress",
        "status",
        "summary",
        "findings",
        "summary_markdown",
        "run_history",
        "cli_consistency",
    }
    reports = artifact_reports_map(
        AUDIT_ARTIFACTS,
        profile="full",
        enabled_artifact_ids=enabled_audit_artifact_ids,
    )
    reports["pipeline_status"] = None
    reports["pipeline_summary"] = None
    finding_collection = FindingCollection(tuple(finding.to_record() for finding in findings))
    overall_status_value = "fail" if cli_consistency_report.get("status") == "fail" else "pass"
    summary = {
        "generated_by": "sattlint.devtools.audit.repo_audit_entrypoints",
        "output_dir": sanitized_output_dir,
        "profile": "full",
        "entry_report": "status.json",
        "canonical_command": progress.to_dict()["canonical_command"],
        "pipeline_ran": False,
        "pipeline_summary": None,
        "reports": reports,
        "finding_count": len(findings),
        "severity_counts": entrypoints_module._severity_counts(findings),
        "category_counts": entrypoints_module._category_counts(findings),
        "max_severity": entrypoints_module._max_severity(findings),
        "findings_schema": finding_collection.schema_metadata,
        "history_cleanup_findings": [],
        "findings": [finding.to_dict() for finding in findings],
        "selected_checks": ["cli-consistency"],
        "cli_consistency_status": cli_consistency_report.get("status"),
    }
    status_report = {
        "kind": "sattlint.repo_audit.status",
        "generated_by": "sattlint.devtools.audit.repo_audit_entrypoints",
        "profile": "full",
        "fail_on": fail_on,
        "overall_status": overall_status_value,
        "canonical_command": summary["canonical_command"],
        "status_report": f"{sanitized_output_dir}/status.json",
        "summary_report": f"{sanitized_output_dir}/summary.json",
        "progress_report": f"{sanitized_output_dir}/progress.json",
        "finding_count": summary["finding_count"],
        "blocking_finding_count": blocking_count,
        "max_severity": summary["max_severity"],
        "severity_counts": summary["severity_counts"],
        "category_counts": summary["category_counts"],
        "findings_schema": summary["findings_schema"],
        "pipeline_status_report": None,
        "latest_status_report": None
        if sanitized_latest_output_dir is None
        else f"{sanitized_latest_output_dir}/status.json",
        "latest_summary_report": None
        if sanitized_latest_output_dir is None
        else f"{sanitized_latest_output_dir}/summary.json",
        "top_findings": [
            {
                "id": finding.id,
                "severity": finding.severity,
                "path": finding.path,
                "line": finding.line,
                "message": finding.message,
            }
            for finding in findings[:5]
        ],
        "selected_checks": ["cli-consistency"],
        "cli_consistency_status": cli_consistency_report.get("status"),
    }
    progress.start_stage("write_reports")
    write_json_artifact(output_dir / "status.json", status_report)
    write_json_artifact(output_dir / "summary.json", summary)
    write_json_artifact(output_dir / "findings.json", finding_collection.to_dict())
    write_json_artifact(output_dir / "cli_consistency.json", cli_consistency_report)
    repo_audit._write_markdown(output_dir / "summary.md", findings, summary)
    repo_audit._write_audit_run_history(
        output_dir,
        latest_output_dir=latest_output_dir,
        report_kind="repo_audit_cli_consistency",
        primary_payload=summary,
        status_payload=status_report,
        summary_payload=summary,
    )
    progress.complete_stage("write_reports")
    progress.finalize(overall_status=overall_status_value)
    return summary


__all__ = [
    "_run_repo_audit_cli_consistency_check",
    "_run_repo_audit_findings_checks",
]
