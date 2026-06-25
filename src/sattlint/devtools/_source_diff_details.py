"""Normalized AST detail helpers for source diff reports."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

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


def stable_signature_text(value: object) -> str:
    return re.sub(r"SourceSpan\([^)]*\)", "SourceSpan()", repr(value))


def stable_signature_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, tuple):
        tuple_value = cast(tuple[object, ...], value)
        return tuple(stable_signature_value(item) for item in tuple_value)
    if isinstance(value, list):
        list_value = cast(list[object], value)
        return tuple(stable_signature_value(item) for item in list_value)
    if isinstance(value, Mapping):
        mapping_value = cast(Mapping[object, object], value)
        return tuple(sorted((str(key), stable_signature_value(item)) for key, item in mapping_value.items()))
    return stable_signature_text(value)


def variable_signature(variable: Variable) -> tuple[object, ...]:
    return (
        variable.datatype_text,
        bool(variable.global_var),
        bool(variable.const),
        bool(variable.state),
        bool(variable.opsave),
        bool(variable.secure),
        stable_signature_value(variable.init_value),
        variable.description or "",
        variable.init_is_duration,
    )


def datatype_signature(datatype: DataType) -> tuple[object, ...]:
    return (
        datatype.description or "",
        datatype.datecode,
        tuple((variable.name.casefold(), variable_signature(variable)) for variable in datatype.var_list or []),
    )


def module_header_signature(header: object | None) -> tuple[object, ...] | None:
    if header is None:
        return None
    return (
        getattr(header, "name", ""),
        stable_signature_value(getattr(header, "invoke_coord", None)),
        stable_signature_value(getattr(header, "invocation_arguments", ())),
        stable_signature_value(getattr(header, "layer_info", None)),
        bool(getattr(header, "enable", True)),
        stable_signature_value(getattr(header, "zoom_limits", None)),
        bool(getattr(header, "zoomable", False)),
        stable_signature_value(getattr(header, "enable_tail", None)),
    )


def moduledef_signature(moduledef: ModuleDef | None) -> tuple[object, ...] | None:
    if moduledef is None:
        return None
    return (
        moduledef.clipping_bounds,
        moduledef.zoom_limits,
        moduledef.seq_layers,
        moduledef.grid,
        moduledef.zoomable,
        tuple(stable_signature_text(graph_object) for graph_object in moduledef.graph_objects or []),
        tuple(stable_signature_text(interact_object) for interact_object in moduledef.interact_objects or []),
        tuple(sorted((str(key), stable_signature_text(value)) for key, value in (moduledef.properties or {}).items())),
    )


def modulecode_signature(modulecode: ModuleCode | None) -> tuple[object, ...] | None:
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
                tuple(stable_signature_text(code) for code in sequence.code or []),
            )
            for sequence in modulecode.sequences or []
        ),
        tuple(
            (
                equation.name.casefold(),
                equation.position,
                equation.size,
                tuple(stable_signature_text(code) for code in equation.code or []),
            )
            for equation in modulecode.equations or []
        ),
    )


def submodule_signature(module: SingleModule | FrameModule | ModuleTypeInstance) -> tuple[object, ...]:
    header_signature = module_header_signature(module.header)
    if isinstance(module, SingleModule):
        return (
            "single-module",
            header_signature,
            module.datecode,
            tuple(
                (variable.name.casefold(), variable_signature(variable)) for variable in module.moduleparameters or []
            ),
            tuple((variable.name.casefold(), variable_signature(variable)) for variable in module.localvariables or []),
            tuple(submodule_signature(child) for child in module.submodules or []),
            moduledef_signature(module.moduledef),
            modulecode_signature(module.modulecode),
            tuple(str(mapping) for mapping in module.parametermappings or []),
        )
    if isinstance(module, FrameModule):
        return (
            "frame-module",
            header_signature,
            module.datecode,
            tuple(submodule_signature(child) for child in module.submodules or []),
            moduledef_signature(module.moduledef),
            modulecode_signature(module.modulecode),
        )
    return (
        "moduletype-instance",
        header_signature,
        module.moduletype_name.casefold(),
        tuple(str(mapping) for mapping in module.parametermappings or []),
    )


def variable_detail(variable: Variable) -> dict[str, Any]:
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


def variable_details(variables: Sequence[Variable] | None) -> list[dict[str, Any]]:
    return [variable_detail(variable) for variable in variables or []]


def format_variable_summary(detail: dict[str, Any]) -> str:
    return f"{detail['name']} [{detail['datatype']}]"


def format_qualifiers(detail: dict[str, Any]) -> str:
    qualifiers = cast(tuple[str, ...], detail["qualifiers"])
    return ", ".join(qualifiers) if qualifiers else "none"


def submodule_kind(module: SingleModule | FrameModule | ModuleTypeInstance) -> str:
    if isinstance(module, SingleModule):
        return "singlemodule"
    if isinstance(module, FrameModule):
        return "framemodule"
    return "moduletype-instance"


def submodule_detail(module: SingleModule | FrameModule | ModuleTypeInstance) -> dict[str, Any]:
    detail = {
        "name": module.header.name,
        "kind": submodule_kind(module),
        "parameter_mappings": tuple(str(mapping) for mapping in getattr(module, "parametermappings", ()) or ()),
        "signature": submodule_signature(module),
    }
    if isinstance(module, ModuleTypeInstance):
        detail["moduletype_name"] = module.moduletype_name
    return detail


def submodule_details(
    modules: Sequence[SingleModule | FrameModule | ModuleTypeInstance] | None,
) -> list[dict[str, Any]]:
    return [submodule_detail(module) for module in modules or []]


def format_submodule_summary(detail: dict[str, Any]) -> str:
    if detail["kind"] == "moduletype-instance":
        return f"{detail['name']} [instance:{detail['moduletype_name']}]"
    return f"{detail['name']} [{detail['kind']}]"


def modulecode_entity_code_lines(entity: dict[str, Any]) -> list[str]:
    return list(cast(tuple[str, ...], entity["code_lines"]))


def render_modulecode_entity_lines(entity: Any) -> tuple[str, ...]:
    raw_code = cast(Sequence[object] | None, getattr(entity, "code", None)) or ()
    if hasattr(entity, "type"):
        return tuple(format_seq_nodes(list(raw_code)).splitlines())

    rendered_lines: list[str] = []
    for statement in raw_code:
        rendered_lines.extend(format_expr(statement).splitlines())
    return tuple(rendered_lines)


def modulecode_entity_detail(entity: Any) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "name": entity.name,
        "position": entity.position,
        "size": entity.size,
        "code_lines": render_modulecode_entity_lines(entity),
    }
    if hasattr(entity, "type"):
        detail["type"] = entity.type
        detail["seqcontrol"] = bool(getattr(entity, "seqcontrol", False))
        detail["seqtimer"] = bool(getattr(entity, "seqtimer", False))
    return detail


def modulecode_detail(modulecode: ModuleCode | None) -> dict[str, Any]:
    if modulecode is None:
        return {"sequences": {}, "equations": {}}
    return {
        "sequences": {
            detail["name"].casefold(): detail
            for detail in (modulecode_entity_detail(sequence) for sequence in modulecode.sequences or [])
        },
        "equations": {
            detail["name"].casefold(): detail
            for detail in (modulecode_entity_detail(equation) for equation in modulecode.equations or [])
        },
    }


def moduledef_detail(moduledef: ModuleDef | None) -> dict[str, Any]:
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
            sorted((str(key), stable_signature_text(value)) for key, value in (moduledef.properties or {}).items())
        ),
    }


def basepicture_detail(base_picture: BasePicture) -> dict[str, Any]:
    return {
        "name": "BasePicture",
        "module_kind": "basepicture",
        "parameters": [],
        "variables": variable_details(base_picture.localvariables),
        "submodules": submodule_details(base_picture.submodules),
        "moduledef": moduledef_detail(base_picture.moduledef),
        "modulecode": modulecode_detail(base_picture.modulecode),
    }


def moduletype_detail(moduletype: ModuleTypeDef) -> dict[str, Any]:
    return {
        "name": moduletype.name,
        "module_kind": "moduletype",
        "parameters": variable_details(moduletype.moduleparameters),
        "variables": variable_details(moduletype.localvariables),
        "submodules": submodule_details(moduletype.submodules),
        "moduledef": moduledef_detail(moduletype.moduledef),
        "modulecode": modulecode_detail(moduletype.modulecode),
        "inline_modules": collect_inline_module_details(moduletype.submodules),
    }


def inline_module_detail(
    path: tuple[str, ...],
    module: SingleModule | FrameModule,
    *,
    inline_modules: Mapping[tuple[str, ...], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "name": " > ".join(path),
        "module_kind": submodule_kind(module),
        "parameters": variable_details(getattr(module, "moduleparameters", []) or []),
        "variables": variable_details(getattr(module, "localvariables", []) or []),
        "submodules": submodule_details(module.submodules),
        "moduledef": moduledef_detail(module.moduledef),
        "modulecode": modulecode_detail(module.modulecode),
        "inline_modules": dict(inline_modules or {}),
    }


def collect_inline_module_details(
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
        child_collected = collect_inline_module_details(module.submodules, parent_path=path)
        collected[key] = inline_module_detail(
            path,
            module,
            inline_modules={
                child_key[len(key) :]: child_detail
                for child_key, child_detail in child_collected.items()
                if path_has_prefix(child_key, key)
            },
        )
        collected.update(child_collected)
    return collected


def collect_moduletype_instance_details(
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
        collected.update(collect_moduletype_instance_details(module.submodules, parent_path=path))
    return collected


def path_has_prefix(path: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    return len(path) >= len(prefix) and path[: len(prefix)] == prefix


def module_content_signature(detail: Mapping[str, Any]) -> tuple[object, ...]:
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


def leaf_module_name(display_name: str) -> str:
    return display_name.rsplit(" > ", 1)[-1]


def is_promoted_moduletype_name(singlemodule_display_name: str, moduletype_name: str) -> bool:
    singlemodule_leaf = leaf_module_name(singlemodule_display_name).casefold()
    moduletype_key = moduletype_name.casefold()
    return moduletype_key in {singlemodule_leaf, f"{singlemodule_leaf}type"}


def entry_name_sort_key(entry: dict[str, Any]) -> str:
    return cast(str, entry["name"]).casefold()
