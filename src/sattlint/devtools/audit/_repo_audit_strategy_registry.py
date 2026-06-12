"""Registry-backed definitions for repo-audit finding checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class RepoAuditRunner(Protocol):
    def __call__(self, context: Any, /) -> list[Any]: ...


@dataclass(frozen=True, slots=True)
class RepoAuditCheckStrategy:
    check_id: str
    label: str
    profiles: tuple[str, ...]
    runner: RepoAuditRunner
    owner_surface: str
    estimated_cost: str
    path_globs: tuple[str, ...]
    owner_test_targets: tuple[str, ...]
    ai_summary: str
    ai_instruction_files: tuple[str, ...] = ()

    def to_definition(self) -> dict[str, Any]:
        return {
            "id": self.check_id,
            "label": self.label,
            "profiles": self.profiles,
            "runner": self.runner,
            "owner_surface": self.owner_surface,
            "estimated_cost": self.estimated_cost,
            "path_globs": self.path_globs,
            "owner_test_targets": self.owner_test_targets,
            "ai_summary": self.ai_summary,
            "ai_instruction_files": self.ai_instruction_files,
        }


def build_repo_audit_finding_strategies(
    *,
    verify_recommendations_runner: RepoAuditRunner,
) -> tuple[RepoAuditCheckStrategy, ...]:
    from . import _repo_audit_check_runners as repo_audit_check_runners  # noqa: PLC0415

    return (
        RepoAuditCheckStrategy(
            check_id="text-scan",
            label="Scan repository text for leaks and local paths",
            profiles=("quick", "full"),
            runner=repo_audit_check_runners._run_text_scan_check,
            owner_surface="text-scan",
            estimated_cost="low",
            path_globs=(
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
            owner_test_targets=("tests/test_repo_audit_part1.py",),
            ai_summary="Use when documentation or Python sources may have leaked local paths, secrets, or unsafe text.",
            ai_instruction_files=(".github/instructions/repo-audit.instructions.md",),
        ),
        RepoAuditCheckStrategy(
            check_id="local-ci-parity",
            label="Detect local-versus-CI parity drift in paths, test guards, and local dependency roots",
            profiles=("quick", "full"),
            runner=repo_audit_check_runners._run_local_ci_parity_check,
            owner_surface="local-ci-parity",
            estimated_cost="low",
            path_globs=(
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
            owner_test_targets=("tests/test_repo_audit_part1.py",),
            ai_summary="Use when changes may rely on local-only paths, guards, or machine-specific assumptions.",
            ai_instruction_files=(".github/instructions/repo-audit.instructions.md",),
        ),
        RepoAuditCheckStrategy(
            check_id="documented-commands",
            label="Check documented commands against implemented CLI surfaces",
            profiles=("quick", "full"),
            runner=repo_audit_check_runners._run_documented_commands_check,
            owner_surface="cli-docs",
            estimated_cost="low",
            path_globs=(
                "README.md",
                "CONTRIBUTING.md",
                "docs/references/cli-commands.md",
                "docs/references/ai-agent-reference.md",
                "pyproject.toml",
                "src/sattlint/cli/**",
                "src/sattlint/app*.py",
                "src/sattlint/devtools/audit/repo_audit_cli.py",
            ),
            owner_test_targets=("tests/test_repo_audit_part1.py",),
            ai_summary="Use when CLI help, command docs, or agent reference commands must stay in sync with implementation.",
            ai_instruction_files=(
                ".github/instructions/cli-app.instructions.md",
                ".github/instructions/repo-audit.instructions.md",
            ),
        ),
        RepoAuditCheckStrategy(
            check_id="unused-config-keys",
            label="Report declared but unused config keys",
            profiles=("quick", "full"),
            runner=repo_audit_check_runners._run_unused_config_keys_check,
            owner_surface="config",
            estimated_cost="low",
            path_globs=(
                "pyproject.toml",
                "src/sattlint/config.py",
                "src/sattlint/**/*.py",
            ),
            owner_test_targets=("tests/test_repo_audit_part1.py",),
            ai_summary="Use when config declarations or config consumers change and unused keys may drift.",
            ai_instruction_files=(".github/instructions/cli-app.instructions.md",),
        ),
        RepoAuditCheckStrategy(
            check_id="architecture",
            label="Run repository architecture checks",
            profiles=("quick", "full"),
            runner=repo_audit_check_runners._run_architecture_check,
            owner_surface="architecture",
            estimated_cost="medium",
            path_globs=(
                "src/**",
                "tests/**",
                "metrics/layer_lint_policy.json",
                "pyproject.toml",
            ),
            owner_test_targets=("tests/test_repo_audit_part1.py", "tests/test_repo_audit_part2.py"),
            ai_summary="Use when Python architecture, import layering, or module-size constraints may shift.",
            ai_instruction_files=(".github/instructions/repo-audit.instructions.md",),
        ),
        RepoAuditCheckStrategy(
            check_id="structural-report",
            label="Translate structural report findings into repo-audit findings",
            profiles=("quick", "full"),
            runner=repo_audit_check_runners._run_structural_report_check,
            owner_surface="structural",
            estimated_cost="medium",
            path_globs=(
                "src/**",
                "tests/**",
                "artifacts/analysis/structural_budget_ratchet.json",
            ),
            owner_test_targets=("tests/test_repo_audit_part4.py",),
            ai_summary="Use when structural budget artifacts or their translation into findings may change.",
            ai_instruction_files=(".github/instructions/repo-audit.instructions.md",),
        ),
        RepoAuditCheckStrategy(
            check_id="cli",
            label="Validate CLI descriptions and subcommand help",
            profiles=("quick", "full"),
            runner=repo_audit_check_runners._run_cli_check,
            owner_surface="cli",
            estimated_cost="low",
            path_globs=(
                "pyproject.toml",
                "src/sattlint/cli/**",
                "src/sattlint/app*.py",
                "src/sattlint/devtools/audit/repo_audit_cli.py",
            ),
            owner_test_targets=("tests/test_repo_audit_part1.py",),
            ai_summary="Use when CLI parser descriptions, subcommand help, or interactive command surfaces change.",
            ai_instruction_files=(
                ".github/instructions/cli-app.instructions.md",
                ".github/instructions/repo-audit.instructions.md",
            ),
        ),
        RepoAuditCheckStrategy(
            check_id="logging",
            label="Check library modules for unexpected print calls",
            profiles=("quick", "full"),
            runner=repo_audit_check_runners._run_logging_check,
            owner_surface="logging",
            estimated_cost="low",
            path_globs=("src/**/*.py",),
            owner_test_targets=("tests/test_repo_audit_part1.py",),
            ai_summary="Use when library code changes may introduce unexpected prints or weak failure-path diagnostics.",
            ai_instruction_files=(".github/instructions/repo-audit.instructions.md",),
        ),
        RepoAuditCheckStrategy(
            check_id="ai-gc",
            label="Report stale AI-generated artifacts and oversized local coordination state",
            profiles=("quick", "full"),
            runner=repo_audit_check_runners._run_ai_gc_check,
            owner_surface="ai-hygiene",
            estimated_cost="low",
            path_globs=(
                "artifacts/**",
                "docs/generated/**",
                ".github/coordination/current-work.template.md",
                "src/sattlint/devtools/ai/ai_gc.py",
                "src/sattlint/devtools/audit/repo_audit.py",
                "src/sattlint/devtools/audit/repo_audit_cli.py",
                "src/sattlint/devtools/audit/repo_audit_entrypoints.py",
                "tests/test_repo_audit_part7.py",
            ),
            owner_test_targets=("tests/test_repo_audit_part7.py",),
            ai_summary="Use when AI-generated artifacts, coordination state, or related cleanup policy changes.",
            ai_instruction_files=(".github/instructions/repo-audit.instructions.md",),
        ),
        RepoAuditCheckStrategy(
            check_id="ignored-repo-paths",
            label="Detect ignored repo-local dependency references",
            profiles=("quick", "full"),
            runner=repo_audit_check_runners._run_ignored_repo_paths_check,
            owner_surface="path-safety",
            estimated_cost="low",
            path_globs=(
                "src/**/*.py",
                "tests/**/*.py",
                "scripts/**/*.py",
            ),
            owner_test_targets=("tests/test_repo_audit_part2.py",),
            ai_summary="Use when repo-local ignored paths or hidden dependency roots may leak into tracked code.",
            ai_instruction_files=(".github/instructions/repo-audit.instructions.md",),
        ),
        RepoAuditCheckStrategy(
            check_id="harness-freshness",
            label="Enforce AI harness freshness for instructions, agents, links, and generated maps",
            profiles=("quick", "full"),
            runner=repo_audit_check_runners._run_harness_freshness_check,
            owner_surface="harness-freshness",
            estimated_cost="low",
            path_globs=(
                "AGENTS.md",
                ".github/instructions/**",
                "docs/maintainers/**",
                "docs/public/architecture.md",
                "docs/design-docs/core-beliefs.md",
                "docs/references/ai-agent-reference.md",
                "src/sattlint/devtools/ai/ai_work_map.py",
                "src/sattlint/devtools/doc_gardener.py",
                "src/sattlint/devtools/audit/repo_audit.py",
                "src/sattlint/devtools/audit/repo_audit_entrypoints.py",
                "tests/test_ai_work_map.py",
                "tests/test_repo_audit_part5.py",
            ),
            owner_test_targets=("tests/test_ai_work_map.py", "tests/test_repo_audit_part5.py"),
            ai_summary="Use when AI instructions, agents, generated routing maps, or other AI-control surfaces change.",
            ai_instruction_files=(".github/instructions/repo-audit.instructions.md",),
        ),
        RepoAuditCheckStrategy(
            check_id="coverage",
            label="Translate low-coverage modules into audit findings",
            profiles=("quick", "full"),
            runner=repo_audit_check_runners._run_coverage_check,
            owner_surface="coverage",
            estimated_cost="low",
            path_globs=(
                "tests/**",
                "coverage.xml",
                "pyproject.toml",
            ),
            owner_test_targets=("tests/test_repo_audit_part1.py", "tests/test_repo_audit_part3.py"),
            ai_summary="Use when coverage artifacts or audit-facing coverage recommendations may change.",
            ai_instruction_files=(".github/instructions/repo-audit.instructions.md",),
        ),
        RepoAuditCheckStrategy(
            check_id="public-readiness",
            label="Check public-repository readiness files and metadata",
            profiles=("quick", "full"),
            runner=repo_audit_check_runners._run_public_readiness_check,
            owner_surface="public-readiness",
            estimated_cost="low",
            path_globs=(
                "README.md",
                "CONTRIBUTING.md",
                "SECURITY.md",
                "LICENSE",
                ".github/**",
                "docs/**",
                "pyproject.toml",
            ),
            owner_test_targets=("tests/test_repo_audit_part3.py",),
            ai_summary="Use when top-level repo hygiene, public metadata, or publish-facing docs may drift.",
            ai_instruction_files=(".github/instructions/repo-audit.instructions.md",),
        ),
        RepoAuditCheckStrategy(
            check_id="verify-recommendations",
            label="Verify recommendation metadata and routing catalog coverage",
            profiles=("quick", "full"),
            runner=verify_recommendations_runner,
            owner_surface="recommendations",
            estimated_cost="low",
            path_globs=(
                "src/sattlint/devtools/pipeline.py",
                "src/sattlint/devtools/shared/pipeline_checks.py",
                "src/sattlint/devtools/repo_audit.py",
                "src/sattlint/devtools/audit/repo_audit_cli.py",
                "src/sattlint/devtools/audit/repo_audit_entrypoints.py",
                "tests/test_pipeline_run.py",
                "tests/test_repo_audit_part8.py",
                "tests/test_recommendation_routing.py",
                "docs/references/cli-commands.md",
                "docs/references/ai-agent-reference.md",
            ),
            owner_test_targets=(
                "tests/test_pipeline_run.py",
                "tests/test_repo_audit_part8.py",
                "tests/test_recommendation_routing.py",
            ),
            ai_summary="Use when routing catalogs, recommendation metadata, or generated AI registry outputs change.",
            ai_instruction_files=(".github/instructions/repo-audit.instructions.md",),
        ),
    )


__all__ = ["RepoAuditCheckStrategy", "build_repo_audit_finding_strategies"]
