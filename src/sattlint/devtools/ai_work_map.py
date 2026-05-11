from __future__ import annotations

import argparse
import json
from functools import partial
from pathlib import Path
from typing import Any

from sattlint.devtools import _ai_work_map_parsing as parsing_helpers
from sattlint.devtools import _ai_work_map_planning as planning_helpers
from sattlint.devtools._ai_work_map_freshness import verify_ai_harness_freshness as verify_ai_harness_freshness
from sattlint.devtools.pipeline_checks import normalize_changed_files, path_matches_globs

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
            "tests/test_docgen.py",
            "tests/test_gui.py",
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
            "tests/test_repo_audit.py",
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


_read_lines = parsing_helpers.read_lines
_extract_backtick_items = parsing_helpers.extract_backtick_items
_strip_quotes = parsing_helpers.strip_quotes
_parse_progress_checkbox_states = parsing_helpers.parse_progress_checkbox_states
_is_completed_exec_plan = parsing_helpers.is_completed_exec_plan
_parse_frontmatter = parsing_helpers.parse_frontmatter
_parse_validation_routes = parsing_helpers.parse_validation_routes
_parse_owner_suites = parsing_helpers.parse_owner_suites
_parse_first_validation_commands = parsing_helpers.parse_first_validation_commands
_render_json = parsing_helpers.render_json
_instruction_lookup = planning_helpers.instruction_lookup
_simplify_check_catalog = planning_helpers.simplify_check_catalog
_all_check_entries = planning_helpers.all_check_entries
_render_check_section = planning_helpers.render_check_section
_collect_relevant_checks = planning_helpers.collect_relevant_checks
_match_instruction_files = partial(planning_helpers.match_instruction_files, path_matches_globs=path_matches_globs)
_match_owner_suites = partial(planning_helpers.match_owner_suites, path_matches_globs=path_matches_globs)
_match_agents = partial(planning_helpers.match_agents, path_matches_globs=path_matches_globs)
_select_finish_gate_template = planning_helpers.select_finish_gate_template
_match_blocking_invariants = partial(planning_helpers.match_blocking_invariants, path_matches_globs=path_matches_globs)


def _iter_reference_update_files(repo_root: Path) -> list[Path]:
    return parsing_helpers.iter_reference_update_files(repo_root)


def _rewrite_exec_plan_references(archived: list[dict[str, str]], *, repo_root: Path) -> None:
    return parsing_helpers.rewrite_exec_plan_references(
        archived,
        repo_root=repo_root,
        iter_reference_update_files=_iter_reference_update_files,
    )


def archive_completed_exec_plans(
    active_dir: Path = ACTIVE_EXEC_PLANS_DIR,
    completed_dir: Path = COMPLETED_EXEC_PLANS_DIR,
) -> list[dict[str, str]]:
    return parsing_helpers.archive_completed_exec_plans(
        active_dir,
        completed_dir,
        is_completed_exec_plan=_is_completed_exec_plan,
        rewrite_exec_plan_references=lambda archived, repo_root: _rewrite_exec_plan_references(
            archived,
            repo_root=repo_root,
        ),
    )


def _collect_owner_suite_plans(exec_plans_dir: Path) -> list[dict[str, Any]]:
    return parsing_helpers.collect_owner_suite_plans(exec_plans_dir, repo_root=REPO_ROOT)


def _collect_instruction_metadata(instructions_dir: Path) -> list[dict[str, Any]]:
    return parsing_helpers.collect_instruction_metadata(instructions_dir, repo_root=REPO_ROOT)


def _collect_agent_metadata(agents_dir: Path) -> list[dict[str, Any]]:
    return parsing_helpers.collect_agent_metadata(agents_dir, repo_root=REPO_ROOT)


