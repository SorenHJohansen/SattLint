from __future__ import annotations

from types import SimpleNamespace

from sattlint import _app_analysis_catalog as catalog
from sattlint import _app_analysis_catalog_metadata as catalog_metadata


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


def test_same_cycle_issue_catalog_entries_are_derived_from_rule_source() -> None:
    analyzer_specs = [
        SimpleNamespace(key="same-cycle", name="Same-cycle hazards", description="Check same-scan hazards")
    ]

    entries = catalog.analysis_catalog_entries(analyzer_specs=analyzer_specs)
    same_cycle_issue_entries = [
        entry.entry_id
        for entry in entries
        if entry.section_id == catalog.SECTION_CATALOG_ISSUE_CHECKS
        and entry.entry_id.startswith("catalog.issue.same_cycle_")
    ]

    assert same_cycle_issue_entries == [
        "catalog.issue.same_cycle_parallel_read_write_hazard",
        "catalog.issue.same_cycle_non_state_multi_site_hazard",
        "catalog.issue.same_cycle_shared_access_hazard",
    ]

    shared_access_entry = catalog.analysis_catalog_entry(
        "catalog.issue.same_cycle_shared_access_hazard",
        analyzer_specs=analyzer_specs,
    )
    assert shared_access_entry is not None
    assert shared_access_entry.execution.selected_analyzer_keys == ("same-cycle",)
    assert shared_access_entry.execution.selected_issue_kind_names == frozenset({"same_cycle_shared_access_hazard"})


def test_same_cycle_issue_catalog_details_are_available() -> None:
    specs = catalog_metadata.analyzer_issue_leaf_specs("same-cycle")

    assert [spec.issue_kind for spec in specs] == [
        "same_cycle_parallel_read_write_hazard",
        "same_cycle_non_state_multi_site_hazard",
        "same_cycle_shared_access_hazard",
    ]
    assert (
        catalog_metadata.planner_entry_detection(
            "catalog.issue.same_cycle_shared_access_hazard",
            "same-cycle",
            "",
        )
        == "Shared variables that are read and written across multiple module paths within the same scan."
    )
    assert "intra-scan ordering" in catalog_metadata.planner_entry_how(
        "catalog.issue.same_cycle_shared_access_hazard",
        "same-cycle",
        "",
    )


def test_same_cycle_analyzer_details_are_derived_from_spec_and_issue_specs() -> None:
    detection = catalog_metadata.planner_entry_detection(
        "catalog.analyzer.same-cycle",
        "same-cycle",
        "Detect same-scan shared-variable hazards across modules and parallel SFC branches",
    )
    how = catalog_metadata.planner_entry_how(
        "catalog.analyzer.same-cycle",
        "same-cycle",
        "Detect same-scan shared-variable hazards across modules and parallel SFC branches",
    )

    assert detection == "Detect same-scan shared-variable hazards across modules and parallel SFC branches."
    assert "Non-state multi-site hazard" in how
    assert "Parallel read/write hazard" in how
    assert "Same-scan shared access hazard" in how


def test_composite_analyzer_details_are_derived_from_declared_composition() -> None:
    timing_detection = catalog_metadata.planner_entry_detection(
        "catalog.analyzer.timing",
        "timing",
        "Detect scan-cycle temporal hazards and non precision-scan-safe resource usage",
    )
    timing_how = catalog_metadata.planner_entry_how(
        "catalog.analyzer.timing",
        "timing",
        "Detect scan-cycle temporal hazards and non precision-scan-safe resource usage",
    )
    powerup_detection = catalog_metadata.planner_entry_detection(
        "catalog.analyzer.powerup",
        "powerup",
        "Detect startup-value gaps and unsafe startup defaults that affect power-up behavior",
    )
    powerup_how = catalog_metadata.planner_entry_how(
        "catalog.analyzer.powerup",
        "powerup",
        "Detect startup-value gaps and unsafe startup defaults that affect power-up behavior",
    )
    concurrency_detection = catalog_metadata.planner_entry_detection(
        "catalog.analyzer.scan-concurrency",
        "scan-concurrency",
        "Detect parallel scan or sequence branches that write the same variable without arbitration",
    )
    concurrency_how = catalog_metadata.planner_entry_how(
        "catalog.analyzer.scan-concurrency",
        "scan-concurrency",
        "Detect parallel scan or sequence branches that write the same variable without arbitration",
    )

    assert timing_detection == "Detect scan-cycle temporal hazards and non precision-scan-safe resource usage."
    assert "Runs Lightweight dataflow and Scan-loop resource usage" in timing_how
    assert "Scan-cycle stale read" in timing_how
    assert powerup_detection == "Detect startup-value gaps and unsafe startup defaults that affect power-up behavior."
    assert (
        powerup_how == "Runs Initial value validation and Unsafe defaults and collates their findings into one report."
    )
    assert concurrency_detection == (
        "Detect parallel scan or sequence branches that write the same variable without arbitration."
    )
    assert concurrency_how == "Runs Same-cycle hazards and reports only Parallel branch write race findings."
