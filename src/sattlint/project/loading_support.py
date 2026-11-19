# pyright: reportUnusedFunction=false
from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any, cast

from lark.exceptions import VisitError

from sattlint.parser_api import BasePicture, ProjectLoadError

from ..config.types import ConfigDict
from ..core import profiling as profiling_module
from ..core.debug import debug_enabled
from ..core.syntax import CodeMode, deps_ext_candidates, normalize_code_mode
from ..models.project_graph import ProjectFailure, ProjectGraph
from ..validation.shared import ValidationWarning, coerce_validation_notice
from .support import FAILURE_MARKERS, LOAD_FAILURE_MARKER

_STAGE_ORDER = ("load_or_parse", "validate", "attach_graphics", "index")
log = logging.getLogger("SattLint")


def _format_named_timings(label: str, timings: Mapping[str, float]) -> str:
    parts = [f"{name}={duration:.4f}s" for name, duration in sorted(timings.items())]
    return f"{label}: " + ", ".join(parts)


def _format_refresh_stage_timings(stage_timings: dict[str, float], *, refresh_mode: str) -> str:
    labels = {
        "load_or_parse": "load_or_parse",
        "validate": "validate",
        "attach_graphics": "graphics",
        "index": "index",
    }
    parts: list[str] = []
    for stage_name in _STAGE_ORDER:
        duration = stage_timings.get(stage_name)
        if duration is None:
            if refresh_mode == "ast-only" and stage_name in {"attach_graphics", "index"}:
                parts.append(f"{labels[stage_name]}=skipped")
            continue
        parts.append(f"{labels[stage_name]}={duration:.4f}s")
    return "AST refresh stage totals: " + ", ".join(parts)


def _emit_debug_load_summary(
    cfg: ConfigDict,
    *,
    target_name: str,
    graph: ProjectGraph,
    emit_output_fn: Callable[..., None],
) -> None:
    if not debug_enabled(cfg):
        return

    emit_output_fn(
        f"DEBUG load summary for {target_name}: source_files={len(graph.source_files)}, "
        f"warnings={len(graph.warnings)}, "
        f"missing={len(graph.missing)}, "
        f"unavailable_libraries={len(graph.unavailable_libraries)}"
    )

    if graph.load_stage_timings:
        emit_output_fn(_format_refresh_stage_timings(dict(graph.load_stage_timings), refresh_mode="full"))

    if graph.graphics_load_timings:
        emit_output_fn(_format_named_timings("Graphics load phase totals", dict(graph.graphics_load_timings)))


def _attach_analysis_cache_metadata(graph: ProjectGraph, *, cache_key: str, manifest_files: Iterable[Path]) -> None:
    graph.analysis_cache_key = cache_key
    graph.analysis_manifest_files = frozenset(manifest_files)


def _workspace_dependency_suffixes(mode: CodeMode | str | None) -> tuple[str, ...]:
    """Dependency-sidecar extensions in preference order.

    Draft prefers ``.l`` and falls back to ``.z``; official uses ``.z``. The
    fallback matters because a program can exist only in one body family (an
    official ``.x``/``.z`` program inside a draft project), and skipping its
    dependency list would hide the uses it contributes.
    """
    resolved_mode = normalize_code_mode(mode) or CodeMode.OFFICIAL
    return deps_ext_candidates(resolved_mode)


def _collect_analysis_timings(cfg: ConfigDict) -> bool:
    return bool(cfg.get("debug", False)) or profiling_module.create_profiler().enabled


def _with_status_line(
    *,
    live_status_line_factory: Callable[[], Any],
    run_fn: Callable[[Callable[[str], None]], tuple[BasePicture, ProjectGraph]],
) -> tuple[BasePicture, ProjectGraph]:
    with live_status_line_factory() as status_update_fn:
        return run_fn(cast(Callable[[str], None], status_update_fn))


def _call_load_project_compat(
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]],
    cfg: ConfigDict,
    *,
    target_name: str,
    **kwargs: object,
) -> tuple[BasePicture, ProjectGraph]:
    try:
        signature = inspect.signature(load_project_fn)
    except (TypeError, ValueError):
        return load_project_fn(cfg, target_name=target_name, **kwargs)

    accepts_kwargs = any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values())
    if accepts_kwargs:
        return load_project_fn(cfg, target_name=target_name, **kwargs)

    supported_kwargs = {name: value for name, value in kwargs.items() if name in signature.parameters}
    return load_project_fn(cfg, target_name=target_name, **supported_kwargs)


