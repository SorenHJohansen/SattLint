from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

from ._app_analysis_variable_analyses import (
    LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS,
    VARIABLE_ANALYSES,
)
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
    exclusive_group_id: str | None = None
    suite_role: SuiteRole = "single"
    selected_analyzer_keys: tuple[str, ...] | None = None
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


_VARIABLE_DESCRIPTIONS: dict[str, str] = {
    "1": "Run the full high-confidence variable issue suite.",
    "2": "Report declared variables that are never referenced.",
    "3": "Report datatype fields that stay unused in the analyzed target.",
    "4": "Report values that are only read and should likely be CONST.",
    "5": "Report variables that are written but never read.",
    "6": "Report parameter mappings that point at unknown targets.",
    "7": "Report string mapping pairs whose types do not align.",
    "8": "Report repeated complex datatype definitions that can drift apart.",
    "9": "Report min or max mapping pairs with suspicious naming mismatches.",
    "10": "Report magic-number literals that should become named constants.",
    "11": "Report identifiers that collide within the effective namespace.",
    "12": "Report datatypes whose meaning depends on record field ordering.",
    "13": "Report reset flows that can leak stale values across cycles.",
    "14": "Report variable declarations that shadow another visible name.",
    "15": "Report variables that appear to be used only for UI or display concerns.",
    "16": "Report procedure-status patterns that look incomplete or inconsistent.",
    "17": "Report writes that do not appear to have any downstream effect.",
    "18": "Report likely contract mismatches across module boundaries.",
    "19": "Report values that appear to latch implicitly instead of being reset.",
    "20": "Report globals that could likely be narrowed to a smaller scope.",
    "21": "Report hidden coupling created by shared global state.",
    "22": "Report variables with unusually high fan-in or fan-out.",
}

_SECTION_SPECS: tuple[AnalysisSectionSpec, ...] = (
    AnalysisSectionSpec(
        section_id=SECTION_TOP_LEVEL,
        label="Analyze",
        description="Top-level analysis actions and family entry points.",
        sort_order=100,
    ),
    AnalysisSectionSpec(
        section_id=SECTION_VARIABLE_SUITE,
        label="High-confidence suite",
        description="Broad, high-confidence variable issue coverage.",
        sort_order=200,
    ),
    AnalysisSectionSpec(
        section_id=SECTION_VARIABLE_HIGH_CONFIDENCE,
        label="High-confidence checks",
        description="Focused high-confidence variable checks.",
        sort_order=300,
    ),
    AnalysisSectionSpec(
        section_id=SECTION_VARIABLE_LOW_CONFIDENCE,
        label="Low-confidence checks",
        description="Heuristic variable checks that can need manual confirmation.",
        sort_order=400,
    ),
    AnalysisSectionSpec(
        section_id=SECTION_INVESTIGATION,
        label="Investigation tools",
        description="Debug-oriented tracing for variables and module locals.",
        sort_order=500,
    ),
    AnalysisSectionSpec(
        section_id=SECTION_STRUCTURE_ACTIONS,
        label="Structure & modules",
        description="Structural inspections for module layout and graphics rules.",
        sort_order=600,
    ),
    AnalysisSectionSpec(
        section_id=SECTION_INTERFACE_ACTIONS,
        label="Interfaces & communication",
        description="Checks for external interfaces, ICF paths, and MMS usage.",
        sort_order=700,
    ),
    AnalysisSectionSpec(
        section_id=SECTION_CODE_QUALITY_ACTIONS,
        label="Code quality",
        description="Readability and maintainability checks.",
        sort_order=800,
    ),
    AnalysisSectionSpec(
        section_id=SECTION_CATALOG_SUITE,
        label="Analyzer suite",
        description="The registry-backed analyzer suite entry point.",
        sort_order=900,
    ),
    AnalysisSectionSpec(
        section_id=SECTION_CATALOG_ANALYZERS,
        label="Single analyzers",
        description="Registry-backed analyzers exposed one-by-one.",
        sort_order=1000,
    ),
)

