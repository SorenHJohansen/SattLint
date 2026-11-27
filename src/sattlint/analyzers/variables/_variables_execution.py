"""Execution and issue-collection helpers for variable analysis."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, cast

from sattlint.parser_api import (
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    Variable,
)

from ...core.timings import PhaseTiming
from ...models._variable_issues import (
    DECLARATION_ROLE_LOCAL_VARIABLE,
    DECLARATION_ROLE_MODULE_PARAMETER,
)
from ...reporting.variables_report import (
    IssueKind,
    NeverReadIssue,
    ProcedureStatusIssue,
    ReadOnlyNonConstIssue,
    UnusedIssue,
    VariableIssue,
    WriteWithoutEffectIssue,
)
from ...resolution.scope import ScopeContext
from ...utils.casefolding import casefold_key
from ..reset_contamination import detect_implicit_latching, detect_reset_contamination
from ..shared.variable_utils import mapping_target_name
from ._usage_tracker import UsageTracker
from ._variable_traversal_support import _IGNORED_GRAPHICS_TAIL_BASENAMES
from ._variables_contracts import (
    IssueKindSelection,
    TypedefUsageKey,
    typedef_usage_key,
)
from ._variables_contracts import (
    explicitly_selected_issue_kinds as _explicitly_selected_issue_kinds,
)
from ._variables_contracts import (
    selected_issue_kinds as _selected_issue_kinds,
)
from ._variables_contracts import (
    should_collect_any_issue_kinds as _should_collect_any_issue_kinds,
)
from ._variables_contracts import (
    should_collect_issue_kind as _should_collect_issue_kind,
)
from ._variables_mapping_refs import ordered_alias_links
from ._variables_picture_display_support import (
    build_typedef_root_context,
    record_graphics_binding_occurrences,
    record_picture_display_variable_occurrences,
)
from ._variables_read_before_write import collect_read_before_write_issues as _collect_read_before_write_issues
from ._variables_secure_candidates import SecureCandidateFacts
from ._variables_shadowing import collect_shadowing_issues as _collect_shadowing_issues
from ._variables_status import has_out_of_origin_consumer as _has_out_of_origin_consumer
from ._variables_unsafe_defaults import collect_unsafe_default_issues as _collect_unsafe_default_issues

if TYPE_CHECKING:
    from . import VariablesAnalyzer


_process_root_traversal_count: int = 0


def count_process_root_traversals() -> int:
    """Return the process-wide number of variables root traversals started."""
    return _process_root_traversal_count


log = logging.getLogger("SattLint")

_UnresolvedLookupCounts = dict[str, int]
_UnresolvedLookupExamples = dict[str, tuple[int, str]]


class _ModuleWithParameters(Protocol):
    @property
    def moduledef(self) -> Any: ...

    @property
    def modulecode(self) -> Any: ...

    @property
    def submodules(self) -> list[SingleModule | FrameModule | ModuleTypeInstance] | None: ...

    @property
    def moduleparameters(self) -> list[Variable] | None: ...


_USAGE_VARIABLE_ISSUE_KINDS: frozenset[IssueKind] = frozenset(
    {
        IssueKind.UNUSED,
        IssueKind.READ_ONLY_NON_CONST,
        IssueKind.PROCEDURE_STATUS,
        IssueKind.NEVER_READ,
        IssueKind.WRITE_WITHOUT_EFFECT,
    }
)
_TYPEDEF_SCAN_ISSUE_KINDS: frozenset[IssueKind] = _USAGE_VARIABLE_ISSUE_KINDS
_USAGE_DERIVED_ISSUE_KINDS: frozenset[IssueKind] = _USAGE_VARIABLE_ISSUE_KINDS | frozenset(
    {
        IssueKind.UNUSED_DATATYPE_FIELD,
        IssueKind.FIELD_READ_ONLY,
        IssueKind.FIELD_NEVER_READ,
        IssueKind.GLOBAL_SCOPE_MINIMIZATION,
        IssueKind.HIDDEN_GLOBAL_COUPLING,
        IssueKind.HIGH_FAN_IN_OUT,
    }
)
_POST_TRAVERSAL_ISSUE_KINDS: frozenset[IssueKind] = frozenset(
    {
        IssueKind.DATATYPE_DUPLICATION,
        IssueKind.RESET_CONTAMINATION,
        IssueKind.IMPLICIT_LATCH,
        IssueKind.SECURE_CANDIDATE,
        IssueKind.STRING_MAPPING_MISMATCH,
        IssueKind.WRITE_WITHOUT_EFFECT,
        IssueKind.SHADOWING,
        IssueKind.UNSAFE_BOOLEAN_DEFAULT,
        IssueKind.READ_BEFORE_WRITE,
    }
)
_DATATYPE_FIELD_ISSUE_KINDS: frozenset[IssueKind] = frozenset(
    {
        IssueKind.UNUSED_DATATYPE,
        IssueKind.UNUSED_DATATYPE_FIELD,
        IssueKind.FIELD_READ_ONLY,
        IssueKind.FIELD_NEVER_READ,
    }
)
_FINAL_SYNTHESIS_ISSUE_KINDS: frozenset[IssueKind] = frozenset(
    {
        IssueKind.GLOBAL_SCOPE_MINIMIZATION,
        IssueKind.HIDDEN_GLOBAL_COUPLING,
        IssueKind.HIGH_FAN_IN_OUT,
    }
)


def _maybe_update_status(self: object, detail: str) -> None:
    update_status = getattr(self, "_update_status", None)
    if callable(update_status):
        update_status(detail)


def _format_selected_issue_kinds(self: IssueKindSelection) -> str:
    selected_kinds = _selected_issue_kinds(self)
    if not selected_kinds:
        return "all default issue kinds"
    return ", ".join(kind.value for kind in sorted(selected_kinds, key=lambda item: item.value))


def _format_phase_timing_summary(self: object) -> str | None:
    phase_timings = cast(list[PhaseTiming] | None, getattr(self, "_phase_timings", None))
    if phase_timings is None or not phase_timings:
        return None

    parts = [f"{entry.phase}={entry.duration_ms:.3f}" for entry in phase_timings]
    return ", ".join(parts) if parts else None


def _log_debug_analysis_summary(self: IssueKindSelection, issue_counts: dict[str, int]) -> None:
    log.debug("Variables analysis complete. Issues=%d", len(getattr(self, "_issues", [])))
    log.debug("Variables selected issue kinds: %s", _format_selected_issue_kinds(self))
    if issue_counts:
        log.debug(
            "Variables issue counts: %s",
            ", ".join(f"{issue_kind}={count}" for issue_kind, count in issue_counts.items()),
        )
    else:
        log.debug("Variables issue counts: none")

    phase_summary = _format_phase_timing_summary(self)
    if phase_summary is not None:
        log.debug("Variables phase timings (ms): %s", phase_summary)

    unresolved_total = getattr(self, "_unresolved_variable_lookup_total", 0)
    unresolved_counts = cast(_UnresolvedLookupCounts | None, getattr(self, "_unresolved_variable_lookup_counts", None))
    unresolved_examples = cast(
        _UnresolvedLookupExamples | None,
        getattr(self, "_unresolved_variable_lookup_examples", None),
    )
    if not isinstance(unresolved_total, int) or unresolved_total <= 0:
        return
    if unresolved_counts is None:
        unresolved_counts = {}
    if unresolved_examples is None:
        unresolved_examples = {}

    filtered_counts = {
        variable_name: count
        for variable_name, count in unresolved_counts.items()
        if variable_name.casefold() not in _IGNORED_GRAPHICS_TAIL_BASENAMES
    }
    filtered_total = sum(filtered_counts.values())
    suppressed_total = max(unresolved_total - filtered_total, 0)
    if filtered_total <= 0:
        if suppressed_total > 0:
            log.debug(
                "Variables unresolved lookups: suppressed %d ignored UI token hit(s)",
                suppressed_total,
            )
        return

    log.debug(
        "Variables unresolved lookups: total=%d unique=%d%s",
        filtered_total,
        len(filtered_counts),
        f" suppressed_noise={suppressed_total}" if suppressed_total else "",
    )
    for variable_name, count in sorted(
        filtered_counts.items(),
        key=lambda item: (-item[1], item[0].casefold()),
    )[:10]:
        env_size, path = unresolved_examples.get(variable_name, (0, ""))
        log.debug(
            "  unresolved %s x%d (first env size=%d, first path=%s)",
            variable_name,
            count,
            env_size,
            path,
        )


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


_mapping_target_name = mapping_target_name


def _reset_analysis_state(self: VariablesAnalyzer) -> None:
    def _clear_or_set(attr_name: str, default: object) -> None:
        current = getattr(self, attr_name, None)
        clear_method = getattr(current, "clear", None)
        if callable(clear_method):
            clear_method()
            return
        setattr(self, attr_name, default)

    self._issues = []
    self._param_mapping_issue_indexes = {}
    context_builder = getattr(self, "context_builder", None)
    if context_builder is not None:
        context_builder.issues = self._issues
    _clear_or_set("_analysis_warnings", [])
    _clear_or_set("_warned_ambiguous_types", set[str]())
    self._last_status_message = None
    self._limit_to_module_path = None
    _clear_or_set("_phase_timings", [])
    _clear_or_set("_record_component_order_datatypes_seen", set[str]())
    previous_tracker = getattr(self, "usage_tracker", None)
    self.usage_tracker = UsageTracker(
        record_access_graph=getattr(previous_tracker, "record_access_graph", True),
        record_locations=getattr(previous_tracker, "record_locations", True),
    )
    _clear_or_set("_site_stack", [])
    selected_kinds = getattr(self, "_selected_issue_kinds", None)
    self._secure_candidate_facts = (
        SecureCandidateFacts() if selected_kinds is None or IssueKind.SECURE_CANDIDATE in selected_kinds else None
    )
    self._secure_in_step = False
    self._secure_step_name = None
    self._secure_in_transition = False
    self._secure_transition_name = None
    _clear_or_set("_used_dependency_libraries", set[str]())
    _clear_or_set("used_params_by_typedef", {})
    _clear_or_set("param_reads_by_typedef", {})
    _clear_or_set("param_ui_reads_by_typedef", {})
    _clear_or_set("param_non_ui_reads_by_typedef", {})
    _clear_or_set("param_writes_by_typedef", {})
    _clear_or_set("_alias_links", [])
    _clear_or_set("_effect_flow_edges", defaultdict[tuple[str, ...], set[tuple[str, ...]]](set))
    _clear_or_set("_effect_flow_display_names", {})
    _clear_or_set("_external_effect_sinks", set[tuple[str, ...]]())
    _clear_or_set("_effective_output_keys", set[tuple[str, ...]]())
    _clear_or_set("_procedure_status_bindings", {})
    _clear_or_set("_ignorable_output_variable_ids", set[int]())
    _clear_or_set("_out_of_origin_consumer_variable_ids", set[int]())
    _clear_or_set("_contexts_by_module_path", {})
    _clear_or_set("_analyzing_typedefs", set[TypedefUsageKey]())
    _clear_or_set("datatype_leaf_index_cache", {})
    self._root_variable_access_summary_cache_token = None
    self._root_variable_access_summary_cache = {}


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
            shared_artifacts=getattr(self, "_shared_artifacts", None),
            analyzed_target_is_library=self._analyzed_target_is_library,
        )
        self._trace(
            "reset-contamination-scan",
            added_issue_count=len(self._issues) - issue_count_before_reset,
        )

    if _should_collect_issue_kind(self, IssueKind.IMPLICIT_LATCH):
        issue_count_before_latch = len(self._issues)
        detect_implicit_latching(
            self.bp,
            self._issues,
            self._limit_to_module_path,
            shared_artifacts=getattr(self, "_shared_artifacts", None),
            analyzed_target_is_library=self._analyzed_target_is_library,
        )
        self._trace(
            "implicit-latch-scan",
            added_issue_count=len(self._issues) - issue_count_before_latch,
        )

    if _should_collect_issue_kind(self, IssueKind.SECURE_CANDIDATE):
        issue_count_before_secure = len(self._issues)
        facts = self._secure_candidate_facts
        if facts is not None:
            self._issues.extend(
                facts.build_issues(
                    self.contexts_by_module_path,
                    root_library=getattr(self.bp, "origin_lib", None),
                )
            )
        self._trace(
            "secure-candidate-scan",
            added_issue_count=len(self._issues) - issue_count_before_secure,
        )

    if _should_collect_issue_kind(self, IssueKind.WRITE_WITHOUT_EFFECT):
        self._effective_output_keys = self._compute_effective_output_keys()

    if _should_collect_issue_kind(self, IssueKind.SHADOWING):
        issue_count_before_shadowing = len(self._issues)
        _collect_shadowing_issues(self)
        self._trace(
            "shadowing-scan",
            added_issue_count=len(self._issues) - issue_count_before_shadowing,
        )

    if _should_collect_issue_kind(self, IssueKind.UNSAFE_BOOLEAN_DEFAULT):
        issue_count_before_unsafe_defaults = len(self._issues)
        _collect_unsafe_default_issues(self)
        self._trace(
            "unsafe-default-scan",
            added_issue_count=len(self._issues) - issue_count_before_unsafe_defaults,
        )

    if _should_collect_issue_kind(self, IssueKind.READ_BEFORE_WRITE):
        issue_count_before_read_before_write = len(self._issues)
        _collect_read_before_write_issues(self)
        self._trace(
            "read-before-write-scan",
            added_issue_count=len(self._issues) - issue_count_before_read_before_write,
        )


def _declared_datatype_names(node: object) -> set[str]:
    names: set[str] = set()
    for variable in [
        *cast(list[Variable], getattr(node, "moduleparameters", None) or []),
        *cast(list[Variable], getattr(node, "localvariables", None) or []),
    ]:
        datatype = variable.datatype
        if isinstance(datatype, str) and datatype:
            names.add(datatype.casefold())
    return names


def _instantiated_moduletype_names(node: object) -> set[str]:
    return {
        child.moduletype_name.casefold()
        for child in cast(list[object], getattr(node, "submodules", None) or [])
        if isinstance(child, ModuleTypeInstance)
    }


def _has_sequences(self: VariablesAnalyzer, node: object, seen: set[str] | None = None) -> bool:
    """Whether *node* or anything it instantiates carries SFC sequences."""
    visited: set[str] = set() if seen is None else set(seen)
    code = getattr(node, "modulecode", None)
    if getattr(code, "sequences", None):
        return True
    index = cast(dict[str, tuple[ModuleTypeDef, ...]], getattr(self, "typedef_index", None) or {})
    for child in cast(list[object], getattr(node, "submodules", None) or []):
        if isinstance(child, ModuleTypeInstance):
            key = child.moduletype_name.casefold()
            if key in visited:
                continue
            visited.add(key)
            for resolved in index.get(key, ()):
                if _has_sequences(self, resolved, visited):
                    return True
            continue
        if _has_sequences(self, child, visited):
            return True
    return False


def _consumer_moduletype_names(self: VariablesAnalyzer) -> set[str] | None:
    """The dependency module types that can reach the analyzed library's data.

    The sweep after the root traversal exists to find out-of-origin consumers,
    but the merged view also carries every library that merely sits beside the
    analyzed one. Walking all of those records usage nothing can consume and
    costs most of the analysis. A consumer is found instead by what it can
    reach: a declaration of the analyzed origin, a record type whose fields do,
    or another consumer it instantiates. ``None`` means the view declares
    nothing to reach, so the sweep keeps its exhaustive behaviour.
    """
    datatype_defs = cast(list[object], getattr(self.bp, "datatype_defs", None) or [])
    moduletype_defs = self.bp.moduletype_defs or []
    root_datatypes = {
        str(getattr(datatype, "name", "")).casefold()
        for datatype in datatype_defs
        if self._is_from_root_origin(
            getattr(datatype, "origin_file", None),
            getattr(datatype, "origin_lib", None),
        )
    }
    root_moduletypes = {
        moduletype.name.casefold()
        for moduletype in moduletype_defs
        if self._is_from_root_origin(
            getattr(moduletype, "origin_file", None),
            getattr(moduletype, "origin_lib", None),
        )
    }
    if not root_datatypes and not root_moduletypes:
        return None

    reaching_datatypes = set(root_datatypes)
    dependency_datatypes = [
        datatype
        for datatype in datatype_defs
        if not self._is_from_root_origin(
            getattr(datatype, "origin_file", None),
            getattr(datatype, "origin_lib", None),
        )
    ]
    changed = True
    while changed:
        changed = False
        for datatype in dependency_datatypes:
            name = str(getattr(datatype, "name", "")).casefold()
            if name in reaching_datatypes:
                continue
            if _declared_datatype_names(datatype) & reaching_datatypes:
                reaching_datatypes.add(name)
                changed = True

    dependency_types = [
        moduletype
        for moduletype in moduletype_defs
        if not self._is_from_root_origin(
            getattr(moduletype, "origin_file", None),
            getattr(moduletype, "origin_lib", None),
        )
    ]
    instantiated: dict[str, set[str]] = {}
    consumers: set[str] = set()
    for moduletype in dependency_types:
        name = moduletype.name.casefold()
        children = _instantiated_moduletype_names(moduletype)
        instantiated[name] = children
        if (_declared_datatype_names(moduletype) & reaching_datatypes) or (children & root_moduletypes):
            consumers.add(name)
    changed = True
    while changed:
        changed = False
        for name, children in instantiated.items():
            if name in consumers:
                continue
            if children & consumers:
                consumers.add(name)
                changed = True
    return consumers


def _analyze_library_dependency_typedef_usage(self: VariablesAnalyzer) -> None:
    if self._limit_to_module_path is not None:
        return
    if not self.analyzed_target_is_library:
        return

    diverted_issues = self._issues
    diverted_indexes = self._param_mapping_issue_indexes
    diverted_context_issues = self.context_builder.issues
    temp_issues: list[VariableIssue] = []

    self._issues = temp_issues
    self._param_mapping_issue_indexes = {}
    self.context_builder.issues = temp_issues
    consumers = _consumer_moduletype_names(self)
    collect_secure_candidates = _should_collect_issue_kind(self, IssueKind.SECURE_CANDIDATE)
    try:
        for moduletype in self.bp.moduletype_defs or []:
            if self._is_from_root_origin(
                getattr(moduletype, "origin_file", None),
                getattr(moduletype, "origin_lib", None),
            ):
                continue
            # Secure-candidate facts are recorded from step and transition code,
            # so an SFC type is walked even when nothing reaches it.
            if (
                consumers is not None
                and moduletype.name.casefold() not in consumers
                and not (collect_secure_candidates and _has_sequences(self, moduletype))
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
    collect_read_only_non_const = _should_collect_issue_kind(self, IssueKind.READ_ONLY_NON_CONST)
    collect_never_read = _should_collect_issue_kind(self, IssueKind.NEVER_READ)
    collect_write_without_effect = _should_collect_issue_kind(self, IssueKind.WRITE_WITHOUT_EFFECT)

    for variable in self.bp.localvariables or []:
        role = DECLARATION_ROLE_LOCAL_VARIABLE
        usage = self._get_usage(variable)
        # A contract outside the analyzed origin proves the variable is consumed even
        # though the read is invisible, so absence of use is not evidence of dead code.
        consumed_out_of_origin = _has_out_of_origin_consumer(self, variable)
        if collect_unused and usage.is_unused and not consumed_out_of_origin:
            self._append_issue(
                UnusedIssue(module_path=bp_path.copy(), variable=variable, role=role, declaration_role=role)
            )
            continue
        procedure_status = self._procedure_status_issue(variable, usage) if collect_procedure_status else None
        if collect_procedure_status and procedure_status is not None:
            status_role, field_path = procedure_status
            self._append_issue(
                ProcedureStatusIssue(
                    module_path=bp_path.copy(),
                    variable=variable,
                    role=status_role,
                    field_path=field_path,
                    declaration_role=role,
                )
            )
            continue
        if (
            collect_read_only_non_const
            and usage.is_read_only
            and not bool(variable.const)
            and self._is_const_candidate(variable)
        ):
            self._append_issue(
                ReadOnlyNonConstIssue(module_path=bp_path.copy(), variable=variable, role=role, declaration_role=role)
            )
        elif (
            collect_never_read
            and usage.written
            and not usage.read
            and not consumed_out_of_origin
            and not self._has_ignorable_output_binding(variable)
        ):
            self._append_issue(
                NeverReadIssue(module_path=bp_path.copy(), variable=variable, role=role, declaration_role=role)
            )
        elif collect_write_without_effect and (
            usage.read
            and usage.written
            and not self._has_output_effect(variable, bp_path)
            and not self._has_procedure_status_binding(variable)
        ):
            self._append_issue(
                WriteWithoutEffectIssue(module_path=bp_path.copy(), variable=variable, role=role, declaration_role=role)
            )

    if (
        collect_unused
        or collect_procedure_status
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
    collect_read_only_non_const = _should_collect_issue_kind(self, IssueKind.READ_ONLY_NON_CONST)
    collect_never_read = _should_collect_issue_kind(self, IssueKind.NEVER_READ)
    collect_write_without_effect = _should_collect_issue_kind(self, IssueKind.WRITE_WITHOUT_EFFECT)
    collect_datatype_fields = _explicitly_selected_issue_kinds(self, _DATATYPE_FIELD_ISSUE_KINDS)
    collect_any_typedef_issue = (
        collect_unused
        or collect_procedure_status
        or collect_read_only_non_const
        or collect_never_read
        or collect_write_without_effect
    )

    if not collect_any_typedef_issue and not collect_datatype_fields:
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
            or collect_read_only_non_const
            or collect_never_read
            or collect_write_without_effect
        ):
            continue

        for variable in moduletype.moduleparameters or []:
            role = DECLARATION_ROLE_MODULE_PARAMETER
            usage = self._get_usage(variable)
            # A library's module type is its public interface; a program outside
            # the analyzed target connects these parameters even when the
            # library's own code does not touch them.
            is_external_interface = getattr(self, "analyzed_target_is_library", False)
            if (
                collect_unused
                and usage.is_unused
                and not _has_out_of_origin_consumer(self, variable)
                and not is_external_interface
            ):
                self._append_issue(
                    UnusedIssue(module_path=td_path.copy(), variable=variable, role=role, declaration_role=role)
                )
                continue
            procedure_status = self._procedure_status_issue(variable, usage) if collect_procedure_status else None
            if collect_procedure_status and procedure_status is not None:
                status_role, field_path = procedure_status
                self._append_issue(
                    ProcedureStatusIssue(
                        module_path=td_path.copy(),
                        variable=variable,
                        role=status_role,
                        field_path=field_path,
                        declaration_role=role,
                    )
                )
                continue
        for module in moduletype.submodules or []:
            self._collect_issues_from_module(module, path=td_path, current_library=current_library)

        for variable in moduletype.localvariables or []:
            role = DECLARATION_ROLE_LOCAL_VARIABLE
            usage = self._get_usage(variable)
            consumed_out_of_origin = _has_out_of_origin_consumer(self, variable)
            if collect_unused and usage.is_unused and not consumed_out_of_origin:
                self._append_issue(
                    UnusedIssue(module_path=td_path.copy(), variable=variable, role=role, declaration_role=role)
                )
                continue
            procedure_status = self._procedure_status_issue(variable, usage) if collect_procedure_status else None
            if collect_procedure_status and procedure_status is not None:
                status_role, field_path = procedure_status
                self._append_issue(
                    ProcedureStatusIssue(
                        module_path=td_path.copy(),
                        variable=variable,
                        role=status_role,
                        field_path=field_path,
                        declaration_role=role,
                    )
                )
                continue
            if (
                collect_read_only_non_const
                and usage.is_read_only
                and not bool(variable.const)
                and self._is_const_candidate(variable)
            ):
                self._append_issue(
                    ReadOnlyNonConstIssue(
                        module_path=td_path.copy(), variable=variable, role=role, declaration_role=role
                    )
                )
            elif (
                collect_never_read
                and usage.written
                and not usage.read
                and not consumed_out_of_origin
                and not self._has_ignorable_output_binding(variable)
            ):
                self._append_issue(
                    NeverReadIssue(module_path=td_path.copy(), variable=variable, role=role, declaration_role=role)
                )
            elif collect_write_without_effect and (
                usage.read
                and usage.written
                and not self._has_output_effect(variable, td_path)
                and not self._has_procedure_status_binding(variable)
            ):
                self._append_issue(
                    WriteWithoutEffectIssue(
                        module_path=td_path.copy(), variable=variable, role=role, declaration_role=role
                    )
                )


def run(  # noqa: PLR0915
    self: VariablesAnalyzer,
    apply_alias_back_propagation: bool = True,
    limit_to_module_path: list[str] | None = None,
) -> list[VariableIssue]:
    _reset_analysis_state(self)
    global _process_root_traversal_count
    _process_root_traversal_count += 1
    shared_artifacts = getattr(self, "_shared_artifacts", None)
    if shared_artifacts is not None:
        shared_artifacts.counters.variable_root_traversals += 1
    self._unresolved_variable_lookup_total = 0
    self._unresolved_variable_lookup_counts = defaultdict(int)
    self._unresolved_variable_lookup_examples = {}
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
        log.debug(
            "Variables analysis start: %s locals=%d submodules=%d typedefs=%d selected=%s",
            self.bp.header.name,
            len(self.bp.localvariables or []),
            len(self.bp.submodules or []),
            len(self.bp.moduletype_defs or []),
            _format_selected_issue_kinds(self),
        )

    def _record_display_bindings() -> None:
        record_graphics_binding_occurrences(self)
        record_picture_display_variable_occurrences(self)

    def _propagate_aliases() -> None:
        self._apply_alias_back_propagation()
        self._propagate_procedure_status_bindings()

    def _finalize_issues() -> None:
        if _should_collect_any_issue_kinds(
            self,
            frozenset(
                {
                    IssueKind.GLOBAL_SCOPE_MINIMIZATION,
                    IssueKind.HIDDEN_GLOBAL_COUPLING,
                    IssueKind.HIGH_FAN_IN_OUT,
                }
            ),
        ):
            build_root_variable_access_summaries = getattr(self, "_build_root_variable_access_summaries", None)
            if callable(build_root_variable_access_summaries):
                _run_timed_phase(
                    self,
                    "root-variable-access-summary-build",
                    build_root_variable_access_summaries,
                )
        if _should_collect_issue_kind(self, IssueKind.GLOBAL_SCOPE_MINIMIZATION):
            self._add_global_scope_minimization_issues()
        if _should_collect_issue_kind(self, IssueKind.HIDDEN_GLOBAL_COUPLING):
            self._add_hidden_global_coupling_issues()
        if _should_collect_issue_kind(self, IssueKind.HIGH_FAN_IN_OUT):
            self._add_high_fan_in_out_issues()

    is_library_target = bool(getattr(self, "_analyzed_target_is_library", False))
    includes_dependency_typedef_usage = bool(getattr(self, "_include_dependency_moduletype_usage", False))
    should_record_display_bindings = _should_collect_any_issue_kinds(self, _USAGE_DERIVED_ISSUE_KINDS)
    datatype_field_selected = _explicitly_selected_issue_kinds(self, _DATATYPE_FIELD_ISSUE_KINDS)
    should_analyze_dependency_typedef_usage = _should_collect_any_issue_kinds(self, _USAGE_DERIVED_ISSUE_KINDS) and (
        _selected_issue_kinds(self) is None
        or (is_library_target and (includes_dependency_typedef_usage or datatype_field_selected))
    )
    should_propagate_aliases = apply_alias_back_propagation and _should_collect_any_issue_kinds(
        self,
        _USAGE_DERIVED_ISSUE_KINDS,
    )
    should_run_post_traversal_checks = _should_collect_any_issue_kinds(self, _POST_TRAVERSAL_ISSUE_KINDS)
    should_collect_basepicture_issues = _should_collect_any_issue_kinds(self, _USAGE_VARIABLE_ISSUE_KINDS)
    should_collect_typedef_issues = _should_collect_any_issue_kinds(
        self,
        _TYPEDEF_SCAN_ISSUE_KINDS | _DATATYPE_FIELD_ISSUE_KINDS,
    )
    should_finalize_issues = _should_collect_any_issue_kinds(self, _FINAL_SYNTHESIS_ISSUE_KINDS)
    should_collect_datatype_field_issues = datatype_field_selected

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

        def _collect_datatype_field_issues() -> None:
            # Both passes need the same variable inventory. Build it once; the
            # inventory is the expensive part when the dependency closure is
            # large, and each pass only reads it.
            variables = self.iter_variables_for_datatype_field_analysis()
            self._add_unused_datatype_field_issues(variables)
            if hasattr(self, "_add_field_usage_asymmetry_issues"):
                self._add_field_usage_asymmetry_issues(variables)

        _run_timed_phase(self, "datatype-field-scan", _collect_datatype_field_issues)
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
        _log_debug_analysis_summary(self, issue_counts)

    return self._issues


reset_analysis_state = _reset_analysis_state


def _is_external_typename(self: VariablesAnalyzer, typename: str) -> bool:
    return typename.casefold() not in self.typedef_index


def _analyze_typedef(self: VariablesAnalyzer, mt: ModuleTypeDef, path: list[str]) -> None:
    mt_key = typedef_usage_key(mt)
    if mt_key in self._analyzing_typedefs:
        return

    self._analyzing_typedefs.add(mt_key)

    try:
        params = list(mt.moduleparameters or [])
        locals_ = list(mt.localvariables or [])

        env = {casefold_key(variable.name): variable for variable in params}
        env.update({casefold_key(variable.name): variable for variable in locals_})

        context = build_typedef_root_context(self, mt, path)

        self._walk_moduledef(mt.moduledef, context, path)
        self._walk_module_code(mt.modulecode, context, path)
        self._walk_submodules(mt.submodules or [], parent_context=context, parent_path=path)
        self._walk_typedef_groupconn(mt, context, path)

        used_reads = {
            casefold_key(variable.name) for variable in (mt.moduleparameters or []) if self._get_usage(variable).read
        }
        used_ui_reads = {
            casefold_key(variable.name) for variable in (mt.moduleparameters or []) if self._get_usage(variable).ui_read
        }
        used_non_ui_reads = {
            casefold_key(variable.name)
            for variable in (mt.moduleparameters or [])
            if self._get_usage(variable).non_ui_read
        }
        used_writes = {
            casefold_key(variable.name) for variable in (mt.moduleparameters or []) if self._get_usage(variable).written
        }

        used_params = used_reads | used_writes
        self.used_params_by_typedef[mt_key] = used_params
        self.param_reads_by_typedef[mt_key] = used_reads
        self.param_ui_reads_by_typedef[mt_key] = used_ui_reads
        self.param_non_ui_reads_by_typedef[mt_key] = used_non_ui_reads
        self.param_writes_by_typedef[mt_key] = used_writes

    finally:
        self._analyzing_typedefs.discard(mt_key)


def _apply_alias_back_propagation(self: VariablesAnalyzer) -> None:
    for parent_var, child_var, field_prefix in ordered_alias_links(self._alias_links):
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

    used_reads = {
        casefold_key(variable.name) for variable in (mod.moduleparameters or []) if self._get_usage(variable).read
    }
    used_ui_reads = {
        casefold_key(variable.name) for variable in (mod.moduleparameters or []) if self._get_usage(variable).ui_read
    }
    used_non_ui_reads = {
        casefold_key(variable.name)
        for variable in (mod.moduleparameters or [])
        if self._get_usage(variable).non_ui_read
    }
    used_writes = {
        casefold_key(variable.name) for variable in (mod.moduleparameters or []) if self._get_usage(variable).written
    }
    return used_reads, used_ui_reads, used_non_ui_reads, used_writes


def _analyze_typedef_with_context(
    self: VariablesAnalyzer,
    mt: ModuleTypeDef,
    context: ScopeContext,
    path: list[str],
) -> None:
    mt_key = typedef_usage_key(mt)
    if mt_key in self._analyzing_typedefs:
        return

    self._analyzing_typedefs.add(mt_key)

    try:
        self._walk_moduledef(mt.moduledef, context, path)
        self._walk_module_code(mt.modulecode, context, path)
        self._walk_submodules(mt.submodules or [], parent_context=context, parent_path=path)
        self._walk_typedef_groupconn(mt, context, path)

        used_reads = {
            casefold_key(variable.name) for variable in (mt.moduleparameters or []) if self._get_usage(variable).read
        }
        used_ui_reads = {
            casefold_key(variable.name) for variable in (mt.moduleparameters or []) if self._get_usage(variable).ui_read
        }
        used_non_ui_reads = {
            casefold_key(variable.name)
            for variable in (mt.moduleparameters or [])
            if self._get_usage(variable).non_ui_read
        }
        used_writes = {
            casefold_key(variable.name) for variable in (mt.moduleparameters or []) if self._get_usage(variable).written
        }

        self.used_params_by_typedef[mt_key] = used_reads | used_writes
        self.param_reads_by_typedef[mt_key] = used_reads
        self.param_ui_reads_by_typedef[mt_key] = used_ui_reads
        self.param_non_ui_reads_by_typedef[mt_key] = used_non_ui_reads
        self.param_writes_by_typedef[mt_key] = used_writes
    finally:
        self._analyzing_typedefs.discard(mt_key)


class VariablesExecutionMixin:
    def _run_timed_phase(self: Any, phase: str, callback: Callable[[], object]) -> None:
        _run_timed_phase(self, phase, callback)

    def _reset_analysis_state(self: Any) -> None:
        _reset_analysis_state(self)

    def _analyze_root_scope(self: Any) -> ScopeContext:
        return _analyze_root_scope(self)

    def _run_post_traversal_analyses(self: Any) -> None:
        _run_post_traversal_analyses(self)

    def _analyze_library_dependency_typedef_usage(self: Any) -> None:
        _analyze_library_dependency_typedef_usage(self)

    def _collect_basepicture_issues(self: Any, bp_path: list[str]) -> None:
        _collect_basepicture_issues(self, bp_path)

    def _collect_typedef_issues(self: Any) -> None:
        _collect_typedef_issues(self)

    def run(
        self: Any,
        apply_alias_back_propagation: bool = True,
        limit_to_module_path: list[str] | None = None,
    ) -> list[VariableIssue]:
        return run(
            self,
            apply_alias_back_propagation=apply_alias_back_propagation,
            limit_to_module_path=limit_to_module_path,
        )

    def _is_external_typename(self: Any, typename: str) -> bool:
        return _is_external_typename(self, typename)

    def _analyze_typedef(self: Any, mt: ModuleTypeDef, path: list[str]) -> None:
        _analyze_typedef(self, mt, path)

    def _apply_alias_back_propagation(self: Any) -> None:
        _apply_alias_back_propagation(self)

    def _analyze_single_module_with_context(
        self: Any,
        mod: _ModuleWithParameters,
        context: ScopeContext,
        path: list[str],
    ) -> tuple[set[str], set[str], set[str], set[str]]:
        return _analyze_single_module_with_context(self, mod, context, path)

    def _analyze_typedef_with_context(
        self: Any,
        mt: ModuleTypeDef,
        context: ScopeContext,
        path: list[str],
    ) -> None:
        _analyze_typedef_with_context(self, mt, context, path)


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
    "VariablesExecutionMixin",
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
