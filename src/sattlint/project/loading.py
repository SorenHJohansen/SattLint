# pyright: reportPrivateUsage=false
from __future__ import annotations

import contextlib
from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
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
from ..core.debug import debug_enabled, log_load_failure
from ..core.memory import release_unused_memory
from ..core.progress import AnalysisProgressEvent, ProgressCallback, ProgressPhase
from ..core.syntax import CodeMode, normalize_code_mode
from ..graphics.graphics_context_helpers import resolve_graphics_companion_path
from ..models.project_graph import ProjectGraph, merge_project_basepicture
from ..utils.casefolding import unit_key
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
    load_parser_projects,
    read_dependency_names,
)
from .support import LoadFailureDetail, configured_icf_files, describe_load_failure

LoadedProject = tuple[str, BasePicture, ProjectGraph]


def iter_loaded_projects(
    cfg: ConfigDict,
    *,
    refresh_ast: bool,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]],
    emit_output_fn: Callable[..., None],
    failure_sink: Callable[[str, LoadFailureDetail], None] | None = None,
    progress_fn: ProgressCallback | None = None,
) -> Iterator[LoadedProject]:
    target_names = require_analyzed_targets_fn(cfg)
    target_total = len(target_names)
    for target_index, target_name in enumerate(target_names, start=1):
        if progress_fn is not None:
            progress_fn(
                AnalysisProgressEvent(
                    phase=ProgressPhase.LOADING,
                    target_total=target_total,
                    target_index=target_index,
                    target_name=target_name,
                )
            )
        try:
            project_bp, graph = load_project_fn(
                cfg,
                target_name=target_name,
                refresh_ast=refresh_ast,
                collect_stage_timings=_collect_analysis_timings(cfg),
            )
        except (OSError, RuntimeError, ValueError, ProjectLoadError) as exc:
            detail = describe_load_failure(target_name, exc)
            log_load_failure(
                f"Failed to load analysis target {target_name!r}",
                exc=exc,
                logger=log,
                debug=debug_enabled(cfg),
            )
            if failure_sink is not None:
                failure_sink(target_name, detail)
            emit_output_fn(f"\n=== Target: {target_name} ===")
            emit_output_fn("? Failed to load target:")
            emit_output_fn(detail.message)
            if progress_fn is not None:
                # A failed target still finishes: the status bar must move past
                # it instead of counting it as outstanding work forever.
                progress_fn(
                    AnalysisProgressEvent(
                        phase=ProgressPhase.TARGET_COMPLETE,
                        target_total=target_total,
                        target_index=target_index,
                        target_name=target_name,
                    )
                )
            continue
        _emit_debug_load_summary(cfg, target_name=target_name, graph=graph, emit_output_fn=emit_output_fn)
        yield target_name, project_bp, graph
        # The consumer drops its references before asking for the next target.
        # Clear this frame too, so loading the next target does not keep the
        # previous graph alive alongside it.
        del project_bp, graph
        release_unused_memory()


def source_paths_for_current_target(
    project_bp: BasePicture,
    graph: ProjectGraph,
    *,
    unit_equal_fn: Callable[[str, str], bool],
    unit_key_fn: Callable[[str], str],
) -> set[Path]:
    source_files: set[Path] = graph.source_files
    root_source_path = graph.root_source_path_for_basepicture(project_bp)
    if isinstance(root_source_path, Path):
        return {root_source_path}

    origin_file = getattr(project_bp, "origin_file", None)
    if origin_file:
        matches = {path for path in source_files if unit_equal_fn(path.name, origin_file)}
        # Several libraries can hold a file with that name; a single match
        # identifies the target, a crowd does not, so fall through instead.
        if len(matches) == 1:
            return matches

    target_name = unit_key_fn(
        getattr(project_bp, "program_name", None) or getattr(project_bp, "name", None) or project_bp.header.name
    )
    return {path for path in source_files if unit_key_fn(path.stem) == target_name}


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


