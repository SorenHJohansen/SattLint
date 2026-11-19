# pyright: reportPrivateUsage=false
from __future__ import annotations

import contextlib
from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from sattlint.parser_api import (
    BasePicture,
    LoadMode,
    LoadValidation,
    ProjectLoadError,
    resolve_distribution_companion_path,
)

from .. import cache as cache_module
from ..config.types import ConfigDict
from ..core.debug import log_debug_exception
from ..core.syntax import CodeMode, normalize_code_mode
from ..graphics.graphics_context_helpers import resolve_graphics_companion_path
from ..models.project_graph import ProjectGraph, merge_project_basepicture
from .loader_config import build_parser_binding, validate_loader_config
from .loading_support import (
    _attach_analysis_cache_metadata,
    _collect_analysis_timings,
    _emit_debug_load_summary,
    _include_reverse_library_consumers,
    _with_status_line,
    log,
    record_project_load_failure,
)
from .parser_adapter import (
    CircularDependencyError,
    ParserProjectBinding,
    convert_project_into_graph,
    find_dependency_path,
    load_parser_project,
    read_dependency_names,
)
from .support import configured_icf_files

LoadedProject = tuple[str, BasePicture, ProjectGraph]


def iter_loaded_projects(
    cfg: ConfigDict,
    *,
    use_cache: bool,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]],
    emit_output_fn: Callable[..., None],
    failure_sink: Callable[[str, str], None] | None = None,
) -> Iterator[LoadedProject]:
    for target_name in require_analyzed_targets_fn(cfg):
        try:
            project_bp, graph = load_project_fn(
                cfg,
                target_name=target_name,
                use_cache=use_cache,
                collect_stage_timings=_collect_analysis_timings(cfg),
            )
        except (OSError, RuntimeError, ValueError, ProjectLoadError) as exc:
            log_debug_exception(f"Failed to load analysis target {target_name!r}", logger=log)
            if failure_sink is not None:
                failure_sink(target_name, str(exc))
            emit_output_fn(f"\n=== Target: {target_name} ===")
            emit_output_fn("? Failed to load target:")
            emit_output_fn(str(exc))
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
    source_files: set[Path] = graph.source_files
    root_source_path = graph.root_source_path_for_basepicture(project_bp)
    if isinstance(root_source_path, Path):
        return {root_source_path}

    origin_file = getattr(project_bp, "origin_file", None)
    if origin_file:
        matches = {path for path in source_files if casefold_equal_fn(path.name, origin_file)}
        # Several libraries can hold a file with that name; a single match
        # identifies the target, a crowd does not, so fall through instead.
        if len(matches) == 1:
            return matches

    target_name = casefold_key_fn(
        getattr(project_bp, "program_name", None) or getattr(project_bp, "name", None) or project_bp.header.name
    )
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
    find_dependency_path_fn: Callable[[str], Path | None],
    resolve_graphics_companion_path_fn: Callable[..., Path | None],
    resolve_distribution_companion_path_fn: Callable[..., Path | None] = resolve_distribution_companion_path,
) -> set[Path]:
    manifest_files: set[Path] = set(graph.source_files)
    # One resolved mode for both companion families: an absent mode takes the
    # configured default instead of a different default per resolver.
    mode = normalize_code_mode(cfg.get("mode")) or CodeMode.OFFICIAL
    parser_mode = LoadMode(mode.value)

    for source_path in tuple(manifest_files):
        companion_path = resolve_graphics_companion_path_fn(source_path, mode=mode)
        if companion_path is not None and companion_path != source_path:
            manifest_files.add(companion_path)

        # A distribution companion is a second artifact beside the same body.
        # Editing it changes what the parser sees, so it belongs in the
        # manifest even though SattLint never analyzes its contents.
        distribution_path = resolve_distribution_companion_path_fn(source_path, mode=parser_mode)
        if distribution_path is not None:
            manifest_files.add(distribution_path)

    for target_name in graph.ast_by_name:
        # The parser resolves a sidecar beside the selected body, so the lookup
        # needs no requester directory.
        deps_path = find_dependency_path_fn(target_name)
        if deps_path is not None:
            manifest_files.add(deps_path)

    # ICF inputs participate in analysis-input tracking so ICF analysis
    # results go stale when configured ICF files change. The directory itself
    # is part of the manifest too: the file list is a snapshot, so a newly
    # added ICF file would otherwise change neither the key nor the manifest.
    icf_dir, icf_files = configured_icf_files(cfg)
    manifest_files.update(icf_files)
    if icf_dir is not None:
        # A missing directory is recorded too: creating it later must
        # invalidate the entry, and a stat of a missing path fails validation.
        manifest_files.add(icf_dir)

    return manifest_files


