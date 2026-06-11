from __future__ import annotations

from types import SimpleNamespace

from sattlint import _app_analysis_catalog as catalog
from sattlint import _app_analysis_planner as planner


def test_planner_prefers_variable_suite_over_overlapping_leaf() -> None:
    plan = planner.plan_analysis_entries(
        [catalog.ENTRY_VARIABLE_HIGH_CONFIDENCE_SUITE, "variables.issue.2"],
        available_handler_names={"run_variable_analysis"},
    )

    assert [step.step_id for step in plan.steps] == [catalog.STEP_VARIABLE_HIGH_CONFIDENCE_SUITE]
    assert [skip.entry_id for skip in plan.skipped_entries] == ["variables.issue.2"]
    assert plan.is_runnable is True


def test_planner_merges_suite_aliases_and_drops_overlapping_catalog_leaf() -> None:
    analyzer_specs = [SimpleNamespace(key="shadowing", name="Shadowing", description="Check shadowing")]

    plan = planner.plan_analysis_entries(
        [
            catalog.ENTRY_CATALOG_FULL_SUITE,
            catalog.ENTRY_ANALYZE_FULL_SUITE,
            "catalog.analyzer.shadowing",
        ],
        analyzer_specs=analyzer_specs,
        available_handler_names={"_run_checks"},
    )

    assert [step.step_id for step in plan.steps] == [catalog.STEP_ANALYZER_SUITE]
    assert plan.steps[0].source_entry_ids == (
        catalog.ENTRY_ANALYZE_FULL_SUITE,
        catalog.ENTRY_CATALOG_FULL_SUITE,
    )
    assert [skip.entry_id for skip in plan.skipped_entries] == [
        "catalog.analyzer.shadowing",
        catalog.ENTRY_CATALOG_FULL_SUITE,
    ]


def test_planner_uses_catalog_sort_order_instead_of_selection_order() -> None:
    plan = planner.plan_analysis_entries(
        [catalog.ENTRY_COMMENTED_OUT_CODE, catalog.ENTRY_DATATYPE_USAGE, "variables.issue.2"],
        available_handler_names={"run_comment_code_analysis", "run_datatype_usage_analysis", "run_variable_analysis"},
    )

    assert [step.label for step in plan.steps] == [
        "Unused variables",
        "Datatype usage analysis",
        "Commented-out code",
    ]


def test_planner_reports_missing_handlers() -> None:
    plan = planner.plan_analysis_entries(
        [catalog.ENTRY_COMMENTED_OUT_CODE],
        available_handler_names=set(),
    )

    assert plan.is_runnable is False
    assert [item.handler_name for item in plan.missing_handlers] == ["run_comment_code_analysis"]
    assert [step.label for step in plan.executable_steps] == []


def test_planner_merges_same_analyzer_issue_leaf_steps() -> None:
    analyzer_specs = [SimpleNamespace(key="dataflow", name="Dataflow", description="Check dataflow")]

    plan = planner.plan_analysis_entries(
        [
            "catalog.issue.dataflow.dead_overwrite",
            "catalog.issue.dataflow.read_before_write",
        ],
        analyzer_specs=analyzer_specs,
        available_handler_names={"_run_checks"},
    )

    assert [step.step_id for step in plan.steps] == ["step.analyzer.dataflow"]
    assert plan.steps[0].label == "Dataflow"
    assert plan.steps[0].source_entry_ids == (
        "catalog.issue.dataflow.read_before_write",
        "catalog.issue.dataflow.dead_overwrite",
    )
    assert plan.steps[0].execution.selected_issue_kind_names == frozenset(
        {"dataflow.read_before_write", "dataflow.dead_overwrite"}
    )
    assert [skip.entry_id for skip in plan.skipped_entries] == ["catalog.issue.dataflow.dead_overwrite"]


def test_render_analysis_plan_summary_mentions_skips_and_missing_handlers() -> None:
    analyzer_specs = [SimpleNamespace(key="shadowing", name="Shadowing", description="Check shadowing")]
    plan = planner.plan_analysis_entries(
        [catalog.ENTRY_ANALYZE_FULL_SUITE, "catalog.analyzer.shadowing", "missing.entry"],
        analyzer_specs=analyzer_specs,
        available_handler_names={"run_variable_analysis"},
    )

    summary = planner.render_analysis_plan_summary(plan)

    assert "Execution order" in summary
    assert "Full analyzer suite (missing handler)" in summary
    assert "Normalized overlaps" in summary
    assert "Unknown selections" in summary
    assert "Missing handlers" in summary