TOP_LEVEL_ANALYSIS_FAMILIES: tuple[TopLevelAnalysisFamilySpec, ...] = (
    TopLevelAnalysisFamilySpec(
        family_id=FAMILY_ANALYZE_SUITE,
        label="Full analyzer suite",
        description="Run every enabled registry-backed analyzer.",
        classic_menu_key="1",
        navigation_mode="direct",
        section_ids=(SECTION_TOP_LEVEL,),
        entry_id=ENTRY_ANALYZE_FULL_SUITE,
    ),
    TopLevelAnalysisFamilySpec(
        family_id=FAMILY_VARIABLE_ISSUES,
        label="Variable issues",
        description="Focused variable reports plus investigation tools.",
        classic_menu_key="2",
        navigation_mode="submenu",
        section_ids=(
            SECTION_VARIABLE_SUITE,
            SECTION_VARIABLE_HIGH_CONFIDENCE,
            SECTION_VARIABLE_LOW_CONFIDENCE,
            SECTION_INVESTIGATION,
        ),
    ),
    TopLevelAnalysisFamilySpec(
        family_id=FAMILY_STRUCTURE_MODULES,
        label="Structure & modules",
        description="Inspect module layout, duplication, and tree structure.",
        classic_menu_key="3",
        navigation_mode="submenu",
        section_ids=(SECTION_STRUCTURE_ACTIONS,),
    ),
    TopLevelAnalysisFamilySpec(
        family_id=FAMILY_INTERFACES,
        label="Interfaces & communication",
        description="Check MMS mappings and validate ICF paths.",
        classic_menu_key="4",
        navigation_mode="submenu",
        section_ids=(SECTION_INTERFACE_ACTIONS,),
    ),
    TopLevelAnalysisFamilySpec(
        family_id=FAMILY_CODE_QUALITY,
        label="Code quality",
        description="Readability and maintainability checks.",
        classic_menu_key="5",
        navigation_mode="submenu",
        section_ids=(SECTION_CODE_QUALITY_ACTIONS,),
    ),
    TopLevelAnalysisFamilySpec(
        family_id=FAMILY_ANALYZER_CATALOG,
        label="Analyzer catalog",
        description="Choose one registry-backed analyzer by name.",
        classic_menu_key="6",
        navigation_mode="submenu",
        section_ids=(SECTION_CATALOG_SUITE, SECTION_CATALOG_ANALYZERS),
    ),
    TopLevelAnalysisFamilySpec(
        family_id=FAMILY_INVESTIGATION,
        label="Advanced analysis & debug",
        description="Targeted tracing for variables and module locals.",
        classic_menu_key="7",
        navigation_mode="submenu",
        section_ids=(SECTION_INVESTIGATION,),
    ),
)


def _variable_entry_sort_order(key: str, *, low_confidence: bool) -> int:
    base = 400 if low_confidence else 300
    if key == "1":
        return 200
    return base + int(key)


def _variable_entry(key: str) -> AnalysisCatalogEntry:
    label, kinds = VARIABLE_ANALYSES[key]
    low_confidence = key in LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS
    if key == "1":
        section_id = SECTION_VARIABLE_SUITE
        exclusive_group_id = EXCLUSIVE_GROUP_VARIABLE_HIGH_CONFIDENCE
        suite_role: SuiteRole = "suite"
    elif low_confidence:
        section_id = SECTION_VARIABLE_LOW_CONFIDENCE
        exclusive_group_id = None
        suite_role = "single"
    else:
        section_id = SECTION_VARIABLE_HIGH_CONFIDENCE
        exclusive_group_id = EXCLUSIVE_GROUP_VARIABLE_HIGH_CONFIDENCE
        suite_role = "leaf"
    variable_issue_kinds = None if kinds is None else frozenset(kinds)
    return AnalysisCatalogEntry(
        entry_id=(ENTRY_VARIABLE_HIGH_CONFIDENCE_SUITE if key == "1" else f"variables.issue.{key}"),
        family_id=FAMILY_VARIABLE_ISSUES,
        section_id=section_id,
        label=label,
        description=_VARIABLE_DESCRIPTIONS[key],
        execution=AnalysisExecutionSpec(
            kind="run_variable_analysis",
            handler_name="run_variable_analysis",
            require_targets=True,
            action_text="variable issue analysis",
            normalized_step_id=(STEP_VARIABLE_HIGH_CONFIDENCE_SUITE if key == "1" else f"step.variable-issue.{key}"),
            exclusive_group_id=exclusive_group_id,
            suite_role=suite_role,
            variable_issue_kinds=variable_issue_kinds,
        ),
        sort_order=_variable_entry_sort_order(key, low_confidence=low_confidence),
        classic_menu_key=key,
    )


