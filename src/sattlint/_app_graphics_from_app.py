from __future__ import annotations

from typing import Any

from sattline_parser.models.ast_model import BasePicture

from . import _app_graphics_menus as graphics_menus_module
from . import graphics_rules as graphics_rules_module
from .config_types import ConfigDict
from .models.project_graph import ProjectGraph


def discover_graphics_rule_selector_options_from_app(
    cfg: ConfigDict | None,
    *,
    selector_field: str,
    module_kind: str,
    app_module: Any,
) -> list[dict[str, Any]]:
    return app_module.app_graphics.discover_graphics_rule_selector_options(
        cfg,
        selector_field=selector_field,
        module_kind=module_kind,
        has_analyzed_targets_fn=app_module._has_analyzed_targets,
        iter_loaded_projects_fn=app_module._iter_loaded_projects,
        collect_graphics_layout_entries_for_target_fn=app_module._collect_graphics_layout_entries_for_target,
    )


def pick_or_prompt_graphics_rule_selector_value_from_app(
    selector_field: str,
    module_kind: str,
    *,
    cfg: ConfigDict | None,
    app_module: Any,
) -> str:
    return app_module.app_graphics.pick_or_prompt_graphics_rule_selector_value(
        selector_field,
        module_kind,
        cfg=cfg,
        discover_graphics_rule_selector_options_fn=app_module._discover_graphics_rule_selector_options,
    )


def annotate_graphics_entries_with_structure_paths_from_app(
    entries: list[dict[str, Any]],
    project_bp: BasePicture,
    graph: ProjectGraph,
    *,
    app_module: Any,
) -> list[dict[str, Any]]:
    return app_module.app_graphics.annotate_graphics_entries_with_structure_paths(
        entries,
        project_bp,
        graph,
        classify_documentation_structure_fn=app_module.classify_documentation_structure,
        discover_documentation_unit_candidates_fn=app_module.discover_documentation_unit_candidates,
    )


def graphics_rules_menu_from_app(cfg: ConfigDict | None, *, app_module: Any) -> None:
    graphics_menus_module.graphics_rules_menu(
        cfg,
        get_graphics_rules_path_fn=app_module.get_graphics_rules_path,
        load_graphics_rules_fn=app_module.load_graphics_rules,
        save_graphics_rules_fn=app_module.save_graphics_rules,
        prompt_graphics_rule_definition_with_config_fn=app_module._prompt_graphics_rule_definition_with_config,
        graphics_rule_label_fn=app_module._graphics_rule_label,
        clear_screen_fn=app_module.clear_screen,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        confirm_fn=app_module.confirm,
        prompt_fn=app_module.prompt,
        quit_app_fn=app_module.quit_app,
        pause_fn=app_module.pause,
        print_graphics_rules_summary_fn=app_module.app_graphics.print_graphics_rules_summary,
        emit_output_fn=app_module.app_graphics.emit_output,
        upsert_graphics_rule_fn=graphics_rules_module.upsert_graphics_rule,
        remove_graphics_rule_fn=graphics_rules_module.remove_graphics_rule,
        interaction=app_module.build_menu_interaction(),
    )


def prompt_graphics_rule_definition_with_config_from_app(
    cfg: ConfigDict | None,
    *,
    app_module: Any,
) -> dict[str, Any] | None:
    return app_module.app_graphics.prompt_graphics_rule_definition_with_config(
        cfg,
        prompt_fn=app_module.prompt,
        pause_fn=app_module.pause,
        pick_or_prompt_graphics_rule_selector_value_fn=app_module._pick_or_prompt_graphics_rule_selector_value,
        interaction=app_module.build_menu_interaction(),
    )


def collect_graphics_layout_entries_for_target_from_app(
    target_name: str,
    project_bp: BasePicture,
    graph: ProjectGraph,
    *,
    app_module: Any,
) -> list[dict[str, Any]]:
    return app_module.app_graphics.collect_graphics_layout_entries_for_target(
        target_name,
        project_bp,
        graph,
        annotate_graphics_entries_with_structure_paths_fn=app_module._annotate_graphics_entries_with_structure_paths,
    )


def run_graphics_rules_validation_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    app_module.app_graphics.run_graphics_rules_validation(
        cfg,
        get_graphics_rules_path_fn=app_module.get_graphics_rules_path,
        load_graphics_rules_fn=app_module.load_graphics_rules,
        iter_loaded_projects_fn=app_module._iter_loaded_projects,
        collect_graphics_layout_entries_for_target_fn=app_module._collect_graphics_layout_entries_for_target,
        pause_fn=app_module.pause,
    )
