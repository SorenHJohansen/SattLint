"""Analyzer-backed enrichment for editor-facing semantic snapshots."""

from __future__ import annotations

from typing import Any

from .analyzers.framework import AnalysisContext, Issue
from .analyzers.variables import VariablesAnalyzer
from .core.diagnostics import (
    SemanticDiagnostic,
    build_module_diagnostic_sites,
    merge_semantic_diagnostics_by_file,
    project_report_issues_by_file,
    project_variable_issues_by_file,
)
from .core.semantic import SemanticAnalysisArtifacts, SymbolDefinition
from .models.ast_model import BasePicture
from .models.project_graph import ProjectGraph
from .reporting.variables_report import VariableIssue


def _project_lsp_report_diagnostics(
    base_picture: BasePicture,
    project_graph: ProjectGraph,
    debug: bool,
) -> dict[str, tuple[SemanticDiagnostic, ...]]:
    from .analyzers.registry import SEMANTIC_LAYER_ANALYZER_KEY, get_default_analyzer_catalog

    context = AnalysisContext(
        base_picture=base_picture,
        graph=project_graph,
        debug=debug,
    )
    module_sites_by_path = build_module_diagnostic_sites(base_picture)
    projected_reports: list[dict[str, tuple[SemanticDiagnostic, ...]]] = []

    for analyzer in get_default_analyzer_catalog().analyzers:
        if not analyzer.delivery.lsp_exposed:
            continue
        if analyzer.spec.key in {SEMANTIC_LAYER_ANALYZER_KEY, "variables"}:
            continue

        report = analyzer.spec.run(context)
        issues = getattr(report, "issues", None)
        if not isinstance(issues, list):
            continue

        report_issues = tuple(issue for issue in issues if isinstance(issue, Issue))
        if not report_issues:
            continue

        projected_reports.append(
            project_report_issues_by_file(
                report_issues,
                module_sites_by_path,
                analyzer_key=analyzer.spec.key,
            )
        )

    return merge_semantic_diagnostics_by_file(*projected_reports)


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
    if collect_variable_diagnostics:
        diagnostics_analyzer = VariablesAnalyzer(
            base_picture,
            debug=debug,
            fail_loudly=False,
            unavailable_libraries=project_graph.unavailable_libraries,
        )
        diagnostics = tuple(diagnostics_analyzer.run())
        semantic_diagnostics_by_file = merge_semantic_diagnostics_by_file(
            project_variable_issues_by_file(diagnostics, definitions_by_key),
            _project_lsp_report_diagnostics(base_picture, project_graph, debug),
        )

    return SemanticAnalysisArtifacts(
        diagnostics=diagnostics,
        accesses_by_definition_key={
            key: tuple(events) for key, events in usage_analyzer.access_graph.by_path_key.items()
        },
        effect_flow_edges=usage_analyzer.effect_flow_edges,
        effect_flow_display_names=usage_analyzer.effect_flow_display_names,
        semantic_diagnostics_by_file=semantic_diagnostics_by_file,
    )


__all__ = ["build_variable_semantic_artifacts"]
