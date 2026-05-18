from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from .models.project_graph import ProjectGraph

ConfigDict = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]


def discover_graphics_rule_selector_options(
    cfg: ConfigDict | None,
    *,
    selector_field: str,
    module_kind: str,
    discover_graphics_rule_selector_options_fn: Callable[..., list[dict[str, Any]]],
    has_analyzed_targets_fn: Callable[[ConfigDict], bool],
    iter_loaded_projects_fn: Callable[[ConfigDict], Iterator[LoadedProject]],
    collect_graphics_layout_entries_for_target_fn: Callable[[str, BasePicture, ProjectGraph], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]],
        discover_graphics_rule_selector_options_fn(
            cfg,
            selector_field=selector_field,
            module_kind=module_kind,
            has_analyzed_targets_fn=has_analyzed_targets_fn,
            iter_loaded_projects_fn=iter_loaded_projects_fn,
            collect_graphics_layout_entries_for_target_fn=collect_graphics_layout_entries_for_target_fn,
        ),
    )


def pick_or_prompt_graphics_rule_selector_value(
    selector_field: str,
    module_kind: str,
    *,
    cfg: ConfigDict | None,
    pick_or_prompt_graphics_rule_selector_value_fn: Callable[..., str],
    discover_graphics_rule_selector_options_fn: Callable[..., list[dict[str, Any]]],
) -> str:
    return cast(
        str,
        pick_or_prompt_graphics_rule_selector_value_fn(
            selector_field,
            module_kind,
            cfg=cfg,
            discover_graphics_rule_selector_options_fn=discover_graphics_rule_selector_options_fn,
        ),
    )


def annotate_graphics_entries_with_structure_paths(
    entries: list[dict[str, Any]],
    project_bp: BasePicture,
    graph: ProjectGraph,
    *,
    annotate_graphics_entries_with_structure_paths_fn: Callable[..., list[dict[str, Any]]],
    classify_documentation_structure_fn: Callable[..., Any],
    discover_documentation_unit_candidates_fn: Callable[..., list[Any]],
) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]],
        annotate_graphics_entries_with_structure_paths_fn(
            entries,
            project_bp,
            graph,
            classify_documentation_structure_fn=classify_documentation_structure_fn,
            discover_documentation_unit_candidates_fn=discover_documentation_unit_candidates_fn,
        ),
    )


def graphics_rules_menu(
    cfg: ConfigDict | None,
    *,
    graphics_rules_menu_fn: Callable[..., None],
    get_graphics_rules_path_fn: Callable[[], Path],
    load_graphics_rules_fn: Callable[[Path | None], tuple[dict[str, Any], bool]],
    save_graphics_rules_fn: Callable[[Path, dict[str, Any]], None],
    prompt_graphics_rule_definition_with_config_fn: Callable[[ConfigDict | None], dict[str, Any] | None],
    graphics_rule_label_fn: Callable[[dict[str, Any]], str],
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    confirm_fn: Callable[[str], bool],
    prompt_fn: Callable[..., str],
    quit_app_fn: Callable[[], None],
    pause_fn: Callable[[], None],
) -> None:
    graphics_rules_menu_fn(
        cfg,
        get_graphics_rules_path_fn=get_graphics_rules_path_fn,
        load_graphics_rules_fn=load_graphics_rules_fn,
        save_graphics_rules_fn=save_graphics_rules_fn,
        prompt_graphics_rule_definition_with_config_fn=prompt_graphics_rule_definition_with_config_fn,
        graphics_rule_label_fn=graphics_rule_label_fn,
        clear_screen_fn=clear_screen_fn,
        print_menu_fn=print_menu_fn,
        menu_option_factory=menu_option_factory,
        confirm_fn=confirm_fn,
        prompt_fn=prompt_fn,
        quit_app_fn=quit_app_fn,
        pause_fn=pause_fn,
    )


def prompt_graphics_rule_definition_with_config(
    cfg: ConfigDict | None,
    *,
    prompt_graphics_rule_definition_with_config_fn: Callable[..., dict[str, Any] | None],
    prompt_fn: Callable[..., str],
    pause_fn: Callable[[], None],
    pick_or_prompt_graphics_rule_selector_value_fn: Callable[..., str],
) -> dict[str, Any] | None:
    return cast(
        dict[str, Any] | None,
        prompt_graphics_rule_definition_with_config_fn(
            cfg,
            prompt_fn=prompt_fn,
            pause_fn=pause_fn,
            pick_or_prompt_graphics_rule_selector_value_fn=pick_or_prompt_graphics_rule_selector_value_fn,
        ),
    )


def collect_graphics_layout_entries_for_target(
    target_name: str,
    project_bp: BasePicture,
    graph: ProjectGraph,
    *,
    collect_graphics_layout_entries_for_target_fn: Callable[..., list[dict[str, Any]]],
    annotate_graphics_entries_with_structure_paths_fn: Callable[..., list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]],
        collect_graphics_layout_entries_for_target_fn(
            target_name,
            project_bp,
            graph,
            annotate_graphics_entries_with_structure_paths_fn=annotate_graphics_entries_with_structure_paths_fn,
        ),
    )


