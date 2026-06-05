from __future__ import annotations

from typing import Any

from . import _app_analysis_menus as analysis_menus_module

ConfigDict = dict[str, Any]


def _emit_output_fn(app_module: Any) -> Any:
    return app_module.app_analysis.emit_output


def variable_usage_submenu_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    analysis_menus_module.variable_usage_submenu(
        cfg,
        clear_screen_fn=app_module.clear_screen,
        quit_app_fn=app_module.quit_app,
        run_variable_analysis_fn=app_module.run_variable_analysis,
        run_datatype_usage_analysis_fn=app_module.run_datatype_usage_analysis,
        run_debug_variable_usage_fn=app_module.run_debug_variable_usage,
        run_module_localvar_analysis_fn=app_module.run_module_localvar_analysis,
        pause_fn=app_module.pause,
        emit_output_fn=_emit_output_fn(app_module),
        interaction=app_module.build_menu_interaction(),
    )


def module_analysis_submenu_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    analysis_menus_module.module_analysis_submenu(
        cfg,
        clear_screen_fn=app_module.clear_screen,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        quit_app_fn=app_module.quit_app,
        run_module_duplicates_analysis_fn=app_module.run_module_duplicates_analysis,
        run_module_find_by_name_fn=app_module.run_module_find_by_name,
        run_module_tree_debug_fn=app_module.run_module_tree_debug,
        run_graphics_rules_validation_fn=app_module.run_graphics_rules_validation,
        pause_fn=app_module.pause,
        emit_output_fn=_emit_output_fn(app_module),
        interaction=app_module.build_menu_interaction(),
    )


def interface_communication_submenu_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    analysis_menus_module.interface_communication_submenu(
        cfg,
        clear_screen_fn=app_module.clear_screen,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        quit_app_fn=app_module.quit_app,
        run_mms_interface_analysis_fn=app_module.run_mms_interface_analysis,
        run_icf_validation_fn=app_module.run_icf_validation,
        run_icf_formatter_fn=app_module.run_icf_formatter,
        pause_fn=app_module.pause,
        emit_output_fn=_emit_output_fn(app_module),
        interaction=app_module.build_menu_interaction(),
    )


def code_quality_submenu_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    analysis_menus_module.code_quality_submenu(
        cfg,
        clear_screen_fn=app_module.clear_screen,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        quit_app_fn=app_module.quit_app,
        run_comment_code_analysis_fn=app_module.run_comment_code_analysis,
        pause_fn=app_module.pause,
        emit_output_fn=_emit_output_fn(app_module),
        interaction=app_module.build_menu_interaction(),
    )


def analyzer_catalog_menu_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    analysis_menus_module.analyzer_catalog_menu(
        cfg,
        clear_screen_fn=app_module.clear_screen,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        quit_app_fn=app_module.quit_app,
        get_enabled_analyzers_fn=app_module._get_enabled_analyzers,
        run_checks_fn=app_module._run_checks,
        pause_fn=app_module.pause,
        emit_output_fn=_emit_output_fn(app_module),
        interaction=app_module.build_menu_interaction(),
    )


def advanced_analysis_menu_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    analysis_menus_module.advanced_analysis_menu(
        cfg,
        clear_screen_fn=app_module.clear_screen,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        quit_app_fn=app_module.quit_app,
        run_datatype_usage_analysis_fn=app_module.run_datatype_usage_analysis,
        run_debug_variable_usage_fn=app_module.run_debug_variable_usage,
        run_module_localvar_analysis_fn=app_module.run_module_localvar_analysis,
        pause_fn=app_module.pause,
        emit_output_fn=_emit_output_fn(app_module),
        interaction=app_module.build_menu_interaction(),
    )


def analysis_menu_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    analysis_menus_module.analysis_menu(
        cfg,
        clear_screen_fn=app_module.clear_screen,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        quit_app_fn=app_module.quit_app,
        run_checks_fn=app_module._run_checks,
        variable_usage_submenu_fn=app_module.variable_usage_submenu,
        module_analysis_submenu_fn=app_module.module_analysis_submenu,
        interface_communication_submenu_fn=app_module.interface_communication_submenu,
        code_quality_submenu_fn=app_module.code_quality_submenu,
        analyzer_catalog_menu_fn=app_module.analyzer_catalog_menu,
        advanced_analysis_menu_fn=app_module.advanced_analysis_menu,
        summarize_targets_fn=app_module._summarize_targets,
        pause_fn=app_module.pause,
        emit_output_fn=_emit_output_fn(app_module),
        interaction=app_module.build_menu_interaction(),
    )
