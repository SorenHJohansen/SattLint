from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from .models.project_graph import ProjectGraph


def _app() -> Any:
    from . import app as app_module

    return app_module


def _summarize_targets(cfg: dict[str, object]) -> str:
    app = _app()
    return app.app_startup_module.summarize_targets_from_app(cfg, app_module=app)


def show_help(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_startup_module.show_help_from_app(cfg, app_module=app)


def get_help_text(cfg: dict[str, object]) -> str:
    app = _app()
    return app.app_startup_module.get_help_text_from_app(cfg, app_module=app)


def _get_analyzed_targets(cfg: dict[str, object]) -> list[str]:
    app = _app()
    return cast(list[str], app.app_support.get_analyzed_targets(cfg))


def _require_analyzed_targets(cfg: dict[str, object]) -> list[str]:
    app = _app()
    return cast(list[str], app.app_support.require_analyzed_targets(cfg))


def _has_analyzed_targets(cfg: dict[str, object]) -> bool:
    app = _app()
    return cast(bool, app.app_support.has_analyzed_targets(cfg, get_analyzed_targets_fn=_get_analyzed_targets))


def _require_targets_for_menu_action(cfg: dict[str, object], action: str) -> bool:
    app = _app()
    return cast(
        bool,
        app.app_support.require_targets_for_menu_action(
            cfg,
            action,
            has_analyzed_targets_fn=_has_analyzed_targets,
            print_fn=print,
            pause_fn=app.pause,
        ),
    )


def _cache_key_for_target(cfg: dict[str, object], target_name: str) -> str:
    app = _app()
    compute_cache_key_fn = cast(Callable[[Mapping[str, object]], str], app.cache.compute_cache_key)
    return cast(str, app.app_support.cache_key_for_target(cfg, target_name, compute_cache_key_fn=compute_cache_key_fn))


def _split_csv_values(raw: str) -> list[str]:
    app = _app()
    return cast(list[str], app.app_support.split_csv_values(raw))


def _discover_graphics_rule_selector_options(
    cfg: dict[str, object] | None,
    *,
    selector_field: str,
    module_kind: str,
) -> list[dict[str, Any]]:
    app = _app()
    return app.app_graphics_from_app_module.discover_graphics_rule_selector_options_from_app(
        cfg,
        selector_field=selector_field,
        module_kind=module_kind,
        app_module=app,
    )


def _pick_or_prompt_graphics_rule_selector_value(
    selector_field: str,
    module_kind: str,
    *,
    cfg: dict[str, object] | None = None,
) -> str:
    app = _app()
    return app.app_graphics_from_app_module.pick_or_prompt_graphics_rule_selector_value_from_app(
        selector_field,
        module_kind,
        cfg=cfg,
        app_module=app,
    )


def _annotate_graphics_entries_with_structure_paths(
    entries: list[dict[str, Any]],
    project_bp: BasePicture,
    graph: ProjectGraph,
) -> list[dict[str, Any]]:
    app = _app()
    return app.app_graphics_from_app_module.annotate_graphics_entries_with_structure_paths_from_app(
        entries,
        project_bp,
        graph,
        app_module=app,
    )


def graphics_rules_menu(cfg: dict[str, object] | None = None) -> None:
    app = _app()
    app.app_graphics_from_app_module.graphics_rules_menu_from_app(cfg, app_module=app)


def _prompt_graphics_rule_definition_with_config(cfg: dict[str, object] | None) -> dict[str, Any] | None:
    app = _app()
    return app.app_graphics_from_app_module.prompt_graphics_rule_definition_with_config_from_app(
        cfg,
        app_module=app,
    )


def _collect_graphics_layout_entries_for_target(
    target_name: str,
    project_bp: BasePicture,
    graph: ProjectGraph,
) -> list[dict[str, Any]]:
    app = _app()
    return app.app_graphics_from_app_module.collect_graphics_layout_entries_for_target_from_app(
        target_name,
        project_bp,
        graph,
        app_module=app,
    )


def run_graphics_rules_validation(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_graphics_from_app_module.run_graphics_rules_validation_from_app(cfg, app_module=app)


def _get_documentation_unit_selection() -> dict[str, Any]:
    app = _app()
    return app.app_docs_from_app_module.get_documentation_unit_selection_from_app(app_module=app)


def preview_documentation_unit_candidates(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_docs_from_app_module.preview_documentation_unit_candidates_from_app(cfg, app_module=app)


def configure_documentation_scope_by_moduletype(cfg: dict[str, object]) -> bool:
    del cfg
    app = _app()
    return app.app_docs_from_app_module.configure_documentation_scope_by_moduletype_from_app(app_module=app)


def configure_documentation_scope_by_instance_path(cfg: dict[str, object]) -> bool:
    del cfg
    app = _app()
    return app.app_docs_from_app_module.configure_documentation_scope_by_instance_path_from_app(app_module=app)


def reset_documentation_scope(cfg: dict[str, object]) -> bool:
    del cfg
    app = _app()
    return app.app_docs_from_app_module.reset_documentation_scope_from_app(app_module=app)


def run_generate_documentation(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_docs_from_app_module.run_generate_documentation_from_app(cfg, app_module=app)


def documentation_menu(cfg: dict[str, object]) -> bool:
    app = _app()
    return app.app_docs_from_app_module.documentation_menu_from_app(cfg, app_module=app)


def _iter_loaded_projects(
    cfg: dict[str, object],
    *,
    use_cache: bool = True,
) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
    app = _app()
    return cast(
        Iterator[tuple[str, BasePicture, ProjectGraph]],
        app.app_analysis.iter_loaded_projects(
            cfg,
            use_cache=use_cache,
            require_analyzed_targets_fn=_require_analyzed_targets,
            load_project_fn=app.load_project,
        ),
    )


def _source_paths_for_current_target(project_bp: BasePicture, graph: ProjectGraph) -> set[Path]:
    app = _app()
    return cast(set[Path], app.app_analysis.source_paths_for_current_target(project_bp, graph))


def _target_is_library(cfg: dict[str, object], project_bp: BasePicture, graph: ProjectGraph) -> bool:
    app = _app()
    return cast(bool, app.app_analysis.target_is_library(cfg, project_bp, graph))


def load_project(
    cfg: dict[str, object],
    target_name: str | None = None,
    *,
    use_cache: bool = True,
    use_file_ast_cache: bool = True,
    refresh_mode: str = "full",
    collect_stage_timings: bool = False,
    status_update_fn: Callable[[str], None] | None = None,
) -> tuple[BasePicture, ProjectGraph]:
    app = _app()
    return cast(
        tuple[BasePicture, ProjectGraph],
        app.app_analysis.load_project(
            cfg,
            target_name=target_name,
            use_cache=use_cache,
            use_file_ast_cache=use_file_ast_cache,
            refresh_mode=refresh_mode,
            collect_stage_timings=collect_stage_timings,
            require_analyzed_targets_fn=app._require_analyzed_targets,
            cache_key_for_target_fn=app._cache_key_for_target,
            target_load_error_factory=app.TargetLoadError,
            get_cache_dir_fn=app.get_cache_dir,
            status_update_fn=status_update_fn,
        ),
    )


def load_program_ast(
    cfg: dict[str, object],
    program_name: str,
    *,
    force_dependency_resolution: bool = False,
) -> tuple[BasePicture, ProjectGraph]:
    app = _app()
    return cast(
        tuple[BasePicture, ProjectGraph],
        app.app_analysis.load_program_ast(
            cfg,
            program_name,
            force_dependency_resolution=force_dependency_resolution,
        ),
    )


def force_refresh_ast(cfg: dict[str, object]) -> tuple[BasePicture, ProjectGraph] | None:
    app = _app()
    return cast(
        tuple[BasePicture, ProjectGraph] | None,
        app.app_analysis.force_refresh_ast(
            cfg,
            get_analyzed_targets_fn=app._get_analyzed_targets,
            cache_key_for_target_fn=app._cache_key_for_target,
            load_project_fn=app.load_project,
            ast_cache_cls=app.ASTCache,
            get_cache_dir_fn=app.get_cache_dir,
        ),
    )


def ensure_ast_cache(cfg: dict[str, object], *, emit_output_fn: Callable[..., None] | None = None) -> bool:
    app = _app()
    return cast(
        bool,
        app.app_analysis.ensure_ast_cache(
            cfg,
            get_analyzed_targets_fn=app._get_analyzed_targets,
            cache_key_for_target_fn=app._cache_key_for_target,
            load_project_fn=app.load_project,
            ast_cache_cls=app.ASTCache,
            get_cache_dir_fn=app.get_cache_dir,
            emit_output_fn=app.emit_output if emit_output_fn is None else emit_output_fn,
        ),
    )


def refresh_analysis_caches(cfg: dict[str, object]) -> tuple[BasePicture, ProjectGraph] | None:
    app = _app()
    return cast(
        tuple[BasePicture, ProjectGraph] | None,
        app.app_analysis.refresh_analysis_caches(
            cfg,
            force_refresh_ast_fn=app.force_refresh_ast,
            get_cache_dir_fn=app.get_cache_dir,
            get_cache_manager_fn=app.cache_module.get_cache_manager,
            emit_output_fn=app.emit_output,
        ),
    )
