from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from .casefolding import casefold_equal, casefold_key
from .models.project_graph import ProjectGraph

ConfigDict = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]


def _workspace_dependency_suffixes(mode: str) -> tuple[str, ...]:
    return (".l", ".z") if casefold_equal(mode, "draft") else (".z",)


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
            project_bp, graph = load_project_fn(
                cfg,
                target_name=target_name,
                use_cache=use_cache,
            )
        except Exception as exc:
            emit_output_fn(f"\n=== Target: {target_name} ===")
            emit_output_fn("? Failed to load target:")
            emit_output_fn(exc)
            continue
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


def load_project(
    cfg: ConfigDict,
    target_name: str | None = None,
    *,
    use_cache: bool,
    use_file_ast_cache: bool,
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

    key = cache_key_for_target_fn(cfg, selected_target)
    cached = cache.load(key) if use_cache else None

    if cached and cast(bool, cache.validate(cached, fast=False)):
        return cast(tuple[BasePicture, ProjectGraph], cached["project"])

    loader = engine_module.SattLineProjectLoader(
        program_dir=Path(cfg["program_dir"]),
        other_lib_dirs=[Path(path) for path in cfg["other_lib_dirs"]],
        abb_lib_dir=Path(cfg["ABB_lib_dir"]),
        mode=engine_module.CodeMode(cfg["mode"]),
        scan_root_only=cfg["scan_root_only"],
        debug=cfg["debug"],
        use_file_ast_cache=use_file_ast_cache,
        status_update_fn=status_update_fn,
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

    _include_reverse_library_consumers(
        cfg,
        selected_target=selected_target,
        root_bp=root_bp,
        graph=graph,
        loader=loader,
        require_analyzed_targets_fn=require_analyzed_targets_fn,
        engine_module=engine_module,
    )

    project_bp = engine_module.merge_project_basepicture(root_bp, graph)
    cache.save(
        key,
        project=(project_bp, graph),
        files=set(graph.source_files),
    )
    return project_bp, graph


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
    result = None
    total_targets = len(targets)
    emit_output_fn(f"Refreshing AST caches for {total_targets} target(s)...")
    for index, target_name in enumerate(targets, start=1):
        emit_output_fn(f"\nRefreshing AST cache for {target_name}... ({index}/{total_targets})")
        cache.clear(cache_key_for_target_fn(cfg, target_name))
        result = load_project_fn(
            cfg,
            target_name=target_name,
            use_cache=False,
            use_file_ast_cache=False,
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
        cached = cache.load(cache_key_for_target_fn(cfg, target_name))
        if cached:
            has_manifest = bool(cached.get("files"))
            if fast and has_manifest:
                is_valid = cast(bool, cache.validate(cached, fast=True))
            else:
                is_valid = cast(bool, cache.validate(cached, fast=fast))
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
            emit_output_fn(f"❌ Failed to build AST cache for {target_name}: {exc}")
            ok = False

    return ok
