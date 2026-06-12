from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

from sattline_parser.models.ast_model import BasePicture

from .config_types import ConfigDict
from .models.project_graph import ProjectGraph

LoadedProject = tuple[str, BasePicture, ProjectGraph]


def run_icf_formatter(
    cfg: ConfigDict,
    *,
    run_format_icf_command_fn: Callable[[ConfigDict], int],
    pause_fn: Callable[[], None],
) -> None:
    run_format_icf_command_fn(cfg)
    pause_fn()


def show_config(
    cfg: ConfigDict,
    *,
    show_config_fn: Callable[..., None],
    get_graphics_rules_path_fn: Callable[[], Path],
    load_graphics_rules_fn: Callable[[Path | None], tuple[dict[str, Any], bool]],
    graphics_rule_config_line_fn: Callable[[dict[str, Any]], str],
) -> None:
    show_config_fn(
        cfg,
        get_graphics_rules_path_fn=get_graphics_rules_path_fn,
        load_graphics_rules_fn=load_graphics_rules_fn,
        graphics_rule_config_line_fn=graphics_rule_config_line_fn,
    )


def print_menu(
    title: str,
    options: Sequence[Any],
    *,
    intro: str | None,
    note: str | None,
    print_menu_owner_fn: Callable[..., None],
    print_fn: Callable[..., None],
) -> None:
    print_menu_owner_fn(title, options, print_fn=print_fn, intro=intro, note=note)


def summarize_targets(
    cfg: ConfigDict,
    *,
    summarize_targets_fn: Callable[..., str],
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
) -> str:
    return summarize_targets_fn(cfg, get_analyzed_targets_fn=get_analyzed_targets_fn)


def show_help(
    cfg: ConfigDict,
    *,
    show_help_fn: Callable[..., None],
    clear_screen_fn: Callable[[], None],
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    summarize_targets_fn: Callable[[ConfigDict], str],
    print_fn: Callable[..., None],
    pause_fn: Callable[[], None],
) -> None:
    show_help_fn(
        cfg,
        clear_screen_fn=clear_screen_fn,
        get_analyzed_targets_fn=get_analyzed_targets_fn,
        summarize_targets_fn=summarize_targets_fn,
        print_fn=print_fn,
        pause_fn=pause_fn,
    )


def get_help_text(
    cfg: ConfigDict,
    *,
    get_help_text_fn: Callable[..., str],
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]],
    summarize_targets_fn: Callable[[ConfigDict], str],
) -> str:
    return str(
        get_help_text_fn(
            cfg,
            get_analyzed_targets_fn=get_analyzed_targets_fn,
            summarize_targets_fn=summarize_targets_fn,
        )
    )


def dump_menu(
    cfg: ConfigDict,
    *,
    dump_menu_fn: Callable[..., None],
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    confirm_fn: Callable[[str], bool],
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]],
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] | None = None,
    analyze_variables_fn: Callable[..., Any],
) -> None:
    dump_menu_fn(
        cfg,
        clear_screen_fn=clear_screen_fn,
        print_menu_fn=print_menu_fn,
        menu_option_factory=menu_option_factory,
        quit_app_fn=quit_app_fn,
        confirm_fn=confirm_fn,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        target_is_library_fn=target_is_library_fn,
        analyze_variables_fn=analyze_variables_fn,
    )


def config_menu(
    cfg: ConfigDict,
    *,
    config_menu_fn: Callable[..., bool],
    config_path: Path,
    clear_screen_fn: Callable[[], None],
    show_config_fn: Callable[[ConfigDict], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    prompt_fn: Callable[..., str],
    pause_fn: Callable[[], None],
    confirm_fn: Callable[[str], bool],
    target_exists_fn: Callable[[str, ConfigDict], bool],
    save_config_fn: Callable[[Path, ConfigDict], None],
    apply_debug_fn: Callable[[ConfigDict], None],
    graphics_rules_menu_fn: Callable[[ConfigDict], None],
    quit_app_fn: Callable[[], None],
) -> bool:
    return config_menu_fn(
        cfg,
        config_path=config_path,
        clear_screen_fn=clear_screen_fn,
        show_config_fn=show_config_fn,
        print_menu_fn=print_menu_fn,
        menu_option_factory=menu_option_factory,
        prompt_fn=prompt_fn,
        pause_fn=pause_fn,
        confirm_fn=confirm_fn,
        target_exists_fn=target_exists_fn,
        save_config_fn=save_config_fn,
        apply_debug_fn=apply_debug_fn,
        graphics_rules_menu_fn=graphics_rules_menu_fn,
        quit_app_fn=quit_app_fn,
    )


def tools_menu(
    cfg: ConfigDict,
    *,
    tools_menu_fn: Callable[..., None],
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    self_check_fn: Callable[[ConfigDict], bool],
    pause_fn: Callable[[], None],
    require_targets_for_menu_action_fn: Callable[[ConfigDict, str], bool],
    dump_menu_fn: Callable[[ConfigDict], None],
    run_source_diff_report_fn: Callable[[ConfigDict], None],
    confirm_fn: Callable[[str], bool],
    force_refresh_ast_fn: Callable[[ConfigDict], Any],
) -> None:
    tools_menu_fn(
        cfg,
        clear_screen_fn=clear_screen_fn,
        print_menu_fn=print_menu_fn,
        menu_option_factory=menu_option_factory,
        quit_app_fn=quit_app_fn,
        self_check_fn=self_check_fn,
        pause_fn=pause_fn,
        require_targets_for_menu_action_fn=require_targets_for_menu_action_fn,
        dump_menu_fn=dump_menu_fn,
        run_source_diff_report_fn=run_source_diff_report_fn,
        confirm_fn=confirm_fn,
        force_refresh_ast_fn=force_refresh_ast_fn,
    )