def _static_catalog_entries() -> tuple[AnalysisCatalogEntry, ...]:
    entries: list[AnalysisCatalogEntry] = [
        AnalysisCatalogEntry(
            entry_id=ENTRY_ANALYZE_FULL_SUITE,
            family_id=FAMILY_ANALYZE_SUITE,
            section_id=SECTION_TOP_LEVEL,
            label="Full analyzer suite",
            description="Run every enabled registry-backed analyzer.",
            execution=AnalysisExecutionSpec(
                kind="run_checks",
                handler_name="_run_checks",
                require_targets=True,
                action_text="analysis checks",
                normalized_step_id=STEP_ANALYZER_SUITE,
                exclusive_group_id=EXCLUSIVE_GROUP_ANALYZER_SUITE,
                suite_role="suite",
            ),
            sort_order=100,
            classic_menu_key="1",
        )
    ]
    entries.extend(_variable_entry(key) for key in VARIABLE_ANALYSES)
    entries.extend(
        [
            AnalysisCatalogEntry(
                entry_id=ENTRY_DATATYPE_USAGE,
                family_id=FAMILY_INVESTIGATION,
                section_id=SECTION_INVESTIGATION,
                label="Datatype usage analysis",
                description="Trace field-level usage for one variable name.",
                execution=AnalysisExecutionSpec(
                    kind="run_handler",
                    handler_name="run_datatype_usage_analysis",
                    require_targets=True,
                    action_text="investigation analysis",
                    normalized_step_id="step.investigation.datatype-usage",
                ),
                sort_order=500,
                classic_menu_key="23",
            ),
            AnalysisCatalogEntry(
                entry_id=ENTRY_VARIABLE_USAGE_TRACE,
                family_id=FAMILY_INVESTIGATION,
                section_id=SECTION_INVESTIGATION,
                label="Variable usage trace",
                description="Show fields and locations for one variable name.",
                execution=AnalysisExecutionSpec(
                    kind="run_handler",
                    handler_name="run_debug_variable_usage",
                    require_targets=True,
                    action_text="investigation analysis",
                    normalized_step_id="step.investigation.variable-usage-trace",
                ),
                sort_order=501,
                classic_menu_key="24",
            ),
            AnalysisCatalogEntry(
                entry_id=ENTRY_MODULE_LOCAL_VARIABLES,
                family_id=FAMILY_INVESTIGATION,
                section_id=SECTION_INVESTIGATION,
                label="Module local variable analysis",
                description="Inspect field usage inside one module path.",
                execution=AnalysisExecutionSpec(
                    kind="run_handler",
                    handler_name="run_module_localvar_analysis",
                    require_targets=True,
                    action_text="investigation analysis",
                    normalized_step_id="step.investigation.module-local-variables",
                ),
                sort_order=502,
                classic_menu_key="25",
            ),
            AnalysisCatalogEntry(
                entry_id="structure.compare-module-variants",
                family_id=FAMILY_STRUCTURE_MODULES,
                section_id=SECTION_STRUCTURE_ACTIONS,
                label="Compare module variants",
                description="Compare matching module names across instances.",
                execution=AnalysisExecutionSpec(
                    kind="run_handler",
                    handler_name="run_module_duplicates_analysis",
                    require_targets=True,
                    action_text="module analysis",
                    normalized_step_id="step.structure.compare-module-variants",
                ),
                sort_order=600,
                classic_menu_key="1",
            ),
            AnalysisCatalogEntry(
                entry_id="structure.find-module-instances",
                family_id=FAMILY_STRUCTURE_MODULES,
                section_id=SECTION_STRUCTURE_ACTIONS,
                label="Find module instances",
                description="List where a module name appears in the current target.",
                execution=AnalysisExecutionSpec(
                    kind="run_handler",
                    handler_name="run_module_find_by_name",
                    require_targets=True,
                    action_text="module analysis",
                    normalized_step_id="step.structure.find-module-instances",
                ),
                sort_order=601,
                classic_menu_key="2",
            ),
            AnalysisCatalogEntry(
                entry_id="structure.inspect-module-tree",
                family_id=FAMILY_STRUCTURE_MODULES,
                section_id=SECTION_STRUCTURE_ACTIONS,
                label="Inspect module tree",
                description="Print the module tree for debugging structure.",
                execution=AnalysisExecutionSpec(
                    kind="run_handler",
                    handler_name="run_module_tree_debug",
                    require_targets=True,
                    action_text="module analysis",
                    normalized_step_id="step.structure.inspect-module-tree",
                ),
                sort_order=602,
                classic_menu_key="3",
            ),
            AnalysisCatalogEntry(
                entry_id="structure.validate-graphics-rules",
                family_id=FAMILY_STRUCTURE_MODULES,
                section_id=SECTION_STRUCTURE_ACTIONS,
                label="Validate graphics rules",
                description="Check configured graphics rules against loaded modules.",
                execution=AnalysisExecutionSpec(
                    kind="run_handler",
                    handler_name="run_graphics_rules_validation",
                    require_targets=True,
                    action_text="module analysis",
                    normalized_step_id="step.structure.validate-graphics-rules",
                ),
                sort_order=603,
                classic_menu_key="4",
            ),
            AnalysisCatalogEntry(
                entry_id="interfaces.mms-interface-variables",
                family_id=FAMILY_INTERFACES,
                section_id=SECTION_INTERFACE_ACTIONS,
                label="MMS interface variables",
                description="Inventory MMSWriteVar or MMSReadVar usage and related checks.",
                execution=AnalysisExecutionSpec(
                    kind="run_handler",
                    handler_name="run_mms_interface_analysis",
                    require_targets=True,
                    action_text="interface analysis",
                    normalized_step_id="step.interfaces.mms-interface-variables",
                ),
                sort_order=700,
                classic_menu_key="1",
            ),
            AnalysisCatalogEntry(
                entry_id="interfaces.validate-icf-paths",
                family_id=FAMILY_INTERFACES,
                section_id=SECTION_INTERFACE_ACTIONS,
                label="Validate ICF paths",
                description="Validate ICF entries against each program AST.",
                execution=AnalysisExecutionSpec(
                    kind="run_handler",
                    handler_name="run_icf_validation",
                    require_targets=True,
                    action_text="interface analysis",
                    normalized_step_id="step.interfaces.validate-icf-paths",
                ),
                sort_order=701,
                classic_menu_key="2",
            ),
            AnalysisCatalogEntry(
                entry_id="interfaces.format-icf-files",
                family_id=FAMILY_INTERFACES,
                section_id=SECTION_INTERFACE_ACTIONS,
                label="Format ICF files",
                description="Normalize Unit, Journal, Operation, and Group spacing in configured .icf files.",
                execution=AnalysisExecutionSpec(
                    kind="run_handler",
                    handler_name="run_icf_formatter",
                    require_targets=True,
                    action_text="interface analysis",
                    normalized_step_id="step.interfaces.format-icf-files",
                ),
                sort_order=702,
                classic_menu_key="3",
            ),
            AnalysisCatalogEntry(
                entry_id=ENTRY_COMMENTED_OUT_CODE,
                family_id=FAMILY_CODE_QUALITY,
                section_id=SECTION_CODE_QUALITY_ACTIONS,
                label="Commented-out code",
                description="Scan raw source comments for code-like content.",
                execution=AnalysisExecutionSpec(
                    kind="run_handler",
                    handler_name="run_comment_code_analysis",
                    require_targets=True,
                    action_text="code-quality checks",
                    normalized_step_id="step.code-quality.commented-out-code",
                ),
                sort_order=800,
                classic_menu_key="1",
            ),
            AnalysisCatalogEntry(
                entry_id=ENTRY_CATALOG_FULL_SUITE,
                family_id=FAMILY_ANALYZER_CATALOG,
                section_id=SECTION_CATALOG_SUITE,
                label="Run full analyzer suite",
                description="Run every default analyzer in sequence.",
                execution=AnalysisExecutionSpec(
                    kind="run_checks",
                    handler_name="_run_checks",
                    require_targets=True,
                    action_text="analyzer catalog",
                    normalized_step_id=STEP_ANALYZER_SUITE,
                    exclusive_group_id=EXCLUSIVE_GROUP_ANALYZER_SUITE,
                    suite_role="suite",
                ),
                sort_order=900,
                classic_menu_key="1",
            ),
        ]
    )
    return tuple(entries)


