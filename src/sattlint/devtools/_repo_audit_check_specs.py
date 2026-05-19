"""Repo-audit check catalog and recommendation helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sattlint.devtools import pipeline as pipeline_module
from sattlint.devtools.pipeline_checks import matching_changed_files, normalize_changed_files
from sattlint.path_sanitizer import sanitize_path_for_report


def _entrypoints_module() -> Any:
    from sattlint.devtools import repo_audit_entrypoints as entrypoints_module

    return entrypoints_module


def _run_verify_recommendations_check(_context: Any) -> list[Any]:
    from sattlint.devtools import ai_work_map as ai_work_map_module

    entrypoints_module = _entrypoints_module()
    repo_audit = entrypoints_module._repo_audit_module()
    output_dir = repo_audit.DEFAULT_OUTPUT_DIR
    pipeline_catalog = pipeline_module.build_pipeline_check_catalog(
        profile="full", output_dir=output_dir / repo_audit.PIPELINE_OUTPUT_DIRNAME
    )
    repo_catalog = entrypoints_module.build_repo_audit_check_catalog(
        profile="full",
        output_dir=output_dir,
        fail_on="high",
    )
    reports = (
        entrypoints_module.verify_check_catalog(pipeline_catalog, repo_root=repo_audit.REPO_ROOT),
        entrypoints_module.verify_check_catalog(repo_catalog, repo_root=repo_audit.REPO_ROOT),
    )
    findings: list[Any] = []
    for report in reports:
        for issue in report["issues"]:
            findings.append(
                repo_audit.Finding(
                    id=f"recommendation-{issue['issue_id']}-{issue['check_id']}",
                    category="feature-wiring",
                    severity="high",
                    confidence="high",
                    message=issue["message"],
                    detail=json.dumps(issue, sort_keys=True),
                    source="verify-recommendations",
                )
            )
    generated_artifacts = (
        (
            ai_work_map_module.DEFAULT_OUTPUT_PATH,
            ai_work_map_module.render_ai_work_map(),
            "ai-work-map",
        ),
        (
            ai_work_map_module.DEFAULT_SESSION_CONTEXT_OUTPUT_PATH,
            ai_work_map_module.render_session_context_map(),
            "ai-session-context-map",
        ),
        (
            ai_work_map_module.DEFAULT_CHECK_CATALOG_OUTPUT_PATH,
            ai_work_map_module.render_ai_check_catalog(),
            "ai-check-catalog",
        ),
    )
    regenerate_command = "python -m sattlint.devtools.ai_work_map --write"
    for artifact_path, expected, artifact_id in generated_artifacts:
        actual = artifact_path.read_text(encoding="utf-8") if artifact_path.exists() else None
        if actual == expected:
            continue
        try:
            relative_path = artifact_path.relative_to(repo_audit.REPO_ROOT).as_posix()
        except ValueError:
            relative_path = artifact_path.as_posix()
        findings.append(
            repo_audit.Finding(
                id=f"recommendation-generated-artifact-drift-{artifact_id}",
                category="feature-wiring",
                severity="high",
                confidence="high",
                message=(
                    f"Checked-in generated routing artifact '{relative_path}' is stale. Regenerate with "
                    f"'{regenerate_command}'."
                ),
                detail=json.dumps(
                    {
                        "artifact_id": artifact_id,
                        "artifact_path": relative_path,
                        "regenerate_command": regenerate_command,
                    },
                    sort_keys=True,
                ),
                path=relative_path,
                source="verify-recommendations",
            )
        )
    return findings


def build_repo_audit_check_catalog(
    *,
    profile: str = "full",
    output_dir: Path | None = None,
    fail_on: str = "high",
) -> dict[str, Any]:
    entrypoints_module = _entrypoints_module()
    repo_audit = entrypoints_module._repo_audit_module()
    if profile not in repo_audit.AUDIT_PROFILE_CHOICES:
        raise ValueError(f"Unsupported audit profile: {profile}")
    resolved_output_dir = (output_dir or repo_audit.DEFAULT_OUTPUT_DIR).resolve()
    sanitized_output_dir = (
        sanitize_path_for_report(resolved_output_dir, repo_root=repo_audit.REPO_ROOT) or resolved_output_dir.as_posix()
    )
    pipeline_catalog = pipeline_module.build_pipeline_check_catalog(
        profile=profile,
        output_dir=resolved_output_dir / repo_audit.PIPELINE_OUTPUT_DIRNAME,
    )
    checks: list[dict[str, Any]] = []
    for entry in pipeline_catalog["checks"]:
        checks.append(
            {
                "id": entry["id"],
                "label": entry["label"],
                "profiles": entry["profiles"],
                "artifact_ids": entry["artifact_ids"],
                "source": "pipeline",
                "owner_surface": entry["owner_surface"],
                "estimated_cost": entry["estimated_cost"],
                "path_globs": entry["path_globs"],
                "owner_test_targets": entry["owner_test_targets"],
                "ai_summary": entry["ai_summary"],
                "ai_instruction_files": entry["ai_instruction_files"],
                "command": entry["command"],
            }
        )
    for definition in entrypoints_module._repo_audit_finding_check_definitions():
        if profile not in tuple(definition["profiles"]):
            continue
        checks.append(
            {
                "id": definition["id"],
                "label": definition["label"],
                "profiles": list(definition["profiles"]),
                "artifact_ids": [
                    "progress",
                    "status",
                    "summary",
                    "findings",
                    "summary_markdown",
                    "run_history",
                    *(["ai_gc"] if definition["id"] == "ai-gc" else []),
                ],
                "source": "repo-audit",
                "owner_surface": definition["owner_surface"],
                "estimated_cost": definition["estimated_cost"],
                "path_globs": list(definition["path_globs"]),
                "owner_test_targets": list(definition["owner_test_targets"]),
                "ai_summary": definition["ai_summary"],
                "ai_instruction_files": list(definition["ai_instruction_files"]),
                "command": (
                    f"sattlint-repo-audit --profile {profile} --check {definition['id']} --skip-pipeline "
                    f"--fail-on {fail_on} --output-dir {sanitized_output_dir}"
                ),
            }
        )
    if profile == "full":
        checks.append(
            {
                "id": "cli-consistency",
                "label": "Build the full CLI consistency report",
                "profiles": ["full"],
                "artifact_ids": [
                    "progress",
                    "status",
                    "summary",
                    "findings",
                    "summary_markdown",
                    "run_history",
                    "cli_consistency",
                ],
                "source": "repo-audit",
                "owner_surface": "cli-docs",
                "estimated_cost": "low",
                "path_globs": [
                    "README.md",
                    "CONTRIBUTING.md",
                    "docs/references/cli-commands.md",
                    "docs/references/ai-agent-reference.md",
                    "pyproject.toml",
                    "src/sattlint/cli/**",
                    "src/sattlint/app*.py",
                    "src/sattlint/devtools/repo_audit_cli.py",
                ],
                "owner_test_targets": ["tests/test_repo_audit.py"],
                "ai_summary": "Use when CLI consistency reporting or command-reference alignment changes.",
                "ai_instruction_files": [
                    ".github/instructions/cli-app.instructions.md",
                    ".github/instructions/repo-audit.instructions.md",
                ],
                "command": (
                    f"sattlint-repo-audit --profile full --check cli-consistency --skip-pipeline "
                    f"--fail-on {fail_on} --output-dir {sanitized_output_dir}"
                ),
            }
        )
    return {
        "kind": "sattlint.repo_audit.check_catalog",
        "schema_version": 1,
        "profile": profile,
        "fail_on": fail_on,
        "checks": checks,
    }


def build_repo_audit_check_recommendations(
    *,
    profile: str = "full",
    output_dir: Path | None = None,
    fail_on: str = "high",
    changed_files: Iterable[str] | None = None,
) -> dict[str, Any]:
    entrypoints_module = _entrypoints_module()
    repo_audit = entrypoints_module._repo_audit_module()
    resolved_output_dir = (output_dir or repo_audit.DEFAULT_OUTPUT_DIR).resolve()
    changed_file_list = normalize_changed_files(
        pipeline_module.detect_changed_files(repo_root=repo_audit.REPO_ROOT) if changed_files is None else changed_files
    )
    catalog = entrypoints_module.build_repo_audit_check_catalog(
        profile=profile,
        output_dir=resolved_output_dir,
        fail_on=fail_on,
    )
    fallback_required = False
    fallback_reason: str | None = None
    recommendation_reasons: dict[str, str] = {}

    if not changed_file_list:
        fallback_required = True
        fallback_reason = (
            "No changed files were provided or detected, so the full supported repo-audit profile is recommended."
        )
    elif matching_changed_files(changed_file_list, entrypoints_module.REPO_AUDIT_RECOMMENDATION_CONTROL_SURFACE_GLOBS):
        fallback_required = True
        fallback_reason = "Changed files touch the repo-audit control surface, so targeted Python proof and recommendation verification are recommended instead of widening to the full supported repo-audit profile."
        for entry in catalog["checks"]:
            if entry["id"] not in set(entrypoints_module.REPO_AUDIT_RECOMMENDATION_CONTROL_SURFACE_CHECK_IDS):
                continue
            recommendation_reasons[entry["id"]] = fallback_reason

    if fallback_required and fallback_reason is not None:
        if not recommendation_reasons:
            for entry in catalog["checks"]:
                recommendation_reasons[entry["id"]] = fallback_reason
    else:
        for entry in catalog["checks"]:
            matched_files = matching_changed_files(changed_file_list, entry["path_globs"])
            if not matched_files:
                continue
            recommendation_reasons[entry["id"]] = f"Matched {matched_files[0]} against the {entry['id']} routing globs."
        if not recommendation_reasons:
            fallback_required = True
            fallback_reason = "No audit routing globs matched the changed files, so the full supported repo-audit profile is recommended."
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

    suggested_finish_gate_commands = entrypoints_module._build_repo_audit_finish_gate_commands(
        profile=profile,
        output_dir=resolved_output_dir,
        fail_on=fail_on,
        changed_files=changed_file_list,
        recommended_checks=recommended_checks,
        ruff_command=["ruff"],
        pyright_command=["pyright"],
        python_command=["python"],
    )

    return {
        "kind": "sattlint.repo_audit.check_recommendations",
        "schema_version": 1,
        "profile": profile,
        "fail_on": fail_on,
        "changed_files": list(changed_file_list),
        "fallback_required": fallback_required,
        "fallback_reason": fallback_reason,
        "recommended_check_ids": [entry["id"] for entry in recommended_checks],
        "recommended_pipeline_check_ids": [
            entry["id"] for entry in recommended_checks if entry["source"] == "pipeline"
        ],
        "recommended_repo_audit_check_ids": [
            entry["id"] for entry in recommended_checks if entry["source"] == "repo-audit"
        ],
        "suggested_check_commands": [entry["command"] for entry in recommended_checks],
        "suggested_finish_gate_commands": [entry["command"] for entry in suggested_finish_gate_commands],
        "recommended_checks": recommended_checks,
        "skipped_checks": skipped_checks,
        "proof_requirements": pipeline_module.build_change_proof_requirements(
            changed_files=changed_file_list,
            recommended_checks=recommended_checks,
        ),
        "why_this_gate": entrypoints_module._build_recommendation_why_this_gate(
            changed_files=changed_file_list,
            recommended_checks=recommended_checks,
            skipped_checks=skipped_checks,
        ),
    }


__all__ = [
    "_run_verify_recommendations_check",
    "build_repo_audit_check_catalog",
    "build_repo_audit_check_recommendations",
]