def _merge_instruction_files_for_planning(
    work_map: dict[str, Any],
    changed_files: list[str],
    relevant_checks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return planning_helpers.merge_instruction_files_for_planning(
        work_map,
        changed_files,
        relevant_checks,
        match_instruction_files=_match_instruction_files,
    )


def render_ai_check_catalog(work_map: dict[str, Any] | None = None) -> str:
    resolved_work_map = build_ai_work_map() if work_map is None else work_map
    pipeline_checks: list[dict[str, Any]] = [
        entry for entry in resolved_work_map.get("pipeline_checks", []) if isinstance(entry, dict)
    ]
    repo_audit_checks: list[dict[str, Any]] = [
        entry for entry in resolved_work_map.get("repo_audit_checks", []) if isinstance(entry, dict)
    ]
    lines = [
        "# AI Check Catalog",
        "",
        "Generated from the pipeline and repo-audit check registries.",
        "Regenerate with `python -m sattlint.devtools.ai_work_map --write`.",
        "",
    ]
    lines.extend(_render_check_section("Pipeline Checks", pipeline_checks))
    lines.extend(_render_check_section("Repo Audit Checks", repo_audit_checks))
    return "\n".join(lines).rstrip() + "\n"


def build_ai_work_map() -> dict[str, Any]:
    from sattlint.devtools import pipeline, repo_audit_entrypoints

    pipeline_catalog = pipeline.build_pipeline_check_catalog(
        profile="full",
        output_dir=DEFAULT_OUTPUT_DIR / "pipeline",
    )
    repo_catalog = repo_audit_entrypoints.build_repo_audit_check_catalog(
        profile="full",
        output_dir=DEFAULT_OUTPUT_DIR,
        fail_on="high",
    )
    return {
        "kind": "sattlint.ai_work_map",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.ai_work_map",
        "default_entrypoint": dict(DEFAULT_AGENT_ENTRYPOINT),
        "generated_from": {
            "validation_map": VALIDATION_MAP_PATH.relative_to(REPO_ROOT).as_posix(),
            "active_exec_plans": f"{ACTIVE_EXEC_PLANS_DIR.relative_to(REPO_ROOT).as_posix()}/*.md",
            "pipeline_catalog": "sattlint.devtools.pipeline.build_pipeline_check_catalog(profile='full')",
            "repo_audit_catalog": (
                "sattlint.devtools.repo_audit_entrypoints.build_repo_audit_check_catalog(profile='full')"
            ),
        },
        "validation_routes": _parse_validation_routes(VALIDATION_MAP_PATH),
        "finish_gate_templates": [dict(template) for template in FINISH_GATE_TEMPLATES],
        "blocking_invariant_rules": [dict(rule) for rule in BLOCKING_INVARIANT_RULES],
        "instructions": _collect_instruction_metadata(INSTRUCTIONS_DIR),
        "agents": _collect_agent_metadata(AGENTS_DIR),
        "agent_routing": list(AGENT_ROUTING_RULES),
        "pipeline_checks": _simplify_check_catalog(pipeline_catalog),
        "repo_audit_checks": _simplify_check_catalog(repo_catalog, source="repo-audit"),
        "owner_suite_plans": _collect_owner_suite_plans(ACTIVE_EXEC_PLANS_DIR),
    }


def build_session_context_map(work_map: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved_work_map = build_ai_work_map() if work_map is None else work_map
    return {
        "kind": "sattlint.ai_session_context_map",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.ai_work_map",
        "generated_from": {
            "work_map": DEFAULT_OUTPUT_PATH.relative_to(REPO_ROOT).as_posix(),
        },
        "default_entrypoint": dict(resolved_work_map.get("default_entrypoint", {})),
        "finish_gate_templates": list(resolved_work_map.get("finish_gate_templates", [])),
        "blocking_invariant_rules": list(resolved_work_map.get("blocking_invariant_rules", [])),
        "instructions": list(resolved_work_map.get("instructions", [])),
        "agents": list(resolved_work_map.get("agents", [])),
        "agent_routing": list(resolved_work_map.get("agent_routing", [])),
        "owner_suite_plans": list(resolved_work_map.get("owner_suite_plans", [])),
    }


def load_ai_work_map(path: Path = DEFAULT_OUTPUT_PATH) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return build_ai_work_map()


def load_session_context_map(path: Path = DEFAULT_SESSION_CONTEXT_OUTPUT_PATH) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return build_session_context_map()


def build_planning_context(
    *,
    changed_files: list[str] | None,
    recommended_check_ids: list[str] | None,
    selected_surface: str,
    work_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_work_map = load_ai_work_map() if work_map is None else work_map
    normalized_changed_files = normalize_changed_files(changed_files)
    resolved_check_ids = [] if recommended_check_ids is None else list(dict.fromkeys(recommended_check_ids))
    relevant_checks = _collect_relevant_checks(resolved_work_map, resolved_check_ids)
    owner_test_targets: list[str] = []
    owner_surfaces: list[str] = []
    for entry in relevant_checks:
        owner_surface = str(entry.get("owner_surface", "")).strip()
        if owner_surface and owner_surface not in owner_surfaces:
            owner_surfaces.append(owner_surface)
        for target in entry.get("owner_test_targets", []):
            target_text = str(target).strip()
            if target_text and target_text not in owner_test_targets:
                owner_test_targets.append(target_text)

    owning_agents = _match_agents(resolved_work_map, normalized_changed_files, owner_surfaces, selected_surface)
    nearest_owner_suites = _match_owner_suites(resolved_work_map, normalized_changed_files, owner_test_targets)
    instruction_files = _merge_instruction_files_for_planning(
        resolved_work_map,
        normalized_changed_files,
        relevant_checks,
    )
    first_validation_commands: list[str] = []
    for suite in nearest_owner_suites:
        for command in suite.get("first_validation_commands", []):
            command_text = str(command).strip()
            if command_text and command_text not in first_validation_commands:
                first_validation_commands.append(command_text)
    finish_gate_template = _select_finish_gate_template(resolved_work_map, selected_surface)
    blocking_invariants = _match_blocking_invariants(resolved_work_map, normalized_changed_files, selected_surface)

    return {
        "default_entrypoint": dict(resolved_work_map.get("default_entrypoint", {})),
        "primary_agent": None if not owning_agents else owning_agents[0]["name"],
        "owning_agents": owning_agents,
        "owner_surfaces": owner_surfaces,
        "recommended_check_ids": resolved_check_ids,
        "relevant_checks": relevant_checks,
        "owner_test_targets": owner_test_targets,
        "instruction_files": instruction_files,
        "nearest_owner_suites": nearest_owner_suites,
        "first_validation_commands": first_validation_commands,
        "finish_gate_template": finish_gate_template,
        "blocking_invariants": blocking_invariants,
    }


def render_ai_work_map() -> str:
    return _render_json(build_ai_work_map())


def render_session_context_map() -> str:
    return _render_json(build_session_context_map())


def write_ai_check_catalog(output_path: Path = DEFAULT_CHECK_CATALOG_OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_ai_check_catalog(), encoding="utf-8", newline="\n")
    return output_path


def write_ai_work_map(output_path: Path = DEFAULT_OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_ai_work_map(), encoding="utf-8", newline="\n")
    return output_path


def write_session_context_map(output_path: Path = DEFAULT_SESSION_CONTEXT_OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_session_context_map(), encoding="utf-8", newline="\n")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the machine-readable SattLint AI work map.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Path for the generated JSON file.")
    parser.add_argument(
        "--session-output",
        type=Path,
        default=DEFAULT_SESSION_CONTEXT_OUTPUT_PATH,
        help="Path for the compact session-start planning JSON file.",
    )
    parser.add_argument(
        "--reference-output",
        type=Path,
        default=DEFAULT_CHECK_CATALOG_OUTPUT_PATH,
        help="Path for the generated AI check reference markdown file.",
    )
    parser.add_argument("--write", action="store_true", help="Write the generated JSON to --output.")
    parser.add_argument("--check", action="store_true", help="Fail when --output does not match the generated JSON.")
    parser.add_argument("--stdout", action="store_true", help="Print the generated JSON to stdout.")
    args = parser.parse_args(argv)

    if args.write:
        archive_completed_exec_plans()

    rendered = render_ai_work_map()
    session_rendered = render_session_context_map()
    reference_rendered = render_ai_check_catalog()
    if args.check:
        existing = args.output.read_text(encoding="utf-8") if args.output.exists() else None
        session_existing = args.session_output.read_text(encoding="utf-8") if args.session_output.exists() else None
        reference_existing = (
            args.reference_output.read_text(encoding="utf-8") if args.reference_output.exists() else None
        )
        if existing != rendered or session_existing != session_rendered or reference_existing != reference_rendered:
            return 1
    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
        args.session_output.parent.mkdir(parents=True, exist_ok=True)
        args.session_output.write_text(session_rendered, encoding="utf-8", newline="\n")
        args.reference_output.parent.mkdir(parents=True, exist_ok=True)
        args.reference_output.write_text(reference_rendered, encoding="utf-8", newline="\n")
    if args.stdout or (not args.write and not args.check):
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