def run_graphics_rules_validation(
    cfg: ConfigDict,
    *,
    run_graphics_rules_validation_fn: Callable[..., None],
    get_graphics_rules_path_fn: Callable[[], Path],
    load_graphics_rules_fn: Callable[[Path | None], tuple[dict[str, Any], bool]],
    iter_loaded_projects_fn: Callable[[ConfigDict], Iterator[LoadedProject]],
    collect_graphics_layout_entries_for_target_fn: Callable[[str, BasePicture, ProjectGraph], list[dict[str, Any]]],
    pause_fn: Callable[[], None],
) -> None:
    run_graphics_rules_validation_fn(
        cfg,
        get_graphics_rules_path_fn=get_graphics_rules_path_fn,
        load_graphics_rules_fn=load_graphics_rules_fn,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        collect_graphics_layout_entries_for_target_fn=collect_graphics_layout_entries_for_target_fn,
        pause_fn=pause_fn,
    )


def get_documentation_unit_selection(
    *,
    get_documentation_unit_selection_fn: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    return cast(dict[str, Any], get_documentation_unit_selection_fn())


def preview_documentation_unit_candidates(
    cfg: ConfigDict,
    *,
    preview_documentation_unit_candidates_fn: Callable[..., None],
    iter_loaded_projects_fn: Callable[[ConfigDict], Iterator[LoadedProject]],
    pause_fn: Callable[[], None],
) -> None:
    preview_documentation_unit_candidates_fn(
        cfg,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        pause_fn=pause_fn,
    )


def configure_documentation_scope_by_moduletype(
    *,
    configure_documentation_scope_by_moduletype_fn: Callable[..., bool],
    split_csv_values_fn: Callable[[str], list[str]],
    pause_fn: Callable[[], None],
) -> bool:
    return cast(
        bool,
        configure_documentation_scope_by_moduletype_fn(
            split_csv_values_fn=split_csv_values_fn,
            pause_fn=pause_fn,
        ),
    )


def configure_documentation_scope_by_instance_path(
    *,
    configure_documentation_scope_by_instance_path_fn: Callable[..., bool],
    split_csv_values_fn: Callable[[str], list[str]],
    pause_fn: Callable[[], None],
) -> bool:
    return cast(
        bool,
        configure_documentation_scope_by_instance_path_fn(
            split_csv_values_fn=split_csv_values_fn,
            pause_fn=pause_fn,
        ),
    )


def reset_documentation_scope(
    *,
    reset_documentation_scope_fn: Callable[..., bool],
    pause_fn: Callable[[], None],
) -> bool:
    return cast(bool, reset_documentation_scope_fn(pause_fn=pause_fn))


def run_generate_documentation(
    cfg: ConfigDict,
    *,
    run_generate_documentation_fn: Callable[..., None],
    iter_loaded_projects_fn: Callable[[ConfigDict], Iterator[LoadedProject]],
    prompt_fn: Callable[..., str],
    pause_fn: Callable[[], None],
) -> None:
    run_generate_documentation_fn(
        cfg,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        prompt_fn=prompt_fn,
        pause_fn=pause_fn,
    )


def documentation_menu(
    cfg: ConfigDict,
    *,
    documentation_menu_fn: Callable[..., bool],
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    pause_fn: Callable[[], None],
    split_csv_values_fn: Callable[[str], list[str]],
    iter_loaded_projects_fn: Callable[[ConfigDict], Iterator[LoadedProject]],
    prompt_fn: Callable[..., str],
) -> bool:
    return cast(
        bool,
        documentation_menu_fn(
            cfg,
            clear_screen_fn=clear_screen_fn,
            print_menu_fn=print_menu_fn,
            menu_option_factory=menu_option_factory,
            quit_app_fn=quit_app_fn,
            pause_fn=pause_fn,
            split_csv_values_fn=split_csv_values_fn,
            iter_loaded_projects_fn=iter_loaded_projects_fn,
            prompt_fn=prompt_fn,
        ),
    )


__all__ = [
    "annotate_graphics_entries_with_structure_paths",
    "collect_graphics_layout_entries_for_target",
    "configure_documentation_scope_by_instance_path",
    "configure_documentation_scope_by_moduletype",
    "discover_graphics_rule_selector_options",
    "documentation_menu",
    "get_documentation_unit_selection",
    "graphics_rules_menu",
    "pick_or_prompt_graphics_rule_selector_value",
    "preview_documentation_unit_candidates",
    "prompt_graphics_rule_definition_with_config",
    "reset_documentation_scope",
    "run_generate_documentation",
    "run_graphics_rules_validation",
]
