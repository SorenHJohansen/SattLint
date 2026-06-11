# pyright: reportPrivateUsage=false

"""Tests for full-suite analyzers.

Covers SFC parallel write race, dataflow, variables analyzer suites,
version drift, initial values, naming consistency, alarm integrity,
safety paths, and taint paths.
"""

import json
from types import SimpleNamespace
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FrameModule,
    GraphObject,
    IntLiteral,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    SFCTransition,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers import registry as registry_module
from sattlint.analyzers.alarm_integrity import analyze_alarm_integrity
from sattlint.analyzers.dataflow import analyze_dataflow
from sattlint.analyzers.framework import AnalyzerSpec
from sattlint.analyzers.initial_values import analyze_initial_values
from sattlint.analyzers.mms import (
    _extract_external_tag,
    _find_parameter_mapping,
    _find_variable,
    _normalize_external_tag,
    _tag_family_key,
)
from sattlint.analyzers.modules import (
    AstDiffDetail,
    CodeDiff,
    ComparisonResult,
    SubmoduleDiff,
    VariableDiff,
    _build_upgrade_notes,
    _collect_named_item_diffs,
    _common_module_prefix,
    _compact_diff,
    _diff_normalized_variants,
    _group_instances_by_variant,
    _normalize_ast_value,
    analyze_version_drift,
    compare_modules,
    create_fingerprint,
)
from sattlint.analyzers.naming import analyze_naming_consistency, get_configured_naming_rules
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.safety_paths import analyze_safety_paths
from sattlint.analyzers.sfc import analyze_sfc
from sattlint.analyzers.sfc._sfc_guard_logic import _normalize_guard_signature
from sattlint.analyzers.taint_paths import analyze_taint_paths
from sattlint.analyzers.variable_usage_reporting import (
    _find_module_instances,
    debug_variable_usage,
    report_datatype_usage,
    report_module_localvar_fields,
)
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
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

__all__ = [
    "AnalyzerSpec",
    "Any",
    "AstDiffDetail",
    "BasePicture",
    "CodeDiff",
    "ComparisonResult",
    "DataType",
    "Equation",
    "FrameModule",
    "GraphObject",
    "IntLiteral",
    "IssueKind",
    "ModuleCode",
    "ModuleDef",
    "ModuleHeader",
    "ModuleTypeDef",
    "ModuleTypeInstance",
    "ParameterMapping",
    "SFCCodeBlocks",
    "SFCParallel",
    "SFCStep",
    "SFCTransition",
    "Sequence",
    "SimpleNamespace",
    "Simple_DataType",
    "SingleModule",
    "SubmoduleDiff",
    "Variable",
    "VariableDiff",
    "VariablesAnalyzer",
    "_build_upgrade_notes",
    "_collect_named_item_diffs",
    "_common_module_prefix",
    "_compact_diff",
    "_diff_normalized_variants",
    "_extract_external_tag",
    "_find_module_instances",
    "_find_parameter_mapping",
    "_find_variable",
    "_group_instances_by_variant",
    "_hdr",
    "_issue_kinds",
    "_normalize_ast_value",
    "_normalize_external_tag",
    "_normalize_guard_signature",
    "_state_ref",
    "_status_bridge_typedef",
    "_tag_family_key",
    "_varref",
    "analyze_alarm_integrity",
    "analyze_dataflow",
    "analyze_initial_values",
    "analyze_naming_consistency",
    "analyze_safety_paths",
    "analyze_sfc",
    "analyze_taint_paths",
    "analyze_version_drift",
    "cast",
    "compare_modules",
    "const",
    "create_fingerprint",
    "debug_variable_usage",
    "get_configured_naming_rules",
    "get_default_analyzers",
    "json",
    "registry_module",
    "report_datatype_usage",
    "report_module_localvar_fields",
]
