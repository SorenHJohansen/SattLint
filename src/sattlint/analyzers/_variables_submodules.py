"""Submodule traversal helpers for variable analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from sattline_parser.models.ast_model import (
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    SingleModule,
    Variable,
)

from ..casefolding import is_anytype_name
from ..grammar import constants as const
from ..reporting.variables_report import IssueKind, VariableIssue
from ..resolution import decorate_segment
from ..resolution.common import path_startswith_casefold, resolve_moduletype_def_strict, varname_base, varname_full
from ..resolution.scope import ScopeContext
from ..types import VariableId
from .variable_utils import external_mapping_usage

if TYPE_CHECKING:
    from .variables import VariablesAnalyzer


def _maybe_update_status(self: object, detail: str) -> None:
    update_status = getattr(self, "_update_status", None)
    if callable(update_status):
        update_status(detail)


def _mapping_target_name(mapping: ParameterMapping) -> str | None:
    return varname_base(cast(Any, mapping).target)


def _mapping_source_full_ref(mapping: ParameterMapping) -> str | None:
    return varname_full(cast(Any, mapping).source)


def _should_walk_submodule_path(self: VariablesAnalyzer, child_path: list[str]) -> bool:
    if self.limit_to_module_path is None:
        return True
    return path_startswith_casefold(self.limit_to_module_path, child_path) or path_startswith_casefold(
        child_path, self.limit_to_module_path
    )


def _display_path_for_child(
    self: VariablesAnalyzer,
    child: SingleModule | FrameModule | ModuleTypeInstance,
    parent_context: ScopeContext,
) -> list[str]:
    child_name = child.header.name
    if isinstance(child, SingleModule):
        return [*parent_context.display_module_path, decorate_segment(child_name, "SM")]
    if isinstance(child, FrameModule):
        return [*parent_context.display_module_path, decorate_segment(child_name, "FM")]
    return [
        *parent_context.display_module_path,
        decorate_segment(child_name, "MT", moduletype_name=child.moduletype_name),
    ]


def _walk_submodule_headers(
    self: VariablesAnalyzer,
    child: SingleModule | FrameModule | ModuleTypeInstance,
    inst_context: ScopeContext,
    child_path: list[str],
) -> None:
    self.walk_header_enable(child.header, inst_context, path=child_path)
    self.walk_header_invoke_tails(child.header, inst_context, path=child_path)
    self.walk_header_groupconn(child.header, inst_context, path=child_path)


def _walk_singlemodule_subtree(
    self: VariablesAnalyzer,
    child: SingleModule,
    parent_context: ScopeContext,
    parent_path: list[str],
    child_path: list[str],
    child_display_path: list[str],
) -> None:
    child_context = self.context_builder.build_for_single(
        child,
        parent_context,
        module_path=child_path,
        display_module_path=child_display_path,
    )
    self.contexts_by_module_path[tuple(child_path)] = child_context

    self.walk_moduledef(child.moduledef, child_context, child_path)
    self.walk_module_code(child.modulecode, child_context, child_path)
    _walk_submodules(self, child.submodules or [], child_context, child_path)

    used_reads = {variable.name.lower() for variable in (child.moduleparameters or []) if self.get_usage(variable).read}
    used_ui_reads = {
        variable.name.lower() for variable in (child.moduleparameters or []) if self.get_usage(variable).ui_read
    }
    used_non_ui_reads = {
        variable.name.lower() for variable in (child.moduleparameters or []) if self.get_usage(variable).non_ui_read
    }
    used_writes = {
        variable.name.lower() for variable in (child.moduleparameters or []) if self.get_usage(variable).written
    }

    for mapping in child.parametermappings or []:
        full_source_name = _mapping_source_full_ref(mapping)
        source_name = varname_base(full_source_name) if full_source_name is not None else None
        target_name = _mapping_target_name(mapping)
        resolve_variable = getattr(parent_context, "resolve_variable", None)

        if full_source_name is None:
            continue
        if source_name and target_name and not mapping.is_source_global and callable(resolve_variable):
            source_var, source_field_prefix, _decl_path, _decl_disp = parent_context.resolve_variable(full_source_name)
            target_var = child_context.env.get(target_name.casefold())

            if source_var and target_var:
                mapping_name = source_field_prefix or ""
                self.alias_links.append((source_var, target_var, mapping_name))

    for mapping in child.parametermappings or []:
        _propagate_mapping_to_parent(
            self,
            mapping,
            child_used_reads=used_reads,
            child_ui_reads=used_ui_reads,
            child_non_ui_reads=used_non_ui_reads,
            child_used_writes=used_writes,
            parent_env=parent_context.env,
            parent_path=parent_path,
            external_typename=None,
            parent_context=parent_context,
            child_context=child_context,
        )

    self.check_param_mappings_for_single(
        child,
        child_env=child_context.env,
        parent_env=parent_context.env,
        parent_path=child_path,
    )


def _walk_framemodule_subtree(
    self: VariablesAnalyzer,
    child: FrameModule,
    parent_context: ScopeContext,
    child_path: list[str],
    child_display_path: list[str],
) -> None:
    frame_context = self.repath_context(
        parent_context,
        module_path=child_path,
        display_module_path=child_display_path,
    )
    self.contexts_by_module_path[tuple(child_path)] = frame_context
    self.walk_moduledef(child.moduledef, frame_context, child_path)
    self.walk_module_code(child.modulecode, frame_context, child_path)
    _walk_submodules(self, child.submodules or [], frame_context, child_path)


def _walk_moduletype_instance_subtree(
    self: VariablesAnalyzer,
    child: ModuleTypeInstance,
    parent_context: ScopeContext,
    parent_path: list[str],
    child_path: list[str],
    child_display_path: list[str],
) -> None:
    child_name = child.header.name
    external = self.is_external_typename(child.moduletype_name)
    moduletype: ModuleTypeDef | None = None

    if not external:
        try:
            moduletype = resolve_moduletype_def_strict(
                self.bp,
                child.moduletype_name,
                current_library=parent_context.current_library,
                unavailable_libraries=self.unavailable_libraries,
            )
        except ValueError:
            moduletype = None
            external = True

    reads: set[str] | None = None
    ui_reads: set[str] | None = None
    non_ui_reads: set[str] | None = None
    writes: set[str] | None = None
    typedef_context: ScopeContext | None = None
    dependency_owned_moduletype = False

    if moduletype is not None and not self.is_from_root_origin(
        getattr(moduletype, "origin_file", None),
        getattr(moduletype, "origin_lib", None),
    ):
        dependency_owned_moduletype = True
        if self.analyzed_target_is_library and not self.include_dependency_moduletype_usage:
            moduletype = None
            external = True

    if moduletype:
        mt_key = child.moduletype_name.lower()
        typedef_context = self.context_builder.build_for_typedef(
            moduletype,
            child,
            parent_context,
            module_path=child_path,
            display_module_path=child_display_path,
        )
        self.contexts_by_module_path[tuple(child_path)] = typedef_context

        if mt_key not in self.param_reads_by_typedef and mt_key not in self.analyzing_typedefs:
            self.analyze_typedef_with_context(moduletype, typedef_context, path=child_path)

        for mapping in child.parametermappings or []:
            full_source_name = _mapping_source_full_ref(mapping)
            source_name = varname_base(full_source_name) if full_source_name is not None else None
            target_name = _mapping_target_name(mapping)
            resolve_variable = getattr(parent_context, "resolve_variable", None)

            if full_source_name is None:
                continue
            if source_name and target_name and not mapping.is_source_global and callable(resolve_variable):
                source_var, source_field_prefix, _decl_path, _decl_disp = parent_context.resolve_variable(
                    full_source_name
                )
                target_var = typedef_context.env.get(target_name.casefold())

                if source_var and target_var:
                    mapping_name = source_field_prefix or ""
                    self.alias_links.append((source_var, target_var, mapping_name))

        reads = self.param_reads_by_typedef.get(mt_key, set())
        ui_reads = self.param_ui_reads_by_typedef.get(mt_key, set())
        non_ui_reads = self.param_non_ui_reads_by_typedef.get(mt_key, set())
        writes = self.param_writes_by_typedef.get(mt_key, set())

    for mapping in child.parametermappings or []:
        full_source_name = _mapping_source_full_ref(mapping)
        target_name = _mapping_target_name(mapping)
        mapping_reads = reads
        mapping_writes = writes
        known_external_usage = external_mapping_usage(child.moduletype_name, target_name) if external else None
        needs_dependency_field_propagation = (
            dependency_owned_moduletype and full_source_name is not None and "." in full_source_name
        )
        if known_external_usage is not None and target_name is not None:
            reads_from_source, writes_to_source = known_external_usage
            mapping_reads = set(reads or set())
            mapping_writes = set(writes or set())
            if reads_from_source:
                mapping_reads.add(target_name)
            if writes_to_source:
                mapping_writes.add(target_name)
        _propagate_mapping_to_parent(
            self,
            mapping,
            child_used_reads=mapping_reads,
            child_ui_reads=ui_reads,
            child_non_ui_reads=non_ui_reads,
            child_used_writes=mapping_writes,
            parent_env=parent_context.env,
            parent_path=parent_path,
            external_typename=(
                child.moduletype_name
                if (external or needs_dependency_field_propagation) and known_external_usage is None
                else None
            ),
            parent_context=parent_context,
            child_context=typedef_context,
        )

    if moduletype is not None:
        self.check_param_mappings_for_type_instance(
            child,
            parent_env=parent_context.env,
            parent_path=[*parent_path, child_name],
            current_library=parent_context.current_library,
        )


def _walk_submodules(
    self: VariablesAnalyzer,
    children: list[SingleModule | FrameModule | ModuleTypeInstance],
    parent_context: ScopeContext,
    parent_path: list[str],
) -> None:
    for child in children:
        child_name = child.header.name
        child_path = [*parent_path, child_name]
        if not _should_walk_submodule_path(self, child_path):
            continue

        if getattr(self, "debug", False):
            display_path = " > ".join(child_path[-4:])
            if len(child_path) > 4:
                display_path = f"... > {display_path}"
            _maybe_update_status(self, f"walking module path {display_path}")

        child_display_path = _display_path_for_child(self, child, parent_context)
        inst_context = self.repath_context(
            parent_context,
            module_path=child_path,
            display_module_path=child_display_path,
        )
        _walk_submodule_headers(self, child, inst_context, child_path)

        if isinstance(child, SingleModule):
            _walk_singlemodule_subtree(self, child, parent_context, parent_path, child_path, child_display_path)
        elif isinstance(child, FrameModule):
            _walk_framemodule_subtree(self, child, parent_context, child_path, child_display_path)
        else:
            _walk_moduletype_instance_subtree(self, child, parent_context, parent_path, child_path, child_display_path)


def _propagate_mapping_to_parent(
    self: VariablesAnalyzer,
    pm: ParameterMapping,
    child_used_reads: set[str] | None,
    child_ui_reads: set[str] | None,
    child_non_ui_reads: set[str] | None,
    child_used_writes: set[str] | None,
    parent_env: dict[str, Variable],
    parent_path: list[str],
    external_typename: str | None,
    parent_context: ScopeContext | None = None,
    child_context: ScopeContext | None = None,
) -> None:
    self.effect_flow_tracker.propagate_mapping_to_parent(
        pm,
        child_used_reads,
        child_ui_reads,
        child_non_ui_reads,
        child_used_writes,
        parent_env,
        parent_path,
        external_typename,
        parent_context,
        child_context,
    )


def _lookup_env_var_from_varname_dict(
    self: VariablesAnalyzer,
    var_dict_or_other: Any,
    env: dict[str, Variable],
) -> Variable | None:
    if isinstance(var_dict_or_other, dict) and const.KEY_VAR_NAME in var_dict_or_other:
        var_dict = cast(dict[str, object], var_dict_or_other)
        base = varname_base(var_dict)
        if base is not None:
            return env.get(base)
    return None


def _detect_datatype_duplications(self: VariablesAnalyzer) -> None:
    var_locations: list[tuple[Any, list[str], str]] = []

    bp_path = [self.bp.header.name]
    for variable in self.bp.localvariables or []:
        var_locations.append((variable, bp_path.copy(), "localvariable"))

    def _collect_from_module(mod: SingleModule | FrameModule | ModuleTypeInstance, path: list[str]) -> None:
        if isinstance(mod, SingleModule):
            my_path = [*path, mod.header.name]
            for variable in mod.moduleparameters or []:
                var_locations.append((variable, my_path.copy(), "moduleparameter"))
            for variable in mod.localvariables or []:
                var_locations.append((variable, my_path.copy(), "localvariable"))
            for child in mod.submodules or []:
                _collect_from_module(child, my_path)
        elif isinstance(mod, FrameModule):
            my_path = [*path, mod.header.name]
            for child in mod.submodules or []:
                _collect_from_module(child, my_path)

    for module in self.bp.submodules or []:
        _collect_from_module(module, bp_path)

    for moduletype in self.bp.moduletype_defs or []:
        if not self.is_from_root_origin(
            getattr(moduletype, "origin_file", None),
            getattr(moduletype, "origin_lib", None),
        ):
            continue
        td_path = [self.bp.header.name, f"TypeDef:{moduletype.name}"]
        for variable in moduletype.moduleparameters or []:
            var_locations.append((variable, td_path.copy(), "moduleparameter"))
        for variable in moduletype.localvariables or []:
            var_locations.append((variable, td_path.copy(), "localvariable"))

    complex_vars = [
        (variable, path, role)
        for variable, path, role in var_locations
        if not isinstance(variable.datatype, Simple_DataType) and not is_anytype_name(variable.datatype_text)
    ]

    by_datatype: dict[tuple[tuple[str, ...], str], list[tuple[Any, list[str], str]]] = {}
    for variable, path, role in complex_vars:
        datatype_key = variable.datatype_text.lower()
        scope_key = tuple(segment.casefold() for segment in path)
        by_datatype.setdefault((scope_key, datatype_key), []).append((variable, path, role))

    declared_record_names = {datatype.name.casefold() for datatype in self.bp.datatype_defs or []}
    for (_scope_key, datatype_name), occurrences in by_datatype.items():
        if len(occurrences) < 2:
            continue
        if datatype_name in declared_record_names:
            continue

        first_var, first_path, first_role = occurrences[0]
        duplicate_locs = [(path, role, VariableId(variable.name)) for variable, path, role in occurrences[1:]]

        self.append_issue(
            VariableIssue(
                kind=IssueKind.DATATYPE_DUPLICATION,
                module_path=first_path,
                variable=first_var,
                role=first_role,
                duplicate_count=len(occurrences),
                duplicate_locations=duplicate_locs,
            )
        )


detect_datatype_duplications = _detect_datatype_duplications
display_path_for_child = _display_path_for_child
lookup_env_var_from_varname_dict = _lookup_env_var_from_varname_dict
propagate_mapping_to_parent = _propagate_mapping_to_parent
should_walk_submodule_path = _should_walk_submodule_path
walk_framemodule_subtree = _walk_framemodule_subtree
walk_moduletype_instance_subtree = _walk_moduletype_instance_subtree
walk_singlemodule_subtree = _walk_singlemodule_subtree
walk_submodule_headers = _walk_submodule_headers
walk_submodules = _walk_submodules

__all__ = [
    "detect_datatype_duplications",
    "display_path_for_child",
    "lookup_env_var_from_varname_dict",
    "propagate_mapping_to_parent",
    "should_walk_submodule_path",
    "walk_framemodule_subtree",
    "walk_moduletype_instance_subtree",
    "walk_singlemodule_subtree",
    "walk_submodule_headers",
    "walk_submodules",
]
