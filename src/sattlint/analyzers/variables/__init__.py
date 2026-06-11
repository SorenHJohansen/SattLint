"""Variable usage analysis and reporting utilities."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from collections.abc import Callable, Generator
from collections.abc import Set as AbstractSet
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, ClassVar

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    SingleModule,
    Variable,
)

from ...reporting.variables_report import (
    DEFAULT_VARIABLE_ANALYSIS_KINDS,
    IssueKind,
    VariableIssue,
    VariablesReport,
)
from ...resolution import CanonicalSymbolTable, TypeGraph
from ...resolution.context_builder import ContextBuilder
from ...resolution.scope import ScopeContext
from ..framework import AnalysisContext, AnalysisSharedArtifacts, AnalyzerLifecycleMixin, VariableAnalysisArtifacts
from ..shared._dedupe import get_or_register_index
from ..shared._validators import AnyTypeFieldContract, ContractMappingValidator, MinMaxValidator, StringMappingValidator
from ..shared.variable_utils import VariablesConstMixin
from ._usage_tracker import UsageTracker
from ._variable_issue_collection import VariablesIssueCollectionMixin
from ._variable_traversal import VariablesTraversalMixin
from ._variables_access import VariablesAccessMixin
from ._variables_analyzer_facade import VariablesAnalyzerFacadeMixin
from ._variables_contracts import VariablesContractsMixin
from ._variables_effect_flow import EffectFlowTracker
from ._variables_execution import VariablesExecutionMixin
from ._variables_status import ProcedureStatusBinding, VariablesStatusMixin, configured_naming_role_patterns
from ._variables_submodules import VariablesSubmodulesMixin

if TYPE_CHECKING:
    from ...tracing import AnalysisTraceRecorder

log = logging.getLogger("SattLint")

__all__ = ["ScopeContext", "VariablesAnalyzer", "analyze_variables", "filter_variable_report"]


def _collect_module_vars_for_artifacts(module: object, any_var_index: dict[str, list[Variable]]) -> None:
    if isinstance(module, SingleModule):
        for variable in module.moduleparameters or []:
            any_var_index.setdefault(variable.name.lower(), []).append(variable)
        for variable in module.localvariables or []:
            any_var_index.setdefault(variable.name.lower(), []).append(variable)
        for child in module.submodules or []:
            _collect_module_vars_for_artifacts(child, any_var_index)
        return
    if isinstance(module, FrameModule):
        for child in module.submodules or []:
            _collect_module_vars_for_artifacts(child, any_var_index)
        return
    if isinstance(module, ModuleTypeInstance):
        return


def _build_variable_analysis_artifacts(base_picture: BasePicture) -> VariableAnalysisArtifacts:
    typedef_index: dict[str, list[ModuleTypeDef]] = {}
    dependency_library_display_names: dict[str, str] = {}

    root_origin_lib = getattr(base_picture, "origin_lib", None)
    if root_origin_lib:
        dependency_library_display_names[root_origin_lib.casefold()] = root_origin_lib

    for moduletype in base_picture.moduletype_defs or []:
        typedef_index.setdefault(moduletype.name.lower(), []).append(moduletype)
        if moduletype.origin_lib:
            dependency_library_display_names.setdefault(moduletype.origin_lib.casefold(), moduletype.origin_lib)

    for datatype in base_picture.datatype_defs or []:
        origin_lib = getattr(datatype, "origin_lib", None)
        if origin_lib:
            dependency_library_display_names.setdefault(origin_lib.casefold(), origin_lib)

    root_env = {variable.name.lower(): variable for variable in (base_picture.localvariables or [])}
    any_var_index: dict[str, list[Variable]] = {}
    for variable in base_picture.localvariables or []:
        any_var_index.setdefault(variable.name.lower(), []).append(variable)
    for module in base_picture.submodules or []:
        _collect_module_vars_for_artifacts(module, any_var_index)
    for moduletype in base_picture.moduletype_defs or []:
        for variable in moduletype.moduleparameters or []:
            any_var_index.setdefault(variable.name.lower(), []).append(variable)
        for variable in moduletype.localvariables or []:
            any_var_index.setdefault(variable.name.lower(), []).append(variable)

    return VariableAnalysisArtifacts(
        type_graph=TypeGraph.from_basepicture(base_picture),
        typedef_index={key: tuple(values) for key, values in typedef_index.items()},
        dependency_library_display_names=dict(dependency_library_display_names),
        root_env=dict(root_env),
        any_var_index={key: tuple(values) for key, values in any_var_index.items()},
    )


def analyze_variables(
    base_picture: BasePicture,
    analysis_context: AnalysisContext | None = None,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
    include_dependency_moduletype_usage: bool | None = None,
    selected_issue_kinds: AbstractSet[IssueKind | str] | None = None,
    trace_recorder: AnalysisTraceRecorder | None = None,
    config: dict[str, Any] | None = None,
    status_update_fn: Callable[[str], None] | None = None,
) -> VariablesReport:
    effective_include_dependency_moduletype_usage = (
        analyzed_target_is_library
        if include_dependency_moduletype_usage is None
        else include_dependency_moduletype_usage
    )
    normalized_selected_issue_kinds = _normalize_selected_issue_kinds(selected_issue_kinds)
    init_started_at = time.perf_counter()
    analyzer = VariablesAnalyzer(
        base_picture,
        debug=debug,
        fail_loudly=False,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
        include_dependency_moduletype_usage=effective_include_dependency_moduletype_usage,
        selected_issue_kinds=normalized_selected_issue_kinds,
        trace_recorder=trace_recorder,
        config=config,
        status_update_fn=status_update_fn,
        shared_artifacts=(analysis_context.shared_artifacts if analysis_context is not None else None),
    )
    init_duration_ms = round((time.perf_counter() - init_started_at) * 1000, 3)
    issues = analyzer.run()
    return VariablesReport(
        basepicture_name=base_picture.header.name,
        issues=issues,
        accesses_by_definition_key={key: tuple(events) for key, events in analyzer.access_graph.by_path_key.items()},
        effect_flow_edges=analyzer.effect_flow_edges,
        effect_flow_display_names=analyzer.effect_flow_display_names,
        selected_issue_kinds=normalized_selected_issue_kinds,
        visible_kinds=(
            normalized_selected_issue_kinds
            if normalized_selected_issue_kinds is not None
            else frozenset(DEFAULT_VARIABLE_ANALYSIS_KINDS)
        ),
        include_empty_sections=True,
        phase_timings=[
            {"phase": "analyzer-init", "duration_ms": init_duration_ms},
            *analyzer.phase_timings,
        ],
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
        accesses_by_definition_key=dict(report.accesses_by_definition_key),
        effect_flow_edges=dict(report.effect_flow_edges),
        effect_flow_display_names=dict(report.effect_flow_display_names),
        selected_issue_kinds=frozenset(kinds),
        visible_kinds=frozenset(kinds),
        include_empty_sections=True,
        phase_timings=list(report.phase_timings),
    )


def _normalize_selected_issue_kinds(
    selected_issue_kinds: AbstractSet[IssueKind | str] | None,
) -> frozenset[IssueKind] | None:
    if selected_issue_kinds is None:
        return None

    normalized: set[IssueKind] = set()
    for raw_kind in selected_issue_kinds:
        if isinstance(raw_kind, IssueKind):
            normalized.add(raw_kind)
            continue
        try:
            normalized.add(IssueKind(str(raw_kind)))
        except ValueError:
            continue
    return frozenset(normalized)


def _issue_uses_typedef_path(issue: VariableIssue) -> bool:
    return any(segment.startswith("TypeDef:") for segment in issue.module_path)


def _string_mapping_issue_preference(issue: VariableIssue) -> tuple[int, int]:
    source_decl_module_path = issue.source_decl_module_path or issue.module_path
    declaration_distance = max(0, len(issue.module_path) - len(source_decl_module_path))
    return declaration_distance, 1 if _issue_uses_typedef_path(issue) else 0


class VariablesAnalyzer(
    AnalyzerLifecycleMixin,
    VariablesAnalyzerFacadeMixin,
    VariablesIssueCollectionMixin,
    VariablesTraversalMixin,
    VariablesAccessMixin,
    VariablesContractsMixin,
    VariablesStatusMixin,
    VariablesSubmodulesMixin,
    VariablesExecutionMixin,
    VariablesConstMixin,
):
    """Walk the AST, record variable usage, and emit issue reports."""

    _OPAQUE_BUILTIN_TYPES: ClassVar[set[str]] = {
        "eventsortrectype",
        "sortedeventtype",
    }

    def _resolve_variable_artifacts(
        self,
        shared_artifacts: AnalysisSharedArtifacts | None,
    ) -> VariableAnalysisArtifacts:
        variable_artifacts = shared_artifacts.variable_analysis if shared_artifacts is not None else None
        if variable_artifacts is not None:
            return variable_artifacts

        variable_artifacts = _build_variable_analysis_artifacts(self.bp)
        if shared_artifacts is not None:
            shared_artifacts.variable_analysis = variable_artifacts
            shared_artifacts.counters.variable_foundation_builds += 1
        return variable_artifacts

    def _initialize_usage_state(self) -> None:
        self._issues: list[VariableIssue] = []
        self._param_mapping_issue_indexes: dict[tuple[IssueKind, int], int] = {}
        self._record_component_order_datatypes_seen: set[str] = set()
        self.usage_tracker = UsageTracker()
        self._site_stack: list[str] = []

    def _initialize_artifact_state(
        self,
        variable_artifacts: VariableAnalysisArtifacts,
        *,
        build_anytype_contracts: bool,
    ) -> None:
        self.typedef_index = {key: list(values) for key, values in variable_artifacts.typedef_index.items()}
        self._used_dependency_libraries: set[str] = set()
        self._dependency_library_display_names = dict(variable_artifacts.dependency_library_display_names)
        self.used_params_by_typedef: dict[str, set[str]] = {}
        self.param_reads_by_typedef: dict[str, set[str]] = {}
        self.param_ui_reads_by_typedef: dict[str, set[str]] = {}
        self.param_non_ui_reads_by_typedef: dict[str, set[str]] = {}
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
        self._contexts_by_module_path: dict[tuple[str, ...], ScopeContext] = {}
        self._root_env = dict(variable_artifacts.root_env)
        self._any_var_index = {key: list(values) for key, values in variable_artifacts.any_var_index.items()}
        self._analyzing_typedefs: set[str] = set()
        self._anytype_field_contracts_by_owner: dict[int, dict[str, AnyTypeFieldContract]] = {}
        self._required_parameter_names_by_owner: dict[int, dict[str, str]] = {}
        self._array_element_datatypes_by_key: dict[tuple[str, ...], Simple_DataType | str] = {}
        should_build_anytype_contracts = build_anytype_contracts and (
            self._selected_issue_kinds is None or IssueKind.CONTRACT_MISMATCH in self._selected_issue_kinds
        )
        if should_build_anytype_contracts:
            self._anytype_field_contracts_by_owner = self._build_anytype_field_contracts()

        self._contract_validator = ContractMappingValidator(
            self.type_graph,
            anytype_field_contracts=self._anytype_field_contracts_by_owner,
        )
        self._min_max_validator = MinMaxValidator()
        self._string_validator = StringMappingValidator()

    def __init__(
        self,
        base_picture: BasePicture,
        debug: bool = False,
        fail_loudly: bool = True,
        unavailable_libraries: set[str] | None = None,
        analyzed_target_is_library: bool = False,
        include_dependency_moduletype_usage: bool = False,
        selected_issue_kinds: AbstractSet[IssueKind | str] | None = None,
        trace_recorder: AnalysisTraceRecorder | None = None,
        build_anytype_contracts: bool = True,
        config: dict[str, Any] | None = None,
        status_update_fn: Callable[[str], None] | None = None,
        shared_artifacts: AnalysisSharedArtifacts | None = None,
    ):
        self.bp = base_picture
        self.debug = debug
        self.fail_loudly = fail_loudly
        self._unavailable_libraries = unavailable_libraries or set()
        self._analyzed_target_is_library = analyzed_target_is_library
        self._include_dependency_moduletype_usage = include_dependency_moduletype_usage
        self._selected_issue_kinds = _normalize_selected_issue_kinds(selected_issue_kinds)
        self._analysis_warnings: list[str] = []
        self._initialize_lifecycle(
            trace_namespace="variables",
            trace_recorder=trace_recorder,
            status_update_fn=status_update_fn,
            status_prefix="Analyzing variable issues",
        )
        self._shared_artifacts = shared_artifacts
        self._suppress_param_mapping_validation_depth = 0
        self._limit_to_module_path: list[str] | None = None
        self._unresolved_variable_lookup_total = 0
        self._unresolved_variable_lookup_counts: dict[str, int] = defaultdict(int)
        self._unresolved_variable_lookup_examples: dict[str, tuple[int, str]] = {}
        self._naming_role_patterns = configured_naming_role_patterns(config)
        self._root_variable_access_summary_cache_token: tuple[int, int] | None = None
        self._root_variable_access_summary_cache: dict[str, Any] = {}
        self._initialize_usage_state()

        variable_artifacts = self._resolve_variable_artifacts(shared_artifacts)

        self.type_graph = variable_artifacts.type_graph
        self.symbol_table = CanonicalSymbolTable()
        self.context_builder = ContextBuilder(
            base_picture=self.bp,
            symbol_table=self.symbol_table,
            type_graph=self.type_graph,
            issues=self._issues,
            global_lookup_fn=self._lookup_global_variable,
        )
        self._initialize_artifact_state(
            variable_artifacts,
            build_anytype_contracts=build_anytype_contracts,
        )

    def _warn(self, message: str) -> None:
        self._analysis_warnings.append(message)
        if self.debug:
            log.warning(message)
        self._trace("warning", message=message)

    def warn(self, message: str) -> None:
        self._warn(message)

    @contextmanager
    def divert_issue_collection(self) -> Generator[None]:
        diverted_issues = self._issues
        diverted_indexes = self._param_mapping_issue_indexes
        diverted_context_issues = self.context_builder.issues
        temp_issues: list[VariableIssue] = []
        self._issues = temp_issues
        self._param_mapping_issue_indexes = {}
        self.context_builder.issues = temp_issues
        self._suppress_param_mapping_validation_depth += 1
        try:
            yield
        finally:
            self._suppress_param_mapping_validation_depth -= 1
            self._issues = diverted_issues
            self._param_mapping_issue_indexes = diverted_indexes
            self.context_builder.issues = diverted_context_issues

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

    def _append_param_mapping_issue(self, mapping: ParameterMapping, issue: VariableIssue) -> None:
        dedupe_key = (issue.kind, id(mapping))
        existing_index = get_or_register_index(
            self._param_mapping_issue_indexes,
            dedupe_key,
            len(self._issues),
        )
        if existing_index is None:
            self._append_issue(issue)
            return

        existing_issue = self._issues[existing_index]
        if issue.kind is IssueKind.STRING_MAPPING_MISMATCH:
            if _string_mapping_issue_preference(issue) > _string_mapping_issue_preference(existing_issue):
                self._issues[existing_index] = issue
                self._trace(
                    "issue-deduped",
                    kind=issue.kind.value,
                    module_path=issue.module_path,
                    replaced_module_path=existing_issue.module_path,
                    variable=(issue.variable.name if issue.variable is not None else None),
                )
            return
        if _issue_uses_typedef_path(issue) and not _issue_uses_typedef_path(existing_issue):
            self._issues[existing_index] = issue
            self._trace(
                "issue-deduped",
                kind=issue.kind.value,
                module_path=issue.module_path,
                replaced_module_path=existing_issue.module_path,
                variable=(issue.variable.name if issue.variable is not None else None),
            )
