# pyright: reportUnusedFunction=false
"""Project and target orchestration for the application layer.

Direct replacement for the old ``_app_facade_project`` helpers: these
functions bind the owning implementations (:mod:`sattlint.app_analysis`,
:mod:`sattlint.app_support`, :mod:`sattlint.cache`) to the application
defaults, so external callers get the same behaviour the interactive TUI
used to depend on (in particular ``TargetLoadError`` on load failures).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

from sattline_parser.models.ast_model import BasePicture

from .. import app_analysis as app_analysis_module
from .. import app_support
from .. import cache as cache_module
from .. import console as console_module
from ..app_base import pause
from ..config_types import ConfigDict
from ..models.project_graph import ProjectGraph

ASTCache = cache_module.ASTCache
TargetLoadError = app_support.TargetLoadError
LoadedProject = tuple[str, BasePicture, ProjectGraph]


def get_analyzed_targets(cfg: ConfigDict) -> list[str]:
    return app_support.get_analyzed_targets(cfg)


def require_analyzed_targets(cfg: ConfigDict) -> list[str]:
    return app_support.require_analyzed_targets(cfg)


def has_analyzed_targets(cfg: ConfigDict) -> bool:
    return app_support.has_analyzed_targets(cfg, get_analyzed_targets_fn=get_analyzed_targets)


def require_targets_for_menu_action(cfg: ConfigDict, action: str) -> bool:
    return app_support.require_targets_for_menu_action(
        cfg,
        action,
        has_analyzed_targets_fn=has_analyzed_targets,
        print_fn=print,
        pause_fn=pause,
    )


def cache_key_for_target(cfg: ConfigDict, target_name: str) -> str:
    return app_support.cache_key_for_target(
        cfg,
        target_name,
        compute_cache_key_fn=cache_module.compute_cache_key,
    )


def split_csv_values(raw: str) -> list[str]:
    return app_support.split_csv_values(raw)


def configured_icf_files(cfg: ConfigDict) -> tuple[Path | None, list[Path]]:
    return app_support.configured_icf_files(cfg)


def source_paths_for_current_target(project_bp: BasePicture, graph: ProjectGraph) -> set[Path]:
    return app_analysis_module.source_paths_for_current_target(project_bp, graph)


def target_is_library(cfg: ConfigDict, project_bp: BasePicture, graph: ProjectGraph) -> bool:
    return app_analysis_module.target_is_library(cfg, project_bp, graph)


def load_project(
    cfg: ConfigDict,
    target_name: str | None = None,
    *,
    use_cache: bool = True,
    use_file_ast_cache: bool = True,
    refresh_mode: str = "full",
    collect_stage_timings: bool = False,
    status_update_fn: Callable[[str], None] | None = None,
) -> tuple[BasePicture, ProjectGraph]:
    return app_analysis_module.load_project(
        cfg,
        target_name=target_name,
        use_cache=use_cache,
        use_file_ast_cache=use_file_ast_cache,
        refresh_mode=refresh_mode,
        collect_stage_timings=collect_stage_timings,
        require_analyzed_targets_fn=require_analyzed_targets,
        cache_key_for_target_fn=cache_key_for_target,
        target_load_error_factory=TargetLoadError,
        get_cache_dir_fn=cache_module.get_cache_dir,
        status_update_fn=status_update_fn,
    )


def load_program_ast(
    cfg: ConfigDict,
    program_name: str,
    *,
    force_dependency_resolution: bool = False,
) -> tuple[BasePicture, ProjectGraph]:
    return app_analysis_module.load_program_ast(
        cfg,
        program_name,
        force_dependency_resolution=force_dependency_resolution,
    )


def iter_loaded_projects(
    cfg: ConfigDict,
    *,
    use_cache: bool = True,
) -> Iterator[LoadedProject]:
    return app_analysis_module.iter_loaded_projects(
        cfg,
        use_cache=use_cache,
        require_analyzed_targets_fn=require_analyzed_targets,
        load_project_fn=load_project,
    )


def force_refresh_ast(cfg: ConfigDict) -> tuple[BasePicture, ProjectGraph] | None:
    return app_analysis_module.force_refresh_ast(
        cfg,
        get_analyzed_targets_fn=get_analyzed_targets,
        cache_key_for_target_fn=cache_key_for_target,
        load_project_fn=load_project,
        ast_cache_cls=ASTCache,
        get_cache_dir_fn=cache_module.get_cache_dir,
    )


def ensure_ast_cache(cfg: ConfigDict, *, emit_output_fn: Callable[..., None] | None = None) -> bool:
    return app_analysis_module.ensure_ast_cache(
        cfg,
        get_analyzed_targets_fn=get_analyzed_targets,
        cache_key_for_target_fn=cache_key_for_target,
        load_project_fn=load_project,
        ast_cache_cls=ASTCache,
        get_cache_dir_fn=cache_module.get_cache_dir,
        emit_output_fn=console_module.print_output if emit_output_fn is None else emit_output_fn,
    )


def refresh_analysis_caches(cfg: ConfigDict) -> tuple[BasePicture, ProjectGraph] | None:
    return app_analysis_module.refresh_analysis_caches(
        cfg,
        force_refresh_ast_fn=force_refresh_ast,
        get_cache_dir_fn=cache_module.get_cache_dir,
        get_cache_manager_fn=cache_module.get_cache_manager,
        emit_output_fn=console_module.print_output,
    )
