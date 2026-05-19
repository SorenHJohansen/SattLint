"""Pipeline recommendation assembly helpers."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sattlint.devtools._pipeline_finish_gate import _build_finish_gate_commands, build_change_proof_requirements


def _pipeline_cli_owner_module() -> Any:
    from sattlint.devtools import _pipeline_cli as owner_module

    return owner_module


def build_pipeline_check_recommendations(
    *,
    profile: str,
    output_dir: Path | None,
    changed_files: Iterable[str] | None,
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module
    from sattlint.devtools import pipeline_checks

    owner_module = _pipeline_cli_owner_module()
    resolved_output_dir = (output_dir or pipeline_module.DEFAULT_OUTPUT_DIR).resolve()
    resolved_changed_files = pipeline_module.normalize_changed_files(
        pipeline_module.detect_changed_files(repo_root=pipeline_module.REPO_ROOT)
        if changed_files is None
        else changed_files
    )
    catalog = owner_module.build_pipeline_check_catalog(
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
        resolved_changed_files, pipeline_checks.PIPELINE_RECOMMENDATION_CONTROL_SURFACE_GLOBS
    ):
        fallback_required = True
        fallback_reason = "Changed files touch the pipeline control surface, so targeted Python proof is recommended instead of widening to the full supported pipeline slice."
        for entry in catalog["checks"]:
            if entry["id"] not in set(pipeline_checks.PIPELINE_RECOMMENDATION_CONTROL_SURFACE_CHECK_IDS):
                continue
            recommendation_reasons[entry["id"]] = fallback_reason

    if fallback_required and fallback_reason is not None:
        if not recommendation_reasons:
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
        "why_this_gate": owner_module._build_recommendation_why_this_gate(
            changed_files=resolved_changed_files,
            recommended_checks=recommended_checks,
            skipped_checks=skipped_checks,
        ),
    }


__all__ = ["build_pipeline_check_recommendations"]
