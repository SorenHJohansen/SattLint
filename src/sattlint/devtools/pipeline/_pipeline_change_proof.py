"""Change-scoped proof helpers for pipeline and repo-audit finish gates."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sattlint.devtools.json_helpers import json_mapping as _json_mapping
from sattlint.path_sanitizer import sanitize_path_for_report


def _mutation_guidance(changed_files: Iterable[str]) -> dict[str, Any]:
    from sattlint.devtools._portable_command_text import pytest_command  # noqa: PLC0415

    from .. import pipeline as pipeline_module  # noqa: PLC0415

    normalized_changed_files = pipeline_module.normalize_changed_files(changed_files)
    matched_surfaces: list[str] = []
    suggested_commands: list[str] = []
    rules = (
        (
            "parser",
            ("src/sattlint/grammar/", "src/sattlint/transformer/", "src/sattlint/models/ast_model.py"),
            pytest_command(
                "--no-cov",
                "tests/test_ast_tools.py",
                "tests/analyzers/test_cyclomatic_complexity.py",
                "-x",
                "-q",
                "--tb=short",
            ),
        ),
        (
            "validation",
            (
                "src/sattlint/validation.py",
                "src/sattlint/_validation",
            ),
            pytest_command("--no-cov", "tests/test_cli.py", "-x", "-q", "--tb=short"),
        ),
        (
            "routing",
            (
                "src/sattlint/devtools/pipeline.py",
                "src/sattlint/devtools/shared/pipeline_checks.py",
                "src/sattlint/devtools/repo_audit.py",
                "src/sattlint/devtools/repo_audit_cli.py",
                "src/sattlint/devtools/repo_audit_entrypoints.py",
                "src/sattlint/devtools/ai_work_map.py",
                "tests/test_recommendation_routing.py",
            ),
            pytest_command(
                "--no-cov",
                "tests/test_pipeline_run.py",
                "tests/test_repo_audit_part8.py",
                "tests/test_recommendation_routing.py",
                "-x",
                "-q",
                "--tb=short",
            ),
        ),
    )
    for surface_name, prefixes, command in rules:
        if not any(path_text.startswith(prefix) for prefix in prefixes for path_text in normalized_changed_files):
            continue
        matched_surfaces.append(surface_name)
        if command not in suggested_commands:
            suggested_commands.append(command)

    if not matched_surfaces:
        return {
            "status": "not-applicable",
            "critical_surfaces": [],
            "suggested_commands": [],
            "suggestion": None,
        }
    return {
        "status": "advisory",
        "critical_surfaces": matched_surfaces,
        "suggested_commands": suggested_commands,
        "suggestion": (
            "Prefer mutation-style or property-style assertions for parser, validation, and routing seams before "
            "treating the repo-wide coverage percentage as sufficient proof."
        ),
    }


def _changed_source_python_files(changed_files: Iterable[str]) -> list[str]:
    return [path_text for path_text in changed_files if path_text.endswith(".py") and path_text.startswith("src/")]


def build_change_proof_requirements(
    *,
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    from .. import pipeline as pipeline_module  # noqa: PLC0415
    from . import _pipeline_finish_gate as finish_gate_module  # noqa: PLC0415

    normalized_changed_files = pipeline_module.normalize_changed_files(changed_files)
    owner_test_targets = finish_gate_module.owner_test_targets_for_checks(recommended_checks)
    touched_python_files = finish_gate_module.focused_python_files(normalized_changed_files)
    touched_source_files = _changed_source_python_files(touched_python_files)
    focused_behavior_required = bool(touched_python_files)
    focused_behavior_status = "satisfied" if (not focused_behavior_required or owner_test_targets) else "missing"
    return {
        "focused_behavior_test": {
            "required": focused_behavior_required,
            "status": focused_behavior_status,
            "owner_test_targets": owner_test_targets,
            "reason": (
                "Code changes require at least one focused owner pytest target."
                if focused_behavior_required
                else "No changed Python files require a focused owner pytest target."
            ),
        },
        "coverage": {
            "required": bool(touched_source_files),
            "preferred_mode": "changed-lines" if touched_source_files else None,
            "fallback_mode": "touched-files" if touched_source_files else None,
            "touched_source_files": touched_source_files,
            "reason": (
                "Touched source files should be proven by focused changed-line coverage when executable diff lines "
                "exist, or touched-file coverage otherwise."
                if touched_source_files
                else "No changed source files require focused coverage proof."
            ),
        },
        "mutation_guidance": _mutation_guidance(normalized_changed_files),
    }


def evaluate_change_scoped_coverage_proof(
    *,
    repo_root: Path,
    coverage_output_path: Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    from .. import pipeline as pipeline_module  # noqa: PLC0415

    report = pipeline_module.build_coverage_summary_report(
        repo_root,
        coverage_path=coverage_output_path,
        changed_files=changed_files,
    )
    change_scoped = dict(report["change_scoped"])
    change_scoped["coverage_path"] = (
        sanitize_path_for_report(coverage_output_path.resolve(), repo_root=repo_root)
        or coverage_output_path.resolve().as_posix()
    )
    return change_scoped


def compact_pipeline_summary_timing(pipeline_summary: dict[str, Any] | None) -> dict[str, Any]:
    if pipeline_summary is None:
        return {}
    mapping = _json_mapping(pipeline_summary)
    if mapping is None:
        return {}
    return dict(mapping.get("timing") or {})


__all__ = [
    "build_change_proof_requirements",
    "compact_pipeline_summary_timing",
    "evaluate_change_scoped_coverage_proof",
]
