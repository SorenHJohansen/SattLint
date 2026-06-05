from __future__ import annotations

import inspect
import logging
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import app_telemetry as telemetry_module
from ._app_debug import debug_enabled, log_debug_exception
from .casefolding import casefold_equal, casefold_key
from .models.project_graph import ProjectGraph

ConfigDict = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]
_STAGE_ORDER = ("load_or_parse", "validate", "attach_graphics", "index", "ast_cache_save")
log = logging.getLogger("SattLint")


def _safe_count(value: object) -> int:
    try:
        return len(cast(Any, value))
    except TypeError:
        return 0


def _format_named_timings(label: str, timings: Mapping[str, float]) -> str:
    parts = [f"{name}={duration:.4f}s" for name, duration in sorted(timings.items())]
    return f"{label}: " + ", ".join(parts)


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
) -> None:
    if not target_is_library(
        cfg,
        root_bp,
        graph,
        source_paths_for_current_target_fn=lambda project_bp, current_graph: source_paths_for_current_target(
            project_bp,
            current_graph,
            casefold_equal_fn=casefold_equal,
            casefold_key_fn=casefold_key,
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
        loader._visit(target_name, graph, False, requester_dir=deps_path.parent, syntax_check=False)

    for candidate in require_analyzed_targets_fn(cfg):
        if candidate.casefold() == selected_key:
            continue

        deps_path = loader._find_deps_with_context(candidate, requester_dir=requester_dir)
        candidate_dependencies = cast(list[str], loader._read_deps(deps_path) if deps_path else [])
        if not any(dep.casefold() == selected_key for dep in candidate_dependencies):
            continue

        _queue_reverse_consumer(candidate, deps_path)

    for candidate, deps_path in _iter_workspace_reverse_library_consumer_dependency_files(cfg):
        if candidate.casefold() == selected_key:
            continue

        candidate_dependencies = cast(list[str], loader._read_deps(deps_path))
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
    compute_cache_key_fn: Callable[[ConfigDict], str],
) -> str:
    cache_cfg = cfg.copy()
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
        except Exception as exc:
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
            origin_file = getattr(project_bp, "origin_file", None)
            if isinstance(origin_file, str) and origin_file.strip():
                requester_dirs = {Path(cfg["program_dir"])}

        for requester_dir in requester_dirs or {None}:
            deps_path = find_dependency_path_fn(target_name, requester_dir)
            if deps_path is not None:
                manifest_files.add(deps_path)

    return manifest_files


def load_project(
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
    targets = require_analyzed_targets_fn(cfg)
    selected_target = target_name or targets[0]
    cache_dir = get_cache_dir_fn()
    cache = ast_cache_cls(cache_dir)

    def build_project_view(root_bp: BasePicture, graph: ProjectGraph) -> BasePicture:
        if refresh_mode == "ast-only":
            return root_bp
        return cast(BasePicture, engine_module.merge_project_basepicture(root_bp, graph))

    key = cache_key_for_target_fn(cfg, selected_target)
    if use_cache and cast(bool, cache.validate(key, fast=False)):
        cached = cache.load(key)
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

    loader = engine_module.SattLineProjectLoader(
        program_dir=Path(cfg["program_dir"]),
        other_lib_dirs=[Path(path) for path in cfg["other_lib_dirs"]],
        abb_lib_dir=Path(cfg["ABB_lib_dir"]),
        mode=engine_module.CodeMode(cfg["mode"]),
        scan_root_only=cfg["scan_root_only"],
        debug=cfg["debug"],
        use_file_ast_cache=use_file_ast_cache,
        status_update_fn=status_update_fn,
        refresh_mode=refresh_mode,
        stage_timing_sink=record_stage_timing if collect_stage_timings else None,
        graphics_timing_sink=record_graphics_timing if collect_stage_timings else None,
    )

    graph = loader.resolve(selected_target, strict=False)
    try:
        deps_path = loader._find_deps_with_context(
            selected_target,
            requester_dir=Path(cfg["program_dir"]),
        )
        direct_dependencies = cast(list[str], loader._read_deps(deps_path) if deps_path else [])
    finally:
        flush_lookup_cache = getattr(loader, "_flush_lookup_cache", None)
        if callable(flush_lookup_cache):
            flush_lookup_cache()

    root_bp = graph.ast_by_name.get(selected_target)
    if not root_bp:
        if target_load_error_factory is None:
            raise RuntimeError(f"Target {selected_target!r} was not parsed.")
        raise target_load_error_factory(
            selected_target,
            resolved=list(graph.ast_by_name.keys()),
            missing=graph.missing,
            warnings=graph.warnings,
            direct_dependencies=direct_dependencies,
        )

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
    )

    project_bp = build_project_view(root_bp, graph)
    manifest_files = cache_manifest_files(
        cfg,
        graph,
        find_dependency_path_fn=lambda name, requester_dir: loader._find_deps_with_context(
            name,
            requester_dir=requester_dir,
        ),
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
    loader = engine_module.SattLineProjectLoader(
        program_dir=Path(cfg["program_dir"]),
        other_lib_dirs=[Path(path) for path in cfg["other_lib_dirs"]],
        abb_lib_dir=Path(cfg["ABB_lib_dir"]),
        mode=engine_module.CodeMode(cfg["mode"]),
        scan_root_only=False if force_dependency_resolution else cfg["scan_root_only"],
        debug=cfg["debug"],
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

    cache = ast_cache_cls(get_cache_dir_fn())
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

    cache = ast_cache_cls(get_cache_dir_fn())
    fast = cfg.get("fast_cache_validation", False)
    ok = True
    total_targets = len(targets)
    emit_output_fn(f"Refreshing AST caches for {total_targets} target(s)...")
    for index, target_name in enumerate(targets, start=1):
        emit_output_fn(f"\nChecking AST cache for {target_name}... ({index}/{total_targets})")
        key = cache_key_for_target_fn(cfg, target_name)
        has_payload = cast(bool, cache.has_payload(key))
        has_manifest = cast(bool, cache.has_manifest(key))
        if has_payload:
            is_valid = cast(bool, cache.validate(key, fast=fast))
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
            load_project_fn(cfg, target_name=target_name, use_cache=False)
            emit_output_fn("✔ AST cache updated")
        except Exception as exc:
            log_debug_exception(cfg, f"Failed to rebuild AST cache for {target_name!r}", logger=log)
            emit_output_fn(f"❌ Failed to build AST cache for {target_name}: {exc}")
            ok = False

    return ok
