"""Section builders for source diff reports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture
from sattlint.devtools._source_diff_deltas import (
    collect_promoted_singlemodule_entries,
    diff_modulecode_detail,
    diff_moduledef_detail,
    diff_nested_inline_module_code_diffs,
    diff_submodule_details,
    diff_variable_details,
    format_change_value,
    format_summary_delta,
)
from sattlint.devtools._source_diff_details import (
    basepicture_detail,
    collect_inline_module_details,
    datatype_signature,
    entry_name_sort_key,
    format_submodule_summary,
    format_variable_summary,
    modulecode_detail,
    modulecode_signature,
    moduledef_detail,
    moduledef_signature,
    moduletype_detail,
    path_has_prefix,
    submodule_signature,
    variable_details,
)
from sattlint.tracing import collect_ast_summary


def full_module_details(detail: dict[str, Any]) -> list[str]:
    details: list[str] = []
    for variable_detail in cast(list[dict[str, Any]], detail["parameters"]):
        details.append(f"Added parameter {format_variable_summary(variable_detail)}")
    for variable_detail in cast(list[dict[str, Any]], detail["variables"]):
        details.append(f"Added variable {format_variable_summary(variable_detail)}")
    for submodule_detail in cast(list[dict[str, Any]], detail["submodules"]):
        details.append(f"Added submodule {format_submodule_summary(submodule_detail)}")
    moduledef_details = diff_moduledef_detail(
        cast(dict[str, Any], detail["moduledef"]),
        moduledef_detail(None),
    )
    details.extend(detail_text.replace("Changed moduledef ", "Added moduledef ") for detail_text in moduledef_details)
    modulecode_details, _ = diff_modulecode_detail(
        cast(dict[str, Any], detail["modulecode"]),
        modulecode_detail(None),
    )
    details.extend(detail_text.replace("Changed ", "Added ") for detail_text in modulecode_details)
    return details


def build_module_entry(
    name: str,
    *,
    change_kind: str,
    draft: dict[str, Any] | None,
    official: dict[str, Any] | None,
) -> dict[str, Any]:
    details: list[str] = []
    code_diffs: list[dict[str, Any]] = []

    if draft is not None and official is None:
        details = full_module_details(draft)
        return {
            "name": name,
            "module_kind": draft["module_kind"],
            "change_kind": change_kind,
            "details": details,
            "code_diffs": code_diffs,
        }
    if draft is None and official is not None:
        details = [detail.replace("Added ", "Removed ") for detail in full_module_details(official)]
        return {
            "name": name,
            "module_kind": official["module_kind"],
            "change_kind": change_kind,
            "details": details,
            "code_diffs": code_diffs,
        }

    if draft is None or official is None:
        raise ValueError("module entry diff requires both draft and official details")
    details.extend(
        diff_variable_details(
            "parameter",
            cast(list[dict[str, Any]], draft["parameters"]),
            cast(list[dict[str, Any]], official["parameters"]),
        )
    )
    details.extend(
        diff_variable_details(
            "variable",
            cast(list[dict[str, Any]], draft["variables"]),
            cast(list[dict[str, Any]], official["variables"]),
        )
    )
    details.extend(
        diff_submodule_details(
            cast(list[dict[str, Any]], draft["submodules"]), cast(list[dict[str, Any]], official["submodules"])
        )
    )
    details.extend(
        diff_moduledef_detail(cast(dict[str, Any], draft["moduledef"]), cast(dict[str, Any], official["moduledef"]))
    )
    modulecode_details, code_diffs = diff_modulecode_detail(
        cast(dict[str, Any], draft["modulecode"]),
        cast(dict[str, Any], official["modulecode"]),
    )
    details.extend(modulecode_details)
    if draft["module_kind"] == "moduletype":
        code_diffs.extend(
            diff_nested_inline_module_code_diffs(
                cast(dict[tuple[str, ...], dict[str, Any]], draft.get("inline_modules", {})),
                cast(dict[tuple[str, ...], dict[str, Any]], official.get("inline_modules", {})),
            )
        )
    return {
        "name": name,
        "module_kind": draft["module_kind"],
        "change_kind": change_kind,
        "details": details,
        "code_diffs": code_diffs,
    }


def build_named_entries_section(
    *,
    kind: str,
    title: str,
    label: str,
    draft_map: Mapping[Any, tuple[str, dict[str, Any]]],
    official_map: Mapping[Any, tuple[str, dict[str, Any]]],
    empty_message: str,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []

    for key in sorted(draft_map.keys() - official_map.keys(), key=str):
        display_name, detail = draft_map[key]
        entries.append(build_module_entry(display_name, change_kind="added", draft=detail, official=None))
    for key in sorted(official_map.keys() - draft_map.keys(), key=str):
        display_name, detail = official_map[key]
        entries.append(build_module_entry(display_name, change_kind="removed", draft=None, official=detail))
    for key in sorted(draft_map.keys() & official_map.keys(), key=str):
        draft_name, draft_detail = draft_map[key]
        official_name, official_detail = official_map[key]
        if draft_detail == official_detail:
            continue
        entries.append(
            build_module_entry(
                draft_name or official_name, change_kind="changed", draft=draft_detail, official=official_detail
            )
        )

    items = [f"{entry['change_kind'].capitalize()} {label} {entry['name']}" for entry in entries] or [empty_message]
    return {
        "kind": kind,
        "title": title,
        "changed": bool(entries),
        "items": items,
        "entries": entries,
    }


def build_datatype_section(draft_bp: BasePicture, official_bp: BasePicture) -> dict[str, Any]:
    draft_map = {datatype.name.casefold(): datatype for datatype in draft_bp.datatype_defs or []}
    official_map = {datatype.name.casefold(): datatype for datatype in official_bp.datatype_defs or []}
    entries: list[dict[str, Any]] = []

    for key in sorted(draft_map.keys() - official_map.keys()):
        datatype = draft_map[key]
        entries.append(
            {
                "name": datatype.name,
                "change_kind": "added",
                "details": [
                    *([] if datatype.description is None else [f"Description: {datatype.description}"]),
                    *[
                        f"Added field {format_variable_summary(detail)}"
                        for detail in variable_details(datatype.var_list)
                    ],
                ],
            }
        )
    for key in sorted(official_map.keys() - draft_map.keys()):
        datatype = official_map[key]
        entries.append(
            {
                "name": datatype.name,
                "change_kind": "removed",
                "details": [
                    f"Removed field {format_variable_summary(detail)}" for detail in variable_details(datatype.var_list)
                ],
            }
        )
    for key in sorted(draft_map.keys() & official_map.keys()):
        draft_datatype = draft_map[key]
        official_datatype = official_map[key]
        if datatype_signature(draft_datatype) == datatype_signature(official_datatype):
            continue
        details: list[str] = []
        if draft_datatype.description != official_datatype.description:
            details.append(
                f"Changed description {format_change_value(official_datatype.description)} -> {format_change_value(draft_datatype.description)}"
            )
        if draft_datatype.datecode != official_datatype.datecode:
            details.append(f"Changed datecode {official_datatype.datecode} -> {draft_datatype.datecode}")
        details.extend(
            diff_variable_details(
                "field",
                variable_details(draft_datatype.var_list),
                variable_details(official_datatype.var_list),
            )
        )
        entries.append({"name": draft_datatype.name, "change_kind": "changed", "details": details})

    items = [f"{entry['change_kind'].capitalize()} datatype {entry['name']}" for entry in entries] or [
        "No datatype changes."
    ]
    return {
        "kind": "changed-datatypes",
        "title": "Changed Datatypes",
        "changed": bool(entries),
        "items": items,
        "entries": entries,
    }


def build_basepicture_section(draft_bp: BasePicture, official_bp: BasePicture) -> dict[str, Any]:
    draft_detail = basepicture_detail(draft_bp)
    official_detail = basepicture_detail(official_bp)
    if draft_detail == official_detail:
        return {
            "kind": "basepicture",
            "title": "BasePicture",
            "changed": False,
            "items": ["No BasePicture changes."],
            "entries": [],
        }
    entry = build_module_entry("BasePicture", change_kind="changed", draft=draft_detail, official=official_detail)
    return {
        "kind": "basepicture",
        "title": "BasePicture",
        "changed": True,
        "items": ["Changed BasePicture"],
        "entries": [entry],
    }


def build_moduletype_section(
    draft_bp: BasePicture,
    official_bp: BasePicture,
    *,
    promoted_moduletype_sources: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    draft_map = {
        moduletype.name.casefold(): (moduletype.name, moduletype_detail(moduletype))
        for moduletype in draft_bp.moduletype_defs or []
    }
    official_map = {
        moduletype.name.casefold(): (moduletype.name, moduletype_detail(moduletype))
        for moduletype in official_bp.moduletype_defs or []
    }
    entries: list[dict[str, Any]] = []
    promoted_moduletype_sources = dict(promoted_moduletype_sources or {})

    for key in sorted(draft_map.keys() - official_map.keys(), key=str):
        display_name, detail = draft_map[key]
        entry = build_module_entry(display_name, change_kind="added", draft=detail, official=None)
        if key in promoted_moduletype_sources:
            entry["details"] = [f"Extracted from inline singlemodule {promoted_moduletype_sources[key]}"]
        entries.append(entry)
    for key in sorted(official_map.keys() - draft_map.keys(), key=str):
        display_name, detail = official_map[key]
        entries.append(build_module_entry(display_name, change_kind="removed", draft=None, official=detail))
    for key in sorted(draft_map.keys() & official_map.keys(), key=str):
        draft_name, draft_detail = draft_map[key]
        official_name, official_detail = official_map[key]
        if draft_detail == official_detail:
            continue
        entries.append(
            build_module_entry(
                draft_name or official_name, change_kind="changed", draft=draft_detail, official=official_detail
            )
        )

    items = [f"{entry['change_kind'].capitalize()} moduletype {entry['name']}" for entry in entries] or [
        "No moduletype changes."
    ]
    return {
        "kind": "changed-moduletypes",
        "title": "Changed Moduletypes",
        "changed": bool(entries),
        "items": items,
        "entries": entries,
    }


def build_singlemodule_section(
    draft_bp: BasePicture,
    official_bp: BasePicture,
    *,
    promotion_entries: list[dict[str, Any]] | None = None,
    promoted_roots: set[tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    draft_inline = collect_inline_module_details(draft_bp.submodules)
    official_inline = collect_inline_module_details(official_bp.submodules)
    if promotion_entries is None or promoted_roots is None:
        promotion_entries, promoted_roots, _ = collect_promoted_singlemodule_entries(
            draft_bp=draft_bp,
            official_bp=official_bp,
            official_inline=official_inline,
        )

    def is_suppressed(path: tuple[str, ...]) -> bool:
        return any(path_has_prefix(path, root) for root in promoted_roots)

    draft_map = {key: (detail["name"], detail) for key, detail in draft_inline.items() if not is_suppressed(key)}
    official_map = {key: (detail["name"], detail) for key, detail in official_inline.items() if not is_suppressed(key)}
    section = build_named_entries_section(
        kind="changed-singlemodules",
        title="Changed Singlemodules",
        label="singlemodule",
        draft_map=draft_map,
        official_map=official_map,
        empty_message="No singlemodule changes.",
    )
    if promotion_entries:
        section["entries"].extend(promotion_entries)
        section["entries"].sort(key=entry_name_sort_key)
        section["changed"] = bool(section["entries"])
        section["items"] = [
            f"{entry['change_kind'].capitalize()} singlemodule {entry['name']}" for entry in section["entries"]
        ]
    return section


def build_ast_comparison_sections(draft_bp: BasePicture, official_bp: BasePicture) -> list[dict[str, Any]]:
    draft_summary = collect_ast_summary(draft_bp)
    official_summary = collect_ast_summary(official_bp)
    ast_items = [
        format_summary_delta(summary_key, draft_summary[summary_key], official_summary[summary_key])
        for summary_key in sorted(draft_summary)
        if draft_summary[summary_key] != official_summary[summary_key]
    ]
    if moduledef_signature(draft_bp.moduledef) != moduledef_signature(official_bp.moduledef):
        ast_items.append("Changed BasePicture module definition")
    if modulecode_signature(draft_bp.modulecode) != modulecode_signature(official_bp.modulecode):
        ast_items.append("Changed BasePicture module code")
    if tuple(submodule_signature(module) for module in draft_bp.submodules or []) != tuple(
        submodule_signature(module) for module in official_bp.submodules or []
    ):
        ast_items.append("Changed BasePicture submodule tree")

    official_inline = collect_inline_module_details(official_bp.submodules)
    promotion_entries, promoted_roots, promoted_moduletype_sources = collect_promoted_singlemodule_entries(
        draft_bp=draft_bp,
        official_bp=official_bp,
        official_inline=official_inline,
    )

    return [
        {
            "kind": "ast-overview",
            "title": "AST Overview",
            "changed": bool(ast_items),
            "items": ast_items or ["No AST structure changes."],
        },
        build_basepicture_section(draft_bp, official_bp),
        build_datatype_section(draft_bp, official_bp),
        build_moduletype_section(
            draft_bp,
            official_bp,
            promoted_moduletype_sources=promoted_moduletype_sources,
        ),
        build_singlemodule_section(
            draft_bp,
            official_bp,
            promotion_entries=promotion_entries,
            promoted_roots=promoted_roots,
        ),
    ]
