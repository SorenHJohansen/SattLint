from __future__ import annotations

from typing import Any

from .config_types import ConfigDict


def get_documentation_unit_selection_from_app(*, app_module: Any) -> dict[str, Any]:
    return app_module.app_docs.get_documentation_unit_selection()


def preview_documentation_unit_candidates_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    app_module.app_docs.preview_documentation_unit_candidates(
        cfg,
        iter_loaded_projects_fn=app_module._iter_loaded_projects,
        pause_fn=app_module.pause,
    )


def configure_documentation_scope_by_moduletype_from_app(*, app_module: Any) -> bool:
    return app_module.app_docs.configure_documentation_scope_by_moduletype(
        split_csv_values_fn=app_module._split_csv_values,
        interaction=app_module.build_menu_interaction(),
    )


def configure_documentation_scope_by_instance_path_from_app(*, app_module: Any) -> bool:
    return app_module.app_docs.configure_documentation_scope_by_instance_path(
        split_csv_values_fn=app_module._split_csv_values,
        interaction=app_module.build_menu_interaction(),
    )


def reset_documentation_scope_from_app(*, app_module: Any) -> bool:
    return app_module.app_docs.reset_documentation_scope(interaction=app_module.build_menu_interaction())


def run_generate_documentation_from_app(cfg: ConfigDict, *, app_module: Any) -> None:
    app_module.app_docs.run_generate_documentation(
        cfg,
        iter_loaded_projects_fn=app_module._iter_loaded_projects,
        interaction=app_module.build_menu_interaction(),
    )


def documentation_menu_from_app(cfg: ConfigDict, *, app_module: Any) -> bool:
    return app_module.app_docs.documentation_menu(
        cfg,
        clear_screen_fn=app_module.clear_screen,
        print_menu_fn=app_module._print_menu,
        menu_option_factory=app_module._menu_option,
        quit_app_fn=app_module.quit_app,
        split_csv_values_fn=app_module._split_csv_values,
        iter_loaded_projects_fn=app_module._iter_loaded_projects,
        interaction=app_module.build_menu_interaction(),
    )
