"""Tests for state-integrity analyzers.

Covers reset contamination, implicit latch, SFC step contract,
write-without-effect, hidden global coupling, global scope minimization,
high fan-in/out, and variables report summary.
"""

from types import SimpleNamespace
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ParameterMapping,
    Sequence,
    SFCAlternative,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers import reset_contamination as reset_contamination_module
from sattlint.analyzers._variables_effect_flow import EffectFlowTracker
from sattlint.analyzers.sfc import analyze_sfc
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.reporting.variables_report import (
    ALL_VARIABLE_ANALYSIS_KINDS,
    VariableIssue,
    VariablesReport,
)
from sattlint.resolution.scope import ScopeContext
from sattlint.types import VariableId


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


__all__ = [
    "ALL_VARIABLE_ANALYSIS_KINDS",
    "Any",
    "BasePicture",
    "EffectFlowTracker",
    "Equation",
    "FrameModule",
    "IssueKind",
    "ModuleCode",
    "ModuleHeader",
    "ModuleTypeDef",
    "ParameterMapping",
    "SFCAlternative",
    "SFCCodeBlocks",
    "SFCParallel",
    "SFCStep",
    "SFCSubsequence",
    "SFCTransition",
    "SFCTransitionSub",
    "ScopeContext",
    "Sequence",
    "SimpleNamespace",
    "Simple_DataType",
    "SingleModule",
    "SourceSpan",
    "Variable",
    "VariableId",
    "VariableIssue",
    "VariablesAnalyzer",
    "VariablesReport",
    "_hdr",
    "_issue_kinds",
    "_state_ref",
    "_status_bridge_typedef",
    "_varref",
    "analyze_sfc",
    "cast",
    "const",
    "reset_contamination_module",
]
