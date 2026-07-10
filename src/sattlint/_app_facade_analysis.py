from __future__ import annotations

from typing import Any, cast

from .analyzers.shadowing import analyze_shadowing
from .analyzers.variables import IssueKind, analyze_variables, filter_variable_report


def _app() -> Any:
    from . import app as app_module

    return app_module


def run_variable_analysis(cfg: dict[str, object], kinds: set[IssueKind] | None) -> None:
    app = _app()
    app.app_analysis.run_variable_analysis(
        cfg,
        kinds,
        iter_loaded_projects_fn=app._iter_loaded_projects,
        target_is_library_fn=app._target_is_library,
        analyze_variables_fn=analyze_variables,
        analyze_shadowing_fn=analyze_shadowing,
        filter_variable_report_fn=filter_variable_report,
        print_validation_warnings_fn=app._print_validation_warnings,
        target_validation_warnings_fn=app._target_validation_warnings,
        pause_fn=app.pause,
    )


def run_datatype_usage_analysis(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis.run_datatype_usage_analysis(
        cfg,
        iter_loaded_projects_fn=app._iter_loaded_projects,
        pause_fn=app.pause,
        interaction=app.build_menu_interaction(),
    )


def variable_usage_submenu(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis_from_app_module.variable_usage_submenu_from_app(cfg, app_module=app)


def module_analysis_submenu(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis_from_app_module.module_analysis_submenu_from_app(cfg, app_module=app)


def interface_communication_submenu(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis_from_app_module.interface_communication_submenu_from_app(cfg, app_module=app)


def code_quality_submenu(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis_from_app_module.code_quality_submenu_from_app(cfg, app_module=app)


def analyzer_catalog_menu(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis_from_app_module.analyzer_catalog_menu_from_app(cfg, app_module=app)


def advanced_analysis_menu(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis_from_app_module.advanced_analysis_menu_from_app(cfg, app_module=app)


def analysis_menu(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis_from_app_module.analysis_menu_from_app(cfg, app_module=app)


def run_module_duplicates_analysis(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis.run_module_duplicates_analysis(
        cfg,
        iter_loaded_projects_fn=app._iter_loaded_projects,
        pause_fn=app.pause,
        interaction=app.build_menu_interaction(),
    )


def run_module_find_by_name(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis.run_module_find_by_name(
        cfg,
        iter_loaded_projects_fn=app._iter_loaded_projects,
        pause_fn=app.pause,
        interaction=app.build_menu_interaction(),
    )


def run_module_tree_debug(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis.run_module_tree_debug(
        cfg,
        prompt_fn=app.prompt,
        iter_loaded_projects_fn=app._iter_loaded_projects,
        pause_fn=app.pause,
    )


def run_analysis_menu(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis.run_analysis_menu(cfg, analysis_menu_fn=app.analysis_menu)


def variable_analysis_menu(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis.variable_analysis_menu(cfg, analysis_menu_fn=app.analysis_menu)


def run_module_localvar_analysis(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis.run_module_localvar_analysis(
        cfg,
        load_project_fn=app.load_project,
        iter_loaded_projects_fn=app._iter_loaded_projects,
        pause_fn=app.pause,
        interaction=app.build_menu_interaction(),
    )


def _get_enabled_analyzers() -> list[Any]:
    app = _app()
    return cast(list[Any], app.get_default_cli_analyzers())


def _get_selectable_analyzers() -> list[Any]:
    app = _app()
    return cast(list[Any], app.get_selectable_analyzers())


def _run_checks(
    cfg: dict[str, object],
    selected_keys: list[str] | None,
    *,
    selected_issue_kinds: set[str] | frozenset[str] | None = None,
) -> None:
    app = _app()
    app.app_analysis.run_checks(
        cfg,
        selected_keys,
        selected_issue_kinds=selected_issue_kinds,
        iter_loaded_projects_fn=app._iter_loaded_projects,
        get_enabled_analyzers_fn=app._get_selectable_analyzers if selected_keys else app._get_enabled_analyzers,
        target_is_library_fn=app._target_is_library,
        pause_fn=app.pause,
    )


def run_checks_menu(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis.run_checks_menu(cfg, run_checks_fn=app._run_checks)


def run_mms_interface_analysis(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis.run_mms_interface_analysis(
        cfg,
        iter_loaded_projects_fn=app._iter_loaded_projects,
        pause_fn=app.pause,
    )


def run_icf_validation(cfg: dict[str, object]) -> None:
    app = _app()

    def _load_program_ast(local_cfg: dict[str, object], program_name: str):
        return app.load_program_ast(local_cfg, program_name, force_dependency_resolution=True)

    app.app_analysis.run_icf_validation(
        cfg,
        configured_icf_files_fn=app._configured_icf_files,
        load_program_ast_fn=_load_program_ast,
        validate_icf_entries_against_program_fn=app.validate_icf_entries_against_program,
        pause_fn=app.pause,
    )


def run_debug_variable_usage(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis.run_debug_variable_usage(
        cfg,
        iter_loaded_projects_fn=app._iter_loaded_projects,
        pause_fn=app.pause,
        interaction=app.build_menu_interaction(),
    )


def run_comment_code_analysis(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis.run_comment_code_analysis(
        cfg,
        iter_loaded_projects_fn=app._iter_loaded_projects,
        source_paths_for_current_target_fn=app._source_paths_for_current_target,
        pause_fn=app.pause,
    )


def run_advanced_datatype_analysis(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_analysis.run_advanced_datatype_analysis(
        cfg,
        iter_loaded_projects_fn=app._iter_loaded_projects,
        pause_fn=app.pause,
        interaction=app.build_menu_interaction(),
    )


def dump_menu(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_menus_from_app_module.dump_menu_from_app(cfg, app_module=app)


def run_source_diff_report(cfg: dict[str, object], *, _pause_fn=None) -> None:
    app = _app()
    app.app_source_diff_module.run_source_diff_report(
        cfg,
        iter_loaded_projects_fn=app._iter_loaded_projects,
        source_paths_for_current_target_fn=app._source_paths_for_current_target,
        live_status_line_factory=app.console_module.live_status_line,
        build_pair_report_fn=app.source_diff_report_module.build_pair_report,
        render_markdown_fn=app.source_diff_report_module.render_markdown,
        emit_output_fn=app.emit_output,
        pause_fn=_pause_fn if _pause_fn is not None else app.pause,
    )


def config_menu(cfg: dict[str, object]) -> bool:
    app = _app()
    return app.app_menus_from_app_module.config_menu_from_app(cfg, app_module=app)


def tools_menu(cfg: dict[str, object]) -> None:
    app = _app()
    app.app_menus_from_app_module.tools_menu_from_app(cfg, app_module=app)
