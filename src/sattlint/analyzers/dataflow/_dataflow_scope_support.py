from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from sattlint.parser_api import (
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    SingleModule,
    Variable,
    VarRef,
)

from ...resolution.common import varname_base
from ...resolution.scope import ScopeContext
from ...utils.casefolding import casefold_key
from ._dataflow_common import StateMap


class DataflowScopeSupportMixin:
    def _build_scope_context(
        self: Any,
        variables: list[Variable],
        *,
        param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]],
        module_path: list[str],
        current_library: str | None,
        parent_context: ScopeContext | None,
        moduleparameter_keys: frozenset[str] = frozenset(),
        children: Iterable[SingleModule | FrameModule | ModuleTypeInstance] = (),
    ) -> ScopeContext:
        context = ScopeContext(
            env={casefold_key(variable.name): variable for variable in variables},
            param_mappings=param_mappings,
            module_path=module_path.copy(),
            display_module_path=module_path.copy(),
            moduleparameter_keys=moduleparameter_keys,
            current_library=current_library,
            parent_context=parent_context,
        )
        context.submodule_mapped_source_keys.update(self._child_mapped_source_keys(children, context))
        if self._analyzed_target_is_library:
            mapped_names = param_mappings.keys()
            self._unmapped_interface_parameter_ids.update(
                id(variable)
                for variable in variables
                if casefold_key(variable.name) in moduleparameter_keys
                and casefold_key(variable.name) not in mapped_names
            )
        return context

    def _child_mapped_source_keys(
        self: Any,
        children: Iterable[SingleModule | FrameModule | ModuleTypeInstance],
        context: ScopeContext,
    ) -> set[tuple[str, ...]]:
        """Symbol keys a direct child can write through its parameter mappings."""
        keys: set[tuple[str, ...]] = set()
        for child in children:
            mappings = cast(list[ParameterMapping], getattr(child, "parametermappings", None) or [])
            for mapping in mappings:
                if mapping.is_source_global:
                    continue
                source = mapping.source
                if isinstance(source, VarRef):
                    full_source = source.name
                else:
                    continue
                if not full_source:
                    continue
                variable, field_path, decl_path, _display_path = context.resolve_variable(full_source)
                if variable is None:
                    continue
                keys.add(self._state_key(decl_path, variable.name, field_path))
        return keys

    def _iter_root_typedefs(self: Any) -> list[ModuleTypeDef]:
        moduletype_defs = cast(list[ModuleTypeDef] | None, getattr(self.bp, "moduletype_defs", None))
        return [
            moduletype
            for moduletype in (moduletype_defs or [])
            if self._is_from_root_origin(
                getattr(moduletype, "origin_file", None),
                getattr(moduletype, "origin_lib", None),
            )
        ]

    def _build_typedef_seed(
        self: Any,
        moduletype: ModuleTypeDef,
        module_path: list[str],
    ) -> tuple[ScopeContext, StateMap]:
        variables = [*(moduletype.moduleparameters or []), *(moduletype.localvariables or [])]
        context = self._build_scope_context(
            variables,
            param_mappings={},
            module_path=module_path,
            current_library=moduletype.origin_lib or getattr(self.bp, "origin_lib", None),
            parent_context=None,
            moduleparameter_keys=frozenset(
                casefold_key(variable.name) for variable in moduletype.moduleparameters or []
            ),
            children=moduletype.submodules or [],
        )
        return context, self._seed_state({}, module_path, variables)

    def _build_single_context(
        self: Any,
        mod: SingleModule,
        parent_context: ScopeContext,
        module_path: list[str],
    ) -> ScopeContext:
        return self._build_scope_context(
            [*(mod.moduleparameters or []), *(mod.localvariables or [])],
            param_mappings=self._build_parameter_mappings(
                mod.parametermappings or [],
                parent_context,
            ),
            module_path=module_path,
            current_library=parent_context.current_library,
            parent_context=parent_context,
            moduleparameter_keys=frozenset(casefold_key(variable.name) for variable in mod.moduleparameters or []),
            children=mod.submodules or [],
        )

    def _build_typedef_context(
        self: Any,
        moduletype: ModuleTypeDef,
        instance: ModuleTypeInstance,
        parent_context: ScopeContext,
        module_path: list[str],
    ) -> ScopeContext:
        return self._build_scope_context(
            [*(moduletype.moduleparameters or []), *(moduletype.localvariables or [])],
            param_mappings=self._build_parameter_mappings(
                instance.parametermappings or [],
                parent_context,
            ),
            module_path=module_path,
            current_library=moduletype.origin_lib or parent_context.current_library,
            parent_context=parent_context,
            moduleparameter_keys=frozenset(
                casefold_key(variable.name) for variable in moduletype.moduleparameters or []
            ),
            children=moduletype.submodules or [],
        )

    def _build_parameter_mappings(
        self: Any,
        mappings: list[ParameterMapping],
        parent_context: ScopeContext,
    ) -> dict[str, tuple[Variable, str, list[str], list[str]]]:
        resolved: dict[str, tuple[Variable, str, list[str], list[str]]] = {}
        for mapping in mappings:
            if mapping.is_source_global:
                continue
            target_name = varname_base(mapping.target)
            if not target_name:
                continue
            source = cast(VarRef | str | None, mapping.source)
            if isinstance(source, VarRef):
                full_source = source.name
            elif isinstance(source, str):
                full_source = source
            else:
                continue
            source_var, field_prefix, decl_path, decl_display_path = parent_context.resolve_variable(str(full_source))
            if source_var is None:
                continue
            resolved[target_name.casefold()] = (
                source_var,
                field_prefix,
                decl_path,
                decl_display_path,
            )
        return resolved


__all__ = ["DataflowScopeSupportMixin"]
