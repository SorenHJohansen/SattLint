"""Builder for ScopeContexts with variable resolution and symbol registration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sattline_parser.models.ast_model import BasePicture, FrameModule, ModuleTypeInstance, SingleModule, Variable

from ..models._variable_issues import IssueKind, VariableIssue
from ._alias_utils import varname_base, varname_full
from ._moduletype_resolution import resolve_moduletype_def_strict
from .paths import decorate_segment
from .scope import ScopeContext
from .symbol_table import SymbolKind

if TYPE_CHECKING:
    from sattline_parser.models.ast_model import ModuleTypeDef

    from .symbol_table import CanonicalSymbolTable
    from .type_graph import TypeGraph


@dataclass(frozen=True)
class _TypedefContextTemplate:
    env: dict[str, Variable]
    moduleparameter_keys: frozenset[str]
    param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]]
    name_collisions: tuple[tuple[Variable, Variable], ...]
    unknown_parameter_targets: tuple[str, ...]


def find_var_in_scope(bp: BasePicture, instance_path: list[str], var_name: str) -> Variable | None:
    return ContextBuilder.resolve_variable_in_scope(bp, instance_path, var_name)


class ContextBuilder:
    def __init__(
        self,
        base_picture: BasePicture,
        symbol_table: CanonicalSymbolTable,
        type_graph: TypeGraph,
        issues: list[VariableIssue],
        global_lookup_fn: Callable[[str | None], Variable | None],
        root_library: str | None = None,
    ):
        self.bp = base_picture
        self.symbol_table = symbol_table
        self.type_graph = type_graph
        self.issues = issues
        self.global_lookup_fn = global_lookup_fn
        self.root_library = root_library if root_library is not None else getattr(base_picture, "origin_lib", None)
        self._typedef_context_cache: dict[tuple[object, ...], _TypedefContextTemplate] = {}

    def _typedef_mapping_signature(self, instance: ModuleTypeInstance) -> tuple[tuple[str, ...], ...]:
        signature: list[tuple[str, ...]] = []
        for parameter_mapping in instance.parametermappings or []:
            signature.append(
                (
                    (varname_full(parameter_mapping.target) or "").casefold(),
                    (parameter_mapping.source_type or "").casefold(),
                    (varname_full(parameter_mapping.source) or "").casefold(),
                    "1" if parameter_mapping.is_source_global else "0",
                    "1" if parameter_mapping.is_duration else "0",
                    ""
                    if parameter_mapping.source_literal is None
                    else str(parameter_mapping.source_literal).casefold(),
                )
            )
        return tuple(signature)

    def _typedef_context_cache_key(
        self,
        moduletype: ModuleTypeDef,
        instance: ModuleTypeInstance,
        parent_context: ScopeContext | None,
    ) -> tuple[object, ...]:
        parent_key = (
            () if parent_context is None else tuple(segment.casefold() for segment in parent_context.module_path)
        )
        return (
            moduletype.name.casefold(),
            parent_key,
            self._typedef_mapping_signature(instance),
            None
            if parent_context is None
            else parent_context.current_library.casefold()
            if parent_context.current_library
            else None,
        )

    @staticmethod
    def resolve_variable_in_scope(
        base_picture: BasePicture,
        instance_path: list[str],
        var_name: str,
        *,
        root_library: str | None = None,
    ) -> Variable | None:
        if not var_name:
            return None

        context = ScopeContext(
            env={variable.name.casefold(): variable for variable in base_picture.localvariables or []},
            param_mappings={},
            module_path=[base_picture.header.name],
            display_module_path=[decorate_segment(base_picture.header.name, "BP")],
            current_library=root_library if root_library is not None else getattr(base_picture, "origin_lib", None),
            parent_context=None,
        )
        if not instance_path:
            return context.resolve_global_name(var_name)[0]

        raw_segments = list(instance_path)
        if raw_segments and raw_segments[0].casefold() == base_picture.header.name.casefold():
            raw_segments = raw_segments[1:]

        current_node: BasePicture | SingleModule | FrameModule | ModuleTypeDef = base_picture
        for segment in raw_segments[:-1]:
            child = ContextBuilder._find_child_node(base_picture, current_node, segment, context.current_library)
            if child is None:
                return None

            if isinstance(child, SingleModule):
                context = ScopeContext(
                    env={
                        variable.name.casefold(): variable
                        for variable in [*list(child.moduleparameters or []), *list(child.localvariables or [])]
                    },
                    param_mappings={},
                    module_path=[*context.module_path, child.header.name],
                    display_module_path=[*context.display_module_path, decorate_segment(child.header.name, "SM")],
                    moduleparameter_keys=frozenset(
                        variable.name.casefold() for variable in child.moduleparameters or []
                    ),
                    current_library=context.current_library,
                    parent_context=context,
                )
                current_node = child
                continue

            if isinstance(child, FrameModule):
                current_node = child
                continue

            typedef = ContextBuilder._resolve_instance_typedef(base_picture, child, context.current_library)
            if typedef is None:
                return None
            context = ScopeContext(
                env={
                    variable.name.casefold(): variable
                    for variable in [*list(typedef.moduleparameters or []), *list(typedef.localvariables or [])]
                },
                param_mappings={},
                module_path=[*context.module_path, child.header.name],
                display_module_path=[
                    *context.display_module_path,
                    decorate_segment(child.header.name, "MT", child.moduletype_name),
                ],
                moduleparameter_keys=frozenset(variable.name.casefold() for variable in typedef.moduleparameters or []),
                current_library=typedef.origin_lib or context.current_library,
                parent_context=context,
            )
            current_node = typedef

        return context.resolve_global_name(var_name)[0]

    @staticmethod
    def _find_child_node(
        base_picture: BasePicture,
        current_node: BasePicture | SingleModule | FrameModule | ModuleTypeDef,
        segment: str,
        current_library: str | None,
    ) -> SingleModule | FrameModule | ModuleTypeInstance | None:
        children = list(current_node.submodules or [])
        wanted = segment.casefold()
        for child in children:
            if child.header.name.casefold() == wanted:
                return child
        return None

    @staticmethod
    def _resolve_instance_typedef(
        base_picture: BasePicture,
        instance: ModuleTypeInstance,
        current_library: str | None,
    ) -> ModuleTypeDef | None:
        try:
            return resolve_moduletype_def_strict(
                base_picture,
                instance.moduletype_name,
                current_library=current_library,
            )
        except ValueError:
            return None

    def _emit_typedef_context_issues(
        self,
        template: _TypedefContextTemplate,
        module_path: list[str],
    ) -> None:
        for parameter, local_variable in template.name_collisions:
            self.issues.append(
                VariableIssue(
                    kind=IssueKind.NAME_COLLISION,
                    module_path=module_path.copy(),
                    variable=local_variable,
                    role=f"name collision with parameter {parameter.name!r}",
                    source_variable=parameter,
                )
            )

        for target_display_name in template.unknown_parameter_targets:
            self.issues.append(
                VariableIssue(
                    kind=IssueKind.UNKNOWN_PARAMETER_TARGET,
                    module_path=module_path.copy(),
                    variable=None,
                    role=f"unknown parameter mapping target {target_display_name!r}",
                )
            )

    def _register_typedef_variables(self, moduletype: ModuleTypeDef, module_path: list[str]) -> None:
        for variable in moduletype.moduleparameters or []:
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=variable,
                kind=SymbolKind.PARAMETER,
                type_graph=self.type_graph,
            )
        for variable in moduletype.localvariables or []:
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=variable,
                kind=SymbolKind.LOCAL,
                type_graph=self.type_graph,
            )

    def _build_typedef_context_template(
        self,
        moduletype: ModuleTypeDef,
        instance: ModuleTypeInstance,
        parent_context: ScopeContext | None,
    ) -> _TypedefContextTemplate:
        env: dict[str, Variable] = {}
        params = list(moduletype.moduleparameters or [])
        locals_ = list(moduletype.localvariables or [])

        param_keys = {variable.name.casefold(): variable for variable in params}
        local_keys = {variable.name.casefold(): variable for variable in locals_}
        name_collisions = tuple(
            (param_keys[key], local_keys[key]) for key in sorted(set(param_keys.keys()) & set(local_keys.keys()))
        )

        for variable in params:
            env[variable.name.lower()] = variable
        for variable in locals_:
            env[variable.name.lower()] = variable

        param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]] = {}
        unknown_parameter_targets: list[str] = []
        for parameter_mapping in instance.parametermappings or []:
            target_name = varname_base(parameter_mapping.target)
            if not target_name or parameter_mapping.is_source_global:
                continue
            target_display_name = varname_full(parameter_mapping.target) or "<unknown>"
            target_key = target_name.casefold()

            if target_key not in param_keys:
                unknown_parameter_targets.append(target_display_name)
                continue

            if parent_context is None:
                continue

            full_source = varname_full(parameter_mapping.source)
            if not full_source:
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

        return _TypedefContextTemplate(
            env=env,
            moduleparameter_keys=frozenset(param_keys.keys()),
            param_mappings=param_mappings,
            name_collisions=name_collisions,
            unknown_parameter_targets=tuple(unknown_parameter_targets),
        )

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
            moduleparameter_keys=frozenset(),
            current_library=self.root_library,
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
            target_display_name = varname_full(parameter_mapping.target) or "<unknown>"
            target_key = target_name.casefold()

            if target_key not in param_keys:
                self.issues.append(
                    VariableIssue(
                        kind=IssueKind.UNKNOWN_PARAMETER_TARGET,
                        module_path=module_path.copy(),
                        variable=None,
                        role=(f"unknown parameter mapping target {target_display_name!r}"),
                    )
                )
                continue

            full_source = varname_full(parameter_mapping.source)
            if not full_source:
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
            moduleparameter_keys=frozenset(param_keys.keys()),
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
        module_path = module_path or []
        display_module_path = display_module_path or []

        cache_key = self._typedef_context_cache_key(moduletype, instance, parent_context)
        template = self._typedef_context_cache.get(cache_key)
        if template is None:
            template = self._build_typedef_context_template(moduletype, instance, parent_context)
            self._typedef_context_cache[cache_key] = template

        self._emit_typedef_context_issues(template, module_path)
        self._register_typedef_variables(moduletype, module_path)

        return ScopeContext(
            env=template.env,
            param_mappings=template.param_mappings,
            module_path=module_path,
            display_module_path=display_module_path,
            moduleparameter_keys=template.moduleparameter_keys,
            current_library=parent_context.current_library if parent_context else None,
            parent_context=parent_context,
        )
