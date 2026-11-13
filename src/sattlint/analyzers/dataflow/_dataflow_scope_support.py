from __future__ import annotations

from typing import Any, cast

from sattlint.parser_api import ModuleTypeDef, ModuleTypeInstance, ParameterMapping, SingleModule, Variable, VarRef

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
    ) -> ScopeContext:
        return ScopeContext(
            env={casefold_key(variable.name): variable for variable in variables},
            param_mappings=param_mappings,
            module_path=module_path.copy(),
            display_module_path=module_path.copy(),
            moduleparameter_keys=moduleparameter_keys,
            current_library=current_library,
            parent_context=parent_context,
        )

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
