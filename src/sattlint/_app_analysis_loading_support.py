from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Iterable, Iterator, Mapping, Sized
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import app_telemetry as telemetry_module
from ._app_debug import debug_enabled, log_debug_exception
from .casefolding import casefold_equal
from .config_types import ConfigDict
from .models.project_graph import ProjectGraph

_STAGE_ORDER = ("load_or_parse", "validate", "attach_graphics", "index", "ast_cache_save")
log = logging.getLogger("SattLint")


def _safe_count(value: object) -> int:
    if isinstance(value, Sized):
        return len(value)
    return 0


def _format_named_timings(label: str, timings: Mapping[str, float]) -> str:
    parts = [f"{name}={duration:.4f}s" for name, duration in sorted(timings.items())]
    return f"{label}: " + ", ".join(parts)


def _format_refresh_stage_timings(stage_timings: dict[str, float], *, refresh_mode: str) -> str:
    labels = {
        "load_or_parse": "load_or_parse",
        "validate": "validate",
        "attach_graphics": "graphics",
        "index": "index",
        "ast_cache_save": "ast_cache_save",
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
        f"DEBUG load summary for {target_name}: source_files={_safe_count(getattr(graph, 'source_files', None))}, "
        f"warnings={_safe_count(getattr(graph, 'warnings', None))}, "
        f"missing={_safe_count(getattr(graph, 'missing', None))}, "
        f"unavailable_libraries={_safe_count(getattr(graph, 'unavailable_libraries', None))}"
    )

    stage_timings = getattr(graph, "load_stage_timings", None)
    if isinstance(stage_timings, Mapping) and stage_timings:
        emit_output_fn(
            _format_refresh_stage_timings(dict(cast(Mapping[str, float], stage_timings)), refresh_mode="full")
        )

    graphics_timings = getattr(graph, "graphics_load_timings", None)
    if isinstance(graphics_timings, Mapping) and graphics_timings:
        emit_output_fn(_format_named_timings("Graphics load phase totals", cast(Mapping[str, float], graphics_timings)))


def _attach_analysis_cache_metadata(graph: ProjectGraph, *, cache_key: str, manifest_files: Iterable[Path]) -> None:
    graph.analysis_cache_key = cache_key
    graph.analysis_manifest_files = frozenset(manifest_files)


def _loader_find_dependency_path(loader: Any, target_name: str, requester_dir: Path | None) -> Path | None:
    public_finder = getattr(loader, "find_dependency_path", None)
    if callable(public_finder):
        return cast(Path | None, public_finder(target_name, requester_dir=requester_dir))
    private_finder = getattr(loader, "_find_deps_with_context", None)
    if callable(private_finder):
        return cast(Path | None, private_finder(target_name, requester_dir=requester_dir))
    return None


def _loader_read_dependency_names(loader: Any, deps_path: Path | None) -> list[str]:
    if deps_path is None:
        return []
    public_reader = getattr(loader, "read_dependency_names", None)
    if callable(public_reader):
        return cast(list[str], public_reader(deps_path))
    private_reader = getattr(loader, "_read_deps", None)
    if callable(private_reader):
        return cast(list[str], private_reader(deps_path))
    return []


def _loader_flush_lookup_cache(loader: Any) -> None:
    public_flush = getattr(loader, "flush_lookup_cache", None)
    if callable(public_flush):
        public_flush()
        return
    private_flush = getattr(loader, "_flush_lookup_cache", None)
    if callable(private_flush):
        private_flush()


def _loader_visit_target(
    loader: Any,
    target_name: str,
    graph: ProjectGraph,
    syntax_only: bool,
    *,
    requester_dir: Path | None,
    syntax_check: bool,
) -> None:
    public_visit = getattr(loader, "visit_target", None)
    if callable(public_visit):
        public_visit(
            target_name,
            graph,
            syntax_only,
            requester_dir=requester_dir,
            syntax_check=syntax_check,
        )
        return
    private_visit = getattr(loader, "_visit", None)
    if callable(private_visit):
        private_visit(
            target_name,
            graph,
            syntax_only,
            requester_dir=requester_dir,
            syntax_check=syntax_check,
        )
        return
    raise AttributeError("loader does not provide visit_target or _visit")


def _workspace_dependency_suffixes(mode: str) -> tuple[str, ...]:
    return (".l", ".z") if casefold_equal(mode, "draft") else (".z",)


