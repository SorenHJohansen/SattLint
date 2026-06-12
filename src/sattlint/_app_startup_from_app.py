from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any

from sattline_parser.models.ast_model import BasePicture

from . import _app_interactive_menus as interactive_core
from . import _app_startup as startup_core
from .cli import command_handlers as cli_command_handlers_module
from .cli import entry as cli_entry
from .models.project_graph import ProjectGraph

ConfigDict = startup_core.ConfigDict


def run_cli_from_app(argv: list[str], *, app_module: Any) -> int:
    return cli_entry.run_cli(
        argv,
        config_path=app_module.CONFIG_PATH,
        build_cli_parser_fn=app_module.build_cli_parser,
        load_config_fn=app_module.load_config,
        apply_debug_fn=app_module.apply_debug,
        command_handlers=cli_command_handlers_module.build_app_command_handlers(app_module),
        exit_success=app_module.EXIT_SUCCESS,
        exit_usage_error=app_module.EXIT_USAGE_ERROR,
    )


def cli_from_app(*, app_module: Any) -> int:
    argv_source = getattr(app_module, "sys", sys).argv
    return main_from_app(list(argv_source[1:]), app_module=app_module)


def run_validate_config_command_from_app(
    cfg: ConfigDict,
    *,
    config_path: startup_core.Path,
    default_used: bool,
    output_format: str = "text",
    app_module: Any,
) -> int:
    return startup_core.run_validate_config_command(
        cfg,
        config_path=config_path,
        default_used=default_used,
        validate_config_fn=app_module.validate_effective_config,
        output_format=output_format,
        exit_success=app_module.EXIT_SUCCESS,
        exit_usage_error=app_module.EXIT_USAGE_ERROR,
    )


def run_analyze_command_from_app(
    cfg: ConfigDict,
    *,
    selected_keys: list[str] | None,
    selected_issue_kinds: frozenset[str] | None = None,
    use_cache: bool,
    output_format: str = "text",
    app_module: Any,
) -> int:
    return startup_core.run_analyze_command(
        cfg,
        selected_keys=selected_keys,
        selected_issue_kinds=selected_issue_kinds,
        use_cache=use_cache,
        output_format=output_format,
        run_analyze_command_fn=app_module.app_cli_commands.run_analyze_command,
        iter_loaded_projects_fn=app_module._iter_loaded_projects,
        collect_run_checks_result_fn=app_module.app_analysis.collect_run_checks_result,
        get_selectable_analyzers_fn=app_module._get_selectable_analyzers,
        get_enabled_analyzers_fn=app_module._get_enabled_analyzers,
        target_is_library_fn=app_module._target_is_library,
        exit_success=app_module.EXIT_SUCCESS,
    )


def run_simulate_command_from_app(
    cfg: ConfigDict,
    *,
    target_path: str,
    module_name: str,
    mode: str,
    max_scans: int,
    output_format: str,
    output_path: str | None,
    use_cache: bool,
    app_module: Any,
) -> int:
    return startup_core.run_simulate_command(
        cfg,
        target_path=target_path,
        module_name=module_name,
        mode=mode,
        max_scans=max_scans,
        output_format=output_format,
        output_path=output_path,
        use_cache=use_cache,
        run_simulate_command_fn=app_module.app_cli_commands.run_simulate_command,
        simulate_fn=app_module._simulate_target,
        exit_success=app_module.EXIT_SUCCESS,
        exit_usage_error=app_module.EXIT_USAGE_ERROR,
    )


def run_docgen_command_from_app(
    cfg: ConfigDict,
    *,
    use_cache: bool,
    output_dir: str | None,
    output_path: str | None,
    app_module: Any,
) -> int:
    return startup_core.run_docgen_command(
        cfg,
        use_cache=use_cache,
        output_dir=output_dir,
        output_path=output_path,
        run_docgen_command_fn=app_module.app_cli_commands.run_docgen_command,
        iter_loaded_projects_fn=app_module._iter_loaded_projects,
        documentation_unit_selection_fn=app_module._get_documentation_unit_selection,
        exit_success=app_module.EXIT_SUCCESS,
        exit_usage_error=app_module.EXIT_USAGE_ERROR,
    )


