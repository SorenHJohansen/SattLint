"""Finish-gate execution helpers for the pipeline CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast


def run_recommended_pipeline_finish_gate(
    output_dir: Path,
    *,
    trace_target: Path | None,
    profile: str,
    include_vulture: bool | None,
    include_bandit: bool | None,
    baseline_findings: Path | None,
    corpus_manifest_dir: Path | None,
    changed_files: list[str] | None,
    slow_phase_threshold_ms: float,
    phase_budget_ms: float,
    total_budget_ms: float,
    fail_on_drift: bool,
    fail_on_budget: bool,
    pytest_workers: str | None = None,
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module  # noqa: PLC0415

    from . import _pipeline_finish_gate as finish_gate_module  # noqa: PLC0415

    recommendation = pipeline_module.build_pipeline_check_recommendations(
        profile=profile,
        output_dir=output_dir,
        changed_files=pipeline_module.normalize_changed_files(changed_files),
        pytest_workers=pytest_workers,
    )
    recommended_check_ids = cast(list[str], recommendation.get("recommended_check_ids") or [])
    recommended_checks = cast(list[dict[str, Any]], recommendation.get("recommended_checks") or [])
    recommended_changed_files = cast(list[str], recommendation.get("changed_files") or [])
    proof_requirements = cast(
        dict[str, Any],
        recommendation.get("proof_requirements")
        or pipeline_module.build_change_proof_requirements(
            changed_files=recommended_changed_files,
            recommended_checks=recommended_checks,
        ),
    )
    selected_pipeline_checks = finish_gate_module.finish_gate_pipeline_check_ids(
        recommended_check_ids=recommended_check_ids,
        changed_files=recommended_changed_files,
        recommended_checks=recommended_checks,
        pytest_workers=pytest_workers,
    )
    summary = pipeline_module.run_pipeline(
        output_dir,
        trace_target=trace_target,
        profile=profile,
        include_vulture=include_vulture,
        include_bandit=include_bandit,
        baseline_findings=baseline_findings,
        corpus_manifest_dir=corpus_manifest_dir,
        changed_files=recommended_changed_files,
        slow_phase_threshold_ms=slow_phase_threshold_ms,
        phase_budget_ms=phase_budget_ms,
        total_budget_ms=total_budget_ms,
        fail_on_drift=fail_on_drift,
        fail_on_budget=fail_on_budget,
        selected_checks=selected_pipeline_checks,
        pytest_workers=pytest_workers,
    )
    finish_gate_steps = finish_gate_module.build_finish_gate_commands(
        profile=profile,
        output_dir=output_dir,
        changed_files=recommended_changed_files,
        recommended_checks=recommended_checks,
        ruff_command=[pipeline_module.resolve_venv_tool("ruff") or "ruff"],
        pyright_command=[pipeline_module.resolve_venv_tool("pyright") or "pyright"],
        python_command=[pipeline_module.resolve_python_executable()],
        pytest_workers=pytest_workers,
    )[1:]
    step_reports = finish_gate_module.execute_finish_gate_steps(
        steps=finish_gate_steps,
        run_command=pipeline_module.run_command,
        pipeline_summary=summary,
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
        if str(step_report.get("status", "pass")) == "fail":
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
            repo_root=pipeline_module.REPO_ROOT,
            coverage_output_path=Path(coverage_step["coverage_output_path"]),
            changed_files=recommended_changed_files,
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
        repo_root=pipeline_module.REPO_ROOT,
        changed_files=recommended_changed_files,
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
    finish_gate_report: dict[str, Any] = {
        "kind": "sattlint.pipeline.finish_gate",
        "schema_version": 1,
        "status": finish_gate_status,
        "commands": step_reports,
        "changed_files": recommended_changed_files,
        "selected_pipeline_checks": selected_pipeline_checks,
        "owner_test_targets": finish_gate_module.owner_test_targets_for_checks(recommended_checks),
        "proof_requirements": proof_requirements,
        "coverage_proof": coverage_proof,
        "structural_surface_proof": structural_surface_proof,
        "timing": finish_gate_module.summarize_finish_gate_timing(step_reports),
    }
    pipeline_module.write_json_artifact(output_dir / "finish_gate.json", finish_gate_report)
    return {
        "recommendation": recommendation,
        "pipeline_summary": summary,
        "finish_gate": finish_gate_report,
        "overall_status": "fail"
        if summary["status"]["overall_status"] == "fail" or finish_gate_status == "fail"
        else "pass",
    }


__all__ = ["run_recommended_pipeline_finish_gate"]
