"""Dedicated validator classes for variable analysis."""
from __future__ import annotations
from dataclasses import dataclass
import re
import logging
from typing import Any, Mapping, Protocol

from ..grammar import constants as const
from ..models.ast_model import Variable, ParameterMapping, Simple_DataType
from ..reporting.variables_report import IssueKind, VariableIssue
from ..resolution import TypeGraph
from ..resolution.common import varname_full
from ..validation import (
    _assignment_type_matches,
    _extract_time_literal,
    _has_time_literal_marker,
    _infer_literal_datatype,
    _is_valid_time_literal,
    _literal_matches_expected_datatype,
    _resolve_variable_field_datatype,
    _split_dotted_name,
)

log = logging.getLogger("SattLint")


@dataclass(frozen=True, slots=True)
class AnyTypeFieldContract:
    field_paths: tuple[str, ...]


class Validator(Protocol):
    """Protocol for validators."""

    def validate(self, **_kwargs: Any) -> list[VariableIssue]:
        """Run validation and return a list of issues."""
        ...


class StringMappingValidator:
    """Validates string variable mapping types."""

    _STRING_LIMITS: dict[Simple_DataType, int] = {
        Simple_DataType.IDENTSTRING: 15,
        Simple_DataType.TAGSTRING: 30,
        Simple_DataType.STRING: 40,
        Simple_DataType.LINESTRING: 80,
        Simple_DataType.MAXSTRING: 140,
    }
    _STRING_TYPES: set[Simple_DataType] = set(_STRING_LIMITS.keys())

    def _is_string_simple_type(self, dt: Simple_DataType | str | None) -> bool:
        return isinstance(dt, Simple_DataType) and dt in self._STRING_TYPES

    def check_string_mapping(
        self,
        tgt_var: Variable,
        src_var: Variable,
        path: list[str],
    ) -> list[VariableIssue]:
        """
        Check if string variable mappings have mismatched types.

        SattLine requires strict string type matching (e.g. String40 -> String40).
        """
        issues: list[VariableIssue] = []

        # Only check when both are built-in string types
        if self._is_string_simple_type(tgt_var.datatype) and \
           self._is_string_simple_type(src_var.datatype):

            if tgt_var.datatype is not src_var.datatype:
                issue = VariableIssue(
                    kind=IssueKind.STRING_MAPPING_MISMATCH,
                    module_path=list(path),
                    variable=tgt_var,
                    role="parameter mapping type mismatch",
                    source_variable=src_var,
                )
                issues.append(issue)

        return issues
class MinMaxValidator:
    """Validates min/max naming conventions in parameter mappings."""

    _MIN_NAME_TOKENS: set[str] = {"min", "minimum"}
    _MAX_NAME_TOKENS: set[str] = {"max", "maximum"}

    def _mapping_name_text(self, value: Any) -> str | None:
        if isinstance(value, dict) and const.KEY_VAR_NAME in value:
            return value[const.KEY_VAR_NAME]
        if isinstance(value, Variable):
            return value.name
        if isinstance(value, str):
            return value
        return None

    def _tokenize_name(self, name: str) -> set[str]:
        parts = re.split(r"[\s_.\-]+", name)
        tokens: list[str] = []
        for part in parts:
            if not part:
                continue
            # Split camelCase and numbers
            sub_parts = re.findall(
                r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+",
                part,
            )
            tokens.extend(sub_parts or [part])
        return {t.lower() for t in tokens if t}

    def _minmax_flags(self, name: str) -> tuple[bool, bool, bool]:
        tokens = self._tokenize_name(name)
        has_min = any(t in self._MIN_NAME_TOKENS for t in tokens)
        has_max = any(t in self._MAX_NAME_TOKENS for t in tokens)
        return has_min, has_max, has_min and has_max

    def check_min_max_mapping(
        self,
        pm: ParameterMapping,
        tgt_var: Variable,
        src_var: Variable,
        path: list[str],
    ) -> list[VariableIssue]:
        """
        Check for mismatched min/max semantics in parameter mappings.

        Example: Mapping a 'MaxLimit' variable to a 'MinLimit' parameter.
        """
        issues: list[VariableIssue] = []

        tgt_name = self._mapping_name_text(pm.target) or tgt_var.name
        src_name = self._mapping_name_text(pm.source) or src_var.name

        if not tgt_name or not src_name:
            return issues

        tgt_min, tgt_max, tgt_amb = self._minmax_flags(tgt_name)
        src_min, src_max, src_amb = self._minmax_flags(src_name)

        # If ambiguous (contains both min and max), skip check
        if tgt_amb or src_amb:
            return issues

        # Check for cross-mapping
        if (tgt_min and src_max) or (tgt_max and src_min):
            issue = VariableIssue(
                kind=IssueKind.MIN_MAX_MAPPING_MISMATCH,
                module_path=list(path),
                variable=tgt_var,
                role="min/max mapping mismatch",
                source_variable=src_var,
            )
            issues.append(issue)

        return issues


