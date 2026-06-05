from __future__ import annotations

from ._app_analysis_catalog_shared import (
    ENTRY_ANALYZE_FULL_SUITE,
    ENTRY_CATALOG_FULL_SUITE,
    ENTRY_COMMENTED_OUT_CODE,
    ENTRY_DATATYPE_USAGE,
    ENTRY_MODULE_LOCAL_VARIABLES,
    ENTRY_VARIABLE_HIGH_CONFIDENCE_SUITE,
    ENTRY_VARIABLE_USAGE_TRACE,
    EXCLUSIVE_GROUP_ANALYZER_SUITE,
    EXCLUSIVE_GROUP_VARIABLE_HIGH_CONFIDENCE,
    FAMILY_ANALYZE_SUITE,
    FAMILY_ANALYZER_CATALOG,
    FAMILY_CODE_QUALITY,
    FAMILY_INTERFACES,
    FAMILY_INVESTIGATION,
    FAMILY_STRUCTURE_MODULES,
    FAMILY_VARIABLE_ISSUES,
    SECTION_CATALOG_ANALYZERS,
    SECTION_CATALOG_SUITE,
    SECTION_CODE_QUALITY_ACTIONS,
    SECTION_INTERFACE_ACTIONS,
    SECTION_INVESTIGATION,
    SECTION_STRUCTURE_ACTIONS,
    SECTION_TOP_LEVEL,
    SECTION_VARIABLE_HIGH_CONFIDENCE,
    SECTION_VARIABLE_LOW_CONFIDENCE,
    SECTION_VARIABLE_SUITE,
    STEP_ANALYZER_SUITE,
    STEP_VARIABLE_HIGH_CONFIDENCE_SUITE,
    AnalysisCatalogEntry,
    AnalysisExecutionSpec,
    AnalysisSectionSpec,
    SuiteRole,
    TopLevelAnalysisFamilySpec,
)
from ._app_analysis_variable_analyses import (
    LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS,
    VARIABLE_ANALYSES,
)

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

SECTION_SPECS: tuple[AnalysisSectionSpec, ...] = (
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


def build_static_catalog_entries() -> tuple[AnalysisCatalogEntry, ...]:
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


STATIC_ANALYSIS_CATALOG_ENTRIES: tuple[AnalysisCatalogEntry, ...] = build_static_catalog_entries()
