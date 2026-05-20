"""Planning and rendering helpers for the AI work map."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any, TypedDict, cast

from .json_helpers import nonempty_string_entries

type JsonDict = dict[str, object]


class InstructionMatch(TypedDict):
    name: str
    file_path: str
    description: str
    matched_files: list[str]


class PlanningInstructionEntry(TypedDict):
    name: str
    file_path: str
    description: str
    matched_files: list[str]
    selection_reasons: list[str]


class OwnerSuiteMatch(TypedDict):
    plan_path: str
    tests: list[str]
    targets: list[str]
    matched_targets: list[str]
    matched_tests: list[str]
    first_validation_commands: list[str]
    score: int


class AgentMatch(TypedDict):
    name: str
    file_path: str
    description: str
    matched_files: list[str]
    matched_owner_surfaces: list[str]
    score: int


class FinishGateTemplate(TypedDict):
    selected_surface: str
    command: str
    description: str
    includes: list[str]


class BlockingInvariantMatch(TypedDict):
    id: str
    summary: str
    details: str
    matched_files: list[str]


def _dict_entries(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    entries: list[JsonDict] = []
    for item in items:
        if isinstance(item, dict):
            entries.append(cast(JsonDict, item))
    return entries


_string_entries = partial(nonempty_string_entries, include_tuples=True, strip=True)


def _string_value(value: object, default: str = "") -> str:
    return default if value is None else str(value)


def instruction_lookup(work_map: dict[str, Any]) -> dict[str, JsonDict]:
    lookup: dict[str, JsonDict] = {}
    for entry in _dict_entries(work_map.get("instructions")):
        file_path = _string_value(entry.get("file_path")).strip()
        if not file_path:
            continue
        lookup[file_path] = entry
    return lookup


def simplify_check_catalog(catalog: dict[str, Any], *, source: str | None = None) -> list[dict[str, Any]]:
    simplified: list[dict[str, Any]] = []
    for entry in _dict_entries(catalog.get("checks")):
        if source is not None and _string_value(entry.get("source")) != source:
            continue
        simplified.append(
            {
                "id": _string_value(entry.get("id")),
                "label": _string_value(entry.get("label")),
                "source": _string_value(entry.get("source"), source or "pipeline"),
                "owner_surface": _string_value(entry.get("owner_surface")),
                "estimated_cost": _string_value(entry.get("estimated_cost")),
                "path_globs": _string_entries(entry.get("path_globs")),
                "owner_test_targets": _string_entries(entry.get("owner_test_targets")),
                "ai_summary": _string_value(entry.get("ai_summary")),
                "ai_instruction_files": _string_entries(entry.get("ai_instruction_files")),
                "command": _string_value(entry.get("command")),
            }
        )
    return simplified


def all_check_entries(work_map: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for collection_name in ("pipeline_checks", "repo_audit_checks"):
        checks.extend(_dict_entries(work_map.get(collection_name)))
    return checks


def render_check_section(title: str, checks: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not checks:
        lines.extend(["- none", ""])
        return lines
    for entry in checks:
        check_id = _string_value(entry.get("id"), "unknown")
        lines.extend(
            [
                f"### `{check_id}`",
                "",
                f"- Label: {_string_value(entry.get('label'))}",
                f"- Owner surface: {_string_value(entry.get('owner_surface'))}",
                f"- Estimated cost: {_string_value(entry.get('estimated_cost'))}",
                f"- AI summary: {_string_value(entry.get('ai_summary'))}",
                "- AI instruction files:",
            ]
        )
        instruction_files = _string_entries(entry.get("ai_instruction_files"))
        if not instruction_files:
            lines.append("  - none")
        else:
            for path_text in instruction_files:
                lines.append(f"  - `{path_text}`")
        lines.append("- Owner tests:")
        owner_tests = _string_entries(entry.get("owner_test_targets"))
        if not owner_tests:
            lines.append("  - none")
        else:
            for path_text in owner_tests:
                lines.append(f"  - `{path_text}`")
        lines.extend(
            [
                f"- Command: `{_string_value(entry.get('command'))}`",
                "",
            ]
        )
    return lines


def collect_relevant_checks(work_map: dict[str, Any], recommended_check_ids: list[str]) -> list[JsonDict]:
    checks = [
        *_dict_entries(work_map.get("pipeline_checks")),
        *_dict_entries(work_map.get("repo_audit_checks")),
    ]
    check_lookup: dict[str, JsonDict] = {str(entry["id"]): entry for entry in checks if "id" in entry}
    return [check_lookup[check_id] for check_id in recommended_check_ids if check_id in check_lookup]


def match_instruction_files(
    work_map: dict[str, Any],
    changed_files: list[str],
    *,
    path_matches_globs: Callable[[str, list[str]], bool],
) -> list[InstructionMatch]:
    matched: list[InstructionMatch] = []
    for entry in _dict_entries(work_map.get("instructions")):
        apply_to = _string_entries(entry.get("apply_to"))
        matched_files = [path_text for path_text in changed_files if path_matches_globs(path_text, apply_to)]
        if not matched_files:
            continue
        matched.append(
            {
                "name": _string_value(entry.get("name"), "unknown"),
                "file_path": _string_value(entry.get("file_path")),
                "description": _string_value(entry.get("description")),
                "matched_files": matched_files,
            }
        )
    return matched


def merge_instruction_files_for_planning(
    work_map: dict[str, Any],
    changed_files: list[str],
    relevant_checks: list[JsonDict],
    *,
    match_instruction_files: Callable[[dict[str, Any], list[str]], list[InstructionMatch]],
) -> list[PlanningInstructionEntry]:
    lookup = instruction_lookup(work_map)
    merged: dict[str, PlanningInstructionEntry] = {}
    ordered_paths: list[str] = []

    def ensure_entry(file_path: str) -> PlanningInstructionEntry:
        if file_path not in merged:
            metadata = lookup.get(file_path)
            merged[file_path] = {
                "name": file_path if metadata is None else _string_value(metadata.get("name"), file_path),
                "file_path": file_path,
                "description": "" if metadata is None else _string_value(metadata.get("description")),
                "matched_files": [],
                "selection_reasons": [],
            }
            ordered_paths.append(file_path)
        return merged[file_path]

    for entry in match_instruction_files(work_map, changed_files):
        file_path = entry["file_path"].strip()
        if not file_path:
            continue
        resolved = ensure_entry(file_path)
        for matched_file in entry["matched_files"]:
            matched_text = matched_file.strip()
            if matched_text and matched_text not in resolved["matched_files"]:
                resolved["matched_files"].append(matched_text)
        if "changed-files" not in resolved["selection_reasons"]:
            resolved["selection_reasons"].append("changed-files")

    for check in relevant_checks:
        check_id = _string_value(check.get("id")).strip()
        reason = f"recommended-check:{check_id}" if check_id else "recommended-check"
        for file_path in _string_entries(check.get("ai_instruction_files")):
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
) -> list[OwnerSuiteMatch]:
    ranked: list[OwnerSuiteMatch] = []
    owner_test_set = set(owner_test_targets)
    for plan in _dict_entries(work_map.get("owner_suite_plans")):
        for suite in _dict_entries(plan.get("suites")):
            targets = _string_entries(suite.get("targets"))
            tests = _string_entries(suite.get("tests"))
            matched_targets = [path_text for path_text in changed_files if path_matches_globs(path_text, targets)]
            matched_tests = [test_path for test_path in tests if test_path in owner_test_set]
            score = len(matched_targets) * 8 + len(matched_tests) * 2
            if score <= 0:
                continue
            ranked.append(
                {
                    "plan_path": _string_value(plan.get("plan_path")),
                    "tests": tests,
                    "targets": targets,
                    "matched_targets": matched_targets,
                    "matched_tests": matched_tests,
                    "first_validation_commands": _string_entries(plan.get("first_validation_commands")),
                    "score": score,
                }
            )
    ranked.sort(key=lambda item: (-item["score"], item["plan_path"], tuple(item["tests"])))
    return ranked[:3]


def match_agents(
    work_map: dict[str, Any],
    changed_files: list[str],
    owner_surfaces: list[str],
    selected_surface: str,
    *,
    path_matches_globs: Callable[[str, list[str]], bool],
) -> list[AgentMatch]:
    agent_lookup: dict[str, JsonDict] = {}
    for entry in _dict_entries(work_map.get("agents")):
        agent_lookup[_string_value(entry.get("name"), "unknown")] = entry
    ranked: list[AgentMatch] = []
    for rule in _dict_entries(work_map.get("agent_routing")):
        agent_name = _string_value(rule.get("agent_name")).strip()
        if not agent_name or agent_name not in agent_lookup:
            continue
        path_globs = _string_entries(rule.get("path_globs"))
        matched_files = [path_text for path_text in changed_files if path_matches_globs(path_text, path_globs)]
        keywords = [keyword.casefold() for keyword in _string_entries(rule.get("owner_surface_keywords"))]
        matched_owner_surfaces = [
            surface for surface in owner_surfaces if any(keyword in surface.casefold() for keyword in keywords)
        ]
        selected_surface_match = selected_surface in set(_string_entries(rule.get("selected_surfaces")))
        score = len(matched_files) * 6 + len(matched_owner_surfaces) * 2 + (1 if selected_surface_match else 0)
        if score <= 0:
            continue
        metadata = agent_lookup[agent_name]
        ranked.append(
            {
                "name": agent_name,
                "file_path": _string_value(metadata.get("file_path")),
                "description": _string_value(metadata.get("description")),
                "matched_files": matched_files,
                "matched_owner_surfaces": matched_owner_surfaces,
                "score": score,
            }
        )
    ranked.sort(key=lambda item: (-item["score"], item["name"]))
    return ranked[:3]


def select_finish_gate_template(work_map: dict[str, Any], selected_surface: str) -> FinishGateTemplate | None:
    for entry in _dict_entries(work_map.get("finish_gate_templates")):
        if _string_value(entry.get("selected_surface")).strip() != selected_surface:
            continue
        return {
            "selected_surface": selected_surface,
            "command": _string_value(entry.get("command")),
            "description": _string_value(entry.get("description")),
            "includes": _string_entries(entry.get("includes")),
        }
    return None


def match_blocking_invariants(
    work_map: dict[str, Any],
    changed_files: list[str],
    selected_surface: str,
    *,
    path_matches_globs: Callable[[str, list[str]], bool],
) -> list[BlockingInvariantMatch]:
    matched: list[BlockingInvariantMatch] = []
    for entry in _dict_entries(work_map.get("blocking_invariant_rules")):
        selected_surfaces = set(_string_entries(entry.get("selected_surfaces")))
        if selected_surfaces and selected_surface not in selected_surfaces:
            continue
        path_globs = _string_entries(entry.get("path_globs"))
        matched_files = [path_text for path_text in changed_files if path_matches_globs(path_text, path_globs)]
        if path_globs and not matched_files:
            continue
        matched.append(
            {
                "id": _string_value(entry.get("id"), "unknown"),
                "summary": _string_value(entry.get("summary")),
                "details": _string_value(entry.get("details")),
                "matched_files": matched_files,
            }
        )
    return matched
