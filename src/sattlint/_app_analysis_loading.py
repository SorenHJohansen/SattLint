# pyright: reportPrivateUsage=false
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import app_telemetry as telemetry_module
from . import cache as cache_module
from ._app_analysis_loading_support import (
    _attach_analysis_cache_metadata,
    _call_load_project_compat,
    _collect_analysis_timings,
    _emit_debug_load_summary,
    _format_refresh_stage_timings,
    _include_reverse_library_consumers,
    _loader_find_dependency_path,
    _loader_flush_lookup_cache,
    _loader_read_dependency_names,
    _with_status_line,
    log,
)
from ._app_debug import log_debug_exception
from .casefolding import casefold_equal, casefold_key
from .config_types import ConfigDict
from .models.project_graph import ProjectGraph, RootOrigin

LoadedProject = tuple[str, BasePicture, ProjectGraph]


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
) -> Iterator[LoadedProject]:
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


def source_paths_for_current_target(
    project_bp: BasePicture,
    graph: ProjectGraph,
    *,
    casefold_equal_fn: Callable[[str, str], bool],
    casefold_key_fn: Callable[[str], str],
) -> set[Path]:
    source_files: set[Path] = getattr(graph, "source_files", set())
    root_source_path_for_basepicture = getattr(graph, "root_source_path_for_basepicture", None)
    if callable(root_source_path_for_basepicture):
        root_source_path = root_source_path_for_basepicture(project_bp)
        if isinstance(root_source_path, Path):
            return {root_source_path}

    origin_file = getattr(project_bp, "origin_file", None)
    if origin_file:
        matches = {path for path in source_files if casefold_equal_fn(path.name, origin_file)}
        if matches:
            return matches

    target_name = casefold_key_fn(project_bp.header.name)
    return {path for path in source_files if casefold_key_fn(path.stem) == target_name}


def target_is_library(
    cfg: ConfigDict,
    project_bp: BasePicture,
    graph: ProjectGraph,
    *,
    source_paths_for_current_target_fn: Callable[[BasePicture, ProjectGraph], set[Path]],
    is_within_directory_fn: Callable[[Path, Path], bool],
) -> bool:
    program_dir = cfg.get("program_dir")
    if not program_dir:
        return False

    source_paths = source_paths_for_current_target_fn(project_bp, graph)
    if not source_paths:
        return False

    program_path = Path(program_dir)
    return all(not is_within_directory_fn(path, program_path) for path in source_paths)


def cache_manifest_files(
    cfg: ConfigDict,
    graph: ProjectGraph,
    *,
    find_dependency_path_fn: Callable[[str, Path | None], Path | None],
    resolve_graphics_companion_path_fn: Callable[..., Path | None],
    casefold_equal_fn: Callable[[str, str], bool],
    casefold_key_fn: Callable[[str], str],
) -> set[Path]:
    manifest_files: set[Path] = set(getattr(graph, "source_files", set()))

    for source_path in tuple(manifest_files):
        companion_path = resolve_graphics_companion_path_fn(source_path, mode=cfg.get("mode"))
        if companion_path is not None and companion_path != source_path:
            manifest_files.add(companion_path)

    ast_by_name = cast(dict[str, BasePicture], getattr(graph, "ast_by_name", {}))
    for target_name, project_bp in ast_by_name.items():
        source_paths = source_paths_for_current_target(
            project_bp,
            graph,
            casefold_equal_fn=casefold_equal_fn,
            casefold_key_fn=casefold_key_fn,
        )
        requester_dirs = {path.parent for path in source_paths}
        if not requester_dirs:
            root_source_path_for_basepicture = getattr(graph, "root_source_path_for_basepicture", None)
            if callable(root_source_path_for_basepicture):
                root_source_path = root_source_path_for_basepicture(project_bp)
                if isinstance(root_source_path, Path):
                    requester_dirs = {root_source_path.parent}

        if not requester_dirs:
            origin_file = getattr(project_bp, "origin_file", None)
            if isinstance(origin_file, str) and origin_file.strip():
                requester_dirs = {Path(cfg["program_dir"])}

        for requester_dir in requester_dirs or {None}:
            deps_path = find_dependency_path_fn(target_name, requester_dir)
            if deps_path is not None:
                manifest_files.add(deps_path)

    return manifest_files


