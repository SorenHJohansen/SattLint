"""Review-friendly reports for draft `.s` versus official `.x` source pairs."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from lark.exceptions import LarkError

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.api import read_text_with_fallback
from sattline_parser.grammar.parser_decode import is_compressed, preprocess_sl_text
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    FrameModule,
    ModuleCode,
    ModuleDef,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    Variable,
)
from sattline_parser.utils.formatter import format_expr, format_seq_nodes
from sattlint import cli_output
from sattlint.devtools._diff_rendering import (
    build_unified_diff_lines,
    normalize_layout_text,
    summarize_unified_diff_lines,
)
from sattlint.devtools._io import emit_progress, sanitize_repo_path
from sattlint.repo_paths import repo_root_from
from sattlint.tracing import collect_ast_summary
from sattlint.validation import validate_transformed_basepicture

REPO_ROOT = repo_root_from(Path(__file__))
DEFAULT_JSON_OUTPUT_FILENAME = "source_diff_report.json"
DEFAULT_MARKDOWN_OUTPUT_FILENAME = "source_diff_report.md"


_emit_progress = emit_progress


_source_diff_repo_path = sanitize_repo_path


def _pair_name(draft_file: Path, official_file: Path) -> str:
    if draft_file.stem.casefold() == official_file.stem.casefold():
        return draft_file.stem
    return f"{draft_file.stem} vs {official_file.stem}"


def _read_source_text(path: Path) -> str:
    source_text = read_text_with_fallback(path)
    if is_compressed(source_text):
        source_text, _ = preprocess_sl_text(source_text)
    return source_text


def _stable_signature_text(value: object) -> str:
    return re.sub(r"SourceSpan\([^)]*\)", "SourceSpan()", repr(value))


def _stable_signature_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, tuple):
        tuple_value = cast(tuple[object, ...], value)
        return tuple(_stable_signature_value(item) for item in tuple_value)
    if isinstance(value, list):
        list_value = cast(list[object], value)
        return tuple(_stable_signature_value(item) for item in list_value)
    if isinstance(value, Mapping):
        mapping_value = cast(Mapping[object, object], value)
        return tuple(sorted((str(key), _stable_signature_value(item)) for key, item in mapping_value.items()))
    return _stable_signature_text(value)


def _variable_signature(variable: Variable) -> tuple[object, ...]:
    return (
        variable.datatype_text,
        bool(variable.global_var),
        bool(variable.const),
        bool(variable.state),
        bool(variable.opsave),
        bool(variable.secure),
        _stable_signature_value(variable.init_value),
        variable.description or "",
        variable.init_is_duration,
    )


def _datatype_signature(datatype: DataType) -> tuple[object, ...]:
    return (
        datatype.description or "",
        datatype.datecode,
        tuple((variable.name.casefold(), _variable_signature(variable)) for variable in datatype.var_list or []),
    )


def _module_header_signature(header: object | None) -> tuple[object, ...] | None:
    if header is None:
        return None
    return (
        getattr(header, "name", ""),
        _stable_signature_value(getattr(header, "invoke_coord", None)),
        _stable_signature_value(getattr(header, "invocation_arguments", ())),
        _stable_signature_value(getattr(header, "layer_info", None)),
        bool(getattr(header, "enable", True)),
        _stable_signature_value(getattr(header, "zoom_limits", None)),
        bool(getattr(header, "zoomable", False)),
        _stable_signature_value(getattr(header, "enable_tail", None)),
    )


def _moduledef_signature(moduledef: ModuleDef | None) -> tuple[object, ...] | None:
    if moduledef is None:
        return None
    return (
        moduledef.clipping_bounds,
        moduledef.zoom_limits,
        moduledef.seq_layers,
        moduledef.grid,
        moduledef.zoomable,
        tuple(_stable_signature_text(graph_object) for graph_object in moduledef.graph_objects or []),
        tuple(_stable_signature_text(interact_object) for interact_object in moduledef.interact_objects or []),
        tuple(sorted((str(key), _stable_signature_text(value)) for key, value in (moduledef.properties or {}).items())),
    )


def _modulecode_signature(modulecode: ModuleCode | None) -> tuple[object, ...] | None:
    if modulecode is None:
        return None
    return (
        tuple(
            (
                sequence.name.casefold(),
                sequence.type.casefold(),
                sequence.position,
                sequence.size,
                bool(sequence.seqcontrol),
                bool(sequence.seqtimer),
                tuple(_stable_signature_text(code) for code in sequence.code or []),
            )
            for sequence in modulecode.sequences or []
        ),
        tuple(
            (
                equation.name.casefold(),
                equation.position,
                equation.size,
                tuple(_stable_signature_text(code) for code in equation.code or []),
            )
            for equation in modulecode.equations or []
        ),
    )


def _submodule_signature(module: SingleModule | FrameModule | ModuleTypeInstance) -> tuple[object, ...]:
    header_signature = _module_header_signature(module.header)
    if isinstance(module, SingleModule):
        return (
            "single-module",
            header_signature,
            module.datecode,
            tuple(
                (variable.name.casefold(), _variable_signature(variable)) for variable in module.moduleparameters or []
            ),
            tuple(
                (variable.name.casefold(), _variable_signature(variable)) for variable in module.localvariables or []
            ),
            tuple(_submodule_signature(child) for child in module.submodules or []),
            _moduledef_signature(module.moduledef),
            _modulecode_signature(module.modulecode),
            tuple(str(mapping) for mapping in module.parametermappings or []),
        )
    if isinstance(module, FrameModule):
        return (
            "frame-module",
            header_signature,
            module.datecode,
            tuple(_submodule_signature(child) for child in module.submodules or []),
            _moduledef_signature(module.moduledef),
            _modulecode_signature(module.modulecode),
        )
    return (
        "moduletype-instance",
        header_signature,
        module.moduletype_name.casefold(),
        tuple(str(mapping) for mapping in module.parametermappings or []),
    )


def _format_summary_delta(summary_key: str, draft_value: int, official_value: int) -> str:
    label = summary_key.replace("_", " ")
    return f"{label}: {official_value} -> {draft_value}"


def _format_change_value(value: object) -> str:
    return "<none>" if value in {None, ""} else str(value)


def _variable_detail(variable: Variable) -> dict[str, Any]:
    qualifiers = tuple(
        flag
        for flag, enabled in (
            ("global", variable.global_var),
            ("const", variable.const),
            ("state", variable.state),
            ("opsave", variable.opsave),
            ("secure", variable.secure),
        )
        if enabled
    )
    return {
        "name": variable.name,
        "datatype": variable.datatype_text,
        "qualifiers": qualifiers,
        "init_value": repr(variable.init_value),
        "description": variable.description or "",
        "init_is_duration": variable.init_is_duration,
    }


def _variable_details(variables: Sequence[Variable] | None) -> list[dict[str, Any]]:
    return [_variable_detail(variable) for variable in variables or []]


def _format_variable_summary(detail: dict[str, Any]) -> str:
    return f"{detail['name']} [{detail['datatype']}]"


def _format_qualifiers(detail: dict[str, Any]) -> str:
    qualifiers = cast(tuple[str, ...], detail["qualifiers"])
    return ", ".join(qualifiers) if qualifiers else "none"


def _diff_variable_details(label: str, draft: list[dict[str, Any]], official: list[dict[str, Any]]) -> list[str]:
    draft_map = {detail["name"].casefold(): detail for detail in draft}
    official_map = {detail["name"].casefold(): detail for detail in official}
    details: list[str] = []

    for key in sorted(draft_map.keys() - official_map.keys()):
        details.append(f"Added {label} {_format_variable_summary(draft_map[key])}")
    for key in sorted(official_map.keys() - draft_map.keys()):
        details.append(f"Removed {label} {_format_variable_summary(official_map[key])}")
    for key in sorted(draft_map.keys() & official_map.keys()):
        draft_detail = draft_map[key]
        official_detail = official_map[key]
        if draft_detail == official_detail:
            continue
        fragments: list[str] = []
        if draft_detail["datatype"] != official_detail["datatype"]:
            fragments.append(
                f"datatype {_format_change_value(official_detail['datatype'])} -> {_format_change_value(draft_detail['datatype'])}"
            )
        if draft_detail["qualifiers"] != official_detail["qualifiers"]:
            fragments.append(f"qualifiers {_format_qualifiers(official_detail)} -> {_format_qualifiers(draft_detail)}")
        if draft_detail["init_value"] != official_detail["init_value"]:
            fragments.append(
                f"init {_format_change_value(official_detail['init_value'])} -> {_format_change_value(draft_detail['init_value'])}"
            )
        if draft_detail["description"] != official_detail["description"]:
            fragments.append(
                f"description {_format_change_value(official_detail['description'])} -> {_format_change_value(draft_detail['description'])}"
            )
        if draft_detail["init_is_duration"] != official_detail["init_is_duration"]:
            fragments.append(
                "init_is_duration "
                f"{_format_change_value(official_detail['init_is_duration'])} -> {_format_change_value(draft_detail['init_is_duration'])}"
            )
        details.append(f"Changed {label} {draft_detail['name']} ({'; '.join(fragments)})")

    return details


def _submodule_kind(module: SingleModule | FrameModule | ModuleTypeInstance) -> str:
    if isinstance(module, SingleModule):
        return "singlemodule"
    if isinstance(module, FrameModule):
        return "framemodule"
    return "moduletype-instance"


def _submodule_detail(module: SingleModule | FrameModule | ModuleTypeInstance) -> dict[str, Any]:
    detail = {
        "name": module.header.name,
        "kind": _submodule_kind(module),
        "parameter_mappings": tuple(str(mapping) for mapping in getattr(module, "parametermappings", ()) or ()),
        "signature": _submodule_signature(module),
    }
    if isinstance(module, ModuleTypeInstance):
        detail["moduletype_name"] = module.moduletype_name
    return detail


def _submodule_details(
    modules: Sequence[SingleModule | FrameModule | ModuleTypeInstance] | None,
) -> list[dict[str, Any]]:
    return [_submodule_detail(module) for module in modules or []]


def _format_submodule_summary(detail: dict[str, Any]) -> str:
    if detail["kind"] == "moduletype-instance":
        return f"{detail['name']} [instance:{detail['moduletype_name']}]"
    return f"{detail['name']} [{detail['kind']}]"


def _diff_submodule_details(draft: list[dict[str, Any]], official: list[dict[str, Any]]) -> list[str]:
    draft_map = {detail["name"].casefold(): detail for detail in draft}
    official_map = {detail["name"].casefold(): detail for detail in official}
    details: list[str] = []

    for key in sorted(draft_map.keys() - official_map.keys()):
        details.append(f"Added submodule {_format_submodule_summary(draft_map[key])}")
    for key in sorted(official_map.keys() - draft_map.keys()):
        details.append(f"Removed submodule {_format_submodule_summary(official_map[key])}")
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
                f"{_format_change_value(official_detail.get('moduletype_name'))} -> {_format_change_value(draft_detail.get('moduletype_name'))}"
            )
        if draft_detail["parameter_mappings"] != official_detail["parameter_mappings"]:
            fragments.append("parameter mappings changed")
        if (draft_detail["signature"] != official_detail["signature"] and not fragments) or (
            draft_detail["signature"] != official_detail["signature"] and "definition changed" not in fragments
        ):
            fragments.append("definition changed")
        details.append(f"Changed submodule {draft_detail['name']} ({'; '.join(fragments)})")

    return details


def _modulecode_entity_code_lines(entity: dict[str, Any]) -> list[str]:
    return list(cast(tuple[str, ...], entity["code_lines"]))


def _build_inline_diff_lines(*, label: str, name: str, draft_lines: list[str], official_lines: list[str]) -> list[str]:
    return list(
        difflib.unified_diff(
            official_lines,
            draft_lines,
            fromfile=f"previous {label} {name}",
            tofile=f"draft {label} {name}",
            lineterm="",
        )
    )


def _render_modulecode_entity_lines(entity: Any) -> tuple[str, ...]:
    raw_code = cast(Sequence[object] | None, getattr(entity, "code", None)) or ()
    if hasattr(entity, "type"):
        return tuple(format_seq_nodes(list(raw_code)).splitlines())

    rendered_lines: list[str] = []
    for statement in raw_code:
        rendered_lines.extend(format_expr(statement).splitlines())
    return tuple(rendered_lines)


def _modulecode_entity_detail(entity: Any) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "name": entity.name,
        "position": entity.position,
        "size": entity.size,
        "code_lines": _render_modulecode_entity_lines(entity),
    }
    if hasattr(entity, "type"):
        detail["type"] = entity.type
        detail["seqcontrol"] = bool(getattr(entity, "seqcontrol", False))
        detail["seqtimer"] = bool(getattr(entity, "seqtimer", False))
    return detail


def _modulecode_detail(modulecode: ModuleCode | None) -> dict[str, Any]:
    if modulecode is None:
        return {"sequences": {}, "equations": {}}
    return {
        "sequences": {
            detail["name"].casefold(): detail
            for detail in (_modulecode_entity_detail(sequence) for sequence in modulecode.sequences or [])
        },
        "equations": {
            detail["name"].casefold(): detail
            for detail in (_modulecode_entity_detail(equation) for equation in modulecode.equations or [])
        },
    }


def _diff_modulecode_entities(
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
                    f"{field_name} {_format_change_value(official_detail.get(field_name))} -> {_format_change_value(draft_detail.get(field_name))}"
                )
        if draft_detail["code_lines"] != official_detail["code_lines"]:
            fragments.append("code changed")
            code_diffs.append(
                {
                    "label": f"{label.title()} {draft_detail['name']}",
                    "diff_lines": _build_inline_diff_lines(
                        label=label,
                        name=draft_detail["name"],
                        draft_lines=_modulecode_entity_code_lines(draft_detail),
                        official_lines=_modulecode_entity_code_lines(official_detail),
                    ),
                }
            )
        details.append(f"Changed {label} {draft_detail['name']} ({'; '.join(fragments)})")

    return details, code_diffs


def _diff_modulecode_detail(draft: dict[str, Any], official: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    sequence_details, sequence_diffs = _diff_modulecode_entities(
        "sequence",
        cast(dict[str, dict[str, Any]], draft["sequences"]),
        cast(dict[str, dict[str, Any]], official["sequences"]),
    )
    equation_details, equation_diffs = _diff_modulecode_entities(
        "equation",
        cast(dict[str, dict[str, Any]], draft["equations"]),
        cast(dict[str, dict[str, Any]], official["equations"]),
    )
    return sequence_details + equation_details, sequence_diffs + equation_diffs


def _diff_nested_inline_module_code_diffs(
    draft: Mapping[tuple[str, ...], dict[str, Any]],
    official: Mapping[tuple[str, ...], dict[str, Any]],
) -> list[dict[str, Any]]:
    code_diffs: list[dict[str, Any]] = []

    for key in sorted(draft.keys() & official.keys()):
        draft_detail = draft[key]
        official_detail = official[key]
        _, nested_code_diffs = _diff_modulecode_detail(
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


def _moduledef_detail(moduledef: ModuleDef | None) -> dict[str, Any]:
    if moduledef is None:
        return {
            "clipping_bounds": None,
            "zoom_limits": None,
            "seq_layers": None,
            "grid": None,
            "zoomable": None,
            "graph_object_count": 0,
            "interact_object_count": 0,
            "properties": (),
        }
    return {
        "clipping_bounds": moduledef.clipping_bounds,
        "zoom_limits": moduledef.zoom_limits,
        "seq_layers": moduledef.seq_layers,
        "grid": moduledef.grid,
        "zoomable": moduledef.zoomable,
        "graph_object_count": len(moduledef.graph_objects or []),
        "interact_object_count": len(moduledef.interact_objects or []),
        "properties": tuple(
            sorted((str(key), _stable_signature_text(value)) for key, value in (moduledef.properties or {}).items())
        ),
    }


def _diff_moduledef_detail(draft: dict[str, Any], official: dict[str, Any]) -> list[str]:
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
                f"Changed moduledef {field_name} ({_format_change_value(official[field_name])} -> {_format_change_value(draft[field_name])})"
            )
    return details


def _basepicture_detail(base_picture: BasePicture) -> dict[str, Any]:
    return {
        "name": "BasePicture",
        "module_kind": "basepicture",
        "parameters": [],
        "variables": _variable_details(base_picture.localvariables),
        "submodules": _submodule_details(base_picture.submodules),
        "moduledef": _moduledef_detail(base_picture.moduledef),
        "modulecode": _modulecode_detail(base_picture.modulecode),
    }


def _moduletype_detail(moduletype: ModuleTypeDef) -> dict[str, Any]:
    return {
        "name": moduletype.name,
        "module_kind": "moduletype",
        "parameters": _variable_details(moduletype.moduleparameters),
        "variables": _variable_details(moduletype.localvariables),
        "submodules": _submodule_details(moduletype.submodules),
        "moduledef": _moduledef_detail(moduletype.moduledef),
        "modulecode": _modulecode_detail(moduletype.modulecode),
        "inline_modules": _collect_inline_module_details(moduletype.submodules),
    }


def _inline_module_detail(
    path: tuple[str, ...],
    module: SingleModule | FrameModule,
    *,
    inline_modules: Mapping[tuple[str, ...], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "name": " > ".join(path),
        "module_kind": _submodule_kind(module),
        "parameters": _variable_details(getattr(module, "moduleparameters", []) or []),
        "variables": _variable_details(getattr(module, "localvariables", []) or []),
        "submodules": _submodule_details(module.submodules),
        "moduledef": _moduledef_detail(module.moduledef),
        "modulecode": _modulecode_detail(module.modulecode),
        "inline_modules": dict(inline_modules or {}),
    }


def _collect_inline_module_details(
    modules: Sequence[SingleModule | FrameModule | ModuleTypeInstance] | None,
    *,
    parent_path: tuple[str, ...] = (),
) -> dict[tuple[str, ...], dict[str, Any]]:
    collected: dict[tuple[str, ...], dict[str, Any]] = {}
    for index, module in enumerate(modules or [], start=1):
        if isinstance(module, ModuleTypeInstance):
            continue
        module_name = module.header.name or f"<unnamed-{index}>"
        path = (*parent_path, module_name)
        key = tuple(segment.casefold() for segment in path)
        child_collected = _collect_inline_module_details(module.submodules, parent_path=path)
        collected[key] = _inline_module_detail(
            path,
            module,
            inline_modules={
                child_key[len(key) :]: child_detail
                for child_key, child_detail in child_collected.items()
                if _path_has_prefix(child_key, key)
            },
        )
        collected.update(child_collected)
    return collected


def _collect_moduletype_instance_details(
    modules: Sequence[SingleModule | FrameModule | ModuleTypeInstance] | None,
    *,
    parent_path: tuple[str, ...] = (),
) -> dict[tuple[str, ...], dict[str, Any]]:
    collected: dict[tuple[str, ...], dict[str, Any]] = {}
    for index, module in enumerate(modules or [], start=1):
        module_name = module.header.name or f"<unnamed-{index}>"
        path = (*parent_path, module_name)
        key = tuple(segment.casefold() for segment in path)
        if isinstance(module, ModuleTypeInstance):
            collected[key] = {
                "name": " > ".join(path),
                "moduletype_name": module.moduletype_name,
                "parameter_mappings": tuple(str(mapping) for mapping in module.parametermappings or ()),
            }
            continue
        collected.update(_collect_moduletype_instance_details(module.submodules, parent_path=path))
    return collected


def _path_has_prefix(path: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    return len(path) >= len(prefix) and path[: len(prefix)] == prefix


def _module_content_signature(detail: Mapping[str, Any]) -> tuple[object, ...]:
    return (
        tuple(tuple(sorted(item.items())) for item in cast(list[dict[str, Any]], detail["parameters"])),
        tuple(tuple(sorted(item.items())) for item in cast(list[dict[str, Any]], detail["variables"])),
        tuple(tuple(sorted(item.items())) for item in cast(list[dict[str, Any]], detail["submodules"])),
        tuple(sorted(cast(dict[str, Any], detail["moduledef"]).items())),
        (
            tuple(
                sorted(cast(dict[str, dict[str, Any]], cast(dict[str, Any], detail["modulecode"])["sequences"]).items())
            ),
            tuple(
                sorted(cast(dict[str, dict[str, Any]], cast(dict[str, Any], detail["modulecode"])["equations"]).items())
            ),
        ),
    )


def _leaf_module_name(display_name: str) -> str:
    return display_name.rsplit(" > ", 1)[-1]


def _is_promoted_moduletype_name(singlemodule_display_name: str, moduletype_name: str) -> bool:
    singlemodule_leaf = _leaf_module_name(singlemodule_display_name).casefold()
    moduletype_key = moduletype_name.casefold()
    return moduletype_key in {singlemodule_leaf, f"{singlemodule_leaf}type"}


def _entry_name_sort_key(entry: dict[str, Any]) -> str:
    return cast(str, entry["name"]).casefold()


def _collect_promoted_singlemodule_entries(
    *,
    draft_bp: BasePicture,
    official_bp: BasePicture,
    official_inline: Mapping[tuple[str, ...], dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[tuple[str, ...]], dict[str, str]]:
    draft_instances = _collect_moduletype_instance_details(draft_bp.submodules)
    added_moduletype_details = {
        moduletype.name.casefold(): _moduletype_detail(moduletype)
        for moduletype in draft_bp.moduletype_defs or []
        if moduletype.name.casefold()
        not in {existing.name.casefold() for existing in official_bp.moduletype_defs or []}
    }
    added_moduletype_signatures = {
        name: _module_content_signature(detail) for name, detail in added_moduletype_details.items()
    }

    entries: list[dict[str, Any]] = []
    promoted_roots: set[tuple[str, ...]] = set()
    promoted_moduletype_sources: dict[str, str] = {}
    for key in sorted(official_inline, key=len):
        if any(_path_has_prefix(key, root) for root in promoted_roots):
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
            official_signature = _module_content_signature(official_detail)
            matching_added_moduletype_names = [
                cast(str, detail["name"])
                for name, detail in added_moduletype_details.items()
                if added_moduletype_signatures[name] == official_signature
                and _is_promoted_moduletype_name(cast(str, official_detail["name"]), cast(str, detail["name"]))
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


def _full_module_details(detail: dict[str, Any]) -> list[str]:
    details: list[str] = []
    for variable_detail in cast(list[dict[str, Any]], detail["parameters"]):
        details.append(f"Added parameter {_format_variable_summary(variable_detail)}")
    for variable_detail in cast(list[dict[str, Any]], detail["variables"]):
        details.append(f"Added variable {_format_variable_summary(variable_detail)}")
    for submodule_detail in cast(list[dict[str, Any]], detail["submodules"]):
        details.append(f"Added submodule {_format_submodule_summary(submodule_detail)}")
    moduledef_details = _diff_moduledef_detail(
        cast(dict[str, Any], detail["moduledef"]),
        _moduledef_detail(None),
    )
    details.extend(detail_text.replace("Changed moduledef ", "Added moduledef ") for detail_text in moduledef_details)
    modulecode_details, _ = _diff_modulecode_detail(
        cast(dict[str, Any], detail["modulecode"]),
        _modulecode_detail(None),
    )
    details.extend(detail_text.replace("Changed ", "Added ") for detail_text in modulecode_details)
    return details


def _build_module_entry(
    name: str,
    *,
    change_kind: str,
    draft: dict[str, Any] | None,
    official: dict[str, Any] | None,
) -> dict[str, Any]:
    details: list[str] = []
    code_diffs: list[dict[str, Any]] = []

    if draft is not None and official is None:
        details = _full_module_details(draft)
        return {
            "name": name,
            "module_kind": draft["module_kind"],
            "change_kind": change_kind,
            "details": details,
            "code_diffs": code_diffs,
        }
    if draft is None and official is not None:
        details = [detail.replace("Added ", "Removed ") for detail in _full_module_details(official)]
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
        _diff_variable_details(
            "parameter",
            cast(list[dict[str, Any]], draft["parameters"]),
            cast(list[dict[str, Any]], official["parameters"]),
        )
    )
    details.extend(
        _diff_variable_details(
            "variable",
            cast(list[dict[str, Any]], draft["variables"]),
            cast(list[dict[str, Any]], official["variables"]),
        )
    )
    details.extend(
        _diff_submodule_details(
            cast(list[dict[str, Any]], draft["submodules"]), cast(list[dict[str, Any]], official["submodules"])
        )
    )
    details.extend(
        _diff_moduledef_detail(cast(dict[str, Any], draft["moduledef"]), cast(dict[str, Any], official["moduledef"]))
    )
    modulecode_details, code_diffs = _diff_modulecode_detail(
        cast(dict[str, Any], draft["modulecode"]),
        cast(dict[str, Any], official["modulecode"]),
    )
    details.extend(modulecode_details)
    if draft["module_kind"] == "moduletype":
        code_diffs.extend(
            _diff_nested_inline_module_code_diffs(
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


def _build_named_entries_section[EntryKeyT](
    *,
    kind: str,
    title: str,
    label: str,
    draft_map: Mapping[EntryKeyT, tuple[str, dict[str, Any]]],
    official_map: Mapping[EntryKeyT, tuple[str, dict[str, Any]]],
    empty_message: str,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []

    for key in sorted(draft_map.keys() - official_map.keys(), key=str):
        display_name, detail = draft_map[key]
        entries.append(_build_module_entry(display_name, change_kind="added", draft=detail, official=None))
    for key in sorted(official_map.keys() - draft_map.keys(), key=str):
        display_name, detail = official_map[key]
        entries.append(_build_module_entry(display_name, change_kind="removed", draft=None, official=detail))
    for key in sorted(draft_map.keys() & official_map.keys(), key=str):
        draft_name, draft_detail = draft_map[key]
        official_name, official_detail = official_map[key]
        if draft_detail == official_detail:
            continue
        entries.append(
            _build_module_entry(
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


def _build_datatype_section(draft_bp: BasePicture, official_bp: BasePicture) -> dict[str, Any]:
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
                        f"Added field {_format_variable_summary(detail)}"
                        for detail in _variable_details(datatype.var_list)
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
                    f"Removed field {_format_variable_summary(detail)}"
                    for detail in _variable_details(datatype.var_list)
                ],
            }
        )
    for key in sorted(draft_map.keys() & official_map.keys()):
        draft_datatype = draft_map[key]
        official_datatype = official_map[key]
        if _datatype_signature(draft_datatype) == _datatype_signature(official_datatype):
            continue
        details: list[str] = []
        if draft_datatype.description != official_datatype.description:
            details.append(
                f"Changed description {_format_change_value(official_datatype.description)} -> {_format_change_value(draft_datatype.description)}"
            )
        if draft_datatype.datecode != official_datatype.datecode:
            details.append(f"Changed datecode {official_datatype.datecode} -> {draft_datatype.datecode}")
        details.extend(
            _diff_variable_details(
                "field",
                _variable_details(draft_datatype.var_list),
                _variable_details(official_datatype.var_list),
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


def _build_basepicture_section(draft_bp: BasePicture, official_bp: BasePicture) -> dict[str, Any]:
    draft_detail = _basepicture_detail(draft_bp)
    official_detail = _basepicture_detail(official_bp)
    if draft_detail == official_detail:
        return {
            "kind": "basepicture",
            "title": "BasePicture",
            "changed": False,
            "items": ["No BasePicture changes."],
            "entries": [],
        }
    entry = _build_module_entry("BasePicture", change_kind="changed", draft=draft_detail, official=official_detail)
    return {
        "kind": "basepicture",
        "title": "BasePicture",
        "changed": True,
        "items": ["Changed BasePicture"],
        "entries": [entry],
    }


def _build_moduletype_section(
    draft_bp: BasePicture,
    official_bp: BasePicture,
    *,
    promoted_moduletype_sources: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    draft_map = {
        moduletype.name.casefold(): (moduletype.name, _moduletype_detail(moduletype))
        for moduletype in draft_bp.moduletype_defs or []
    }
    official_map = {
        moduletype.name.casefold(): (moduletype.name, _moduletype_detail(moduletype))
        for moduletype in official_bp.moduletype_defs or []
    }
    entries: list[dict[str, Any]] = []
    promoted_moduletype_sources = dict(promoted_moduletype_sources or {})

    for key in sorted(draft_map.keys() - official_map.keys(), key=str):
        display_name, detail = draft_map[key]
        entry = _build_module_entry(display_name, change_kind="added", draft=detail, official=None)
        if key in promoted_moduletype_sources:
            entry["details"] = [f"Extracted from inline singlemodule {promoted_moduletype_sources[key]}"]
        entries.append(entry)
    for key in sorted(official_map.keys() - draft_map.keys(), key=str):
        display_name, detail = official_map[key]
        entries.append(_build_module_entry(display_name, change_kind="removed", draft=None, official=detail))
    for key in sorted(draft_map.keys() & official_map.keys(), key=str):
        draft_name, draft_detail = draft_map[key]
        official_name, official_detail = official_map[key]
        if draft_detail == official_detail:
            continue
        entries.append(
            _build_module_entry(
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


def _build_singlemodule_section(
    draft_bp: BasePicture,
    official_bp: BasePicture,
    *,
    promotion_entries: list[dict[str, Any]] | None = None,
    promoted_roots: set[tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    draft_inline = _collect_inline_module_details(draft_bp.submodules)
    official_inline = _collect_inline_module_details(official_bp.submodules)
    if promotion_entries is None or promoted_roots is None:
        promotion_entries, promoted_roots, _ = _collect_promoted_singlemodule_entries(
            draft_bp=draft_bp,
            official_bp=official_bp,
            official_inline=official_inline,
        )

    def _is_suppressed(path: tuple[str, ...]) -> bool:
        return any(_path_has_prefix(path, root) for root in promoted_roots)

    draft_map = {key: (detail["name"], detail) for key, detail in draft_inline.items() if not _is_suppressed(key)}
    official_map = {key: (detail["name"], detail) for key, detail in official_inline.items() if not _is_suppressed(key)}
    section = _build_named_entries_section(
        kind="changed-singlemodules",
        title="Changed Singlemodules",
        label="singlemodule",
        draft_map=draft_map,
        official_map=official_map,
        empty_message="No singlemodule changes.",
    )
    if promotion_entries:
        section["entries"].extend(promotion_entries)
        section["entries"].sort(key=_entry_name_sort_key)
        section["changed"] = bool(section["entries"])
        section["items"] = [
            f"{entry['change_kind'].capitalize()} singlemodule {entry['name']}" for entry in section["entries"]
        ]
    return section


def _build_ast_comparison_sections(draft_bp: BasePicture, official_bp: BasePicture) -> list[dict[str, Any]]:
    draft_summary = collect_ast_summary(draft_bp)
    official_summary = collect_ast_summary(official_bp)
    ast_items = [
        _format_summary_delta(summary_key, draft_summary[summary_key], official_summary[summary_key])
        for summary_key in sorted(draft_summary)
        if draft_summary[summary_key] != official_summary[summary_key]
    ]
    if _moduledef_signature(draft_bp.moduledef) != _moduledef_signature(official_bp.moduledef):
        ast_items.append("Changed BasePicture module definition")
    if _modulecode_signature(draft_bp.modulecode) != _modulecode_signature(official_bp.modulecode):
        ast_items.append("Changed BasePicture module code")
    if tuple(_submodule_signature(module) for module in draft_bp.submodules or []) != tuple(
        _submodule_signature(module) for module in official_bp.submodules or []
    ):
        ast_items.append("Changed BasePicture submodule tree")

    official_inline = _collect_inline_module_details(official_bp.submodules)
    promotion_entries, promoted_roots, promoted_moduletype_sources = _collect_promoted_singlemodule_entries(
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
        _build_basepicture_section(draft_bp, official_bp),
        _build_datatype_section(draft_bp, official_bp),
        _build_moduletype_section(
            draft_bp,
            official_bp,
            promoted_moduletype_sources=promoted_moduletype_sources,
        ),
        _build_singlemodule_section(
            draft_bp,
            official_bp,
            promotion_entries=promotion_entries,
            promoted_roots=promoted_roots,
        ),
    ]


def _parse_side_for_report(
    source_text: str | None,
    *,
    source_path: Path,
    side: str,
) -> tuple[BasePicture | None, bool, bool, list[dict[str, str]]]:
    if source_text is None:
        return None, False, False, []

    errors: list[dict[str, str]] = []
    try:
        base_picture = parser_core_parse_source_text(
            source_text,
            source_path=source_path,
            log_failures=False,
        )
    except (LarkError, RuntimeError, ValueError) as exc:
        errors.append(
            {
                "side": side,
                "phase": "parse",
                "error": str(exc),
                "error_type": type(exc).__name__,
            }
        )
        return None, False, False, errors

    validation_ok = True
    try:
        validate_transformed_basepicture(base_picture)
    except (RuntimeError, ValueError) as exc:
        validation_ok = False
        errors.append(
            {
                "side": side,
                "phase": "validation",
                "error": str(exc),
                "error_type": type(exc).__name__,
            }
        )

    return base_picture, True, validation_ok, errors


def _discover_pairs(workspace_root: Path) -> list[tuple[Path, Path]]:
    indexed: dict[str, dict[str, Path]] = {}
    for path in workspace_root.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.casefold()
        if suffix not in {".s", ".x"}:
            continue
        relative = path.relative_to(workspace_root)
        key = (relative.parent / relative.stem).as_posix().casefold()
        indexed.setdefault(key, {})[suffix] = path.resolve()

    pairs: list[tuple[Path, Path]] = []
    for pair in indexed.values():
        draft_file = pair.get(".s")
        official_file = pair.get(".x")
        if draft_file is None or official_file is None:
            continue
        pairs.append((draft_file, official_file))
    return sorted(pairs, key=lambda item: (_pair_name(item[0], item[1]).casefold(), str(item[0]).casefold()))


def _resolve_explicit_pair(
    *,
    workspace_root: Path,
    draft_file: str | None,
    official_file: str | None,
) -> tuple[list[tuple[Path, Path]], list[dict[str, str]]]:
    if not draft_file and not official_file:
        return [], []
    if not draft_file or not official_file:
        return [], [
            {
                "draft_file": draft_file or "",
                "official_file": official_file or "",
                "message": "Explicit pair mode requires both --draft-file and --official-file.",
            }
        ]

    resolved_draft = (
        (workspace_root / draft_file).resolve() if not Path(draft_file).is_absolute() else Path(draft_file).resolve()
    )
    resolved_official = (
        (workspace_root / official_file).resolve()
        if not Path(official_file).is_absolute()
        else Path(official_file).resolve()
    )
    errors: list[dict[str, str]] = []
    if not resolved_draft.is_file() or not resolved_official.is_file():
        errors.append(
            {
                "draft_file": _source_diff_repo_path(resolved_draft, workspace_root=workspace_root),
                "official_file": _source_diff_repo_path(resolved_official, workspace_root=workspace_root),
                "message": "Draft or official source file does not exist.",
            }
        )
        return [], errors
    return [(resolved_draft, resolved_official)], []


def build_pair_report(
    draft_file: Path,
    official_file: Path,
    *,
    workspace_root: Path,
) -> dict[str, Any]:
    resolved_workspace_root = workspace_root.resolve()
    resolved_draft = draft_file.resolve()
    resolved_official = official_file.resolve()
    sanitized_draft = _source_diff_repo_path(resolved_draft, workspace_root=resolved_workspace_root)
    sanitized_official = _source_diff_repo_path(resolved_official, workspace_root=resolved_workspace_root)

    errors: list[dict[str, str]] = []
    draft_text: str | None = None
    official_text: str | None = None
    draft_bp: BasePicture | None = None
    official_bp: BasePicture | None = None

    try:
        draft_text = _read_source_text(resolved_draft)
    except (OSError, UnicodeError) as exc:
        errors.append({"side": "draft", "error": str(exc), "error_type": type(exc).__name__})
    try:
        official_text = _read_source_text(resolved_official)
    except (OSError, UnicodeError) as exc:
        errors.append({"side": "official", "error": str(exc), "error_type": type(exc).__name__})

    draft_bp, draft_parse_ok, draft_validation_ok, draft_errors = _parse_side_for_report(
        draft_text,
        source_path=resolved_draft,
        side="draft",
    )
    official_bp, official_parse_ok, official_validation_ok, official_errors = _parse_side_for_report(
        official_text,
        source_path=resolved_official,
        side="official",
    )
    errors.extend(draft_errors)
    errors.extend(official_errors)

    diff_lines: list[str] = []
    summary = {"addition_count": 0, "deletion_count": 0, "changed_line_count": 0}
    if draft_text is not None and official_text is not None:
        diff_lines = build_unified_diff_lines(
            resolved_official,
            workspace_root=resolved_workspace_root,
            original=official_text,
            transformed=draft_text,
            to_file=sanitized_draft,
        )
        summary = summarize_unified_diff_lines(diff_lines)

    sections: list[dict[str, Any]] = []
    if draft_bp is not None and official_bp is not None:
        sections = _build_ast_comparison_sections(draft_bp, official_bp)

    classification = "error"
    if draft_bp is not None and official_bp is not None and draft_text is not None and official_text is not None:
        if draft_text == official_text:
            classification = "identical"
        elif normalize_layout_text(draft_text) == normalize_layout_text(official_text):
            classification = "layout-only"
        else:
            classification = "structural"

    status = "error"
    if classification != "error":
        status = "ok" if not errors else "partial"

    return {
        "pair_name": _pair_name(resolved_draft, resolved_official),
        "draft_file": sanitized_draft,
        "official_file": sanitized_official,
        "status": status,
        "classification": classification,
        "changed": summary["changed_line_count"] > 0,
        "parse_checks": {
            "draft_parse_ok": draft_parse_ok,
            "official_parse_ok": official_parse_ok,
        },
        "validation_checks": {
            "draft_validation_ok": draft_validation_ok,
            "official_validation_ok": official_validation_ok,
        },
        "summary": summary,
        "sections": sections,
        "errors": errors,
    }


def build_source_diff_report(
    workspace_root: Path = REPO_ROOT,
    *,
    draft_file: str | None = None,
    official_file: str | None = None,
    discover_pairs: bool = False,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    resolved_workspace_root = workspace_root.resolve()
    if progress_callback is not None:
        progress_callback("Source diff: resolving comparison pairs")

    pairs, selection_errors = _resolve_explicit_pair(
        workspace_root=resolved_workspace_root,
        draft_file=draft_file,
        official_file=official_file,
    )
    if not pairs and not selection_errors and discover_pairs:
        pairs = _discover_pairs(resolved_workspace_root)
        if not pairs:
            selection_errors.append(
                {
                    "draft_file": "",
                    "official_file": "",
                    "message": "No same-basename .s/.x pairs were found. Use --draft-file and --official-file to compare one explicit pair.",
                }
            )
    elif not pairs and not selection_errors:
        selection_errors.append(
            {
                "draft_file": "",
                "official_file": "",
                "message": "Select one explicit pair with --draft-file and --official-file, or use --discover-pairs.",
            }
        )

    pair_reports: list[dict[str, Any]] = []
    for index, (resolved_draft, resolved_official) in enumerate(pairs, start=1):
        if progress_callback is not None:
            progress_callback(
                f"Source diff: comparing {index}/{len(pairs)} {_source_diff_repo_path(resolved_draft, workspace_root=resolved_workspace_root)}"
            )
        pair_reports.append(
            build_pair_report(
                resolved_draft,
                resolved_official,
                workspace_root=resolved_workspace_root,
            )
        )

    error_count = len(selection_errors) + sum(1 for report in pair_reports if report["status"] != "ok")
    status = "ok"
    if error_count and not pair_reports:
        status = "error"
    elif error_count:
        status = "partial"

    return {
        "generated_by": "sattlint.devtools.source_diff_report",
        "report_kind": "source-diff-report",
        "status": status,
        "workspace_root": _source_diff_repo_path(resolved_workspace_root, workspace_root=resolved_workspace_root),
        "summary": {
            "compared_pair_count": len(pair_reports),
            "changed_pair_count": sum(1 for report in pair_reports if report["changed"]),
            "identical_pair_count": sum(1 for report in pair_reports if report["classification"] == "identical"),
            "layout_only_pair_count": sum(1 for report in pair_reports if report["classification"] == "layout-only"),
            "structural_pair_count": sum(1 for report in pair_reports if report["classification"] == "structural"),
            "error_count": error_count,
        },
        "pairs": pair_reports,
        "selection_errors": selection_errors,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SattLint .s/.x Diff Report",
        "",
        f"Status: {report['status']}",
        f"Compared pairs: {report['summary']['compared_pair_count']}",
        f"Changed pairs: {report['summary']['changed_pair_count']}",
        f"Identical pairs: {report['summary']['identical_pair_count']}",
        f"Layout-only pairs: {report['summary']['layout_only_pair_count']}",
        f"Structural pairs: {report['summary']['structural_pair_count']}",
        f"Errors: {report['summary']['error_count']}",
    ]

    if report["selection_errors"]:
        lines.extend(["", "## Selection Errors", ""])
        for error in report["selection_errors"]:
            lines.append(f"- {error['message']}")

    for pair in report["pairs"]:
        lines.extend(
            [
                "",
                f"## {pair['pair_name']}",
                "",
                f"Draft file: {pair['draft_file']}",
                f"Official file: {pair['official_file']}",
                f"Status: {pair['status']}",
                f"Classification: {pair['classification']}",
                f"Changed lines: {pair['summary']['changed_line_count']}",
                "",
            ]
        )
        if pair["errors"]:
            lines.append("Errors:")
            for error in pair["errors"]:
                phase = error.get("phase")
                prefix = error["side"] if not phase else f"{error['side']} {phase}"
                lines.append(f"- {prefix}: {error['error_type']}: {error['error']}")
            lines.append("")
        if pair["sections"]:
            for section in pair["sections"]:
                lines.append(f"### {section['title']}")
                for item in section["items"]:
                    lines.append(f"- {item}")
                for entry in section.get("entries", []):
                    lines.append("")
                    lines.append(f"#### {entry['name']}")
                    module_kind = entry.get("module_kind")
                    if module_kind is not None:
                        lines.append(f"- Kind: {module_kind}")
                    lines.append(f"- Change: {entry['change_kind']}")
                    for detail in entry.get("details", []):
                        lines.append(f"- {detail}")
                    for code_diff in entry.get("code_diffs", []):
                        lines.append("")
                        lines.append(f"##### {code_diff['label']}")
                        lines.append("```diff")
                        lines.extend(code_diff["diff_lines"])
                        lines.append("```")
                lines.append("")
        else:
            lines.append("No AST comparison sections available.")
    return "\n".join(lines) + "\n"


def _write_report_artifacts(output_dir: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / DEFAULT_JSON_OUTPUT_FILENAME
    markdown_path = output_dir / DEFAULT_MARKDOWN_OUTPUT_FILENAME
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def build_cli_parser(*, prog: str = "sattlint-source-diff-report", add_help: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        add_help=add_help,
        description="Build a review-friendly diff report between draft .s and official .x source pairs.",
    )
    parser.add_argument("--workspace-root", default=str(REPO_ROOT), help="Workspace root used for relative paths.")
    parser.add_argument("--draft-file", default=None, help="Draft .s file to compare.")
    parser.add_argument("--official-file", default=None, help="Official .x file to compare.")
    parser.add_argument(
        "--discover-pairs",
        action="store_true",
        help="Discover same-basename .s/.x pairs under the workspace root.",
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="Stdout format.")
    parser.add_argument(
        "--output-dir", default=None, help="Optional directory that receives JSON and Markdown reports."
    )
    parser.add_argument("--no-progress", action="store_true", help="Suppress progress messages on stderr.")
    return parser


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = build_cli_parser()
    return parser.parse_args(list(argv) if argv is not None else sys.argv[1:])


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    progress_callback = None if args.no_progress else _emit_progress
    report = build_source_diff_report(
        Path(args.workspace_root).resolve(),
        draft_file=None if args.draft_file is None else str(args.draft_file),
        official_file=None if args.official_file is None else str(args.official_file),
        discover_pairs=bool(args.discover_pairs),
        progress_callback=progress_callback,
    )
    output_error: OSError | None = None
    if args.output_dir:
        try:
            _write_report_artifacts(Path(args.output_dir).resolve(), report)
        except OSError as exc:
            output_error = exc

    if args.format == "markdown":
        print(render_markdown(report))
    else:
        print(cli_output.render_json_output(report))

    if output_error is not None:
        print(f"source diff output error: {output_error}", file=sys.stderr, flush=True)
        return 1
    return 0 if report["status"] in {"ok", "partial"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
