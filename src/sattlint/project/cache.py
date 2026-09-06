"""Analysis report cache orchestration.

Builds and drives the :class:`AnalysisReportCache` used to memoize analyzer
reports against a project's AST cache manifest. These helpers are
orchestration over the ``cache`` subsystem, so they accept injected callables
and stay independent of CLI/output concerns.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

from .. import cache as cache_module
from ..analyzers.variables import IssueKind
from ..cache import AnalysisReportCache
from ..config.types import ConfigDict
from ..models.project_graph import ProjectGraph

log = logging.getLogger("SattLint")


def create_analysis_report_cache(
    cfg: ConfigDict,
    *,
    use_cache: bool,
    debug_enabled_fn: Callable[[ConfigDict], bool],
    analysis_report_cache_cls: type[AnalysisReportCache],
    get_cache_dir_fn: Callable[[], Path],
) -> AnalysisReportCache | None:
    if not use_cache:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Analysis report cache disabled by configuration")
        return None
    if debug_enabled_fn(cfg):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Analysis report cache disabled in debug mode")
        return None
    return cast(
        AnalysisReportCache,
        cache_module.build_analysis_report_cache(get_cache_dir_fn(), analysis_report_cache_cls),
    )


def graph_analysis_cache_metadata(graph: ProjectGraph) -> tuple[str, frozenset[Path]] | None:
    cache_key = getattr(graph, "analysis_cache_key", None)
    if not isinstance(cache_key, str) or not cache_key:
        return None

    manifest_files_obj = getattr(graph, "analysis_manifest_files", None)
    if not isinstance(manifest_files_obj, (set, frozenset)):
        return None

    manifest_entries = cast(set[object] | frozenset[object], manifest_files_obj)
    manifest_files = frozenset(path for path in manifest_entries if isinstance(path, Path))
    if len(manifest_files) != len(manifest_entries) or not manifest_files:
        return None

    return cache_key, manifest_files


def run_with_analysis_report_cache(
    graph: ProjectGraph,
    *,
    report_cache: AnalysisReportCache | None,
    analyzer_cache_key: str,
    run_fn: Callable[[], Any],
    compute_analysis_report_cache_key_fn: Callable[[str, str], str],
) -> Any:
    metadata = graph_analysis_cache_metadata(graph)
    if report_cache is None or metadata is None:
        if report_cache is not None and metadata is None and log.isEnabledFor(logging.DEBUG):
            log.debug("Analysis report cache bypassed: graph missing cache metadata for %s", analyzer_cache_key)
        return run_fn()

    project_cache_key, manifest_files = metadata
    cache_key = compute_analysis_report_cache_key_fn(project_cache_key, analyzer_cache_key)
    cached = report_cache.load(cache_key)
    if cached and report_cache.validate(cached, fast=False):
        cached_map = cast(Mapping[str, object], cached) if isinstance(cached, Mapping) else None
        if cached_map is not None and "report" in cached_map:
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Analysis report cache hit: %s", analyzer_cache_key)
            report: Any = cached_map["report"]
            return report

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Analysis report cache miss: %s", analyzer_cache_key)

    report = run_fn()
    report_cache.save(cache_key, report=report, files=manifest_files)
    return report


def variable_issue_kinds_cache_key(kinds: set[IssueKind]) -> str:
    return ",".join(sorted(kind.name.casefold() for kind in kinds))


def unavailable_libraries(graph: ProjectGraph) -> set[str]:
    return cast(set[str], getattr(graph, "unavailable_libraries", set[str]()))
