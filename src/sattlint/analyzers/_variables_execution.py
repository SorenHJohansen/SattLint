"""Execution and issue-collection helpers for variable analysis."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable
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
from ..resolution.common import varname_base
from ..resolution.scope import ScopeContext
from ._variables_picture_display_support import (
    build_typedef_root_context,
    record_graphics_binding_occurrences,
    record_picture_display_variable_occurrences,
)
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


_USAGE_VARIABLE_ISSUE_KINDS: frozenset[IssueKind] = frozenset(
    {
        IssueKind.UNUSED,
        IssueKind.READ_ONLY_NON_CONST,
        IssueKind.UI_ONLY,
        IssueKind.PROCEDURE_STATUS,
        IssueKind.NEVER_READ,
        IssueKind.WRITE_WITHOUT_EFFECT,
    }
)
_TYPEDEF_SCAN_ISSUE_KINDS: frozenset[IssueKind] = _USAGE_VARIABLE_ISSUE_KINDS | frozenset({IssueKind.NAME_COLLISION})
_USAGE_DERIVED_ISSUE_KINDS: frozenset[IssueKind] = _USAGE_VARIABLE_ISSUE_KINDS | frozenset(
    {
        IssueKind.UNUSED_DATATYPE_FIELD,
        IssueKind.NAMING_ROLE_MISMATCH,
        IssueKind.GLOBAL_SCOPE_MINIMIZATION,
        IssueKind.HIDDEN_GLOBAL_COUPLING,
        IssueKind.HIGH_FAN_IN_OUT,
    }
)
_POST_TRAVERSAL_ISSUE_KINDS: frozenset[IssueKind] = frozenset(
    {
        IssueKind.DATATYPE_DUPLICATION,
        IssueKind.LAYOUT_OVERLAP,
        IssueKind.RESET_CONTAMINATION,
        IssueKind.IMPLICIT_LATCH,
        IssueKind.WRITE_WITHOUT_EFFECT,
    }
)
_FINAL_SYNTHESIS_ISSUE_KINDS: frozenset[IssueKind] = frozenset(
    {
        IssueKind.NAMING_ROLE_MISMATCH,
        IssueKind.GLOBAL_SCOPE_MINIMIZATION,
        IssueKind.HIDDEN_GLOBAL_COUPLING,
        IssueKind.HIGH_FAN_IN_OUT,
    }
)
_PARAM_MAPPING_CHECK_ISSUE_KINDS: frozenset[IssueKind] = frozenset(
    {
        IssueKind.CONTRACT_MISMATCH,
        IssueKind.STRING_MAPPING_MISMATCH,
        IssueKind.MIN_MAX_MAPPING_MISMATCH,
    }
)


def _selected_issue_kinds(self: object) -> frozenset[IssueKind] | set[IssueKind] | None:
    return getattr(self, "_selected_issue_kinds", None)


def _should_collect_issue_kind(self: object, kind: IssueKind) -> bool:
    selected_kinds = _selected_issue_kinds(self)
    return selected_kinds is None or kind in selected_kinds


def _should_collect_any_issue_kinds(self: object, kinds: frozenset[IssueKind]) -> bool:
    selected_kinds = _selected_issue_kinds(self)
    return selected_kinds is None or bool(selected_kinds & kinds)


def _maybe_update_status(self: object, detail: str) -> None:
    update_status = getattr(self, "_update_status", None)
    if callable(update_status):
        update_status(detail)


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


def _run_timed_phase(self: VariablesAnalyzer, phase: str, callback: Callable[[], object]) -> None:
    record_phase_timing = getattr(self, "_record_phase_timing", None)
    if not callable(record_phase_timing):
        callback()
        return
    started_at = time.perf_counter()
    try:
        callback()
    finally:
        record_phase_timing(phase, started_at)


def _analyze_root_scope(self: VariablesAnalyzer) -> ScopeContext:
    root_context = self.context_builder.build_for_basepicture()
    self._trace("root-context-built", root_symbols=len(root_context.env))

    root_path = [self.bp.header.name]
    self._contexts_by_module_path[tuple(root_path)] = root_context
    self._walk_module_code(self.bp.modulecode, root_context, path=root_path)
    self._walk_moduledef(self.bp.moduledef, root_context, path=root_path)
    self._walk_header_enable(self.bp.header, root_context, path=root_path)
    self._walk_header_invoke_tails(self.bp.header, root_context, path=root_path)
    self._walk_header_groupconn(self.bp.header, root_context, path=root_path)
    self._walk_submodules(self.bp.submodules or [], parent_context=root_context, parent_path=root_path)
    return root_context


def _run_post_traversal_analyses(self: VariablesAnalyzer) -> None:
    if _should_collect_issue_kind(self, IssueKind.DATATYPE_DUPLICATION):
        self._detect_datatype_duplications()

    if _should_collect_issue_kind(self, IssueKind.RESET_CONTAMINATION):
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

    if _should_collect_issue_kind(self, IssueKind.IMPLICIT_LATCH):
        issue_count_before_latch = len(self._issues)
        detect_implicit_latching(self.bp, self._issues, self._limit_to_module_path)
        self._trace(
            "implicit-latch-scan",
            added_issue_count=len(self._issues) - issue_count_before_latch,
        )

    if _should_collect_issue_kind(self, IssueKind.LAYOUT_OVERLAP):
        layout_issues = collect_layout_overlap_issues(
            self.bp,
            limit_to_module_path=self._limit_to_module_path,
        )
        for issue in layout_issues:
            self._append_issue(issue)
        self._trace("layout-overlap-scan", added_issue_count=len(layout_issues))

    if _should_collect_issue_kind(self, IssueKind.WRITE_WITHOUT_EFFECT):
        self._effective_output_keys = self._compute_effective_output_keys()


def _analyze_library_dependency_typedef_usage(self: VariablesAnalyzer) -> None:
    if self._limit_to_module_path is not None:
        return
    if not self.analyzed_target_is_library or not self.include_dependency_moduletype_usage:
        return

    diverted_issues = self._issues
    diverted_indexes = self._param_mapping_issue_indexes
    diverted_context_issues = self.context_builder.issues
    temp_issues: list[VariableIssue] = []

    self._issues = temp_issues
    self._param_mapping_issue_indexes = {}
    self.context_builder.issues = temp_issues
    try:
        for moduletype in self.bp.moduletype_defs or []:
            if self._is_from_root_origin(
                getattr(moduletype, "origin_file", None),
                getattr(moduletype, "origin_lib", None),
            ):
                continue
            _maybe_update_status(self, f"scanning dependency typedef {moduletype.name}")
            td_path = [self.bp.header.name, f"TypeDef:{moduletype.name}"]
            self._analyze_typedef(moduletype, path=td_path)
    finally:
        self._issues = diverted_issues
        self._param_mapping_issue_indexes = diverted_indexes
        self.context_builder.issues = diverted_context_issues


def _collect_basepicture_issues(self: VariablesAnalyzer, bp_path: list[str]) -> None:
    collect_unused = _should_collect_issue_kind(self, IssueKind.UNUSED)
    collect_procedure_status = _should_collect_issue_kind(self, IssueKind.PROCEDURE_STATUS)
    collect_ui_only = _should_collect_issue_kind(self, IssueKind.UI_ONLY)
    collect_read_only_non_const = _should_collect_issue_kind(self, IssueKind.READ_ONLY_NON_CONST)
    collect_never_read = _should_collect_issue_kind(self, IssueKind.NEVER_READ)
    collect_write_without_effect = _should_collect_issue_kind(self, IssueKind.WRITE_WITHOUT_EFFECT)

    for variable in self.bp.localvariables or []:
        role = "localvariable"
        usage = self._get_usage(variable)
        if collect_unused and usage.is_unused:
            self._add_issue(IssueKind.UNUSED, bp_path, variable, role=role)
            continue
        procedure_status = self._procedure_status_issue(variable, usage) if collect_procedure_status else None
        if collect_procedure_status and procedure_status is not None:
            status_role, field_path = procedure_status
            self._add_issue(IssueKind.PROCEDURE_STATUS, bp_path, variable, role=status_role, field_path=field_path)
            continue
        if collect_ui_only and usage.is_display_only:
            self._add_issue(IssueKind.UI_ONLY, bp_path, variable, role=role)
        elif (
            collect_read_only_non_const
            and usage.is_read_only
            and not bool(variable.const)
            and self._is_const_candidate(variable)
        ):
            self._add_issue(IssueKind.READ_ONLY_NON_CONST, bp_path, variable, role=role)
        elif (
            collect_never_read and usage.written and not usage.read and not self._has_ignorable_output_binding(variable)
        ):
            self._add_issue(IssueKind.NEVER_READ, bp_path, variable, role=role)
        elif collect_write_without_effect and (
            usage.read
            and usage.written
            and not self._has_output_effect(variable, bp_path)
            and not self._has_procedure_status_binding(variable)
        ):
            self._add_issue(IssueKind.WRITE_WITHOUT_EFFECT, bp_path, variable, role=role)

    if (
        collect_unused
        or collect_procedure_status
        or collect_ui_only
        or collect_read_only_non_const
        or collect_never_read
        or collect_write_without_effect
    ):
        current_library = getattr(self.bp, "origin_lib", None)
        for module in self.bp.submodules or []:
            self._collect_issues_from_module(module, path=bp_path, current_library=current_library)


def _collect_typedef_issues(self: VariablesAnalyzer) -> None:
    if self._limit_to_module_path is not None:
        return

    collect_unused = _should_collect_issue_kind(self, IssueKind.UNUSED)
    collect_procedure_status = _should_collect_issue_kind(self, IssueKind.PROCEDURE_STATUS)
    collect_ui_only = _should_collect_issue_kind(self, IssueKind.UI_ONLY)
    collect_read_only_non_const = _should_collect_issue_kind(self, IssueKind.READ_ONLY_NON_CONST)
    collect_never_read = _should_collect_issue_kind(self, IssueKind.NEVER_READ)
    collect_write_without_effect = _should_collect_issue_kind(self, IssueKind.WRITE_WITHOUT_EFFECT)
    collect_name_collisions = _should_collect_issue_kind(self, IssueKind.NAME_COLLISION)

    if not collect_name_collisions and not (
        collect_unused
        or collect_procedure_status
        or collect_ui_only
        or collect_read_only_non_const
        or collect_never_read
        or collect_write_without_effect
    ):
        return

    for moduletype in self.bp.moduletype_defs or []:
        if not self._is_from_root_origin(
            getattr(moduletype, "origin_file", None),
            getattr(moduletype, "origin_lib", None),
        ):
            continue
        _maybe_update_status(self, f"collecting typedef issues for {moduletype.name}")
        td_path = [self.bp.header.name, f"TypeDef:{moduletype.name}"]
        current_library = moduletype.origin_lib or getattr(self.bp, "origin_lib", None)

        self._analyze_typedef(moduletype, path=td_path)
        if collect_write_without_effect:
            self._effective_output_keys = self._compute_effective_output_keys()

        if not (
            collect_unused
            or collect_procedure_status
            or collect_ui_only
            or collect_read_only_non_const
            or collect_never_read
            or collect_write_without_effect
        ):
            continue

        for variable in moduletype.moduleparameters or []:
            role = "moduleparameter"
            usage = self._get_usage(variable)
            if collect_unused and usage.is_unused:
                self._add_issue(IssueKind.UNUSED, td_path, variable, role=role)
                continue
            procedure_status = self._procedure_status_issue(variable, usage) if collect_procedure_status else None
            if collect_procedure_status and procedure_status is not None:
                status_role, field_path = procedure_status
                self._add_issue(IssueKind.PROCEDURE_STATUS, td_path, variable, role=status_role, field_path=field_path)
                continue
            if collect_ui_only and usage.is_display_only:
                self._add_issue(IssueKind.UI_ONLY, td_path, variable, role=role)
            elif collect_write_without_effect and (
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
            if collect_unused and usage.is_unused:
                self._add_issue(IssueKind.UNUSED, td_path, variable, role=role)
                continue
            procedure_status = self._procedure_status_issue(variable, usage) if collect_procedure_status else None
            if collect_procedure_status and procedure_status is not None:
                status_role, field_path = procedure_status
                self._add_issue(IssueKind.PROCEDURE_STATUS, td_path, variable, role=status_role, field_path=field_path)
                continue
            if collect_ui_only and usage.is_display_only:
                self._add_issue(IssueKind.UI_ONLY, td_path, variable, role=role)
            elif (
                collect_read_only_non_const
                and usage.is_read_only
                and not bool(variable.const)
                and self._is_const_candidate(variable)
            ):
                self._add_issue(IssueKind.READ_ONLY_NON_CONST, td_path, variable, role=role)
            elif (
                collect_never_read
                and usage.written
                and not usage.read
                and not self._has_ignorable_output_binding(variable)
            ):
                self._add_issue(IssueKind.NEVER_READ, td_path, variable, role=role)
            elif collect_write_without_effect and (
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
    self._param_mapping_issue_indexes = {}
    self.context_builder.issues = self._issues
    self._limit_to_module_path = limit_to_module_path
    self._phase_timings = []
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

    def _record_display_bindings() -> None:
        record_graphics_binding_occurrences(self)
        record_picture_display_variable_occurrences(self)

    def _propagate_aliases() -> None:
        self._apply_alias_back_propagation()
        self._propagate_procedure_status_bindings()

    def _finalize_issues() -> None:
        if _should_collect_issue_kind(self, IssueKind.NAMING_ROLE_MISMATCH):
            self._add_naming_role_mismatch_issues()
        if _should_collect_issue_kind(self, IssueKind.GLOBAL_SCOPE_MINIMIZATION):
            self._add_global_scope_minimization_issues()
        if _should_collect_issue_kind(self, IssueKind.HIDDEN_GLOBAL_COUPLING):
            self._add_hidden_global_coupling_issues()
        if _should_collect_issue_kind(self, IssueKind.HIGH_FAN_IN_OUT):
            self._add_high_fan_in_out_issues()

    is_library_target = bool(getattr(self, "_analyzed_target_is_library", False))
    includes_dependency_typedef_usage = bool(getattr(self, "_include_dependency_moduletype_usage", False))
    should_record_display_bindings = _should_collect_any_issue_kinds(self, _USAGE_DERIVED_ISSUE_KINDS)
    should_analyze_dependency_typedef_usage = _should_collect_any_issue_kinds(self, _USAGE_DERIVED_ISSUE_KINDS) and (
        _selected_issue_kinds(self) is None or (is_library_target and includes_dependency_typedef_usage)
    )
    should_propagate_aliases = apply_alias_back_propagation and _should_collect_any_issue_kinds(
        self,
        _USAGE_DERIVED_ISSUE_KINDS,
    )
    should_run_post_traversal_checks = _should_collect_any_issue_kinds(self, _POST_TRAVERSAL_ISSUE_KINDS)
    should_collect_basepicture_issues = _should_collect_any_issue_kinds(self, _USAGE_VARIABLE_ISSUE_KINDS)
    should_collect_typedef_issues = _should_collect_any_issue_kinds(self, _TYPEDEF_SCAN_ISSUE_KINDS)
    should_finalize_issues = _should_collect_any_issue_kinds(self, _FINAL_SYNTHESIS_ISSUE_KINDS)
    should_collect_datatype_field_issues = _should_collect_issue_kind(self, IssueKind.UNUSED_DATATYPE_FIELD)

    _maybe_update_status(self, "building root scope")
    _run_timed_phase(self, "root-traversal", self._analyze_root_scope)
    if should_record_display_bindings:
        _maybe_update_status(self, "recording display bindings")
        _run_timed_phase(self, "display-binding-scan", _record_display_bindings)
    if should_analyze_dependency_typedef_usage:
        _maybe_update_status(self, "analyzing dependency typedef usage")
        _run_timed_phase(self, "dependency-typedef-usage", self._analyze_library_dependency_typedef_usage)

    if should_propagate_aliases:
        _maybe_update_status(self, "propagating aliases")
        _run_timed_phase(self, "alias-propagation", _propagate_aliases)
        self._trace("alias-back-propagation", alias_link_count=len(self._alias_links))

    if should_run_post_traversal_checks:
        _maybe_update_status(self, "running post-traversal checks")
        _run_timed_phase(self, "post-traversal-checks", self._run_post_traversal_analyses)

    bp_path = [self.bp.header.name]
    if should_collect_basepicture_issues:
        _maybe_update_status(self, "collecting base picture issues")
        _run_timed_phase(self, "base-picture-issue-scan", lambda: self._collect_basepicture_issues(bp_path))
    if should_collect_typedef_issues:
        _maybe_update_status(self, "collecting typedef issues")
        _run_timed_phase(self, "typedef-scan", self._collect_typedef_issues)

    if should_finalize_issues:
        _maybe_update_status(self, "finalizing findings")
        _run_timed_phase(self, "final-issue-synthesis", _finalize_issues)
    if should_collect_datatype_field_issues:
        _run_timed_phase(self, "datatype-field-scan", self._add_unused_datatype_field_issues)
    if not should_finalize_issues:
        _maybe_update_status(self, "finalizing findings")
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

        context = build_typedef_root_context(self, mt, path)

        self._walk_moduledef(mt.moduledef, context, path)
        self._walk_module_code(mt.modulecode, context, path)
        self._walk_submodules(mt.submodules or [], parent_context=context, parent_path=path)
        self._walk_typedef_groupconn(mt, context, path)

        used_reads = {
            variable.name.lower() for variable in (mt.moduleparameters or []) if self._get_usage(variable).read
        }
        used_ui_reads = {
            variable.name.lower() for variable in (mt.moduleparameters or []) if self._get_usage(variable).ui_read
        }
        used_non_ui_reads = {
            variable.name.lower() for variable in (mt.moduleparameters or []) if self._get_usage(variable).non_ui_read
        }
        used_writes = {
            variable.name.lower() for variable in (mt.moduleparameters or []) if self._get_usage(variable).written
        }

        used_params = used_reads | used_writes
        self.used_params_by_typedef[mt.name] = used_params
        self.param_reads_by_typedef[mt.name.lower()] = used_reads
        self.param_ui_reads_by_typedef[mt.name.lower()] = used_ui_reads
        self.param_non_ui_reads_by_typedef[mt.name.lower()] = used_non_ui_reads
        self.param_writes_by_typedef[mt.name.lower()] = used_writes

        if _should_collect_any_issue_kinds(self, _PARAM_MAPPING_CHECK_ISSUE_KINDS):
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
        ui_read_locations = {tuple(location) for location in child_usage.ui_usage_locations}

        for field_path, locations in (child_usage.field_reads or {}).items():
            if field_prefix and field_path:
                full_field_path = f"{field_prefix}.{field_path}"
            elif field_prefix:
                full_field_path = field_prefix
            else:
                full_field_path = field_path

            for location in locations:
                parent_usage.mark_field_read(
                    full_field_path,
                    location,
                    ui=tuple(location) in ui_read_locations,
                )

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
            is_ui_read = tuple(location) in ui_read_locations
            if field_prefix:
                if kind == "read":
                    parent_usage.mark_field_read(field_prefix, location, ui=is_ui_read)
                elif kind == "write":
                    parent_usage.mark_field_written(field_prefix, location)
            else:
                if kind == "read":
                    if is_ui_read:
                        parent_usage.mark_ui_read(location)
                    else:
                        parent_usage.mark_read(location)
                elif kind == "write":
                    parent_usage.mark_written(location)


def _analyze_single_module_with_context(
    self: VariablesAnalyzer,
    mod: _ModuleWithParameters,
    context: ScopeContext,
    path: list[str],
) -> tuple[set[str], set[str], set[str], set[str]]:
    self._walk_moduledef(mod.moduledef, context, path)
    self._walk_module_code(mod.modulecode, context, path)
    self._walk_submodules(mod.submodules or [], parent_context=context, parent_path=path)

    used_reads = {variable.name.lower() for variable in (mod.moduleparameters or []) if self._get_usage(variable).read}
    used_ui_reads = {
        variable.name.lower() for variable in (mod.moduleparameters or []) if self._get_usage(variable).ui_read
    }
    used_non_ui_reads = {
        variable.name.lower() for variable in (mod.moduleparameters or []) if self._get_usage(variable).non_ui_read
    }
    used_writes = {
        variable.name.lower() for variable in (mod.moduleparameters or []) if self._get_usage(variable).written
    }
    return used_reads, used_ui_reads, used_non_ui_reads, used_writes


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
        used_ui_reads = {
            variable.name.lower() for variable in (mt.moduleparameters or []) if self._get_usage(variable).ui_read
        }
        used_non_ui_reads = {
            variable.name.lower() for variable in (mt.moduleparameters or []) if self._get_usage(variable).non_ui_read
        }
        used_writes = {
            variable.name.lower() for variable in (mt.moduleparameters or []) if self._get_usage(variable).written
        }

        self.used_params_by_typedef[mt.name] = used_reads | used_writes
        self.param_reads_by_typedef[mt_key] = used_reads
        self.param_ui_reads_by_typedef[mt_key] = used_ui_reads
        self.param_non_ui_reads_by_typedef[mt_key] = used_non_ui_reads
        self.param_writes_by_typedef[mt_key] = used_writes
    finally:
        self._analyzing_typedefs.discard(mt_key)


analyze_root_scope = _analyze_root_scope
analyze_library_dependency_typedef_usage = _analyze_library_dependency_typedef_usage
analyze_single_module_with_context = _analyze_single_module_with_context
analyze_typedef = _analyze_typedef
analyze_typedef_with_context = _analyze_typedef_with_context
apply_alias_back_propagation = _apply_alias_back_propagation
collect_basepicture_issues = _collect_basepicture_issues
collect_typedef_issues = _collect_typedef_issues
is_external_typename = _is_external_typename
run_timed_phase = _run_timed_phase
run_post_traversal_analyses = _run_post_traversal_analyses

__all__ = [
    "analyze_library_dependency_typedef_usage",
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
    "run_timed_phase",
]
