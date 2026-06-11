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
from sattlint.analyzers.sfc import analyze_sfc
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.analyzers.variables._variables_effect_flow import EffectFlowTracker
from sattlint.reporting.variables_report import (
    ALL_VARIABLE_ANALYSIS_KINDS,
    VariableIssue,
    VariablesReport,
)
from sattlint.resolution.scope import ScopeContext
from sattlint.types import VariableId
from tests._reset_contamination_test_api import reset_contamination_module
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
