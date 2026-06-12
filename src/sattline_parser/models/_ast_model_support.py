from __future__ import annotations

import textwrap
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from ..utils.formatter import format_expr, format_list, format_optional, format_seq_nodes

if TYPE_CHECKING:
    from .ast_model import (
        BasePicture,
        DataType,
        FrameModule,
        GraphObject,
        InteractObject,
        ModuleCode,
        ModuleTypeDef,
        ModuleTypeInstance,
        ParameterMapping,
        SingleModule,
        Variable,
    )

type FormatExprFn = Callable[..., str]
type FormatListFn = Callable[..., str]
type FormatOptionalFn = Callable[..., str]
type FormatSeqNodesFn = Callable[..., str]
type AstNodeDict = dict[str, Any]
type PropertyMap = dict[str, Any]
type ModulePath = list[str]
type UsageKind = Literal["read", "write"]
type UsageLocation = tuple[ModulePath, UsageKind]


def variable_list() -> list[Variable]:
    return []


def usage_location_list() -> list[UsageLocation]:
    return []


def property_map() -> PropertyMap:
    return {}


def graph_object_list() -> list[GraphObject]:
    return []


def interact_object_list() -> list[InteractObject]:
    return []


def any_list() -> list[Any]:
    return []


def submodule_list() -> list[SingleModule | FrameModule | ModuleTypeInstance]:
    return []


def parameter_mapping_list() -> list[ParameterMapping]:
    return []


def datatype_def_list() -> list[DataType]:
    return []


def moduletype_def_list() -> list[ModuleTypeDef]:
    return []


def library_dependency_map() -> dict[str, list[str]]:
    return {}


def _unwrap_statement_node(value: Any, *, statement_key: str) -> Any:
    if hasattr(value, "data") and value.data == statement_key:
        children = getattr(value, "children", [])
        return children[0] if children else value
    return value


def render_module_code(module_code: ModuleCode, *, statement_key: str) -> str:
    seq_lines: list[str] = []
    if module_code.sequences:
        for sequence in module_code.sequences:
            size_str = f" with size {sequence.size}" if getattr(sequence, "size", None) is not None else ""
            seq_lines.append(
                f"Sequence {sequence.name!r} at {sequence.position}{size_str} (type={sequence.type})\n"
                f"    Code:\n" + textwrap.indent(format_seq_nodes(sequence.code), "        ")
            )
    else:
        seq_lines.append("No sequences")

    eq_lines: list[str] = []
    if module_code.equations:
        for equation in module_code.equations:
            pretty_code = [
                format_expr(_unwrap_statement_node(statement, statement_key=statement_key))
                for statement in equation.code
            ]
            size_str = f" with size {equation.size}" if getattr(equation, "size", None) is not None else ""
            eq_lines.append(
                f"EquationBlock name={equation.name!r} at {equation.position}{size_str}\n"
                f"    Code:\n" + textwrap.indent("\n".join(pretty_code), "        ")
            )

    return (
        "ModuleCode{\n"
        + textwrap.indent("Sequences:\n" + textwrap.indent("\n\n".join(seq_lines), "    "), "    ")
        + "\n\n"
        + textwrap.indent("Equations:\n" + textwrap.indent("\n\n".join(eq_lines), "    "), "    ")
        + "\n}"
    )


def render_single_module(module: SingleModule) -> str:
    lines = [
        f"Name            : {module.header.name!r}",
        f"Enable          : {module.header.enable}",
        f"Invoke_coord    : {module.header.invoke_coord!r}",
        f"Datecode        : {module.datecode!r}",
        f"Moduleparameters: {format_list(module.moduleparameters)}",
        f"Localvariables  : {format_list(module.localvariables)}",
        f"Submodules      : {format_list(module.submodules)}",
        f"ModuleCode      : {format_optional(module.modulecode)}",
        f"ParameterMappings: {format_list(module.parametermappings)}",
    ]
    return "SingleModule{\n" + textwrap.indent("\n".join(lines), "    ") + "}"


def render_frame_module(module: FrameModule) -> str:
    lines = [
        f"Name         : {module.header.name!r}",
        f"Enable       : {module.header.enable}",
        f"Invoke_coord : {module.header.invoke_coord!r}",
        f"Datecode     : {module.datecode!r}",
        f"Submodules   : {format_list(module.submodules)}",
        f"ModuleCode   : {format_optional(module.modulecode)}",
    ]
    return "FrameModule{\n" + textwrap.indent("\n".join(lines), "    ") + "}"


def render_moduletype_instance(instance: ModuleTypeInstance) -> str:
    lines = [
        f"Name             : {instance.header.name!r}",
        f"Enable           : {instance.header.enable}",
        f"Enable_tail      : {instance.header.enable_tail}",
        f"Invoke_coord     : {instance.header.invoke_coord!r}",
        f"ModuleTypeName   : {instance.moduletype_name!r}",
        f"ParameterMappings: {format_list(instance.parametermappings)}",
    ]
    return "ModuleTypeInstance{\n" + textwrap.indent("\n".join(lines), "    ") + "}"


def render_moduletype_def(moduletype: ModuleTypeDef) -> str:
    lines = [
        f"Name            : {moduletype.name!r}",
        f"Datecode        : {moduletype.datecode!r}",
        f"OriginFile      : {moduletype.origin_file!r}",
        f"OriginLib       : {moduletype.origin_lib!r}",
        f"Moduleparameters: {format_list(moduletype.moduleparameters)}",
        f"Localvariables  : {format_list(moduletype.localvariables)}",
        f"Submodules      : {format_list(moduletype.submodules)}",
        f"ModuleCode      : {format_optional(moduletype.modulecode)}",
        f"ParameterMappings: {format_list(moduletype.parametermappings)}",
    ]
    return "ModulType{\n" + textwrap.indent("\n".join(lines), "    ") + "}"


def render_base_picture(base_picture: BasePicture) -> str:
    lines = [
        f"Name: {base_picture.name!r}\n"
        f"Position: {base_picture.position!r}\n\n"
        f"TYPEDEFINITIONS (Records): {format_list(base_picture.datatype_defs)}\n\n"
        f"TYPEDEFINITIONS (Modules): {format_list(base_picture.moduletype_defs)}\n"
        f"Localvariables: {format_list(base_picture.localvariables)}\n\n"
        f"Submodules: {format_list(base_picture.submodules)}\n\n"
        f"ModuleCode: {base_picture.modulecode}\n\n"
    ]
    return "BasePicture{\n" + textwrap.indent("\n  ".join(lines), "    ") + "}"