def load_project(  # noqa: PLR0915
    cfg: ConfigDict,
    target_name: str | None = None,
    *,
    use_cache: bool,
    use_file_ast_cache: bool,
    refresh_mode: str = "full",
    collect_stage_timings: bool = False,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    cache_key_for_target_fn: Callable[[ConfigDict, str], str],
    target_load_error_factory: Callable[..., Exception] | None,
    get_cache_dir_fn: Callable[[], Path],
    ast_cache_cls: type[Any],
    engine_module: Any,
    status_update_fn: Callable[[str], None] | None = None,
) -> tuple[BasePicture, ProjectGraph]:
    engine_module.validate_loader_config(cfg)
    targets = require_analyzed_targets_fn(cfg)
    selected_target = target_name or targets[0]
    cache_dir = get_cache_dir_fn()
    cache = cache_module.build_ast_cache(cache_dir, ast_cache_cls)

    def build_project_view(root_bp: BasePicture, graph: ProjectGraph) -> BasePicture:
        if refresh_mode == "ast-only":
            return root_bp
        project_bp = cast(BasePicture, engine_module.merge_project_basepicture(root_bp, graph))
        root_origin_for_basepicture = getattr(graph, "root_origin_for_basepicture", None)
        if callable(root_origin_for_basepicture):
            root_origin = cast(RootOrigin | None, root_origin_for_basepicture(project_bp))
            if root_origin is not None:
                origin_file = root_origin.origin_file
                origin_lib = root_origin.library_name
                if origin_file and origin_file != getattr(project_bp, "origin_file", None):
                    project_bp = replace(project_bp, origin_file=origin_file, origin_lib=origin_lib)
        return project_bp

    key = cache_key_for_target_fn(cfg, selected_target)
    if use_cache:
        cached = cache.load_validated(key)
        payload_map = cast(Mapping[str, object], cached) if isinstance(cached, Mapping) else None
        cached_project = payload_map.get("project") if payload_map is not None else None
        cached_project_tuple = cast(tuple[object, ...], cached_project) if isinstance(cached_project, tuple) else None
        if cached_project_tuple is not None and len(cached_project_tuple) == 2:
            root_bp, graph = cast(tuple[BasePicture, ProjectGraph], cached_project_tuple)
            _attach_analysis_cache_metadata(
                graph,
                cache_key=key,
                manifest_files=cache.manifest_paths(key),
            )
            return build_project_view(root_bp, graph), graph

    stage_timings: dict[str, float] = {}
    stage_timings_by_program: dict[str, dict[str, float]] = defaultdict(dict)
    graphics_timings: dict[str, float] = {}
    graphics_timings_by_program: dict[str, dict[str, float]] = defaultdict(dict)

    def record_stage_timing(owner_name: str, stage_name: str, duration: float) -> None:
        stage_timings[stage_name] = stage_timings.get(stage_name, 0.0) + duration
        owner_timings = stage_timings_by_program.setdefault(owner_name, {})
        owner_timings[stage_name] = owner_timings.get(stage_name, 0.0) + duration

    def record_graphics_timing(owner_name: str, phase_name: str, duration: float) -> None:
        graphics_timings[phase_name] = graphics_timings.get(phase_name, 0.0) + duration
        owner_timings = graphics_timings_by_program.setdefault(owner_name, {})
        owner_timings[phase_name] = owner_timings.get(phase_name, 0.0) + duration

    loader, root_bp, graph = engine_module.load_project_graph(
        cfg,
        selected_target,
        use_file_ast_cache=use_file_ast_cache,
        status_update_fn=status_update_fn,
        refresh_mode=refresh_mode,
        stage_timing_sink=record_stage_timing if collect_stage_timings else None,
        graphics_timing_sink=record_graphics_timing if collect_stage_timings else None,
    )
    try:
        deps_path = _loader_find_dependency_path(loader, selected_target, Path(cfg["program_dir"]))
        direct_dependencies = _loader_read_dependency_names(loader, deps_path)
    finally:
        _loader_flush_lookup_cache(loader)

    if not root_bp:
        if target_load_error_factory is None:
            raise RuntimeError(f"Target {selected_target!r} was not parsed.")
        error_kwargs: dict[str, object] = {
            "resolved": list(graph.ast_by_name.keys()),
            "missing": graph.missing,
            "warnings": graph.warnings,
            "direct_dependencies": direct_dependencies,
        }
        if hasattr(graph, "failures"):
            error_kwargs["failures"] = graph.failures
        raise target_load_error_factory(selected_target, **error_kwargs)

    if collect_stage_timings:
        graph.load_stage_timings = dict(stage_timings)
        graph.load_stage_timings_by_program = {
            name: dict(program_timings) for name, program_timings in stage_timings_by_program.items()
        }
        graph.graphics_load_timings = dict(graphics_timings)
        graph.graphics_load_timings_by_program = {
            name: dict(program_timings) for name, program_timings in graphics_timings_by_program.items()
        }

    if refresh_mode == "ast-only":
        return root_bp, graph

    _include_reverse_library_consumers(
        cfg,
        selected_target=selected_target,
        root_bp=root_bp,
        graph=graph,
        loader=loader,
        require_analyzed_targets_fn=require_analyzed_targets_fn,
        engine_module=engine_module,
        target_is_library_fn=target_is_library,
        source_paths_for_current_target_fn=lambda project_bp, current_graph: source_paths_for_current_target(
            project_bp,
            current_graph,
            casefold_equal_fn=casefold_equal,
            casefold_key_fn=casefold_key,
        ),
    )

    project_bp = build_project_view(root_bp, graph)
    manifest_files = cache_manifest_files(
        cfg,
        graph,
        find_dependency_path_fn=lambda name, requester_dir: _loader_find_dependency_path(loader, name, requester_dir),
        resolve_graphics_companion_path_fn=engine_module.resolve_graphics_companion_path,
        casefold_equal_fn=casefold_equal,
        casefold_key_fn=casefold_key,
    )
    _attach_analysis_cache_metadata(
        graph,
        cache_key=key,
        manifest_files=manifest_files,
    )
    cache.save(
        key,
        project=(root_bp, graph),
        files=manifest_files,
    )
    return project_bp, graph


