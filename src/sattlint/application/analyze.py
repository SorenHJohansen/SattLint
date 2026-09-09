# pyright: reportUnusedFunction=false
"""Analysis actions for the application layer.

Direct replacement for the old ``_app_facade_analysis`` helpers.  Each
function wires the owning implementation (:mod:`sattlint.application.commands`,
:mod:`sattlint.application.checks`) to the project loading defaults, producing
a callable surface that is independent of any specific terminal.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from ..analyzers import catalog as analysis_catalog_module
from ..analyzers import icf as icf_module
from ..analyzers.shadowing import analyze_shadowing
from ..analyzers.variables import IssueKind, analyze_variables, filter_variable_report
from ..config.types import ConfigDict
from ..models.project_graph import ProjectGraph
from ..project import support as support_module
from . import checks as checks_module
from . import menu_commands as menu_commands_module
from . import project as project_application


def _get_enabled_analyzers() -> list[Any]:
    return cast(list[Any], analysis_catalog_module.get_default_cli_analyzers())


get_enabled_analyzers = _get_enabled_analyzers


def _get_selectable_analyzers() -> list[Any]:
    return cast(list[Any], analysis_catalog_module.get_selectable_analyzers())


get_selectable_analyzers = _get_selectable_analyzers


def run_variable_analysis(cfg: ConfigDict, kinds: set[IssueKind] | None) -> None:
    menu_commands_module.run_variable_analysis(
        cfg,
        kinds,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        target_is_library_fn=project_application.target_is_library,
        analyze_variables_fn=analyze_variables,
        analyze_shadowing_fn=analyze_shadowing,
        filter_variable_report_fn=filter_variable_report,
    )


def run_icf_validation(cfg: ConfigDict) -> None:
    def _load_program_ast(local_cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
        return project_application.load_program_ast(local_cfg, program_name)

    menu_commands_module.run_icf_validation(
        cfg,
        configured_icf_files_fn=support_module.configured_icf_files,
        load_program_ast_fn=_load_program_ast,
        validate_icf_entries_against_program_fn=icf_module.validate_icf_entries_against_program,
    )


def run_mms_interface_analysis(cfg: ConfigDict) -> None:
    menu_commands_module.run_mms_interface_analysis(
        cfg,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
    )


def run_comment_code_analysis(cfg: ConfigDict) -> None:
    menu_commands_module.run_comment_code_analysis(
        cfg,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        source_paths_for_current_target_fn=project_application.source_paths_for_current_target,
    )


def run_checks(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    selected_issue_kinds: set[str] | frozenset[str] | None = None,
    use_cache: bool = True,
) -> None:
    checks_module.run_checks(
        cfg,
        selected_keys,
        selected_issue_kinds=selected_issue_kinds,
        use_cache=use_cache,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        get_enabled_analyzers_fn=_get_selectable_analyzers if selected_keys else _get_enabled_analyzers,
        target_is_library_fn=project_application.target_is_library,
    )


def run_checks_result(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    selected_issue_kinds: set[str] | frozenset[str] | None = None,
    use_cache: bool = True,
) -> checks_module.ChecksRunResult:
    return checks_module.run_checks_result(
        cfg,
        selected_keys,
        selected_issue_kinds=selected_issue_kinds,
        use_cache=use_cache,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        get_enabled_analyzers_fn=_get_selectable_analyzers if selected_keys else _get_enabled_analyzers,
        target_is_library_fn=project_application.target_is_library,
    )


def run_checks_menu(cfg: ConfigDict, *, run_checks_fn: Callable[[ConfigDict, list[str] | None], None]) -> None:
    checks_module.run_checks_menu(cfg, run_checks_fn=run_checks_fn)
