from __future__ import annotations

from types import SimpleNamespace

from sattlint import _app_analysis_catalog as catalog


def test_top_level_analysis_families_preserve_classic_numbering() -> None:
    families = catalog.TOP_LEVEL_ANALYSIS_FAMILIES

    assert [(family.classic_menu_key, family.label) for family in families] == [
        ("1", "Full analyzer suite"),
        ("2", "Variable issues"),
        ("3", "Structure & modules"),
        ("4", "Interfaces & communication"),
        ("5", "Code quality"),
        ("6", "Analyzer catalog"),
        ("7", "Advanced analysis & debug"),
    ]
    assert families[0].entry_id == catalog.ENTRY_ANALYZE_FULL_SUITE
    assert families[0].navigation_mode == "direct"
    assert families[1].section_ids[-1] == catalog.SECTION_INVESTIGATION
    assert families[-1].section_ids == (catalog.SECTION_INVESTIGATION,)


def test_variable_issue_catalog_reuses_investigation_entries() -> None:
    entries = catalog.analysis_entries_for_sections(
        (
            catalog.SECTION_VARIABLE_SUITE,
            catalog.SECTION_VARIABLE_HIGH_CONFIDENCE,
            catalog.SECTION_VARIABLE_LOW_CONFIDENCE,
            catalog.SECTION_INVESTIGATION,
        )
    )

    entry_ids = {entry.entry_id for entry in entries}
    assert catalog.ENTRY_VARIABLE_HIGH_CONFIDENCE_SUITE in entry_ids
    assert catalog.ENTRY_DATATYPE_USAGE in entry_ids
    assert catalog.ENTRY_VARIABLE_USAGE_TRACE in entry_ids
    assert catalog.ENTRY_MODULE_LOCAL_VARIABLES in entry_ids

    suite_entry = catalog.analysis_catalog_entry(catalog.ENTRY_VARIABLE_HIGH_CONFIDENCE_SUITE)
    assert suite_entry is not None
    assert suite_entry.execution.kind == "run_variable_analysis"
    assert suite_entry.execution.suite_role == "suite"
    assert suite_entry.execution.exclusive_group_id == catalog.EXCLUSIVE_GROUP_VARIABLE_HIGH_CONFIDENCE


def test_dynamic_analyzer_catalog_entries_share_suite_group() -> None:
    analyzer_specs = [
        SimpleNamespace(key="shadowing", name="Shadowing", description="Check shadowing"),
        SimpleNamespace(key="comments", name="Comments", description="Comment quality"),
    ]

    entries = catalog.analysis_catalog_entries(analyzer_specs=analyzer_specs)

    full_suite = catalog.analysis_catalog_entry(catalog.ENTRY_CATALOG_FULL_SUITE, analyzer_specs=analyzer_specs)
    assert full_suite is not None
    assert full_suite.execution.normalized_step_id == catalog.STEP_ANALYZER_SUITE

    dynamic_entries = [entry for entry in entries if entry.section_id == catalog.SECTION_CATALOG_ANALYZERS]
    assert [entry.entry_id for entry in dynamic_entries] == [
        "catalog.analyzer.shadowing",
        "catalog.analyzer.comments",
    ]
    assert [entry.classic_menu_key for entry in dynamic_entries] == ["2", "3"]
    assert all(entry.execution.kind == "run_checks" for entry in dynamic_entries)
    assert all(
        entry.execution.exclusive_group_id == catalog.EXCLUSIVE_GROUP_ANALYZER_SUITE for entry in dynamic_entries
    )
    assert dynamic_entries[0].execution.selected_analyzer_keys == ("shadowing",)


def test_analysis_catalog_entry_returns_none_for_unknown_id() -> None:
    assert catalog.analysis_catalog_entry("missing.entry") is None
