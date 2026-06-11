from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, cast

from ._app_analysis_catalog_data import (
    SECTION_SPECS as _SECTION_SPECS,
)
from ._app_analysis_catalog_data import (
    STATIC_ANALYSIS_CATALOG_ENTRIES,
    TOP_LEVEL_ANALYSIS_FAMILIES,
)
from ._app_analysis_catalog_metadata import (
    analyzer_has_issue_leaf_specs,
    analyzer_issue_exclusive_group_id,
    analyzer_issue_leaf_specs,
)
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
    SECTION_CATALOG_ISSUE_CHECKS,
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
    TopLevelAnalysisFamilySpec,
)

__all__ = [
    "ENTRY_ANALYZE_FULL_SUITE",
    "ENTRY_CATALOG_FULL_SUITE",
    "ENTRY_COMMENTED_OUT_CODE",
    "ENTRY_DATATYPE_USAGE",
    "ENTRY_MODULE_LOCAL_VARIABLES",
    "ENTRY_VARIABLE_HIGH_CONFIDENCE_SUITE",
    "ENTRY_VARIABLE_USAGE_TRACE",
    "EXCLUSIVE_GROUP_ANALYZER_SUITE",
    "EXCLUSIVE_GROUP_VARIABLE_HIGH_CONFIDENCE",
    "FAMILY_ANALYZER_CATALOG",
    "FAMILY_ANALYZE_SUITE",
    "FAMILY_CODE_QUALITY",
    "FAMILY_INTERFACES",
    "FAMILY_INVESTIGATION",
    "FAMILY_STRUCTURE_MODULES",
    "FAMILY_VARIABLE_ISSUES",
    "SECTION_CATALOG_ANALYZERS",
    "SECTION_CATALOG_ISSUE_CHECKS",
    "SECTION_CATALOG_SUITE",
    "SECTION_CODE_QUALITY_ACTIONS",
    "SECTION_INTERFACE_ACTIONS",
    "SECTION_INVESTIGATION",
    "SECTION_STRUCTURE_ACTIONS",
    "SECTION_TOP_LEVEL",
    "SECTION_VARIABLE_HIGH_CONFIDENCE",
    "SECTION_VARIABLE_LOW_CONFIDENCE",
    "SECTION_VARIABLE_SUITE",
    "STATIC_ANALYSIS_CATALOG_ENTRIES",
    "STEP_ANALYZER_SUITE",
    "STEP_VARIABLE_HIGH_CONFIDENCE_SUITE",
    "TOP_LEVEL_ANALYSIS_FAMILIES",
    "AnalysisCatalogEntry",
    "AnalysisExecutionSpec",
    "AnalysisSectionSpec",
    "TopLevelAnalysisFamilySpec",
    "analysis_catalog_entries",
    "analysis_catalog_entry",
    "analysis_entries_for_family",
    "analysis_entries_for_section",
    "analysis_entries_for_sections",
    "analysis_section_specs",
    "dynamic_analyzer_catalog_entries",
    "top_level_analysis_family",
]


def analysis_section_specs() -> tuple[AnalysisSectionSpec, ...]:
    return _SECTION_SPECS


def top_level_analysis_family(family_id: str) -> TopLevelAnalysisFamilySpec:
    for family in TOP_LEVEL_ANALYSIS_FAMILIES:
        if family.family_id == family_id:
            return family
    raise KeyError(family_id)


def dynamic_analyzer_catalog_entries(analyzer_specs: Sequence[Any]) -> tuple[AnalysisCatalogEntry, ...]:
    entries: list[AnalysisCatalogEntry] = []
    issue_entries: list[AnalysisCatalogEntry] = []
    issue_sort_order = 950
    for index, spec in enumerate(analyzer_specs, start=2):
        spec_obj = cast(object, spec)
        key = str(getattr(spec_obj, "key", "") or "").strip()
        name = str(getattr(spec_obj, "name", "") or "").strip()
        description = str(getattr(spec_obj, "description", "") or "").strip()
        if not key or not name:
            continue
        has_issue_leaf_specs = analyzer_has_issue_leaf_specs(key)
        exclusive_group_id = analyzer_issue_exclusive_group_id(key)
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
                    step_label=name,
                    exclusive_group_id=(exclusive_group_id or EXCLUSIVE_GROUP_ANALYZER_SUITE),
                    suite_role=("suite" if has_issue_leaf_specs else "leaf"),
                    selected_analyzer_keys=(key,),
                ),
                sort_order=1000 + index,
                classic_menu_key=str(index),
            )
        )
        for item_index, issue_spec in enumerate(analyzer_issue_leaf_specs(key), start=1):
            issue_entries.append(
                AnalysisCatalogEntry(
                    entry_id=f"catalog.issue.{issue_spec.issue_kind}",
                    family_id=FAMILY_ANALYZER_CATALOG,
                    section_id=SECTION_CATALOG_ISSUE_CHECKS,
                    label=f"{name}: {issue_spec.label}",
                    description=f"Run only the {issue_spec.label} findings from {name}.",
                    execution=AnalysisExecutionSpec(
                        kind="run_checks",
                        handler_name="_run_checks",
                        require_targets=True,
                        action_text="analyzer issue check",
                        normalized_step_id=f"step.analyzer.{key}",
                        step_label=name,
                        exclusive_group_id=exclusive_group_id,
                        suite_role="leaf",
                        selected_analyzer_keys=(key,),
                        selected_issue_kind_names=frozenset({issue_spec.issue_kind}),
                    ),
                    sort_order=issue_sort_order + item_index,
                )
            )
        issue_sort_order += len(analyzer_issue_leaf_specs(key)) + 1
    return tuple(issue_entries + entries)


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
