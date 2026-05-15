from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from .models.project_graph import ProjectGraph

ConfigDict = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]


def run_cli(
    argv: list[str],
    *,
    run_cli_owner_fn: Callable[..., int],
    config_path: Path,
    build_cli_parser_fn: Callable[[], Any],
    run_syntax_check_command_fn: Callable[[str], int],
    load_config_fn: Callable[[Path], tuple[ConfigDict, bool]],
    apply_debug_fn: Callable[[ConfigDict], None],
    run_validate_config_command_fn: Callable[..., int],
    run_analyze_command_fn: Callable[..., int],
    run_simulate_command_fn: Callable[..., int],
    run_docgen_command_fn: Callable[..., int],
    run_format_icf_command_fn: Callable[..., int],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    return cast(
        int,
        run_cli_owner_fn(
            argv,
            config_path=config_path,
            build_cli_parser_fn=build_cli_parser_fn,
            run_syntax_check_command_fn=run_syntax_check_command_fn,
            load_config_fn=load_config_fn,
            apply_debug_fn=apply_debug_fn,
            run_validate_config_command_fn=run_validate_config_command_fn,
            run_analyze_command_fn=run_analyze_command_fn,
            run_simulate_command_fn=run_simulate_command_fn,
            run_docgen_command_fn=run_docgen_command_fn,
            run_format_icf_command_fn=run_format_icf_command_fn,
            exit_success=exit_success,
            exit_usage_error=exit_usage_error,
        ),
    )


def run_validate_config_command(
    cfg: ConfigDict,
    *,
    config_path: Path,
    default_used: bool,
    run_validate_config_command_fn: Callable[..., int],
    validate_config_fn: Callable[[ConfigDict], Any],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    return cast(
        int,
        run_validate_config_command_fn(
            cfg,
            config_path=config_path,
            default_used=default_used,
            validate_config_fn=validate_config_fn,
            exit_success=exit_success,
            exit_usage_error=exit_usage_error,
        ),
    )


def run_analyze_command(
    cfg: ConfigDict,
    *,
    selected_keys: list[str] | None,
    use_cache: bool,
    run_analyze_command_fn: Callable[..., int],
    run_checks_owner_fn: Callable[..., None],
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]],
    get_selectable_analyzers_fn: Callable[[], list[Any]],
    get_enabled_analyzers_fn: Callable[[], list[Any]],
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool],
    exit_success: int,
) -> int:
    def _run_checks(local_cfg: ConfigDict, local_selected_keys: list[str] | None, local_use_cache: bool) -> None:
        def _iter_nested_projects(nested_cfg: ConfigDict) -> Iterator[LoadedProject]:
            return iter_loaded_projects_fn(nested_cfg, use_cache=local_use_cache)

        run_checks_owner_fn(
            local_cfg,
            local_selected_keys,
            iter_loaded_projects_fn=_iter_nested_projects,
            get_enabled_analyzers_fn=get_selectable_analyzers_fn if local_selected_keys else get_enabled_analyzers_fn,
            target_is_library_fn=target_is_library_fn,
            pause_fn=None,
        )

    return cast(
        int,
        run_analyze_command_fn(
            cfg,
            selected_keys=selected_keys,
            use_cache=use_cache,
            run_checks_fn=_run_checks,
            exit_success=exit_success,
        ),
    )


