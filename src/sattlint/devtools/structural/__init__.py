"""Structural devtools reports and analysis helpers."""

from __future__ import annotations

from . import impact_analyzer, metrics_dashboard, structural_reports
from .structural_reports import (
    GRAPHICS_LAYOUT_COMPARISON_FIELDS,
    REPO_ROOT,
    StructuralReportsBundle,
    WorkspaceGraphInputs,
    collect_analyzer_registry_report,
    collect_architecture_report,
    collect_call_graph_report,
    collect_dependency_graph_report,
    collect_graphics_layout_report,
    collect_impact_analysis_report,
    collect_phase2_rule_metadata_gate,
    collect_structural_budget_report,
    collect_structural_reports,
    collect_workspace_graph_inputs,
    count_structural_lines,
    main,
    normalize_graph_inputs,
    read_structural_text,
)

__all__ = [
    "GRAPHICS_LAYOUT_COMPARISON_FIELDS",
    "REPO_ROOT",
    "StructuralReportsBundle",
    "WorkspaceGraphInputs",
    "collect_analyzer_registry_report",
    "collect_architecture_report",
    "collect_call_graph_report",
    "collect_dependency_graph_report",
    "collect_graphics_layout_report",
    "collect_impact_analysis_report",
    "collect_phase2_rule_metadata_gate",
    "collect_structural_budget_report",
    "collect_structural_reports",
    "collect_workspace_graph_inputs",
    "count_structural_lines",
    "impact_analyzer",
    "main",
    "metrics_dashboard",
    "normalize_graph_inputs",
    "read_structural_text",
    "structural_reports",
]
