"""Repo-audit catalog metadata and recommendation helper builders."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from sattlint.devtools.shared.pipeline_checks import matching_changed_files, normalize_changed_files
from sattlint.path_sanitizer import sanitize_path_for_report

from ._repo_audit_strategy_registry import (
    RepoAuditRunnerMap,
    build_repo_audit_finding_runner_map,
    build_repo_audit_finding_strategies,
)

REPO_AUDIT_FINDING_CHECK_IDS = (
    "text-scan",
    "local-ci-parity",
    "documented-commands",
    "unused-config-keys",
    "architecture",
    "structural-report",
    "cli",
    "logging",
    "ai-gc",
    "ignored-repo-paths",
    "harness-freshness",
    "coverage",
    "public-readiness",
    "verify-recommendations",
)
REPO_AUDIT_SPECIAL_CHECK_IDS = ("cli-consistency",)
REPO_AUDIT_INDIVIDUAL_CHECK_IDS = REPO_AUDIT_FINDING_CHECK_IDS + REPO_AUDIT_SPECIAL_CHECK_IDS
REPO_AUDIT_RECOMMENDATION_CONTROL_SURFACE_GLOBS = (
    "pyproject.toml",
    "src/sattlint/devtools/pipeline.py",
    "src/sattlint/devtools/shared/pipeline_checks.py",
    "src/sattlint/devtools/audit/repo_audit.py",
    "src/sattlint/devtools/audit/repo_audit_cli.py",
    "src/sattlint/devtools/audit/repo_audit_entrypoints.py",
)
REPO_AUDIT_RECOMMENDATION_CONTROL_SURFACE_CHECK_IDS = ("ruff", "pyright", "pytest", "verify-recommendations")
REPO_AUDIT_RECOMMENDATION_FALLBACK_GLOBS = REPO_AUDIT_RECOMMENDATION_CONTROL_SURFACE_GLOBS
AI_FEEDBACK_FILENAME = "ai_feedback.json"


def build_repo_audit_finding_check_definitions(
    *,
    verify_recommendations_runner: Callable[[Any], list[Any]] | None = None,
    runners: RepoAuditRunnerMap | None = None,
    runner_overrides: RepoAuditRunnerMap | None = None,
) -> tuple[dict[str, Any], ...]:
    resolved_runners = runners
    if resolved_runners is None:
        if verify_recommendations_runner is None:
            raise TypeError("verify_recommendations_runner is required when runners are not provided")
        resolved_runners = build_repo_audit_finding_runner_map(
            verify_recommendations_runner=verify_recommendations_runner,
            runner_overrides=runner_overrides,
        )
    return tuple(strategy.to_definition() for strategy in build_repo_audit_finding_strategies(runners=resolved_runners))


def build_repo_audit_finish_gate_commands(
    *,
    profile: str,
    output_dir: Path,
    fail_on: str,
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
    ruff_command: list[str],
    pyright_command: list[str],
    python_command: list[str],
    repo_root: Path,
    changed_file_flag_args: Callable[[Iterable[str]], list[str]],
    focused_python_files: Callable[[Iterable[str]], list[str]],
    build_owner_pytest_step: Callable[..., dict[str, Any] | None],
    shell_command: Callable[[list[str]], str],
    pytest_workers: str | None = None,
) -> list[dict[str, Any]]:
    normalized_changed_files = normalize_changed_files(changed_files)
    commands: list[dict[str, Any]] = []
    finish_gate_argv = [
        "sattlint-repo-audit",
        "--profile",
        profile,
        "--run-recommended-finish-gate",
        *changed_file_flag_args(normalized_changed_files),
        "--fail-on",
        fail_on,
        "--output-dir",
        sanitize_path_for_report(output_dir.resolve(), repo_root=repo_root) or output_dir.resolve().as_posix(),
    ]
    if pytest_workers is not None and str(pytest_workers).strip():
        finish_gate_argv.extend(["--pytest-workers", str(pytest_workers).strip()])
    commands.append(
        {
            "id": "recommended-finish-gate",
            "label": "Run the recommended repo-audit finish gate",
            "command": shell_command(finish_gate_argv),
            "argv": finish_gate_argv,
        }
    )
    touched_python_files = focused_python_files(normalized_changed_files)
    if touched_python_files:
        ruff_argv = [*ruff_command, "check", *touched_python_files]
        pyright_argv = [*pyright_command, *touched_python_files]
        commands.append(
            {
                "id": "ruff-touched-python",
                "label": "Run Ruff on touched Python files",
                "command": shell_command(ruff_argv),
                "argv": ruff_argv,
            }
        )
        commands.append(
            {
                "id": "pyright-touched-python",
                "label": "Run Pyright on touched Python files",
                "command": shell_command(pyright_argv),
                "argv": pyright_argv,
            }
        )
    coverage_output_path = output_dir / "coverage_proof.xml"
    owner_pytest_step = build_owner_pytest_step(
        changed_files=normalized_changed_files,
        recommended_checks=recommended_checks,
        python_command=python_command,
        coverage_output_path=coverage_output_path,
        pytest_workers=pytest_workers,
    )
    if owner_pytest_step is not None:
        commands.append(owner_pytest_step)
    return commands


def build_recommendation_why_this_gate(
    *,
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
    skipped_checks: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    normalized_changed_files = normalize_changed_files(changed_files)
    matched_routes: list[dict[str, Any]] = []
    for entry in recommended_checks:
        matched_routes.append(
            {
                "check_id": entry["id"],
                "source": entry["source"],
                "owner_surface": entry["owner_surface"],
                "matched_files": matching_changed_files(normalized_changed_files, entry["path_globs"]),
                "path_globs": entry["path_globs"],
                "reason": entry["reason"],
            }
        )
    return {
        "changed_files": normalized_changed_files,
        "matched_routes": matched_routes,
        "skipped_checks": list(skipped_checks),
    }


__all__ = [
    "AI_FEEDBACK_FILENAME",
    "REPO_AUDIT_FINDING_CHECK_IDS",
    "REPO_AUDIT_INDIVIDUAL_CHECK_IDS",
    "REPO_AUDIT_RECOMMENDATION_CONTROL_SURFACE_CHECK_IDS",
    "REPO_AUDIT_RECOMMENDATION_CONTROL_SURFACE_GLOBS",
    "REPO_AUDIT_RECOMMENDATION_FALLBACK_GLOBS",
    "REPO_AUDIT_SPECIAL_CHECK_IDS",
    "build_recommendation_why_this_gate",
    "build_repo_audit_finding_check_definitions",
    "build_repo_audit_finding_runner_map",
    "build_repo_audit_finish_gate_commands",
]
