from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from .analyzers.variables import IssueKind
from .cache import AnalysisReportCache
from .models.project_graph import ProjectGraph
from .reporting.variables_report import VariablesReport

ConfigDict = dict[str, Any]
log = logging.getLogger("SattLint")


def normalize_report_target_name(report: Any, target_name: str) -> Any:
    if not target_name:
        return report

    for attr_name in ("basepicture_name", "name"):
        if not hasattr(report, attr_name):
            continue
        try:
            setattr(report, attr_name, target_name)
        except AttributeError:
            continue
    return report


def select_report_source_path(
    project_bp: Any,
    graph: Any,
    *,
    source_paths_for_current_target_fn: Callable[[Any, Any], set[Path]],
    casefold_equal_fn: Callable[[str, str], bool],
) -> Path | None:
    try:
        source_paths = source_paths_for_current_target_fn(project_bp, graph)
    except Exception:
        return None

    if not source_paths:
        return None

    origin_file = getattr(project_bp, "origin_file", None)
    candidates = [path for path in source_paths if origin_file and casefold_equal_fn(path.name, origin_file)]
    if not candidates:
        candidates = list(source_paths)

    def _candidate_key(path: Path) -> tuple[float, str]:
        try:
            return (path.stat().st_mtime, str(path))
        except OSError:
            return (float("-inf"), str(path))

    return max(candidates, key=_candidate_key)


def source_version_label(
    project_bp: Any,
    source_path: Path | None,
    *,
    draft_source_suffixes: frozenset[str],
    official_source_suffixes: frozenset[str],
) -> str | None:
    if source_path is not None:
        suffix = source_path.suffix.casefold()
    else:
        origin_file = getattr(project_bp, "origin_file", None)
        suffix = Path(origin_file).suffix.casefold() if origin_file else ""

    if suffix in draft_source_suffixes:
        return "draft"
    if suffix in official_source_suffixes:
        return "official"
    return None


def source_last_changed(source_path: Path | None) -> str | None:
    if source_path is None:
        return None

    try:
        return datetime.fromtimestamp(source_path.stat().st_mtime).strftime("%Y-%m-%d")
    except OSError:
        return None


def attach_variable_report_metadata(
    report: VariablesReport,
    project_bp: Any,
    graph: Any,
    *,
    select_report_source_path_fn: Callable[[Any, Any], Path | None],
    source_version_label_fn: Callable[[Any, Path | None], str | None],
    source_last_changed_fn: Callable[[Path | None], str | None],
) -> VariablesReport:
    source_path = select_report_source_path_fn(project_bp, graph)
    report.analyzed_version = source_version_label_fn(project_bp, source_path)
    report.last_changed = source_last_changed_fn(source_path)
    return report


def create_analysis_report_cache(
    cfg: ConfigDict,
    *,
    use_cache_enabled_fn: Callable[[ConfigDict], bool],
    debug_enabled_fn: Callable[[ConfigDict], bool],
    analysis_report_cache_cls: type[AnalysisReportCache],
    get_cache_dir_fn: Callable[[], Path],
) -> AnalysisReportCache | None:
    if not use_cache_enabled_fn(cfg):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Analysis report cache disabled by configuration")
        return None
    if debug_enabled_fn(cfg):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Analysis report cache disabled in debug mode")
        return None
    return analysis_report_cache_cls(get_cache_dir_fn())


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
            return cast(Any, cached_map["report"])

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Analysis report cache miss: %s", analyzer_cache_key)

    report = run_fn()
    report_cache.save(cache_key, report=report, files=manifest_files)
    return report


def variable_issue_kinds_cache_key(kinds: set[IssueKind]) -> str:
    return ",".join(sorted(kind.name.casefold() for kind in kinds))


def unavailable_libraries(graph: ProjectGraph) -> set[str]:
    return cast(set[str], getattr(graph, "unavailable_libraries", set[str]()))
