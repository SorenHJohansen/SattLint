"""Repo-audit recommended-run helpers."""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from sattlint.contracts import FindingCollection
from sattlint.devtools import pipeline as pipeline_module
from sattlint.devtools._pipeline_finish_gate import execute_finish_gate_steps, summarize_finish_gate_timing
from sattlint.devtools.artifact_registry import AUDIT_ARTIFACTS, artifact_reports_map
from sattlint.devtools.pipeline_artifacts import write_json_artifact
from sattlint.devtools.progress_reporting import ProgressReporter
from sattlint.path_sanitizer import sanitize_path_for_report

RECOMMENDED_REPO_AUDIT_MAX_WORKERS = 2


def _entrypoints_module() -> Any:
    from sattlint.devtools import repo_audit_entrypoints as entrypoints_module

    return entrypoints_module


def _normalize_repo_relative_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def _finding_matches_changed_files(finding: Any, changed_files: list[str]) -> bool:
    finding_path = getattr(finding, "path", None)
    if not isinstance(finding_path, str) or not finding_path.strip():
        return True

    normalized_path = _normalize_repo_relative_path(finding_path)
    return bool(
        _entrypoints_module().matching_changed_files(
            changed_files,
            [normalized_path, f"{normalized_path}/**"],
        )
    )


def _filter_custom_findings_to_changed_files(findings: list[Any], changed_files: list[str]) -> list[Any]:
    if not changed_files:
        return findings
    return [finding for finding in findings if _finding_matches_changed_files(finding, changed_files)]


