"""Planning and rendering helpers for the AI work map."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def instruction_lookup(work_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for entry in work_map.get("instructions", []):
        if not isinstance(entry, dict):
            continue
        file_path = str(entry.get("file_path", "")).strip()
        if not file_path:
            continue
        lookup[file_path] = entry
    return lookup


def simplify_check_catalog(catalog: dict[str, Any], *, source: str | None = None) -> list[dict[str, Any]]:
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
                "ai_summary": str(entry.get("ai_summary", "")),
                "ai_instruction_files": [
                    str(item) for item in entry.get("ai_instruction_files", []) if str(item).strip()
                ],
                "command": entry["command"],
            }
        )
    return simplified


def all_check_entries(work_map: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for collection_name in ("pipeline_checks", "repo_audit_checks"):
        for entry in work_map.get(collection_name, []):
            if isinstance(entry, dict):
                checks.append(entry)
    return checks


def render_check_section(title: str, checks: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not checks:
        lines.extend(["- none", ""])
        return lines
    for entry in checks:
        check_id = str(entry.get("id", "unknown"))
        lines.extend(
            [
                f"### `{check_id}`",
                "",
                f"- Label: {entry.get('label', '')!s}",
                f"- Owner surface: {entry.get('owner_surface', '')!s}",
                f"- Estimated cost: {entry.get('estimated_cost', '')!s}",
                f"- AI summary: {entry.get('ai_summary', '')!s}",
                "- AI instruction files:",
            ]
        )
        instruction_files = [
            str(path_text) for path_text in entry.get("ai_instruction_files", []) if str(path_text).strip()
        ]
        if not instruction_files:
            lines.append("  - none")
        else:
            for path_text in instruction_files:
                lines.append(f"  - `{path_text}`")
        lines.append("- Owner tests:")
        owner_tests = [str(path_text) for path_text in entry.get("owner_test_targets", []) if str(path_text).strip()]
        if not owner_tests:
            lines.append("  - none")
        else:
            for path_text in owner_tests:
                lines.append(f"  - `{path_text}`")
        lines.extend(
            [
                f"- Command: `{entry.get('command', '')!s}`",
                "",
            ]
        )
    return lines


def collect_relevant_checks(work_map: dict[str, Any], recommended_check_ids: list[str]) -> list[dict[str, Any]]:
    checks = [*work_map.get("pipeline_checks", []), *work_map.get("repo_audit_checks", [])]
    check_lookup = {str(entry["id"]): entry for entry in checks if isinstance(entry, dict) and "id" in entry}
    return [check_lookup[check_id] for check_id in recommended_check_ids if check_id in check_lookup]


def match_instruction_files(
    work_map: dict[str, Any],
    changed_files: list[str],
    *,
    path_matches_globs: Callable[[str, list[str]], bool],
) -> list[dict[str, Any]]:
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


def merge_instruction_files_for_planning(
    work_map: dict[str, Any],
    changed_files: list[str],
    relevant_checks: list[dict[str, Any]],
    *,
    match_instruction_files: Callable[[dict[str, Any], list[str]], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    lookup = instruction_lookup(work_map)
    merged: dict[str, dict[str, Any]] = {}
    ordered_paths: list[str] = []

    def ensure_entry(file_path: str) -> dict[str, Any]:
        if file_path not in merged:
            metadata = lookup.get(file_path, {})
            merged[file_path] = {
                "name": str(metadata.get("name", file_path)),
                "file_path": file_path,
                "description": str(metadata.get("description", "")),
                "matched_files": [],
                "selection_reasons": [],
            }
            ordered_paths.append(file_path)
        return merged[file_path]

    for entry in match_instruction_files(work_map, changed_files):
        file_path = str(entry.get("file_path", "")).strip()
        if not file_path:
            continue
        resolved = ensure_entry(file_path)
        for matched_file in entry.get("matched_files", []):
            matched_text = str(matched_file).strip()
            if matched_text and matched_text not in resolved["matched_files"]:
                resolved["matched_files"].append(matched_text)
        if "changed-files" not in resolved["selection_reasons"]:
            resolved["selection_reasons"].append("changed-files")

    for check in relevant_checks:
        check_id = str(check.get("id", "")).strip()
        reason = f"recommended-check:{check_id}" if check_id else "recommended-check"
        for raw_path in check.get("ai_instruction_files", []):
            file_path = str(raw_path).strip()
            if not file_path:
                continue
            resolved = ensure_entry(file_path)
            if reason not in resolved["selection_reasons"]:
                resolved["selection_reasons"].append(reason)

    return [merged[file_path] for file_path in ordered_paths]


def match_owner_suites(
    work_map: dict[str, Any],
    changed_files: list[str],
    owner_test_targets: list[str],
    *,
    path_matches_globs: Callable[[str, list[str]], bool],
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


def match_agents(
    work_map: dict[str, Any],
    changed_files: list[str],
    owner_surfaces: list[str],
    selected_surface: str,
    *,
    path_matches_globs: Callable[[str, list[str]], bool],
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


def select_finish_gate_template(work_map: dict[str, Any], selected_surface: str) -> dict[str, Any] | None:
    for entry in work_map.get("finish_gate_templates", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("selected_surface", "")).strip() != selected_surface:
            continue
        return {
            "selected_surface": selected_surface,
            "command": str(entry.get("command", "")),
            "description": str(entry.get("description", "")),
            "includes": [str(item) for item in entry.get("includes", []) if str(item).strip()],
        }
    return None


def match_blocking_invariants(
    work_map: dict[str, Any],
    changed_files: list[str],
    selected_surface: str,
    *,
    path_matches_globs: Callable[[str, list[str]], bool],
) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for entry in work_map.get("blocking_invariant_rules", []):
        if not isinstance(entry, dict):
            continue
        selected_surfaces = {str(item).strip() for item in entry.get("selected_surfaces", []) if str(item).strip()}
        if selected_surfaces and selected_surface not in selected_surfaces:
            continue
        path_globs = [str(pattern) for pattern in entry.get("path_globs", []) if str(pattern).strip()]
        matched_files = [path_text for path_text in changed_files if path_matches_globs(path_text, path_globs)]
        if path_globs and not matched_files:
            continue
        matched.append(
            {
                "id": str(entry.get("id", "unknown")),
                "summary": str(entry.get("summary", "")),
                "details": str(entry.get("details", "")),
                "matched_files": matched_files,
            }
        )
    return matched
