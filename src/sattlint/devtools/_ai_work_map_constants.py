from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATION_MAP_PATH = REPO_ROOT / ".github" / "skills" / "validation-routing" / "references" / "validation-map.md"
ACTIVE_EXEC_PLANS_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"
COMPLETED_EXEC_PLANS_DIR = REPO_ROOT / "docs" / "exec-plans" / "completed"
INSTRUCTIONS_DIR = REPO_ROOT / ".github" / "instructions"
AGENTS_DIR = REPO_ROOT / ".github" / "agents"
DEFAULT_OUTPUT_PATH = REPO_ROOT / ".github" / "skills" / "validation-routing" / "references" / "ai-work-map.json"
DEFAULT_SESSION_CONTEXT_OUTPUT_PATH = (
    REPO_ROOT / ".github" / "skills" / "validation-routing" / "references" / "ai-session-context-map.json"
)
DEFAULT_CHECK_CATALOG_OUTPUT_PATH = (
    REPO_ROOT / ".github" / "skills" / "validation-routing" / "references" / "ai-check-catalog.md"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "generated" / "ai-work-map"
REFERENCE_UPDATE_SUFFIXES = {".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
REFERENCE_UPDATE_SKIP_ROOTS = {".git", ".venv", "artifacts", "htmlcov", "__pycache__"}
SEMANTIC_OWNER_SUGGESTION_TOP_K = 3
AGENT_ROUTING_RULES: tuple[dict[str, Any], ...] = (
    {
        "agent_name": "CLI App Menu",
        "selected_surfaces": ("repo-audit", "pipeline"),
        "owner_surface_keywords": ("cli", "console", "config"),
        "path_globs": (
            "src/sattlint/app.py",
            "src/sattlint/config.py",
            "src/sattlint/cli/**",
            "tests/test_cli.py",
            "tests/test_app*.py",
        ),
    },
    {
        "agent_name": "Documentation Generation",
        "selected_surfaces": ("repo-audit", "pipeline"),
        "owner_surface_keywords": ("docgen", "classification", "docs"),
        "path_globs": (
            "src/sattlint/docgenerator/**",
            "tests/test_docgen*.py",
            "tests/test_app_docgen.py",
        ),
    },
    {
        "agent_name": "Parser Analysis",
        "selected_surfaces": ("pipeline",),
        "owner_surface_keywords": ("parser", "trace", "corpus", "strict"),
        "path_globs": (
            "src/sattline_parser/**",
            "src/sattlint/validation.py",
            "tests/parser/**",
            "tests/fixtures/sample_sattline_files/**",
        ),
    },
    {
        "agent_name": "Workspace LSP",
        "selected_surfaces": ("pipeline",),
        "owner_surface_keywords": ("workspace", "semantic", "lsp"),
        "path_globs": (
            "src/sattlint/core/**",
            "src/sattlint_lsp/**",
            "vscode/sattline-vscode/**",
            "tests/test_editor_api.py",
            "tests/test_lsp*.py",
        ),
    },
    {
        "agent_name": "Repo Audit",
        "selected_surfaces": ("repo-audit", "pipeline"),
        "owner_surface_keywords": (
            "architecture",
            "coverage",
            "feature-wiring",
            "harness",
            "logging",
            "path-safety",
            "public-readiness",
            "recommendations",
            "structural",
            "text-scan",
        ),
        "path_globs": (
            "src/sattlint/devtools/**",
            "tests/test_repo_audit*.py",
            "tests/test_pipeline*.py",
            "tests/test_artifact_contracts.py",
            "docs/references/cli-commands.md",
            "docs/references/ai-agent-reference.md",
        ),
    },
    {
        "agent_name": "SattLint Orchestrator",
        "selected_surfaces": ("repo-audit", "pipeline"),
        "owner_surface_keywords": ("recommendations", "structural", "python-tests", "python-style"),
        "path_globs": (
            ".git/sattlint-ai-coordination/current_work_lock.json",
            "docs/exec-plans/**",
            ".github/skills/**",
            ".github/instructions/**",
        ),
    },
)
DEFAULT_AGENT_ENTRYPOINT = {
    "id": "planning-context",
    "command": "sattlint-repo-audit --profile full --planning-context --output-dir artifacts/audit",
    "companion_command": "sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit",
    "description": (
        "Default machine entrypoint for agents. Returns changed files, owning surface, instruction files, "
        "first focused validation, finish-gate plan, and blocking invariants in one response."
    ),
}
FINISH_GATE_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "selected_surface": "pipeline",
        "command": "sattlint-analysis-pipeline --profile full --run-recommended-finish-gate --output-dir artifacts/audit/pipeline",
        "description": "Shared-pipeline finish gate for changes that do not need repo-audit-specific checks.",
        "includes": (
            "recommended pipeline slice",
            "touched-file Ruff",
            "touched-file Pyright",
            "owner pytest targets",
        ),
    },
    {
        "selected_surface": "repo-audit",
        "command": "sattlint-repo-audit --profile full --run-recommended-finish-gate --output-dir artifacts/audit",
        "description": "Combined repo-audit finish gate for changes that require repo-audit-specific checks.",
        "includes": (
            "recommended repo-audit slice",
            "touched-file Ruff",
            "touched-file Pyright",
            "owner pytest targets",
        ),
    },
)
BLOCKING_INVARIANT_RULES: tuple[dict[str, Any], ...] = (
    {
        "id": "focused-validation-first",
        "summary": "Run the first focused executable validation immediately after the first substantive edit.",
        "details": "Do not widen scope before that check when a narrow executable validation exists.",
        "selected_surfaces": ("session-start", "pipeline", "repo-audit"),
        "path_globs": (),
    },
    {
        "id": "repo-venv-validation",
        "summary": "Use repo venv commands, not the VS Code test runner, for first validation.",
        "details": "Targeted pytest or repo-local tool commands are the expected first validation path in this repo.",
        "selected_surfaces": ("session-start", "pipeline", "repo-audit"),
        "path_globs": (),
    },
    {
        "id": "python-finish-gate-clean",
        "summary": "Do not finish Python edits with touched-file Ruff or Pyright errors.",
        "details": "Python finish gates require focused behavior validation plus touched-file Ruff and Pyright checks.",
        "selected_surfaces": ("session-start", "pipeline", "repo-audit"),
        "path_globs": ("src/**/*.py", "tests/**/*.py", "scripts/**/*.py"),
    },
    {
        "id": "shared-infra-widen-after-focused-check",
        "summary": "Shared infra and devtools changes widen only after the focused check passes.",
        "details": "Use owner-suite validation or quick repo audit after the narrow check for shared infra or cross-subsystem wiring.",
        "selected_surfaces": ("pipeline", "repo-audit"),
        "path_globs": (
            "src/sattlint/devtools/**",
            ".github/hooks/**",
            ".github/instructions/**",
            ".github/skills/**",
        ),
    },
    {
        "id": "cli-menu-tests-stay-in-sync",
        "summary": "If CLI menu layout or numbering changes, update tests/test_app.py in the same change.",
        "details": "CLI menu invariants require the interactive app tests to move with the menu surface.",
        "selected_surfaces": ("session-start", "pipeline", "repo-audit"),
        "path_globs": ("src/sattlint/app.py",),
    },
    {
        "id": "restart-lsp-after-editor-surface-edits",
        "summary": "Restart the language server after semantic core, LSP, editor_api, or VS Code client edits.",
        "details": "Run sattlineLsp.restartServer after changes under the editor or workspace loading surfaces.",
        "selected_surfaces": ("session-start", "pipeline", "repo-audit"),
        "path_globs": (
            "src/sattlint/core/**",
            "src/sattlint_lsp/**",
            "src/sattlint/editor_api.py",
            "vscode/sattline-vscode/**",
        ),
    },
)

__all__ = [
    "ACTIVE_EXEC_PLANS_DIR",
    "AGENTS_DIR",
    "AGENT_ROUTING_RULES",
    "BLOCKING_INVARIANT_RULES",
    "COMPLETED_EXEC_PLANS_DIR",
    "DEFAULT_AGENT_ENTRYPOINT",
    "DEFAULT_CHECK_CATALOG_OUTPUT_PATH",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_OUTPUT_PATH",
    "DEFAULT_SESSION_CONTEXT_OUTPUT_PATH",
    "FINISH_GATE_TEMPLATES",
    "INSTRUCTIONS_DIR",
    "REFERENCE_UPDATE_SKIP_ROOTS",
    "REFERENCE_UPDATE_SUFFIXES",
    "REPO_ROOT",
    "SEMANTIC_OWNER_SUGGESTION_TOP_K",
    "VALIDATION_MAP_PATH",
]