def run_cache_prune_command_from_app(*, cache_dir: str | None, app_module: Any) -> int:
    return startup_core.run_cache_prune_command(
        cache_dir=cache_dir,
        run_cache_prune_command_fn=app_module.app_cli_commands.run_cache_prune_command,
        prune_cache_dir_fn=app_module.cache.prune_cache_dir,
        get_cache_dir_fn=app_module.get_cache_dir,
        exit_success=app_module.EXIT_SUCCESS,
        exit_usage_error=app_module.EXIT_USAGE_ERROR,
    )


def run_telemetry_summary_command_from_app(
    cfg: ConfigDict,
    *,
    config_path: startup_core.Path,
    output_format: str,
    output_path: str | None,
    app_module: Any,
) -> int:
    return startup_core.run_telemetry_summary_command(
        cfg,
        config_path=config_path,
        output_format=output_format,
        output_path=output_path,
        run_telemetry_summary_command_fn=app_module.app_cli_commands.run_telemetry_summary_command,
        telemetry_output_path_fn=app_module.app_telemetry.telemetry_output_path_for_config,
        summarize_telemetry_fn=app_module.telemetry_summary.summarize_telemetry_file,
        render_text_summary_fn=app_module.telemetry_summary.render_text_summary,
        exit_success=app_module.EXIT_SUCCESS,
        exit_usage_error=app_module.EXIT_USAGE_ERROR,
    )


def run_icf_formatter_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    interactive_core.run_icf_formatter(
        cfg,
        run_format_icf_command_fn=app_module.run_format_icf_command,
        pause_fn=app_module.pause,
    )


def show_config_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    interactive_core.show_config(
        cfg,
        show_config_fn=app_module.app_graphics.show_config,
        get_graphics_rules_path_fn=app_module.get_graphics_rules_path,
        load_graphics_rules_fn=app_module.load_graphics_rules,
        graphics_rule_config_line_fn=app_module._graphics_rule_config_line,
    )


def print_menu_from_app(
    title: str,
    options: Sequence[Any],
    *,
    intro: str | None,
    note: str | None,
    app_module: Any,
) -> None:
    interactive_core.print_menu(
        title,
        options,
        intro=intro,
        note=note,
        print_menu_owner_fn=app_module.app_support.print_menu,
        print_fn=print,
    )


def summarize_targets_from_app(cfg: ConfigDict, *, app_module: Any) -> str:
    return interactive_core.summarize_targets(
        cfg,
        summarize_targets_fn=app_module.app_support.summarize_targets,
        get_analyzed_targets_fn=app_module._get_analyzed_targets,
    )


def show_help_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    interactive_core.show_help(
        cfg,
        show_help_fn=app_module.app_support.show_help,
        clear_screen_fn=app_module.clear_screen,
        get_analyzed_targets_fn=app_module._get_analyzed_targets,
        summarize_targets_fn=app_module._summarize_targets,
        print_fn=print,
        pause_fn=app_module.pause,
    )


def get_help_text_from_app(cfg: ConfigDict, *, app_module: Any) -> str:
    return interactive_core.get_help_text(
        cfg,
        get_help_text_fn=app_module.app_support.get_help_text,
        get_analyzed_targets_fn=app_module._get_analyzed_targets,
        summarize_targets_fn=app_module._summarize_targets,
    )