def load_project_with_live_status(
    cfg: ConfigDict,
    target_name: str | None = None,
    *,
    use_cache: bool,
    use_file_ast_cache: bool,
    refresh_mode: str,
    collect_stage_timings: bool,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    cache_key_for_target_fn: Callable[[ConfigDict, str], str],
    target_load_error_factory: Callable[..., Exception] | None,
    get_cache_dir_fn: Callable[[], Path],
    ast_cache_cls: type[Any],
    engine_module: Any,
    live_status_line_factory: Callable[[], Any],
) -> tuple[BasePicture, ProjectGraph]:
    return _with_status_line(
        live_status_line_factory=live_status_line_factory,
        run_fn=lambda status_update_fn: load_project(
            cfg,
            target_name=target_name,
            use_cache=use_cache,
            use_file_ast_cache=use_file_ast_cache,
            refresh_mode=refresh_mode,
            collect_stage_timings=collect_stage_timings,
            require_analyzed_targets_fn=require_analyzed_targets_fn,
            cache_key_for_target_fn=cache_key_for_target_fn,
            target_load_error_factory=target_load_error_factory,
            get_cache_dir_fn=get_cache_dir_fn,
            ast_cache_cls=ast_cache_cls,
            engine_module=engine_module,
            status_update_fn=status_update_fn,
        ),
    )


def load_program_ast(
    cfg: ConfigDict,
    program_name: str,
    *,
    force_dependency_resolution: bool,
    engine_module: Any,
    status_update_fn: Callable[[str], None] | None = None,
) -> tuple[BasePicture, ProjectGraph]:
    loader = engine_module.build_project_loader(
        cfg,
        status_update_fn=status_update_fn,
    )

    graph = loader.resolve(program_name, strict=False)
    root_bp = graph.ast_by_name.get(program_name)
    if not root_bp:
        raise RuntimeError(f"Program '{program_name}' not parsed. Resolved: {list(graph.ast_by_name.keys())}")

    return root_bp, graph


def load_program_ast_with_live_status(
    cfg: ConfigDict,
    program_name: str,
    *,
    force_dependency_resolution: bool,
    engine_module: Any,
    live_status_line_factory: Callable[[], Any],
) -> tuple[BasePicture, ProjectGraph]:
    return _with_status_line(
        live_status_line_factory=live_status_line_factory,
        run_fn=lambda status_update_fn: load_program_ast(
            cfg,
            program_name,
            force_dependency_resolution=force_dependency_resolution,
            engine_module=engine_module,
            status_update_fn=status_update_fn,
        ),
    )


