"""Variable usage analysis and reporting utilities."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any, ClassVar

from sattline_parser.models.ast_model import BasePicture, ModuleTypeDef, Variable

from ..reporting.variables_report import (
    DEFAULT_VARIABLE_ANALYSIS_KINDS,
    IssueKind,
    VariableIssue,
    VariablesReport,
)
from ..resolution import CanonicalSymbolTable, TypeGraph
from ..resolution.context_builder import ContextBuilder
from ..resolution.scope import ScopeContext
from ._variables_access import (
    canonical_path,
    collect_effect_sink_keys,
    collect_expression_effect_sources,
    collect_function_input_effect_keys,
    compute_effective_output_keys,
    effect_key_for_variable,
    extract_field_path,
    has_output_effect,
    is_from_root_origin,
    iter_leaf_field_paths_strict,
    lookup_global_variable,
    mapping_source_effect_key,
    mark_record_wide_builtin_access,
    mark_ref_access,
    pop_site,
    push_site,
    record_access,
    record_assignment_effect_flow,
    record_effect_flow,
    record_function_call_effect_flow,
    resolve_effect_key,
    resolve_local_effect_key,
    resolve_mapped_effect_source_key,
    site_str,
    strict_datatype_at_field_prefix,
)
from ._variables_analyzer_facade import VariablesAnalyzerFacadeMixin
from ._variables_contracts import (
    build_anytype_field_contracts,
    build_anytype_parameter_contract,
    check_param_mapping,
    check_param_mappings_for_single,
    check_param_mappings_for_type_instance,
    get_required_parameter_names_for_typedef,
    index_all_variables,
    iter_anytype_typedefs,
)
from ._variables_effect_flow import EffectFlowTracker
from ._variables_execution import (
    analyze_root_scope,
    analyze_single_module_with_context,
    analyze_typedef,
    analyze_typedef_with_context,
    apply_alias_back_propagation,
    collect_basepicture_issues,
    collect_typedef_issues,
    is_external_typename,
    run,
    run_post_traversal_analyses,
)
from ._variables_status import (
    ProcedureStatusBinding,
    add_naming_role_mismatch_issues,
    bind_ignorable_output,
    bind_procedure_status,
    configured_naming_role_patterns,
    has_ignorable_output_binding,
    has_procedure_status_binding,
    matches_naming_role,
    naming_role_mismatch_reason,
    procedure_status_issue,
    propagate_procedure_status_bindings,
    record_ignorable_output_bindings,
    record_procedure_status_bindings,
)
from ._variables_submodules import (
    detect_datatype_duplications,
    display_path_for_child,
    lookup_env_var_from_varname_dict,
    propagate_mapping_to_parent,
    should_walk_submodule_path,
    walk_framemodule_subtree,
    walk_moduletype_instance_subtree,
    walk_singlemodule_subtree,
    walk_submodule_headers,
    walk_submodules,
)
from .usage_tracker import UsageTracker
from .validators import AnyTypeFieldContract, ContractMappingValidator, MinMaxValidator, StringMappingValidator
from .variable_issue_collection import (
    _add_global_scope_minimization_issues,
    _add_hidden_global_coupling_issues,
    _add_high_fan_in_out_issues,
    _add_issue,
    _add_magic_number_issue,
    _add_unused_datatype_field_issues,
    _collect_issues_from_module,
    _iter_variables_for_datatype_field_analysis,
)
from .variable_traversal import (
    _extract_var_basenames_from_tree,
    _handle_function_call,
    _mark_var_by_basename,
    _repath_context,
    _scan_for_varrefs,
    _walk_graph_object,
    _walk_header_enable,
    _walk_header_groupconn,
    _walk_header_invoke_tails,
    _walk_interact_object,
    _walk_module_code,
    _walk_moduledef,
    _walk_seq_nodes,
    _walk_sequence,
    _walk_stmt_or_expr,
    _walk_tail,
    _walk_typedef_groupconn,
)
from .variable_utils import is_const_candidate

if TYPE_CHECKING:
    from ..tracing import AnalysisTraceRecorder

log = logging.getLogger("SattLint")

__all__ = ["ScopeContext", "VariablesAnalyzer", "analyze_variables", "filter_variable_report"]


def analyze_variables(
    base_picture: BasePicture,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
    include_dependency_moduletype_usage: bool = False,
    trace_recorder: AnalysisTraceRecorder | None = None,
    config: dict[str, Any] | None = None,
) -> VariablesReport:
    analyzer = VariablesAnalyzer(
        base_picture,
        debug=debug,
        fail_loudly=False,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
        include_dependency_moduletype_usage=include_dependency_moduletype_usage,
        trace_recorder=trace_recorder,
        config=config,
    )
    issues = analyzer.run()
    return VariablesReport(
        basepicture_name=base_picture.header.name,
        issues=issues,
        visible_kinds=frozenset(DEFAULT_VARIABLE_ANALYSIS_KINDS),
        include_empty_sections=True,
    )


def filter_variable_report(
    report: VariablesReport,
    kinds: set[IssueKind],
) -> VariablesReport:
    if not kinds:
        return report

    filtered = [issue for issue in report.issues if issue.kind in kinds]

    return VariablesReport(
        basepicture_name=report.basepicture_name,
        issues=filtered,
        visible_kinds=frozenset(kinds),
        include_empty_sections=True,
    )


class VariablesAnalyzer(VariablesAnalyzerFacadeMixin):
    """Walk the AST, record variable usage, and emit issue reports."""

    _OPAQUE_BUILTIN_TYPES: ClassVar[set[str]] = {
        "alarm4realspar",
        "arrayobject",
        "eventqueueitem",
        "eventsortrectype",
        "multrealspar",
        "randomgenerator",
        "relaypidtunerpar",
        "sortedeventtype",
    }

    def __init__(
        self,
        base_picture: BasePicture,
        debug: bool = False,
        fail_loudly: bool = True,
        unavailable_libraries: set[str] | None = None,
        analyzed_target_is_library: bool = False,
        include_dependency_moduletype_usage: bool = False,
        trace_recorder: AnalysisTraceRecorder | None = None,
        build_anytype_contracts: bool = True,
        config: dict[str, Any] | None = None,
    ):
        self.bp = base_picture
        self.debug = debug
        self.fail_loudly = fail_loudly
        self._unavailable_libraries = unavailable_libraries or set()
        self._analyzed_target_is_library = analyzed_target_is_library
        self._include_dependency_moduletype_usage = include_dependency_moduletype_usage
        self._analysis_warnings: list[str] = []
        self._trace_recorder = trace_recorder
        self._limit_to_module_path: list[str] | None = None
        self._naming_role_patterns = configured_naming_role_patterns(config)

        self._issues: list[VariableIssue] = []
        self.usage_tracker = UsageTracker()
        self._site_stack: list[str] = []

        self.type_graph = TypeGraph.from_basepicture(self.bp)
        self.symbol_table = CanonicalSymbolTable()
        self.context_builder = ContextBuilder(
            base_picture=self.bp,
            symbol_table=self.symbol_table,
            type_graph=self.type_graph,
            issues=self._issues,
            global_lookup_fn=self._lookup_global_variable,
        )

        self.typedef_index: dict[str, list[ModuleTypeDef]] = {}
        for moduletype in self.bp.moduletype_defs or []:
            self.typedef_index.setdefault(moduletype.name.lower(), []).append(moduletype)
        self.used_params_by_typedef: dict[str, set[str]] = {}
        self.param_reads_by_typedef: dict[str, set[str]] = {}
        self.param_writes_by_typedef: dict[str, set[str]] = {}
        self._alias_links: list[tuple[Variable, Variable, str]] = []
        self._effect_flow_edges: dict[tuple[str, ...], set[tuple[str, ...]]] = defaultdict(set)
        self._effect_flow_display_names: dict[tuple[str, ...], str] = {}
        self._external_effect_sinks: set[tuple[str, ...]] = set()
        self._effective_output_keys: set[tuple[str, ...]] = set()
        self._procedure_status_bindings: dict[int, list[ProcedureStatusBinding]] = defaultdict(list)
        self._ignorable_output_variable_ids: set[int] = set()

        self._effect_flow_tracker = EffectFlowTracker(
            effect_flow_edges=self._effect_flow_edges,
            effect_flow_display_names=self._effect_flow_display_names,
            external_effect_sinks=self._external_effect_sinks,
            effective_output_keys=self._effective_output_keys,
            lookup_global_variable_fn=self._lookup_global_variable,
            get_usage_fn=self._get_usage,
            canonical_path_fn=self._canonical_path,
            record_access_fn=self._record_access,
        )

        self._root_env: dict[str, Variable] = {
            variable.name.lower(): variable for variable in (self.bp.localvariables or [])
        }
        self._any_var_index: dict[str, list[Variable]] = {}
        self._index_all_variables()
        self._analyzing_typedefs: set[str] = set()
        self._anytype_field_contracts_by_owner: dict[int, dict[str, AnyTypeFieldContract]] = {}
        self._required_parameter_names_by_owner: dict[int, dict[str, str]] = {}
        if build_anytype_contracts:
            self._anytype_field_contracts_by_owner = self._build_anytype_field_contracts()

        self._contract_validator = ContractMappingValidator(
            self.type_graph,
            anytype_field_contracts=self._anytype_field_contracts_by_owner,
        )
        self._min_max_validator = MinMaxValidator()
        self._string_validator = StringMappingValidator()

    _repath_context = _repath_context
    _handle_function_call = _handle_function_call
    _walk_header_enable = _walk_header_enable
    _walk_header_invoke_tails = _walk_header_invoke_tails
    _walk_header_groupconn = _walk_header_groupconn
    _walk_typedef_groupconn = _walk_typedef_groupconn
    _walk_moduledef = _walk_moduledef
    _walk_graph_object = _walk_graph_object
    _walk_interact_object = _walk_interact_object
    _scan_for_varrefs = _scan_for_varrefs
    _walk_tail = _walk_tail
    _extract_var_basenames_from_tree = _extract_var_basenames_from_tree
    _mark_var_by_basename = _mark_var_by_basename
    _walk_module_code = _walk_module_code
    _walk_sequence = _walk_sequence
    _walk_seq_nodes = _walk_seq_nodes
    _walk_stmt_or_expr = _walk_stmt_or_expr
    _add_issue = _add_issue
    _iter_variables_for_datatype_field_analysis = _iter_variables_for_datatype_field_analysis
    _add_unused_datatype_field_issues = _add_unused_datatype_field_issues
    _add_hidden_global_coupling_issues = _add_hidden_global_coupling_issues
    _add_high_fan_in_out_issues = _add_high_fan_in_out_issues
    _add_global_scope_minimization_issues = _add_global_scope_minimization_issues
    _add_magic_number_issue = _add_magic_number_issue
    _collect_issues_from_module = _collect_issues_from_module

    _bind_procedure_status = bind_procedure_status
    _bind_ignorable_output = bind_ignorable_output
    _record_procedure_status_bindings = record_procedure_status_bindings
    _record_ignorable_output_bindings = record_ignorable_output_bindings
    _propagate_procedure_status_bindings = propagate_procedure_status_bindings
    _procedure_status_issue = procedure_status_issue
    _has_ignorable_output_binding = has_ignorable_output_binding
    _has_procedure_status_binding = has_procedure_status_binding
    _naming_role_mismatch_reason = naming_role_mismatch_reason
    _matches_naming_role = matches_naming_role
    _add_naming_role_mismatch_issues = add_naming_role_mismatch_issues

    _iter_anytype_typedefs = iter_anytype_typedefs
    _build_anytype_parameter_contract = build_anytype_parameter_contract
    _build_anytype_field_contracts = build_anytype_field_contracts
    _get_required_parameter_names_for_typedef = get_required_parameter_names_for_typedef
    _check_param_mappings_for_single = check_param_mappings_for_single
    _check_param_mappings_for_type_instance = check_param_mappings_for_type_instance
    _check_param_mapping = check_param_mapping
    _index_all_variables = index_all_variables
    _is_const_candidate = is_const_candidate

    _canonical_path = canonical_path
    _record_access = record_access
    _mark_ref_access = mark_ref_access
    _effect_key_for_variable = effect_key_for_variable
    _resolve_effect_key = resolve_effect_key
    _mapping_source_effect_key = mapping_source_effect_key
    _resolve_local_effect_key = resolve_local_effect_key
    _resolve_mapped_effect_source_key = resolve_mapped_effect_source_key
    _record_effect_flow = record_effect_flow
    _collect_function_input_effect_keys = collect_function_input_effect_keys
    _collect_expression_effect_sources = collect_expression_effect_sources
    _record_assignment_effect_flow = record_assignment_effect_flow
    _record_function_call_effect_flow = record_function_call_effect_flow
    _collect_effect_sink_keys = collect_effect_sink_keys
    _compute_effective_output_keys = compute_effective_output_keys
    _has_output_effect = has_output_effect
    _site_str = site_str
    _push_site = push_site
    _pop_site = pop_site
    _strict_datatype_at_field_prefix = strict_datatype_at_field_prefix
    _iter_leaf_field_paths_strict = iter_leaf_field_paths_strict
    _mark_record_wide_builtin_access = mark_record_wide_builtin_access
    _lookup_global_variable = lookup_global_variable
    _is_from_root_origin = is_from_root_origin
    _extract_field_path = extract_field_path

    _analyze_root_scope = analyze_root_scope
    _run_post_traversal_analyses = run_post_traversal_analyses
    _collect_basepicture_issues = collect_basepicture_issues
    _collect_typedef_issues = collect_typedef_issues
    run = run
    _is_external_typename = is_external_typename
    _analyze_typedef = analyze_typedef
    _apply_alias_back_propagation = apply_alias_back_propagation
    _analyze_single_module_with_context = analyze_single_module_with_context
    _analyze_typedef_with_context = analyze_typedef_with_context

    _should_walk_submodule_path = should_walk_submodule_path
    _display_path_for_child = display_path_for_child
    _walk_submodule_headers = walk_submodule_headers
    _walk_singlemodule_subtree = walk_singlemodule_subtree
    _walk_framemodule_subtree = walk_framemodule_subtree
    _walk_moduletype_instance_subtree = walk_moduletype_instance_subtree
    _walk_submodules = walk_submodules
    _propagate_mapping_to_parent = propagate_mapping_to_parent
    _lookup_env_var_from_varname_dict = lookup_env_var_from_varname_dict
    _detect_datatype_duplications = detect_datatype_duplications

    def _warn(self, message: str) -> None:
        self._analysis_warnings.append(message)
        if self.debug:
            log.warning(message)
        self._trace("warning", message=message)

    def warn(self, message: str) -> None:
        self._warn(message)

    def trace(self, action: str, **data: Any) -> None:
        self._trace(action, **data)

    def _trace(self, action: str, **data: Any) -> None:
        if self._trace_recorder is None:
            return
        self._trace_recorder.event("variables", action, **data)

    def _append_issue(self, issue: VariableIssue) -> None:
        self._issues.append(issue)
        self._trace(
            "issue",
            kind=issue.kind.value,
            module_path=issue.module_path,
            variable=(issue.variable.name if issue.variable is not None else None),
            role=issue.role,
            field_path=issue.field_path,
            site=issue.site,
        )
