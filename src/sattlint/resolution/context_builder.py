"""Builder for ScopeContexts with variable resolution and symbol registration."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ..grammar import constants as const
from ..reporting.variables_report import IssueKind, VariableIssue
from .common import varname_base
from .paths import decorate_segment
from .scope import ScopeContext
from .symbol_table import SymbolKind

if TYPE_CHECKING:
    from ..models.ast_model import BasePicture, ModuleTypeDef, ModuleTypeInstance, SingleModule, Variable
    from .symbol_table import CanonicalSymbolTable
    from .type_graph import TypeGraph


class ContextBuilder:
    def __init__(
        self,
        base_picture: BasePicture,
        symbol_table: CanonicalSymbolTable,
        type_graph: TypeGraph,
        issues: list[VariableIssue],
        global_lookup_fn: Callable[[str | None], Variable | None],
    ):
        self.bp = base_picture
        self.symbol_table = symbol_table
        self.type_graph = type_graph
        self.issues = issues
        self.global_lookup_fn = global_lookup_fn

    def build_for_basepicture(self) -> ScopeContext:
        """Build root scope context for BasePicture."""
        env: dict[str, Variable] = {}
        for variable in self.bp.localvariables or []:
            env[variable.name.lower()] = variable

        module_path = [self.bp.header.name]
        display_path = [decorate_segment(self.bp.header.name, "BP")]

        for variable in self.bp.localvariables or []:
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=variable,
                kind=SymbolKind.LOCAL,
                type_graph=self.type_graph,
            )

        return ScopeContext(
            env=env,
            param_mappings={},
            module_path=module_path,
            display_module_path=display_path,
            current_library=getattr(self.bp, "origin_lib", None),
            parent_context=None,
        )

    def build_for_single(
        self,
        mod: SingleModule,
        parent_context: ScopeContext,
        module_path: list[str],
        display_module_path: list[str],
    ) -> ScopeContext:
        """Build scope context with parameter mapping resolution."""
        env: dict[str, Variable] = {}

        params = list(mod.moduleparameters or [])
        locals_ = list(mod.localvariables or [])

        param_keys = {variable.name.casefold(): variable for variable in params}
        local_keys = {variable.name.casefold(): variable for variable in locals_}
        for key in set(param_keys.keys()) & set(local_keys.keys()):
            parameter = param_keys[key]
            local_variable = local_keys[key]
            self.issues.append(
                VariableIssue(
                    kind=IssueKind.NAME_COLLISION,
                    module_path=module_path.copy(),
                    variable=local_variable,
                    role=f"name collision with parameter {parameter.name!r}",
                    source_variable=parameter,
                )
            )

        for variable in params:
            env[variable.name.lower()] = variable
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=variable,
                kind=SymbolKind.PARAMETER,
                type_graph=self.type_graph,
            )
        for variable in locals_:
            env[variable.name.lower()] = variable
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=variable,
                kind=SymbolKind.LOCAL,
                type_graph=self.type_graph,
            )

        param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]] = {}

        for parameter_mapping in mod.parametermappings or []:
            target_name = varname_base(parameter_mapping.target)
            if not target_name or parameter_mapping.is_source_global:
                continue
            target_display_name = (
                parameter_mapping.target[const.KEY_VAR_NAME]
                if isinstance(parameter_mapping.target, dict) and const.KEY_VAR_NAME in parameter_mapping.target
                else str(parameter_mapping.target)
            )
            target_key = target_name.casefold()

            if target_key not in param_keys:
                self.issues.append(
                    VariableIssue(
                        kind=IssueKind.UNKNOWN_PARAMETER_TARGET,
                        module_path=module_path.copy(),
                        variable=None,
                        role=(f"unknown parameter mapping target " f"{target_display_name!r}"),
                    )
                )
                continue

            if isinstance(parameter_mapping.source, dict) and const.KEY_VAR_NAME in parameter_mapping.source:
                full_source = parameter_mapping.source[const.KEY_VAR_NAME]
            elif isinstance(parameter_mapping.source, str):
                full_source = parameter_mapping.source
            else:
                continue

            source_var, source_field_prefix, source_decl_path, source_decl_display_path = (
                parent_context.resolve_variable(full_source)
            )

            if source_var:
                param_mappings[target_key] = (
                    source_var,
                    source_field_prefix,
                    source_decl_path,
                    source_decl_display_path,
                )

        return ScopeContext(
            env=env,
            param_mappings=param_mappings,
            module_path=module_path,
            display_module_path=display_module_path,
            current_library=parent_context.current_library,
            parent_context=parent_context,
        )

    def build_for_typedef(
        self,
        moduletype: ModuleTypeDef,
        instance: ModuleTypeInstance,
        parent_context: ScopeContext | None = None,
        module_path: list[str] | None = None,
        display_module_path: list[str] | None = None,
    ) -> ScopeContext:
        """Build scope context for a typedef instance with parameter mappings."""
        env: dict[str, Variable] = {}

        module_path = module_path or []
        display_module_path = display_module_path or []

        params = list(moduletype.moduleparameters or [])
        locals_ = list(moduletype.localvariables or [])

        param_keys = {variable.name.casefold(): variable for variable in params}
        local_keys = {variable.name.casefold(): variable for variable in locals_}
        for key in set(param_keys.keys()) & set(local_keys.keys()):
            parameter = param_keys[key]
            local_variable = local_keys[key]
            self.issues.append(
                VariableIssue(
                    kind=IssueKind.NAME_COLLISION,
                    module_path=module_path.copy(),
                    variable=local_variable,
                    role=f"name collision with parameter {parameter.name!r}",
                    source_variable=parameter,
                )
            )

        for variable in params:
            env[variable.name.lower()] = variable
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=variable,
                kind=SymbolKind.PARAMETER,
                type_graph=self.type_graph,
            )
        for variable in locals_:
            env[variable.name.lower()] = variable
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=variable,
                kind=SymbolKind.LOCAL,
                type_graph=self.type_graph,
            )

        param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]] = {}
        for parameter_mapping in instance.parametermappings or []:
            target_name = varname_base(parameter_mapping.target)
            if not target_name or parameter_mapping.is_source_global:
                continue
            target_display_name = (
                parameter_mapping.target[const.KEY_VAR_NAME]
                if isinstance(parameter_mapping.target, dict) and const.KEY_VAR_NAME in parameter_mapping.target
                else str(parameter_mapping.target)
            )
            target_key = target_name.casefold()

            if target_key not in param_keys:
                self.issues.append(
                    VariableIssue(
                        kind=IssueKind.UNKNOWN_PARAMETER_TARGET,
                        module_path=module_path.copy(),
                        variable=None,
                        role=(f"unknown parameter mapping target " f"{target_display_name!r}"),
                    )
                )
                continue

            if parent_context is None:
                continue

            if isinstance(parameter_mapping.source, dict) and const.KEY_VAR_NAME in parameter_mapping.source:
                full_source = parameter_mapping.source[const.KEY_VAR_NAME]
            elif isinstance(parameter_mapping.source, str):
                full_source = parameter_mapping.source
            else:
                continue

            source_var, source_field_prefix, source_decl_path, source_decl_display_path = (
                parent_context.resolve_variable(full_source)
            )
            if source_var:
                param_mappings[target_key] = (
                    source_var,
                    source_field_prefix,
                    source_decl_path,
                    source_decl_display_path,
                )

        return ScopeContext(
            env=env,
            param_mappings=param_mappings,
            module_path=module_path,
            display_module_path=display_module_path,
            current_library=parent_context.current_library if parent_context else None,
            parent_context=parent_context,
        )
