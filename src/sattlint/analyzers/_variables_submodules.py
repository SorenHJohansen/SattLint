"""Submodule traversal helpers for variable analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sattline_parser.models.ast_model import (
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    SingleModule,
)

from ..casefolding import is_anytype_name
from ..grammar import constants as const
from ..reporting.variables_report import IssueKind, VariableIssue
from ..resolution import decorate_segment
from ..resolution.common import path_startswith_casefold, resolve_moduletype_def_strict, varname_base
from ..resolution.scope import ScopeContext

if TYPE_CHECKING:
    from .variables import VariablesAnalyzer


def _should_walk_submodule_path(self: VariablesAnalyzer, child_path: list[str]) -> bool:
    if self._limit_to_module_path is None:
        return True
    return path_startswith_casefold(self._limit_to_module_path, child_path) or path_startswith_casefold(
        child_path, self._limit_to_module_path
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
    if isinstance(child, ModuleTypeInstance):
        return [
            *parent_context.display_module_path,
            decorate_segment(child_name, "MT", moduletype_name=child.moduletype_name),
        ]
    return [*parent_context.display_module_path, child_name]


def _walk_submodule_headers(
    self: VariablesAnalyzer,
    child: SingleModule | FrameModule | ModuleTypeInstance,
    inst_context: ScopeContext,
    child_path: list[str],
) -> None:
    self._walk_header_enable(child.header, inst_context, path=child_path)
    self._walk_header_invoke_tails(child.header, inst_context, path=child_path)
    self._walk_header_groupconn(child.header, inst_context, path=child_path)


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

    self._walk_moduledef(child.moduledef, child_context, child_path)
    self._walk_module_code(child.modulecode, child_context, child_path)
    self._walk_submodules(child.submodules or [], child_context, child_path)

    used_reads = {
        variable.name.lower() for variable in (child.moduleparameters or []) if self._get_usage(variable).read
    }
    used_writes = {
        variable.name.lower() for variable in (child.moduleparameters or []) if self._get_usage(variable).written
    }

    for mapping in child.parametermappings or []:
        source_name = varname_base(mapping.source)
        target_name = varname_base(mapping.target)

        if source_name and target_name and not mapping.is_source_global:
            if isinstance(mapping.source, dict) and const.KEY_VAR_NAME in mapping.source:
                full_source_name = mapping.source[const.KEY_VAR_NAME]
            elif isinstance(mapping.source, str):
                full_source_name = mapping.source
            else:
                continue

            source_var, source_field_prefix, _decl_path, _decl_disp = parent_context.resolve_variable(full_source_name)
            target_var = child_context.env.get(target_name.casefold())

            if source_var and target_var:
                mapping_name = source_field_prefix or ""
                self._alias_links.append((source_var, target_var, mapping_name))

    for mapping in child.parametermappings or []:
        self._propagate_mapping_to_parent(
            mapping,
            child_used_reads=used_reads,
            child_used_writes=used_writes,
            parent_env=parent_context.env,
            parent_path=parent_path,
            external_typename=None,
            parent_context=parent_context,
            child_context=child_context,
        )

    self._check_param_mappings_for_single(
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
    frame_context = self._repath_context(
        parent_context,
        module_path=child_path,
        display_module_path=child_display_path,
    )
    self._walk_moduledef(child.moduledef, frame_context, child_path)
    self._walk_module_code(child.modulecode, frame_context, child_path)
    self._walk_submodules(child.submodules or [], frame_context, child_path)


def _walk_moduletype_instance_subtree(
    self: VariablesAnalyzer,
    child: ModuleTypeInstance,
    parent_context: ScopeContext,
    parent_path: list[str],
    child_path: list[str],
    child_display_path: list[str],
) -> None:
    child_name = child.header.name
    external = self._is_external_typename(child.moduletype_name)
    moduletype: ModuleTypeDef | None = None

    if not external:
        try:
            moduletype = resolve_moduletype_def_strict(
                self.bp,
                child.moduletype_name,
                current_library=parent_context.current_library,
                unavailable_libraries=self._unavailable_libraries,
            )
        except ValueError:
            moduletype = None
            external = True

    if external and not self._analyzed_target_is_library:
        return

    if moduletype is not None and not self._is_from_root_origin(getattr(moduletype, "origin_file", None)):
        if not self._analyzed_target_is_library and not self._include_dependency_moduletype_usage:
            self._check_param_mappings_for_type_instance(
                child,
                parent_env=parent_context.env,
                parent_path=[*parent_path, child_name],
                current_library=parent_context.current_library,
            )
            return
        if self._analyzed_target_is_library and not self._include_dependency_moduletype_usage:
            moduletype = None
            external = True

    reads: set[str] | None = None
    writes: set[str] | None = None
    typedef_context: ScopeContext | None = None

    if moduletype:
        mt_key = child.moduletype_name.lower()
        typedef_context = self.context_builder.build_for_typedef(
            moduletype,
            child,
            parent_context,
            module_path=child_path,
            display_module_path=child_display_path,
        )

        if mt_key not in self.param_reads_by_typedef and mt_key not in self._analyzing_typedefs:
            self._analyze_typedef_with_context(moduletype, typedef_context, path=child_path)

        for mapping in child.parametermappings or []:
            source_name = varname_base(mapping.source)
            target_name = varname_base(mapping.target)

            if source_name and target_name and not mapping.is_source_global:
                if isinstance(mapping.source, dict) and const.KEY_VAR_NAME in mapping.source:
                    full_source_name = mapping.source[const.KEY_VAR_NAME]
                elif isinstance(mapping.source, str):
                    full_source_name = mapping.source
                else:
                    continue

                source_var, source_field_prefix, _decl_path, _decl_disp = parent_context.resolve_variable(
                    full_source_name
                )
                target_var = typedef_context.env.get(target_name.casefold())

                if source_var and target_var:
                    mapping_name = source_field_prefix or ""
                    self._alias_links.append((source_var, target_var, mapping_name))

        reads = self.param_reads_by_typedef.get(mt_key, set())
        writes = self.param_writes_by_typedef.get(mt_key, set())

    for mapping in child.parametermappings or []:
        self._propagate_mapping_to_parent(
            mapping,
            child_used_reads=reads,
            child_used_writes=writes,
            parent_env=parent_context.env,
            parent_path=parent_path,
            external_typename=(child.moduletype_name if external else None),
            parent_context=parent_context,
            child_context=typedef_context,
        )

    if moduletype is not None:
        self._check_param_mappings_for_type_instance(
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
        if not self._should_walk_submodule_path(child_path):
            continue

        child_display_path = self._display_path_for_child(child, parent_context)
        inst_context = self._repath_context(
            parent_context,
            module_path=child_path,
            display_module_path=child_display_path,
        )
        self._walk_submodule_headers(child, inst_context, child_path)

        if isinstance(child, SingleModule):
            self._walk_singlemodule_subtree(child, parent_context, parent_path, child_path, child_display_path)
        elif isinstance(child, FrameModule):
            self._walk_framemodule_subtree(child, parent_context, child_path, child_display_path)
        elif isinstance(child, ModuleTypeInstance):
            self._walk_moduletype_instance_subtree(child, parent_context, parent_path, child_path, child_display_path)


def _propagate_mapping_to_parent(
    self: VariablesAnalyzer,
    pm,
    child_used_reads: set[str] | None,
    child_used_writes: set[str] | None,
    parent_env,
    parent_path,
    external_typename,
    parent_context: ScopeContext | None = None,
    child_context: ScopeContext | None = None,
) -> None:
    self._effect_flow_tracker.propagate_mapping_to_parent(
        pm,
        child_used_reads,
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
    env,
):
    if isinstance(var_dict_or_other, dict) and const.KEY_VAR_NAME in var_dict_or_other:
        base = varname_base(var_dict_or_other)
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
        if not self._is_from_root_origin(getattr(moduletype, "origin_file", None)):
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
        duplicate_locs = [(path, role, variable.name) for variable, path, role in occurrences[1:]]

        self._append_issue(
            VariableIssue(
                kind=IssueKind.DATATYPE_DUPLICATION,
                module_path=first_path,
                variable=first_var,
                role=first_role,
                duplicate_count=len(occurrences),
                duplicate_locations=duplicate_locs,
            )
        )
