"""Recursive structural-validation walkers for modules and dependency context."""

from __future__ import annotations

from collections.abc import Sequence as AbcSequence

from sattline_parser.models.ast_model import FrameModule, ModuleTypeDef, ModuleTypeInstance, SingleModule, Variable

from ._validation_structure_core import (
    _merge_env,
    _module_code_policy,
    _ModuleValidationPolicy,
    _validate_identifier,
    _validate_module_code,
    _validate_parameter_mappings,
    _validate_unique_submodule_names,
    _validate_variable_list,
)
from .resolution.type_graph import TypeGraph


def _validate_module(
    module: object,
    context: str,
    parent_env: dict[str, Variable],
    type_graph: TypeGraph,
    known_datatypes: AbcSequence[str],
    moduletype_index: dict[str, list[ModuleTypeDef]],
    allow_unresolved_external_datatypes: bool = False,
    enforce_unique_submodule_names: bool = True,
    policy: _ModuleValidationPolicy | None = None,
) -> None:
    active_policy = policy or _ModuleValidationPolicy()

    if isinstance(module, SingleModule):
        _validate_identifier(module.header.name, f"{context} module")
        module_context = f"{context} module {module.header.name!r}"
        _validate_variable_list(
            module.moduleparameters,
            module_context,
            type_graph=type_graph,
            known_datatypes=known_datatypes,
            allow_unresolved_external_datatypes=allow_unresolved_external_datatypes,
        )
        _validate_variable_list(
            module.localvariables,
            module_context,
            type_graph=type_graph,
            known_datatypes=known_datatypes,
            allow_unresolved_external_datatypes=allow_unresolved_external_datatypes,
        )
        env = _merge_env(parent_env, module.moduleparameters)
        env = _merge_env(env, module.localvariables)
        _validate_parameter_mappings(
            module.parametermappings,
            module_context,
            type_graph=type_graph,
            expected_parameters={variable.name.casefold(): variable for variable in module.moduleparameters or []},
            source_env=parent_env,
            policy=active_policy,
        )
        _validate_module_code(
            module.modulecode,
            module_context,
            env,
            type_graph,
            module_code_policy=_module_code_policy(active_policy),
        )
        _validate_unique_submodule_names(
            module.submodules,
            module_context,
            enforce_unique_names=enforce_unique_submodule_names,
        )
        for submodule in module.submodules or []:
            _validate_module(
                submodule,
                module_context,
                env,
                type_graph,
                known_datatypes,
                moduletype_index,
                allow_unresolved_external_datatypes,
                enforce_unique_submodule_names,
                policy=active_policy,
            )
        return

    if isinstance(module, FrameModule):
        _validate_identifier(module.header.name, f"{context} frame")
        module_context = f"{context} frame {module.header.name!r}"
        _validate_module_code(
            module.modulecode,
            module_context,
            parent_env,
            type_graph,
            module_code_policy=_module_code_policy(active_policy),
        )
        _validate_unique_submodule_names(
            module.submodules,
            module_context,
            enforce_unique_names=enforce_unique_submodule_names,
        )
        for submodule in module.submodules or []:
            _validate_module(
                submodule,
                module_context,
                parent_env,
                type_graph,
                known_datatypes,
                moduletype_index,
                allow_unresolved_external_datatypes,
                enforce_unique_submodule_names,
                policy=active_policy,
            )
        return

    if isinstance(module, ModuleTypeInstance):
        _validate_identifier(module.header.name, f"{context} module instance")
        _validate_identifier(module.moduletype_name, f"{context} module type reference")
        matches = moduletype_index.get(module.moduletype_name.casefold(), [])
        expected_parameters = None
        if len(matches) == 1:
            expected_parameters = {variable.name.casefold(): variable for variable in matches[0].moduleparameters or []}
        _validate_parameter_mappings(
            module.parametermappings,
            f"{context} module instance {module.header.name!r}",
            type_graph=type_graph,
            expected_parameters=expected_parameters,
            source_env=parent_env,
            policy=active_policy,
        )


def _validate_module_dependency_context(
    module: object,
    context: str,
    parent_env: dict[str, Variable],
    type_graph: TypeGraph,
    moduletype_index: dict[str, list[ModuleTypeDef]],
    *,
    policy: _ModuleValidationPolicy | None = None,
) -> None:
    active_policy = policy or _ModuleValidationPolicy()

    if isinstance(module, SingleModule):
        module_context = f"{context} module {module.header.name!r}"
        env = _merge_env(parent_env, module.moduleparameters)
        env = _merge_env(env, module.localvariables)
        _validate_parameter_mappings(
            module.parametermappings,
            module_context,
            type_graph=type_graph,
            expected_parameters={variable.name.casefold(): variable for variable in module.moduleparameters or []},
            source_env=parent_env,
            policy=active_policy,
        )
        for submodule in module.submodules or []:
            _validate_module_dependency_context(
                submodule,
                module_context,
                env,
                type_graph,
                moduletype_index,
                policy=active_policy,
            )
        return

    if isinstance(module, FrameModule):
        module_context = f"{context} frame {module.header.name!r}"
        for submodule in module.submodules or []:
            _validate_module_dependency_context(
                submodule,
                module_context,
                parent_env,
                type_graph,
                moduletype_index,
                policy=active_policy,
            )
        return

    if isinstance(module, ModuleTypeInstance):
        matches = moduletype_index.get(module.moduletype_name.casefold(), [])
        expected_parameters = None
        if len(matches) == 1:
            expected_parameters = {variable.name.casefold(): variable for variable in matches[0].moduleparameters or []}
        _validate_parameter_mappings(
            module.parametermappings,
            f"{context} module instance {module.header.name!r}",
            type_graph=type_graph,
            expected_parameters=expected_parameters,
            source_env=parent_env,
            policy=active_policy,
        )