def run_simulate_command(
    cfg: ConfigDict,
    *,
    target_path: str,
    module_name: str,
    mode: str,
    max_scans: int,
    output_format: str,
    output_path: str | None,
    use_cache: bool,
    run_simulate_command_fn: Callable[..., int],
    simulate_fn: Callable[..., Any],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    return cast(
        int,
        run_simulate_command_fn(
            cfg,
            target_path=target_path,
            module_name=module_name,
            mode=mode,
            max_scans=max_scans,
            output_format=output_format,
            output_path=output_path,
            use_cache=use_cache,
            simulate_fn=simulate_fn,
            exit_success=exit_success,
            exit_usage_error=exit_usage_error,
        ),
    )


def run_docgen_command(
    cfg: ConfigDict,
    *,
    use_cache: bool,
    output_dir: str | None,
    output_path: str | None,
    run_docgen_command_fn: Callable[..., int],
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]],
    documentation_unit_selection_fn: Callable[[], dict[str, Any]],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    def _iter_projects(local_cfg: ConfigDict, local_use_cache: bool) -> Iterator[LoadedProject]:
        return iter_loaded_projects_fn(local_cfg, use_cache=local_use_cache)

    return cast(
        int,
        run_docgen_command_fn(
            cfg,
            use_cache=use_cache,
            output_dir=output_dir,
            output_path=output_path,
            iter_loaded_projects_fn=_iter_projects,
            documentation_unit_selection_fn=documentation_unit_selection_fn,
            exit_success=exit_success,
            exit_usage_error=exit_usage_error,
        ),
    )


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
    return cast(str, summarize_targets_fn(cfg, get_analyzed_targets_fn=get_analyzed_targets_fn))


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
    return cast(
        bool,
        config_menu_fn(
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
        ),
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
        confirm_fn=confirm_fn,
        force_refresh_ast_fn=force_refresh_ast_fn,
    )


def main(
    argv: list[str] | None,
    *,
    run_cli_fn: Callable[[list[str]], int],
    load_config_fn: Callable[[Path], tuple[ConfigDict, bool]],
    config_path: Path,
    apply_debug_fn: Callable[[ConfigDict], None],
    emit_output_fn: Callable[..., None],
    pause_fn: Callable[[], None],
    self_check_fn: Callable[[ConfigDict], bool],
    confirm_fn: Callable[[str], bool],
    has_analyzed_targets_fn: Callable[[ConfigDict], bool],
    ensure_ast_cache_fn: Callable[[ConfigDict], bool],
    run_main_loop_fn: Callable[..., None],
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    summarize_targets_fn: Callable[[ConfigDict], str],
    require_targets_for_menu_action_fn: Callable[[ConfigDict, str], bool],
    analysis_menu_fn: Callable[[ConfigDict], None],
    documentation_menu_fn: Callable[[ConfigDict], bool],
    config_menu_fn: Callable[[ConfigDict], bool],
    tools_menu_fn: Callable[[ConfigDict], None],
    show_help_fn: Callable[[ConfigDict], None],
    save_config_fn: Callable[[Path, ConfigDict], None],
    quit_app_fn: Callable[[], None],
    quit_app_error: type[BaseException],
) -> int:
    cli_args = [] if argv is None else argv
    if cli_args:
        return run_cli_fn(cli_args)

    try:
        cfg, default_used = load_config_fn(config_path)
        apply_debug_fn(cfg)
        if default_used:
            emit_output_fn("Warning: Default config created. Open Setup before running analysis.")
            pause_fn()
        else:
            if not self_check_fn(cfg) and not confirm_fn("Self-check failed. Continue?"):
                return 0
            if has_analyzed_targets_fn(cfg) and not ensure_ast_cache_fn(cfg):
                pause_fn()
        run_main_loop_fn(
            cfg,
            clear_screen_fn=clear_screen_fn,
            print_menu_fn=print_menu_fn,
            menu_option_factory=menu_option_factory,
            summarize_targets_fn=summarize_targets_fn,
            require_targets_for_menu_action_fn=require_targets_for_menu_action_fn,
            analysis_menu_fn=analysis_menu_fn,
            documentation_menu_fn=documentation_menu_fn,
            config_menu_fn=config_menu_fn,
            tools_menu_fn=tools_menu_fn,
            show_help_fn=show_help_fn,
            confirm_fn=confirm_fn,
            save_config_fn=save_config_fn,
            config_path=config_path,
            quit_app_fn=quit_app_fn,
        )
        return 0
    except quit_app_error:
        return 0
