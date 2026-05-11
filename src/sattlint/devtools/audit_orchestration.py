"""Repo-audit orchestration helpers for harness freshness and report generation."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any


def doc_gardener_finding_to_repo_audit(finding: Any, *, finding_factory: Callable[..., Any]) -> Any:
    return finding_factory(
        id=f"harness-{str(finding.category).replace('_', '-')}",
        category="harness-freshness",
        severity=str(finding.severity).casefold(),
        confidence="high",
        message=str(finding.message),
        path=str(finding.file) or None,
        line=None if int(getattr(finding, "line", 0)) <= 0 else int(finding.line),
        source="harness-freshness",
    )


def ai_harness_issue_to_finding(issue: dict[str, Any], *, finding_factory: Callable[..., Any]) -> Any:
    issue_id = str(issue.get("issue_id", "ai-harness-issue")).strip() or "ai-harness-issue"
    return finding_factory(
        id=f"harness-{issue_id}",
        category="harness-freshness",
        severity=str(issue.get("severity", "high")).casefold(),
        confidence="high",
        message=str(issue.get("message", "AI harness freshness issue.")),
        path=str(issue.get("path", "")).strip() or None,
        detail=json.dumps(issue, sort_keys=True),
        source="harness-freshness",
    )


def run_harness_freshness_check(
    context: Any,
    *,
    verify_ai_harness_freshness_fn: Callable[..., dict[str, Any]],
    patch_doc_gardener_paths_fn: Callable[[Path], Any],
    doc_gardener_module: Any,
    ai_harness_issue_to_finding_fn: Callable[[dict[str, Any]], Any],
    doc_gardener_finding_to_repo_audit_fn: Callable[[Any], Any],
    harness_freshness_doc_scanners: tuple[str, ...],
) -> list[Any]:
    findings = [
        ai_harness_issue_to_finding_fn(issue)
        for issue in verify_ai_harness_freshness_fn(
            repo_root=context.root,
            output_path=context.root / ".github" / "skills" / "validation-routing" / "references" / "ai-work-map.json",
            session_output_path=context.root
            / ".github"
            / "skills"
            / "validation-routing"
            / "references"
            / "ai-session-context-map.json",
        )["issues"]
    ]
    with patch_doc_gardener_paths_fn(context.root):
        for scanner_name in harness_freshness_doc_scanners:
            findings.extend(
                doc_gardener_finding_to_repo_audit_fn(finding)
                for finding in getattr(doc_gardener_module, scanner_name)()
            )
    return findings


def audit_repository(
    output_dir: Path,
    *,
    profile: str,
    fail_on: str,
    include_generated: bool,
    leaks_only: bool,
    suspicious_identifiers: Iterable[str],
    skip_pipeline: bool,
    skip_vulture: bool,
    skip_bandit: bool,
    latest_output_dir: Path | None,
    repo_root: Path,
    pipeline_output_dirname: str,
    sanitize_path_for_report_fn: Callable[[Path], str | None],
    progress_reporter_factory: Callable[..., Any],
    recommended_command_fn: Callable[..., str],
    default_corpus_manifest_dir_fn: Callable[[], Path | None],
    pipeline_module: Any,
    find_pipeline_findings_fn: Callable[[Path], list[Any]],
    collect_custom_findings_fn: Callable[..., list[Any]],
    filter_ai_gc_findings_for_output_dir_fn: Callable[..., list[Any]],
    filter_ai_gc_report_for_output_dir_fn: Callable[..., dict[str, Any]],
    build_ai_gc_report_fn: Callable[..., dict[str, Any]],
    dedupe_findings_fn: Callable[[Iterable[Any]], list[Any]],
    is_leak_finding_fn: Callable[[Any], bool],
    severity_rank: dict[str, int],
    blocking_finding_count_fn: Callable[[list[Any], str], int],
    severity_counts_fn: Callable[[list[Any]], dict[str, int]],
    category_counts_fn: Callable[[list[Any]], dict[str, int]],
    max_severity_fn: Callable[[list[Any]], str | None],
    artifact_reports_map_fn: Callable[..., dict[str, str | None]],
    audit_artifacts: Any,
    finding_collection_factory: Callable[[tuple[Any, ...]], Any],
    write_json_artifact_fn: Callable[[Path, dict[str, Any]], None],
    ai_gc_report_filename: str,
    write_markdown_fn: Callable[[Path, list[Any], dict[str, Any]], None],
    build_cli_consistency_report_fn: Callable[..., dict[str, Any]],
    write_audit_run_history_fn: Callable[..., dict[str, Any]],
    mirror_latest_reports_fn: Callable[[Path, Path | None], None],
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ai_gc_report: dict[str, Any] | None = None
    pipeline_summary: dict[str, Any] | None = None
    pipeline_findings: list[Any] = []
    audit_profile = "leaks" if leaks_only else profile
    sanitized_output_dir = sanitize_path_for_report_fn(output_dir) or output_dir.as_posix()
    sanitized_latest_output_dir = (
        None
        if latest_output_dir is None
        else sanitize_path_for_report_fn(latest_output_dir) or latest_output_dir.as_posix()
    )
    progress = progress_reporter_factory(
        kind="sattlint.repo_audit.progress",
        title="Repository audit",
        output_dir=output_dir,
        write_json=write_json_artifact_fn,
        stages=[
            ("pipeline", "Run shared pipeline"),
            ("custom_scan", "Run repository-specific checks"),
            ("merge_findings", "Merge and normalize findings"),
            ("write_reports", "Write audit reports"),
        ],
        canonical_command=recommended_command_fn(
            output_dir=sanitized_output_dir,
            profile=profile,
            fail_on=fail_on,
            leaks_only=leaks_only,
        ),
    )
    if not skip_pipeline and not leaks_only:
        pipeline_output_dir = output_dir / pipeline_output_dirname
        corpus_manifest_dir = default_corpus_manifest_dir_fn()
        progress.start_stage("pipeline")
        pipeline_summary = pipeline_module._run_pipeline(
            pipeline_output_dir,
            trace_target=pipeline_module.DEFAULT_TRACE_TARGET
            if pipeline_module.DEFAULT_TRACE_TARGET.exists()
            else None,
            profile=profile,
            include_vulture=False if skip_vulture else None,
            include_bandit=False if skip_bandit else None,
            corpus_manifest_dir=corpus_manifest_dir,
        )
        pipeline_findings = find_pipeline_findings_fn(pipeline_output_dir)
        progress.complete_stage("pipeline", detail=f"{len(pipeline_findings)} pipeline findings")
    else:
        progress.skip_stage("pipeline", detail="skipped by flags" if skip_pipeline or leaks_only else None)

    progress.start_stage("custom_scan")
    custom_findings = collect_custom_findings_fn(
        repo_root,
        include_generated=(include_generated or leaks_only),
        tracked_only=True,
        suspicious_identifiers=suspicious_identifiers,
    )
    custom_findings = filter_ai_gc_findings_for_output_dir_fn(custom_findings, output_dir_path=sanitized_output_dir)
    if not leaks_only:
        ai_gc_report = filter_ai_gc_report_for_output_dir_fn(
            build_ai_gc_report_fn(repo_root),
            output_dir_path=sanitized_output_dir,
        )
    progress.complete_stage("custom_scan", detail=f"{len(custom_findings)} custom findings")
    progress.start_stage("merge_findings")
    findings = dedupe_findings_fn([*pipeline_findings, *custom_findings])
    if leaks_only:
        findings = [finding for finding in findings if is_leak_finding_fn(finding)]
    findings = sorted(
        findings,
        key=lambda item: (-severity_rank[item.severity], item.category, item.path or "", item.line or 0, item.id),
    )
    blocking_count = blocking_finding_count_fn(findings, fail_on)
    enabled_audit_artifact_ids = {"progress", "status", "summary", "findings", "summary_markdown", "run_history"}
    if audit_profile == "full":
        enabled_audit_artifact_ids.add("cli_consistency")
    if ai_gc_report is not None:
        enabled_audit_artifact_ids.add("ai_gc")
    reports = artifact_reports_map_fn(
        audit_artifacts, profile=audit_profile, enabled_artifact_ids=enabled_audit_artifact_ids
    )
    progress.complete_stage("merge_findings", detail=f"{len(findings)} total findings")
    reports["pipeline_status"] = None if pipeline_summary is None else f"{pipeline_output_dirname}/status.json"
    reports["pipeline_summary"] = None if pipeline_summary is None else f"{pipeline_output_dirname}/summary.json"
    finding_collection = finding_collection_factory(tuple(finding.to_record() for finding in findings))
    overall_status_value = "fail" if blocking_count else "pass"
    summary = {
        "generated_by": "sattlint.devtools.repo_audit",
        "output_dir": sanitized_output_dir,
        "profile": audit_profile,
        "entry_report": "status.json",
        "canonical_command": recommended_command_fn(
            output_dir=sanitized_output_dir,
            profile=profile,
            fail_on=fail_on,
            leaks_only=leaks_only,
        ),
        "pipeline_ran": (not skip_pipeline and not leaks_only),
        "pipeline_summary": pipeline_summary,
        "reports": reports,
        "finding_count": len(findings),
        "severity_counts": severity_counts_fn(findings),
        "category_counts": category_counts_fn(findings),
        "max_severity": max_severity_fn(findings),
        "findings_schema": finding_collection.schema_metadata,
        "history_cleanup_findings": [finding.to_dict() for finding in findings if finding.history_cleanup_recommended],
        "findings": [finding.to_dict() for finding in findings],
    }
    status_report = {
        "kind": "sattlint.repo_audit.status",
        "generated_by": "sattlint.devtools.repo_audit",
        "profile": audit_profile,
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
        "pipeline_status_report": None
        if pipeline_summary is None
        else f"{sanitized_output_dir}/{pipeline_output_dirname}/status.json",
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
    }
    progress.start_stage("write_reports")
    write_json_artifact_fn(output_dir / "status.json", status_report)
    write_json_artifact_fn(output_dir / "summary.json", summary)
    write_json_artifact_fn(output_dir / "findings.json", finding_collection.to_dict())
    if ai_gc_report is not None:
        write_json_artifact_fn(output_dir / ai_gc_report_filename, ai_gc_report)
    write_markdown_fn(output_dir / "summary.md", findings, summary)
    if audit_profile == "full":
        cli_consistency_report = build_cli_consistency_report_fn(root=repo_root)
        write_json_artifact_fn(output_dir / "cli_consistency.json", cli_consistency_report)
    write_audit_run_history_fn(
        output_dir,
        latest_output_dir=latest_output_dir,
        report_kind="repo_audit",
        primary_payload=summary,
        status_payload=status_report,
        summary_payload=summary,
    )
    mirror_latest_reports_fn(output_dir, latest_output_dir)
    progress.complete_stage("write_reports")
    progress.finalize(overall_status=overall_status_value)
    return summary
