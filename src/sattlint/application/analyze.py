# pyright: reportUnusedFunction=false
"""Analysis actions for the application layer.

Direct replacement for the old ``_app_facade_analysis`` helpers.  Each
function wires the owning implementation (:mod:`sattlint.application.commands`,
:mod:`sattlint.application.checks`) to the project loading defaults, producing
a callable surface that is independent of any specific terminal.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, cast

from ..analyzers import catalog as analysis_catalog_module
from ..config.types import ConfigDict
from ..core.progress import ProgressCallback
from . import checks as checks_module
from . import project as project_application


def _get_selectable_analyzers() -> list[Any]:
    return cast(list[Any], analysis_catalog_module.get_selectable_analyzers())


get_selectable_analyzers = _get_selectable_analyzers


def selectable_analyzer_keys() -> tuple[str, ...]:
    return analysis_catalog_module.get_selectable_analyzer_keys()


def no_analyzer_selection_message(available: Iterable[str] | None = None) -> str:
    """The one guidance text for a run that named no analyzer.

    ``available`` lets a caller that already offers a narrower list (the Textual
    Analyze view) name the analyzers it actually shows.
    """
    keys = ", ".join(sorted(available) if available is not None else selectable_analyzer_keys())
    return (
        "No analyzers selected. Name at least one with --analyzer, or list the keys "
        f"under 'analyzers' in the project file. Selectable analyzers: {keys}"
    )


def run_checks(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    use_cache: bool = True,
    refresh_ast: bool = False,
    project_path: str = "",
    jobs: int | None = None,
    emit_output: Callable[[str], None] | None = None,
) -> None:
    checks_module.run_checks(
        cfg,
        selected_keys,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        get_enabled_analyzers_fn=_get_selectable_analyzers,
        target_is_library_fn=project_application.target_is_library,
        use_cache=use_cache,
        refresh_ast=refresh_ast,
        project_path=project_path,
        jobs=jobs,
        emit_output=emit_output,
    )


def run_checks_result(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    use_cache: bool = True,
    refresh_ast: bool = False,
    project_path: str = "",
    jobs: int | None = None,
    emit_output: Callable[[str], None] | None = None,
) -> checks_module.ChecksRunResult:
    return checks_module.run_checks_result(
        cfg,
        selected_keys,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        get_enabled_analyzers_fn=_get_selectable_analyzers,
        target_is_library_fn=project_application.target_is_library,
        use_cache=use_cache,
        refresh_ast=refresh_ast,
        project_path=project_path,
        jobs=jobs,
        emit_output=emit_output,
    )


def collect_checks_result(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    use_cache: bool = True,
    refresh_ast: bool = False,
    persist_run: bool = True,
    project_path: str = "",
    jobs: int | None = None,
    emit_output: Callable[[str], None] | None = None,
    progress: ProgressCallback | None = None,
) -> checks_module.ChecksRunResult:
    """Run checks without emitting the human-readable report to stdout."""
    return checks_module.collect_run_checks_result(
        cfg,
        selected_keys,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        get_enabled_analyzers_fn=_get_selectable_analyzers,
        target_is_library_fn=project_application.target_is_library,
        use_cache=use_cache,
        refresh_ast=refresh_ast,
        persist_run=persist_run,
        project_path=project_path,
        jobs=jobs,
        emit_output=emit_output,
        progress=progress,
    )