def force_refresh_ast(
    cfg: ConfigDict,
    *,
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    cache_key_for_target_fn: Callable[[ConfigDict, str], str],
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]],
    ast_cache_cls: type[Any],
    get_cache_dir_fn: Callable[[], Path],
    emit_output_fn: Callable[..., None],
) -> tuple[BasePicture, ProjectGraph] | None:
    targets = get_analyzed_targets_fn(cfg)
    if not targets:
        return None

    cache = cache_module.build_ast_cache(get_cache_dir_fn(), ast_cache_cls)
    telemetry = telemetry_module.create_app_telemetry(cfg)
    result = None
    total_targets = len(targets)
    collect_stage_timings = bool(cfg.get("debug", False)) or telemetry.enabled
    emit_output_fn(f"Refreshing AST caches for {total_targets} target(s)...")
    for index, target_name in enumerate(targets, start=1):
        emit_output_fn(f"\nRefreshing AST cache for {target_name}... ({index}/{total_targets})")
        cache.clear(cache_key_for_target_fn(cfg, target_name))
        started_at = perf_counter()
        result = _call_load_project_compat(
            load_project_fn,
            cfg,
            target_name=target_name,
            use_cache=False,
            use_file_ast_cache=False,
            refresh_mode="ast-only",
            collect_stage_timings=collect_stage_timings,
        )
        duration_ms = (perf_counter() - started_at) * 1000
        if collect_stage_timings:
            _bp, graph = result
            stage_timings = getattr(graph, "load_stage_timings", None)
            if isinstance(stage_timings, dict):
                stage_timings_s = dict(cast(dict[str, float], stage_timings))
                stage_timings_ms = telemetry_module.normalize_named_timings_ms(stage_timings_s, scale=1000.0)
                stage_bottleneck = telemetry_module.bottleneck_from_named_timings(stage_timings_ms, kind="stage")
                graphics_timings_ms = telemetry_module.normalize_named_timings_ms(
                    getattr(graph, "graphics_load_timings", None),
                    scale=1000.0,
                )
                graphics_bottleneck = telemetry_module.bottleneck_from_named_timings(
                    graphics_timings_ms,
                    kind="graphics-phase",
                )
                emit_output_fn(
                    _format_refresh_stage_timings(
                        stage_timings_s,
                        refresh_mode="ast-only",
                    )
                )
                payload: dict[str, object] = {
                    "refresh_mode": "ast-only",
                    "stage_timings_s": stage_timings_s,
                }
                if stage_timings_ms:
                    payload["stage_timings_ms"] = stage_timings_ms
                if stage_bottleneck is not None:
                    payload["stage_bottleneck"] = stage_bottleneck
                    payload["bottleneck_kind"] = "stage"
                    payload["bottleneck"] = stage_bottleneck
                if graphics_timings_ms:
                    payload["graphics_timings_ms"] = graphics_timings_ms
                if graphics_bottleneck is not None:
                    payload["graphics_bottleneck"] = graphics_bottleneck
                    current_bottleneck = cast(dict[str, object] | None, payload.get("bottleneck"))
                    if current_bottleneck is None or cast(float, graphics_bottleneck["duration_ms"]) > cast(
                        float,
                        current_bottleneck["duration_ms"],
                    ):
                        payload["bottleneck_kind"] = "graphics-phase"
                        payload["bottleneck"] = graphics_bottleneck
                telemetry.emit(
                    operation="ast-refresh",
                    target_name=target_name,
                    duration_ms=duration_ms,
                    success=True,
                    payload=payload,
                )
            else:
                telemetry.emit(
                    operation="ast-refresh",
                    target_name=target_name,
                    duration_ms=duration_ms,
                    success=True,
                    payload={"refresh_mode": "ast-only"},
                )
        else:
            telemetry.emit(
                operation="ast-refresh",
                target_name=target_name,
                duration_ms=duration_ms,
                success=True,
                payload={"refresh_mode": "ast-only"},
            )
        emit_output_fn("OK AST cache refreshed")
    return result


def ensure_ast_cache(
    cfg: ConfigDict,
    *,
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    cache_key_for_target_fn: Callable[[ConfigDict, str], str],
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]],
    ast_cache_cls: type[Any],
    get_cache_dir_fn: Callable[[], Path],
    emit_output_fn: Callable[..., None],
) -> bool:
    targets = get_analyzed_targets_fn(cfg)
    if not targets:
        return True

    cache = cache_module.build_ast_cache(get_cache_dir_fn(), ast_cache_cls)
    ok = True
    total_targets = len(targets)
    emit_output_fn(f"Refreshing AST caches for {total_targets} target(s)...")
    for index, target_name in enumerate(targets, start=1):
        emit_output_fn(f"\nChecking AST cache for {target_name}... ({index}/{total_targets})")
        key = cache_key_for_target_fn(cfg, target_name)
        has_payload = cast(bool, cache.has_payload(key))
        has_manifest = cast(bool, cache.has_manifest(key))
        if has_payload:
            is_valid = has_manifest and cast(bool, cache.has_cache_artifact(key))
            if is_valid:
                emit_output_fn("✔ AST cache OK")
                continue

            if has_manifest:
                emit_output_fn("⚠ AST cache stale; rebuilding (this may take a while)...")
            else:
                emit_output_fn("⚠ AST cache missing file manifest; rebuilding (this may take a while)...")
        else:
            emit_output_fn("⚠ AST cache missing; building (this may take a while)...")

        try:
            _call_load_project_compat(
                load_project_fn,
                cfg,
                target_name=target_name,
                use_cache=False,
                status_update_fn=emit_output_fn,
            )
            emit_output_fn("✔ AST cache updated")
        except (OSError, RuntimeError, ValueError) as exc:
            log_debug_exception(cfg, f"Failed to rebuild AST cache for {target_name!r}", logger=log)
            emit_output_fn(f"❌ Failed to build AST cache for {target_name}: {exc}")
            ok = False

    return ok