STATIC_ANALYSIS_CATALOG_ENTRIES: tuple[AnalysisCatalogEntry, ...] = _static_catalog_entries()


def analysis_section_specs() -> tuple[AnalysisSectionSpec, ...]:
    return _SECTION_SPECS


def top_level_analysis_family(family_id: str) -> TopLevelAnalysisFamilySpec:
    for family in TOP_LEVEL_ANALYSIS_FAMILIES:
        if family.family_id == family_id:
            return family
    raise KeyError(family_id)


def dynamic_analyzer_catalog_entries(analyzer_specs: Sequence[Any]) -> tuple[AnalysisCatalogEntry, ...]:
    entries: list[AnalysisCatalogEntry] = []
    for index, spec in enumerate(analyzer_specs, start=2):
        spec_obj = cast(object, spec)
        key = str(getattr(spec_obj, "key", "") or "").strip()
        name = str(getattr(spec_obj, "name", "") or "").strip()
        description = str(getattr(spec_obj, "description", "") or "").strip()
        if not key or not name:
            continue
        entries.append(
            AnalysisCatalogEntry(
                entry_id=f"catalog.analyzer.{key}",
                family_id=FAMILY_ANALYZER_CATALOG,
                section_id=SECTION_CATALOG_ANALYZERS,
                label=name,
                description=description or f"Run analyzer '{name}'.",
                execution=AnalysisExecutionSpec(
                    kind="run_checks",
                    handler_name="_run_checks",
                    require_targets=True,
                    action_text="analyzer catalog",
                    normalized_step_id=f"step.analyzer.{key}",
                    exclusive_group_id=EXCLUSIVE_GROUP_ANALYZER_SUITE,
                    suite_role="leaf",
                    selected_analyzer_keys=(key,),
                ),
                sort_order=1000 + index,
                classic_menu_key=str(index),
            )
        )
    return tuple(entries)


