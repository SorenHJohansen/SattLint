from __future__ import annotations

from typing import Any

ConfigDict = dict[str, Any]


def dump_menu_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    app_module.app_menus.dump_menu(
        cfg,
        clear_screen_fn=app_module.clear_screen,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        quit_app_fn=app_module.quit_app,
        iter_loaded_projects_fn=app_module._iter_loaded_projects,
        target_is_library_fn=app_module._target_is_library,
        analyze_variables_fn=app_module.analyze_variables,
        interaction=app_module.build_menu_interaction(),
    )


def config_menu_from_app(cfg: ConfigDict, *, app_module: Any) -> bool:
    return app_module.app_menus.config_menu(
        cfg,
        config_path=app_module.CONFIG_PATH,
        clear_screen_fn=app_module.clear_screen,
        show_config_fn=app_module.show_config,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        target_exists_fn=app_module.target_exists,
        save_config_fn=app_module.save_config,
        apply_debug_fn=app_module.apply_debug,
        graphics_rules_menu_fn=app_module.graphics_rules_menu,
        quit_app_fn=app_module.quit_app,
        interaction=app_module.build_menu_interaction(),
    )


def tools_menu_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    app_module.app_menus.tools_menu(
        cfg,
        clear_screen_fn=app_module.clear_screen,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        quit_app_fn=app_module.quit_app,
        self_check_fn=app_module.self_check,
        require_targets_for_menu_action_fn=app_module._require_targets_for_menu_action,
        dump_menu_fn=app_module.dump_menu,
        run_source_diff_report_fn=app_module.run_source_diff_report,
        force_refresh_ast_fn=app_module.force_refresh_ast,
        interaction=app_module.build_menu_interaction(),
    )