def _load_parser_graph(
    binding: ParserProjectBinding,
    target_name: str,
    *,
    strict: bool,
    lib_names: dict[str, str],
    validate: LoadValidation = LoadValidation.INVOKED,
    index_program_view: bool = True,
) -> ProjectGraph:
    graph = ProjectGraph()
    project = load_parser_project(binding, [target_name], validate=validate)
    convert_project_into_graph(
        project,
        graph,
        binding=binding,
        root_name=target_name,
        strict=strict,
        lib_names=lib_names,
        index_program_view=index_program_view,
    )
    return graph


def _visit_targets_into_graph(
    binding: ParserProjectBinding,
    graph: ProjectGraph,
    targets: list[tuple[str, Path | None]],
    *,
    lib_names: dict[str, str],
) -> None:
    if not targets:
        return
    names = [name for name, _ in targets]
    # One batched parser load for every reverse-library consumer: the union
    # closure is parsed once instead of once per consumer, so shared dependency
    # programs (typically the selected library's own closure) are not re-parsed.
    try:
        project = load_parser_project(binding, names)
    except (ProjectLoadError, CircularDependencyError):
        # The parser returns a complete closure or raises, so one broken
        # consumer fails the batch. The selected target is already in the graph,
        # so retry per consumer and record the ones that cannot load.
        for name in names:
            try:
                single = load_parser_project(binding, [name])
            except (ProjectLoadError, CircularDependencyError) as exc:
                # A cycle is a load failure of the consumer; keep its parser
                # explanation but record it through the load-failure channel.
                load_error = exc if isinstance(exc, ProjectLoadError) else ProjectLoadError(name, str(exc))
                record_project_load_failure(graph, name, load_error)
                continue
            convert_project_into_graph(
                single,
                graph,
                binding=binding,
                root_name=name,
                strict=False,
                lib_names=lib_names,
            )
        return
    convert_project_into_graph(
        project,
        graph,
        binding=binding,
        root_name=names[0],
        strict=False,
        lib_names=lib_names,
        extra_roots=tuple(names[1:]),
    )


