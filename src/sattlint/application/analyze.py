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

from ..analyzers import catalog as analysis_catalog_module
from ..config.types import ConfigDict
from . import checks as checks_module
from . import project as project_application


def _get_enabled_analyzers() -> list[Any]:
    return cast(list[Any], analysis_catalog_module.get_default_cli_analyzers())


get_enabled_analyzers = _get_enabled_analyzers


def _get_selectable_analyzers() -> list[Any]:
    return cast(list[Any], analysis_catalog_module.get_selectable_analyzers())


get_selectable_analyzers = _get_selectable_analyzers


def _selected_analyzers_fn(selected_keys: list[str] | None) -> Callable[[], list[Any]]:
    return _get_selectable_analyzers if selected_keys else _get_enabled_analyzers


def _invoke_checks[ResultT](
    checks_fn: Callable[..., ResultT],
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    **options: object,
) -> ResultT:
    """Call one ``checks`` entry point with the shared project-loading defaults."""
    return checks_fn(
        cfg,
        selected_keys,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        get_enabled_analyzers_fn=_selected_analyzers_fn(selected_keys),
        target_is_library_fn=project_application.target_is_library,
        **options,
    )


def run_checks(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    use_cache: bool = True,
) -> None:
    _invoke_checks(checks_module.run_checks, cfg, selected_keys, use_cache=use_cache)


def run_checks_result(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    use_cache: bool = True,
) -> checks_module.ChecksRunResult:
    return _invoke_checks(checks_module.run_checks_result, cfg, selected_keys, use_cache=use_cache)


def collect_checks_result(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    use_cache: bool = True,
    persist_run: bool = True,
) -> checks_module.ChecksRunResult:
    """Run checks without emitting the human-readable report to stdout."""
    return _invoke_checks(
        checks_module.collect_run_checks_result,
        cfg,
        selected_keys,
        use_cache=use_cache,
        persist_run=persist_run,
    )
