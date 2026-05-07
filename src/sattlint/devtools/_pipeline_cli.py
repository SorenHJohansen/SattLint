"""Pipeline CLI and recommendation helpers."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sattlint.devtools._pipeline_finish_gate import (
    _build_finish_gate_commands,
    _build_owner_pytest_step,
    _changed_file_flag_args,
    _focused_python_files,
    _owner_test_targets_for_checks,
    _shell_command,
    build_change_proof_requirements,
    evaluate_change_scoped_coverage_proof,
)


def build_pipeline_check_catalog(
    *,
    profile: str,
    output_dir: Path | None,
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module
    from sattlint.devtools import pipeline_checks

    return pipeline_checks.build_pipeline_check_catalog(
        profile=profile,
        output_dir=output_dir or pipeline_module.DEFAULT_OUTPUT_DIR,
        repo_root=pipeline_module.REPO_ROOT,
        validate_profile=pipeline_module._profile_settings,
    )


def _changed_source_python_files(changed_files: Iterable[str]) -> list[str]:
    return [path_text for path_text in _focused_python_files(changed_files) if path_text.startswith("src/")]


def _build_recommendation_why_this_gate(
    *,
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
    skipped_checks: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module
    from sattlint.devtools import pipeline_checks

    normalized_changed_files = pipeline_module.normalize_changed_files(changed_files)
    matched_routes: list[dict[str, Any]] = []
    for entry in recommended_checks:
        matched_files = pipeline_checks.matching_changed_files(normalized_changed_files, entry["path_globs"])
        matched_routes.append(
            {
                "check_id": entry["id"],
                "owner_surface": entry["owner_surface"],
                "matched_files": matched_files,
                "path_globs": entry["path_globs"],
                "reason": entry["reason"],
            }
        )
    return {
        "changed_files": normalized_changed_files,
        "matched_routes": matched_routes,
        "skipped_checks": list(skipped_checks),
    }


def _build_recommendation_drift_report(
    *,
    profile: str,
    changed_files: Iterable[str],
    recommended_check_ids: Iterable[str],
    tool_statuses: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module

    recommended_ids = list(dict.fromkeys(recommended_check_ids))
    observed_nonpassing_check_ids = [
        check_id
        for check_id in pipeline_module.PIPELINE_CHECK_IDS
        if tool_statuses.get(check_id, {}).get("status") in {"fail", "pass_with_notes"}
    ]
    omitted_nonpassing_check_ids = [
        check_id for check_id in observed_nonpassing_check_ids if check_id not in recommended_ids
    ]
    return {
        "kind": "sattlint.pipeline.recommendation_drift",
        "schema_version": 1,
        "profile": profile,
        "changed_files": pipeline_module.normalize_changed_files(changed_files),
        "recommended_check_ids": recommended_ids,
        "observed_nonpassing_check_ids": observed_nonpassing_check_ids,
        "omitted_nonpassing_check_ids": omitted_nonpassing_check_ids,
        "status": "drift" if omitted_nonpassing_check_ids else "consistent",
    }


def build_pipeline_check_recommendations(
    *,
    profile: str,
    output_dir: Path | None,
    changed_files: Iterable[str] | None,
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module
    from sattlint.devtools import pipeline_checks

    resolved_output_dir = (output_dir or pipeline_module.DEFAULT_OUTPUT_DIR).resolve()
    resolved_changed_files = pipeline_module.normalize_changed_files(
        pipeline_module._detect_changed_files(repo_root=pipeline_module.REPO_ROOT)
        if changed_files is None
        else changed_files
    )
    catalog = build_pipeline_check_catalog(
        profile=profile,
        output_dir=resolved_output_dir,
    )
    fallback_required = False
    fallback_reason: str | None = None
    recommendation_reasons: dict[str, str] = {}

    if not resolved_changed_files:
        fallback_required = True
        fallback_reason = (
            "No changed files were provided or detected, so the full supported pipeline slice is recommended."
        )
    elif pipeline_checks.matching_changed_files(
        resolved_changed_files, pipeline_checks.PIPELINE_RECOMMENDATION_FALLBACK_GLOBS
    ):
        fallback_required = True
        fallback_reason = (
            "Changed files touch the pipeline control surface, so the full supported pipeline slice is recommended."
        )

    if fallback_required and fallback_reason is not None:
        for entry in catalog["checks"]:
            recommendation_reasons[entry["id"]] = fallback_reason
    else:
        for entry in catalog["checks"]:
            matched_files = pipeline_checks.matching_changed_files(resolved_changed_files, entry["path_globs"])
            if not matched_files:
                continue
            recommendation_reasons[entry["id"]] = f"Matched {matched_files[0]} against the {entry['id']} routing globs."
        if not recommendation_reasons:
            fallback_required = True
            fallback_reason = "No pipeline routing globs matched the changed files, so the full supported pipeline slice is recommended."
            for entry in catalog["checks"]:
                recommendation_reasons[entry["id"]] = fallback_reason

    recommended_checks: list[dict[str, Any]] = []
    skipped_checks: list[dict[str, Any]] = []
    for entry in catalog["checks"]:
        reason = recommendation_reasons.get(entry["id"])
        if reason is None:
            skipped_checks.append(
                {
                    "id": entry["id"],
                    "label": entry["label"],
                    "reason": "No changed-file route matched this check.",
                }
            )
            continue
        recommended_checks.append({**entry, "reason": reason})

    suggested_finish_gate_commands = _build_finish_gate_commands(
        profile=profile,
        output_dir=resolved_output_dir,
        changed_files=resolved_changed_files,
        recommended_checks=recommended_checks,
        ruff_command=["ruff"],
        pyright_command=["pyright"],
        python_command=["python"],
    )

    return {
        "kind": "sattlint.pipeline.check_recommendations",
        "schema_version": 1,
        "profile": profile,
        "changed_files": resolved_changed_files,
        "fallback_required": fallback_required,
        "fallback_reason": fallback_reason,
        "recommended_check_ids": [entry["id"] for entry in recommended_checks],
        "suggested_check_commands": [entry["command"] for entry in recommended_checks],
        "suggested_finish_gate_commands": [entry["command"] for entry in suggested_finish_gate_commands],
        "recommended_checks": recommended_checks,
        "skipped_checks": skipped_checks,
        "proof_requirements": build_change_proof_requirements(
            changed_files=resolved_changed_files,
            recommended_checks=recommended_checks,
        ),
        "why_this_gate": _build_recommendation_why_this_gate(
            changed_files=resolved_changed_files,
            recommended_checks=recommended_checks,
            skipped_checks=skipped_checks,
        ),
    }


def run_recommended_pipeline_finish_gate(
    output_dir: Path,
    *,
    trace_target: Path | None,
    profile: str,
    include_vulture: bool | None,
    include_bandit: bool | None,
    baseline_findings: Path | None,
    corpus_manifest_dir: Path | None,
    changed_files: Iterable[str] | None,
    slow_phase_threshold_ms: float,
    phase_budget_ms: float,
    total_budget_ms: float,
    fail_on_drift: bool,
    fail_on_budget: bool,
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module

    recommendation = pipeline_module.build_pipeline_check_recommendations(
        profile=profile,
        output_dir=output_dir,
        changed_files=changed_files,
    )
    proof_requirements = recommendation.get("proof_requirements") or pipeline_module.build_change_proof_requirements(
        changed_files=recommendation.get("changed_files", []),
        recommended_checks=recommendation.get("recommended_checks", []),
    )
    summary = pipeline_module._run_pipeline(
        output_dir,
        trace_target=trace_target,
        profile=profile,
        include_vulture=include_vulture,
        include_bandit=include_bandit,
        baseline_findings=baseline_findings,
        corpus_manifest_dir=corpus_manifest_dir,
        changed_files=pipeline_module.normalize_changed_files(changed_files),
        slow_phase_threshold_ms=slow_phase_threshold_ms,
        phase_budget_ms=phase_budget_ms,
        total_budget_ms=total_budget_ms,
        fail_on_drift=fail_on_drift,
        fail_on_budget=fail_on_budget,
        selected_checks=recommendation["recommended_check_ids"],
    )
    finish_gate_steps = _build_finish_gate_commands(
        profile=profile,
        output_dir=output_dir,
        changed_files=recommendation["changed_files"],
        recommended_checks=recommendation["recommended_checks"],
        ruff_command=[pipeline_module._resolve_venv_tool("ruff") or "ruff"],
        pyright_command=[pipeline_module._resolve_venv_tool("pyright") or "pyright"],
        python_command=[pipeline_module._resolve_python_executable()],
    )[1:]
    step_reports: list[dict[str, Any]] = []
    finish_gate_status = "pass"
    coverage_proof: dict[str, Any] = {
        "status": "not-required",
        "mode": "skipped",
        "coverage_path": None,
    }
    for step in finish_gate_steps:
        result = pipeline_module._run_command(step["id"], step["argv"])
        step_status = "pass" if result.exit_code == 0 else "fail"
        if step_status == "fail":
            finish_gate_status = "fail"
        step_reports.append(
            {
                "id": step["id"],
                "label": step["label"],
                "command": step["command"],
                "exit_code": result.exit_code,
                "duration_seconds": result.duration_seconds,
                "status": step_status,
            }
        )
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
        "kind": "sattlint.pipeline.finish_gate",
        "schema_version": 1,
        "status": finish_gate_status,
        "commands": step_reports,
        "changed_files": recommendation["changed_files"],
        "owner_test_targets": _owner_test_targets_for_checks(recommendation["recommended_checks"]),
        "proof_requirements": proof_requirements,
        "coverage_proof": coverage_proof,
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


__all__ = [
    "_build_finish_gate_commands",
    "_build_owner_pytest_step",
    "_build_recommendation_drift_report",
    "_build_recommendation_why_this_gate",
    "_changed_file_flag_args",
    "_focused_python_files",
    "_owner_test_targets_for_checks",
    "_shell_command",
    "build_change_proof_requirements",
    "build_pipeline_check_catalog",
    "build_pipeline_check_recommendations",
    "evaluate_change_scoped_coverage_proof",
    "run_recommended_pipeline_finish_gate",
]
