from __future__ import annotations

from typing import Any

from sattline_parser.models.ast_model import ModuleTypeDef, ModuleTypeInstance, ParameterMapping, SingleModule, Variable

from ..casefolding import casefold_key
from ..grammar import constants as const
from ..resolution.common import varname_base
from ..resolution.scope import ScopeContext
from ._dataflow_common import StateMap


class _DataflowScopeSupportMixin:
    def _build_scope_context(
        self: Any,
        variables: list[Variable],
        *,
        param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]],
        module_path: list[str],
        current_library: str | None,
        parent_context: ScopeContext | None,
    ) -> ScopeContext:
        return ScopeContext(
            env={casefold_key(variable.name): variable for variable in variables},
            param_mappings=param_mappings,
            module_path=module_path.copy(),
            display_module_path=module_path.copy(),
            current_library=current_library,
            parent_context=parent_context,
        )

    def _iter_root_typedefs(self: Any) -> list[ModuleTypeDef]:
        return [
            moduletype
            for moduletype in (self.bp.moduletype_defs or [])
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
            if isinstance(mapping.source, dict) and const.KEY_VAR_NAME in mapping.source:
                full_source = mapping.source[const.KEY_VAR_NAME]
            elif isinstance(mapping.source, str):
                full_source = mapping.source
            else:
                continue
            source_var, field_prefix, decl_path, decl_display_path = parent_context.resolve_variable(full_source)
            if source_var is None:
                continue
            resolved[target_name.casefold()] = (
                source_var,
                field_prefix,
                decl_path,
                decl_display_path,
            )
        return resolved


__all__ = ["_DataflowScopeSupportMixin"]
