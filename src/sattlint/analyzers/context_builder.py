"""Builder for ScopeContexts with variable resolution and symbol registration."""
from __future__ import annotations
from typing import Callable, TYPE_CHECKING
from ..grammar import constants as const
from ..resolution.scope import ScopeContext
from ..resolution import SymbolKind, decorate_segment
from ..resolution.common import varname_base
from ..reporting.variables_report import IssueKind, VariableIssue

if TYPE_CHECKING:
    from ..models.ast_model import BasePicture, ModuleTypeDef, SingleModule, ModuleTypeInstance, Variable
    from ..resolution import CanonicalSymbolTable, TypeGraph

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
        for v in self.bp.localvariables or []:
            env[v.name.lower()] = v

        module_path = [self.bp.header.name]
        display_path = [decorate_segment(self.bp.header.name, "BP")]

        for v in self.bp.localvariables or []:
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=v,
                kind=SymbolKind.LOCAL,
                type_graph=self.type_graph,
            )

        return ScopeContext(
            env=env,
            param_mappings={},
            module_path=module_path,
            display_module_path=display_path,
            current_library=getattr(self.bp, "origin_lib", None),
            parent_context=None
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

        # Add module parameters and locals
        params = list(mod.moduleparameters or [])
        locals_ = list(mod.localvariables or [])

        param_keys = {v.name.casefold(): v for v in params}
        local_keys = {v.name.casefold(): v for v in locals_}
        for k in (set(param_keys.keys()) & set(local_keys.keys())):
            p = param_keys[k]
            lv = local_keys[k]
            self.issues.append(
                VariableIssue(
                    kind=IssueKind.NAME_COLLISION,
                    module_path=module_path.copy(),
                    variable=lv,
                    role=f"name collision with parameter {p.name!r}",
                    source_variable=p,
                )
            )

        for v in params:
            env[v.name.lower()] = v
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=v,
                kind=SymbolKind.PARAMETER,
                type_graph=self.type_graph,
            )
        for v in locals_:
            env[v.name.lower()] = v
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=v,
                kind=SymbolKind.LOCAL,
                type_graph=self.type_graph,
            )

        # Build parameter mappings with field prefixes
        param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]] = {}

        for pm in mod.parametermappings or []:
            target_name = varname_base(pm.target)
            if not target_name or pm.is_source_global:
                continue

            # Extract full source reference (e.g., "Dv.I.WT001")
            if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                full_source = pm.source[const.KEY_VAR_NAME]
            elif isinstance(pm.source, str):
                full_source = pm.source
            else:
                continue

            # Resolve source variable from parent context
            source_var, source_field_prefix, source_decl_path, source_decl_display_path = parent_context.resolve_variable(full_source)

            if source_var:
                # Store mapping: parameter name -> (actual variable, field prefix)
                param_mappings[target_name.lower()] = (
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
            parent_context=parent_context
        )

    def build_for_typedef(
        self,
        mt: ModuleTypeDef,
        instance: ModuleTypeInstance,
        parent_context: ScopeContext | None = None,
        module_path: list[str] | None = None,
        display_module_path: list[str] | None = None,
    ) -> ScopeContext:
        """Build scope context for a typedef instance with parameter mappings."""
        env: dict[str, Variable] = {}

        module_path = module_path or []
        display_module_path = display_module_path or []

        # Add typedef's parameters and locals
        params = list(mt.moduleparameters or [])
        locals_ = list(mt.localvariables or [])

        param_keys = {v.name.casefold(): v for v in params}
        local_keys = {v.name.casefold(): v for v in locals_}
        for k in (set(param_keys.keys()) & set(local_keys.keys())):
            p = param_keys[k]
            lv = local_keys[k]
            self.issues.append(
                VariableIssue(
                    kind=IssueKind.NAME_COLLISION,
                    module_path=module_path.copy(),
                    variable=lv,
                    role=f"name collision with parameter {p.name!r}",
                    source_variable=p,
                )
            )

        for v in params:
            env[v.name.lower()] = v
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=v,
                kind=SymbolKind.PARAMETER,
                type_graph=self.type_graph,
            )
        for v in locals_:
            env[v.name.lower()] = v
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=v,
                kind=SymbolKind.LOCAL,
                type_graph=self.type_graph,
            )

        # Map instance parameters to parent variables
        param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]] = {}
        for pm in instance.parametermappings or []:
            target_name = varname_base(pm.target)
            if not target_name or pm.is_source_global:
                continue

            if parent_context:
                # Allow full dotted source mapping for partial transfers
                if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                    full_source = pm.source[const.KEY_VAR_NAME]
                elif isinstance(pm.source, str):
                    full_source = pm.source
                else:
                    full_source = None

                if full_source:
                    source_var, source_field_prefix, source_decl_path, source_decl_display_path = parent_context.resolve_variable(full_source)
                    if source_var:
                        param_mappings[target_name.lower()] = (
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
            current_library=mt.origin_lib or (parent_context.current_library if parent_context else None),
            parent_context=parent_context
        )
