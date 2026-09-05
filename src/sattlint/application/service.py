"""Typed application service API for project analysis.

This is the Phase 5 contract: callers interact with a deliberate
:class:`Project` domain object and typed :class:`AnalysisOptions` instead of
raw ``ConfigDict``/``(BasePicture, ProjectGraph)`` tuples.  The application
layer owns the ``Project → SemanticSnapshot → Analyzer execution →
AnalysisResult`` pipeline, so callers never build a snapshot themselves.

The service is additive: the existing ``run_*``/``collect_run_checks_result``
surfaces remain for terminal-facing flows; this module is the typed entry point
for API consumers.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sattline_parser.models.ast_model import BasePicture

from ..analyzers import dispatch as analysis_dispatch_module
from ..analyzers.framework import AnalysisContext, Report, build_analysis_context
from ..config.types import ConfigDict
from ..core.semantic import SemanticSnapshot, build_snapshot_from_loaded_project
from ..models.project_graph import ProjectGraph
from . import analyze as analyze_application
from . import project as project_application


@dataclass(frozen=True)
class Project:
    """Deliberate domain object for one loaded analysis target."""

    name: str
    base_picture: BasePicture
    graph: ProjectGraph
    config: ConfigDict
    entry_file: Path
    workspace_root: Path


@dataclass(frozen=True)
class AnalysisOptions:
    """Typed application options, decoupled from the raw project config."""

    selected_analyzer_keys: tuple[str, ...] | None = None
    selected_issue_kinds: frozenset[str] | None = None
    collect_variable_diagnostics: bool = True
    debug: bool = False


@dataclass(frozen=True)
class AnalyzerReport:
    analyzer_key: str
    report: Report


@dataclass(frozen=True)
class ProjectAnalysisResult:
    project: Project
    snapshot: SemanticSnapshot
    analyzer_reports: tuple[AnalyzerReport, ...]
    selected_analyzer_keys: tuple[str, ...]


def _resolve_entry_file(project_name: str, graph: ProjectGraph, config: ConfigDict) -> Path:
    root_source_path_for_name = getattr(graph, "root_source_path_for_name", None)
    if callable(root_source_path_for_name):
        root_source_path = root_source_path_for_name(project_name)
        if isinstance(root_source_path, Path):
            return root_source_path.resolve()

    source_files = graph.source_files
    if source_files:
        return next(iter(source_files)).resolve()

    program_dir = Path(config["program_dir"]).resolve()
    return program_dir


def load_project_handle(
    cfg: ConfigDict,
    target_name: str | None = None,
    *,
    use_cache: bool = True,
    use_file_ast_cache: bool = True,
    refresh_mode: str = "full",
    collect_stage_timings: bool = False,
    status_update_fn: Callable[[str], None] | None = None,
) -> Project:
    """Load an analysis target and return it as a typed :class:`Project`."""
    base_picture, graph = project_application.load_project(
        cfg,
        target_name,
        use_cache=use_cache,
        use_file_ast_cache=use_file_ast_cache,
        refresh_mode=refresh_mode,
        collect_stage_timings=collect_stage_timings,
        status_update_fn=status_update_fn,
    )
    resolved_name = target_name or graph.ast_by_name.keys().__iter__().__next__()
    entry_file = _resolve_entry_file(resolved_name, graph, cfg)
    workspace_root = Path(cfg["program_dir"]).resolve()
    return Project(
        name=resolved_name,
        base_picture=base_picture,
        graph=graph,
        config=cfg,
        entry_file=entry_file,
        workspace_root=workspace_root,
    )


def _get_dispatch_analyzers(
    selected_analyzer_keys: Collection[str] | None,
    get_enabled_analyzers_fn: Callable[[], list[Any]],
) -> tuple[Any, ...]:
    return analysis_dispatch_module.get_cli_dispatch_analyzers(
        selected_keys=selected_analyzer_keys,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
    )


def _build_context(project: Project, options: AnalysisOptions) -> AnalysisContext:
    is_library = project_application.target_is_library(
        project.config,
        project.base_picture,
        project.graph,
    )
    return build_analysis_context(
        project.base_picture,
        graph=project.graph,
        debug=options.debug,
        target_is_library=is_library,
        selected_issue_kinds=options.selected_issue_kinds,
        config=project.config,
        create_shared_artifacts=True,
    )


def analyze_project(
    project: Project,
    options: AnalysisOptions,
    *,
    get_enabled_analyzers_fn: Callable[[], list[Any]] | None = None,
) -> ProjectAnalysisResult:
    """Run the ``Project → SemanticSnapshot → Analyzer execution`` pipeline.

    The caller never builds a snapshot; the application layer owns it and
    returns it on the result for downstream querying.
    """
    snapshot = build_snapshot_from_loaded_project(
        project.base_picture,
        project.graph,
        entry_file=project.entry_file,
        workspace_root=project.workspace_root,
        collect_variable_diagnostics=options.collect_variable_diagnostics,
        debug=options.debug,
    )
    enabled_analyzers = (
        analyze_application.get_enabled_analyzers if get_enabled_analyzers_fn is None else get_enabled_analyzers_fn
    )
    analyzers = _get_dispatch_analyzers(options.selected_analyzer_keys, enabled_analyzers)
    context = _build_context(project, options)

    analyzer_reports: list[AnalyzerReport] = []
    for spec in analyzers:
        report = analysis_dispatch_module.run_registry_analyzer(spec, context)
        analyzer_reports.append(AnalyzerReport(analyzer_key=str(spec.key), report=report))

    return ProjectAnalysisResult(
        project=project,
        snapshot=snapshot,
        analyzer_reports=tuple(analyzer_reports),
        selected_analyzer_keys=tuple(str(spec.key) for spec in analyzers),
    )


__all__ = [
    "AnalysisOptions",
    "AnalyzerReport",
    "Project",
    "ProjectAnalysisResult",
    "analyze_project",
    "load_project_handle",
]