class ContractMappingValidator:
    """Validates parameter mappings against strict datatype compatibility rules."""

    def __init__(
        self,
        type_graph: TypeGraph,
        anytype_field_contracts: Mapping[int, Mapping[str, AnyTypeFieldContract]] | None = None,
    ):
        self._type_graph = type_graph
        self._anytype_field_contracts = {
            owner_id: dict(contracts)
            for owner_id, contracts in (anytype_field_contracts or {}).items()
        }

    def _datatype_key(self, datatype: Simple_DataType | str | None) -> str | None:
        if datatype is None:
            return None
        if isinstance(datatype, Simple_DataType):
            return datatype.value.casefold()
        return str(datatype).casefold()

    def _is_string_simple_type(self, datatype: Simple_DataType | str | None) -> bool:
        return isinstance(datatype, Simple_DataType) and datatype in StringMappingValidator._STRING_TYPES

    def _format_datatype(self, datatype: Simple_DataType | str | None) -> str:
        if datatype is None:
            return "unknown"
        if isinstance(datatype, Simple_DataType):
            return datatype.value
        return str(datatype)

    def _resolve_source_required_field_datatype(
        self,
        mapping: ParameterMapping,
        source_variable: Variable,
        required_field_path: str,
    ) -> Simple_DataType | str | None:
        source_name = varname_full(mapping.source)
        if not source_name:
            return None

        _base_name, source_field_path = _split_dotted_name(source_name)
        required_segments = tuple(segment for segment in required_field_path.split(".") if segment)
        combined_path = source_field_path + required_segments

        if not combined_path:
            return source_variable.datatype

        return _resolve_variable_field_datatype(
            source_variable,
            combined_path,
            self._type_graph,
        )

    def _check_anytype_field_contracts(
        self,
        mapping: ParameterMapping,
        target_variable: Variable,
        source_variable: Variable | None,
        path: list[str],
        *,
        owner_contract_id: int | None,
    ) -> list[VariableIssue]:
        if owner_contract_id is None or source_variable is None or mapping.source_literal is not None:
            return []

        contracts_by_param = self._anytype_field_contracts.get(owner_contract_id)
        if not contracts_by_param:
            return []

        contract = contracts_by_param.get(target_variable.name.casefold())
        if contract is None or not contract.field_paths:
            return []

        source_name = varname_full(mapping.source) or source_variable.name
        target_name = varname_full(mapping.target) or target_variable.name
        issues: list[VariableIssue] = []

        for required_field_path in contract.field_paths:
            datatype = self._resolve_source_required_field_datatype(
                mapping,
                source_variable,
                required_field_path,
            )
            if datatype is not None:
                continue

            issues.append(
                VariableIssue(
                    kind=IssueKind.CONTRACT_MISMATCH,
                    module_path=list(path),
                    variable=target_variable,
                    role=(
                        "cross-module contract mismatch: "
                        f"{source_name} ({self._format_datatype(source_variable.datatype)}) => "
                        f"{target_name} ({self._format_datatype(target_variable.datatype)}) "
                        f"missing required field {required_field_path!r}"
                    ),
                    source_variable=source_variable,
                    field_path=required_field_path,
                )
            )

        return issues

    def _resolve_target_datatype(
        self,
        target_name: str,
        target_variable: Variable,
    ) -> tuple[Simple_DataType | str | None, str | None]:
        _base_name, field_path = _split_dotted_name(target_name)
        if not field_path:
            return target_variable.datatype, None

        datatype = _resolve_variable_field_datatype(
            target_variable,
            field_path,
            self._type_graph,
        )
        return datatype, ".".join(field_path)

    def _resolve_source_datatype(
        self,
        mapping: ParameterMapping,
        source_variable: Variable | None,
    ) -> tuple[Simple_DataType | str | None, str | None]:
        if mapping.source_literal is not None:
            return (
                _infer_literal_datatype(
                    mapping.source_literal,
                    is_duration=bool(mapping.is_duration),
                ),
                repr(mapping.source_literal),
            )

        source_name = varname_full(mapping.source)
        if not source_name or source_variable is None:
            return None, source_name

        _base_name, field_path = _split_dotted_name(source_name)
        if not field_path:
            return source_variable.datatype, source_name

        datatype = _resolve_variable_field_datatype(
            source_variable,
            field_path,
            self._type_graph,
        )
        return datatype, source_name

    def check_contract_mapping(
        self,
        pm: ParameterMapping,
        tgt_var: Variable,
        src_var: Variable | None,
        path: list[str],
        *,
        owner_contract_id: int | None = None,
    ) -> list[VariableIssue]:
        issues: list[VariableIssue] = []

        target_name = varname_full(pm.target) or tgt_var.name
        target_datatype, target_field_path = self._resolve_target_datatype(
            target_name,
            tgt_var,
        )
        if target_datatype is None:
            return issues

        source_datatype, source_name = self._resolve_source_datatype(pm, src_var)
        if source_datatype is None:
            return issues

        source_key = self._datatype_key(source_datatype)
        target_key = self._datatype_key(target_datatype)
        if source_key is None or target_key is None or source_key == target_key:
            return issues

        if target_key == "anytype":
            return self._check_anytype_field_contracts(
                pm,
                tgt_var,
                src_var,
                path,
                owner_contract_id=owner_contract_id,
            )

        if pm.source_literal is not None and _literal_matches_expected_datatype(
            pm.source_literal,
            target_datatype,
            is_duration=bool(pm.is_duration),
        ):
            return issues

        if self._is_string_simple_type(source_datatype) and self._is_string_simple_type(target_datatype):
            return issues

        if (
            _assignment_type_matches(source_datatype, target_datatype)
            and source_datatype == const.GRAMMAR_VALUE_TIME_VALUE
            and (
                pm.source_literal is None
                or not _has_time_literal_marker(pm.source_literal)
                or _is_valid_time_literal(_extract_time_literal(pm.source_literal))
            )
        ):
            return issues

        issue = VariableIssue(
            kind=IssueKind.CONTRACT_MISMATCH,
            module_path=list(path),
            variable=tgt_var,
            role=(
                "cross-module contract mismatch: "
                f"{source_name or 'value'} ({self._format_datatype(source_datatype)}) => "
                f"{target_name} ({self._format_datatype(target_datatype)})"
            ),
            source_variable=src_var,
            field_path=target_field_path,
        )
        issues.append(issue)
        return issues
