from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sattline_parser.models.ast_model import BasePicture

from . import _app_startup_docs_graphics
from .models.project_graph import ProjectGraph

ConfigDict = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]


@dataclass(frozen=True)
class InteractiveCliOverrides:
    config_path: Path
    debug: bool
    ui_mode: str | None = None


annotate_graphics_entries_with_structure_paths = (
    _app_startup_docs_graphics.annotate_graphics_entries_with_structure_paths
)
collect_graphics_layout_entries_for_target = _app_startup_docs_graphics.collect_graphics_layout_entries_for_target
configure_documentation_scope_by_instance_path = (
    _app_startup_docs_graphics.configure_documentation_scope_by_instance_path
)
configure_documentation_scope_by_moduletype = _app_startup_docs_graphics.configure_documentation_scope_by_moduletype
discover_graphics_rule_selector_options = _app_startup_docs_graphics.discover_graphics_rule_selector_options
documentation_menu = _app_startup_docs_graphics.documentation_menu
get_documentation_unit_selection = _app_startup_docs_graphics.get_documentation_unit_selection
graphics_rules_menu = _app_startup_docs_graphics.graphics_rules_menu
pick_or_prompt_graphics_rule_selector_value = _app_startup_docs_graphics.pick_or_prompt_graphics_rule_selector_value
preview_documentation_unit_candidates = _app_startup_docs_graphics.preview_documentation_unit_candidates
prompt_graphics_rule_definition_with_config = _app_startup_docs_graphics.prompt_graphics_rule_definition_with_config
reset_documentation_scope = _app_startup_docs_graphics.reset_documentation_scope
run_generate_documentation = _app_startup_docs_graphics.run_generate_documentation
run_graphics_rules_validation = _app_startup_docs_graphics.run_graphics_rules_validation


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
    run_cache_prune_command_fn: Callable[..., int] | None = None,
    run_telemetry_summary_command_fn: Callable[..., int],
    run_format_icf_command_fn: Callable[..., int],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    return run_cli_owner_fn(
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
        run_cache_prune_command_fn=run_cache_prune_command_fn,
        run_telemetry_summary_command_fn=run_telemetry_summary_command_fn,
        run_format_icf_command_fn=run_format_icf_command_fn,
        exit_success=exit_success,
        exit_usage_error=exit_usage_error,
    )


def resolve_interactive_cli_overrides(
    argv: list[str],
    *,
    build_cli_parser_fn: Callable[[], Any] | None,
    default_config_path: Path,
) -> InteractiveCliOverrides | None:
    if not argv or build_cli_parser_fn is None:
        return None

    try:
        parser = build_cli_parser_fn()
        parsed_namespace, leftover = parser.parse_known_args(argv)
    except SystemExit:
        return None

    if leftover:
        return None

    command = getattr(parsed_namespace, "command", None)
    if command is not None:
        return None

    quiet = bool(getattr(parsed_namespace, "quiet", False))
    no_cache = bool(getattr(parsed_namespace, "no_cache", False))
    if quiet or no_cache:
        return None

    debug = bool(getattr(parsed_namespace, "debug", False))
    ui_mode = getattr(parsed_namespace, "ui", None)
    config_path_text = getattr(parsed_namespace, "config", None)
    if not debug and config_path_text is None and ui_mode is None:
        return None

    config_path = Path(config_path_text) if config_path_text else default_config_path
    return InteractiveCliOverrides(config_path=config_path, debug=debug, ui_mode=ui_mode)


