# pyright: reportUnusedFunction=false
"""Analysis actions for the application layer.

Direct replacement for the old ``_app_facade_analysis`` helpers.  Each
function wires the owning implementation (:mod:`sattlint.app_analysis`)
to the application-level defaults (interaction, pause, and project
loading), producing a callable surface that is independent of any
specific terminal.
"""

from __future__ import annotations

from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from .. import analysis_catalog as analysis_catalog_module
from .. import app_analysis as app_analysis_module
from ..analyzers.shadowing import analyze_shadowing
from ..analyzers.variables import IssueKind, analyze_variables, filter_variable_report
from ..app_base import pause, prompt
from ..config_types import ConfigDict
from ..models.project_graph import ProjectGraph
from . import project as project_application
from ._interaction import menu_interaction


def _get_enabled_analyzers() -> list[Any]:
    return cast(list[Any], analysis_catalog_module.get_default_cli_analyzers())


get_enabled_analyzers = _get_enabled_analyzers


def _get_selectable_analyzers() -> list[Any]:
    return cast(list[Any], analysis_catalog_module.get_selectable_analyzers())


get_selectable_analyzers = _get_selectable_analyzers


def run_variable_analysis(cfg: ConfigDict, kinds: set[IssueKind] | None) -> None:
    app_analysis_module.run_variable_analysis(
        cfg,
        kinds,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        target_is_library_fn=project_application.target_is_library,
        analyze_variables_fn=analyze_variables,
        analyze_shadowing_fn=analyze_shadowing,
        filter_variable_report_fn=filter_variable_report,
        pause_fn=pause,
    )


def run_datatype_usage_analysis(cfg: ConfigDict) -> None:
    app_analysis_module.run_datatype_usage_analysis(
        cfg,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        pause_fn=pause,
        interaction=menu_interaction(),
    )


def run_module_duplicates_analysis(cfg: ConfigDict) -> None:
    app_analysis_module.run_module_duplicates_analysis(
        cfg,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        pause_fn=pause,
        interaction=menu_interaction(),
    )


def run_module_find_by_name(cfg: ConfigDict) -> None:
    app_analysis_module.run_module_find_by_name(
        cfg,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        pause_fn=pause,
        interaction=menu_interaction(),
    )


def run_module_tree_debug(cfg: ConfigDict) -> None:
    app_analysis_module.run_module_tree_debug(
        cfg,
        prompt_fn=prompt,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        pause_fn=pause,
    )


def run_module_localvar_analysis(cfg: ConfigDict) -> None:
    app_analysis_module.run_module_localvar_analysis(
        cfg,
        load_project_fn=project_application.load_project,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        pause_fn=pause,
        interaction=menu_interaction(),
    )


def run_icf_validation(cfg: ConfigDict) -> None:
    def _load_program_ast(local_cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
        return project_application.load_program_ast(local_cfg, program_name, force_dependency_resolution=True)

    app_analysis_module.run_icf_validation(
        cfg,
        configured_icf_files_fn=project_application.configured_icf_files,
        load_program_ast_fn=_load_program_ast,
        validate_icf_entries_against_program_fn=app_analysis_module.validate_icf_entries_against_program,
        pause_fn=pause,
    )


def run_mms_interface_analysis(cfg: ConfigDict) -> None:
    app_analysis_module.run_mms_interface_analysis(
        cfg,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        pause_fn=pause,
    )


def run_debug_variable_usage(cfg: ConfigDict) -> None:
    app_analysis_module.run_debug_variable_usage(
        cfg,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        pause_fn=pause,
        interaction=menu_interaction(),
    )


def run_comment_code_analysis(cfg: ConfigDict) -> None:
    app_analysis_module.run_comment_code_analysis(
        cfg,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        source_paths_for_current_target_fn=project_application.source_paths_for_current_target,
        pause_fn=pause,
    )


def run_advanced_datatype_analysis(cfg: ConfigDict) -> None:
    app_analysis_module.run_advanced_datatype_analysis(
        cfg,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        pause_fn=pause,
        interaction=menu_interaction(),
    )


def run_checks(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    selected_issue_kinds: set[str] | frozenset[str] | None = None,
) -> None:
    app_analysis_module.run_checks(
        cfg,
        selected_keys,
        selected_issue_kinds=selected_issue_kinds,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        get_enabled_analyzers_fn=_get_selectable_analyzers if selected_keys else _get_enabled_analyzers,
        target_is_library_fn=project_application.target_is_library,
        pause_fn=pause,
    )