def load_project(  # noqa: PLR0915
    cfg: ConfigDict,
    target_name: str | None = None,
    *,
    use_cache: bool,
    refresh_mode: str = "full",
    collect_stage_timings: bool = False,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    cache_key_for_target_fn: Callable[[ConfigDict, str], str],
    target_load_error_factory: Callable[..., Exception] | None,
    get_cache_dir_fn: Callable[[], Path | None],
    ast_cache_cls: type[Any],
    status_update_fn: Callable[[str], None] | None = None,
) -> tuple[BasePicture, ProjectGraph]:
    validate_loader_config(cfg)
    targets = require_analyzed_targets_fn(cfg)
    selected_target = target_name or targets[0]
    ast_only = str(refresh_mode).strip().lower() == "ast-only"
    cache_dir = get_cache_dir_fn()
    cache = None if cache_dir is None else cache_module.build_ast_cache(cache_dir, ast_cache_cls)

    def build_project_view(root_bp: BasePicture, graph: ProjectGraph) -> BasePicture:
        if ast_only:
            return root_bp
        project_bp = merge_project_basepicture(root_bp, graph)
        root_origin = graph.root_origin_for_basepicture(project_bp)
        if root_origin is not None:
            origin_file = root_origin.origin_file
            origin_lib = root_origin.library_name
            if origin_file and origin_file != getattr(project_bp, "origin_file", None):
                project_bp = replace(project_bp, origin_file=origin_file, origin_lib=origin_lib)
        return project_bp

    key = cache_key_for_target_fn(cfg, selected_target)
    if use_cache and cache is not None:
        cached = cache.load_validated(key)
        payload_map = cast(Mapping[str, object], cached) if isinstance(cached, Mapping) else None
        cached_project = payload_map.get("project") if payload_map is not None else None
        cached_project_tuple = cast(tuple[object, ...], cached_project) if isinstance(cached_project, tuple) else None
        if cached_project_tuple is not None and len(cached_project_tuple) == 2:
            root_bp, graph = cast(tuple[BasePicture, ProjectGraph], cached_project_tuple)
            # The cached entry carries the timings of the load that produced it;
            # reporting them as this run's stages would be a fabricated number.
            # Test doubles may use slotted stubs without some of these diagnostic
            # fields, so each one is guarded on its own.
            with contextlib.suppress(AttributeError):
                graph.loaded_from_cache = True
            with contextlib.suppress(AttributeError):
                graph.load_stage_timings = {}
            with contextlib.suppress(AttributeError):
                graph.load_stage_timings_by_program = {}
            with contextlib.suppress(AttributeError):
                graph.graphics_load_timings = {}
            with contextlib.suppress(AttributeError):
                graph.graphics_load_timings_by_program = {}
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

    binding = build_parser_binding(
        cfg,
        status_update_fn=status_update_fn,
        stage_timing_sink=record_stage_timing if collect_stage_timings else None,
        graphics_timing_sink=record_graphics_timing if collect_stage_timings else None,
    )
    lib_names: dict[str, str] = {}
    graph = _load_parser_graph(
        binding,
        selected_target,
        strict=False,
        lib_names=lib_names,
        validate=LoadValidation.NONE if ast_only else LoadValidation.INVOKED,
        index_program_view=not ast_only,
    )
    root_bp = graph.ast_by_name.get(selected_target)
    deps_path = find_dependency_path(binding, selected_target)
    direct_dependencies = list(read_dependency_names(deps_path)) if deps_path is not None else []

    if not root_bp:
        if target_load_error_factory is None:
            raise RuntimeError(f"Target {selected_target!r} was not parsed.")
        error_kwargs: dict[str, object] = {
            "resolved": list(graph.ast_by_name.keys()),
            "missing": graph.missing,
            "warnings": graph.warnings,
            "direct_dependencies": direct_dependencies,
            "failures": graph.failures,
        }
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

    if ast_only:
        return root_bp, graph

    _include_reverse_library_consumers(
        cfg,
        selected_target=selected_target,
        root_bp=root_bp,
        graph=graph,
        find_dependency_path_fn=lambda name: find_dependency_path(binding, name),
        read_dependency_names_fn=lambda deps_path: (
            list(read_dependency_names(deps_path)) if deps_path is not None else []
        ),
        visit_targets_fn=lambda targets: _visit_targets_into_graph(binding, graph, targets, lib_names=lib_names),
        require_analyzed_targets_fn=require_analyzed_targets_fn,
    )

    project_bp = build_project_view(root_bp, graph)
    manifest_files = cache_manifest_files(
        cfg,
        graph,
        find_dependency_path_fn=lambda name: find_dependency_path(binding, name),
        resolve_graphics_companion_path_fn=resolve_graphics_companion_path,
    )
    if graph.unavailable_libraries or getattr(graph, "failures", None):
        # A dependency that is absent now can appear as a file later, and the
        # manifest cannot see a file that does not exist yet. Persisting this
        # graph would replay the unresolved or failed result after the cause is
        # fixed, so load again next run instead. The graph carries no
        # report-cache metadata either, so a caller cannot key a report cache
        # against it.
        return project_bp, graph
    _attach_analysis_cache_metadata(
        graph,
        cache_key=key,
        manifest_files=manifest_files,
    )
    if cache is not None:
        try:
            cache.save(
                key,
                project=(root_bp, graph),
                files=manifest_files,
            )
        except OSError as exc:
            log.debug("AST cache write failed for %s: %s", selected_target, exc)
    return project_bp, graph


