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
from sattlint.analyzers.shadowing import analyze_shadowing
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.analyzers.variables import _variable_issue_collection as variable_issue_collection_module
from sattlint.analyzers.variables import _variables_execution as variables_execution_module
from sattlint.engine import parse_source_file
from sattlint.reporting.variables_report import (
    VariableIssue,
    VariablesReport,
)
from sattlint.resolution.scope import ScopeContext
from tests.helpers.variable_test_support import (
    UsageStub as _UsageStub,
)
from tests.helpers.variable_test_support import (
    access_event as _access_event,
)
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)
from tests.helpers.variable_test_support import (
    issue_kinds as _issue_kinds,
)
from tests.helpers.variable_test_support import (
    state_ref as _state_ref,
)
from tests.helpers.variable_test_support import (
    status_bridge_typedef as _status_bridge_typedef,
)
from tests.helpers.variable_test_support import (
    varref as _varref,
)
from tests.test_analyzers_variables_adjacent_analyzers import (  # noqa: F401
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
