"""Variable usage analysis and reporting utilities."""

from __future__ import annotations

import difflib
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from ..call_signatures import CallParameterSignature, resolve_call_signature
from ..grammar import constants as const
from ..models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    SingleModule,
    Variable,
)
from ..models.usage import VariableUsage
from ..reporting.variables_report import (
    DEFAULT_VARIABLE_ANALYSIS_KINDS,
    IssueKind,
    VariableIssue,
    VariablesReport,
)
from ..resolution import (
    AccessGraph,
    AccessKind,
    CanonicalPath,
    CanonicalSymbolTable,
    TypeGraph,
    decorate_segment,
)
from ..resolution.common import (
    path_startswith_casefold,
    resolve_moduletype_def_strict,
    varname_base,
)
from ..resolution.context_builder import ContextBuilder
from ..resolution.scope import ScopeContext
from .reset_contamination import detect_implicit_latching, detect_reset_contamination
from .sattline_builtins import get_function_signature
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


@dataclass(frozen=True)
class _NamingRolePatterns:
    prefixes: tuple[str, ...] = ()
    suffixes: tuple[str, ...] = ()


_DEFAULT_NAMING_ROLE_PATTERNS: dict[str, _NamingRolePatterns] = {
    "command": _NamingRolePatterns(suffixes=("cmd",)),
    "status": _NamingRolePatterns(suffixes=("status",)),
    "alarm": _NamingRolePatterns(suffixes=("alarm",)),
}


