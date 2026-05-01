from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from sattlint.devtools import pipeline
from sattlint.devtools.pipeline_checks import normalize_changed_files, path_matches_globs

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATION_MAP_PATH = REPO_ROOT / ".github" / "skills" / "validation-routing" / "references" / "validation-map.md"
ACTIVE_EXEC_PLANS_DIR = REPO_ROOT / "docs" / "exec-plans" / "active"
INSTRUCTIONS_DIR = REPO_ROOT / ".github" / "instructions"
AGENTS_DIR = REPO_ROOT / ".github" / "agents"
DEFAULT_OUTPUT_PATH = REPO_ROOT / ".github" / "skills" / "validation-routing" / "references" / "ai-work-map.json"
DEFAULT_SESSION_CONTEXT_OUTPUT_PATH = (
    REPO_ROOT / ".github" / "skills" / "validation-routing" / "references" / "ai-session-context-map.json"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "generated" / "ai-work-map"

BACKTICK_RE = re.compile(r"`([^`]+)`")
VALIDATION_ROUTE_RE = re.compile(r"^- (?P<surface>.+):\s*$")
QUOTED_ITEM_RE = re.compile(r'"([^"]+)"')
OWNER_SUITE_HEADINGS = (
    "Primary owner suites for this plan:",
    "Existing owner suites that this plan may reuse instead of creating new suites when the fit is real:",
)
FIRST_VALIDATION_HEADING = "Per-slice first validations:"
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
            "tests/test_parser*.py",
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
            ".github/coordination/current-work.md",
            "docs/exec-plans/**",
            ".github/skills/**",
            ".github/instructions/**",
        ),
    },
)


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _extract_backtick_items(text: str) -> list[str]:
    return [item.strip() for item in BACKTICK_RE.findall(text) if item.strip()]


