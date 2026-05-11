"""Optional and derived report helpers for the static-analysis pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sattlint.devtools.baselines import build_analysis_diff_report, load_finding_collection
from sattlint.devtools.current_debt_snapshot import build_current_debt_snapshot_report
from sattlint.devtools.derived_reports import (
    build_incremental_analysis_report,
    build_performance_budget_report,
    build_profiling_summary_report,
)
from sattlint.devtools.differential import build_differential_report
from sattlint.devtools.finding_exports import build_pipeline_finding_collection
from sattlint.devtools.semantic_reports import build_rule_metrics_report, build_sattline_semantic_report
from sattlint.devtools.structural_reports import WorkspaceGraphInputs
from sattlint.path_sanitizer import sanitize_path_for_report


def collect_optional_reports(
    context: dict[str, Any],
    *,
    trace_target: Path | None,
    repo_root: Path,
    collect_structural_report_bundle: Any,
    collect_trace_report: Any,
    run_corpus_suite_fn: Any,
) -> dict[str, Any]:
    progress = context["progress"]
    structural_budget_report: dict[str, Any] = {"skipped": not context["run_structural_reports"]}
    architecture_report: dict[str, Any] = {"findings": [], "skipped": not context["run_structural_reports"]}
    analyzer_registry_report: dict[str, Any] = {"rules": [], "skipped": not context["run_structural_reports"]}
    dependency_graph_report: dict[str, Any] = {"edges": [], "skipped": not context["run_structural_reports"]}
    call_graph_report: dict[str, Any] = {"edges": [], "skipped": not context["run_structural_reports"]}
    graphics_layout_report: dict[str, Any] = {
        "entries": [],
        "groups": [],
        "findings": [],
        "skipped": not context["run_structural_reports"],
    }
    impact_analysis_report: dict[str, Any] = {
        "library_impacts": [],
        "module_impacts": [],
        "skipped": not context["run_structural_reports"],
    }
    workspace_graph_inputs: WorkspaceGraphInputs | None = None

    if context["run_structural_reports"]:
        progress.start_stage("structural_reports")
        structural_reports = collect_structural_report_bundle(progress_callback=progress.log)
        structural_budget_report = structural_reports.structural_budget_report
        architecture_report = structural_reports.architecture_report
        analyzer_registry_report = structural_reports.analyzer_registry_report
        workspace_graph_inputs = structural_reports.graph_inputs
        dependency_graph_report = structural_reports.dependency_graph_report
        call_graph_report = structural_reports.call_graph_report
        graphics_layout_report = structural_reports.graphics_layout_report
        impact_analysis_report = structural_reports.impact_analysis_report
        progress.complete_stage(
            "structural_reports",
            detail=(
                f"{len(dependency_graph_report['edges'])} dependency edges, "
                f"{len(call_graph_report['edges'])} call edges"
            ),
        )
    else:
        progress.skip_stage("structural_reports", detail="skipped by profile")

    trace_report: dict[str, Any] | None = None
    if context["run_trace"]:
        if trace_target is None:
            raise ValueError("trace_target is required when run_trace is enabled")
        trace_target_label = sanitize_path_for_report(trace_target, repo_root=repo_root) or trace_target.as_posix()
        progress.start_stage("trace", detail=trace_target_label)
        trace_report = collect_trace_report(trace_target)
        progress.complete_stage("trace", detail=trace_target_label)
    else:
        progress.skip_stage("trace", detail="skipped by profile")

    corpus_results_report: dict[str, Any] | None = None
    if context["run_corpus"]:
        progress.start_stage("corpus")
        corpus_results_report = run_corpus_suite_fn(
            context["output_dir"],
            manifest_dir=context["resolved_corpus_manifest_dir"],
            repo_root=repo_root,
            write_results=False,
        ).to_dict()
        if corpus_results_report is None:
            raise ValueError("run_corpus_suite returned no report")
        corpus_summary = corpus_results_report["summary"]
        progress.complete_stage(
            "corpus",
            detail=(f"{corpus_summary['case_count']} cases, {corpus_summary['failed_count']} failed"),
        )
    else:
        progress.skip_stage("corpus", detail="no manifest directory")

    return {
        "analyzer_registry_report": analyzer_registry_report,
        "architecture_report": architecture_report,
        "call_graph_report": call_graph_report,
        "corpus_results_report": corpus_results_report,
        "dependency_graph_report": dependency_graph_report,
        "graphics_layout_report": graphics_layout_report,
        "impact_analysis_report": impact_analysis_report,
        "structural_budget_report": structural_budget_report,
        "trace_report": trace_report,
        "workspace_graph_inputs": workspace_graph_inputs,
    }


def build_derived_reports(
    context: dict[str, Any],
    stage_reports: dict[str, Any],
    optional_reports: dict[str, Any],
    *,
    baseline_findings: Path | None,
    slow_phase_threshold_ms: float,
    phase_budget_ms: float,
    total_budget_ms: float,
    repo_root: Path,
    default_trace_target: Path,
    build_coverage_summary_report_fn: Any,
) -> dict[str, Any]:
    incremental_analysis_report = build_incremental_analysis_report(
        context["resolved_changed_files"],
        repo_root=repo_root,
        analyzer_registry_report=(
            optional_reports["analyzer_registry_report"] if context["run_structural_reports"] else None
        ),
    )
    coverage_summary_report: dict[str, Any] | None = None
    if context["run_coverage_summary"]:
        coverage_summary_report = build_coverage_summary_report_fn(repo_root)
    current_debt_snapshot_report = build_current_debt_snapshot_report(
        repo_root,
        structural_budget_report=optional_reports["structural_budget_report"],
        coverage_summary_report=coverage_summary_report,
    )

    profiling_summary_report = build_profiling_summary_report(
        optional_reports["trace_report"],
        slow_phase_threshold_ms=slow_phase_threshold_ms,
    )
    performance_budget_report = build_performance_budget_report(
        profiling_summary_report,
        total_budget_ms=total_budget_ms,
        phase_budget_ms=phase_budget_ms,
    )

    phase2_rule_metadata_gate = {
        "status": "skipped",
        "enforced_fields": ["acceptance_tests", "mutation_applicability"],
        "advisory_fields": ["corpus_cases"],
        "blocking_finding_ids": [],
        "advisory_finding_ids": [],
        "blocking_rule_ids": [],
        "advisory_rule_ids": [],
    }
    if context["run_structural_reports"]:
        phase2_rule_metadata_gate = optional_reports["architecture_report"].get(
            "phase2_rule_metadata_gate",
            phase2_rule_metadata_gate,
        )

    context["progress"].start_stage("findings")
    finding_collection = build_pipeline_finding_collection(
        repo_root=repo_root,
        ruff_findings=stage_reports["ruff_findings"],
        pyright_findings=stage_reports["pyright_findings"],
        pytest_report=stage_reports["pytest_report"],
        vulture_findings=(
            []
            if stage_reports["vulture_report"].get("skipped")
            else list(stage_reports["vulture_report"].get("findings", []))
        ),
        bandit_findings=(
            []
            if stage_reports["bandit_report"].get("skipped")
            else list(stage_reports["bandit_report"].get("findings", []))
        ),
        architecture_findings=list(optional_reports["architecture_report"].get("findings", [])),
    )
    context["progress"].complete_stage(
        "findings",
        detail=f"{len(finding_collection.findings)} normalized findings",
    )

    sattline_semantic_report: dict[str, Any] | None = None
    rule_metrics_report: dict[str, Any] | None = None
    if context["run_structural_reports"]:
        findings_dict = finding_collection.to_dict()
        sattline_semantic_report = build_sattline_semantic_report(findings_dict)
        rule_metrics_report = build_rule_metrics_report(
            findings_dict,
            optional_reports["analyzer_registry_report"]
            if not optional_reports["analyzer_registry_report"].get("skipped")
            else None,
        )

    analysis_diff_report: dict[str, Any] | None = None
    differential_report: dict[str, Any] | None = None
    if baseline_findings is not None:
        baseline_collection = load_finding_collection(baseline_findings)
        baseline_label = (
            sanitize_path_for_report(baseline_findings, repo_root=repo_root) or baseline_findings.as_posix()
        )
        analysis_diff_report = build_analysis_diff_report(
            baseline=baseline_collection,
            current=finding_collection,
            baseline_label=baseline_label,
            current_label="findings.json",
        )
        differential_report = build_differential_report(
            baseline_collection,
            finding_collection,
            baseline_label=baseline_label,
            current_label="findings.json",
        ).to_dict()

    mutation_results: dict[str, Any] | None = None
    if context.get("run_mutation_analysis"):
        from sattlint.devtools.mutation_engine import run_mutation_analysis

        target = context.get("mutation_target") or default_trace_target
        if target.exists():
            mutation_results = run_mutation_analysis(target, finding_collection).to_dict()

    return {
        "analysis_diff_report": analysis_diff_report,
        "current_debt_snapshot_report": current_debt_snapshot_report,
        "coverage_summary_report": coverage_summary_report,
        "differential_report": differential_report,
        "finding_collection": finding_collection,
        "findings_schema": finding_collection.schema_metadata,
        "incremental_analysis_report": incremental_analysis_report,
        "mutation_results": mutation_results,
        "performance_budget_report": performance_budget_report,
        "phase2_rule_metadata_gate": phase2_rule_metadata_gate,
        "profiling_summary_report": profiling_summary_report,
        "rule_metrics_report": rule_metrics_report,
        "sattline_semantic_report": sattline_semantic_report,
    }
