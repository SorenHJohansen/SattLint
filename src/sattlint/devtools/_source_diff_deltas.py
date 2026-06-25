"""Delta and promotion helpers for source diff reports."""

from __future__ import annotations

import difflib
from collections.abc import Mapping
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture
from sattlint.devtools._source_diff_details import (
    collect_moduletype_instance_details,
    format_qualifiers,
    format_submodule_summary,
    format_variable_summary,
    is_promoted_moduletype_name,
    module_content_signature,
    modulecode_entity_code_lines,
    moduletype_detail,
    path_has_prefix,
)


def format_summary_delta(summary_key: str, draft_value: int, official_value: int) -> str:
    label = summary_key.replace("_", " ")
    return f"{label}: {official_value} -> {draft_value}"


def format_change_value(value: object) -> str:
    return "<none>" if value in {None, ""} else str(value)


def diff_variable_details(label: str, draft: list[dict[str, Any]], official: list[dict[str, Any]]) -> list[str]:
    draft_map = {detail["name"].casefold(): detail for detail in draft}
    official_map = {detail["name"].casefold(): detail for detail in official}
    details: list[str] = []

    for key in sorted(draft_map.keys() - official_map.keys()):
        details.append(f"Added {label} {format_variable_summary(draft_map[key])}")
    for key in sorted(official_map.keys() - draft_map.keys()):
        details.append(f"Removed {label} {format_variable_summary(official_map[key])}")
    for key in sorted(draft_map.keys() & official_map.keys()):
        draft_detail = draft_map[key]
        official_detail = official_map[key]
        if draft_detail == official_detail:
            continue
        fragments: list[str] = []
        if draft_detail["datatype"] != official_detail["datatype"]:
            fragments.append(
                f"datatype {format_change_value(official_detail['datatype'])} -> {format_change_value(draft_detail['datatype'])}"
            )
        if draft_detail["qualifiers"] != official_detail["qualifiers"]:
            fragments.append(f"qualifiers {format_qualifiers(official_detail)} -> {format_qualifiers(draft_detail)}")
        if draft_detail["init_value"] != official_detail["init_value"]:
            fragments.append(
                f"init {format_change_value(official_detail['init_value'])} -> {format_change_value(draft_detail['init_value'])}"
            )
        if draft_detail["description"] != official_detail["description"]:
            fragments.append(
                f"description {format_change_value(official_detail['description'])} -> {format_change_value(draft_detail['description'])}"
            )
        if draft_detail["init_is_duration"] != official_detail["init_is_duration"]:
            fragments.append(
                "init_is_duration "
                f"{format_change_value(official_detail['init_is_duration'])} -> {format_change_value(draft_detail['init_is_duration'])}"
            )
        details.append(f"Changed {label} {draft_detail['name']} ({'; '.join(fragments)})")

    return details


def diff_submodule_details(draft: list[dict[str, Any]], official: list[dict[str, Any]]) -> list[str]:
    draft_map = {detail["name"].casefold(): detail for detail in draft}
    official_map = {detail["name"].casefold(): detail for detail in official}
    details: list[str] = []

    for key in sorted(draft_map.keys() - official_map.keys()):
        details.append(f"Added submodule {format_submodule_summary(draft_map[key])}")
    for key in sorted(official_map.keys() - draft_map.keys()):
        details.append(f"Removed submodule {format_submodule_summary(official_map[key])}")
    for key in sorted(draft_map.keys() & official_map.keys()):
        draft_detail = draft_map[key]
        official_detail = official_map[key]
        if draft_detail == official_detail:
            continue
        fragments: list[str] = []
        if draft_detail["kind"] != official_detail["kind"]:
            fragments.append(f"kind {official_detail['kind']} -> {draft_detail['kind']}")
        if draft_detail.get("moduletype_name") != official_detail.get("moduletype_name"):
            fragments.append(
                "moduletype "
                f"{format_change_value(official_detail.get('moduletype_name'))} -> {format_change_value(draft_detail.get('moduletype_name'))}"
            )
        if draft_detail["parameter_mappings"] != official_detail["parameter_mappings"]:
            fragments.append("parameter mappings changed")
        if (draft_detail["signature"] != official_detail["signature"] and not fragments) or (
            draft_detail["signature"] != official_detail["signature"] and "definition changed" not in fragments
        ):
            fragments.append("definition changed")
        details.append(f"Changed submodule {draft_detail['name']} ({'; '.join(fragments)})")

    return details


def build_inline_diff_lines(*, label: str, name: str, draft_lines: list[str], official_lines: list[str]) -> list[str]:
    return list(
        difflib.unified_diff(
            official_lines,
            draft_lines,
            fromfile=f"previous {label} {name}",
            tofile=f"draft {label} {name}",
            lineterm="",
        )
    )