def _normalize_role_pattern_values(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    values: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        value = item.strip().casefold()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return tuple(values)


def _configured_naming_role_patterns(
    config: dict[str, Any] | None,
) -> dict[str, _NamingRolePatterns]:
    patterns = dict(_DEFAULT_NAMING_ROLE_PATTERNS)
    if not isinstance(config, dict):
        return patterns

    analysis = config.get("analysis", {})
    if not isinstance(analysis, dict):
        return patterns

    naming = analysis.get("naming", {})
    if not isinstance(naming, dict):
        return patterns

    raw_role_patterns = naming.get("role_patterns", {})
    if not isinstance(raw_role_patterns, dict):
        return patterns

    for role_name, defaults in _DEFAULT_NAMING_ROLE_PATTERNS.items():
        raw_rule = raw_role_patterns.get(role_name, {})
        if not isinstance(raw_rule, dict):
            continue
        prefixes = tuple(
            dict.fromkeys((*defaults.prefixes, *_normalize_role_pattern_values(raw_rule.get("prefixes", []))))
        )
        suffixes = tuple(
            dict.fromkeys((*defaults.suffixes, *_normalize_role_pattern_values(raw_rule.get("suffixes", []))))
        )
        patterns[role_name] = _NamingRolePatterns(prefixes=prefixes, suffixes=suffixes)

    return patterns


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


def analyze_variables(
    base_picture: BasePicture,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
    include_dependency_moduletype_usage: bool = False,
    trace_recorder: AnalysisTraceRecorder | None = None,
    config: dict[str, Any] | None = None,
) -> VariablesReport:
    """
    Analyze a BasePicture AST and return a comprehensive report:
      - UNUSED variables
      - READ_ONLY_NON_CONST variables

    Variable.read / Variable.written are populated during traversal [3], and
    Variable itself remains the core AST (no report concerns baked in) [1].
    """
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

    filtered = [i for i in report.issues if i.kind in kinds]

    return VariablesReport(
        basepicture_name=report.basepicture_name,
        issues=filtered,
        visible_kinds=frozenset(kinds),
        include_empty_sections=True,
    )


@dataclass(frozen=True)
class _ProcedureStatusBinding:
    call_name: str
    parameter_name: str
    channel_kind: str
    field_path: str | None = None


class VariablesAnalyzer:
    """
    Walks the AST and marks VariableUsage.read / VariableUsage.written.
    Propagates usage through ParameterMappings into child modules.
    GLOBAL mapping resolves by walking up the scope chain and only counts
    as used when the mapped parameter is read/written in the child.
    External ModuleTypeInstance mappings are considered used.
    """

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
        self._naming_role_patterns = _configured_naming_role_patterns(config)

        # Unified collection of issues
        self._issues: list[VariableIssue] = []

        # Decoupled usage tracking
        self.usage_tracker = UsageTracker()

        # Traversal context for better error messages (equation/sequence/step/etc.)
        self._site_stack: list[str] = []

        # Resolution layers
        self.type_graph = TypeGraph.from_basepicture(self.bp)
        self.symbol_table = CanonicalSymbolTable()
        # self.access_graph is now managed by UsageTracker

        self.context_builder = ContextBuilder(
            base_picture=self.bp,
            symbol_table=self.symbol_table,
            type_graph=self.type_graph,
            issues=self._issues,
            global_lookup_fn=self._lookup_global_variable,
        )

        self.typedef_index: dict[str, list[ModuleTypeDef]] = {}
        for mt in self.bp.moduletype_defs or []:
            self.typedef_index.setdefault(mt.name.lower(), []).append(mt)
        self.used_params_by_typedef: dict[str, set[str]] = {}
        self.param_reads_by_typedef: dict[str, set[str]] = {}
        self.param_writes_by_typedef: dict[str, set[str]] = {}
        self._alias_links: list[
            tuple[Variable, Variable, str]
        ] = []  # (parent_var, child_param_var, field_path_in_parent)
        self._effect_flow_edges: dict[tuple[str, ...], set[tuple[str, ...]]] = defaultdict(set)
        self._effect_flow_display_names: dict[tuple[str, ...], str] = {}
        self._external_effect_sinks: set[tuple[str, ...]] = set()
        self._effective_output_keys: set[tuple[str, ...]] = set()
        self._procedure_status_bindings: dict[int, list[_ProcedureStatusBinding]] = defaultdict(list)

        # Index BasePicture/global variables (localvariables)
        self._root_env: dict[str, Variable] = {v.name.lower(): v for v in (self.bp.localvariables or [])}

        # Fallback index across the whole AST (by name) to be robust
        self._any_var_index: dict[str, list[Variable]] = {}
        self._index_all_variables()
        self._analyzing_typedefs: set[str] = set()
        self._anytype_field_contracts_by_owner: dict[int, dict[str, AnyTypeFieldContract]] = {}
        self._required_parameter_names_by_owner: dict[int, dict[str, str]] = {}
        if build_anytype_contracts:
            self._anytype_field_contracts_by_owner = self._build_anytype_field_contracts()

        # Load dedicated validators
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

    def _build_anytype_field_contracts(self) -> dict[int, dict[str, AnyTypeFieldContract]]:
        typedefs_with_anytype = [
            typedef
            for typedef in (self.bp.moduletype_defs or [])
            if any(
                isinstance(variable.datatype, str) and variable.datatype.casefold() == "anytype"
                for variable in (typedef.moduleparameters or [])
            )
        ]
        if not typedefs_with_anytype:
            return {}

        extractor = VariablesAnalyzer(
            self.bp,
            debug=False,
            fail_loudly=False,
            unavailable_libraries=self._unavailable_libraries,
            analyzed_target_is_library=self._analyzed_target_is_library,
            include_dependency_moduletype_usage=self._include_dependency_moduletype_usage,
            trace_recorder=None,
            build_anytype_contracts=False,
        )
        contracts: dict[int, dict[str, AnyTypeFieldContract]] = {}

        for typedef in typedefs_with_anytype:
            extractor._analyze_typedef(
                typedef,
                path=[self.bp.header.name, f"TypeDef:{typedef.name}"],
            )

            parameter_contracts: dict[str, AnyTypeFieldContract] = {}
            for variable in typedef.moduleparameters or []:
                if not (isinstance(variable.datatype, str) and variable.datatype.casefold() == "anytype"):
                    continue

                usage = extractor._get_usage(variable)
                field_paths = sorted(set((usage.field_reads or {}).keys()) | set((usage.field_writes or {}).keys()))
                if not field_paths:
                    continue

                parameter_contracts[variable.name.casefold()] = AnyTypeFieldContract(field_paths=tuple(field_paths))

            if parameter_contracts:
                contracts[id(typedef)] = parameter_contracts

        return contracts

    def _get_usage(self, variable: Variable) -> VariableUsage:
        return self.usage_tracker.get_usage(variable)

    def _get_required_parameter_names_for_typedef(
        self,
        moduletype: ModuleTypeDef,
    ) -> dict[str, str]:
        owner_id = id(moduletype)
        cached = self._required_parameter_names_by_owner.get(owner_id)
        if cached is not None:
            return cached

        extractor = VariablesAnalyzer(
            self.bp,
            debug=False,
            fail_loudly=False,
            unavailable_libraries=self._unavailable_libraries,
            analyzed_target_is_library=self._analyzed_target_is_library,
            include_dependency_moduletype_usage=self._include_dependency_moduletype_usage,
            trace_recorder=None,
            build_anytype_contracts=False,
        )
        extractor._analyze_typedef(
            moduletype,
            path=[self.bp.header.name, f"TypeDef:{moduletype.name}"],
        )

        required_names: dict[str, str] = {}
        for variable in moduletype.moduleparameters or []:
            usage = extractor._get_usage(variable)
            if not (usage.read or usage.written):
                continue
            if usage.is_display_only:
                continue
            required_names[variable.name.casefold()] = variable.name

        self._required_parameter_names_by_owner[owner_id] = required_names
        return required_names

    @property
    def access_graph(self) -> AccessGraph:
        return self.usage_tracker.access_graph

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

    @property
    def issues(self) -> list[VariableIssue]:
        return self._issues

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

    def _bind_procedure_status(
        self,
        full_ref: str,
        *,
        call_name: str,
        parameter: CallParameterSignature,
        context: ScopeContext,
    ) -> None:
        resolved_var, resolved_field_path, _decl_path, _decl_display = context.resolve_variable(full_ref)
        if resolved_var is None:
            return

        binding = _ProcedureStatusBinding(
            call_name=call_name,
            parameter_name=parameter.name,
            channel_kind=parameter.channel_kind or "status",
            field_path=resolved_field_path or None,
        )
        bindings = self._procedure_status_bindings[id(resolved_var)]
        if binding not in bindings:
            bindings.append(binding)

    def _record_procedure_status_bindings(
        self,
        fn_name: str,
        args: list[Any],
        context: ScopeContext,
    ) -> None:
        signature = resolve_call_signature(fn_name)
        if signature is None:
            return

        for index, parameter in enumerate(signature.parameters):
            if not parameter.is_status_channel or index >= len(args):
                continue
            argument = args[index]
            if not (isinstance(argument, dict) and const.KEY_VAR_NAME in argument):
                continue
            self._bind_procedure_status(
                argument[const.KEY_VAR_NAME],
                call_name=fn_name,
                parameter=parameter,
                context=context,
            )

    def _propagate_procedure_status_bindings(self) -> None:
        for source_var, target_var, mapping_name in self._alias_links:
            propagated: list[_ProcedureStatusBinding] = []
            for binding in self._procedure_status_bindings.get(id(target_var), []):
                field_path = binding.field_path
                if mapping_name and field_path:
                    field_path = f"{mapping_name}.{field_path}"
                elif mapping_name:
                    field_path = mapping_name
                propagated.append(
                    _ProcedureStatusBinding(
                        call_name=binding.call_name,
                        parameter_name=binding.parameter_name,
                        channel_kind=binding.channel_kind,
                        field_path=field_path,
                    )
                )

            if not propagated:
                continue

            source_bindings = self._procedure_status_bindings[id(source_var)]
            for binding in propagated:
                if binding not in source_bindings:
                    source_bindings.append(binding)

    def _procedure_status_issue(
        self,
        variable: Variable,
        usage: VariableUsage,
    ) -> tuple[str, str | None] | None:
        bindings = self._procedure_status_bindings.get(id(variable), [])
        if not bindings or not usage.written:
            return None
        if usage.non_ui_read:
            return None

        binding = bindings[0]
        channel_label = (
            "procedure status output" if binding.channel_kind == "status" else "procedure async-operation handle"
        )
        if usage.ui_read:
            return (
                f"{channel_label} from {binding.call_name!r} parameter {binding.parameter_name!r} is only surfaced through UI wiring and is not checked in control logic.",
                binding.field_path,
            )
        return (
            f"{channel_label} from {binding.call_name!r} parameter {binding.parameter_name!r} is ignored after the procedure writes it.",
            binding.field_path,
        )

    def _has_procedure_status_binding(self, variable: Variable) -> bool:
        return bool(self._procedure_status_bindings.get(id(variable)))

    def _naming_role_mismatch_reason(
        self,
        variable: Variable,
        usage: VariableUsage,
        decl_path: list[str],
    ) -> str | None:
        name_key = variable.name.casefold()
        if self._matches_naming_role(name_key, "command"):
            if usage.read and usage.written and not self._has_output_effect(variable, decl_path):
                return "Cmd-suffixed variable behaves like internal state instead of a one-way command signal."
            return None
        if self._matches_naming_role(name_key, "status"):
            if usage.written and not self._has_procedure_status_binding(variable):
                return (
                    "Status-suffixed variable is written directly in logic instead of being treated as observed status."
                )
            return None
        if self._matches_naming_role(name_key, "alarm"):
            if usage.non_ui_read:
                return "Alarm-suffixed variable is consumed in non-UI logic and behaves like a control input."
            return None
        return None

    def _matches_naming_role(self, name_key: str, role_name: str) -> bool:
        patterns = self._naming_role_patterns.get(role_name, _NamingRolePatterns())
        return any(name_key.startswith(prefix) for prefix in patterns.prefixes) or any(
            name_key.endswith(suffix) for suffix in patterns.suffixes
        )

    def _add_naming_role_mismatch_issues(self) -> None:
        for decl_path, variable, _decl_role in _iter_variables_for_datatype_field_analysis(self):
            usage = self._get_usage(variable)
            reason = self._naming_role_mismatch_reason(variable, usage, decl_path)
            if reason is None:
                continue
            self._add_issue(
                IssueKind.NAMING_ROLE_MISMATCH,
                decl_path,
                variable,
                role=reason,
            )

    def _check_param_mappings_for_single(
        self,
        mod: SingleModule,
        child_env: dict[str, Variable],
        parent_env: dict[str, Variable],
        parent_path: list[str],
    ) -> None:
        params_by_name = {v.name.casefold(): v for v in (mod.moduleparameters or [])}
        mapped_target_keys = {
            target_name.casefold()
            for pm in mod.parametermappings or []
            for target_name in [varname_base(pm.target)]
            if target_name and target_name.casefold() in params_by_name
        }

        for parameter in mod.moduleparameters or []:
            if parameter.name.casefold() in mapped_target_keys:
                continue
            usage = self._get_usage(parameter)
            if not (usage.read or usage.written):
                continue
            if usage.is_display_only:
                continue
            self._append_issue(
                VariableIssue(
                    kind=IssueKind.REQUIRED_PARAMETER_CONNECTION,
                    module_path=list(parent_path),
                    variable=parameter,
                    role=("required parameter connection missing for " f"{parameter.name!r}"),
                )
            )

        for pm in mod.parametermappings or []:
            tgt_name = varname_base(pm.target)
            tgt_var = params_by_name.get(tgt_name) if tgt_name else None
            self._check_param_mapping(pm, tgt_var, parent_env, parent_path)

    def _check_param_mappings_for_type_instance(
        self,
        inst,  # ModuleTypeInstance
        parent_env: dict[str, Variable],
        parent_path: list[str],
        current_library: str | None = None,
    ) -> None:
        try:
            mt = resolve_moduletype_def_strict(
                self.bp,
                inst.moduletype_name,
                current_library=current_library,
                unavailable_libraries=self._unavailable_libraries,
            )
        except ValueError:
            return
        # Only parameters are valid mapping targets [2]
        params_by_name = {v.name.casefold(): v for v in (mt.moduleparameters or [])}
        mapped_target_keys = {
            target_name.casefold()
            for pm in inst.parametermappings or []
            for target_name in [varname_base(pm.target)]
            if target_name and target_name.casefold() in params_by_name
        }
        required_parameter_names = self._get_required_parameter_names_for_typedef(mt)
        for required_key in sorted(required_parameter_names):
            if required_key in mapped_target_keys:
                continue
            required_variable = params_by_name.get(required_key)
            if required_variable is None:
                continue
            self._append_issue(
                VariableIssue(
                    kind=IssueKind.REQUIRED_PARAMETER_CONNECTION,
                    module_path=list(parent_path),
                    variable=required_variable,
                    role=("required parameter connection missing for " f"{required_variable.name!r}"),
                )
            )
        for pm in inst.parametermappings or []:
            tgt_name = varname_base(pm.target)
            tgt_var = params_by_name.get(tgt_name) if tgt_name else None
            self._check_param_mapping(
                pm,
                tgt_var,
                parent_env,
                parent_path,
                owner_contract_id=id(mt),
            )

    def _check_param_mapping(
        self,
        pm: ParameterMapping,
        tgt_var: Variable | None,
        parent_env: dict[str, Variable],
        path: list[str],
        *,
        owner_contract_id: int | None = None,
    ) -> None:
        # If we cannot resolve target variable, we cannot validate types
        if tgt_var is None:
            return

        # 1) GLOBAL: no source variable to compare
        if pm.is_source_global:
            return

        # 2) Variable-to-variable mapping: enforce identical string type [2][4]
        src_var = self._lookup_env_var_from_varname_dict(pm.source, parent_env)
        if src_var is None:
            # Try resolving from root/global scope if not in parent env
            src_var = self._lookup_global_variable(varname_base(pm.source))

        self._issues.extend(
            self._contract_validator.check_contract_mapping(
                pm,
                tgt_var,
                src_var,
                path,
                owner_contract_id=owner_contract_id,
            )
        )

        if src_var is None:
            return  # cannot validate

        # Delegate validation to dedicated validators
        self._issues.extend(self._string_validator.check_string_mapping(tgt_var, src_var, path))
        self._issues.extend(self._min_max_validator.check_min_max_mapping(pm, tgt_var, src_var, path))

    def _index_all_variables(self) -> None:
        def _add(v: Variable):
            self._any_var_index.setdefault(v.name.lower(), []).append(v)

        # BasePicture locals
        for v in self.bp.localvariables or []:
            _add(v)

        # Descendants
        def _walk(mods):
            for m in mods or []:
                if isinstance(m, SingleModule):
                    for v in m.moduleparameters or []:
                        _add(v)
                    for v in m.localvariables or []:
                        _add(v)
                    _walk(m.submodules or [])
                elif isinstance(m, FrameModule):
                    _walk(m.submodules or [])
                # ModuleTypeInstance declares no variables

        _walk(self.bp.submodules or [])

        # TypeDefs declared in this file
        for mt in self.bp.moduletype_defs or []:
            for v in mt.moduleparameters or []:
                _add(v)
            for v in mt.localvariables or []:
                _add(v)

    def _is_const_candidate(self, v: Variable) -> bool:
        # Built-ins are normalized to Simple_DataType in Variable.__post_init__ [1]
        return isinstance(v.datatype, Simple_DataType)

    def _canonical_path(
        self,
        module_path: list[str],
        variable: Variable,
        field_path: str | None,
    ) -> CanonicalPath:
        segs = [*list(module_path), variable.name]
        if field_path:
            segs.extend([p for p in field_path.split(".") if p])
        return CanonicalPath(tuple(segs))

    def _record_access(
        self,
        kind: AccessKind,
        canonical_path: CanonicalPath,
        context: ScopeContext,
        syntactic_ref: str,
    ) -> None:
        self.usage_tracker.record_access(
            kind=kind,
            canonical_path=canonical_path,
            context=context,
            syntactic_ref=syntactic_ref,
        )

    def _mark_ref_access(
        self,
        full_ref: str,
        context: ScopeContext,
        path: list[str],
        kind: AccessKind,
        *,
        is_ui_read: bool = False,
    ) -> None:
        base = full_ref.split(".", 1)[0].lower()
        local_field_path = full_ref.split(".", 1)[1] if "." in full_ref else ""
        local_var = context.env.get(base)
        if local_var is not None and base in context.param_mappings:
            self.usage_tracker.mark_ref_access(
                variable=local_var,
                field_path=local_field_path,
                decl_module_path=context.module_path,
                context=context,
                path=path,
                kind=kind,
                syntactic_ref=full_ref,
                ui_read=is_ui_read,
            )

        var, field_path, decl_module_path, _decl_display = context.resolve_variable(full_ref)
        if var is None:
            return

        self.usage_tracker.mark_ref_access(
            variable=var,
            field_path=field_path,
            decl_module_path=decl_module_path,
            context=context,
            path=path,
            kind=kind,
            syntactic_ref=full_ref,
            ui_read=is_ui_read,
        )

    def _effect_key_for_variable(
        self,
        variable: Variable,
        decl_module_path: list[str],
    ) -> tuple[str, ...]:
        display_segments = (*decl_module_path, variable.name)
        key = tuple(segment.casefold() for segment in display_segments)
        self._effect_flow_display_names.setdefault(key, ".".join(display_segments))
        return key

    def _resolve_effect_key(
        self,
        full_ref: str,
        context: ScopeContext,
    ) -> tuple[str, ...] | None:
        base_name = varname_base(full_ref)
        if base_name:
            local_var = context.env.get(base_name.casefold())
            if local_var is not None:
                return self._effect_key_for_variable(local_var, context.module_path)
        variable, _field_path, decl_module_path, _decl_display = context.resolve_variable(full_ref)
        if variable is None:
            return None
        return self._effect_key_for_variable(variable, decl_module_path)

    def _mapping_source_effect_key(
        self,
        pm: ParameterMapping,
        *,
        parent_env: dict[str, Variable],
        parent_context: ScopeContext | None,
    ) -> tuple[str, ...] | None:
        if pm.is_source_global:
            full_source = None
            if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                full_source = pm.source[const.KEY_VAR_NAME]
            elif isinstance(pm.source, str):
                full_source = pm.source
            if not full_source:
                return None
            source_base = full_source.split(".", 1)[0]
            if parent_context is not None:
                source_var, decl_path, _decl_display = parent_context.resolve_global_name(source_base)
            else:
                source_var = parent_env.get(source_base.casefold())
                decl_path = []
                if source_var is None:
                    source_var = self._lookup_global_variable(source_base)
                    decl_path = [self.bp.header.name] if source_var is not None else []
            if source_var is None:
                return None
            return self._effect_key_for_variable(source_var, decl_path)

        if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
            full_source = pm.source[const.KEY_VAR_NAME]
        elif isinstance(pm.source, str):
            full_source = pm.source
        else:
            return None

        if parent_context is not None:
            return self._resolve_effect_key(full_source, parent_context)

        source_base = varname_base(full_source)
        if not source_base:
            return None
        source_var = parent_env.get(source_base.casefold()) or self._lookup_global_variable(source_base)
        if source_var is None:
            return None
        return self._effect_key_for_variable(source_var, [self.bp.header.name])

    def _resolve_local_effect_key(
        self,
        full_ref: str,
        context: ScopeContext,
    ) -> tuple[str, ...] | None:
        base = full_ref.split(".", 1)[0].lower()
        variable = context.env.get(base)
        if variable is None:
            return None
        return self._effect_key_for_variable(variable, context.module_path)

    def _resolve_mapped_effect_source_key(
        self,
        full_ref: str,
        context: ScopeContext,
    ) -> tuple[str, ...] | None:
        base = full_ref.split(".", 1)[0].lower()
        mapping = context.param_mappings.get(base)
        if mapping is None:
            return None
        source_var, _field_prefix, source_decl_path, _source_decl_display_path = mapping
        return self._effect_key_for_variable(source_var, source_decl_path)

    def _record_effect_flow(
        self,
        source_key: tuple[str, ...] | None,
        target_key: tuple[str, ...] | None,
    ) -> None:
        if source_key is None or target_key is None:
            return
        self._effect_flow_edges[source_key].add(target_key)

    def _collect_function_input_effect_keys(
        self,
        fn_name: str | None,
        args: list[Any],
        context: ScopeContext,
    ) -> set[tuple[str, ...]]:
        if not fn_name:
            input_sources: set[tuple[str, ...]] = set()
            for arg in args:
                input_sources.update(self._collect_expression_effect_sources(arg, context))
            return input_sources

        fn_key = fn_name.casefold()
        if fn_key in {"copyvariable", "copyvarnosort"}:
            if args and isinstance(args[0], dict) and const.KEY_VAR_NAME in args[0]:
                key = self._resolve_effect_key(args[0][const.KEY_VAR_NAME], context)
                return {key} if key is not None else set()
            return set()

        if fn_key == "initvariable":
            return set()

        sig = get_function_signature(fn_name)
        if sig is None:
            fallback_sources: set[tuple[str, ...]] = set()
            for arg in args:
                fallback_sources.update(self._collect_expression_effect_sources(arg, context))
            return fallback_sources

        signature_sources: set[tuple[str, ...]] = set()
        for idx, arg in enumerate(args):
            direction = "in"
            if idx < len(sig.parameters):
                direction = sig.parameters[idx].direction
            if direction not in {"in", "in var", "inout"}:
                continue
            signature_sources.update(self._collect_expression_effect_sources(arg, context))
        return signature_sources

    def _collect_expression_effect_sources(
        self,
        obj: Any,
        context: ScopeContext,
    ) -> set[tuple[str, ...]]:
        sources: set[tuple[str, ...]] = set()

        if obj is None:
            return sources

        if isinstance(obj, dict):
            if const.KEY_VAR_NAME in obj:
                full_ref = obj[const.KEY_VAR_NAME]
                key = self._resolve_effect_key(full_ref, context)
                if key is not None:
                    sources.add(key)
                return sources
            for value in obj.values():
                sources.update(self._collect_expression_effect_sources(value, context))
            return sources

        if isinstance(obj, list):
            for item in obj:
                sources.update(self._collect_expression_effect_sources(item, context))
            return sources

        if hasattr(obj, "data"):
            for child in getattr(obj, "children", []):
                sources.update(self._collect_expression_effect_sources(child, context))
            return sources

        if isinstance(obj, tuple):
            if obj and obj[0] == const.KEY_FUNCTION_CALL:
                _, fn_name, args = obj
                return self._collect_function_input_effect_keys(fn_name, args or [], context)
            for item in obj[1:] if obj and isinstance(obj[0], str) else obj:
                sources.update(self._collect_expression_effect_sources(item, context))
            return sources

        return sources

    def _record_assignment_effect_flow(
        self,
        target_ref: str,
        expr: Any,
        context: ScopeContext,
    ) -> None:
        target_key = self._resolve_effect_key(target_ref, context)
        for source_key in self._collect_expression_effect_sources(expr, context):
            self._record_effect_flow(source_key, target_key)

    def _record_function_call_effect_flow(
        self,
        fn_name: str | None,
        args: list[Any],
        context: ScopeContext,
    ) -> None:
        if not fn_name:
            return

        fn_key = fn_name.casefold()
        if fn_key in {"copyvariable", "copyvarnosort"}:
            if len(args) < 2:
                return
            if not (
                isinstance(args[0], dict)
                and const.KEY_VAR_NAME in args[0]
                and isinstance(args[1], dict)
                and const.KEY_VAR_NAME in args[1]
            ):
                return
            source_key = self._resolve_effect_key(args[0][const.KEY_VAR_NAME], context)
            target_key = self._resolve_effect_key(args[1][const.KEY_VAR_NAME], context)
            self._record_effect_flow(source_key, target_key)
            return

        if fn_key == "initvariable":
            return

        sig = get_function_signature(fn_name)
        if sig is None:
            return

        input_keys: set[tuple[str, ...]] = set()
        output_keys: set[tuple[str, ...]] = set()
        for idx, arg in enumerate(args):
            direction = "in"
            if idx < len(sig.parameters):
                direction = sig.parameters[idx].direction

            if direction in {"in", "in var", "inout"}:
                input_keys.update(self._collect_expression_effect_sources(arg, context))

            if direction in {"out", "inout"} and isinstance(arg, dict) and const.KEY_VAR_NAME in arg:
                key = self._resolve_effect_key(arg[const.KEY_VAR_NAME], context)
                if key is not None:
                    output_keys.add(key)

        for output_key in output_keys:
            for input_key in input_keys:
                self._record_effect_flow(input_key, output_key)

    def _collect_effect_sink_keys(self) -> set[tuple[str, ...]]:
        sink_keys = set(self._external_effect_sinks)

        if not self._analyzed_target_is_library:
            for variable in self.bp.localvariables or []:
                sink_keys.add(self._effect_key_for_variable(variable, [self.bp.header.name]))

        if self._analyzed_target_is_library:
            for moduletype in self.bp.moduletype_defs or []:
                if not self._is_from_root_origin(getattr(moduletype, "origin_file", None)):
                    continue
                decl_path = [self.bp.header.name, f"TypeDef:{moduletype.name}"]
                for variable in moduletype.moduleparameters or []:
                    sink_keys.add(self._effect_key_for_variable(variable, decl_path))

        return sink_keys

    def _compute_effective_output_keys(self) -> set[tuple[str, ...]]:
        sink_keys = self._collect_effect_sink_keys()
        if not sink_keys:
            return set()

        incoming_edges: dict[tuple[str, ...], set[tuple[str, ...]]] = defaultdict(set)
        for source_key, target_keys in self._effect_flow_edges.items():
            for target_key in target_keys:
                incoming_edges[target_key].add(source_key)

        effective_keys = set(sink_keys)
        pending = list(sink_keys)
        while pending:
            target_key = pending.pop()
            for source_key in incoming_edges.get(target_key, set()):
                if source_key in effective_keys:
                    continue
                effective_keys.add(source_key)
                pending.append(source_key)
        return effective_keys

    def _has_output_effect(self, variable: Variable, decl_path: list[str]) -> bool:
        return self._effect_key_for_variable(variable, decl_path) in self._effective_output_keys

    def _site_str(self) -> str:
        if not self._site_stack:
            return ""
        return " > ".join(self._site_stack)

    def _push_site(self, label: str) -> None:
        if label:
            self._site_stack.append(label)

    def _pop_site(self) -> None:
        if self._site_stack:
            self._site_stack.pop()

    def _strict_datatype_at_field_prefix(
        self,
        root_type: Simple_DataType | str,
        field_prefix: str,
        *,
        fn_name: str,
        syntactic_ref: str,
        resolved_var_name: str,
        use_path: list[str],
    ) -> Simple_DataType | str:
        """Resolve the datatype at a dotted field-prefix (strict).

        Used only for record-wide builtin semantics.

        Raises ValueError if:
        - a referenced record type is unknown
        - a referenced field segment doesn't exist
        - the prefix continues into a scalar type
        """
        segments = [s for s in (field_prefix or "").split(".") if s]
        current: Simple_DataType | str = root_type

        for seg in segments:
            if isinstance(current, Simple_DataType):
                site = self._site_str()
                if self.fail_loudly:
                    raise ValueError(
                        f"{fn_name}: at {' -> '.join(use_path)}"
                        f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                        f"cannot access field {seg!r} on scalar datatype {current.value!r}."
                    )
                self._warn(
                    f"{fn_name}: at {' -> '.join(use_path)}"
                    f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"cannot access field {seg!r} on scalar datatype {current.value!r}. Treating as leaf."
                )
                return current

            if isinstance(current, str) and current.casefold() in self._OPAQUE_BUILTIN_TYPES:
                return current

            rec = self.type_graph.record(str(current))
            if rec is None:
                site = self._site_str()
                if self._unavailable_libraries or not self.fail_loudly:
                    self._warn(
                        f"{fn_name}: at {' -> '.join(use_path)}"
                        f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                        f"uses unknown record datatype {str(current)!r}. Treating as leaf."
                    )
                    return current
                raise ValueError(
                    f"{fn_name}: at {' -> '.join(use_path)}"
                    f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"uses unknown record datatype {str(current)!r}."
                )

            f = rec.fields_by_key.get(seg.casefold())
            if f is None:
                available = sorted({fd.name for fd in rec.fields_by_key.values()})
                close = difflib.get_close_matches(seg, available, n=5, cutoff=0.6)
                site = self._site_str()
                if self._unavailable_libraries or not self.fail_loudly:
                    self._warn(
                        f"{fn_name}: at {' -> '.join(use_path)}"
                        f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                        f"uses unknown field {seg!r} in record datatype {rec.name!r}. "
                        f"Available fields: {available[:50]}"
                        + (f". Close matches: {close}" if close else "")
                        + " Treating as leaf."
                    )
                    return str(current)
                raise ValueError(
                    f"{fn_name}: at {' -> '.join(use_path)}"
                    f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"uses unknown field {seg!r} in record datatype {rec.name!r}. "
                    f"Available fields: {available[:50]}" + (f". Close matches: {close}" if close else "")
                )

            current = f.datatype

        return current

    def _iter_leaf_field_paths_strict(
        self,
        root_type: Simple_DataType | str,
        *,
        fn_name: str,
        syntactic_ref: str,
        resolved_var_name: str,
    ) -> list[tuple[str, ...]]:
        """Expand all leaf field paths for a datatype (strict).

        Returns tuples relative to the datatype root.
        Raises ValueError on unknown record types or cycles.
        """
        if isinstance(root_type, Simple_DataType):
            return [()]

        # Builtin pseudo-type: cannot be expanded, treat as leaf.
        if isinstance(root_type, str) and root_type.casefold() == "anytype":
            return [()]

        start = str(root_type)
        results: list[tuple[str, ...]] = []
        stack: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [(start, (), ())]

        while stack:
            type_name, prefix, chain = stack.pop()
            key = type_name.casefold()

            if key in {c.casefold() for c in chain}:
                raise ValueError(
                    f"{fn_name}: datatype cycle detected while expanding {resolved_var_name!r} "
                    f"(ref {syntactic_ref!r}) at record datatype {type_name!r}."
                )

            rec = self.type_graph.record(type_name)
            if rec is None:
                if key in self._OPAQUE_BUILTIN_TYPES:
                    results.append(prefix)
                    continue
                # Unknown external type: record-wide expansion can't proceed.
                # Fail loudly for real record types, but allow the builtin pseudo-type.
                if self._unavailable_libraries:
                    self._warn(
                        f"{fn_name}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                        f"uses unknown record datatype {type_name!r}. "
                        "Treating as leaf due to unavailable libraries."
                    )
                    results.append(prefix)
                    continue
                if type_name.casefold() == "anytype":
                    results.append(prefix)
                    continue
                if self.fail_loudly:
                    raise ValueError(
                        f"{fn_name}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                        f"uses unknown record datatype {type_name!r}."
                    )
                self._warn(
                    f"{fn_name}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"uses unknown record datatype {type_name!r}. Treating as leaf."
                )
                results.append(prefix)
                continue

            next_chain = (*chain, type_name)
            for field in rec.fields_by_key.values():
                new_prefix = (*prefix, field.name)
                if isinstance(field.datatype, Simple_DataType):
                    results.append(new_prefix)
                else:
                    stack.append((str(field.datatype), new_prefix, next_chain))

        return results

    def _mark_record_wide_builtin_access(
        self,
        syntactic_ref: str,
        *,
        kind: AccessKind,
        fn_name: str,
        context: ScopeContext,
        path: list[str],
        is_ui_read: bool = False,
    ) -> None:
        """Mark read/write for every leaf field under the resolved datatype.

        The `syntactic_ref` is what appears in code (e.g. "Dv.Y_Søjle" or "control").
        Resolution (param mappings) is applied via ScopeContext.resolve_variable().
        """
        resolved_var, resolved_field_prefix, _decl_path, _decl_display = context.resolve_variable(syntactic_ref)
        if resolved_var is None:
            site = self._site_str()
            raise ValueError(
                f"{fn_name}: at {' -> '.join(path)}"
                f"{(' [' + site + ']') if site else ''}: cannot resolve variable reference {syntactic_ref!r} for record-wide access."
            )

        dtype_at_prefix = self._strict_datatype_at_field_prefix(
            resolved_var.datatype,
            resolved_field_prefix,
            fn_name=fn_name,
            syntactic_ref=syntactic_ref,
            resolved_var_name=resolved_var.name,
            use_path=path,
        )

        leaf_paths = self._iter_leaf_field_paths_strict(
            dtype_at_prefix,
            fn_name=fn_name,
            syntactic_ref=syntactic_ref,
            resolved_var_name=resolved_var.name,
        )

        for leaf in leaf_paths:
            if not leaf:
                self._mark_ref_access(
                    syntactic_ref,
                    context,
                    path,
                    kind,
                    is_ui_read=is_ui_read,
                )
            else:
                self._mark_ref_access(
                    f"{syntactic_ref}.{'.'.join(leaf)}",
                    context,
                    path,
                    kind,
                    is_ui_read=is_ui_read,
                )

    def _lookup_global_variable(self, base_name: str | None) -> Variable | None:
        if not base_name:
            return None
        normalized = base_name.lower()
        var = self._root_env.get(normalized)
        if var:
            return var
        lst = self._any_var_index.get(normalized)
        return lst[0] if lst else None

    def _is_from_root_origin(self, origin_file: str | None) -> bool:
        if not origin_file:
            # If origin wasn't stamped (e.g., SCAN_ROOT_ONLY), treat as root.
            return True
        root_origin = getattr(self.bp, "origin_file", None)
        if not root_origin:
            # Without a root origin, be conservative: treat as not-from-root
            # (or return True if you want to analyze everything when origin is missing)
            return False

        try:
            return Path(origin_file).stem.lower() == Path(root_origin).stem.lower()
        except Exception:
            return origin_file.rsplit(".", 1)[0].lower() == root_origin.rsplit(".", 1)[0].lower()

    def _extract_field_path(self, var_dict: dict) -> tuple[str | None, str | None]:
        """
        Extract base variable name and field path from variable reference.
        E.g., "Dv.BatchID" -> ("Dv", "BatchID")
            "Dv.Recipe.Name" -> ("Dv", "Recipe.Name")
        """
        if not isinstance(var_dict, dict) or const.KEY_VAR_NAME not in var_dict:
            return None, None

        full_name = var_dict[const.KEY_VAR_NAME]
        if not full_name or "." not in full_name:
            return full_name.lower() if full_name else None, None

        parts = full_name.split(".", 1)
        base = parts[0].lower()
        field_path = parts[1] if len(parts) > 1 else None

        return base, field_path

    # ------------ Entry point ------------

    def run(
        self,
        apply_alias_back_propagation: bool = True,
        limit_to_module_path: list[str] | None = None,
    ) -> list[VariableIssue]:
        # NOTE: When `limit_to_module_path` is set (used by option 9), we must NOT
        # analyze every ModuleTypeDef in the project. That would pull in unrelated
        # code and can legitimately fail loudly (e.g., record-wide builtins) outside
        # the selected subtree.
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
            log.debug(
                "Variables analysis start: %s locals=%d submodules=%d typedefs=%d",
                self.bp.header.name,
                len(self.bp.localvariables or []),
                len(self.bp.submodules or []),
                len(self.bp.moduletype_defs or []),
            )

        # Build root scope context for BasePicture
        root_context = self.context_builder.build_for_basepicture()
        self._trace("root-context-built", root_symbols=len(root_context.env))

        # Analyze BasePicture body
        self._walk_module_code(self.bp.modulecode, root_context, path=[self.bp.header.name])
        self._walk_moduledef(self.bp.moduledef, root_context, path=[self.bp.header.name])
        self._walk_header_enable(self.bp.header, root_context, path=[self.bp.header.name])
        self._walk_header_invoke_tails(self.bp.header, root_context, path=[self.bp.header.name])
        self._walk_header_groupconn(self.bp.header, root_context, path=[self.bp.header.name])

        # Walk submodules with scope propagation
        self._walk_submodules(self.bp.submodules or [], parent_context=root_context, parent_path=[self.bp.header.name])

        if apply_alias_back_propagation:
            self._apply_alias_back_propagation()
            self._propagate_procedure_status_bindings()
            self._trace("alias-back-propagation", alias_link_count=len(self._alias_links))

        self._detect_datatype_duplications()
        issue_count_before_reset = len(self._issues)
        detect_reset_contamination(self.bp, self._issues, self._limit_to_module_path)
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
        self._effective_output_keys = self._compute_effective_output_keys()

        # Collect issues across this file
        bp_path = [self.bp.header.name]

        for v in self.bp.localvariables or []:
            role = "localvariable"
            usage = self._get_usage(v)
            if usage.is_unused:
                self._add_issue(IssueKind.UNUSED, bp_path, v, role=role)
                continue
            procedure_status = self._procedure_status_issue(v, usage)
            if procedure_status is not None:
                status_role, field_path = procedure_status
                self._add_issue(IssueKind.PROCEDURE_STATUS, bp_path, v, role=status_role, field_path=field_path)
                continue
            elif usage.is_display_only:
                self._add_issue(IssueKind.UI_ONLY, bp_path, v, role=role)
            elif usage.is_read_only and not bool(v.const) and self._is_const_candidate(v):
                self._add_issue(IssueKind.READ_ONLY_NON_CONST, bp_path, v, role=role)
            elif usage.written and not usage.read:
                self._add_issue(IssueKind.NEVER_READ, bp_path, v, role=role)
            elif (
                usage.read
                and usage.written
                and not self._has_output_effect(v, bp_path)
                and not self._has_procedure_status_binding(v)
            ):
                self._add_issue(IssueKind.WRITE_WITHOUT_EFFECT, bp_path, v, role=role)

        for mod in self.bp.submodules or []:
            self._collect_issues_from_module(mod, path=bp_path)

        if self._limit_to_module_path is None:
            for mt in self.bp.moduletype_defs or []:
                if not self._is_from_root_origin(getattr(mt, "origin_file", None)):
                    continue
                td_path = [self.bp.header.name, f"TypeDef:{mt.name}"]

                self._analyze_typedef(mt, path=[self.bp.header.name, f"TypeDef:{mt.name}"])

                # moduleparameters: UNUSED only
                for v in mt.moduleparameters or []:
                    role = "moduleparameter"
                    usage = self._get_usage(v)
                    if usage.is_unused:
                        self._add_issue(IssueKind.UNUSED, td_path, v, role=role)
                        continue
                    procedure_status = self._procedure_status_issue(v, usage)
                    if procedure_status is not None:
                        status_role, field_path = procedure_status
                        self._add_issue(IssueKind.PROCEDURE_STATUS, td_path, v, role=status_role, field_path=field_path)
                        continue
                    elif usage.is_display_only:
                        self._add_issue(IssueKind.UI_ONLY, td_path, v, role=role)
                    elif (
                        usage.read
                        and usage.written
                        and not self._has_output_effect(v, td_path)
                        and not self._has_procedure_status_binding(v)
                    ):
                        self._add_issue(
                            IssueKind.WRITE_WITHOUT_EFFECT,
                            td_path,
                            v,
                            role=role,
                        )
                # localvariables: UNUSED / READ_ONLY_NON_CONST / NEVER_READ
                for v in mt.localvariables or []:
                    role = "localvariable"
                    usage = self._get_usage(v)
                    if usage.is_unused:
                        self._add_issue(IssueKind.UNUSED, td_path, v, role=role)
                        continue
                    procedure_status = self._procedure_status_issue(v, usage)
                    if procedure_status is not None:
                        status_role, field_path = procedure_status
                        self._add_issue(IssueKind.PROCEDURE_STATUS, td_path, v, role=status_role, field_path=field_path)
                        continue
                    elif usage.is_display_only:
                        self._add_issue(IssueKind.UI_ONLY, td_path, v, role=role)
                    elif usage.is_read_only and not bool(v.const) and self._is_const_candidate(v):
                        self._add_issue(IssueKind.READ_ONLY_NON_CONST, td_path, v, role=role)
                    elif usage.written and not usage.read:
                        self._add_issue(IssueKind.NEVER_READ, td_path, v, role=role)
                    elif (
                        usage.read
                        and usage.written
                        and not self._has_output_effect(v, td_path)
                        and not self._has_procedure_status_binding(v)
                    ):
                        self._add_issue(
                            IssueKind.WRITE_WITHOUT_EFFECT,
                            td_path,
                            v,
                            role=role,
                        )

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
            log.debug("Variables analysis complete. Issues=%d", len(self._issues))

        return self._issues

    # ------------ Traversal helpers ------------

    def _is_external_typename(self, typename: str) -> bool:
        # Type is external to this file if not present in BasePicture.moduletype_defs [3]
        return typename.lower() not in self.typedef_index

    # ------------ ModuleTypeDef analysis ------------

    def _analyze_typedef(self, mt: ModuleTypeDef, path: list[str]) -> None:
        # Prevent infinite recursion
        mt_key = mt.name.lower()
        if mt_key in self._analyzing_typedefs:
            return

        self._analyzing_typedefs.add(mt_key)

        try:
            params = list(mt.moduleparameters or [])
            locals_ = list(mt.localvariables or [])

            # Enforce: cannot have both a parameter and local with same name
            param_keys = {v.name.casefold(): v for v in params}
            local_keys = {v.name.casefold(): v for v in locals_}
            for k in set(param_keys.keys()) & set(local_keys.keys()):
                p = param_keys[k]
                lv = local_keys[k]
                self._append_issue(
                    VariableIssue(
                        kind=IssueKind.NAME_COLLISION,
                        module_path=path.copy(),
                        variable=lv,
                        role=f"name collision with parameter {p.name!r}",
                        source_variable=p,
                    )
                )

            # Build environment from typedef's parameters + locals
            env: dict[str, Variable] = {}
            for v in params:
                env[v.name.lower()] = v
            for v in locals_:
                env[v.name.lower()] = v

            display_path: list[str] = []
            if path:
                display_path.append(decorate_segment(path[0], "BP"))
                for seg in path[1:]:
                    if seg.startswith("TypeDef:"):
                        display_path.append(decorate_segment(seg, "TD"))
                    else:
                        display_path.append(seg)

            # Create scope context
            context = ScopeContext(
                env=env,
                param_mappings={},
                module_path=path.copy(),
                display_module_path=display_path,
                current_library=mt.origin_lib,
                parent_context=None,
            )

            # Scan typedef ModuleDef first (graph/interact), then ModuleCode
            self._walk_moduledef(mt.moduledef, context, path)
            self._walk_module_code(mt.modulecode, context, path)
            self._walk_submodules(mt.submodules or [], parent_context=context, parent_path=path)
            self._walk_typedef_groupconn(mt, context, path)

            # Track per-parameter read/write usage
            used_reads: set[str] = {v.name.lower() for v in (mt.moduleparameters or []) if self._get_usage(v).read}
            used_writes: set[str] = {v.name.lower() for v in (mt.moduleparameters or []) if self._get_usage(v).written}

            # Preserve existing "used" union for any other consumers
            used_params: set[str] = used_reads | used_writes
            self.used_params_by_typedef[mt.name] = used_params

            # Store separate read/write sets
            self.param_reads_by_typedef[mt.name.lower()] = used_reads
            self.param_writes_by_typedef[mt.name.lower()] = used_writes

            for pm in mt.parametermappings or []:
                tgt_name = varname_base(pm.target)
                tgt_var = env.get(tgt_name) if tgt_name else None
                self._check_param_mapping(pm, tgt_var, env, path)
        finally:
            self._analyzing_typedefs.discard(mt_key)

    def _apply_alias_back_propagation(self) -> None:
        """
        For every alias (parent_var -> child_param_var, field_prefix), replicate usage
        from the child parameter back to the parent variable WITH the field prefix.

        Example:
        parent_var = Dv
        child_var = OpMessage (parameter in child module)
        field_prefix = "OpMessage1"

        If OpMessage.AckText is accessed in child:
            -> Mark Dv field "OpMessage1.AckText" as accessed
        """
        for parent_var, child_var, field_prefix in self._alias_links:
            parent_usage = self._get_usage(parent_var)
            child_usage = self._get_usage(child_var)

            # Replicate field-level accesses WITH prefix reconstruction
            for field_path, locations in (child_usage.field_reads or {}).items():
                # Reconstruct full field path: prefix + field accessed on parameter
                if field_prefix and field_path:
                    full_field_path = f"{field_prefix}.{field_path}"
                elif field_prefix:
                    full_field_path = field_prefix
                else:
                    full_field_path = field_path

                for loc in locations:
                    parent_usage.mark_field_read(full_field_path, loc)

            for field_path, locations in (child_usage.field_writes or {}).items():
                # Reconstruct full field path
                if field_prefix and field_path:
                    full_field_path = f"{field_prefix}.{field_path}"
                elif field_prefix:
                    full_field_path = field_prefix
                else:
                    full_field_path = field_path

                for loc in locations:
                    parent_usage.mark_field_written(full_field_path, loc)

            # Replicate whole-variable accesses as field accesses
            # (accessing the parameter as a whole = accessing that field of parent)
            for loc, kind in child_usage.usage_locations or []:
                if field_prefix:
                    # If there's a field prefix, mark that field as accessed
                    if kind == "read":
                        parent_usage.mark_field_read(field_prefix, loc)
                    elif kind == "write":
                        parent_usage.mark_field_written(field_prefix, loc)  # type: ignore
                else:
                    # No field prefix means whole variable mapping (rare case)
                    if kind == "read":
                        parent_usage.mark_read(loc)
                    elif kind == "write":
                        parent_usage.mark_written(loc)

    def _walk_submodules(
        self,
        children: list[SingleModule | FrameModule | ModuleTypeInstance],
        parent_context: ScopeContext,
        parent_path: list[str],
    ) -> None:
        """Walk submodules with proper scope context propagation."""

        for child in children:
            child_name = child.header.name
            child_path = [*parent_path, child_name]

            # Only traverse:
            #  - nodes along the path to the selected module, and
            #  - nodes within the selected module subtree.
            if self._limit_to_module_path is not None and not (
                path_startswith_casefold(self._limit_to_module_path, child_path)
                or path_startswith_casefold(child_path, self._limit_to_module_path)
            ):
                continue

            if isinstance(child, SingleModule):
                child_display_path = [*parent_context.display_module_path, decorate_segment(child_name, "SM")]
            elif isinstance(child, FrameModule):
                child_display_path = [*parent_context.display_module_path, decorate_segment(child_name, "FM")]
            elif isinstance(child, ModuleTypeInstance):
                child_display_path = [
                    *parent_context.display_module_path,
                    decorate_segment(child_name, "MT", moduletype_name=child.moduletype_name),
                ]
            else:
                child_display_path = [*parent_context.display_module_path, child_name]

            inst_context = self._repath_context(
                parent_context,
                module_path=child_path,
                display_module_path=child_display_path,
            )

            # Handle header-level enable and groupconn
            self._walk_header_enable(child.header, inst_context, path=child_path)
            self._walk_header_invoke_tails(child.header, inst_context, path=child_path)
            self._walk_header_groupconn(child.header, inst_context, path=child_path)

            if isinstance(child, SingleModule):
                # Build scope context with parameter mappings
                child_context = self.context_builder.build_for_single(
                    child,
                    parent_context,
                    module_path=child_path,
                    display_module_path=child_display_path,
                )

                # Use child_context instead of building env dict
                self._walk_moduledef(child.moduledef, child_context, child_path)
                self._walk_module_code(child.modulecode, child_context, child_path)

                # Recursively walk submodules with child context
                self._walk_submodules(
                    child.submodules or [],
                    child_context,  # Pass child context, not parent
                    child_path,
                )

                # Track parameter usage for propagation (unchanged logic)
                used_reads: set[str] = {
                    v.name.lower() for v in (child.moduleparameters or []) if self._get_usage(v).read
                }
                used_writes: set[str] = {
                    v.name.lower() for v in (child.moduleparameters or []) if self._get_usage(v).written
                }

                # Create alias links with field path information
                for pm in child.parametermappings or []:
                    source_name = varname_base(pm.source)
                    target_name = varname_base(pm.target)

                    if source_name and target_name and not pm.is_source_global:
                        # Extract field prefix from mapping
                        if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                            full_source_name = pm.source[const.KEY_VAR_NAME]
                        elif isinstance(pm.source, str):
                            full_source_name = pm.source
                        else:
                            continue

                        # Resolve with field path
                        source_var, source_field_prefix, _decl_path, _decl_disp = parent_context.resolve_variable(
                            full_source_name
                        )
                        target_key = target_name.casefold()
                        target_var = child_context.env.get(target_key)

                        if source_var and target_var:
                            # Store only the source field prefix (relative to the source variable).
                            # This must NOT include the target parameter name.
                            # Examples:
                            #   control => Dv        => mapping_name == ""         (Dv.cmd)
                            #   control => Dv.empty  => mapping_name == "empty"    (Dv.empty.cmd)
                            mapping_name = source_field_prefix or ""

                            self._alias_links.append((source_var, target_var, mapping_name))

                # Propagate usage (unchanged)
                for pm in child.parametermappings or []:
                    self._propagate_mapping_to_parent(
                        pm,
                        child_used_reads=used_reads,
                        child_used_writes=used_writes,
                        parent_env=parent_context.env,
                        parent_path=parent_path,
                        external_typename=None,
                        parent_context=parent_context,
                        child_context=child_context,
                    )

                # Check string type mismatches (unchanged)
                self._check_param_mappings_for_single(
                    child,
                    child_env=child_context.env,
                    parent_env=parent_context.env,
                    parent_path=child_path,
                )

            elif isinstance(child, FrameModule):
                # FrameModule: no new scope, but access locations should be attributed to the frame's instance path.
                frame_context = self._repath_context(
                    parent_context,
                    module_path=child_path,
                    display_module_path=child_display_path,
                )
                self._walk_moduledef(child.moduledef, frame_context, child_path)
                self._walk_module_code(child.modulecode, frame_context, child_path)

                self._walk_submodules(
                    child.submodules or [],
                    frame_context,
                    child_path,
                )

            elif isinstance(child, ModuleTypeInstance):
                external = self._is_external_typename(child.moduletype_name)
                mt: ModuleTypeDef | None = None

                if not external:
                    try:
                        mt = resolve_moduletype_def_strict(
                            self.bp,
                            child.moduletype_name,
                            current_library=parent_context.current_library,
                            unavailable_libraries=self._unavailable_libraries,
                        )
                    except ValueError:
                        mt = None
                        external = True

                if external and not self._analyzed_target_is_library:
                    continue

                if mt is not None and not self._is_from_root_origin(getattr(mt, "origin_file", None)):
                    if not self._analyzed_target_is_library and not self._include_dependency_moduletype_usage:
                        self._check_param_mappings_for_type_instance(
                            child,
                            parent_env=parent_context.env,
                            parent_path=[*parent_path, child_name],
                            current_library=parent_context.current_library,
                        )
                        continue
                    # For library targets, dependency moduletype instances should still
                    # influence mapped variables even though we do not analyze the
                    # dependency body in detail. Treat them like external sinks/sources.
                    if self._analyzed_target_is_library and not self._include_dependency_moduletype_usage:
                        mt = None
                        external = True

                reads, writes = None, None  # Initialize to None
                typedef_context: ScopeContext | None = None

                if mt:
                    mt_key = child.moduletype_name.lower()

                    # Build typedef scope context with mappings
                    typedef_context = self.context_builder.build_for_typedef(
                        mt,
                        child,
                        parent_context,
                        module_path=child_path,
                        display_module_path=child_display_path,
                    )

                    # Analyze typedef if not already done
                    if mt_key not in self.param_reads_by_typedef and mt_key not in self._analyzing_typedefs:
                        # Use context-aware analysis
                        self._analyze_typedef_with_context(mt, typedef_context, path=child_path)

                    # Create alias links with field path information
                    for pm in child.parametermappings or []:
                        source_name = varname_base(pm.source)
                        target_name = varname_base(pm.target)

                        if source_name and target_name and not pm.is_source_global:
                            if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                                full_source_name = pm.source[const.KEY_VAR_NAME]
                            elif isinstance(pm.source, str):
                                full_source_name = pm.source
                            else:
                                continue

                            # Resolve with field path
                            source_var, source_field_prefix, _decl_path, _decl_disp = parent_context.resolve_variable(
                                full_source_name
                            )
                            target_key = target_name.casefold()
                            target_var = typedef_context.env.get(target_key)

                            if source_var and target_var:
                                # Store only the source field prefix (relative to the source variable).
                                # Do not include the target parameter name.
                                mapping_name = source_field_prefix or ""

                                self._alias_links.append((source_var, target_var, mapping_name))

                    reads = self.param_reads_by_typedef.get(mt_key, set())
                    writes = self.param_writes_by_typedef.get(mt_key, set())

                # Propagate usage (unchanged)
                for pm in child.parametermappings or []:
                    self._propagate_mapping_to_parent(
                        pm,
                        child_used_reads=reads,
                        child_used_writes=writes,
                        parent_env=parent_context.env,
                        parent_path=parent_path,
                        external_typename=(child.moduletype_name if external else None),
                        parent_context=parent_context,
                        child_context=typedef_context,
                    )

                if mt is not None:
                    self._check_param_mappings_for_type_instance(
                        child,
                        parent_env=parent_context.env,
                        parent_path=[*parent_path, child_name],
                        current_library=parent_context.current_library,
                    )

    def _analyze_single_module_with_context(
        self, mod: SingleModule, context: ScopeContext, path: list[str]
    ) -> tuple[set[str], set[str]]:
        """Analyze a SingleModule with scope context."""
        self._walk_moduledef(mod.moduledef, context, path)
        self._walk_module_code(mod.modulecode, context, path)
        self._walk_submodules(mod.submodules or [], parent_context=context, parent_path=path)

        used_reads: set[str] = {v.name.lower() for v in (mod.moduleparameters or []) if self._get_usage(v).read}
        used_writes: set[str] = {v.name.lower() for v in (mod.moduleparameters or []) if self._get_usage(v).written}
        return used_reads, used_writes

    def _analyze_typedef_with_context(self, mt: ModuleTypeDef, context: ScopeContext, path: list[str]) -> None:
        """Analyze a ModuleTypeDef with scope context."""
        mt_key = mt.name.lower()
        if mt_key in self._analyzing_typedefs:
            return

        self._analyzing_typedefs.add(mt_key)

        try:
            self._walk_moduledef(mt.moduledef, context, path)
            self._walk_module_code(mt.modulecode, context, path)
            self._walk_submodules(mt.submodules or [], parent_context=context, parent_path=path)
            self._walk_typedef_groupconn(mt, context, path)

            used_reads: set[str] = {v.name.lower() for v in (mt.moduleparameters or []) if self._get_usage(v).read}
            used_writes: set[str] = {v.name.lower() for v in (mt.moduleparameters or []) if self._get_usage(v).written}

            self.used_params_by_typedef[mt.name] = used_reads | used_writes
            self.param_reads_by_typedef[mt_key] = used_reads
            self.param_writes_by_typedef[mt_key] = used_writes
        finally:
            self._analyzing_typedefs.discard(mt_key)

    # ------------ Propagation of parameter mappings ------------

    def _propagate_mapping_to_parent(
        self,
        pm: ParameterMapping,
        child_used_reads: set[str] | None,
        child_used_writes: set[str] | None,
        parent_env: dict[str, Variable],
        parent_path: list[str],
        external_typename: str | None,
        parent_context: ScopeContext | None = None,
        child_context: ScopeContext | None = None,
    ) -> None:
        target_name = varname_base(pm.target)

        if child_context is not None and target_name is not None:
            target_var = child_context.env.get(target_name.casefold())
            source_key = self._mapping_source_effect_key(
                pm,
                parent_env=parent_env,
                parent_context=parent_context,
            )
            if target_var is not None and source_key is not None:
                target_key = self._effect_key_for_variable(target_var, child_context.module_path)
                if child_used_reads is not None and target_name in child_used_reads:
                    self._record_effect_flow(source_key, target_key)
                if child_used_writes is not None and target_name in child_used_writes:
                    self._record_effect_flow(target_key, source_key)

        # GLOBAL: resolve by walking up scopes, and only mark if parameter is used
        if pm.is_source_global:
            full_source = None
            if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                full_source = pm.source[const.KEY_VAR_NAME]
            elif isinstance(pm.source, str):
                full_source = pm.source

            if not full_source:
                return

            source_parts = full_source.split(".", 1)
            source_base = source_parts[0]
            source_field_path = source_parts[1] if len(source_parts) > 1 else ""

            if parent_context is not None:
                src_var, _decl_path, _decl_display = parent_context.resolve_global_name(source_base)
            else:
                src_var = parent_env.get(source_base.lower())
                if src_var is None:
                    src_var = self._lookup_global_variable(source_base)

            if src_var is None:
                return

            # External types: conservatively treat mapping as read+written
            if external_typename is not None:
                if parent_context is not None:
                    source_key = self._resolve_effect_key(full_source, parent_context)
                    if source_key is not None:
                        self._external_effect_sinks.add(source_key)
                external_display_path: list[str] = []
                if parent_path:
                    external_display_path.append(decorate_segment(parent_path[0], "BP"))
                    external_display_path.extend(parent_path[1:])
                use_context = ScopeContext(
                    env=parent_env,
                    param_mappings={},
                    module_path=parent_path.copy(),
                    display_module_path=external_display_path,
                    parent_context=None,
                )

                if source_field_path:
                    self._get_usage(src_var).mark_field_read(source_field_path, parent_path)
                    self._get_usage(src_var).mark_field_written(source_field_path, parent_path)

                    cp = self._canonical_path(parent_path, src_var, source_field_path)
                    self._record_access(AccessKind.READ, cp, use_context, full_source)
                    self._record_access(AccessKind.WRITE, cp, use_context, full_source)
                else:
                    self._get_usage(src_var).mark_read(parent_path)
                    self._get_usage(src_var).mark_written(parent_path)

                    cp = self._canonical_path(parent_path, src_var, "")
                    self._record_access(AccessKind.READ, cp, use_context, full_source)
                    self._record_access(AccessKind.WRITE, cp, use_context, full_source)
                return

            if target_name is not None:
                if child_used_reads is not None and target_name in child_used_reads:
                    if source_field_path:
                        self._get_usage(src_var).mark_field_read(source_field_path, parent_path)
                    else:
                        self._get_usage(src_var).mark_read(parent_path)

                if child_used_writes is not None and target_name in child_used_writes:
                    if source_field_path:
                        self._get_usage(src_var).mark_field_written(source_field_path, parent_path)
                    else:
                        self._get_usage(src_var).mark_written(parent_path)
            return

        # Extract full source path with fields
        if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
            full_source = pm.source[const.KEY_VAR_NAME]
        elif isinstance(pm.source, str):
            full_source = pm.source
        else:
            return

        # Parse the source to get base and field path
        source_parts = full_source.split(".", 1)
        source_base = source_parts[0].lower()
        source_field_path = source_parts[1] if len(source_parts) > 1 else ""

        # Resolve the actual source variable
        src_var = parent_env.get(source_base)
        if src_var is None:
            src_var = self._lookup_global_variable(source_base)

        if src_var is None:
            return

        # External types: conservatively treat mapping as read+written
        if external_typename is not None:
            if parent_context is not None:
                source_key = self._resolve_effect_key(full_source, parent_context)
                if source_key is not None:
                    self._external_effect_sinks.add(source_key)
            external_mapping_display_path: list[str] = []
            if parent_path:
                external_mapping_display_path.append(decorate_segment(parent_path[0], "BP"))
                external_mapping_display_path.extend(parent_path[1:])
            use_context = ScopeContext(
                env=parent_env,
                param_mappings={},
                module_path=parent_path.copy(),
                display_module_path=external_mapping_display_path,
                parent_context=None,
            )

            if source_field_path:
                self._get_usage(src_var).mark_field_read(source_field_path, parent_path)
                self._get_usage(src_var).mark_field_written(source_field_path, parent_path)

                cp = self._canonical_path(parent_path, src_var, source_field_path)
                self._record_access(AccessKind.READ, cp, use_context, full_source)
                self._record_access(AccessKind.WRITE, cp, use_context, full_source)
            else:
                self._get_usage(src_var).mark_read(parent_path)
                self._get_usage(src_var).mark_written(parent_path)

                cp = self._canonical_path(parent_path, src_var, "")
                self._record_access(AccessKind.READ, cp, use_context, full_source)
                self._record_access(AccessKind.WRITE, cp, use_context, full_source)
            return

        # Internal types with field-aware propagation
        if target_name is not None:
            # If the child used the parameter for reading
            if child_used_reads is not None and target_name in child_used_reads:
                if source_field_path:
                    self._get_usage(src_var).mark_field_read(source_field_path, parent_path)
                else:
                    self._get_usage(src_var).mark_read(parent_path)

            # If the child used the parameter for writing
            if child_used_writes is not None and target_name in child_used_writes:
                if source_field_path:
                    self._get_usage(src_var).mark_field_written(source_field_path, parent_path)
                else:
                    self._get_usage(src_var).mark_written(parent_path)

    # ------------ Var lookup helpers ------------

    def _lookup_env_var_from_varname_dict(
        self,
        var_dict_or_other: Any,
        env: dict[str, Variable],
    ) -> Variable | None:
        """
        var_dict_or_other is either a {var_name: "..."} dict (from transformer.variable_name) [5],
        or something else (literal, None, etc.).
        """
        if isinstance(var_dict_or_other, dict) and const.KEY_VAR_NAME in var_dict_or_other:
            base = varname_base(var_dict_or_other)
            if base is not None:
                return env.get(base)
        return None

    def _detect_datatype_duplications(self) -> None:
        """
        Find complex (record) datatypes that are declared multiple times
        across localvariables and moduleparameters instead of being defined
        as a RECORD type once and reused.
        """
        # Collect all variables with their locations
        var_locations: list[tuple[Variable, list[str], str]] = []

        # BasePicture locals
        bp_path = [self.bp.header.name]
        for v in self.bp.localvariables or []:
            var_locations.append((v, bp_path.copy(), "localvariable"))

        # Recursively collect from modules
        def _collect_from_module(mod: SingleModule | FrameModule | ModuleTypeInstance, path: list[str]):
            if isinstance(mod, SingleModule):
                my_path = [*path, mod.header.name]
                for v in mod.moduleparameters or []:
                    var_locations.append((v, my_path.copy(), "moduleparameter"))
                for v in mod.localvariables or []:
                    var_locations.append((v, my_path.copy(), "localvariable"))
                for ch in mod.submodules or []:
                    _collect_from_module(ch, my_path)
            elif isinstance(mod, FrameModule):
                my_path = [*path, mod.header.name]
                for ch in mod.submodules or []:
                    _collect_from_module(ch, my_path)

        for mod in self.bp.submodules or []:
            _collect_from_module(mod, bp_path)

        # Include TypeDef variables (only from root origin)
        for mt in self.bp.moduletype_defs or []:
            if not self._is_from_root_origin(getattr(mt, "origin_file", None)):
                continue
            td_path = [self.bp.header.name, f"TypeDef:{mt.name}"]
            for v in mt.moduleparameters or []:
                var_locations.append((v, td_path.copy(), "moduleparameter"))
            for v in mt.localvariables or []:
                var_locations.append((v, td_path.copy(), "localvariable"))

        # Only check non-built-in user types. AnyType is a wildcard pseudo-type,
        # not a concrete complex datatype declaration candidate.
        complex_vars = [
            (v, path, role)
            for v, path, role in var_locations
            if not isinstance(v.datatype, Simple_DataType) and v.datatype_text.casefold() != "anytype"
        ]

        # Group by declaration scope and datatype name so same user datatype names
        # in peer modules are treated independently.
        by_datatype: dict[tuple[tuple[str, ...], str], list[tuple[Variable, list[str], str]]] = {}
        for v, path, role in complex_vars:
            dt_key = v.datatype_text.lower()
            scope_key = tuple(segment.casefold() for segment in path)
            by_datatype.setdefault((scope_key, dt_key), []).append((v, path, role))

        # Report duplicates (2+ occurrences)
        declared_record_names = {d.name.casefold() for d in self.bp.datatype_defs or []}
        for (_scope_key, dt_name), occurrences in by_datatype.items():
            if len(occurrences) < 2:
                continue

            # Check if this is actually a defined RECORD type
            if dt_name in declared_record_names:
                # It's a legitimate record type being used multiple times - not a duplication issue
                continue

            # Create an issue for the first occurrence, listing all others
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