def run_telemetry_summary_command(
    cfg: ConfigDict,
    *,
    config_path: Path,
    output_format: str,
    output_path: str | None,
    run_telemetry_summary_command_fn: Callable[..., int],
    telemetry_output_path_fn: Callable[[Path], Path],
    summarize_telemetry_fn: Callable[[Path], dict[str, Any]],
    render_text_summary_fn: Callable[[dict[str, Any]], str],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    return run_telemetry_summary_command_fn(
        cfg,
        config_path=config_path,
        output_format=output_format,
        output_path=output_path,
        telemetry_output_path_fn=telemetry_output_path_fn,
        summarize_telemetry_fn=summarize_telemetry_fn,
        render_text_summary_fn=render_text_summary_fn,
        exit_success=exit_success,
        exit_usage_error=exit_usage_error,
    )


def run_cache_prune_command(
    *,
    cache_dir: str | None,
    run_cache_prune_command_fn: Callable[..., int],
    prune_cache_dir_fn: Callable[[Path | None], Any],
    get_cache_dir_fn: Callable[[], Path],
    exit_success: int,
    exit_usage_error: int,
) -> int:
    return run_cache_prune_command_fn(
        cache_dir=cache_dir,
        prune_cache_dir_fn=prune_cache_dir_fn,
        get_cache_dir_fn=get_cache_dir_fn,
        exit_success=exit_success,
        exit_usage_error=exit_usage_error,
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
    return run_validate_config_command_fn(
        cfg,
        config_path=config_path,
        default_used=default_used,
        validate_config_fn=validate_config_fn,
        exit_success=exit_success,
        exit_usage_error=exit_usage_error,
    )


def run_analyze_command(
    cfg: ConfigDict,
    *,
    selected_keys: list[str] | None,
    selected_issue_kinds: frozenset[str] | None = None,
    use_cache: bool,
    run_analyze_command_fn: Callable[..., int],
    run_checks_owner_fn: Callable[..., None],
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]],
    get_selectable_analyzers_fn: Callable[[], list[Any]],
    get_enabled_analyzers_fn: Callable[[], list[Any]],
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool],
    exit_success: int,
) -> int:
    def _run_checks(
        local_cfg: ConfigDict,
        local_selected_keys: list[str] | None,
        local_use_cache: bool,
        *,
        selected_issue_kinds: frozenset[str] | None = None,
    ) -> None:
        def _iter_nested_projects(nested_cfg: ConfigDict) -> Iterator[LoadedProject]:
            return iter_loaded_projects_fn(nested_cfg, use_cache=local_use_cache)

        run_checks_owner_fn(
            local_cfg | {"use_cache": local_use_cache},
            local_selected_keys,
            selected_issue_kinds=selected_issue_kinds,
            iter_loaded_projects_fn=_iter_nested_projects,
            get_enabled_analyzers_fn=get_selectable_analyzers_fn if local_selected_keys else get_enabled_analyzers_fn,
            target_is_library_fn=target_is_library_fn,
            pause_fn=None,
        )

    return run_analyze_command_fn(
        cfg,
        selected_keys=selected_keys,
        selected_issue_kinds=selected_issue_kinds,
        use_cache=use_cache,
        run_checks_fn=_run_checks,
        exit_success=exit_success,
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
    return run_simulate_command_fn(
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

    return run_docgen_command_fn(
        cfg,
        use_cache=use_cache,
        output_dir=output_dir,
        output_path=output_path,
        iter_loaded_projects_fn=_iter_projects,
        documentation_unit_selection_fn=documentation_unit_selection_fn,
        exit_success=exit_success,
        exit_usage_error=exit_usage_error,
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


def main(
    argv: list[str] | None,
    *,
    run_cli_fn: Callable[[list[str]], int],
    build_cli_parser_fn: Callable[[], Any] | None = None,
    load_config_fn: Callable[[Path], tuple[ConfigDict, bool]],
    config_path: Path,
    apply_debug_fn: Callable[[ConfigDict], None],
    resolve_interactive_ui_mode_fn: Callable[[ConfigDict, str | None], str] | None = None,
    set_interactive_ui_mode_fn: Callable[[str], None] | None = None,
    reset_interactive_ui_mode_fn: Callable[[], None] | None = None,
    emit_output_fn: Callable[..., None],
    pause_fn: Callable[[], None],
    self_check_fn: Callable[[ConfigDict], bool],
    confirm_fn: Callable[[str], bool],
    has_analyzed_targets_fn: Callable[[ConfigDict], bool],
    ensure_ast_cache_fn: Callable[[ConfigDict], bool],
    run_main_loop_fn: Callable[..., None],
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    choose_menu_option_fn: Callable[..., str] | None = None,
    interaction: Any | None = None,
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
    interactive_cli_overrides = resolve_interactive_cli_overrides(
        cli_args,
        build_cli_parser_fn=build_cli_parser_fn,
        default_config_path=config_path,
    )
    if cli_args and interactive_cli_overrides is None:
        return run_cli_fn(cli_args)

    try:
        effective_config_path = config_path
        if interactive_cli_overrides is not None:
            effective_config_path = interactive_cli_overrides.config_path

        cfg, default_used = load_config_fn(effective_config_path)
        if interactive_cli_overrides is not None and interactive_cli_overrides.debug:
            cfg["debug"] = True
        apply_debug_fn(cfg)
        resolved_ui_mode = "textual"
        if resolve_interactive_ui_mode_fn is not None:
            resolved_ui_mode = resolve_interactive_ui_mode_fn(
                cfg,
                interactive_cli_overrides.ui_mode if interactive_cli_overrides is not None else None,
            )
        if default_used:
            emit_output_fn("Warning: Default config created. Open Setup before running analysis.")
            pause_fn()
        if set_interactive_ui_mode_fn is not None:
            set_interactive_ui_mode_fn(resolved_ui_mode)
        try:
            run_main_loop_kwargs: dict[str, Any] = {
                "summarize_targets_fn": summarize_targets_fn,
                "show_help_fn": show_help_fn,
                "save_config_fn": save_config_fn,
                "config_path": effective_config_path,
                "quit_app_error": quit_app_error,
            }
            run_main_loop_fn(cfg, **run_main_loop_kwargs)
        finally:
            if reset_interactive_ui_mode_fn is not None:
                reset_interactive_ui_mode_fn()
        return 0
    except quit_app_error:
        return 0
