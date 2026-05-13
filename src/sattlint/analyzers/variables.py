"""Variable usage analysis and reporting utilities."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any, ClassVar

from sattline_parser.models.ast_model import BasePicture, ModuleTypeDef, Variable

from ..models.usage import VariableUsage
from ..reporting.variables_report import (
    DEFAULT_VARIABLE_ANALYSIS_KINDS,
    IssueKind,
    VariableIssue,
    VariablesReport,
)
from ..resolution import AccessGraph, CanonicalSymbolTable, TypeGraph
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
from ._variables_contracts import (
    build_anytype_field_contracts,
    build_anytype_parameter_contract,
    check_param_mapping,
    check_param_mappings_for_single,
    check_param_mappings_for_type_instance,
    get_required_parameter_names_for_typedef,
    index_all_variables,
    is_const_candidate,
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


class VariablesAnalyzer:
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

    def _get_usage(self, variable: Variable) -> VariableUsage:
        return self.usage_tracker.get_usage(variable)

    def get_usage(self, variable: Variable) -> VariableUsage:
        return self._get_usage(variable)

    @property
    def access_graph(self) -> AccessGraph:
        return self.usage_tracker.access_graph

    @property
    def analyzed_target_is_library(self) -> bool:
        return self._analyzed_target_is_library

    @property
    def limit_to_module_path(self) -> list[str] | None:
        return self._limit_to_module_path

    @property
    def unavailable_libraries(self) -> set[str]:
        return self._unavailable_libraries

    @property
    def include_dependency_moduletype_usage(self) -> bool:
        return self._include_dependency_moduletype_usage

    @property
    def alias_links(self) -> list[tuple[Variable, Variable, str]]:
        return self._alias_links

    @property
    def procedure_status_bindings(self) -> dict[int, list[ProcedureStatusBinding]]:
        return self._procedure_status_bindings

    @property
    def ignorable_output_variable_ids(self) -> set[int]:
        return self._ignorable_output_variable_ids

    @property
    def naming_role_patterns(self) -> dict[str, Any]:
        return self._naming_role_patterns

    @property
    def any_var_index(self) -> dict[str, list[Variable]]:
        return self._any_var_index

    @property
    def required_parameter_names_by_owner(self) -> dict[int, dict[str, str]]:
        return self._required_parameter_names_by_owner

    @property
    def contract_validator(self) -> ContractMappingValidator:
        return self._contract_validator

    @property
    def min_max_validator(self) -> MinMaxValidator:
        return self._min_max_validator

    @property
    def string_validator(self) -> StringMappingValidator:
        return self._string_validator

    @property
    def analyzing_typedefs(self) -> set[str]:
        return self._analyzing_typedefs

    @property
    def effect_flow_tracker(self) -> EffectFlowTracker:
        return self._effect_flow_tracker

    @property
    def effective_output_keys(self) -> set[tuple[str, ...]]:
        return self._effective_output_keys

    @property
    def site_stack(self) -> list[str]:
        return self._site_stack

    @property
    def root_env(self) -> dict[str, Variable]:
        return self._root_env

    @property
    def opaque_builtin_types(self) -> set[str]:
        return type(self)._OPAQUE_BUILTIN_TYPES

    @property
    def effect_flow_edges(self) -> dict[tuple[str, ...], tuple[tuple[str, ...], ...]]:
        return {source_key: tuple(sorted(target_keys)) for source_key, target_keys in self._effect_flow_edges.items()}

    @property
    def effect_flow_display_names(self) -> dict[tuple[str, ...], str]:
        return dict(self._effect_flow_display_names)

    @property
    def analysis_warnings(self) -> list[str]:
        return self._analysis_warnings

    def _warn(self, message: str) -> None:
        self._analysis_warnings.append(message)
        if self.debug:
            log.warning(message)
        self._trace("warning", message=message)

    def warn(self, message: str) -> None:
        self._warn(message)

    @property
    def issues(self) -> list[VariableIssue]:
        return self._issues

    def trace(self, action: str, **data: Any) -> None:
        self._trace(action, **data)

    def _trace(self, action: str, **data: Any) -> None:
        if self._trace_recorder is None:
            return
        self._trace_recorder.event("variables", action, **data)

    def append_issue(self, issue: VariableIssue) -> None:
        self._append_issue(issue)

    def add_issue(
        self,
        kind: IssueKind,
        module_path: list[str],
        variable: Variable,
        *,
        role: str = "",
        field_path: str | None = None,
    ) -> None:
        self._add_issue(kind, module_path, variable, role=role, field_path=field_path)

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

    def is_from_root_origin(self, origin_file: str | None, origin_lib: str | None = None) -> bool:
        return self._is_from_root_origin(origin_file, origin_lib)

    def has_output_effect(self, variable: Variable, path: list[str]) -> bool:
        return self._has_output_effect(variable, path)

    def has_procedure_status_binding(self, variable: Variable) -> bool:
        return self._has_procedure_status_binding(variable)

    def has_ignorable_output_binding(self, variable: Variable) -> bool:
        return self._has_ignorable_output_binding(variable)

    def procedure_status_issue(self, variable: Variable, usage: VariableUsage) -> tuple[str, str | None] | None:
        return self._procedure_status_issue(variable, usage)

    def is_const_candidate(self, variable: Variable) -> bool:
        return self._is_const_candidate(variable)

    def site_str(self) -> str | None:
        return self._site_str()

    def bind_procedure_status(
        self,
        full_ref: str,
        *,
        call_name: str,
        parameter: Any,
        context: ScopeContext,
    ) -> None:
        self._bind_procedure_status(
            full_ref,
            call_name=call_name,
            parameter=parameter,
            context=context,
        )

    def bind_ignorable_output(
        self,
        full_ref: str,
        *,
        context: ScopeContext,
    ) -> None:
        self._bind_ignorable_output(full_ref, context=context)

    def matches_naming_role(self, name_key: str, role_name: str) -> bool:
        return self._matches_naming_role(name_key, role_name)

    def naming_role_mismatch_reason(
        self,
        variable: Variable,
        usage: VariableUsage,
        decl_path: list[str],
    ) -> str | None:
        return self._naming_role_mismatch_reason(variable, usage, decl_path)

    def iter_anytype_typedefs(self) -> list[ModuleTypeDef]:
        return self._iter_anytype_typedefs()

    def build_anytype_parameter_contract(
        self,
        extractor: Any,
        variable: Variable,
    ) -> AnyTypeFieldContract | None:
        return self._build_anytype_parameter_contract(extractor, variable)

    def get_required_parameter_names_for_typedef(self, moduletype: ModuleTypeDef) -> dict[str, str]:
        return self._get_required_parameter_names_for_typedef(moduletype)

    def analyze_typedef(self, moduletype: ModuleTypeDef, path: list[str]) -> None:
        self._analyze_typedef(moduletype, path)

    def analyze_typedef_with_context(
        self,
        moduletype: ModuleTypeDef,
        context: ScopeContext,
        path: list[str],
    ) -> None:
        self._analyze_typedef_with_context(moduletype, context, path)

    def is_external_typename(self, typename: str) -> bool:
        return self._is_external_typename(typename)

    def check_param_mapping(
        self,
        pm: Any,
        tgt_var: Variable | None,
        parent_env: dict[str, Variable],
        path: list[str],
        *,
        owner_contract_id: int | None = None,
    ) -> None:
        self._check_param_mapping(
            pm,
            tgt_var,
            parent_env,
            path,
            owner_contract_id=owner_contract_id,
        )

    def lookup_env_var_from_varname_dict(
        self,
        var_dict_or_other: Any,
        env: dict[str, Variable],
    ) -> Variable | None:
        return self._lookup_env_var_from_varname_dict(var_dict_or_other, env)

    def lookup_global_variable(self, var_ref: str | None) -> Variable | None:
        return self._lookup_global_variable(var_ref)

    def repath_context(
        self,
        parent_context: ScopeContext,
        module_path: list[str],
        display_module_path: list[str],
    ) -> ScopeContext:
        return self._repath_context(
            parent_context,
            module_path=module_path,
            display_module_path=display_module_path,
        )

    def walk_header_enable(self, header: Any, context: ScopeContext, path: list[str]) -> None:
        self._walk_header_enable(header, context, path)

    def walk_header_invoke_tails(self, header: Any, context: ScopeContext, path: list[str]) -> None:
        self._walk_header_invoke_tails(header, context, path)

    def walk_header_groupconn(self, header: Any, context: ScopeContext, path: list[str]) -> None:
        self._walk_header_groupconn(header, context, path)

    def walk_moduledef(self, moduledef: Any, context: ScopeContext, path: list[str]) -> None:
        self._walk_moduledef(moduledef, context, path)

    def walk_module_code(self, modulecode: Any, context: ScopeContext, path: list[str]) -> None:
        self._walk_module_code(modulecode, context, path)

    def check_param_mappings_for_single(
        self,
        mod: Any,
        child_env: dict[str, Variable],
        parent_env: dict[str, Variable],
        parent_path: list[str],
    ) -> None:
        self._check_param_mappings_for_single(mod, child_env, parent_env, parent_path)

    def check_param_mappings_for_type_instance(
        self,
        inst: Any,
        parent_env: dict[str, Variable],
        parent_path: list[str],
        current_library: str | None = None,
    ) -> None:
        self._check_param_mappings_for_type_instance(
            inst,
            parent_env,
            parent_path,
            current_library=current_library,
        )
