"""Analysis report metadata enrichment.

Helpers that decorate an analyzer report with source-derived metadata —
target name normalization, source path selection, draft/official version
labelling, and last-changed date.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from .variables_report import VariablesReport


def _origin_file_name(value: object) -> str | None:
    if isinstance(value, Path):
        return value.name
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


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
    preferred_suffixes: frozenset[str] | None = None,
) -> Path | None:
    try:
        source_paths = source_paths_for_current_target_fn(project_bp, graph)
    except AttributeError:
        return None

    if not source_paths:
        return None

    root_source_path_for_basepicture = getattr(graph, "root_source_path_for_basepicture", None)
    if callable(root_source_path_for_basepicture):
        root_source_path = root_source_path_for_basepicture(project_bp)
        if isinstance(root_source_path, Path) and root_source_path in source_paths:
            return root_source_path

    origin_file_name = _origin_file_name(getattr(project_bp, "origin_file", None))
    candidates = [path for path in source_paths if origin_file_name and casefold_equal_fn(path.name, origin_file_name)]
    if not candidates:
        candidates = list(source_paths)

    def _candidate_key(path: Path) -> tuple[int, float, str]:
        suffix = path.suffix.casefold()
        matches_mode = 1 if preferred_suffixes and suffix in preferred_suffixes else 0
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = float("-inf")
        return (matches_mode, mtime, str(path))

    return max(candidates, key=_candidate_key)


def source_version_label(
    project_bp: Any,
    graph: Any,
    source_path: Path | None,
    *,
    draft_source_suffixes: frozenset[str],
    official_source_suffixes: frozenset[str],
) -> str | None:
    if source_path is not None:
        suffix = source_path.suffix.casefold()
    else:
        root_origin_file_for_basepicture = getattr(graph, "root_origin_file_for_basepicture", None)
        origin_file = (
            root_origin_file_for_basepicture(project_bp)
            if callable(root_origin_file_for_basepicture)
            else getattr(project_bp, "origin_file", None)
        )
        origin_file_name = _origin_file_name(origin_file)
        suffix = Path(origin_file_name).suffix.casefold() if origin_file_name else ""

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
    source_version_label_fn: Callable[[Any, Any, Path | None], str | None],
    source_last_changed_fn: Callable[[Path | None], str | None],
) -> VariablesReport:
    source_path = select_report_source_path_fn(project_bp, graph)
    report.analyzed_version = source_version_label_fn(project_bp, graph, source_path)
    report.last_changed = source_last_changed_fn(source_path)
    return report
