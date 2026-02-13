"""Dedicated validator classes for variable analysis."""
from __future__ import annotations
import re
import logging
from typing import Any, Protocol

from ..grammar import constants as const
from ..models.ast_model import Variable, ParameterMapping, Simple_DataType
from ..reporting.variables_report import IssueKind, VariableIssue

log = logging.getLogger("SattLint")


class Validator(Protocol):
    """Protocol for validators."""

    def validate(self, **kwargs: Any) -> list[VariableIssue]:
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
