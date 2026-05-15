"""Facade properties and forwarding methods for VariablesAnalyzer."""

from __future__ import annotations

from typing import Any, ClassVar

from sattline_parser.models.ast_model import ModuleTypeDef, Variable

from ..models.usage import VariableUsage
from ..reporting.variables_report import IssueKind, VariableIssue
from ..resolution import AccessGraph
from ..resolution.scope import ScopeContext
from ._variables_effect_flow import EffectFlowTracker
from ._variables_status import ProcedureStatusBinding
from .validators import AnyTypeFieldContract, ContractMappingValidator, MinMaxValidator, StringMappingValidator


class VariablesAnalyzerFacadeMixin:
    _OPAQUE_BUILTIN_TYPES: ClassVar[set[str]]

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

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

    @property
    def issues(self) -> list[VariableIssue]:
        return self._issues

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


__all__ = ["VariablesAnalyzerFacadeMixin"]
