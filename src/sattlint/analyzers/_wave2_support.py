from __future__ import annotations

from dataclasses import dataclass

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    SingleModule,
    Variable,
)

from ..grammar import constants as const
from ..resolution.common import format_moduletype_label, resolve_moduletype_def_strict, varname_full
from ._wave2_node_traversal import (
    AssignmentEvent,
    StatementSite,
    iter_assignment_events,
    iter_read_variable_names,
    iter_statement_sites,
    root_variable_name,
)
from .variable_utils import merge_variable_env

__all__ = [
    "AssignmentEvent",
    "InstanceParameterValue",
    "ModuleScope",
    "StatementSite",
    "as_bool_literal",
    "as_numeric_literal",
    "as_scalar_literal",
    "collect_instance_parameter_values",
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


@dataclass(frozen=True)
class InstanceParameterValue:
    module_path: tuple[str, ...]
    moduletype_label: str
    parameter_name: str
    value_display: str
    value_signature: str


@dataclass(frozen=True)
class _ParameterValue:
    status: str
    value: object | None = None
    source: str | None = None
    signature: str | None = None


_NodeDict = dict[str, object]


def merge_env(
    env: dict[str, Variable],
    variables: list[Variable] | None,
) -> dict[str, Variable]:
    return merge_variable_env(env, variables)


def walk_module_scopes(base_picture: BasePicture) -> list[ModuleScope]:
    root_path = (base_picture.header.name,)
    root_env = merge_env({}, base_picture.localvariables)
    scopes = [ModuleScope(module_path=root_path, env=root_env, modulecode=base_picture.modulecode)]

    for moduletype in base_picture.moduletype_defs or []:
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


def collect_instance_parameter_values(
    base_picture: BasePicture,
    *,
    unavailable_libraries: set[str] | None = None,
) -> list[InstanceParameterValue]:
    values: list[InstanceParameterValue] = []
    root_path = (base_picture.header.name,)
    root_env = merge_env({}, base_picture.localvariables)
    _walk_instance_modules(
        base_picture,
        base_picture.submodules or [],
        parent_path=root_path,
        env=root_env,
        unavailable_libraries=unavailable_libraries or set(),
        values=values,
    )
    return values


def _walk_instance_modules(
    base_picture: BasePicture,
    modules: list[SingleModule | FrameModule | ModuleTypeInstance],
    *,
    parent_path: tuple[str, ...],
    env: dict[str, Variable],
    unavailable_libraries: set[str],
    values: list[InstanceParameterValue],
) -> None:
    for module in modules:
        module_path = (*parent_path, module.header.name)
        if isinstance(module, ModuleTypeInstance):
            values.extend(
                _collect_instance_parameter_values(
                    base_picture,
                    module,
                    module_path=module_path,
                    env=env,
                    unavailable_libraries=unavailable_libraries,
                )
            )
            continue
        if isinstance(module, SingleModule):
            nested_env = merge_env(env, module.moduleparameters)
            nested_env = merge_env(nested_env, module.localvariables)
            _walk_instance_modules(
                base_picture,
                module.submodules or [],
                parent_path=module_path,
                env=nested_env,
                unavailable_libraries=unavailable_libraries,
                values=values,
            )
            continue
        _walk_instance_modules(
            base_picture,
            module.submodules or [],
            parent_path=module_path,
            env=env,
            unavailable_libraries=unavailable_libraries,
            values=values,
        )


def _collect_instance_parameter_values(
    base_picture: BasePicture,
    instance: ModuleTypeInstance,
    *,
    module_path: tuple[str, ...],
    env: dict[str, Variable],
    unavailable_libraries: set[str],
) -> list[InstanceParameterValue]:
    try:
        moduletype = resolve_moduletype_def_strict(
            base_picture,
            instance.moduletype_name,
            current_library=getattr(instance, "origin_lib", None),
            unavailable_libraries=unavailable_libraries,
        )
    except ValueError:
        moduletype = None

    moduletype_label = format_moduletype_label(moduletype) if moduletype is not None else instance.moduletype_name
    items: list[InstanceParameterValue] = []
    for parameter_name in _parameter_names(instance, moduletype):
        value = _get_parameter_value(instance, moduletype, env, parameter_name)
        if value.status != "resolved" or not value.signature:
            continue
        items.append(
            InstanceParameterValue(
                module_path=module_path,
                moduletype_label=moduletype_label,
                parameter_name=parameter_name,
                value_display=_parameter_value_display(value),
                value_signature=value.signature,
            )
        )
    return items


def _parameter_names(
    instance: ModuleTypeInstance,
    moduletype: ModuleTypeDef | None,
) -> tuple[str, ...]:
    names_by_key: dict[str, str] = {}
    for mapping in instance.parametermappings or []:
        target_name = _mapping_parameter_name(mapping)
        if target_name:
            names_by_key.setdefault(target_name.casefold(), target_name)
    parameters = moduletype.moduleparameters if moduletype is not None else []
    for parameter in parameters:
        if parameter.init_value is not None:
            names_by_key.setdefault(parameter.name.casefold(), parameter.name)
    return tuple(names_by_key[key] for key in sorted(names_by_key))


def _get_parameter_value(
    instance: ModuleTypeInstance,
    moduletype: ModuleTypeDef | None,
    env: dict[str, Variable],
    parameter_name: str,
) -> _ParameterValue:
    mapping = _find_parameter_mapping(instance.parametermappings, parameter_name)
    if mapping is not None:
        resolved = _resolve_mapping_value(mapping, env)
        if resolved is not None:
            return resolved
        return _ParameterValue(status="unresolved_mapping")

    if moduletype is None:
        return _ParameterValue(status="unknown")

    parameter = _find_variable(moduletype.moduleparameters, parameter_name)
    if parameter is None or parameter.init_value is None:
        return _ParameterValue(status="unknown")
    return _ParameterValue(
        status="resolved",
        value=parameter.init_value,
        source=f"default parameter value on {format_moduletype_label(moduletype)}",
        signature=_literal_signature(parameter.init_value),
    )


def _find_parameter_mapping(
    mappings: list[ParameterMapping] | None,
    parameter_name: str,
) -> ParameterMapping | None:
    wanted = parameter_name.casefold()
    for mapping in mappings or []:
        target_name = _mapping_parameter_name(mapping)
        if target_name and target_name.casefold() == wanted:
            return mapping
    return None


def _mapping_parameter_name(mapping: ParameterMapping) -> str | None:
    target_name = varname_full(getattr(mapping, "target", None))
    if not target_name:
        return None
    return target_name.split(".", 1)[0]


def _resolve_mapping_value(
    mapping: ParameterMapping,
    env: dict[str, Variable],
) -> _ParameterValue | None:
    if mapping.source_type == const.KEY_VALUE:
        return _ParameterValue(
            status="resolved",
            value=mapping.source_literal,
            source="literal parameter mapping",
            signature=_literal_signature(mapping.source_literal),
        )

    full_ref = varname_full(getattr(mapping, "source", None))
    if not full_ref or mapping.is_source_global:
        return None
    if "." in full_ref or ":" in full_ref:
        return None

    variable = env.get(full_ref.casefold())
    if variable is None or variable.init_value is None:
        return None
    return _ParameterValue(
        status="resolved",
        value=variable.init_value,
        source=f"init value of variable {variable.name}",
        signature=_literal_signature(variable.init_value),
    )


def _find_variable(
    variables: list[Variable] | None,
    wanted_name: str,
) -> Variable | None:
    wanted = wanted_name.casefold()
    for variable in variables or []:
        if variable.name.casefold() == wanted:
            return variable
    return None


def _parameter_value_display(value: _ParameterValue) -> str:
    if value.value is not None:
        return repr(value.value)
    return value.source or "<unresolved>"


def _literal_signature(value: object | None) -> str:
    if isinstance(value, str):
        return f"literal:{value.strip().casefold()}"
    return f"literal:{value!r}"
