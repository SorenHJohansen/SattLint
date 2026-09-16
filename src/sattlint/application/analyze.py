# pyright: reportUnusedFunction=false
"""Analysis actions for the application layer.

Direct replacement for the old ``_app_facade_analysis`` helpers.  Each
function wires the owning implementation (:mod:`sattlint.application.commands`,
:mod:`sattlint.application.checks`) to the project loading defaults, producing
a callable surface that is independent of any specific terminal.
"""

from __future__ import annotations

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


def run_checks(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    use_cache: bool = True,
) -> None:
    checks_module.run_checks(
        cfg,
        selected_keys,
        use_cache=use_cache,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        get_enabled_analyzers_fn=_get_selectable_analyzers if selected_keys else _get_enabled_analyzers,
        target_is_library_fn=project_application.target_is_library,
    )


def run_checks_result(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    use_cache: bool = True,
) -> checks_module.ChecksRunResult:
    return checks_module.run_checks_result(
        cfg,
        selected_keys,
        use_cache=use_cache,
        iter_loaded_projects_fn=project_application.iter_loaded_projects,
        get_enabled_analyzers_fn=_get_selectable_analyzers if selected_keys else _get_enabled_analyzers,
        target_is_library_fn=project_application.target_is_library,
    )