def _iter_workspace_reverse_library_consumer_dependency_files(
    cfg: ConfigDict,
) -> Iterator[tuple[str, Path]]:
    base_dirs = [Path(cfg["program_dir"]), *(Path(path) for path in cfg["other_lib_dirs"])]
    suffixes = _workspace_dependency_suffixes(cfg.get("mode", "official"))

    # One sidecar per program: the most preferred suffix wins, and a program
    # whose preferred sidecar is absent still contributes through the fallback.
    chosen: dict[str, tuple[tuple[int, int], Path]] = {}
    for directory_rank, base_dir in enumerate(base_dirs):
        if not base_dir.exists() or not base_dir.is_dir():
            continue
        try:
            files = sorted(
                (path for path in base_dir.iterdir() if path.is_file()), key=lambda path: path.name.casefold()
            )
        except OSError:
            continue

        for deps_path in files:
            suffix = deps_path.suffix.casefold()
            if suffix not in suffixes:
                continue
            rank = (suffixes.index(suffix), directory_rank)
            target_key = deps_path.stem.casefold()
            current = chosen.get(target_key)
            if current is None or rank < current[0]:
                chosen[target_key] = (rank, deps_path)

    for _rank, deps_path in chosen.values():
        yield deps_path.stem, deps_path


def _include_reverse_library_consumers(
    cfg: ConfigDict,
    *,
    selected_target: str,
    root_bp: BasePicture,
    graph: ProjectGraph,
    find_dependency_path_fn: Callable[[str], Path | None],
    read_dependency_names_fn: Callable[[Path | None], list[str]],
    visit_targets_fn: Callable[[list[tuple[str, Path | None]]], None],
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
) -> None:
    # A dependant that references the selected target is a real use whether the
    # target is called a program or a library. The old program/library gate
    # depended on where the file lived (``program_dir``), so a library stored
    # beside its programs had no consumers loaded and its types looked unused.
    del root_bp
    selected_key = selected_target.casefold()
    queued_targets: set[tuple[str, str]] = set()
    pending_targets: list[tuple[str, Path | None]] = []

    def _queue_reverse_consumer(target_name: str, deps_path: Path | None) -> None:
        if deps_path is None or target_name.casefold() == selected_key:
            return

        queue_key = (target_name.casefold(), str(deps_path.parent).casefold())
        if queue_key in queued_targets:
            return
        queued_targets.add(queue_key)
        pending_targets.append((target_name, deps_path.parent))

    for candidate in require_analyzed_targets_fn(cfg):
        if candidate.casefold() == selected_key:
            continue

        deps_path = find_dependency_path_fn(candidate)
        candidate_dependencies = read_dependency_names_fn(deps_path)
        if not any(dep.casefold() == selected_key for dep in candidate_dependencies):
            continue

        _queue_reverse_consumer(candidate, deps_path)

    for candidate, deps_path in _iter_workspace_reverse_library_consumer_dependency_files(cfg):
        if candidate.casefold() == selected_key:
            continue

        candidate_dependencies = read_dependency_names_fn(deps_path)
        if not any(dep.casefold() == selected_key for dep in candidate_dependencies):
            continue

        _queue_reverse_consumer(candidate, deps_path)

    # Load and convert every reverse consumer in one batched parser load so
    # their shared dependency closure is parsed once instead of once per
    # consumer; each consumer is still validated as its own root target.
    if pending_targets:
        visit_targets_fn(pending_targets)


def record_project_failure(graph: ProjectGraph, name: str, exception: Exception) -> None:
    message = f"{name} parse/transform error: {exception}"
    line = getattr(exception, "line", None)
    column = getattr(exception, "column", None)
    length = getattr(exception, "length", None)
    if isinstance(exception, VisitError):
        line = line if line is not None else getattr(exception.orig_exc, "line", None)
        column = column if column is not None else getattr(exception.orig_exc, "column", None)
        length = length if length is not None else getattr(exception.orig_exc, "length", None)
    graph.missing.append(message)
    graph.failures[name.casefold()] = ProjectFailure(
        name=name,
        message=message,
        line=line,
        column=column,
        length=length,
    )


def record_project_warning(graph: ProjectGraph, name: str, message: ValidationWarning) -> None:
    notice = coerce_validation_notice(message)
    graph.warnings.append(f"{name}: {notice.message}")
    graph.warning_notices.append((name, notice))


def record_project_load_failure(graph: ProjectGraph, name: str, error: ProjectLoadError) -> None:
    """Record a target the parser could not load at all.

    The error already names the failing program, its message, and the
    dependency edge it was reached through, so the entry keeps that detail
    instead of relabelling it as a parse or transform failure. There is no
    source position to attach: the failure happened before a program AST
    existed.
    """
    message = f"{name}{LOAD_FAILURE_MARKER}{error}"
    graph.missing.append(message)
    graph.failures[name.casefold()] = ProjectFailure(name=name, message=message)


def format_debug_list(title: str, entries: Iterable[str]) -> str:
    items = [str(entry) for entry in entries]
    if not items:
        return f"{title}: none"

    lines = [f"{title} ({len(items)}):"]
    lines.extend(f"  - {item}" for item in items)
    return "\n".join(lines)


def format_debug_missing_entries(entries: Iterable[str]) -> str:
    items = [str(entry) for entry in entries]
    if not items:
        return "Missing/failed: none"

    lines = [f"Missing/failed ({len(items)}):"]
    for item in items:
        for marker in FAILURE_MARKERS:
            if marker in item:
                library_name, detail = item.split(marker, 1)
                lines.append(f"  - {library_name}")
                lines.append(f"    {marker.strip().rstrip(':')}: {detail}")
                break
        else:
            lines.append(f"  - {item}")
    return "\n".join(lines)
