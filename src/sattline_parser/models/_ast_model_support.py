from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal, cast

from ..utils import formatter as formatter_module

if TYPE_CHECKING:
    from .ast_model import (
        DataType,
        FrameModule,
        GraphObject,
        InteractObject,
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

_formatter_module = cast(Any, formatter_module)
format_expr = cast(FormatExprFn, _formatter_module.format_expr)
format_list = cast(FormatListFn, _formatter_module.format_list)
format_optional = cast(FormatOptionalFn, _formatter_module.format_optional)
format_seq_nodes = cast(FormatSeqNodesFn, _formatter_module.format_seq_nodes)


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