def _strip_quotes(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith(('"', "'")) and stripped.endswith(('"', "'")) and len(stripped) >= 2:
        return stripped[1:-1]
    return stripped


def _parse_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    _, _, remainder = text.partition("---\n")
    frontmatter_text, _, _ = remainder.partition("\n---\n")
    data: dict[str, Any] = {}
    for raw_line in frontmatter_text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        value = raw_value.strip()
        if value.startswith("[") and value.endswith("]"):
            quoted_items = QUOTED_ITEM_RE.findall(value)
            if quoted_items:
                data[key] = quoted_items
            else:
                inner = value[1:-1].strip()
                data[key] = [] if not inner else [_strip_quotes(item) for item in inner.split(",") if item.strip()]
            continue
        if value.casefold() in {"true", "false"}:
            data[key] = value.casefold() == "true"
            continue
        data[key] = _strip_quotes(value)
    return data


def _parse_validation_routes(path: Path) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for raw_line in _read_lines(path):
        line = raw_line.rstrip()
        route_match = VALIDATION_ROUTE_RE.match(line)
        if route_match is not None:
            if current is not None:
                routes.append(current)
            current = {
                "surface": route_match.group("surface").strip(),
                "commands": [],
                "notes": [],
            }
            continue
        if current is None:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        commands = _extract_backtick_items(stripped)
        if commands:
            current["commands"].extend(commands)
            note_text = BACKTICK_RE.sub("", stripped).strip()
            if note_text:
                current["notes"].append(note_text)
            continue
        current["notes"].append(stripped)

    if current is not None:
        routes.append(current)
    return routes


def _parse_owner_suites(path: Path) -> list[dict[str, Any]]:
    lines = _read_lines(path)
    suites: list[dict[str, Any]] = []
    collecting = False

    for raw_line in lines:
        line = raw_line.rstrip()
        if line in OWNER_SUITE_HEADINGS:
            collecting = True
            continue
        if not collecting:
            continue
        stripped = line.strip()
        if not stripped:
            if suites:
                break
            continue
        if not stripped.startswith("- "):
            if suites:
                break
            continue
        body = stripped[2:]
        tests_part, separator, targets_part = body.partition("->")
        suites.append(
            {
                "tests": _extract_backtick_items(tests_part),
                "targets": _extract_backtick_items(targets_part),
                "target_summary": targets_part.strip() if separator else tests_part.strip(),
            }
        )
    return suites


def _parse_first_validation_commands(path: Path) -> list[str]:
    lines = _read_lines(path)
    commands: list[str] = []
    collecting = False

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        if line.rstrip() == FIRST_VALIDATION_HEADING:
            collecting = True
            continue
        if not collecting:
            continue
        if not line.strip():
            if commands:
                break
            continue
        if not line.startswith("    "):
            if commands:
                break
            continue
        commands.append(line.strip())
    return commands


def _collect_owner_suite_plans(exec_plans_dir: Path) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for path in sorted(exec_plans_dir.glob("*.md")):
        suites = _parse_owner_suites(path)
        if not suites:
            continue
        plans.append(
            {
                "plan_path": path.relative_to(REPO_ROOT).as_posix(),
                "owner_heading": next(
                    (heading for heading in OWNER_SUITE_HEADINGS if heading in path.read_text(encoding="utf-8")),
                    OWNER_SUITE_HEADINGS[0],
                ),
                "suites": suites,
                "first_validation_commands": _parse_first_validation_commands(path),
            }
        )
    return plans


def _collect_instruction_metadata(instructions_dir: Path) -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for path in sorted(instructions_dir.glob("*.instructions.md")):
        frontmatter = _parse_frontmatter(path)
        metadata.append(
            {
                "file_path": path.relative_to(REPO_ROOT).as_posix(),
                "name": frontmatter.get("name", path.stem),
                "description": frontmatter.get("description", ""),
                "apply_to": list(frontmatter.get("applyTo", [])),
            }
        )
    return metadata


def _collect_agent_metadata(agents_dir: Path) -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for path in sorted(agents_dir.glob("*.agent.md")):
        frontmatter = _parse_frontmatter(path)
        metadata.append(
            {
                "file_path": path.relative_to(REPO_ROOT).as_posix(),
                "name": frontmatter.get("name", path.stem),
                "description": frontmatter.get("description", ""),
                "user_invocable": bool(frontmatter.get("user-invocable", False)),
            }
        )
    return metadata


def _simplify_check_catalog(catalog: dict[str, Any], *, source: str | None = None) -> list[dict[str, Any]]:
    simplified: list[dict[str, Any]] = []
    for entry in catalog["checks"]:
        if source is not None and entry.get("source") != source:
            continue
        simplified.append(
            {
                "id": entry["id"],
                "label": entry["label"],
                "source": entry.get("source", source or "pipeline"),
                "owner_surface": entry["owner_surface"],
                "estimated_cost": entry["estimated_cost"],
                "path_globs": list(entry["path_globs"]),
                "owner_test_targets": list(entry["owner_test_targets"]),
                "command": entry["command"],
            }
        )
    return simplified


def build_ai_work_map() -> dict[str, Any]:
    from sattlint.devtools import repo_audit_entrypoints

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
        "generated_from": {
            "validation_map": VALIDATION_MAP_PATH.relative_to(REPO_ROOT).as_posix(),
            "active_exec_plans": f"{ACTIVE_EXEC_PLANS_DIR.relative_to(REPO_ROOT).as_posix()}/*.md",
            "pipeline_catalog": "sattlint.devtools.pipeline.build_pipeline_check_catalog(profile='full')",
            "repo_audit_catalog": (
                "sattlint.devtools.repo_audit_entrypoints.build_repo_audit_check_catalog(profile='full')"
            ),
        },
        "validation_routes": _parse_validation_routes(VALIDATION_MAP_PATH),
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


def _collect_relevant_checks(work_map: dict[str, Any], recommended_check_ids: list[str]) -> list[dict[str, Any]]:
    checks = [*work_map.get("pipeline_checks", []), *work_map.get("repo_audit_checks", [])]
    check_lookup = {str(entry["id"]): entry for entry in checks if isinstance(entry, dict) and "id" in entry}
    return [check_lookup[check_id] for check_id in recommended_check_ids if check_id in check_lookup]


def _match_instruction_files(work_map: dict[str, Any], changed_files: list[str]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for entry in work_map.get("instructions", []):
        if not isinstance(entry, dict):
            continue
        apply_to = [str(pattern) for pattern in entry.get("apply_to", [])]
        matched_files = [path_text for path_text in changed_files if path_matches_globs(path_text, apply_to)]
        if not matched_files:
            continue
        matched.append(
            {
                "name": str(entry.get("name", "unknown")),
                "file_path": str(entry.get("file_path", "")),
                "description": str(entry.get("description", "")),
                "matched_files": matched_files,
            }
        )
    return matched


def _match_owner_suites(
    work_map: dict[str, Any], changed_files: list[str], owner_test_targets: list[str]
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    owner_test_set = set(owner_test_targets)
    for plan in work_map.get("owner_suite_plans", []):
        if not isinstance(plan, dict):
            continue
        for suite in plan.get("suites", []):
            if not isinstance(suite, dict):
                continue
            targets = [str(item) for item in suite.get("targets", [])]
            tests = [str(item) for item in suite.get("tests", [])]
            matched_targets = [path_text for path_text in changed_files if path_matches_globs(path_text, targets)]
            matched_tests = [test_path for test_path in tests if test_path in owner_test_set]
            score = len(matched_targets) * 8 + len(matched_tests) * 2
            if score <= 0:
                continue
            ranked.append(
                {
                    "plan_path": str(plan.get("plan_path", "")),
                    "tests": tests,
                    "targets": targets,
                    "matched_targets": matched_targets,
                    "matched_tests": matched_tests,
                    "first_validation_commands": list(plan.get("first_validation_commands", [])),
                    "score": score,
                }
            )
    ranked.sort(key=lambda item: (-item["score"], item["plan_path"], item["tests"]))
    return ranked[:3]


def _match_agents(
    work_map: dict[str, Any],
    changed_files: list[str],
    owner_surfaces: list[str],
    selected_surface: str,
) -> list[dict[str, Any]]:
    agent_lookup = {
        str(entry.get("name", "unknown")): entry for entry in work_map.get("agents", []) if isinstance(entry, dict)
    }
    ranked: list[dict[str, Any]] = []
    for rule in work_map.get("agent_routing", []):
        if not isinstance(rule, dict):
            continue
        agent_name = str(rule.get("agent_name", "")).strip()
        if not agent_name or agent_name not in agent_lookup:
            continue
        path_globs = [str(pattern) for pattern in rule.get("path_globs", [])]
        matched_files = [path_text for path_text in changed_files if path_matches_globs(path_text, path_globs)]
        keywords = [str(keyword).casefold() for keyword in rule.get("owner_surface_keywords", [])]
        matched_owner_surfaces = [
            surface for surface in owner_surfaces if any(keyword in surface.casefold() for keyword in keywords)
        ]
        selected_surface_match = selected_surface in {str(item) for item in rule.get("selected_surfaces", [])}
        score = len(matched_files) * 6 + len(matched_owner_surfaces) * 2 + (1 if selected_surface_match else 0)
        if score <= 0:
            continue
        metadata = agent_lookup[agent_name]
        ranked.append(
            {
                "name": agent_name,
                "file_path": str(metadata.get("file_path", "")),
                "description": str(metadata.get("description", "")),
                "matched_files": matched_files,
                "matched_owner_surfaces": matched_owner_surfaces,
                "score": score,
            }
        )
    ranked.sort(key=lambda item: (-item["score"], item["name"]))
    return ranked[:3]


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
    instruction_files = _match_instruction_files(resolved_work_map, normalized_changed_files)
    first_validation_commands: list[str] = []
    for suite in nearest_owner_suites:
        for command in suite.get("first_validation_commands", []):
            command_text = str(command).strip()
            if command_text and command_text not in first_validation_commands:
                first_validation_commands.append(command_text)

    return {
        "primary_agent": None if not owning_agents else owning_agents[0]["name"],
        "owning_agents": owning_agents,
        "instruction_files": instruction_files,
        "nearest_owner_suites": nearest_owner_suites,
        "first_validation_commands": first_validation_commands,
    }


def render_ai_work_map() -> str:
    return json.dumps(build_ai_work_map(), indent=2, sort_keys=True) + "\n"


def render_session_context_map() -> str:
    return json.dumps(build_session_context_map(), indent=2, sort_keys=True) + "\n"


def write_ai_work_map(output_path: Path = DEFAULT_OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_ai_work_map(), encoding="utf-8")
    return output_path


def write_session_context_map(output_path: Path = DEFAULT_SESSION_CONTEXT_OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_session_context_map(), encoding="utf-8")
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
    parser.add_argument("--write", action="store_true", help="Write the generated JSON to --output.")
    parser.add_argument("--check", action="store_true", help="Fail when --output does not match the generated JSON.")
    parser.add_argument("--stdout", action="store_true", help="Print the generated JSON to stdout.")
    args = parser.parse_args(argv)

    rendered = render_ai_work_map()
    session_rendered = render_session_context_map()
    if args.check:
        existing = args.output.read_text(encoding="utf-8") if args.output.exists() else None
        session_existing = args.session_output.read_text(encoding="utf-8") if args.session_output.exists() else None
        if existing != rendered or session_existing != session_rendered:
            return 1
    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        args.session_output.parent.mkdir(parents=True, exist_ok=True)
        args.session_output.write_text(session_rendered, encoding="utf-8")
    if args.stdout or (not args.write and not args.check):
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
