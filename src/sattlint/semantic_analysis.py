"""Analyzer-backed enrichment for editor-facing semantic snapshots."""

from __future__ import annotations

from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from .analyzers.framework import AnalysisContext, Issue
from .analyzers.variables import VariablesAnalyzer
from .core.diagnostics import (
    DiagnosticProjectionResult,
    SemanticDiagnostic,
    build_module_diagnostic_sites,
    merge_diagnostic_projection_results,
    project_report_issues,
    project_variable_issues,
)
from .core.semantic import SemanticAnalysisArtifacts, SymbolDefinition
from .models.project_graph import ProjectGraph
from .reporting.variables_report import VariableIssue


def _project_lsp_report_diagnostics(
    base_picture: BasePicture,
    project_graph: ProjectGraph,
    debug: bool,
) -> DiagnosticProjectionResult:
    from .analyzers.registry import SEMANTIC_LAYER_ANALYZER_KEY, get_default_analyzer_catalog

    context = AnalysisContext(
        base_picture=base_picture,
        graph=project_graph,
        debug=debug,
    )
    module_sites_by_path = build_module_diagnostic_sites(base_picture)
    projected_reports: list[DiagnosticProjectionResult] = []

    for analyzer in get_default_analyzer_catalog().analyzers:
        if not analyzer.delivery.lsp_exposed:
            continue
        if analyzer.spec.key in {SEMANTIC_LAYER_ANALYZER_KEY, "variables"}:
            continue

        report = analyzer.spec.run(context)
        issues = getattr(report, "issues", None)
        if not isinstance(issues, list):
            continue

        typed_issues = cast(list[object], issues)
        report_issues_list: list[Issue] = []
        for issue in typed_issues:
            if isinstance(issue, Issue):
                report_issues_list.append(issue)
        report_issues = tuple(report_issues_list)
        if not report_issues:
            continue

        projected_reports.append(
            project_report_issues(report_issues, module_sites_by_path, analyzer_key=analyzer.spec.key)
        )

    return merge_diagnostic_projection_results(*projected_reports)


def build_variable_semantic_artifacts(
    base_picture: BasePicture,
    project_graph: ProjectGraph,
    collect_variable_diagnostics: bool,
    debug: bool,
    definitions_by_key: dict[tuple[str, ...], SymbolDefinition] | dict[tuple[str, ...], Any],
) -> SemanticAnalysisArtifacts:
    usage_analyzer = VariablesAnalyzer(
        base_picture,
        debug=debug,
        fail_loudly=False,
        unavailable_libraries=project_graph.unavailable_libraries,
        include_dependency_moduletype_usage=True,
    )
    usage_analyzer.run()

    diagnostics: tuple[VariableIssue, ...] = ()
    semantic_diagnostics_by_file: dict[str, tuple[SemanticDiagnostic, ...]] = {}
    semantic_diagnostic_drops = ()
    if collect_variable_diagnostics:
        diagnostics_analyzer = VariablesAnalyzer(
            base_picture,
            debug=debug,
            fail_loudly=False,
            unavailable_libraries=project_graph.unavailable_libraries,
        )
        diagnostics = tuple(diagnostics_analyzer.run())
        projection_result = merge_diagnostic_projection_results(
            project_variable_issues(diagnostics, definitions_by_key),
            _project_lsp_report_diagnostics(base_picture, project_graph, debug),
        )
        semantic_diagnostics_by_file = projection_result.diagnostics_by_file
        semantic_diagnostic_drops = projection_result.dropped_issues

    return SemanticAnalysisArtifacts(
        diagnostics=diagnostics,
        accesses_by_definition_key={
            key: tuple(events) for key, events in usage_analyzer.access_graph.by_path_key.items()
        },
        effect_flow_edges=usage_analyzer.effect_flow_edges,
        effect_flow_display_names=usage_analyzer.effect_flow_display_names,
        semantic_diagnostics_by_file=semantic_diagnostics_by_file,
        semantic_diagnostic_drops=semantic_diagnostic_drops,
    )


__all__ = ["build_variable_semantic_artifacts"]
