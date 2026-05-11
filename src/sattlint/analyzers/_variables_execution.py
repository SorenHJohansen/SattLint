"""Execution and issue-collection helpers for variable analysis."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any, Protocol, cast

from sattline_parser.models.ast_model import (
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    SingleModule,
    Variable,
)
from sattlint.analyzers.layout_geometry import collect_layout_overlap_issues

from ..grammar import constants as const
from ..reporting.variables_report import IssueKind, VariableIssue
from ..resolution import decorate_segment
from ..resolution.common import varname_base
from ..resolution.scope import ScopeContext
from .reset_contamination import detect_implicit_latching, detect_reset_contamination

if TYPE_CHECKING:
    from .variables import VariablesAnalyzer


class _ModuleWithParameters(Protocol):
    @property
    def moduledef(self) -> Any: ...

    @property
    def modulecode(self) -> Any: ...

    @property
    def submodules(self) -> list[SingleModule | FrameModule | ModuleTypeInstance] | None: ...

    @property
    def moduleparameters(self) -> list[Variable] | None: ...


class _ParameterMappingTarget(Protocol):
    target: object


def _mapping_target_name(mapping: ParameterMapping) -> str | None:
    target = cast(_ParameterMappingTarget, mapping).target
    if isinstance(target, str):
        return varname_base(target)
    if isinstance(target, dict):
        target_dict = cast(dict[str, object], target)
        target_name = target_dict.get(const.KEY_VAR_NAME)
        if isinstance(target_name, str):
            return varname_base(target_name)
    return None


def _analyze_root_scope(self: VariablesAnalyzer) -> ScopeContext:
    root_context = self.context_builder.build_for_basepicture()
    self._trace("root-context-built", root_symbols=len(root_context.env))

    root_path = [self.bp.header.name]
    self._walk_module_code(self.bp.modulecode, root_context, path=root_path)
    self._walk_moduledef(self.bp.moduledef, root_context, path=root_path)
    self._walk_header_enable(self.bp.header, root_context, path=root_path)
    self._walk_header_invoke_tails(self.bp.header, root_context, path=root_path)
    self._walk_header_groupconn(self.bp.header, root_context, path=root_path)
    self._walk_submodules(self.bp.submodules or [], parent_context=root_context, parent_path=root_path)
    return root_context


def _run_post_traversal_analyses(self: VariablesAnalyzer) -> None:
    self._detect_datatype_duplications()
    issue_count_before_reset = len(self._issues)
    detect_reset_contamination(
        self.bp,
        self._issues,
        self._limit_to_module_path,
        debug=self.debug,
        trace_fn=self._trace,
    )
    self._trace(
        "reset-contamination-scan",
        added_issue_count=len(self._issues) - issue_count_before_reset,
    )
    issue_count_before_latch = len(self._issues)
    detect_implicit_latching(self.bp, self._issues, self._limit_to_module_path)
    self._trace(
        "implicit-latch-scan",
        added_issue_count=len(self._issues) - issue_count_before_latch,
    )
    layout_issues = collect_layout_overlap_issues(
        self.bp,
        limit_to_module_path=self._limit_to_module_path,
    )
    for issue in layout_issues:
        self._append_issue(issue)
    self._trace("layout-overlap-scan", added_issue_count=len(layout_issues))
    self._effective_output_keys = self._compute_effective_output_keys()


def _collect_basepicture_issues(self: VariablesAnalyzer, bp_path: list[str]) -> None:
    for variable in self.bp.localvariables or []:
        role = "localvariable"
        usage = self._get_usage(variable)
        if usage.is_unused:
            self._add_issue(IssueKind.UNUSED, bp_path, variable, role=role)
            continue
        procedure_status = self._procedure_status_issue(variable, usage)
        if procedure_status is not None:
            status_role, field_path = procedure_status
            self._add_issue(IssueKind.PROCEDURE_STATUS, bp_path, variable, role=status_role, field_path=field_path)
            continue
        if usage.is_display_only:
            self._add_issue(IssueKind.UI_ONLY, bp_path, variable, role=role)
        elif usage.is_read_only and not bool(variable.const) and self._is_const_candidate(variable):
            self._add_issue(IssueKind.READ_ONLY_NON_CONST, bp_path, variable, role=role)
        elif usage.written and not usage.read:
            self._add_issue(IssueKind.NEVER_READ, bp_path, variable, role=role)
        elif (
            usage.read
            and usage.written
            and not self._has_output_effect(variable, bp_path)
            and not self._has_procedure_status_binding(variable)
        ):
            self._add_issue(IssueKind.WRITE_WITHOUT_EFFECT, bp_path, variable, role=role)

    current_library = getattr(self.bp, "origin_lib", None)
    for module in self.bp.submodules or []:
        self._collect_issues_from_module(module, path=bp_path, current_library=current_library)


def _collect_typedef_issues(self: VariablesAnalyzer) -> None:
    if self._limit_to_module_path is not None:
        return

    for moduletype in self.bp.moduletype_defs or []:
        if not self._is_from_root_origin(
            getattr(moduletype, "origin_file", None),
            getattr(moduletype, "origin_lib", None),
        ):
            continue
        td_path = [self.bp.header.name, f"TypeDef:{moduletype.name}"]
        current_library = moduletype.origin_lib or getattr(self.bp, "origin_lib", None)

        self._analyze_typedef(moduletype, path=td_path)

        for variable in moduletype.moduleparameters or []:
            role = "moduleparameter"
            usage = self._get_usage(variable)
            if usage.is_unused:
                self._add_issue(IssueKind.UNUSED, td_path, variable, role=role)
                continue
            procedure_status = self._procedure_status_issue(variable, usage)
            if procedure_status is not None:
                status_role, field_path = procedure_status
                self._add_issue(IssueKind.PROCEDURE_STATUS, td_path, variable, role=status_role, field_path=field_path)
                continue
            if usage.is_display_only:
                self._add_issue(IssueKind.UI_ONLY, td_path, variable, role=role)
            elif (
                usage.read
                and usage.written
                and not self._has_output_effect(variable, td_path)
                and not self._has_procedure_status_binding(variable)
            ):
                self._add_issue(IssueKind.WRITE_WITHOUT_EFFECT, td_path, variable, role=role)

        for module in moduletype.submodules or []:
            self._collect_issues_from_module(module, path=td_path, current_library=current_library)

        for variable in moduletype.localvariables or []:
            role = "localvariable"
            usage = self._get_usage(variable)
            if usage.is_unused:
                self._add_issue(IssueKind.UNUSED, td_path, variable, role=role)
                continue
            procedure_status = self._procedure_status_issue(variable, usage)
            if procedure_status is not None:
                status_role, field_path = procedure_status
                self._add_issue(IssueKind.PROCEDURE_STATUS, td_path, variable, role=status_role, field_path=field_path)
                continue
            if usage.is_display_only:
                self._add_issue(IssueKind.UI_ONLY, td_path, variable, role=role)
            elif usage.is_read_only and not bool(variable.const) and self._is_const_candidate(variable):
                self._add_issue(IssueKind.READ_ONLY_NON_CONST, td_path, variable, role=role)
            elif usage.written and not usage.read:
                self._add_issue(IssueKind.NEVER_READ, td_path, variable, role=role)
            elif (
                usage.read
                and usage.written
                and not self._has_output_effect(variable, td_path)
                and not self._has_procedure_status_binding(variable)
            ):
                self._add_issue(IssueKind.WRITE_WITHOUT_EFFECT, td_path, variable, role=role)


def run(
    self: VariablesAnalyzer,
    apply_alias_back_propagation: bool = True,
    limit_to_module_path: list[str] | None = None,
) -> list[VariableIssue]:
    self._issues = []
    self.context_builder.issues = self._issues
    self._limit_to_module_path = limit_to_module_path
    self._trace(
        "start",
        basepicture_name=self.bp.header.name,
        localvariable_count=len(self.bp.localvariables or []),
        submodule_count=len(self.bp.submodules or []),
        moduletype_count=len(self.bp.moduletype_defs or []),
        apply_alias_back_propagation=apply_alias_back_propagation,
        limit_to_module_path=limit_to_module_path,
    )

    if self.debug:
        log = __import__("logging").getLogger("SattLint")
        log.debug(
            "Variables analysis start: %s locals=%d submodules=%d typedefs=%d",
            self.bp.header.name,
            len(self.bp.localvariables or []),
            len(self.bp.submodules or []),
            len(self.bp.moduletype_defs or []),
        )

    self._analyze_root_scope()

    if apply_alias_back_propagation:
        self._apply_alias_back_propagation()
        self._propagate_procedure_status_bindings()
        self._trace("alias-back-propagation", alias_link_count=len(self._alias_links))

    self._run_post_traversal_analyses()

    bp_path = [self.bp.header.name]
    self._collect_basepicture_issues(bp_path)
    self._collect_typedef_issues()

    self._add_naming_role_mismatch_issues()
    self._add_global_scope_minimization_issues()
    self._add_hidden_global_coupling_issues()
    self._add_high_fan_in_out_issues()
    self._add_unused_datatype_field_issues()
    issue_counts = dict(sorted(Counter(issue.kind.value for issue in self._issues).items()))
    self._trace(
        "complete",
        total_issue_count=len(self._issues),
        issue_counts=issue_counts,
        warning_count=len(self._analysis_warnings),
    )

    if self.debug:
        log = __import__("logging").getLogger("SattLint")
        log.debug("Variables analysis complete. Issues=%d", len(self._issues))

    return self._issues


def _is_external_typename(self: VariablesAnalyzer, typename: str) -> bool:
    return typename.lower() not in self.typedef_index


def _analyze_typedef(self: VariablesAnalyzer, mt: ModuleTypeDef, path: list[str]) -> None:
    mt_key = mt.name.lower()
    if mt_key in self._analyzing_typedefs:
        return

    self._analyzing_typedefs.add(mt_key)

    try:
        params = list(mt.moduleparameters or [])
        locals_ = list(mt.localvariables or [])

        param_keys = {variable.name.casefold(): variable for variable in params}
        local_keys = {variable.name.casefold(): variable for variable in locals_}
        for key in set(param_keys.keys()) & set(local_keys.keys()):
            parameter_var = param_keys[key]
            local_var = local_keys[key]
            self._append_issue(
                VariableIssue(
                    kind=IssueKind.NAME_COLLISION,
                    module_path=path.copy(),
                    variable=local_var,
                    role=f"name collision with parameter {parameter_var.name!r}",
                    source_variable=parameter_var,
                )
            )

        env = {variable.name.lower(): variable for variable in params}
        env.update({variable.name.lower(): variable for variable in locals_})

        display_path: list[str] = []
        if path:
            display_path.append(decorate_segment(path[0], "BP"))
            for segment in path[1:]:
                if segment.startswith("TypeDef:"):
                    display_path.append(decorate_segment(segment, "TD"))
                else:
                    display_path.append(segment)

        context = ScopeContext(
            env=env,
            param_mappings={},
            module_path=path.copy(),
            display_module_path=display_path,
            current_library=mt.origin_lib,
            parent_context=None,
        )

        self._walk_moduledef(mt.moduledef, context, path)
        self._walk_module_code(mt.modulecode, context, path)
        self._walk_submodules(mt.submodules or [], parent_context=context, parent_path=path)
        self._walk_typedef_groupconn(mt, context, path)

        used_reads = {
            variable.name.lower() for variable in (mt.moduleparameters or []) if self._get_usage(variable).read
        }
        used_writes = {
            variable.name.lower() for variable in (mt.moduleparameters or []) if self._get_usage(variable).written
        }

        used_params = used_reads | used_writes
        self.used_params_by_typedef[mt.name] = used_params
        self.param_reads_by_typedef[mt.name.lower()] = used_reads
        self.param_writes_by_typedef[mt.name.lower()] = used_writes

        for mapping in mt.parametermappings or []:
            target_name = _mapping_target_name(mapping)
            target_var = env.get(target_name) if target_name else None
            self._check_param_mapping(mapping, target_var, env, path)
    finally:
        self._analyzing_typedefs.discard(mt_key)


def _apply_alias_back_propagation(self: VariablesAnalyzer) -> None:
    for parent_var, child_var, field_prefix in self._alias_links:
        parent_usage = self._get_usage(parent_var)
        child_usage = self._get_usage(child_var)

        for field_path, locations in (child_usage.field_reads or {}).items():
            if field_prefix and field_path:
                full_field_path = f"{field_prefix}.{field_path}"
            elif field_prefix:
                full_field_path = field_prefix
            else:
                full_field_path = field_path

            for location in locations:
                parent_usage.mark_field_read(full_field_path, location)

        for field_path, locations in (child_usage.field_writes or {}).items():
            if field_prefix and field_path:
                full_field_path = f"{field_prefix}.{field_path}"
            elif field_prefix:
                full_field_path = field_prefix
            else:
                full_field_path = field_path

            for location in locations:
                parent_usage.mark_field_written(full_field_path, location)

        for location, kind in child_usage.usage_locations or []:
            if field_prefix:
                if kind == "read":
                    parent_usage.mark_field_read(field_prefix, location)
                elif kind == "write":
                    parent_usage.mark_field_written(field_prefix, location)
            else:
                if kind == "read":
                    parent_usage.mark_read(location)
                elif kind == "write":
                    parent_usage.mark_written(location)


def _analyze_single_module_with_context(
    self: VariablesAnalyzer,
    mod: _ModuleWithParameters,
    context: ScopeContext,
    path: list[str],
) -> tuple[set[str], set[str]]:
    self._walk_moduledef(mod.moduledef, context, path)
    self._walk_module_code(mod.modulecode, context, path)
    self._walk_submodules(mod.submodules or [], parent_context=context, parent_path=path)

    used_reads = {variable.name.lower() for variable in (mod.moduleparameters or []) if self._get_usage(variable).read}
    used_writes = {
        variable.name.lower() for variable in (mod.moduleparameters or []) if self._get_usage(variable).written
    }
    return used_reads, used_writes


def _analyze_typedef_with_context(
    self: VariablesAnalyzer,
    mt: ModuleTypeDef,
    context: ScopeContext,
    path: list[str],
) -> None:
    mt_key = mt.name.lower()
    if mt_key in self._analyzing_typedefs:
        return

    self._analyzing_typedefs.add(mt_key)

    try:
        self._walk_moduledef(mt.moduledef, context, path)
        self._walk_module_code(mt.modulecode, context, path)
        self._walk_submodules(mt.submodules or [], parent_context=context, parent_path=path)
        self._walk_typedef_groupconn(mt, context, path)

        used_reads = {
            variable.name.lower() for variable in (mt.moduleparameters or []) if self._get_usage(variable).read
        }
        used_writes = {
            variable.name.lower() for variable in (mt.moduleparameters or []) if self._get_usage(variable).written
        }

        self.used_params_by_typedef[mt.name] = used_reads | used_writes
        self.param_reads_by_typedef[mt_key] = used_reads
        self.param_writes_by_typedef[mt_key] = used_writes
    finally:
        self._analyzing_typedefs.discard(mt_key)


analyze_root_scope = _analyze_root_scope
analyze_single_module_with_context = _analyze_single_module_with_context
analyze_typedef = _analyze_typedef
analyze_typedef_with_context = _analyze_typedef_with_context
apply_alias_back_propagation = _apply_alias_back_propagation
collect_basepicture_issues = _collect_basepicture_issues
collect_typedef_issues = _collect_typedef_issues
is_external_typename = _is_external_typename
run_post_traversal_analyses = _run_post_traversal_analyses

__all__ = [
    "analyze_root_scope",
    "analyze_single_module_with_context",
    "analyze_typedef",
    "analyze_typedef_with_context",
    "apply_alias_back_propagation",
    "collect_basepicture_issues",
    "collect_typedef_issues",
    "is_external_typename",
    "run",
    "run_post_traversal_analyses",
]
