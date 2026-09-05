# pyright: reportUnusedFunction=false
"""Project and target orchestration for the application layer.

Direct replacement for the old flat ``app_analysis`` + ``_app_facade_project``
helpers: these functions bind the owning implementations (:mod:`sattlint.project.loading`,
:mod:`sattlint.project.support`, :mod:`sattlint.cache`,
:mod:`sattlint.console`) to the application defaults, so external callers get the
same behaviour the interactive TUI used to depend on (in particular
``TargetLoadError`` on load failures).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from sattline_parser.models.ast_model import BasePicture

from .. import cache as cache_module
from .. import console as console_module
from ..config.types import ConfigDict
from ..models.project_graph import ProjectGraph
from ..project import loading as analysis_loading_module
from ..project import support as support_module
from ..project.loading import is_within_directory
from ..utils.casefolding import casefold_equal, casefold_key

ASTCache = cache_module.ASTCache
AnalysisReportCache = cache_module.AnalysisReportCache
get_cache_dir: Callable[[], Path] = cache_module.get_cache_dir
LoadedProject = tuple[str, BasePicture, ProjectGraph]


def _get_analyzed_targets(cfg: ConfigDict) -> list[str]:
    return support_module.get_analyzed_targets(cfg)


def _require_analyzed_targets(cfg: ConfigDict) -> list[str]:
    return support_module.require_analyzed_targets(cfg)


def _cache_key_for_target(cfg: ConfigDict, target_name: str) -> str:
    return support_module.cache_key_for_target(
        cfg,
        target_name,
        compute_cache_key_fn=cache_module.compute_cache_key,
    )


def cache_key_for_target(cfg: ConfigDict, target_name: str) -> str:
    return _cache_key_for_target(cfg, target_name)


def _target_validation_warnings(target_name: str, warnings: list[str]) -> list[str]:
    return support_module.target_validation_warnings(target_name, warnings)


target_validation_warnings = _target_validation_warnings


def _print_validation_warnings(warnings: list[str], *, limit: int = 12) -> None:
    support_module.print_validation_warnings(warnings, print_fn=emit_output, limit=limit)


print_validation_warnings = _print_validation_warnings


def _source_paths_for_current_target(project_bp: BasePicture, graph: ProjectGraph) -> set[Path]:
    return analysis_loading_module.source_paths_for_current_target(
        project_bp,
        graph,
        casefold_equal_fn=casefold_equal,
        casefold_key_fn=casefold_key,
    )


def source_paths_for_current_target(project_bp: BasePicture, graph: ProjectGraph) -> set[Path]:
    return _source_paths_for_current_target(project_bp, graph)


def _target_is_library(cfg: ConfigDict, project_bp: BasePicture, graph: ProjectGraph) -> bool:
    return analysis_loading_module.target_is_library(
        cfg,
        project_bp,
        graph,
        source_paths_for_current_target_fn=_source_paths_for_current_target,
        is_within_directory_fn=is_within_directory,
    )


def target_is_library(cfg: ConfigDict, project_bp: BasePicture, graph: ProjectGraph) -> bool:
    return _target_is_library(cfg, project_bp, graph)


def _iter_loaded_projects(
    cfg: ConfigDict,
    *,
    use_cache: bool = True,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _require_analyzed_targets,
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]] | None = None,
) -> Iterator[LoadedProject]:
    return analysis_loading_module.iter_loaded_projects(
        cfg,
        use_cache=use_cache,
        require_analyzed_targets_fn=require_analyzed_targets_fn,
        load_project_fn=load_project if load_project_fn is None else load_project_fn,
        emit_output_fn=emit_output,
    )


def iter_loaded_projects(
    cfg: ConfigDict,
    *,
    use_cache: bool = True,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _require_analyzed_targets,
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]] | None = None,
) -> Iterator[LoadedProject]:
    return _iter_loaded_projects(
        cfg,
        use_cache=use_cache,
        require_analyzed_targets_fn=require_analyzed_targets_fn,
        load_project_fn=load_project_fn,
    )


def load_project(
    cfg: ConfigDict,
    target_name: str | None = None,
    *,
    use_cache: bool = True,
    use_file_ast_cache: bool = True,
    refresh_mode: str = "full",
    collect_stage_timings: bool = False,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _require_analyzed_targets,
    cache_key_for_target_fn: Callable[[ConfigDict, str], str] = _cache_key_for_target,
    target_load_error_factory: Callable[..., Exception] | None = support_module.TargetLoadError,
    get_cache_dir_fn: Callable[[], Path] = get_cache_dir,
    status_update_fn: Callable[[str], None] | None = None,
) -> tuple[BasePicture, ProjectGraph]:
    if status_update_fn is not None:
        return analysis_loading_module.load_project(
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
            ast_cache_cls=ASTCache,
            status_update_fn=status_update_fn,
        )
    return analysis_loading_module.load_project_with_live_status(
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
        ast_cache_cls=ASTCache,
        live_status_line_factory=console_module.live_status_line,
    )


def load_program_ast(
    cfg: ConfigDict,
    program_name: str,
) -> tuple[BasePicture, ProjectGraph]:
    return analysis_loading_module.load_program_ast_with_live_status(
        cfg,
        program_name,
        live_status_line_factory=console_module.live_status_line,
    )


def force_refresh_ast(
    cfg: ConfigDict,
    *,
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _get_analyzed_targets,
    cache_key_for_target_fn: Callable[[ConfigDict, str], str] = _cache_key_for_target,
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]] = load_project,
    ast_cache_cls: type[ASTCache] = ASTCache,
    get_cache_dir_fn: Callable[[], Path] = get_cache_dir,
) -> tuple[BasePicture, ProjectGraph] | None:
    return analysis_loading_module.force_refresh_ast(
        cfg,
        get_analyzed_targets_fn=get_analyzed_targets_fn,
        cache_key_for_target_fn=cache_key_for_target_fn,
        load_project_fn=load_project_fn,
        ast_cache_cls=ast_cache_cls,
        get_cache_dir_fn=get_cache_dir_fn,
        emit_output_fn=emit_output,
    )


def ensure_ast_cache(
    cfg: ConfigDict,
    *,
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _get_analyzed_targets,
    cache_key_for_target_fn: Callable[[ConfigDict, str], str] = _cache_key_for_target,
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]] = load_project,
    ast_cache_cls: type[ASTCache] = ASTCache,
    get_cache_dir_fn: Callable[[], Path] = get_cache_dir,
    emit_output_fn: Callable[..., None] | None = None,
) -> bool:
    resolved_emit_output_fn = emit_output if emit_output_fn is None else emit_output_fn
    return analysis_loading_module.ensure_ast_cache(
        cfg,
        get_analyzed_targets_fn=get_analyzed_targets_fn,
        cache_key_for_target_fn=cache_key_for_target_fn,
        load_project_fn=load_project_fn,
        ast_cache_cls=ast_cache_cls,
        get_cache_dir_fn=get_cache_dir_fn,
        emit_output_fn=resolved_emit_output_fn,
    )


def refresh_analysis_caches(
    cfg: ConfigDict,
    *,
    force_refresh_ast_fn: Callable[[ConfigDict], tuple[BasePicture, ProjectGraph] | None] = force_refresh_ast,
    get_cache_dir_fn: Callable[[], Path] = get_cache_dir,
    get_cache_manager_fn: Callable[..., Any] = cache_module.get_cache_manager,
    emit_output_fn: Callable[..., None] | None = None,
) -> tuple[BasePicture, ProjectGraph] | None:
    resolved_emit_output_fn = emit_output if emit_output_fn is None else emit_output_fn
    cache_manager = get_cache_manager_fn(get_cache_dir_fn())
    cleared = cache_manager.clear_all()
    removed_entries = cleared.removed_entries
    if removed_entries == 0:
        resolved_emit_output_fn("All caches already empty.")
    else:
        entry_label = "entry" if removed_entries == 1 else "entries"
        resolved_emit_output_fn(f"Cleared all caches ({removed_entries} {entry_label}).")
    return force_refresh_ast_fn(cfg)


emit_output: Callable[..., None] = console_module.print_output  # type: ignore[assignment]
