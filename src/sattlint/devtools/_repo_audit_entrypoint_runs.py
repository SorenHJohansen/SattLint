"""Repo-audit recommended-run helpers."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sattlint.devtools import pipeline as pipeline_module
from sattlint.devtools._pipeline_finish_gate import execute_finish_gate_steps, summarize_finish_gate_timing
from sattlint.devtools.pipeline_artifacts import write_json_artifact
from sattlint.path_sanitizer import sanitize_path_for_report


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


filter_custom_findings_to_changed_files = _filter_custom_findings_to_changed_files


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
    from sattlint.devtools import _repo_audit_recommended_slice as helper

    return helper.run_recommended_repo_audit_slice(
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
        record_history=record_history,
    )


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
        ruff_command=[pipeline_module.resolve_venv_tool("ruff") or "ruff"],
        pyright_command=[pipeline_module.resolve_venv_tool("pyright") or "pyright"],
        python_command=[pipeline_module.resolve_python_executable()],
        pytest_workers=pytest_workers,
    )[1:]
    step_reports = execute_finish_gate_steps(
        steps=finish_gate_steps,
        run_command=pipeline_module.run_command,
        pipeline_summary=summary.get("pipeline_summary"),
    )
    finish_gate_status = "pass"
    coverage_proof: dict[str, Any] = {
        "status": "not-required",
        "mode": "skipped",
        "coverage_path": None,
    }
    structural_surface_proof: dict[str, Any] = {
        "status": "not-required",
        "checked_files": [],
        "expected_metrics": {},
        "metrics_by_path": {},
        "violations": [],
        "scan_failures": [],
        "reason": "No changed structural Python files require structural surface proof.",
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
            repo_root=entrypoints_module._repo_audit_entrypoints_module().REPO_ROOT,
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
    structural_surface_proof = pipeline_module.evaluate_change_scoped_structural_surface_proof(
        repo_root=entrypoints_module._repo_audit_entrypoints_module().REPO_ROOT,
        changed_files=recommendation["changed_files"],
    )
    if structural_surface_proof["status"] == "fail":
        finish_gate_status = "fail"
        step_reports.append(
            {
                "id": "changed-file-structural-surface",
                "label": "Check changed-file structural surface ceilings",
                "command": "",
                "exit_code": None,
                "duration_seconds": 0.0,
                "status": "fail",
                "detail": structural_surface_proof["reason"],
            }
        )
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
        "structural_surface_proof": structural_surface_proof,
        "timing": summarize_finish_gate_timing(step_reports),
    }
    write_json_artifact(output_dir / "finish_gate.json", finish_gate_report)
    summary["finish_gate"] = finish_gate_report
    summary["overall_status"] = (
        "fail" if summary.get("overall_status") == "fail" or finish_gate_status == "fail" else "pass"
    )
    repo_audit = entrypoints_module._repo_audit_entrypoints_module()
    repo_audit._write_audit_run_history(
        output_dir,
        latest_output_dir=latest_output_dir,
        report_kind="repo_audit_finish_gate",
        primary_payload=summary,
        status_payload=None,
        summary_payload=summary,
    )
    return summary


def run_check_my_changes(
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
    repo_audit = entrypoints_module._repo_audit_entrypoints_module()
    output_dir.mkdir(parents=True, exist_ok=True)
    planning_report = entrypoints_module.build_check_my_changes_planning_report(
        profile=profile,
        output_dir=output_dir,
        fail_on=fail_on,
        changed_files=changed_files,
    )
    recommendation = planning_report["recommendation"]
    resolved_changed_files = planning_report["changed_files"]
    selected_surface = planning_report["selected_surface"]
    selected_reason = planning_report["selected_reason"]
    planning_context = planning_report["planning_context"]
    sanitized_output_dir = (
        sanitize_path_for_report(output_dir.resolve(), repo_root=repo_audit.REPO_ROOT)
        or output_dir.resolve().as_posix()
    )

    if selected_surface == "pipeline":
        selected_output_dir = output_dir / repo_audit.PIPELINE_OUTPUT_DIRNAME
        selected_output_dir.mkdir(parents=True, exist_ok=True)
        sanitized_selected_output_dir = (
            sanitize_path_for_report(selected_output_dir.resolve(), repo_root=repo_audit.REPO_ROOT)
            or selected_output_dir.resolve().as_posix()
        )
        selected_command_argv = [
            "sattlint-analysis-pipeline",
            "--profile",
            profile,
            "--run-recommended-finish-gate",
            *entrypoints_module._changed_file_flag_args(resolved_changed_files),
            "--output-dir",
            sanitized_selected_output_dir,
        ]
        if pytest_workers is not None and str(pytest_workers).strip():
            selected_command_argv.extend(["--pytest-workers", str(pytest_workers).strip()])
        selected_result = pipeline_module.run_recommended_pipeline_finish_gate(
            selected_output_dir,
            trace_target=(
                pipeline_module.DEFAULT_TRACE_TARGET if pipeline_module.DEFAULT_TRACE_TARGET.exists() else None
            ),
            profile=profile,
            include_vulture=False if skip_vulture else None,
            include_bandit=False if skip_bandit else None,
            baseline_findings=None,
            corpus_manifest_dir=entrypoints_module._default_corpus_manifest_dir(),
            changed_files=resolved_changed_files,
            slow_phase_threshold_ms=25.0,
            phase_budget_ms=50.0,
            total_budget_ms=250.0,
            fail_on_drift=False,
            fail_on_budget=False,
            pytest_workers=pytest_workers,
        )
        overall_status = selected_result["overall_status"]
        finish_gate_status = selected_result["finish_gate"]["status"]
        selected_reports = {
            "status": f"{sanitized_selected_output_dir}/status.json",
            "summary": f"{sanitized_selected_output_dir}/summary.json",
            "finish_gate": f"{sanitized_selected_output_dir}/finish_gate.json",
        }
    else:
        sanitized_selected_output_dir = sanitized_output_dir
        selected_command_argv = [
            "sattlint-repo-audit",
            "--profile",
            profile,
            "--run-recommended-finish-gate",
            *entrypoints_module._changed_file_flag_args(resolved_changed_files),
            "--fail-on",
            fail_on,
            "--output-dir",
            sanitized_selected_output_dir,
        ]
        if pytest_workers is not None and str(pytest_workers).strip():
            selected_command_argv.extend(["--pytest-workers", str(pytest_workers).strip()])
        selected_result = entrypoints_module.run_recommended_repo_audit_finish_gate(
            output_dir,
            profile=profile,
            fail_on=fail_on,
            include_generated=include_generated,
            suspicious_identifiers=suspicious_identifiers,
            skip_vulture=skip_vulture,
            skip_bandit=skip_bandit,
            changed_files=resolved_changed_files,
            pytest_workers=pytest_workers,
            latest_output_dir=latest_output_dir,
        )
        overall_status = selected_result["overall_status"]
        finish_gate_status = selected_result["finish_gate"]["status"]
        selected_reports = {
            "status": f"{sanitized_selected_output_dir}/status.json",
            "summary": f"{sanitized_selected_output_dir}/summary.json",
            "finish_gate": f"{sanitized_selected_output_dir}/finish_gate.json",
        }

    report_path = f"{sanitized_output_dir}/check_my_changes.json"
    reports = {
        **selected_reports,
        "check_my_changes": report_path,
        "ai_feedback": f"{sanitized_output_dir}/{entrypoints_module.AI_FEEDBACK_FILENAME}",
    }
    ai_feedback = entrypoints_module._build_ai_feedback_report(
        changed_files=resolved_changed_files,
        selected_surface=selected_surface,
        selected_reason=selected_reason,
        selected_command=entrypoints_module._shell_command(selected_command_argv),
        overall_status=overall_status,
        finish_gate_status=finish_gate_status,
        reports=reports,
        planning_context=planning_context,
        recommendation=recommendation,
        selected_result=selected_result,
    )
    write_json_artifact(output_dir / entrypoints_module.AI_FEEDBACK_FILENAME, ai_feedback)
    report = {
        "kind": "sattlint.check_my_changes",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "profile": profile,
        "fail_on": fail_on,
        "output_dir": sanitized_output_dir,
        "report_path": report_path,
        "changed_files": resolved_changed_files,
        "selected_surface": selected_surface,
        "selected_reason": selected_reason,
        "selected_command": entrypoints_module._shell_command(selected_command_argv),
        "overall_status": overall_status,
        "finish_gate_status": finish_gate_status,
        "reports": reports,
        "timing": {
            "selected_run": (
                dict(
                    entrypoints_module._mapping_of(
                        entrypoints_module._mapping_of(selected_result.get("pipeline_summary")).get("timing")
                    )
                )
                if selected_surface == "pipeline"
                else dict(entrypoints_module._mapping_of(selected_result.get("timing")))
            ),
            "finish_gate": dict(
                entrypoints_module._mapping_of(
                    entrypoints_module._mapping_of(selected_result.get("finish_gate")).get("timing")
                )
            ),
        },
        "proof_requirements": planning_report.get("proof_requirements", {}),
        "planning_context": planning_context,
        "ai_feedback": ai_feedback,
        "recommendation": {
            "fallback_required": recommendation["fallback_required"],
            "fallback_reason": recommendation["fallback_reason"],
            "recommended_check_ids": recommendation["recommended_check_ids"],
            "recommended_pipeline_check_ids": recommendation["recommended_pipeline_check_ids"],
            "recommended_repo_audit_check_ids": recommendation["recommended_repo_audit_check_ids"],
        },
    }
    write_json_artifact(output_dir / "check_my_changes.json", report)
    repo_audit._write_audit_run_history(
        output_dir,
        latest_output_dir=latest_output_dir,
        report_kind="check_my_changes",
        primary_payload=report,
        status_payload=None,
        summary_payload=None,
    )
    return report


__all__ = [
    "run_check_my_changes",
    "run_recommended_repo_audit_finish_gate",
    "run_recommended_repo_audit_slice",
]
