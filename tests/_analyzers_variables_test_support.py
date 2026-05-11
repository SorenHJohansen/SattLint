"""Tests for variable-quality analyzers: MMS, loop output, parameter drift, cyclomatic complexity, scan-loop resource, min/max, contract mismatch, magic numbers, shadowing, variables analysis, and datatype duplication."""

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FloatLiteral,
    GraphObject,
    InteractObject,
    IntLiteral,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCTransition,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers import _variables_execution as variables_execution_module
from sattlint.analyzers import variable_issue_collection as variable_issue_collection_module
from sattlint.analyzers.shadowing import analyze_shadowing
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.engine import parse_source_file
from sattlint.reporting.variables_report import (
    VariableIssue,
    VariablesReport,
)
from sattlint.resolution.scope import ScopeContext
from tests._analyzers_variables_adjacent_analyzers import (  # noqa: F401
    test_cyclomatic_complexity_flags_high_complexity_program_modulecode,
    test_cyclomatic_complexity_flags_high_complexity_sfc_step,
    test_cyclomatic_complexity_ignores_low_complexity_program_modulecode,
    test_loop_output_refactor_detects_cycle_across_equations_and_active_step,
    test_loop_output_refactor_ignores_acyclic_sorted_blocks,
    test_mms_interface_collects_nested_typedef_mappings_and_write_locations,
    test_mms_interface_flags_dead_tags_for_unwritten_outgoing_variables,
    test_mms_interface_flags_duplicate_tags_and_datatype_mismatch_from_icf_entries,
    test_mms_interface_flags_naming_drift_from_icf_entries,
    test_mms_interface_uses_moduletype_default_tags_for_duplicate_and_dead_tag_checks,
    test_parameter_drift_flags_diverging_literal_parameter_values,
    test_parameter_drift_ignores_aligned_literal_parameter_values,
    test_scan_loop_resource_usage_flags_non_precision_builtin_in_active_step_code,
    test_scan_loop_resource_usage_flags_non_precision_builtin_in_equation_block,
    test_scan_loop_resource_usage_ignores_non_precision_builtin_outside_active_scan_context,
)


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(s: str) -> dict:
    return {const.KEY_VAR_NAME: s}


def _state_ref(name: str, state: str) -> dict:
    return {const.KEY_VAR_NAME: name, "state": state}


def _issue_kinds(report) -> set[str]:
    return {issue.kind for issue in report.issues}


def _status_bridge_typedef() -> ModuleTypeDef:
    return ModuleTypeDef(
        name="StatusBridge",
        moduleparameters=[Variable(name="OperationStatus", datatype=Simple_DataType.INTEGER)],
        localvariables=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Destination", datatype=Simple_DataType.INTEGER),
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="BridgeEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [_varref("Source"), _varref("Destination"), _varref("OperationStatus")],
                        )
                    ],
                )
            ]
        ),
    )


class _UsageStub:
    def __init__(
        self,
        *,
        is_unused: bool = False,
        is_display_only: bool = False,
        is_read_only: bool = False,
        read: bool = False,
        written: bool = False,
        field_reads: dict[str, list[object]] | None = None,
        field_writes: dict[str, list[object]] | None = None,
        usage_locations: list[tuple[object, str]] | None = None,
    ) -> None:
        self.is_unused = is_unused
        self.is_display_only = is_display_only
        self.is_read_only = is_read_only
        self.read = read
        self.written = written
        self.field_reads = field_reads or {}
        self.field_writes = field_writes or {}
        self.usage_locations = usage_locations or []

    def mark_field_read(self, field_path: str, location: object) -> None:
        self.field_reads.setdefault(field_path, []).append(location)

    def mark_field_written(self, field_path: str, location: object) -> None:
        self.field_writes.setdefault(field_path, []).append(location)

    def mark_read(self, location: object) -> None:
        self.read = True
        self.usage_locations.append((location, "read"))

    def mark_written(self, location: object) -> None:
        self.written = True
        self.usage_locations.append((location, "write"))


def _access_event(
    path_parts: tuple[str, ...],
    use_module_path: list[str],
    kind: object,
) -> SimpleNamespace:
    return SimpleNamespace(
        canonical_path=SimpleNamespace(key=lambda: path_parts),
        use_module_path=use_module_path,
        kind=kind,
    )


__all__ = [
    "Any",
    "BasePicture",
    "DataType",
    "Equation",
    "FloatLiteral",
    "GraphObject",
    "IntLiteral",
    "InteractObject",
    "IssueKind",
    "ModuleCode",
    "ModuleDef",
    "ModuleHeader",
    "ModuleTypeDef",
    "ModuleTypeInstance",
    "ParameterMapping",
    "Path",
    "SFCTransition",
    "ScopeContext",
    "Sequence",
    "SimpleNamespace",
    "Simple_DataType",
    "SingleModule",
    "SourceSpan",
    "Variable",
    "VariableIssue",
    "VariablesAnalyzer",
    "VariablesReport",
    "_UsageStub",
    "_access_event",
    "_hdr",
    "_issue_kinds",
    "_state_ref",
    "_status_bridge_typedef",
    "_varref",
    "analyze_shadowing",
    "cast",
    "const",
    "logging",
    "parse_source_file",
    "parser_core_parse_source_text",
    "variable_issue_collection_module",
    "variables_execution_module",
]
