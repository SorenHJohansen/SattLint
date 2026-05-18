"""Planning and AI-feedback helpers for repo-audit entrypoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sattlint.path_sanitizer import sanitize_path_for_report


def mapping_of(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def selected_surface_and_reason(recommendation: dict[str, Any]) -> tuple[str, str]:
    selected_surface = "repo-audit" if recommendation["recommended_repo_audit_check_ids"] else "pipeline"
    if selected_surface == "pipeline":
        return (
            selected_surface,
            "No repo-audit-specific checks were recommended, so the shared pipeline finish gate is sufficient.",
        )
    return (
        selected_surface,
        "Repo-audit-specific checks were recommended, so the combined repo-audit finish gate is required.",
    )


def build_selected_finish_gate_plan(
    *,
    profile: str,
    output_dir: Path,
    fail_on: str,
    selected_surface: str,
    changed_files: Any,
    planning_context: dict[str, Any],
    recommendation: dict[str, Any],
    repo_audit: Any,
    pipeline_module: Any,
    normalize_changed_files: Any,
) -> dict[str, Any]:
    normalized_changed_files = normalize_changed_files(changed_files)
    finish_gate_template = mapping_of(planning_context.get("finish_gate_template"))

    if selected_surface == "pipeline":
        selected_output_dir = output_dir / repo_audit.PIPELINE_OUTPUT_DIRNAME
        surface_recommendation = pipeline_module.build_pipeline_check_recommendations(
            profile=profile,
            output_dir=selected_output_dir,
            changed_files=normalized_changed_files,
        )
        command_list = list(surface_recommendation.get("suggested_finish_gate_commands", []))
        recommended_check_ids = list(surface_recommendation.get("recommended_check_ids", []))
        sanitized_selected_output_dir = repo_audit.PIPELINE_OUTPUT_DIRNAME
    else:
        selected_output_dir = output_dir
        command_list = list(recommendation.get("suggested_finish_gate_commands", []))
        recommended_check_ids = list(recommendation.get("recommended_check_ids", []))
        sanitized_selected_output_dir = (
            sanitize_path_for_report(selected_output_dir.resolve(), repo_root=repo_audit.REPO_ROOT)
            or selected_output_dir.resolve().as_posix()
        )
    return {
        "selected_surface": selected_surface,
        "output_dir": sanitized_selected_output_dir,
        "command": None if not command_list else command_list[0],
        "commands": command_list,
        "description": str(finish_gate_template.get("description", "")),
        "includes": string_list(finish_gate_template.get("includes")),
        "owner_test_targets": string_list(planning_context.get("owner_test_targets")),
        "recommended_check_ids": recommended_check_ids,
    }


def build_check_my_changes_planning_report(
    *,
    profile: str,
    output_dir: Path | None,
    fail_on: str,
    changed_files: Any,
    repo_audit: Any,
    build_repo_audit_check_recommendations: Any,
    build_change_proof_requirements: Any,
    build_planning_context: Any,
    build_selected_finish_gate_plan_fn: Any,
) -> dict[str, Any]:
    resolved_output_dir = (output_dir or repo_audit.DEFAULT_OUTPUT_DIR).resolve()
    sanitized_output_dir = (
        sanitize_path_for_report(resolved_output_dir, repo_root=repo_audit.REPO_ROOT) or resolved_output_dir.as_posix()
    )
    recommendation = build_repo_audit_check_recommendations(
        profile=profile,
        output_dir=resolved_output_dir,
        fail_on=fail_on,
        changed_files=changed_files,
    )
    proof_requirements = recommendation.get("proof_requirements") or build_change_proof_requirements(
        changed_files=recommendation.get("changed_files", []),
        recommended_checks=recommendation.get("recommended_checks", []),
    )
    selected_surface, selected_reason = selected_surface_and_reason(recommendation)
    planning_context = build_planning_context(
        changed_files=recommendation["changed_files"],
        recommended_check_ids=recommendation["recommended_check_ids"],
        selected_surface=selected_surface,
    )
    finish_gate = build_selected_finish_gate_plan_fn(
        profile=profile,
        output_dir=resolved_output_dir,
        fail_on=fail_on,
        selected_surface=selected_surface,
        changed_files=recommendation["changed_files"],
        planning_context=planning_context,
        recommendation=recommendation,
    )
    planning_context["finish_gate"] = finish_gate
    return {
        "kind": "sattlint.planning_context",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "default_entrypoint": dict(mapping_of(planning_context.get("default_entrypoint"))),
        "profile": profile,
        "fail_on": fail_on,
        "output_dir": sanitized_output_dir,
        "changed_files": recommendation["changed_files"],
        "owning_surface": selected_surface,
        "selected_surface": selected_surface,
        "selected_reason": selected_reason,
        "finish_gate": finish_gate,
        "proof_requirements": proof_requirements,
        "planning_context": planning_context,
        "recommendation": {
            "fallback_required": recommendation["fallback_required"],
            "fallback_reason": recommendation["fallback_reason"],
            "recommended_check_ids": recommendation["recommended_check_ids"],
            "recommended_pipeline_check_ids": recommendation["recommended_pipeline_check_ids"],
            "recommended_repo_audit_check_ids": recommendation["recommended_repo_audit_check_ids"],
        },
    }


def first_failed_finish_gate_step(finish_gate_report: dict[str, Any]) -> dict[str, Any] | None:
    for step in finish_gate_report.get("commands", []) or []:
        step_dict = mapping_of(step)
        if not step_dict or step_dict.get("status") != "fail":
            continue
        return {
            "id": str(step_dict.get("id", "")),
            "label": str(step_dict.get("label", "")),
            "command": str(step_dict.get("command", "")),
            "exit_code": step_dict.get("exit_code"),
        }
    return None


def build_ai_feedback_report(
    *,
    changed_files: list[str],
    selected_surface: str,
    selected_reason: str,
    selected_command: str,
    overall_status: str,
    finish_gate_status: str,
    reports: dict[str, str],
    planning_context: dict[str, Any],
    recommendation: dict[str, Any],
    selected_result: dict[str, Any],
) -> dict[str, Any]:
    instruction_names: list[str] = []
    for item in planning_context.get("instruction_files", []) or []:
        item_dict = mapping_of(item)
        name = item_dict.get("name")
        if name:
            instruction_names.append(str(name))
    first_validation_commands = string_list(planning_context.get("first_validation_commands"))
    first_failed_step = first_failed_finish_gate_step(mapping_of(selected_result.get("finish_gate")))
    suggested_next_command = (
        str(first_failed_step.get("command", ""))
        if first_failed_step is not None and str(first_failed_step.get("command", "")).strip()
        else (first_validation_commands[0] if first_validation_commands else selected_command)
    )
    return {
        "kind": "sattlint.ai_feedback",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "changed_files": changed_files,
        "selected_surface": selected_surface,
        "selected_reason": selected_reason,
        "selected_command": selected_command,
        "overall_status": overall_status,
        "finish_gate_status": finish_gate_status,
        "primary_agent": planning_context.get("primary_agent"),
        "instruction_names": instruction_names[:3],
        "owner_test_targets": string_list(planning_context.get("owner_test_targets"))[:3],
        "first_validation_commands": first_validation_commands[:3],
        "recommended_check_ids": string_list(recommendation.get("recommended_check_ids")),
        "recommended_pipeline_check_ids": string_list(recommendation.get("recommended_pipeline_check_ids")),
        "recommended_repo_audit_check_ids": string_list(recommendation.get("recommended_repo_audit_check_ids")),
        "first_failed_step": first_failed_step,
        "suggested_next_command": suggested_next_command,
        "reports": reports,
    }