def _progress_stage_duration(progress: ProgressReporter, key: str) -> float:
    for stage in progress.to_dict().get("stages", []):
        if stage.get("key") != key:
            continue
        try:
            return float(stage.get("duration_seconds") or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _run_recommended_pipeline_slice(
    *,
    output_dir: Path,
    profile: str,
    skip_vulture: bool,
    skip_bandit: bool,
    changed_files: list[str],
    entrypoints_module: Any,
    repo_audit: Any,
    pipeline_check_ids: list[str],
    pytest_workers: str | None,
) -> dict[str, Any]:
    pipeline_summary = pipeline_module._run_pipeline(
        output_dir,
        trace_target=(pipeline_module.DEFAULT_TRACE_TARGET if pipeline_module.DEFAULT_TRACE_TARGET.exists() else None),
        profile=profile,
        include_vulture=False if skip_vulture else None,
        include_bandit=False if skip_bandit else None,
        corpus_manifest_dir=entrypoints_module._default_corpus_manifest_dir(),
        changed_files=list(changed_files),
        selected_checks=pipeline_check_ids,
        pytest_workers=pytest_workers,
    )
    return {
        "pipeline_summary": pipeline_summary,
        "pipeline_findings": repo_audit._find_pipeline_findings(output_dir),
    }


def _run_recommended_custom_scan(
    *,
    repo_root: Path,
    include_generated: bool,
    suspicious_identifiers: Iterable[str],
    resolved_changed_files: list[str],
    repo_finding_check_ids: list[str],
    repo_check_ids: list[str],
    entrypoints_module: Any,
    repo_audit: Any,
) -> dict[str, Any]:
    custom_findings: list[Any] = []
    cli_consistency_report = None
    ai_gc_report = None
    if repo_finding_check_ids:
        custom_findings.extend(
            entrypoints_module.collect_custom_findings(
                repo_root,
                include_generated=include_generated,
                tracked_only=True,
                suspicious_identifiers=suspicious_identifiers,
                selected_checks=repo_finding_check_ids,
            )
        )
    if "ai-gc" in repo_check_ids:
        ai_gc_report = repo_audit.build_ai_gc_report(repo_root)
    if "cli-consistency" in repo_check_ids:
        cli_consistency_report = repo_audit.build_cli_consistency_report(root=repo_root)
        custom_findings.extend(entrypoints_module._cli_consistency_findings(cli_consistency_report))
    scoped_custom_findings = _filter_custom_findings_to_changed_files(custom_findings, list(resolved_changed_files))
    return {
        "custom_findings": scoped_custom_findings,
        "filtered_custom_findings": len(custom_findings) - len(scoped_custom_findings),
        "ai_gc_report": ai_gc_report,
        "cli_consistency_report": cli_consistency_report,
    }


def run_recommended_repo_audit_slice(
    output_dir: Path,
    *,
    profile: str,
    fail_on: str,
    include_generated: bool,
    suspicious_identifiers: Iterable[str],
    skip_vulture: bool,
    skip_bandit: bool,
    changed_files: Iterable[str] | None,
    pytest_workers: str | None = None,
    latest_output_dir: Path | None = None,
    record_history: bool = True,
) -> dict[str, Any]:
    entrypoints_module = _entrypoints_module()
    repo_audit = entrypoints_module._repo_audit_module()
    output_dir.mkdir(parents=True, exist_ok=True)
    ai_gc_report = None
    resolved_changed_files = entrypoints_module.normalize_changed_files(
        pipeline_module._detect_changed_files(repo_root=repo_audit.REPO_ROOT)
        if changed_files is None
        else changed_files
    )
    recommendation = entrypoints_module.build_repo_audit_check_recommendations(
        profile=profile,
        output_dir=output_dir,
        fail_on=fail_on,
        changed_files=resolved_changed_files,
    )
    pipeline_check_ids = recommendation["recommended_pipeline_check_ids"]
    repo_check_ids = recommendation["recommended_repo_audit_check_ids"]
    repo_finding_check_ids = [
        check_id for check_id in repo_check_ids if check_id in entrypoints_module.REPO_AUDIT_FINDING_CHECK_IDS
    ]
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
            ("pipeline", "Run recommended pipeline checks"),
            ("custom_scan", "Run recommended repository-specific checks"),
            ("merge_findings", "Merge and normalize findings"),
            ("write_reports", "Write audit reports"),
        ],
        canonical_command=(
            f"sattlint-repo-audit --profile {profile} --run-recommended-slice --fail-on {fail_on} "
            f"--output-dir {sanitized_output_dir}"
        ),
    )
    pipeline_summary: dict[str, Any] | None = None
    pipeline_findings: list[Any] = []
    custom_findings: list[Any] = []
    cli_consistency_report = None
    filtered_custom_findings = 0
    pipeline_output_dir = output_dir / repo_audit.PIPELINE_OUTPUT_DIRNAME
    pipeline_future = None
    custom_scan_future = None
    if pipeline_check_ids:
        progress.start_stage("pipeline")
    else:
        progress.skip_stage("pipeline", detail="no pipeline checks recommended")
    if repo_finding_check_ids or "ai-gc" in repo_check_ids or "cli-consistency" in repo_check_ids:
        progress.start_stage("custom_scan")
    else:
        progress.skip_stage("custom_scan", detail="no repo-audit checks recommended")
    with ThreadPoolExecutor(max_workers=RECOMMENDED_REPO_AUDIT_MAX_WORKERS) as executor:
        if pipeline_check_ids:
            pipeline_future = executor.submit(
                _run_recommended_pipeline_slice,
                output_dir=pipeline_output_dir,
                profile=profile,
                skip_vulture=skip_vulture,
                skip_bandit=skip_bandit,
                changed_files=list(resolved_changed_files),
                entrypoints_module=entrypoints_module,
                repo_audit=repo_audit,
                pipeline_check_ids=pipeline_check_ids,
                pytest_workers=pytest_workers,
            )
        if repo_finding_check_ids or "ai-gc" in repo_check_ids or "cli-consistency" in repo_check_ids:
            custom_scan_future = executor.submit(
                _run_recommended_custom_scan,
                repo_root=repo_audit.REPO_ROOT,
                include_generated=include_generated,
                suspicious_identifiers=suspicious_identifiers,
                resolved_changed_files=list(resolved_changed_files),
                repo_finding_check_ids=repo_finding_check_ids,
                repo_check_ids=repo_check_ids,
                entrypoints_module=entrypoints_module,
                repo_audit=repo_audit,
            )
        if pipeline_future is not None:
            pipeline_result = pipeline_future.result()
            pipeline_summary = pipeline_result["pipeline_summary"]
            pipeline_findings = list(pipeline_result["pipeline_findings"])
            progress.complete_stage("pipeline", detail=f"{len(pipeline_findings)} pipeline findings")
        if custom_scan_future is not None:
            custom_scan_result = custom_scan_future.result()
            custom_findings = list(custom_scan_result["custom_findings"])
            filtered_custom_findings = int(custom_scan_result["filtered_custom_findings"])
            ai_gc_report = custom_scan_result["ai_gc_report"]
            cli_consistency_report = custom_scan_result["cli_consistency_report"]
            custom_scan_detail = f"{len(custom_findings)} custom findings"
            if filtered_custom_findings:
                custom_scan_detail += f" ({filtered_custom_findings} outside changed scope)"
            progress.complete_stage("custom_scan", detail=custom_scan_detail)

    progress.start_stage("merge_findings")
    findings = repo_audit._dedupe_findings([*pipeline_findings, *custom_findings])
    findings = sorted(
        findings,
        key=lambda item: (
            -repo_audit.SEVERITY_RANK[item.severity],
            item.category,
            item.path or "",
            item.line or 0,
            item.id,
        ),
    )
    blocking_count = entrypoints_module._blocking_finding_count(findings, fail_on)
    enabled_audit_artifact_ids = {"progress", "status", "summary", "findings", "summary_markdown", "run_history"}
    if cli_consistency_report is not None:
        enabled_audit_artifact_ids.add("cli_consistency")
    if ai_gc_report is not None:
        enabled_audit_artifact_ids.add("ai_gc")
    reports = artifact_reports_map(
        AUDIT_ARTIFACTS,
        profile=profile,
        enabled_artifact_ids=enabled_audit_artifact_ids,
    )
    progress.complete_stage("merge_findings", detail=f"{len(findings)} total findings")
    reports["pipeline_status"] = (
        None if pipeline_summary is None else f"{repo_audit.PIPELINE_OUTPUT_DIRNAME}/status.json"
    )
    reports["pipeline_summary"] = (
        None if pipeline_summary is None else f"{repo_audit.PIPELINE_OUTPUT_DIRNAME}/summary.json"
    )
    finding_collection = FindingCollection(tuple(finding.to_record() for finding in findings))
    overall_status_value = "fail" if blocking_count else "pass"
    if cli_consistency_report is not None and cli_consistency_report.get("status") == "fail":
        overall_status_value = "fail"
    summary = {
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "output_dir": sanitized_output_dir,
        "profile": profile,
        "entry_report": "status.json",
        "canonical_command": progress.to_dict()["canonical_command"],
        "overall_status": overall_status_value,
        "pipeline_ran": bool(pipeline_check_ids),
        "pipeline_summary": pipeline_summary,
        "reports": reports,
        "finding_count": len(findings),
        "severity_counts": entrypoints_module._severity_counts(findings),
        "category_counts": entrypoints_module._category_counts(findings),
        "max_severity": entrypoints_module._max_severity(findings),
        "findings_schema": finding_collection.schema_metadata,
        "history_cleanup_findings": [finding.to_dict() for finding in findings if finding.history_cleanup_recommended],
        "findings": [finding.to_dict() for finding in findings],
        "selected_checks": recommendation["recommended_check_ids"],
        "selected_pipeline_checks": pipeline_check_ids,
        "selected_repo_audit_checks": repo_check_ids,
        "recommendation": recommendation,
        "cli_consistency_status": None if cli_consistency_report is None else cli_consistency_report.get("status"),
        "timing": {
            "stage_durations_seconds": {
                "pipeline": round(_progress_stage_duration(progress, "pipeline"), 3),
                "custom_scan": round(_progress_stage_duration(progress, "custom_scan"), 3),
                "merge_findings": round(_progress_stage_duration(progress, "merge_findings"), 3),
                "write_reports": 0.0,
            },
            "selected_pipeline_check_durations_seconds": (
                {}
                if pipeline_summary is None
                else dict((pipeline_summary.get("timing") or {}).get("check_durations_seconds") or {})
            ),
            "parallel_worker_count": RECOMMENDED_REPO_AUDIT_MAX_WORKERS,
            "critical_path_duration_seconds": 0.0,
            "total_duration_seconds": 0.0,
        },
    }
    status_report = {
        "kind": "sattlint.repo_audit.status",
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
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
        "pipeline_status_report": None
        if pipeline_summary is None
        else f"{sanitized_output_dir}/{repo_audit.PIPELINE_OUTPUT_DIRNAME}/status.json",
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
        "selected_checks": recommendation["recommended_check_ids"],
        "selected_pipeline_checks": pipeline_check_ids,
        "selected_repo_audit_checks": repo_check_ids,
        "cli_consistency_status": None if cli_consistency_report is None else cli_consistency_report.get("status"),
    }
    progress.start_stage("write_reports")
    write_json_artifact(output_dir / "status.json", status_report)
    write_json_artifact(output_dir / "summary.json", summary)
    write_json_artifact(output_dir / "findings.json", finding_collection.to_dict())
    if ai_gc_report is not None:
        write_json_artifact(output_dir / "ai_gc.json", ai_gc_report)
    repo_audit._write_markdown(output_dir / "summary.md", findings, summary)
    if cli_consistency_report is not None:
        write_json_artifact(output_dir / "cli_consistency.json", cli_consistency_report)
    if record_history:
        repo_audit._write_audit_run_history(
            output_dir,
            latest_output_dir=latest_output_dir,
            report_kind="repo_audit_recommended_slice",
            primary_payload=summary,
            status_payload=status_report,
            summary_payload=summary,
        )
    repo_audit._mirror_latest_reports(output_dir, latest_output_dir)
    progress.complete_stage("write_reports")
    progress.finalize(overall_status=overall_status_value)
    write_reports_duration = round(_progress_stage_duration(progress, "write_reports"), 3)
    stage_durations = summary["timing"]["stage_durations_seconds"]
    stage_durations["write_reports"] = write_reports_duration
    critical_path_duration = round(
        max(stage_durations["pipeline"], stage_durations["custom_scan"])
        + stage_durations["merge_findings"]
        + write_reports_duration,
        3,
    )
    summary["timing"]["critical_path_duration_seconds"] = critical_path_duration
    summary["timing"]["total_duration_seconds"] = round(sum(float(value) for value in stage_durations.values()), 3)
    return summary