def _collect_analysis_timings(cfg: ConfigDict) -> bool:
    return bool(cfg.get("debug", False)) or telemetry_module.create_app_telemetry(cfg).enabled


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
    seen_targets: set[str] = set()
    base_dirs = [Path(cfg["program_dir"]), *(Path(path) for path in cfg["other_lib_dirs"])]
    suffixes = _workspace_dependency_suffixes(str(cfg.get("mode", "draft")))

    for base_dir in base_dirs:
        if not base_dir.exists() or not base_dir.is_dir():
            continue
        try:
            files = sorted(
                (path for path in base_dir.iterdir() if path.is_file()), key=lambda path: path.name.casefold()
            )
        except OSError:
            continue

        for suffix in suffixes:
            for deps_path in files:
                if deps_path.suffix.casefold() != suffix:
                    continue
                target_name = deps_path.stem
                target_key = target_name.casefold()
                if target_key in seen_targets:
                    continue
                seen_targets.add(target_key)
                yield target_name, deps_path


def _include_reverse_library_consumers(
    cfg: ConfigDict,
    *,
    selected_target: str,
    root_bp: BasePicture,
    graph: ProjectGraph,
    loader: Any,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    engine_module: Any,
    target_is_library_fn: Callable[..., bool],
    source_paths_for_current_target_fn: Callable[[BasePicture, ProjectGraph], set[Path]],
) -> None:
    if not target_is_library_fn(
        cfg,
        root_bp,
        graph,
        source_paths_for_current_target_fn=lambda project_bp, current_graph: source_paths_for_current_target_fn(
            project_bp,
            current_graph,
        ),
        is_within_directory_fn=engine_module.is_within_directory,
    ):
        return

    selected_key = selected_target.casefold()
    requester_dir = Path(cfg["program_dir"])
    queued_targets: set[tuple[str, str]] = set()

    def _queue_reverse_consumer(target_name: str, deps_path: Path | None) -> None:
        if deps_path is None or target_name.casefold() == selected_key:
            return

        queue_key = (target_name.casefold(), str(deps_path.parent).casefold())
        if queue_key in queued_targets:
            return
        queued_targets.add(queue_key)
        _loader_visit_target(
            loader,
            target_name,
            graph,
            False,
            requester_dir=deps_path.parent,
            syntax_check=False,
        )

    for candidate in require_analyzed_targets_fn(cfg):
        if candidate.casefold() == selected_key:
            continue

        deps_path = _loader_find_dependency_path(loader, candidate, requester_dir)
        candidate_dependencies = _loader_read_dependency_names(loader, deps_path)
        if not any(dep.casefold() == selected_key for dep in candidate_dependencies):
            continue

        _queue_reverse_consumer(candidate, deps_path)

    for candidate, deps_path in _iter_workspace_reverse_library_consumer_dependency_files(cfg):
        if candidate.casefold() == selected_key:
            continue

        candidate_dependencies = _loader_read_dependency_names(loader, deps_path)
        if not any(dep.casefold() == selected_key for dep in candidate_dependencies):
            continue

        _queue_reverse_consumer(candidate, deps_path)


def get_analyzed_targets(cfg: ConfigDict, *, app_support: Any) -> list[str]:
    return cast(list[str], app_support.get_analyzed_targets(cfg))


def require_analyzed_targets(cfg: ConfigDict, *, app_support: Any) -> list[str]:
    return cast(list[str], app_support.require_analyzed_targets(cfg))


def cache_key_for_target(
    cfg: ConfigDict,
    target_name: str,
    *,
    compute_cache_key_fn: Callable[[Mapping[str, object]], str],
) -> str:
    cache_cfg: dict[str, object] = dict(cfg)
    cache_cfg["analysis_target"] = target_name
    return compute_cache_key_fn(cache_cfg)


def iter_loaded_projects(
    cfg: ConfigDict,
    *,
    use_cache: bool,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]],
    emit_output_fn: Callable[..., None],
) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
    for target_name in require_analyzed_targets_fn(cfg):
        try:
            project_bp, graph = _call_load_project_compat(
                load_project_fn,
                cfg,
                target_name=target_name,
                use_cache=use_cache,
                collect_stage_timings=_collect_analysis_timings(cfg),
            )
        except (OSError, RuntimeError, ValueError) as exc:
            log_debug_exception(cfg, f"Failed to load analysis target {target_name!r}", logger=log)
            emit_output_fn(f"\n=== Target: {target_name} ===")
            emit_output_fn("? Failed to load target:")
            emit_output_fn(exc)
            continue
        _emit_debug_load_summary(cfg, target_name=target_name, graph=graph, emit_output_fn=emit_output_fn)
        yield target_name, project_bp, graph
