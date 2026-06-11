"""Analyzer-backed enrichment for editor-facing semantic snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from sattline_parser.models.ast_model import BasePicture

from .analyzers.framework import AnalysisContext, AnalysisSharedArtifacts, Issue, build_analysis_context
from .analyzers.registry._registry_dispatch import (
    get_lsp_projection_analyzers,
    get_registry_analyzer_spec,
    run_registry_analyzer,
)
from .analyzers.variables import analyze_variables
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
from .reporting.variables_report import VariableIssue, VariablesReport


def _run_variables_report(
    context: AnalysisContext,
    *,
    debug: bool,
    target_is_library: bool,
    include_dependency_moduletype_usage: bool | None = None,
) -> VariablesReport:
    try:
        variables_spec = get_registry_analyzer_spec("variables")
    except KeyError:
        return analyze_variables(
            context.base_picture,
            analysis_context=context,
            debug=debug,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=target_is_library,
            include_dependency_moduletype_usage=include_dependency_moduletype_usage,
            selected_issue_kinds=context.selected_issue_kinds,
            config=context.config,
        )

    return cast(
        VariablesReport,
        run_registry_analyzer(
            variables_spec,
            context,
            overrides=(
                None
                if include_dependency_moduletype_usage is None
                else {"include_dependency_moduletype_usage": include_dependency_moduletype_usage}
            ),
        ),
    )


def _project_lsp_report_diagnostics(
    base_picture: BasePicture,
    project_graph: ProjectGraph,
    debug: bool,
    *,
    config: Mapping[str, object] | None = None,
    target_is_library: bool = False,
    shared_artifacts: AnalysisSharedArtifacts | None = None,
) -> DiagnosticProjectionResult:
    context = build_analysis_context(
        base_picture,
        graph=project_graph,
        debug=debug,
        target_is_library=target_is_library,
        config=config,
        shared_artifacts=shared_artifacts,
        create_shared_artifacts=True,
    )
    module_sites_by_path = build_module_diagnostic_sites(base_picture)
    projected_reports: list[DiagnosticProjectionResult] = []

    for analyzer in get_lsp_projection_analyzers():
        report = run_registry_analyzer(analyzer.spec, context)
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
    definitions_by_key: Mapping[tuple[str, ...], SymbolDefinition],
    *,
    config: Mapping[str, object] | None = None,
    target_is_library: bool = False,
) -> SemanticAnalysisArtifacts:
    context = build_analysis_context(
        base_picture,
        graph=project_graph,
        debug=debug,
        target_is_library=target_is_library,
        config=config,
        create_shared_artifacts=True,
    )
    usage_report = _run_variables_report(
        context,
        debug=debug,
        target_is_library=target_is_library,
        include_dependency_moduletype_usage=True,
    )

    diagnostics: tuple[VariableIssue, ...] = ()
    semantic_diagnostics_by_file: dict[str, tuple[SemanticDiagnostic, ...]] = {}
    semantic_diagnostic_drops = ()
    if collect_variable_diagnostics:
        diagnostics_report = _run_variables_report(
            context,
            debug=debug,
            target_is_library=target_is_library,
        )
        diagnostics = tuple(diagnostics_report.issues)
        projection_result = merge_diagnostic_projection_results(
            project_variable_issues(diagnostics, definitions_by_key),
            _project_lsp_report_diagnostics(
                base_picture,
                project_graph,
                debug,
                config=context.config,
                target_is_library=target_is_library,
                shared_artifacts=context.shared_artifacts,
            ),
        )
        semantic_diagnostics_by_file = projection_result.diagnostics_by_file
        semantic_diagnostic_drops = projection_result.dropped_issues

    return SemanticAnalysisArtifacts(
        diagnostics=diagnostics,
        accesses_by_definition_key=dict(usage_report.accesses_by_definition_key),
        effect_flow_edges=dict(usage_report.effect_flow_edges),
        effect_flow_display_names=dict(usage_report.effect_flow_display_names),
        semantic_diagnostics_by_file=semantic_diagnostics_by_file,
        semantic_diagnostic_drops=semantic_diagnostic_drops,
    )


__all__ = ["build_variable_semantic_artifacts"]