def load_project_with_live_status(
    cfg: ConfigDict,
    target_name: str | None = None,
    *,
    use_cache: bool,
    refresh_mode: str,
    collect_stage_timings: bool,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    cache_key_for_target_fn: Callable[[ConfigDict, str], str],
    target_load_error_factory: Callable[..., Exception] | None,
    get_cache_dir_fn: Callable[[], Path | None],
    ast_cache_cls: type[Any],
    live_status_line_factory: Callable[[], Any],
) -> tuple[BasePicture, ProjectGraph]:
    return _with_status_line(
        live_status_line_factory=live_status_line_factory,
        run_fn=lambda status_update_fn: load_project(
            cfg,
            target_name=target_name,
            use_cache=use_cache,
            refresh_mode=refresh_mode,
            collect_stage_timings=collect_stage_timings,
            require_analyzed_targets_fn=require_analyzed_targets_fn,
            cache_key_for_target_fn=cache_key_for_target_fn,
            target_load_error_factory=target_load_error_factory,
            get_cache_dir_fn=get_cache_dir_fn,
            ast_cache_cls=ast_cache_cls,
            status_update_fn=status_update_fn,
        ),
    )


def load_program_ast(
    cfg: ConfigDict,
    program_name: str,
    *,
    status_update_fn: Callable[[str], None] | None = None,
) -> tuple[BasePicture, ProjectGraph]:
    binding = build_parser_binding(cfg, status_update_fn=status_update_fn)

    lib_names: dict[str, str] = {}
    graph = _load_parser_graph(
        binding,
        program_name,
        strict=False,
        lib_names=lib_names,
        validate=LoadValidation.NONE,
    )
    root_bp = graph.ast_by_name.get(program_name)
    if not root_bp:
        raise RuntimeError(f"Program '{program_name}' not parsed. Resolved: {list(graph.ast_by_name.keys())}")

    return root_bp, graph


def load_program_ast_with_live_status(
    cfg: ConfigDict,
    program_name: str,
    *,
    live_status_line_factory: Callable[[], Any],
) -> tuple[BasePicture, ProjectGraph]:
    return _with_status_line(
        live_status_line_factory=live_status_line_factory,
        run_fn=lambda status_update_fn: load_program_ast(
            cfg,
            program_name,
            status_update_fn=status_update_fn,
        ),
    )


def ensure_ast_cache(
    cfg: ConfigDict,
    *,
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    cache_key_for_target_fn: Callable[[ConfigDict, str], str],
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]],
    ast_cache_cls: type[Any],
    get_cache_dir_fn: Callable[[], Path | None],
    emit_output_fn: Callable[..., None],
) -> bool:
    targets = get_analyzed_targets_fn(cfg)
    if not targets:
        return True

    cache_dir = get_cache_dir_fn()
    cache = None if cache_dir is None else cache_module.build_ast_cache(cache_dir, ast_cache_cls)
    if cache is None:
        emit_output_fn("AST cache is unavailable; skipping the cache refresh.")
        return True
    ok = True
    total_targets = len(targets)
    emit_output_fn(f"Refreshing AST caches for {total_targets} target(s)...")
    for index, target_name in enumerate(targets, start=1):
        emit_output_fn(f"\nChecking AST cache for {target_name}... ({index}/{total_targets})")
        key = cache_key_for_target_fn(cfg, target_name)
        has_payload = cache.has_payload(key)
        has_manifest = cache.has_manifest(key)
        if has_payload:
            is_valid = has_manifest and cache.has_cache_artifact(key)
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
            load_project_fn(
                cfg,
                target_name=target_name,
                use_cache=False,
                status_update_fn=emit_output_fn,
            )
            emit_output_fn("✔ AST cache updated")
        except (OSError, RuntimeError, ValueError, ProjectLoadError) as exc:
            log_debug_exception(f"Failed to rebuild AST cache for {target_name!r}", logger=log)
            emit_output_fn(f"❌ Failed to build AST cache for {target_name}: {exc}")
            ok = False

    return ok


def is_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False
