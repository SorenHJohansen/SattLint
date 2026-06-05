"""Facade properties and forwarding methods for VariablesAnalyzer."""

from __future__ import annotations

from typing import Any, ClassVar

from sattline_parser.models.ast_model import ModuleTypeDef, ParameterMapping, Variable

from ..models.usage import VariableUsage
from ..reporting.variables_report import IssueKind, VariableIssue
from ..resolution.scope import ScopeContext
from ._validators import AnyTypeFieldContract
from ._variables_facade_properties import VariablesAnalyzerFacadePropertiesMixin


class VariablesAnalyzerFacadeMixin(VariablesAnalyzerFacadePropertiesMixin):
    _OPAQUE_BUILTIN_TYPES: ClassVar[set[str]]

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _get_usage(self, variable: Variable) -> VariableUsage:
        return self.usage_tracker.get_usage(variable)

    def get_usage(self, variable: Variable) -> VariableUsage:
        return self._get_usage(variable)

    def append_issue(self, issue: VariableIssue) -> None:
        self._append_issue(issue)

    def append_param_mapping_issue(self, mapping: ParameterMapping, issue: VariableIssue) -> None:
        self._append_param_mapping_issue(mapping, issue)

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

    def analyze_library_dependency_typedef_usage(self) -> None:
        self._analyze_library_dependency_typedef_usage()

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
        source_context: ScopeContext | None,
        path: list[str],
        *,
        owner_contract_id: int | None = None,
    ) -> None:
        self._check_param_mapping(
            pm,
            tgt_var,
            parent_env,
            source_context,
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
        parent_context: ScopeContext,
        parent_path: list[str],
    ) -> None:
        self._check_param_mappings_for_single(mod, child_env, parent_env, parent_context, parent_path)

    def check_param_mappings_for_type_instance(
        self,
        inst: Any,
        parent_env: dict[str, Variable],
        parent_context: ScopeContext,
        parent_path: list[str],
        current_library: str | None = None,
    ) -> None:
        self._check_param_mappings_for_type_instance(
            inst,
            parent_env,
            parent_context,
            parent_path,
            current_library=current_library,
        )


__all__ = ["VariablesAnalyzerFacadeMixin"]
