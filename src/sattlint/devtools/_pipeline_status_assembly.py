"""Pipeline status, exit-code, and count assembly helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sattlint.devtools.corpus import CORPUS_RESULTS_FILENAME


def build_static_tool_statuses(
    stage_reports: dict[str, Any],
    *,
    make_tool_status: Callable[..., dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        "ruff": make_tool_status(
            status=(
                "skipped"
                if stage_reports["ruff_report"].get("skipped")
                else "fail"
                if stage_reports["ruff_report"]["exit_code"] != 0
                else "pass"
            ),
            report=None if stage_reports["ruff_report"].get("skipped") else "ruff.json",
            raw_exit_code=None
            if stage_reports["ruff_report"].get("skipped")
            else stage_reports["ruff_report"]["exit_code"],
            normalized_exit_code=(
                None if stage_reports["ruff_report"].get("skipped") else stage_reports["ruff_report"]["exit_code"]
            ),
            finding_count=stage_reports["ruff_report"].get("finding_count", 0),
            detail=(
                stage_reports["ruff_report"].get("detail", "skipped by check selection")
                if stage_reports["ruff_report"].get("skipped")
                else f"{stage_reports['ruff_report'].get('finding_count', 0)} findings"
            ),
        ),
        "pyright": make_tool_status(
            status=(
                "skipped"
                if stage_reports["pyright_report"].get("skipped")
                else "fail"
                if stage_reports["pyright_report"].get("error_count", 0) > 0
                else "pass_with_warnings"
                if stage_reports["pyright_report"].get("warning_count", 0) > 0
                else "pass"
            ),
            report=None if stage_reports["pyright_report"].get("skipped") else "pyright.json",
            raw_exit_code=(
                None if stage_reports["pyright_report"].get("skipped") else stage_reports["pyright_report"]["exit_code"]
            ),
            normalized_exit_code=(
                None
                if stage_reports["pyright_report"].get("skipped")
                else stage_reports["pyright_report"]["effective_exit_code"]
            ),
            finding_count=stage_reports["pyright_report"].get("error_count", 0),
            note_count=stage_reports["pyright_report"].get("warning_count", 0),
            detail=(
                stage_reports["pyright_report"].get("detail", "skipped by check selection")
                if stage_reports["pyright_report"].get("skipped")
                else (
                    f"{stage_reports['pyright_report'].get('error_count', 0)} errors, "
                    f"{stage_reports['pyright_report'].get('warning_count', 0)} warnings"
                )
            ),
        ),
        "pytest": make_tool_status(
            status=(
                "skipped"
                if stage_reports["pytest_report"].get("skipped")
                else "fail"
                if stage_reports["pytest_report"]["summary"]["failures"]
                or stage_reports["pytest_report"]["summary"]["errors"]
                else "pass"
            ),
            report=None if stage_reports["pytest_report"].get("skipped") else "pytest.json",
            raw_exit_code=(
                None if stage_reports["pytest_report"].get("skipped") else stage_reports["pytest_report"]["exit_code"]
            ),
            normalized_exit_code=(
                None if stage_reports["pytest_report"].get("skipped") else stage_reports["pytest_report"]["exit_code"]
            ),
            finding_count=(
                stage_reports["pytest_report"]["summary"]["failures"]
                + stage_reports["pytest_report"]["summary"]["errors"]
            ),
            detail=(
                stage_reports["pytest_report"].get("detail", "skipped by check selection")
                if stage_reports["pytest_report"].get("skipped")
                else (
                    f"{stage_reports['pytest_report']['summary']['tests']} tests, "
                    f"{stage_reports['pytest_report']['summary']['failures']} failures, "
                    f"{stage_reports['pytest_report']['summary']['errors']} errors"
                )
            ),
        ),
        "vulture": make_tool_status(
            status=(
                "skipped"
                if stage_reports["vulture_report"].get("skipped")
                else "fail"
                if stage_reports["vulture_report"].get("finding_count", 0)
                or stage_reports["vulture_report"].get("exit_code", 0) != 0
                else "pass"
            ),
            report=None if stage_reports["vulture_report"].get("skipped") else "vulture.json",
            raw_exit_code=stage_reports["vulture_report"].get("exit_code"),
            normalized_exit_code=(
                0
                if stage_reports["vulture_report"].get("skipped")
                else stage_reports["vulture_report"].get("exit_code")
            ),
            finding_count=stage_reports["vulture_report"].get("finding_count", 0),
            detail=(
                "skipped by profile"
                if stage_reports["vulture_report"].get("skipped")
                else f"{stage_reports['vulture_report'].get('finding_count', 0)} findings"
            ),
        ),
        "bandit": make_tool_status(
            status=(
                "skipped"
                if stage_reports["bandit_report"].get("skipped")
                else "fail"
                if stage_reports["bandit_report"].get("findings")
                or stage_reports["bandit_report"].get("errors")
                or stage_reports["bandit_report"].get("exit_code", 0) != 0
                else "pass"
            ),
            report=None if stage_reports["bandit_report"].get("skipped") else "bandit.json",
            raw_exit_code=stage_reports["bandit_report"].get("exit_code"),
            normalized_exit_code=(
                0 if stage_reports["bandit_report"].get("skipped") else stage_reports["bandit_report"].get("exit_code")
            ),
            finding_count=len(stage_reports["bandit_report"].get("findings", [])),
            detail=(
                "skipped by profile"
                if stage_reports["bandit_report"].get("skipped")
                else f"{len(stage_reports['bandit_report'].get('findings', []))} findings"
            ),
        ),
    }


def build_extended_tool_statuses(
    optional_reports: dict[str, Any],
    derived_reports: dict[str, Any],
    context: dict[str, Any],
    *,
    make_tool_status: Callable[..., dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        "corpus": make_tool_status(
            status=(
                "skipped"
                if optional_reports["corpus_results_report"] is None
                else "fail"
                if optional_reports["corpus_results_report"]["summary"]["failed_count"] > 0
                else "pass"
            ),
            report=None if optional_reports["corpus_results_report"] is None else CORPUS_RESULTS_FILENAME,
            raw_exit_code=None,
            normalized_exit_code=(
                None
                if optional_reports["corpus_results_report"] is None
                else 1
                if optional_reports["corpus_results_report"]["summary"]["failed_count"] > 0
                else 0
            ),
            finding_count=(
                0
                if optional_reports["corpus_results_report"] is None
                else optional_reports["corpus_results_report"]["summary"]["failed_count"]
            ),
            detail=(
                "skipped because no manifest directory was provided"
                if optional_reports["corpus_results_report"] is None
                else (
                    f"{optional_reports['corpus_results_report']['summary']['case_count']} cases, "
                    f"{optional_reports['corpus_results_report']['summary']['failed_count']} failed"
                )
            ),
        ),
        "rule_metadata": make_tool_status(
            status=(
                "skipped"
                if not context["run_structural_reports"]
                else "fail"
                if derived_reports["phase2_rule_metadata_gate"]["status"] == "fail"
                else "pass"
            ),
            report=None if not context["run_structural_reports"] else "architecture.json",
            raw_exit_code=None,
            normalized_exit_code=(
                None
                if not context["run_structural_reports"]
                else 1
                if derived_reports["phase2_rule_metadata_gate"]["status"] == "fail"
                else 0
            ),
            finding_count=len(derived_reports["phase2_rule_metadata_gate"]["blocking_rule_ids"]),
            detail=(
                "skipped by profile"
                if not context["run_structural_reports"]
                else (
                    f"{len(derived_reports['phase2_rule_metadata_gate']['blocking_rule_ids'])} "
                    "rules missing enforced metadata"
                    if derived_reports["phase2_rule_metadata_gate"]["status"] == "fail"
                    else None
                )
            ),
        ),
    }


def build_core_tool_statuses(
    stage_reports: dict[str, Any],
    optional_reports: dict[str, Any],
    derived_reports: dict[str, Any],
    context: dict[str, Any],
    *,
    make_tool_status: Callable[..., dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    tool_statuses = build_static_tool_statuses(stage_reports, make_tool_status=make_tool_status)
    tool_statuses.update(
        build_extended_tool_statuses(
            optional_reports,
            derived_reports,
            context,
            make_tool_status=make_tool_status,
        )
    )
    return tool_statuses


def build_policy_tool_statuses(
    derived_reports: dict[str, Any],
    *,
    fail_on_drift: bool,
    fail_on_budget: bool,
    make_tool_status: Callable[..., dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        "baseline_drift": make_tool_status(
            status=(
                "skipped"
                if derived_reports["analysis_diff_report"] is None
                else "fail"
                if fail_on_drift
                and (
                    derived_reports["analysis_diff_report"]["summary"]["new_count"] > 0
                    or derived_reports["analysis_diff_report"]["summary"]["resolved_count"] > 0
                )
                else "pass"
            ),
            report=None if derived_reports["analysis_diff_report"] is None else "analysis_diff.json",
            raw_exit_code=None,
            normalized_exit_code=(
                None
                if derived_reports["analysis_diff_report"] is None
                else 1
                if fail_on_drift
                and (
                    derived_reports["analysis_diff_report"]["summary"]["new_count"] > 0
                    or derived_reports["analysis_diff_report"]["summary"]["resolved_count"] > 0
                )
                else 0
            ),
            finding_count=(
                0
                if derived_reports["analysis_diff_report"] is None
                else derived_reports["analysis_diff_report"]["summary"]["new_count"]
                + derived_reports["analysis_diff_report"]["summary"]["resolved_count"]
            ),
            detail=(
                "skipped: no baseline supplied"
                if derived_reports["analysis_diff_report"] is None
                else (
                    f"{derived_reports['analysis_diff_report']['summary']['new_count']} new, "
                    f"{derived_reports['analysis_diff_report']['summary']['resolved_count']} resolved, "
                    f"{derived_reports['analysis_diff_report']['summary']['changed_count']} changed"
                )
            ),
        ),
        "performance_budget": make_tool_status(
            status=(
                "skipped"
                if derived_reports["performance_budget_report"] is None
                else "fail"
                if fail_on_budget and derived_reports["performance_budget_report"]["status"] == "fail"
                else "pass_with_notes"
                if derived_reports["performance_budget_report"]["status"] == "fail"
                else "pass"
            ),
            report=None if derived_reports["performance_budget_report"] is None else "performance_budget.json",
            raw_exit_code=None,
            normalized_exit_code=(
                None
                if derived_reports["performance_budget_report"] is None
                else 1
                if fail_on_budget and derived_reports["performance_budget_report"]["status"] == "fail"
                else 0
            ),
            finding_count=(
                0
                if derived_reports["performance_budget_report"] is None
                else derived_reports["performance_budget_report"]["violation_count"]
            ),
            detail=(
                "skipped because trace profiling is unavailable"
                if derived_reports["performance_budget_report"] is None
                else f"{derived_reports['performance_budget_report']['violation_count']} budget violations"
            ),
        ),
    }


def build_pipeline_tool_exit_codes(
    stage_reports: dict[str, Any],
    optional_reports: dict[str, Any],
    derived_reports: dict[str, Any],
    context: dict[str, Any],
    *,
    fail_on_drift: bool,
    fail_on_budget: bool,
) -> dict[str, int | None]:
    return {
        "ruff": None if stage_reports["ruff_report"].get("skipped") else stage_reports["ruff_report"]["exit_code"],
        "pyright": (
            None
            if stage_reports["pyright_report"].get("skipped")
            else stage_reports["pyright_report"]["effective_exit_code"]
        ),
        "pytest": None
        if stage_reports["pytest_report"].get("skipped")
        else stage_reports["pytest_report"]["exit_code"],
        "vulture": stage_reports["vulture_report"].get("exit_code"),
        "bandit": stage_reports["bandit_report"].get("exit_code"),
        "corpus": (
            None
            if optional_reports["corpus_results_report"] is None
            else 1
            if optional_reports["corpus_results_report"]["summary"]["failed_count"] > 0
            else 0
        ),
        "rule_metadata": (
            None
            if not context["run_structural_reports"]
            else 1
            if derived_reports["phase2_rule_metadata_gate"]["status"] == "fail"
            else 0
        ),
        "baseline_drift": (
            None
            if derived_reports["analysis_diff_report"] is None
            else 1
            if fail_on_drift
            and (
                derived_reports["analysis_diff_report"]["summary"]["new_count"] > 0
                or derived_reports["analysis_diff_report"]["summary"]["resolved_count"] > 0
            )
            else 0
        ),
        "performance_budget": (
            None
            if derived_reports["performance_budget_report"] is None
            else 1
            if fail_on_budget and derived_reports["performance_budget_report"]["status"] == "fail"
            else 0
        ),
    }


def build_pipeline_counts(
    stage_reports: dict[str, Any],
    optional_reports: dict[str, Any],
    derived_reports: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, int | float]:
    incremental_analysis_report = derived_reports["incremental_analysis_report"]
    profiling_summary_report = derived_reports["profiling_summary_report"]
    performance_budget_report = derived_reports["performance_budget_report"]
    pytest_summary = stage_reports["pytest_report"].get(
        "summary", {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    )
    return {
        "baseline_new_findings": 0
        if derived_reports["analysis_diff_report"] is None
        else derived_reports["analysis_diff_report"]["summary"]["new_count"],
        "baseline_resolved_findings": 0
        if derived_reports["analysis_diff_report"] is None
        else derived_reports["analysis_diff_report"]["summary"]["resolved_count"],
        "baseline_changed_findings": 0
        if derived_reports["analysis_diff_report"] is None
        else derived_reports["analysis_diff_report"]["summary"]["changed_count"],
        "baseline_unchanged_findings": 0
        if derived_reports["analysis_diff_report"] is None
        else derived_reports["analysis_diff_report"]["summary"]["unchanged_count"],
        "incremental_changed_file_count": 0
        if incremental_analysis_report is None
        else incremental_analysis_report["summary"]["changed_file_count"],
        "incremental_candidate_analyzer_count": 0
        if incremental_analysis_report is None
        else incremental_analysis_report["summary"]["impacted_analyzer_count"],
        "incremental_blocking_analyzer_count": 0
        if incremental_analysis_report is None
        else incremental_analysis_report["summary"]["fallback_analyzer_count"],
        "normalized_findings": len(derived_reports["finding_collection"].findings),
        "corpus_case_count": 0
        if optional_reports["corpus_results_report"] is None
        else optional_reports["corpus_results_report"]["summary"]["case_count"],
        "corpus_passed_case_count": 0
        if optional_reports["corpus_results_report"] is None
        else optional_reports["corpus_results_report"]["summary"]["passed_count"],
        "corpus_failed_case_count": 0
        if optional_reports["corpus_results_report"] is None
        else optional_reports["corpus_results_report"]["summary"]["failed_count"],
        "corpus_execution_error_count": 0
        if optional_reports["corpus_results_report"] is None
        else optional_reports["corpus_results_report"]["summary"]["execution_error_count"],
        "ruff_findings": stage_reports["ruff_report"].get("finding_count", 0),
        "pyright_errors": stage_reports["pyright_report"].get("error_count", 0),
        "pyright_warnings": stage_reports["pyright_report"].get("warning_count", 0),
        "pytest_failures": pytest_summary["failures"],
        "pytest_errors": pytest_summary["errors"],
        "vulture_findings": stage_reports["vulture_report"].get("finding_count", 0),
        "bandit_findings": len(stage_reports["bandit_report"].get("findings", [])),
        "architecture_findings": len(optional_reports["architecture_report"]["findings"]),
        "semantic_rule_count": len(optional_reports["analyzer_registry_report"]["rules"]),
        "phase2_rule_metadata_blocking_gaps": len(derived_reports["phase2_rule_metadata_gate"]["blocking_rule_ids"]),
        "phase2_rule_metadata_advisory_gaps": len(derived_reports["phase2_rule_metadata_gate"]["advisory_rule_ids"]),
        "dependency_graph_edges": len(optional_reports["dependency_graph_report"]["edges"]),
        "call_graph_edges": len(optional_reports["call_graph_report"]["edges"]),
        "graphics_layout_entries": len(optional_reports["graphics_layout_report"]["entries"]),
        "graphics_layout_groups": len(optional_reports["graphics_layout_report"]["groups"]),
        "graphics_layout_findings": len(optional_reports["graphics_layout_report"]["findings"]),
        "impact_analysis_library_nodes": len(optional_reports["impact_analysis_report"]["library_impacts"]),
        "impact_analysis_module_nodes": len(optional_reports["impact_analysis_report"]["module_impacts"]),
        "workspace_graph_snapshot_failures": 0
        if optional_reports["workspace_graph_inputs"] is None
        else len(optional_reports["workspace_graph_inputs"].snapshot_failures),
        "trace_dataflow_issues": 0
        if optional_reports["trace_report"] is None
        else optional_reports["trace_report"].get("dataflow_analysis", {}).get("issue_count", 0),
        "trace_unreachable_logic": 0
        if optional_reports["trace_report"] is None
        else len(optional_reports["trace_report"].get("heuristics", {}).get("unreachable_logic", [])),
        "trace_transform_violations": 0
        if optional_reports["trace_report"] is None
        else len(optional_reports["trace_report"].get("heuristics", {}).get("transform_invariant_violations", [])),
        "profiling_total_duration_ms": 0.0
        if profiling_summary_report is None
        else profiling_summary_report["total_duration_ms"],
        "profiling_phase_count": 0
        if profiling_summary_report is None
        else profiling_summary_report["summary"]["phase_count"],
        "profiling_slow_phase_count": 0
        if profiling_summary_report is None
        else profiling_summary_report["summary"]["slow_phase_count"],
        "performance_budget_violation_count": 0
        if performance_budget_report is None
        else performance_budget_report["violation_count"],
    }


__all__ = [
    "build_core_tool_statuses",
    "build_extended_tool_statuses",
    "build_pipeline_counts",
    "build_pipeline_tool_exit_codes",
    "build_policy_tool_statuses",
    "build_static_tool_statuses",
]
