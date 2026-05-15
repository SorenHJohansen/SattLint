"""Repo-audit catalog metadata and recommendation helper builders."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from sattlint.devtools.pipeline_checks import matching_changed_files, normalize_changed_files
from sattlint.path_sanitizer import sanitize_path_for_report

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
    "src/sattlint/devtools/pipeline_checks.py",
    "src/sattlint/devtools/repo_audit.py",
    "src/sattlint/devtools/repo_audit_cli.py",
    "src/sattlint/devtools/repo_audit_entrypoints.py",
)
REPO_AUDIT_RECOMMENDATION_CONTROL_SURFACE_CHECK_IDS = ("ruff", "pyright", "pytest", "verify-recommendations")
REPO_AUDIT_RECOMMENDATION_FALLBACK_GLOBS = REPO_AUDIT_RECOMMENDATION_CONTROL_SURFACE_GLOBS
AI_FEEDBACK_FILENAME = "ai_feedback.json"


def _ai_metadata(summary: str, *instruction_files: str) -> dict[str, Any]:
    return {
        "ai_summary": summary,
        "ai_instruction_files": instruction_files,
    }


def build_repo_audit_finding_check_definitions(
    *,
    repo_audit: Any,
    verify_recommendations_runner: Callable[[Any], list[Any]],
) -> tuple[dict[str, Any], ...]:
    return (
        {
            "id": "text-scan",
            "label": "Scan repository text for leaks and local paths",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_text_scan_check,
            "owner_surface": "text-scan",
            "estimated_cost": "low",
            "path_globs": (
                "README.md",
                "CONTRIBUTING.md",
                "SECURITY.md",
                "docs/**",
                ".github/**",
                "src/**/*.py",
                "tests/**/*.py",
                "scripts/**/*.py",
                "pyproject.toml",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
            **_ai_metadata(
                "Use when documentation or Python sources may have leaked local paths, secrets, or unsafe text.",
                ".github/instructions/repo-audit.instructions.md",
            ),
        },
        {
            "id": "local-ci-parity",
            "label": "Detect local-versus-CI parity drift in paths, test guards, and local dependency roots",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_local_ci_parity_check,
            "owner_surface": "local-ci-parity",
            "estimated_cost": "low",
            "path_globs": (
                "README.md",
                "CONTRIBUTING.md",
                "SECURITY.md",
                "docs/**",
                ".github/**",
                "src/**/*.py",
                "tests/**/*.py",
                "scripts/**/*.py",
                "pyproject.toml",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
            **_ai_metadata(
                "Use when changes may rely on local-only paths, guards, or machine-specific assumptions.",
                ".github/instructions/repo-audit.instructions.md",
            ),
        },
        {
            "id": "documented-commands",
            "label": "Check documented commands against implemented CLI surfaces",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_documented_commands_check,
            "owner_surface": "cli-docs",
            "estimated_cost": "low",
            "path_globs": (
                "README.md",
                "CONTRIBUTING.md",
                "docs/references/cli-commands.md",
                "docs/references/ai-agent-reference.md",
                "pyproject.toml",
                "src/sattlint/cli/**",
                "src/sattlint/app*.py",
                "src/sattlint/devtools/repo_audit_cli.py",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
            **_ai_metadata(
                "Use when CLI help, command docs, or agent reference commands must stay in sync with implementation.",
                ".github/instructions/cli-app.instructions.md",
                ".github/instructions/repo-audit.instructions.md",
            ),
        },
        {
            "id": "unused-config-keys",
            "label": "Report declared but unused config keys",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_unused_config_keys_check,
            "owner_surface": "config",
            "estimated_cost": "low",
            "path_globs": (
                "pyproject.toml",
                "src/sattlint/config.py",
                "src/sattlint/**/*.py",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
            **_ai_metadata(
                "Use when config declarations or config consumers change and unused keys may drift.",
                ".github/instructions/cli-app.instructions.md",
            ),
        },
        {
            "id": "architecture",
            "label": "Run repository architecture checks",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_architecture_check,
            "owner_surface": "architecture",
            "estimated_cost": "medium",
            "path_globs": (
                "src/**",
                "tests/**",
                "pyproject.toml",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
            **_ai_metadata(
                "Use when Python architecture, import layering, or module-size constraints may shift.",
                ".github/instructions/repo-audit.instructions.md",
            ),
        },
        {
            "id": "structural-report",
            "label": "Translate structural report findings into repo-audit findings",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_structural_report_check,
            "owner_surface": "structural",
            "estimated_cost": "medium",
            "path_globs": (
                "src/**",
                "tests/**",
                "artifacts/analysis/structural_budget_ratchet.json",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
            **_ai_metadata(
                "Use when structural budget artifacts or their translation into findings may change.",
                ".github/instructions/repo-audit.instructions.md",
            ),
        },
        {
            "id": "cli",
            "label": "Validate CLI descriptions and subcommand help",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_cli_check,
            "owner_surface": "cli",
            "estimated_cost": "low",
            "path_globs": (
                "pyproject.toml",
                "src/sattlint/cli/**",
                "src/sattlint/app*.py",
                "src/sattlint/devtools/repo_audit_cli.py",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
            **_ai_metadata(
                "Use when CLI parser descriptions, subcommand help, or interactive command surfaces change.",
                ".github/instructions/cli-app.instructions.md",
            ),
        },
        {
            "id": "logging",
            "label": "Check library modules for unexpected print calls",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_logging_check,
            "owner_surface": "logging",
            "estimated_cost": "low",
            "path_globs": ("src/**/*.py",),
            "owner_test_targets": ("tests/test_repo_audit.py",),
            **_ai_metadata(
                "Use when library code changes may introduce unexpected prints or weak failure-path diagnostics.",
                ".github/instructions/repo-audit.instructions.md",
            ),
        },
        {
            "id": "ai-gc",
            "label": "Report stale AI-generated artifacts and oversized local coordination state",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_ai_gc_check,
            "owner_surface": "ai-hygiene",
            "estimated_cost": "low",
            "path_globs": (
                "artifacts/**",
                "docs/generated/**",
                ".github/coordination/current-work.template.md",
                "src/sattlint/devtools/ai_gc.py",
                "src/sattlint/devtools/repo_audit.py",
                "src/sattlint/devtools/repo_audit_cli.py",
                "src/sattlint/devtools/repo_audit_entrypoints.py",
                "tests/test_repo_audit.py",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
            **_ai_metadata(
                "Use when AI-generated artifacts, coordination state, or related cleanup policy changes.",
                ".github/instructions/agent-customizations.instructions.md",
                ".github/instructions/repo-audit.instructions.md",
            ),
        },
        {
            "id": "ignored-repo-paths",
            "label": "Detect ignored repo-local dependency references",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_ignored_repo_paths_check,
            "owner_surface": "path-safety",
            "estimated_cost": "low",
            "path_globs": (
                "src/**/*.py",
                "tests/**/*.py",
                "scripts/**/*.py",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
            **_ai_metadata(
                "Use when repo-local ignored paths or hidden dependency roots may leak into tracked code.",
                ".github/instructions/repo-audit.instructions.md",
            ),
        },
        {
            "id": "harness-freshness",
            "label": "Enforce AI harness freshness for instructions, agents, links, and generated maps",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_harness_freshness_check,
            "owner_surface": "harness-freshness",
            "estimated_cost": "low",
            "path_globs": (
                "AGENTS.md",
                ".github/agents/**",
                ".github/instructions/**",
                ".github/skills/**",
                "docs/context-loading-order.md",
                "docs/design-docs/core-beliefs.md",
                "docs/references/ai-agent-reference.md",
                "src/sattlint/devtools/ai_work_map.py",
                "src/sattlint/devtools/doc_gardener.py",
                "src/sattlint/devtools/repo_audit.py",
                "src/sattlint/devtools/repo_audit_entrypoints.py",
                "tests/test_ai_work_map.py",
                "tests/test_repo_audit.py",
            ),
            "owner_test_targets": ("tests/test_ai_work_map.py", "tests/test_repo_audit.py"),
            **_ai_metadata(
                "Use when AI instructions, agents, generated routing maps, or other AI-control surfaces change.",
                ".github/instructions/agent-customizations.instructions.md",
                ".github/instructions/repo-audit.instructions.md",
            ),
        },
        {
            "id": "coverage",
            "label": "Translate low-coverage modules into audit findings",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_coverage_check,
            "owner_surface": "coverage",
            "estimated_cost": "low",
            "path_globs": (
                "tests/**",
                "coverage.xml",
                "pyproject.toml",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
            **_ai_metadata(
                "Use when coverage artifacts or audit-facing coverage recommendations may change.",
                ".github/instructions/repo-audit.instructions.md",
            ),
        },
        {
            "id": "public-readiness",
            "label": "Check public-repository readiness files and metadata",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_public_readiness_check,
            "owner_surface": "public-readiness",
            "estimated_cost": "low",
            "path_globs": (
                "README.md",
                "CONTRIBUTING.md",
                "SECURITY.md",
                "LICENSE",
                ".github/**",
                "docs/**",
                "pyproject.toml",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
            **_ai_metadata(
                "Use when top-level repo hygiene, public metadata, or publish-facing docs may drift.",
                ".github/instructions/repo-audit.instructions.md",
            ),
        },
        {
            "id": "verify-recommendations",
            "label": "Verify recommendation metadata and routing catalog coverage",
            "profiles": ("quick", "full"),
            "runner": verify_recommendations_runner,
            "owner_surface": "recommendations",
            "estimated_cost": "low",
            "path_globs": (
                "src/sattlint/devtools/pipeline.py",
                "src/sattlint/devtools/pipeline_checks.py",
                "src/sattlint/devtools/repo_audit.py",
                "src/sattlint/devtools/repo_audit_cli.py",
                "src/sattlint/devtools/repo_audit_entrypoints.py",
                "tests/test_pipeline_run.py",
                "tests/test_repo_audit.py",
                "tests/test_recommendation_routing.py",
                "docs/references/cli-commands.md",
                "docs/references/ai-agent-reference.md",
            ),
            "owner_test_targets": (
                "tests/test_pipeline_run.py",
                "tests/test_repo_audit.py",
                "tests/test_recommendation_routing.py",
            ),
            **_ai_metadata(
                "Use when routing catalogs, recommendation metadata, or generated AI registry outputs change.",
                ".github/instructions/agent-customizations.instructions.md",
                ".github/instructions/repo-audit.instructions.md",
            ),
        },
    )


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
    ratchet_policy_argv = [*python_command, "scripts/check_ratchet_policy.py"]
    commands.append(
        {
            "id": "ratchet-policy",
            "label": "Run ratchet policy",
            "command": shell_command(ratchet_policy_argv),
            "argv": ratchet_policy_argv,
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
    "build_repo_audit_finish_gate_commands",
]