def _configured_search_roots(cfg: ConfigDict) -> set[Path]:
    """Directories whose entry list decides which sources the loader can find."""
    roots: set[Path] = set()
    for key in ("program_dir", "ABB_lib_dir"):
        raw = str(cfg.get(key, "") or "").strip()
        if raw:
            roots.add(Path(raw).expanduser())
    other_dirs = cfg.get("other_lib_dirs")
    for raw_dir in other_dirs or ():
        text = str(raw_dir).strip()
        if text:
            roots.add(Path(text).expanduser())
    return roots


def cache_manifest_files(
    cfg: ConfigDict,
    graph: ProjectGraph,
    *,
    find_dependency_path_fn: Callable[[str], Path | None],
    resolve_graphics_companion_path_fn: Callable[..., Path | None],
    resolve_distribution_companion_path_fn: Callable[..., Path | None] = resolve_distribution_companion_path,
    include_icf_inputs: bool = True,
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

    # The search roots are a snapshot too: a newly added consumer file changes
    # neither the loaded source list nor a dependency sidecar, but it does
    # change the directory entry. Record the roots so a library report goes
    # stale when a new program starts using it.
    manifest_files.update(_configured_search_roots(cfg))

    # ICF inputs participate in analysis-input tracking so ICF analysis
    # results go stale when configured ICF files change. The directory itself
    # is part of the manifest too: the file list is a snapshot, so a newly
    # added ICF file would otherwise change neither the key nor the manifest.
    if not include_icf_inputs:
        return manifest_files
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
    extra_roots: Sequence[str] = (),
) -> ProjectGraph:
    graph = ProjectGraph()
    project = load_parser_project(binding, [target_name, *extra_roots], validate=validate)
    convert_project_into_graph(
        project,
        graph,
        binding=binding,
        root_name=target_name,
        strict=strict,
        lib_names=lib_names,
        extra_roots=extra_roots,
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
        # consumer fails the batch. Its shared pass keeps every consumer that
        # succeeds without re-parsing the union once per healthy consumer, and
        # each failure is recorded against its own consumer.
        results = load_parser_projects(binding, names)
        for name in names:
            result = results.get(name)
            if result is None:
                record_project_load_failure(graph, name, ProjectLoadError(name, "target was not loaded"))
                continue
            if result.project is None:
                # A cycle is a load failure of the consumer; the adapter already
                # keeps SattLint's wording for it.
                record_project_load_failure(
                    graph,
                    name,
                    result.error or ProjectLoadError(name, "target was not loaded"),
                )
                continue
            convert_project_into_graph(
                result.project,
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
    refresh_ast: bool = False,
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
    # ``refresh_ast`` rebuilds this target's parsed project graph instead of
    # trusting the cached one. Only this layer is bypassed: the parser's
    # per-file caches are verified against the source bytes, so re-parsing them
    # would be pure waste. The analysis report cache has its own switch.
    if not refresh_ast and cache is not None:
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
        # Always on. The parser verifies every entry against the source bytes it
        # was parsed from, so a hit is never stale and skipping it can only cost
        # a re-parse. A graph rebuild below still reuses these per-file parses.
        parser_cache_dir=cache_dir,
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
    refresh_ast: bool = False,
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
            refresh_ast=refresh_ast,
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
    # The parser's per-file cache verifies every entry against the source bytes,
    # so a program the ICF per-run pass loads again is parsed at most once.
    binding = build_parser_binding(
        cfg,
        status_update_fn=status_update_fn,
        parser_cache_dir=cache_module.get_cache_dir_or_none(),
    )

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


def _program_batch_cache_target(program_names: Sequence[str]) -> str:
    """A stable synthetic cache identity for a set of referenced programs.

    Real program names are identifiers, so the separator makes a collision with
    a project target impossible while still hashing the exact set that was
    parsed.
    """
    normalized = sorted(unit_key(name) for name in program_names)
    return "icf-program-batch::" + "|".join(normalized)


def load_program_asts(
    cfg: ConfigDict,
    program_names: Sequence[str],
    *,
    status_update_fn: Callable[[str], None] | None = None,
) -> tuple[dict[str, BasePicture], ProjectGraph]:
    """Load several referenced programs in one parser pass, reusing the AST cache.

    ICF files reference programs that are often not analysis targets. Loading
    them one at a time parsed their shared dependency closure once per program.
    A single parser call parses that closure once, and the batch result is
    cached against the exact program set so later runs skip the parse entirely.
    """
    names = list(dict.fromkeys(name for name in program_names if name))
    if not names:
        return {}, ProjectGraph()

    cache_dir = cache_module.get_cache_dir_or_none()
    cache = None if cache_dir is None else cache_module.build_ast_cache(cache_dir, cache_module.ASTCache)
    key = cache_module.compute_cache_key(cfg, analysis_target=_program_batch_cache_target(names))
    if cache is not None:
        cached = cache.load_validated(key)
        payload_map = cast(Mapping[str, object], cached) if isinstance(cached, Mapping) else None
        cached_project = payload_map.get("project") if payload_map is not None else None
        cached_project_tuple = cast(tuple[object, ...], cached_project) if isinstance(cached_project, tuple) else None
        if cached_project_tuple is not None and len(cached_project_tuple) == 2:
            cached_asts, cached_graph = cast(tuple[dict[str, BasePicture], ProjectGraph], cached_project_tuple)
            with contextlib.suppress(AttributeError):
                cached_graph.loaded_from_cache = True
            for attr in (
                "load_stage_timings",
                "load_stage_timings_by_program",
                "graphics_load_timings",
                "graphics_load_timings_by_program",
            ):
                with contextlib.suppress(AttributeError):
                    setattr(cached_graph, attr, {})
            _attach_analysis_cache_metadata(
                cached_graph,
                cache_key=key,
                manifest_files=cache.manifest_paths(key),
            )
            return dict(cached_asts), cached_graph

    binding = build_parser_binding(
        cfg,
        status_update_fn=status_update_fn,
        parser_cache_dir=cache_dir,
    )
    lib_names: dict[str, str] = {}
    graph = _load_parser_graph(
        binding,
        names[0],
        strict=False,
        lib_names=lib_names,
        validate=LoadValidation.NONE,
        extra_roots=tuple(names[1:]),
    )

    asts: dict[str, BasePicture] = {}
    by_identity: dict[str, str] = {}
    for indexed_name in graph.ast_by_name:
        by_identity.setdefault(unit_key(indexed_name), indexed_name)
    missing: list[str] = []
    for name in names:
        resolved_name = name if name in graph.ast_by_name else by_identity.get(unit_key(name), name)
        program_bp = graph.ast_by_name.get(resolved_name)
        if program_bp is None:
            missing.append(name)
            continue
        asts[name] = program_bp
    if missing:
        raise RuntimeError(f"Program(s) {', '.join(repr(name) for name in missing)} were not parsed.")

    manifest_files = cache_manifest_files(
        cfg,
        graph,
        find_dependency_path_fn=lambda name: find_dependency_path(binding, name),
        resolve_graphics_companion_path_fn=resolve_graphics_companion_path,
        include_icf_inputs=False,
    )
    if graph.unavailable_libraries or getattr(graph, "failures", None):
        # An incomplete batch must not be replayed after the missing dependency
        # appears; the caller still gets this load.

        return asts, graph
    _attach_analysis_cache_metadata(graph, cache_key=key, manifest_files=manifest_files)
    if cache is not None:
        try:
            cache.save(key, project=(asts, graph), files=manifest_files)
        except OSError as exc:
            log.debug("AST cache write failed for the program batch: %s", exc)
    return asts, graph


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
                refresh_ast=True,
                status_update_fn=emit_output_fn,
            )
            emit_output_fn("✔ AST cache updated")
        except (OSError, RuntimeError, ValueError, ProjectLoadError) as exc:
            log_load_failure(
                f"Failed to rebuild AST cache for {target_name!r}",
                exc=exc,
                logger=log,
                debug=debug_enabled(cfg),
            )
            emit_output_fn(f"❌ Failed to build AST cache for {target_name}: {exc}")
            ok = False

    return ok


def is_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False
