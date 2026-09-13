from __future__ import annotations

from dataclasses import dataclass

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeInstance,
    SingleModule,
    Variable,
)

from ._wave2_node_traversal import (
    AssignmentEvent,
    StatementSite,
    iter_assignment_events,
    iter_read_variable_names,
    iter_statement_sites,
    root_variable_name,
)
from .shared.target_origin import TargetOriginFilter
from .shared.variable_utils import merge_variable_env

__all__ = [
    "AssignmentEvent",
    "ModuleScope",
    "StatementSite",
    "as_bool_literal",
    "as_numeric_literal",
    "as_scalar_literal",
    "iter_assignment_events",
    "iter_read_variable_names",
    "iter_statement_sites",
    "merge_env",
    "root_variable_name",
    "walk_module_scopes",
]


@dataclass(frozen=True)
class ModuleScope:
    module_path: tuple[str, ...]
    env: dict[str, Variable]
    modulecode: ModuleCode | None


_NodeDict = dict[str, object]


def merge_env(
    env: dict[str, Variable],
    variables: list[Variable] | None,
) -> dict[str, Variable]:
    return merge_variable_env(env, variables)


def walk_module_scopes(
    base_picture: BasePicture,
    *,
    moduletype_filter: TargetOriginFilter | None = None,
) -> list[ModuleScope]:
    root_path = (base_picture.header.name,)
    root_env = merge_env({}, base_picture.localvariables)
    scopes = [ModuleScope(module_path=root_path, env=root_env, modulecode=base_picture.modulecode)]

    for moduletype in base_picture.moduletype_defs or []:
        if moduletype_filter is not None and not moduletype_filter(moduletype):
            continue
        typedef_env = merge_env({}, moduletype.moduleparameters)
        typedef_env = merge_env(typedef_env, moduletype.localvariables)
        typedef_path = (*root_path, moduletype.name)
        scopes.append(ModuleScope(module_path=typedef_path, env=typedef_env, modulecode=moduletype.modulecode))
        scopes.extend(_walk_nested_modules(moduletype.submodules or [], parent_path=typedef_path, env=typedef_env))

    scopes.extend(_walk_nested_modules(base_picture.submodules or [], parent_path=root_path, env=root_env))
    return scopes


def _walk_nested_modules(
    modules: list[SingleModule | FrameModule | ModuleTypeInstance],
    *,
    parent_path: tuple[str, ...],
    env: dict[str, Variable],
) -> list[ModuleScope]:
    scopes: list[ModuleScope] = []
    for module in modules:
        module_path = (*parent_path, module.header.name)
        if isinstance(module, ModuleTypeInstance):
            continue
        if isinstance(module, SingleModule):
            nested_env = merge_env(env, module.moduleparameters)
            nested_env = merge_env(nested_env, module.localvariables)
            scopes.append(ModuleScope(module_path=module_path, env=nested_env, modulecode=module.modulecode))
            scopes.extend(_walk_nested_modules(module.submodules or [], parent_path=module_path, env=nested_env))
            continue

        scopes.append(ModuleScope(module_path=module_path, env=env, modulecode=module.modulecode))
        scopes.extend(_walk_nested_modules(module.submodules or [], parent_path=module_path, env=env))
    return scopes


def as_scalar_literal(value: object) -> object | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value
    return None


def as_bool_literal(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def as_numeric_literal(value: object) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return value
    return None