def run_recommended_repo_audit_finish_gate(
    output_dir: Path,
    *,
    profile: str,
    fail_on: str,
    include_generated: bool,
    suspicious_identifiers: Iterable[str],
    skip_vulture: bool,
    skip_bandit: bool,
    changed_files: Iterable[str] | None,
    pytest_workers: str | None = None,
    latest_output_dir: Path | None = None,
) -> dict[str, Any]:
    entrypoints_module = _entrypoints_module()
    recommendation = entrypoints_module.build_repo_audit_check_recommendations(
        profile=profile,
        output_dir=output_dir,
        fail_on=fail_on,
        changed_files=changed_files,
    )
    proof_requirements = recommendation.get("proof_requirements") or pipeline_module.build_change_proof_requirements(
        changed_files=recommendation.get("changed_files", []),
        recommended_checks=recommendation.get("recommended_checks", []),
    )
    summary = entrypoints_module.run_recommended_repo_audit_slice(
        output_dir,
        profile=profile,
        fail_on=fail_on,
        include_generated=include_generated,
        suspicious_identifiers=suspicious_identifiers,
        skip_vulture=skip_vulture,
        skip_bandit=skip_bandit,
        changed_files=changed_files,
        pytest_workers=pytest_workers,
        latest_output_dir=latest_output_dir,
        record_history=False,
    )
    finish_gate_steps = entrypoints_module._build_repo_audit_finish_gate_commands(
        profile=profile,
        output_dir=output_dir,
        fail_on=fail_on,
        changed_files=recommendation["changed_files"],
        recommended_checks=recommendation["recommended_checks"],
        ruff_command=[pipeline_module._resolve_venv_tool("ruff") or "ruff"],
        pyright_command=[pipeline_module._resolve_venv_tool("pyright") or "pyright"],
        python_command=[pipeline_module._resolve_python_executable()],
        pytest_workers=pytest_workers,
    )[1:]
    step_reports = execute_finish_gate_steps(
        steps=finish_gate_steps,
        run_command=pipeline_module._run_command,
        pipeline_summary=summary.get("pipeline_summary"),
    )
    finish_gate_status = "pass"
    coverage_proof: dict[str, Any] = {
        "status": "not-required",
        "mode": "skipped",
        "coverage_path": None,
    }
    for step_report in step_reports:
        step_status = str(step_report.get("status", "pass"))
        if step_status == "fail":
            finish_gate_status = "fail"
    if proof_requirements["focused_behavior_test"]["status"] == "missing":
        finish_gate_status = "fail"
        step_reports.append(
            {
                "id": "focused-behavior-test",
                "label": "Require focused owner pytest for changed code",
                "command": "",
                "exit_code": None,
                "duration_seconds": 0.0,
                "status": "fail",
                "detail": proof_requirements["focused_behavior_test"]["reason"],
            }
        )
    coverage_step = next((step for step in finish_gate_steps if step["id"] == "owner-pytest-coverage"), None)
    if coverage_step is not None:
        coverage_proof = pipeline_module.evaluate_change_scoped_coverage_proof(
            repo_root=entrypoints_module._repo_audit_module().REPO_ROOT,
            coverage_output_path=Path(str(coverage_step["coverage_output_path"])),
            changed_files=recommendation["changed_files"],
        )
        if coverage_proof["status"] == "fail":
            finish_gate_status = "fail"
    elif proof_requirements["coverage"]["required"]:
        coverage_proof = {
            "status": "fail",
            "mode": "skipped",
            "coverage_path": None,
            "reason": "Focused coverage proof is required for changed source files but no owner pytest coverage step was available.",
        }
        finish_gate_status = "fail"
    finish_gate_report = {
        "kind": "sattlint.repo_audit.finish_gate",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "status": finish_gate_status,
        "commands": step_reports,
        "changed_files": recommendation["changed_files"],
        "owner_test_targets": entrypoints_module._owner_test_targets_for_checks(recommendation["recommended_checks"]),
        "proof_requirements": proof_requirements,
        "coverage_proof": coverage_proof,
        "timing": summarize_finish_gate_timing(step_reports),
    }
    write_json_artifact(output_dir / "finish_gate.json", finish_gate_report)
    summary["finish_gate"] = finish_gate_report
    summary["overall_status"] = (
        "fail" if summary.get("overall_status") == "fail" or finish_gate_status == "fail" else "pass"
    )
    repo_audit = entrypoints_module._repo_audit_module()
    repo_audit._write_audit_run_history(
        output_dir,
        latest_output_dir=latest_output_dir,
        report_kind="repo_audit_finish_gate",
        primary_payload=summary,
        status_payload=None,
        summary_payload=summary,
    )
    return summary


__all__ = [
    "run_recommended_repo_audit_finish_gate",
    "run_recommended_repo_audit_slice",
]