def diff_modulecode_entities(
    label: str,
    draft_map: dict[str, dict[str, Any]],
    official_map: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    details: list[str] = []
    code_diffs: list[dict[str, Any]] = []

    for key in sorted(draft_map.keys() - official_map.keys()):
        details.append(f"Added {label} {draft_map[key]['name']}")
    for key in sorted(official_map.keys() - draft_map.keys()):
        details.append(f"Removed {label} {official_map[key]['name']}")
    for key in sorted(draft_map.keys() & official_map.keys()):
        draft_detail = draft_map[key]
        official_detail = official_map[key]
        if draft_detail == official_detail:
            continue
        fragments: list[str] = []
        for field_name in ("type", "position", "size", "seqcontrol", "seqtimer"):
            if draft_detail.get(field_name) != official_detail.get(field_name):
                fragments.append(
                    f"{field_name} {format_change_value(official_detail.get(field_name))} -> {format_change_value(draft_detail.get(field_name))}"
                )
        if draft_detail["code_lines"] != official_detail["code_lines"]:
            fragments.append("code changed")
            code_diffs.append(
                {
                    "label": f"{label.title()} {draft_detail['name']}",
                    "diff_lines": build_inline_diff_lines(
                        label=label,
                        name=draft_detail["name"],
                        draft_lines=modulecode_entity_code_lines(draft_detail),
                        official_lines=modulecode_entity_code_lines(official_detail),
                    ),
                }
            )
        details.append(f"Changed {label} {draft_detail['name']} ({'; '.join(fragments)})")

    return details, code_diffs


def diff_modulecode_detail(draft: dict[str, Any], official: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    sequence_details, sequence_diffs = diff_modulecode_entities(
        "sequence",
        cast(dict[str, dict[str, Any]], draft["sequences"]),
        cast(dict[str, dict[str, Any]], official["sequences"]),
    )
    equation_details, equation_diffs = diff_modulecode_entities(
        "equation",
        cast(dict[str, dict[str, Any]], draft["equations"]),
        cast(dict[str, dict[str, Any]], official["equations"]),
    )
    return sequence_details + equation_details, sequence_diffs + equation_diffs


def diff_nested_inline_module_code_diffs(
    draft: Mapping[tuple[str, ...], dict[str, Any]],
    official: Mapping[tuple[str, ...], dict[str, Any]],
) -> list[dict[str, Any]]:
    code_diffs: list[dict[str, Any]] = []

    for key in sorted(draft.keys() & official.keys()):
        draft_detail = draft[key]
        official_detail = official[key]
        _, nested_code_diffs = diff_modulecode_detail(
            cast(dict[str, Any], draft_detail["modulecode"]),
            cast(dict[str, Any], official_detail["modulecode"]),
        )
        for nested_code_diff in nested_code_diffs:
            code_diffs.append(
                {
                    "label": f"{draft_detail['name']} / {nested_code_diff['label']}",
                    "diff_lines": cast(list[str], nested_code_diff["diff_lines"]),
                }
            )

    return code_diffs


def diff_moduledef_detail(draft: dict[str, Any], official: dict[str, Any]) -> list[str]:
    details: list[str] = []
    for field_name in (
        "clipping_bounds",
        "zoom_limits",
        "seq_layers",
        "grid",
        "zoomable",
        "graph_object_count",
        "interact_object_count",
        "properties",
    ):
        if draft[field_name] != official[field_name]:
            details.append(
                f"Changed moduledef {field_name} ({format_change_value(official[field_name])} -> {format_change_value(draft[field_name])})"
            )
    return details


def collect_promoted_singlemodule_entries(
    *,
    draft_bp: BasePicture,
    official_bp: BasePicture,
    official_inline: Mapping[tuple[str, ...], dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[tuple[str, ...]], dict[str, str]]:
    draft_instances = collect_moduletype_instance_details(draft_bp.submodules)
    added_moduletype_details = {
        moduletype.name.casefold(): moduletype_detail(moduletype)
        for moduletype in draft_bp.moduletype_defs or []
        if moduletype.name.casefold()
        not in {existing.name.casefold() for existing in official_bp.moduletype_defs or []}
    }
    added_moduletype_signatures = {
        name: module_content_signature(detail) for name, detail in added_moduletype_details.items()
    }

    entries: list[dict[str, Any]] = []
    promoted_roots: set[tuple[str, ...]] = set()
    promoted_moduletype_sources: dict[str, str] = {}
    for key in sorted(official_inline, key=len):
        if any(path_has_prefix(key, root) for root in promoted_roots):
            continue
        official_detail = official_inline[key]
        if official_detail["module_kind"] != "singlemodule":
            continue

        promoted_moduletype_name: str | None = None
        parameter_mappings_changed = False
        draft_instance = draft_instances.get(key)
        if draft_instance is not None:
            candidate_name = cast(str, draft_instance["moduletype_name"])
            if candidate_name.casefold() in added_moduletype_details:
                promoted_moduletype_name = candidate_name
                parameter_mappings_changed = bool(draft_instance["parameter_mappings"])

        if promoted_moduletype_name is None:
            official_signature = module_content_signature(official_detail)
            matching_added_moduletype_names = [
                cast(str, detail["name"])
                for name, detail in added_moduletype_details.items()
                if added_moduletype_signatures[name] == official_signature
                and is_promoted_moduletype_name(cast(str, official_detail["name"]), cast(str, detail["name"]))
            ]
            if matching_added_moduletype_names:
                promoted_moduletype_name = sorted(matching_added_moduletype_names, key=str.casefold)[0]

        if promoted_moduletype_name is None:
            continue

        promoted_roots.add(key)
        promoted_moduletype_sources[promoted_moduletype_name.casefold()] = cast(str, official_detail["name"])
        details = [f"Promoted to moduletype {promoted_moduletype_name}"]
        if parameter_mappings_changed:
            details.append("Parameter mappings updated on promoted moduletype instance")
        entries.append(
            {
                "name": official_detail["name"],
                "module_kind": official_detail["module_kind"],
                "change_kind": "changed",
                "details": details,
                "code_diffs": [],
            }
        )

    return entries, promoted_roots, promoted_moduletype_sources
