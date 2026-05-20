"""AI work map freshness verification helpers."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any, cast

from sattlint.devtools.json_helpers import nonempty_string_entries
from sattlint.devtools.pipeline_checks import collect_repo_file_inventory, path_matches_globs

type JsonDict = dict[str, object]


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


def _catalog_registry_path(source: str) -> str:
    if source == "pipeline":
        return "src/sattlint/devtools/pipeline_checks.py"
    return "src/sattlint/devtools/repo_audit_entrypoints.py"


def _matched_repo_files(repo_files: list[str], glob_pattern: str) -> list[str]:
    return [path_text for path_text in repo_files if path_matches_globs(path_text, (glob_pattern,))]


def _is_virtual_repo_path_glob(glob_pattern: str) -> bool:
    return glob_pattern.startswith(".git/")


def verify_ai_harness_freshness(
    work_map: dict[str, Any] | None = None,
    session_context_map: dict[str, Any] | None = None,
    *,
    repo_root: Path,
    output_path: Path,
    session_output_path: Path,
    check_catalog_output_path: Path | None = None,
) -> dict[str, Any]:
    from sattlint.devtools import ai_work_map as ai_work_map_module

    resolved_work_map = ai_work_map_module.build_ai_work_map() if work_map is None else work_map
    resolved_session_context_map = (
        ai_work_map_module.build_session_context_map(resolved_work_map)
        if session_context_map is None
        else session_context_map
    )
    resolved_check_catalog_output_path = (
        ai_work_map_module.DEFAULT_CHECK_CATALOG_OUTPUT_PATH
        if check_catalog_output_path is None
        else check_catalog_output_path
    )
    repo_files = collect_repo_file_inventory(repo_root)
    issues: list[dict[str, Any]] = []

    expected_work_map = ai_work_map_module.render_json(resolved_work_map)
    if not output_path.exists():
        issues.append(
            {
                "issue_id": "missing-generated-ai-work-map",
                "severity": "high",
                "message": "Checked-in ai-work-map.json is missing.",
                "path": output_path.relative_to(repo_root).as_posix(),
            }
        )
    elif output_path.read_text(encoding="utf-8") != expected_work_map:
        issues.append(
            {
                "issue_id": "generated-ai-work-map-drift",
                "severity": "high",
                "message": "Checked-in ai-work-map.json does not match the generated routing map.",
                "path": output_path.relative_to(repo_root).as_posix(),
            }
        )

    expected_session_context_map = ai_work_map_module.render_json(resolved_session_context_map)
    if not session_output_path.exists():
        issues.append(
            {
                "issue_id": "missing-generated-ai-session-context-map",
                "severity": "high",
                "message": "Checked-in ai-session-context-map.json is missing.",
                "path": session_output_path.relative_to(repo_root).as_posix(),
            }
        )
    elif session_output_path.read_text(encoding="utf-8") != expected_session_context_map:
        issues.append(
            {
                "issue_id": "generated-ai-session-context-map-drift",
                "severity": "high",
                "message": "Checked-in ai-session-context-map.json does not match the generated session routing map.",
                "path": session_output_path.relative_to(repo_root).as_posix(),
            }
        )

    expected_check_catalog = ai_work_map_module.render_ai_check_catalog(resolved_work_map)
    if not resolved_check_catalog_output_path.exists():
        issues.append(
            {
                "issue_id": "missing-generated-ai-check-catalog",
                "severity": "high",
                "message": "Checked-in ai-check-catalog.md is missing.",
                "path": resolved_check_catalog_output_path.relative_to(repo_root).as_posix(),
            }
        )
    elif resolved_check_catalog_output_path.read_text(encoding="utf-8") != expected_check_catalog:
        issues.append(
            {
                "issue_id": "generated-ai-check-catalog-drift",
                "severity": "high",
                "message": "Checked-in ai-check-catalog.md does not match the generated AI check reference.",
                "path": resolved_check_catalog_output_path.relative_to(repo_root).as_posix(),
            }
        )

    instructions = _dict_entries(resolved_work_map.get("instructions"))
    for entry in instructions:
        file_path = _string_value(entry.get("file_path")).strip()
        apply_to = _string_entries(entry.get("apply_to"))
        if not apply_to:
            issues.append(
                {
                    "issue_id": "orphaned-instruction",
                    "severity": "high",
                    "message": "Instruction metadata is missing applyTo globs, so it cannot be auto-selected.",
                    "path": file_path,
                }
            )
            continue
        for pattern in apply_to:
            if "\\" in pattern:
                issues.append(
                    {
                        "issue_id": "backslash-instruction-applyto-glob",
                        "severity": "medium",
                        "message": "Instruction applyTo globs must use '/' separators.",
                        "path": file_path,
                        "pattern": pattern,
                    }
                )
                continue
            if _matched_repo_files(repo_files, pattern):
                continue
            issues.append(
                {
                    "issue_id": "stale-instruction-applyto-glob",
                    "severity": "medium",
                    "message": "Instruction applyTo glob does not match any tracked repo files.",
                    "path": file_path,
                    "pattern": pattern,
                }
            )

    agents: dict[str, JsonDict] = {}
    for entry in _dict_entries(resolved_work_map.get("agents")):
        agent_name = _string_value(entry.get("name")).strip()
        if agent_name:
            agents[agent_name] = entry
    routed_agents: set[str] = set()
    for rule in _dict_entries(resolved_work_map.get("agent_routing")):
        agent_name = _string_value(rule.get("agent_name")).strip()
        if not agent_name:
            continue
        if agent_name not in agents:
            issues.append(
                {
                    "issue_id": "dangling-agent-routing",
                    "severity": "high",
                    "message": "Agent routing rule references an agent file that does not exist.",
                    "path": "src/sattlint/devtools/ai_work_map.py",
                    "agent_name": agent_name,
                }
            )
            continue
        routed_agents.add(agent_name)
        path_globs = _string_entries(rule.get("path_globs"))
        if not path_globs:
            issues.append(
                {
                    "issue_id": "orphaned-agent-routing",
                    "severity": "high",
                    "message": "Agent routing rule is missing path globs.",
                    "path": "src/sattlint/devtools/ai_work_map.py",
                    "agent_name": agent_name,
                }
            )
            continue
        for pattern in path_globs:
            if "\\" in pattern:
                issues.append(
                    {
                        "issue_id": "backslash-agent-routing-glob",
                        "severity": "medium",
                        "message": "Agent routing globs must use '/' separators.",
                        "path": "src/sattlint/devtools/ai_work_map.py",
                        "agent_name": agent_name,
                        "pattern": pattern,
                    }
                )
                continue
            if _is_virtual_repo_path_glob(pattern):
                continue
            if _matched_repo_files(repo_files, pattern):
                continue
            issues.append(
                {
                    "issue_id": "stale-agent-routing-glob",
                    "severity": "medium",
                    "message": "Agent routing glob does not match any tracked repo files.",
                    "path": "src/sattlint/devtools/ai_work_map.py",
                    "agent_name": agent_name,
                    "pattern": pattern,
                }
            )

    for agent_name, entry in agents.items():
        if agent_name in routed_agents or not bool(entry.get("user_invocable", False)):
            continue
        issues.append(
            {
                "issue_id": "orphaned-agent",
                "severity": "high",
                "message": "User-invocable agent has no routing rule and cannot be recommended automatically.",
                "path": _string_value(entry.get("file_path")).strip(),
                "agent_name": agent_name,
            }
        )

    instruction_lookup = ai_work_map_module.instruction_lookup(resolved_work_map)
    for collection_name in ("pipeline_checks", "repo_audit_checks"):
        for entry in _dict_entries(resolved_work_map.get(collection_name)):
            check_id = _string_value(entry.get("id")).strip()
            if not check_id:
                continue
            source = _string_value(
                entry.get("source"),
                "pipeline" if collection_name == "pipeline_checks" else "repo-audit",
            )
            registry_path = _catalog_registry_path(source)
            ai_summary = _string_value(entry.get("ai_summary")).strip()
            if not ai_summary:
                issues.append(
                    {
                        "issue_id": "undocumented-check",
                        "severity": "high",
                        "message": "Check metadata is missing ai_summary, so the AI reference layer cannot document it.",
                        "path": registry_path,
                        "check_id": check_id,
                    }
                )
            ai_instruction_files = _string_entries(entry.get("ai_instruction_files"))
            if not ai_instruction_files:
                issues.append(
                    {
                        "issue_id": "unmapped-check",
                        "severity": "high",
                        "message": "Check metadata is missing ai_instruction_files, so planning-context cannot surface the right scoped instructions.",
                        "path": registry_path,
                        "check_id": check_id,
                    }
                )
                continue

            for instruction_path in ai_instruction_files:
                if "\\" in instruction_path:
                    issues.append(
                        {
                            "issue_id": "backslash-check-instruction-path",
                            "severity": "medium",
                            "message": "Check instruction paths must use '/' separators.",
                            "path": registry_path,
                            "check_id": check_id,
                            "instruction_path": instruction_path,
                        }
                    )
                    continue
                if instruction_path in instruction_lookup:
                    continue
                issues.append(
                    {
                        "issue_id": "dangling-check-instruction",
                        "severity": "high",
                        "message": "Check metadata references an instruction file that is not present in the instruction registry.",
                        "path": registry_path,
                        "check_id": check_id,
                        "instruction_path": instruction_path,
                    }
                )

    return {
        "kind": "sattlint.ai_harness_freshness",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.ai_work_map",
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
    }


__all__ = ["verify_ai_harness_freshness"]
