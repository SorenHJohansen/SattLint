"""Reusable pipeline check catalog and selection helpers."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from sattlint.path_sanitizer import sanitize_path_for_report


def _ai_metadata(summary: str, *instruction_files: str) -> dict[str, Any]:
    return {
        "ai_summary": summary,
        "ai_instruction_files": instruction_files,
    }


PIPELINE_CHECK_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "ruff",
        "label": "Run Ruff",
        "profiles": ("quick", "full"),
        "artifact_ids": ("ruff",),
        "owner_surface": "python-style",
        "estimated_cost": "low",
        "path_globs": ("src/**/*.py", "tests/**/*.py", "scripts/**/*.py", "pyproject.toml"),
        "owner_test_targets": ("tests/test_pipeline_run.py",),
        **_ai_metadata(
            "Use after touched Python edits for fast style, import-order, and lint hygiene proof.",
            ".github/instructions/sattline-invariants.instructions.md",
        ),
    },
    {
        "id": "pyright",
        "label": "Run pyright",
        "profiles": ("quick", "full"),
        "artifact_ids": ("pyright",),
        "owner_surface": "python-types",
        "estimated_cost": "low",
        "path_globs": ("src/**/*.py", "tests/**/*.py", "scripts/**/*.py", "pyrightconfig.json", "pyproject.toml"),
        "owner_test_targets": ("tests/test_pipeline_run.py",),
        **_ai_metadata(
            "Use when touched Python files need static type proof before widening to broader finish gates.",
            ".github/instructions/sattline-invariants.instructions.md",
        ),
    },
    {
        "id": "pytest",
        "label": "Run pytest",
        "profiles": ("quick", "full"),
        "artifact_ids": ("pytest",),
        "owner_surface": "python-tests",
        "estimated_cost": "medium",
        "path_globs": ("src/**/*.py", "tests/**/*.py", "pyproject.toml"),
        "owner_test_targets": ("tests/test_pipeline_run.py", "tests/test_pipeline_run_recommendations.py"),
        **_ai_metadata(
            "Use targeted owner pytest first for behavior proof on Python changes.",
            ".github/instructions/sattline-invariants.instructions.md",
            ".github/instructions/python-tests.instructions.md",
        ),
    },
    {
        "id": "vulture",
        "label": "Run Vulture",
        "profiles": ("full",),
        "artifact_ids": ("vulture",),
        "owner_surface": "dead-code",
        "estimated_cost": "medium",
        "path_globs": ("src/**/*.py", "tests/**/*.py", "scripts/**/*.py", "pyproject.toml"),
        "owner_test_targets": ("tests/test_pipeline_run.py",),
        **_ai_metadata(
            "Use when dead-code proof is relevant for Python infra or audit-facing changes.",
            ".github/instructions/repo-audit.instructions.md",
        ),
    },
    {
        "id": "bandit",
        "label": "Run Bandit",
        "profiles": ("full",),
        "artifact_ids": ("bandit",),
        "owner_surface": "security",
        "estimated_cost": "medium",
        "path_globs": ("src/**/*.py", "tests/**/*.py", "scripts/**/*.py", "pyproject.toml"),
        "owner_test_targets": ("tests/test_pipeline_run.py",),
        **_ai_metadata(
            "Use when security-sensitive Python edits need static security scan proof.",
            ".github/instructions/repo-audit.instructions.md",
        ),
    },
    {
        "id": "structural-reports",
        "label": "Collect structural reports",
        "profiles": ("full",),
        "artifact_ids": (
            "architecture",
            "analyzer_registry",
            "dependency_graph",
            "call_graph",
            "graphics_layout",
            "impact_analysis",
            "sattline_semantic",
            "rule_metrics",
            "coverage_summary",
        ),
        "owner_surface": "structural",
        "estimated_cost": "high",
        "path_globs": ("src/**/*.py", "tests/**/*.py", "pyproject.toml"),
        "owner_test_targets": ("tests/test_pipeline_collection_graphs.py", "tests/test_pipeline_run.py"),
        **_ai_metadata(
            "Use when architecture, dependency, or structural-budget artifacts need regeneration.",
            ".github/instructions/repo-audit.instructions.md",
        ),
    },
    {
        "id": "trace",
        "label": "Collect trace report",
        "profiles": ("full",),
        "artifact_ids": ("trace", "profiling_summary", "performance_budget"),
        "owner_surface": "trace",
        "estimated_cost": "medium",
        "path_globs": (
            "src/sattline_parser/**",
            "src/sattlint/analyzers/**",
            "src/sattlint/core/**",
            "src/sattlint_lsp/**",
            "tests/fixtures/sample_sattline_files/**",
        ),
        "owner_test_targets": ("tests/test_pipeline_phase2.py",),
        **_ai_metadata(
            "Use when parser, analyzer, or workspace-loading edits need trace or profiling artifacts.",
            ".github/instructions/parser-analysis.instructions.md",
            ".github/instructions/workspace-lsp.instructions.md",
        ),
    },
    {
        "id": "corpus",
        "label": "Run corpus suite",
        "profiles": ("full",),
        "artifact_ids": ("corpus_results",),
        "owner_surface": "corpus",
        "estimated_cost": "high",
        "path_globs": (
            "src/sattline_parser/**",
            "src/sattlint/analyzers/**",
            "tests/fixtures/corpus/**",
            "tests/parser/test_corpus.py",
        ),
        "owner_test_targets": ("tests/parser/test_corpus.py",),
        **_ai_metadata(
            "Use when parser or analyzer changes need corpus-level regression proof.",
            ".github/instructions/parser-analysis.instructions.md",
            ".github/instructions/test-fixtures.instructions.md",
        ),
    },
)
PIPELINE_CHECK_IDS = tuple(str(definition["id"]) for definition in PIPELINE_CHECK_DEFINITIONS)
PIPELINE_RECOMMENDATION_CONTROL_SURFACE_GLOBS = (
    "pyproject.toml",
    "src/sattlint/devtools/pipeline.py",
    "src/sattlint/devtools/pipeline_checks.py",
)
PIPELINE_RECOMMENDATION_CONTROL_SURFACE_CHECK_IDS = ("ruff", "pyright", "pytest")
PIPELINE_RECOMMENDATION_FALLBACK_GLOBS = PIPELINE_RECOMMENDATION_CONTROL_SURFACE_GLOBS
RECOMMENDATION_VERIFY_SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
    "htmlcov",
    "node_modules",
}
RECOMMENDATION_VERIFY_BROAD_MATCH_FRACTION = 0.9


def normalize_changed_files(changed_files: Iterable[str] | None) -> list[str]:
    if changed_files is None:
        return []
    normalized: list[str] = []
    for raw_path in changed_files:
        path_text = raw_path.strip().replace("\\", "/")
        if not path_text or path_text in normalized:
            continue
        normalized.append(path_text)
    return normalized


def path_matches_globs(path_text: str, globs: Iterable[str]) -> bool:
    for pattern in globs:
        if fnmatch.fnmatch(path_text, pattern):
            return True
        if "**/" in pattern and fnmatch.fnmatch(path_text, pattern.replace("**/", "")):
            return True
    return False


def matching_changed_files(changed_files: Iterable[str], globs: Iterable[str]) -> list[str]:
    normalized_globs = tuple(globs)
    return [
        path_text
        for path_text in normalize_changed_files(changed_files)
        if path_matches_globs(path_text, normalized_globs)
    ]


def collect_repo_file_inventory(repo_root: Path) -> list[str]:
    repo_files: list[str] = []
    ignored_dirs = {name.casefold() for name in RECOMMENDATION_VERIFY_SKIP_DIRS}
    for current_root, dir_names, file_names in os.walk(repo_root):
        dir_names[:] = sorted(name for name in dir_names if name.casefold() not in ignored_dirs)
        current_dir = Path(current_root)
        for file_name in file_names:
            repo_files.append((current_dir / file_name).relative_to(repo_root).as_posix())
    return sorted(repo_files)


def verify_check_catalog(catalog: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    repo_files = collect_repo_file_inventory(repo_root)
    issues: list[dict[str, Any]] = []
    repo_file_count = len(repo_files)
    allowed_costs = {"low", "medium", "high"}

    for entry in catalog.get("checks", []):
        check_id = entry.get("id", "<unknown>")
        owner_surface = str(entry.get("owner_surface", "")).strip()
        if not owner_surface:
            issues.append(
                {
                    "check_id": check_id,
                    "issue_id": "missing-owner-surface",
                    "message": "Recommendation entry is missing owner_surface metadata.",
                }
            )
        estimated_cost = str(entry.get("estimated_cost", "")).strip()
        if estimated_cost not in allowed_costs:
            issues.append(
                {
                    "check_id": check_id,
                    "issue_id": "invalid-estimated-cost",
                    "message": f"Recommendation entry uses unsupported estimated_cost '{estimated_cost}'.",
                }
            )
        path_globs = tuple(str(value).strip() for value in entry.get("path_globs", []) if str(value).strip())
        if not path_globs:
            issues.append(
                {
                    "check_id": check_id,
                    "issue_id": "missing-path-globs",
                    "message": "Recommendation entry is missing path_globs metadata.",
                }
            )
            continue
        if any("\\" in pattern for pattern in path_globs):
            issues.append(
                {
                    "check_id": check_id,
                    "issue_id": "backslash-path-glob",
                    "message": "Recommendation path globs must use '/' separators.",
                    "path_globs": list(path_globs),
                }
            )
        matched_files = matching_changed_files(repo_files, path_globs)
        if repo_files and not matched_files:
            issues.append(
                {
                    "check_id": check_id,
                    "issue_id": "dead-path-globs",
                    "message": "Recommendation path globs do not match any tracked repo files.",
                    "path_globs": list(path_globs),
                }
            )
            continue
        if repo_file_count and len(matched_files) / repo_file_count >= RECOMMENDATION_VERIFY_BROAD_MATCH_FRACTION:
            issues.append(
                {
                    "check_id": check_id,
                    "issue_id": "overbroad-path-globs",
                    "message": "Recommendation path globs match almost the entire repository, which is likely too broad.",
                    "match_fraction": round(len(matched_files) / repo_file_count, 3),
                    "matched_file_count": len(matched_files),
                    "repo_file_count": repo_file_count,
                }
            )
        owner_test_targets = tuple(
            str(value).strip() for value in entry.get("owner_test_targets", []) if str(value).strip()
        )
        if not owner_test_targets:
            issues.append(
                {
                    "check_id": check_id,
                    "issue_id": "missing-owner-tests",
                    "message": "Recommendation entry is missing owner_test_targets metadata.",
                }
            )
            continue
        missing_targets = [target for target in owner_test_targets if not (repo_root / target).exists()]
        if missing_targets:
            issues.append(
                {
                    "check_id": check_id,
                    "issue_id": "missing-owner-test-targets",
                    "message": "Recommendation entry references owner tests that do not exist.",
                    "missing_targets": missing_targets,
                }
            )

        ai_summary = str(entry.get("ai_summary", "")).strip()
        if not ai_summary:
            issues.append(
                {
                    "check_id": check_id,
                    "issue_id": "missing-ai-summary",
                    "message": "Recommendation entry is missing ai_summary metadata.",
                }
            )

        ai_instruction_files = tuple(
            str(value).strip() for value in entry.get("ai_instruction_files", []) if str(value).strip()
        )
        if not ai_instruction_files:
            issues.append(
                {
                    "check_id": check_id,
                    "issue_id": "missing-ai-instruction-files",
                    "message": "Recommendation entry is missing ai_instruction_files metadata.",
                }
            )
            continue

        if any("\\" in path_text for path_text in ai_instruction_files):
            issues.append(
                {
                    "check_id": check_id,
                    "issue_id": "backslash-ai-instruction-file",
                    "message": "AI instruction file paths must use '/' separators.",
                    "ai_instruction_files": list(ai_instruction_files),
                }
            )

        missing_instruction_files = [
            path_text for path_text in ai_instruction_files if not (repo_root / path_text).exists()
        ]
        if missing_instruction_files:
            issues.append(
                {
                    "check_id": check_id,
                    "issue_id": "missing-ai-instruction-targets",
                    "message": "Recommendation entry references instruction files that do not exist.",
                    "missing_instruction_files": missing_instruction_files,
                }
            )

    return {
        "kind": "sattlint.recommendation_catalog_verification",
        "schema_version": 1,
        "checked_check_count": len(catalog.get("checks", [])),
        "repo_file_count": repo_file_count,
        "issue_count": len(issues),
        "status": "fail" if issues else "pass",
        "issues": issues,
    }


def supported_pipeline_check_ids(profile: str, *, validate_profile: Callable[[str], object]) -> tuple[str, ...]:
    validate_profile(profile)
    return tuple(
        str(definition["id"]) for definition in PIPELINE_CHECK_DEFINITIONS if profile in tuple(definition["profiles"])
    )


def normalize_selected_checks(
    profile: str,
    selected_checks: Iterable[str] | None,
    *,
    validate_profile: Callable[[str], object],
) -> tuple[str, ...] | None:
    if selected_checks is None:
        return None
    supported = set(supported_pipeline_check_ids(profile, validate_profile=validate_profile))
    normalized: list[str] = []
    for raw_check in selected_checks:
        check_id = raw_check.strip()
        if not check_id:
            continue
        if check_id not in supported:
            supported_text = ", ".join(sorted(supported))
            raise ValueError(
                f"Unsupported pipeline check for profile '{profile}': {check_id}. Supported: {supported_text}"
            )
        if check_id not in normalized:
            normalized.append(check_id)
    if not normalized:
        raise ValueError("At least one non-empty --check value is required when selecting pipeline checks.")
    return tuple(normalized)


def build_pipeline_check_catalog(
    *,
    profile: str,
    output_dir: Path,
    repo_root: Path,
    validate_profile: Callable[[str], object],
) -> dict[str, Any]:
    supported_checks = supported_pipeline_check_ids(profile, validate_profile=validate_profile)
    sanitized_output_dir = (
        sanitize_path_for_report(output_dir.resolve(), repo_root=repo_root) or output_dir.resolve().as_posix()
    )
    checks: list[dict[str, Any]] = []
    for definition in PIPELINE_CHECK_DEFINITIONS:
        if definition["id"] not in supported_checks:
            continue
        checks.append(
            {
                "id": definition["id"],
                "label": definition["label"],
                "profiles": list(definition["profiles"]),
                "artifact_ids": list(definition["artifact_ids"]),
                "owner_surface": definition["owner_surface"],
                "estimated_cost": definition["estimated_cost"],
                "path_globs": list(definition["path_globs"]),
                "owner_test_targets": list(definition["owner_test_targets"]),
                "ai_summary": definition["ai_summary"],
                "ai_instruction_files": list(definition["ai_instruction_files"]),
                "command": (
                    f"sattlint-analysis-pipeline --profile {profile} --check {definition['id']} "
                    f"--output-dir {sanitized_output_dir}"
                ),
            }
        )
    return {
        "kind": "sattlint.pipeline.check_catalog",
        "schema_version": 1,
        "profile": profile,
        "checks": checks,
    }


def skipped_stage_report(tool: str, *, detail: str = "skipped by check selection") -> dict[str, Any]:
    base_report: dict[str, Any] = {
        "tool": tool,
        "skipped": True,
        "detail": detail,
        "exit_code": None,
    }
    if tool == "ruff":
        base_report.update({"finding_count": 0, "findings": []})
    elif tool == "pyright":
        base_report.update(
            {
                "finding_count": 0,
                "findings": [],
                "error_count": 0,
                "warning_count": 0,
                "effective_exit_code": None,
            }
        )
    elif tool == "pytest":
        base_report.update(
            {
                "summary": {"tests": 0, "failures": 0, "errors": 0, "skipped": 0},
                "testcases": [],
            }
        )
    elif tool == "environment":
        base_report = {"kind": "sattlint.pipeline.environment", "schema_version": 1, "skipped": True}
    return base_report


__all__ = [
    "PIPELINE_CHECK_DEFINITIONS",
    "PIPELINE_CHECK_IDS",
    "PIPELINE_RECOMMENDATION_FALLBACK_GLOBS",
    "build_pipeline_check_catalog",
    "collect_repo_file_inventory",
    "matching_changed_files",
    "normalize_changed_files",
    "normalize_selected_checks",
    "path_matches_globs",
    "skipped_stage_report",
    "supported_pipeline_check_ids",
    "verify_check_catalog",
]
