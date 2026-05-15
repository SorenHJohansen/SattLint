"""Machine-readable stdout compaction helpers for repo_audit CLI entrypoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sattlint.path_sanitizer import sanitize_path_for_report

MAX_STDOUT_CHANGED_FILE_PREVIEW = 12
MAX_STDOUT_ITEM_PREVIEW = 8
MAX_STDOUT_COMMAND_LENGTH = 220
STDOUT_COMMAND_HEAD_LENGTH = 160
STDOUT_COMMAND_TAIL_LENGTH = 40


def latest_report_links(
    current_output_dir: Path, *, default_output_dir: Path, repo_root: Path
) -> tuple[str | None, str | None]:
    if current_output_dir == default_output_dir:
        return None, None
    sanitized = sanitize_path_for_report(default_output_dir, repo_root=repo_root) or default_output_dir.as_posix()
    return f"{sanitized}/status.json", f"{sanitized}/summary.json"


def compact_command(command: object) -> tuple[str | None, bool]:
    text = str(command or "").strip()
    if not text:
        return None, False
    if len(text) <= MAX_STDOUT_COMMAND_LENGTH:
        return text, False
    head = text[:STDOUT_COMMAND_HEAD_LENGTH].rstrip()
    tail = text[-STDOUT_COMMAND_TAIL_LENGTH:].lstrip()
    return f"{head} ... {tail}", True


def changed_file_preview(changed_files: object) -> dict[str, Any]:
    paths = [str(item) for item in cast(list[object], changed_files)] if isinstance(changed_files, list) else []
    preview = paths[:MAX_STDOUT_CHANGED_FILE_PREVIEW]
    return {
        "preview": preview,
        "count": len(paths),
        "truncated": len(paths) > len(preview),
        "overflow_count": max(0, len(paths) - len(preview)),
    }


def string_list_preview(items: object, *, max_items: int = MAX_STDOUT_ITEM_PREVIEW) -> dict[str, Any]:
    values = [str(item) for item in cast(list[object], items)] if isinstance(items, list) else []
    preview = values[:max_items]
    return {
        "preview": preview,
        "count": len(values),
        "truncated": len(values) > len(preview),
        "overflow_count": max(0, len(values) - len(preview)),
    }


def compact_command_list(commands: object, *, max_items: int = MAX_STDOUT_ITEM_PREVIEW) -> dict[str, Any]:
    values = cast(list[object], commands) if isinstance(commands, list) else []
    preview: list[str] = []
    truncated_command_count = 0
    for command in values[:max_items]:
        compacted, was_truncated = compact_command(command)
        if compacted is None:
            continue
        preview.append(compacted)
        if was_truncated:
            truncated_command_count += 1
    return {
        "preview": preview,
        "count": len(values),
        "truncated": len(values) > len(preview),
        "overflow_count": max(0, len(values) - len(preview)),
        "truncated_command_count": truncated_command_count,
    }


def apply_preview_fields(payload: dict[str, Any], key: str, preview: dict[str, Any]) -> None:
    payload[key] = preview["preview"]
    payload[f"{key[:-1]}_count" if key.endswith("s") else f"{key}_count"] = preview["count"]
    if preview["truncated"]:
        payload[f"{key}_truncated"] = True
        payload[f"{key}_overflow_count"] = preview["overflow_count"]


def compact_instruction_names(planning_context: dict[str, Any]) -> list[str]:
    instruction_files = planning_context.get("instruction_files")
    if not isinstance(instruction_files, list):
        return []
    instruction_file_items = list(cast(list[object], instruction_files))
    names: list[str] = []
    for item in instruction_file_items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name is not None:
            names.append(str(name))
    return names


def compact_blocking_invariants(planning_context: dict[str, Any]) -> list[dict[str, str]]:
    invariants = planning_context.get("blocking_invariants")
    if not isinstance(invariants, list):
        return []
    invariant_items = list(cast(list[object], invariants))
    compacted: list[dict[str, str]] = []
    for item in invariant_items[:MAX_STDOUT_ITEM_PREVIEW]:
        if not isinstance(item, dict):
            continue
        entry: dict[str, str] = {}
        for key in ("id", "summary"):
            value = item.get(key)
            if value is not None:
                entry[key] = str(value)
        if entry:
            compacted.append(entry)
    return compacted


def compact_finish_gate(finish_gate: object) -> dict[str, Any] | None:
    if not isinstance(finish_gate, dict):
        return None
    finish_gate_dict = cast(dict[str, object], finish_gate)
    payload: dict[str, Any] = {}
    for key in ("selected_surface", "output_dir", "description"):
        value = finish_gate_dict.get(key)
        if value is not None:
            payload[key] = value
    command, command_truncated = compact_command(finish_gate_dict.get("command"))
    if command is not None:
        payload["command"] = command
    if command_truncated:
        payload["command_truncated"] = True
    for key in ("commands", "owner_test_targets", "recommended_check_ids", "includes"):
        preview = (
            compact_command_list(finish_gate_dict.get(key))
            if key == "commands"
            else string_list_preview(finish_gate_dict.get(key))
        )
        if preview["count"] == 0 and not preview["preview"]:
            continue
        apply_preview_fields(payload, key, preview)
        if key == "commands" and preview["truncated_command_count"]:
            payload["commands_with_truncated_text"] = preview["truncated_command_count"]
    return payload


def compact_proof_requirements(proof_requirements: object) -> dict[str, Any] | None:
    if not isinstance(proof_requirements, dict):
        return None
    requirements = cast(dict[str, object], proof_requirements)
    payload: dict[str, Any] = {}
    for section_name in ("focused_behavior_test", "coverage", "mutation_guidance"):
        section = requirements.get(section_name)
        if not isinstance(section, dict):
            continue
        section_dict = cast(dict[str, object], section)
        compacted: dict[str, Any] = {}
        for key in ("required", "status", "reason", "preferred_mode", "fallback_mode", "suggestion"):
            value = section_dict.get(key)
            if value is not None:
                compacted[key] = value
        for key in ("owner_test_targets", "critical_surfaces", "suggested_commands", "touched_source_files"):
            if key not in section_dict:
                continue
            preview = (
                compact_command_list(section_dict.get(key))
                if key == "suggested_commands"
                else string_list_preview(section_dict.get(key))
            )
            if preview["count"] == 0 and not preview["preview"]:
                continue
            apply_preview_fields(compacted, key, preview)
            if key == "suggested_commands" and preview["truncated_command_count"]:
                compacted["suggested_commands_with_truncated_text"] = preview["truncated_command_count"]
        if compacted:
            payload[section_name] = compacted
    return payload


def build_recommend_checks_stdout_report(report: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in (
        "kind",
        "schema_version",
        "profile",
        "fail_on",
        "fallback_required",
        "fallback_reason",
        "recommended_check_ids",
        "recommended_pipeline_check_ids",
        "recommended_repo_audit_check_ids",
    ):
        value = report.get(key)
        if value is not None:
            payload[key] = value
    if "changed_files" in report:
        apply_preview_fields(payload, "changed_files", changed_file_preview(report.get("changed_files")))
    for key in ("suggested_check_commands", "suggested_finish_gate_commands"):
        if key not in report:
            continue
        preview = compact_command_list(report.get(key))
        if preview["count"] == 0 and not preview["preview"]:
            continue
        apply_preview_fields(payload, key, preview)
        if preview["truncated_command_count"]:
            payload[f"{key}_with_truncated_text"] = preview["truncated_command_count"]
    proof_requirements = compact_proof_requirements(report.get("proof_requirements"))
    if proof_requirements is not None:
        payload["proof_requirements"] = proof_requirements
    return payload


def build_planning_context_stdout_report(report: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in (
        "kind",
        "schema_version",
        "generated_by",
        "default_entrypoint",
        "profile",
        "fail_on",
        "output_dir",
        "owning_surface",
        "selected_surface",
        "selected_reason",
    ):
        value = report.get(key)
        if value is not None:
            payload[key] = value
    if "changed_files" in report:
        apply_preview_fields(payload, "changed_files", changed_file_preview(report.get("changed_files")))
    recommendation = report.get("recommendation") if isinstance(report.get("recommendation"), dict) else None
    if recommendation is not None:
        compacted_recommendation: dict[str, Any] = {}
        for key in (
            "fallback_required",
            "fallback_reason",
            "recommended_check_ids",
            "recommended_pipeline_check_ids",
            "recommended_repo_audit_check_ids",
        ):
            value = recommendation.get(key)
            if value is not None:
                compacted_recommendation[key] = value
        if compacted_recommendation:
            payload["recommendation"] = compacted_recommendation
    proof_requirements = compact_proof_requirements(report.get("proof_requirements"))
    if proof_requirements is not None:
        payload["proof_requirements"] = proof_requirements
    planning_context = report.get("planning_context") if isinstance(report.get("planning_context"), dict) else None
    if planning_context is not None:
        compacted_context: dict[str, Any] = {}
        for key in ("primary_agent",):
            value = planning_context.get(key)
            if value is not None:
                compacted_context[key] = value
        for key in ("owner_surfaces", "owner_test_targets", "first_validation_commands"):
            if key not in planning_context:
                continue
            preview = (
                compact_command_list(planning_context.get(key))
                if key == "first_validation_commands"
                else string_list_preview(planning_context.get(key))
            )
            if preview["count"] == 0 and not preview["preview"]:
                continue
            apply_preview_fields(compacted_context, key, preview)
            if key == "first_validation_commands" and preview["truncated_command_count"]:
                compacted_context["first_validation_commands_with_truncated_text"] = preview["truncated_command_count"]
        instruction_names = compact_instruction_names(planning_context)
        if instruction_names:
            apply_preview_fields(compacted_context, "instruction_names", string_list_preview(instruction_names))
        blocking_invariants = compact_blocking_invariants(planning_context)
        if blocking_invariants:
            compacted_context["blocking_invariants"] = blocking_invariants
            if isinstance(planning_context.get("blocking_invariants"), list) and len(
                planning_context["blocking_invariants"]
            ) > len(blocking_invariants):
                compacted_context["blocking_invariants_truncated"] = True
        finish_gate = compact_finish_gate(planning_context.get("finish_gate"))
        if finish_gate is not None:
            compacted_context["finish_gate"] = finish_gate
        if compacted_context:
            payload["planning_context"] = compacted_context
    finish_gate = compact_finish_gate(report.get("finish_gate"))
    if finish_gate is not None:
        payload["finish_gate"] = finish_gate
    return payload


def compact_failed_step(step: object) -> dict[str, Any] | None:
    if not isinstance(step, dict):
        return None
    step_dict = cast(dict[str, object], step)
    payload: dict[str, object] = {
        "id": step_dict.get("id"),
        "label": step_dict.get("label"),
        "exit_code": step_dict.get("exit_code"),
    }
    command, truncated = compact_command(step_dict.get("command"))
    if command is not None:
        payload["command"] = command
    if truncated:
        payload["command_truncated"] = True
    return payload


def build_check_my_changes_stdout_report(report: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in (
        "kind",
        "schema_version",
        "generated_by",
        "profile",
        "fail_on",
        "output_dir",
        "report_path",
        "selected_surface",
        "selected_reason",
        "overall_status",
        "finish_gate_status",
        "reports",
    ):
        value = report.get(key)
        if value is not None:
            payload[key] = value
    if "changed_files" in report:
        preview = changed_file_preview(report.get("changed_files"))
        payload["changed_files"] = preview["preview"]
        payload["changed_file_count"] = preview["count"]
        if preview["truncated"]:
            payload["changed_files_truncated"] = True
            payload["changed_file_overflow_count"] = preview["overflow_count"]
    selected_command, selected_command_truncated = compact_command(report.get("selected_command"))
    if selected_command is not None:
        payload["selected_command"] = selected_command
    if selected_command_truncated:
        payload["selected_command_truncated"] = True
    recommendation = report.get("recommendation") if isinstance(report.get("recommendation"), dict) else None
    if recommendation is not None:
        recommended_check_ids = recommendation.get("recommended_check_ids")
        if isinstance(recommended_check_ids, list):
            payload["recommended_check_ids"] = recommended_check_ids
    ai_feedback = report.get("ai_feedback") if isinstance(report.get("ai_feedback"), dict) else None
    if ai_feedback is not None:
        first_failed_step = compact_failed_step(ai_feedback.get("first_failed_step"))
        if first_failed_step is not None:
            payload["first_failed_step"] = first_failed_step
        suggested_next_command, suggested_next_command_truncated = compact_command(
            ai_feedback.get("suggested_next_command")
        )
        if suggested_next_command is not None:
            payload["suggested_next_command"] = suggested_next_command
        if suggested_next_command_truncated:
            payload["suggested_next_command_truncated"] = True
    return payload


__all__ = [
    "build_check_my_changes_stdout_report",
    "build_planning_context_stdout_report",
    "build_recommend_checks_stdout_report",
    "changed_file_preview",
    "compact_failed_step",
    "compact_finish_gate",
    "compact_proof_requirements",
    "latest_report_links",
]