def discover_graphics_rule_selector_options_from_app(
    cfg: ConfigDict | None,
    *,
    selector_field: str,
    module_kind: str,
    app_module: Any,
) -> list[dict[str, Any]]:
    return startup_core.discover_graphics_rule_selector_options(
        cfg,
        selector_field=selector_field,
        module_kind=module_kind,
        discover_graphics_rule_selector_options_fn=app_module.app_graphics.discover_graphics_rule_selector_options,
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
    return startup_core.pick_or_prompt_graphics_rule_selector_value(
        selector_field,
        module_kind,
        cfg=cfg,
        pick_or_prompt_graphics_rule_selector_value_fn=app_module.app_graphics.pick_or_prompt_graphics_rule_selector_value,
        discover_graphics_rule_selector_options_fn=app_module._discover_graphics_rule_selector_options,
    )


def annotate_graphics_entries_with_structure_paths_from_app(
    entries: list[dict[str, Any]],
    project_bp: BasePicture,
    graph: ProjectGraph,
    *,
    app_module: Any,
) -> list[dict[str, Any]]:
    return startup_core.annotate_graphics_entries_with_structure_paths(
        entries,
        project_bp,
        graph,
        annotate_graphics_entries_with_structure_paths_fn=app_module.app_graphics.annotate_graphics_entries_with_structure_paths,
        classify_documentation_structure_fn=app_module.classify_documentation_structure,
        discover_documentation_unit_candidates_fn=app_module.discover_documentation_unit_candidates,
    )


def graphics_rules_menu_from_app(cfg: ConfigDict | None, *, app_module: Any) -> None:
    startup_core.graphics_rules_menu(
        cfg,
        graphics_rules_menu_fn=app_module.app_graphics.graphics_rules_menu,
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
    )


def prompt_graphics_rule_definition_with_config_from_app(
    cfg: ConfigDict | None,
    *,
    app_module: Any,
) -> dict[str, Any] | None:
    return startup_core.prompt_graphics_rule_definition_with_config(
        cfg,
        prompt_graphics_rule_definition_with_config_fn=app_module.app_graphics.prompt_graphics_rule_definition_with_config,
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
    return startup_core.collect_graphics_layout_entries_for_target(
        target_name,
        project_bp,
        graph,
        collect_graphics_layout_entries_for_target_fn=app_module.app_graphics.collect_graphics_layout_entries_for_target,
        annotate_graphics_entries_with_structure_paths_fn=app_module._annotate_graphics_entries_with_structure_paths,
    )


def run_graphics_rules_validation_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    startup_core.run_graphics_rules_validation(
        cfg,
        run_graphics_rules_validation_fn=app_module.app_graphics.run_graphics_rules_validation,
        get_graphics_rules_path_fn=app_module.get_graphics_rules_path,
        load_graphics_rules_fn=app_module.load_graphics_rules,
        iter_loaded_projects_fn=app_module._iter_loaded_projects,
        collect_graphics_layout_entries_for_target_fn=app_module._collect_graphics_layout_entries_for_target,
        pause_fn=app_module.pause,
    )


def get_documentation_unit_selection_from_app(*, app_module: Any) -> dict[str, Any]:
    return startup_core.get_documentation_unit_selection(
        get_documentation_unit_selection_fn=app_module.app_docs.get_documentation_unit_selection,
    )


def preview_documentation_unit_candidates_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    startup_core.preview_documentation_unit_candidates(
        cfg,
        preview_documentation_unit_candidates_fn=app_module.app_docs.preview_documentation_unit_candidates,
        iter_loaded_projects_fn=app_module._iter_loaded_projects,
        pause_fn=app_module.pause,
    )


def configure_documentation_scope_by_moduletype_from_app(*, app_module: Any) -> bool:
    return startup_core.configure_documentation_scope_by_moduletype(
        configure_documentation_scope_by_moduletype_fn=app_module.app_docs.configure_documentation_scope_by_moduletype,
        split_csv_values_fn=app_module._split_csv_values,
        pause_fn=app_module.pause,
    )


def configure_documentation_scope_by_instance_path_from_app(*, app_module: Any) -> bool:
    return startup_core.configure_documentation_scope_by_instance_path(
        configure_documentation_scope_by_instance_path_fn=app_module.app_docs.configure_documentation_scope_by_instance_path,
        split_csv_values_fn=app_module._split_csv_values,
        pause_fn=app_module.pause,
    )


def reset_documentation_scope_from_app(*, app_module: Any) -> bool:
    return startup_core.reset_documentation_scope(
        reset_documentation_scope_fn=app_module.app_docs.reset_documentation_scope,
        pause_fn=app_module.pause,
    )


def run_generate_documentation_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    startup_core.run_generate_documentation(
        cfg,
        run_generate_documentation_fn=app_module.app_docs.run_generate_documentation,
        iter_loaded_projects_fn=app_module._iter_loaded_projects,
        prompt_fn=app_module.prompt,
        pause_fn=app_module.pause,
    )


def documentation_menu_from_app(cfg: ConfigDict, *, app_module: Any) -> bool:
    return startup_core.documentation_menu(
        cfg,
        documentation_menu_fn=app_module.app_docs.documentation_menu,
        clear_screen_fn=app_module.clear_screen,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        quit_app_fn=app_module.quit_app,
        pause_fn=app_module.pause,
        split_csv_values_fn=app_module._split_csv_values,
        iter_loaded_projects_fn=app_module._iter_loaded_projects,
        prompt_fn=app_module.prompt,
    )


def dump_menu_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    interactive_core.dump_menu(
        cfg,
        dump_menu_fn=app_module.app_menus.dump_menu,
        clear_screen_fn=app_module.clear_screen,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        quit_app_fn=app_module.quit_app,
        confirm_fn=app_module.confirm,
        iter_loaded_projects_fn=app_module._iter_loaded_projects,
        target_is_library_fn=app_module._target_is_library,
        analyze_variables_fn=app_module.analyze_variables,
    )


def config_menu_from_app(cfg: ConfigDict, *, app_module: Any) -> bool:
    return interactive_core.config_menu(
        cfg,
        config_menu_fn=app_module.app_menus.config_menu,
        config_path=app_module.CONFIG_PATH,
        clear_screen_fn=app_module.clear_screen,
        show_config_fn=app_module.show_config,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        prompt_fn=app_module.prompt,
        pause_fn=app_module.pause,
        confirm_fn=app_module.confirm,
        target_exists_fn=app_module.target_exists,
        save_config_fn=app_module.save_config,
        apply_debug_fn=app_module.apply_debug,
        graphics_rules_menu_fn=app_module.graphics_rules_menu,
        quit_app_fn=app_module.quit_app,
    )


def tools_menu_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    interactive_core.tools_menu(
        cfg,
        tools_menu_fn=app_module.app_menus.tools_menu,
        clear_screen_fn=app_module.clear_screen,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        quit_app_fn=app_module.quit_app,
        self_check_fn=app_module.self_check,
        pause_fn=app_module.pause,
        require_targets_for_menu_action_fn=app_module._require_targets_for_menu_action,
        dump_menu_fn=app_module.dump_menu,
        run_source_diff_report_fn=app_module.run_source_diff_report,
        confirm_fn=app_module.confirm,
        force_refresh_ast_fn=app_module.refresh_analysis_caches,
    )


def main_from_app(argv: list[str] | None, *, app_module: Any) -> int:
    return startup_core.main(
        argv,
        run_cli_fn=app_module.run_cli,
        build_cli_parser_fn=app_module.build_cli_parser,
        load_config_fn=app_module.load_config,
        config_path=app_module.CONFIG_PATH,
        apply_debug_fn=app_module.apply_debug,
        resolve_interactive_ui_mode_fn=app_module.resolve_interactive_ui_mode,
        set_interactive_ui_mode_fn=app_module.set_interactive_ui_mode,
        reset_interactive_ui_mode_fn=app_module.reset_interactive_ui_mode,
        emit_output_fn=app_module.emit_output,
        pause_fn=app_module.pause,
        self_check_fn=app_module.self_check,
        confirm_fn=app_module.confirm,
        has_analyzed_targets_fn=app_module._has_analyzed_targets,
        ensure_ast_cache_fn=app_module.ensure_ast_cache,
        run_main_loop_fn=app_module.run_interactive_session,
        clear_screen_fn=app_module.clear_screen,
        print_menu_fn=app_module._print_menu,
        choose_menu_option_fn=app_module.choose_menu_option,
        menu_option_factory=app_module._menu_option,
        summarize_targets_fn=app_module._summarize_targets,
        require_targets_for_menu_action_fn=app_module._require_targets_for_menu_action,
        analysis_menu_fn=app_module.analysis_menu,
        documentation_menu_fn=app_module.documentation_menu,
        config_menu_fn=app_module.config_menu,
        tools_menu_fn=app_module.tools_menu,
        show_help_fn=app_module.show_help,
        save_config_fn=app_module.save_config,
        quit_app_fn=app_module.quit_app,
        quit_app_error=app_module.QuitAppError,
    )