def analysis_catalog_entries(*, analyzer_specs: Sequence[Any] = ()) -> tuple[AnalysisCatalogEntry, ...]:
    return tuple(
        sorted(
            STATIC_ANALYSIS_CATALOG_ENTRIES + dynamic_analyzer_catalog_entries(analyzer_specs),
            key=lambda item: item.sort_order,
        )
    )


def analysis_catalog_entry(entry_id: str, *, analyzer_specs: Sequence[Any] = ()) -> AnalysisCatalogEntry | None:
    for entry in analysis_catalog_entries(analyzer_specs=analyzer_specs):
        if entry.entry_id == entry_id:
            return entry
    return None


def analysis_entries_for_section(
    section_id: str, *, analyzer_specs: Sequence[Any] = ()
) -> tuple[AnalysisCatalogEntry, ...]:
    return tuple(
        entry for entry in analysis_catalog_entries(analyzer_specs=analyzer_specs) if entry.section_id == section_id
    )


def analysis_entries_for_sections(
    section_ids: Iterable[str], *, analyzer_specs: Sequence[Any] = ()
) -> tuple[AnalysisCatalogEntry, ...]:
    wanted = tuple(section_ids)
    return tuple(
        entry for entry in analysis_catalog_entries(analyzer_specs=analyzer_specs) if entry.section_id in wanted
    )


def analysis_entries_for_family(
    family_id: str, *, analyzer_specs: Sequence[Any] = ()
) -> tuple[AnalysisCatalogEntry, ...]:
    family = top_level_analysis_family(family_id)
    entries: list[AnalysisCatalogEntry] = []
    if family.entry_id is not None:
        entry = analysis_catalog_entry(family.entry_id, analyzer_specs=analyzer_specs)
        if entry is not None:
            entries.append(entry)
    entries.extend(analysis_entries_for_sections(family.section_ids, analyzer_specs=analyzer_specs))
    seen: set[str] = set()
    result: list[AnalysisCatalogEntry] = []
    for entry in entries:
        if entry.entry_id in seen:
            continue
        seen.add(entry.entry_id)
        result.append(entry)
    return tuple(result)
