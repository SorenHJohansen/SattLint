from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .analyzers.variables import IssueKind

ExecutionKind = Literal["run_checks", "run_handler", "run_variable_analysis"]
SuiteRole = Literal["suite", "leaf", "single"]
NavigationMode = Literal["direct", "submenu"]

FAMILY_ANALYZE_SUITE = "analyze-suite"
FAMILY_VARIABLE_ISSUES = "variable-issues"
FAMILY_STRUCTURE_MODULES = "structure-modules"
FAMILY_INTERFACES = "interfaces"
FAMILY_CODE_QUALITY = "code-quality"
FAMILY_ANALYZER_CATALOG = "analyzer-catalog"
FAMILY_INVESTIGATION = "investigation"

SECTION_TOP_LEVEL = "top-level"
SECTION_VARIABLE_SUITE = "variable-suite"
SECTION_VARIABLE_HIGH_CONFIDENCE = "variable-high-confidence"
SECTION_VARIABLE_LOW_CONFIDENCE = "variable-low-confidence"
SECTION_INVESTIGATION = "investigation"
SECTION_STRUCTURE_ACTIONS = "structure-actions"
SECTION_INTERFACE_ACTIONS = "interface-actions"
SECTION_CODE_QUALITY_ACTIONS = "code-quality-actions"
SECTION_CATALOG_SUITE = "catalog-suite"
SECTION_CATALOG_ISSUE_CHECKS = "catalog-issue-checks"
SECTION_CATALOG_ANALYZERS = "catalog-analyzers"

ENTRY_ANALYZE_FULL_SUITE = "analyze.full-suite"
ENTRY_VARIABLE_HIGH_CONFIDENCE_SUITE = "variables.high-confidence-suite"
ENTRY_DATATYPE_USAGE = "investigation.datatype-usage"
ENTRY_VARIABLE_USAGE_TRACE = "investigation.variable-usage-trace"
ENTRY_MODULE_LOCAL_VARIABLES = "investigation.module-local-variables"
ENTRY_COMMENTED_OUT_CODE = "code-quality.commented-out-code"
ENTRY_CATALOG_FULL_SUITE = "catalog.full-suite"

STEP_ANALYZER_SUITE = "step.analyzer-suite"
STEP_VARIABLE_HIGH_CONFIDENCE_SUITE = "step.variable-high-confidence-suite"

EXCLUSIVE_GROUP_ANALYZER_SUITE = "exclusive.analyzer-suite"
EXCLUSIVE_GROUP_VARIABLE_HIGH_CONFIDENCE = "exclusive.variable-high-confidence"


@dataclass(frozen=True)
class AnalysisExecutionSpec:
    kind: ExecutionKind
    handler_name: str
    require_targets: bool
    action_text: str
    normalized_step_id: str
    step_label: str | None = None
    exclusive_group_id: str | None = None
    suite_role: SuiteRole = "single"
    selected_analyzer_keys: tuple[str, ...] | None = None
    selected_issue_kind_names: frozenset[str] | None = None
    variable_issue_kinds: frozenset[IssueKind] | None = None


@dataclass(frozen=True)
class AnalysisSectionSpec:
    section_id: str
    label: str
    description: str
    sort_order: int


@dataclass(frozen=True)
class AnalysisCatalogEntry:
    entry_id: str
    family_id: str
    section_id: str
    label: str
    description: str
    execution: AnalysisExecutionSpec
    sort_order: int
    classic_menu_key: str | None = None


@dataclass(frozen=True)
class TopLevelAnalysisFamilySpec:
    family_id: str
    label: str
    description: str
    classic_menu_key: str
    navigation_mode: NavigationMode
    section_ids: tuple[str, ...]
    entry_id: str | None = None
