"""Forwarding property mixin for VariablesAnalyzer facade state."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from typing import Any, ClassVar, Protocol, cast

from sattline_parser.models.ast_model import Variable

from ..reporting.variables_report import VariableIssue
from ..resolution import AccessGraph
from ._variables_effect_flow import EffectFlowTracker
from ._variables_status import ProcedureStatusBinding
from .validators import ContractMappingValidator, MinMaxValidator, StringMappingValidator


class _UsageTrackerView(Protocol):
    access_graph: AccessGraph


class _VariablesAnalyzerFacadeState(Protocol):
    usage_tracker: _UsageTrackerView
    _analyzed_target_is_library: bool
    _limit_to_module_path: list[str] | None
    _unavailable_libraries: set[str]
    _include_dependency_moduletype_usage: bool
    _alias_links: list[tuple[Variable, Variable, str]]
    _procedure_status_bindings: dict[int, list[ProcedureStatusBinding]]
    _ignorable_output_variable_ids: set[int]
    _naming_role_patterns: dict[str, Any]
    _any_var_index: dict[str, list[Variable]]
    _required_parameter_names_by_owner: dict[int, dict[str, str]]
    _contract_validator: ContractMappingValidator
    _min_max_validator: MinMaxValidator
    _string_validator: StringMappingValidator
    _analyzing_typedefs: set[str]
    _effect_flow_tracker: EffectFlowTracker
    _effective_output_keys: set[tuple[str, ...]]
    _site_stack: list[str]
    _root_env: dict[str, Variable]
    _effect_flow_edges: dict[tuple[str, ...], set[tuple[str, ...]]]
    _effect_flow_display_names: dict[tuple[str, ...], str]
    _analysis_warnings: list[str]
    _issues: list[VariableIssue]
    _contexts_by_module_path: dict[tuple[str, ...], Any]


class VariablesAnalyzerFacadePropertiesMixin:
    _OPAQUE_BUILTIN_TYPES: ClassVar[set[str]]

    def _state(self) -> _VariablesAnalyzerFacadeState:
        return cast(_VariablesAnalyzerFacadeState, self)

    @property
    def access_graph(self) -> AccessGraph:
        return self._state().usage_tracker.access_graph

    @property
    def analyzed_target_is_library(self) -> bool:
        return self._state()._analyzed_target_is_library

    @property
    def limit_to_module_path(self) -> list[str] | None:
        return self._state()._limit_to_module_path

    @property
    def unavailable_libraries(self) -> set[str]:
        return self._state()._unavailable_libraries

    @property
    def include_dependency_moduletype_usage(self) -> bool:
        return self._state()._include_dependency_moduletype_usage

    @property
    def alias_links(self) -> list[tuple[Variable, Variable, str]]:
        return self._state()._alias_links

    @property
    def procedure_status_bindings(self) -> dict[int, list[ProcedureStatusBinding]]:
        return self._state()._procedure_status_bindings

    @property
    def ignorable_output_variable_ids(self) -> set[int]:
        return self._state()._ignorable_output_variable_ids

    @property
    def naming_role_patterns(self) -> dict[str, Any]:
        return self._state()._naming_role_patterns

    @property
    def any_var_index(self) -> dict[str, list[Variable]]:
        return self._state()._any_var_index

    @property
    def required_parameter_names_by_owner(self) -> dict[int, dict[str, str]]:
        return self._state()._required_parameter_names_by_owner

    @property
    def contract_validator(self) -> ContractMappingValidator:
        return self._state()._contract_validator

    @property
    def min_max_validator(self) -> MinMaxValidator:
        return self._state()._min_max_validator

    @property
    def string_validator(self) -> StringMappingValidator:
        return self._state()._string_validator

    @property
    def analyzing_typedefs(self) -> set[str]:
        return self._state()._analyzing_typedefs

    @property
    def effect_flow_tracker(self) -> EffectFlowTracker:
        return self._state()._effect_flow_tracker

    @property
    def effective_output_keys(self) -> set[tuple[str, ...]]:
        return self._state()._effective_output_keys

    @property
    def site_stack(self) -> list[str]:
        return self._state()._site_stack

    @property
    def root_env(self) -> dict[str, Variable]:
        return self._state()._root_env

    @property
    def opaque_builtin_types(self) -> set[str]:
        return type(self)._OPAQUE_BUILTIN_TYPES

    @property
    def effect_flow_edges(self) -> dict[tuple[str, ...], tuple[tuple[str, ...], ...]]:
        return {
            source_key: tuple(sorted(target_keys))
            for source_key, target_keys in self._state()._effect_flow_edges.items()
        }

    @property
    def contexts_by_module_path(self) -> dict[tuple[str, ...], Any]:
        return self._state()._contexts_by_module_path

    @property
    def effect_flow_display_names(self) -> dict[tuple[str, ...], str]:
        return dict(self._state()._effect_flow_display_names)

    @property
    def analysis_warnings(self) -> list[str]:
        return self._state()._analysis_warnings

    @property
    def issues(self) -> list[VariableIssue]:
        return self._state()._issues


__all__ = ["VariablesAnalyzerFacadePropertiesMixin"]
