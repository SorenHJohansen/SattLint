"""Shared analyzer registry dispatch helpers."""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any, cast

from ..reporting.variables_report import VariablesReport
from .framework import AnalysisContext, Report


def _registry_module() -> Any:
    from . import registry as registry_module  # noqa: PLC0415 - avoid registry package init cycles

    return registry_module


def _canonical_key(key: str) -> str:
    return _registry_module().canonicalize_analyzer_key(key)


def resolve_selected_analyzers(
    *,
    selected_keys: Collection[str] | None,
    get_enabled_analyzers_fn: Callable[[], list[Any]],
) -> tuple[Any, ...]:
    """Return exactly the selected analyzers, in their declared order.

    With no selection the enabled set is returned unchanged. Selection is exact:
    no analyzer is added, dropped, reordered, or collapsed.
    """
    enabled = get_enabled_analyzers_fn()
    if not selected_keys:
        return tuple(enabled)
    selected = {_canonical_key(key) for key in selected_keys}
    return tuple(spec for spec in enabled if _canonical_key(getattr(spec, "key", "")) in selected)


def get_cli_dispatch_analyzers(
    *,
    selected_keys: Collection[str] | None,
    get_enabled_analyzers_fn: Callable[[], list[Any]],
) -> tuple[Any, ...]:
    return resolve_selected_analyzers(
        selected_keys=selected_keys,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
    )


def get_registry_analyzer_spec(key: str) -> Any:
    registry_module = _registry_module()

    canonical_key = registry_module.canonicalize_analyzer_key(key)
    for analyzer in registry_module.get_default_analyzer_catalog().analyzers:
        if _canonical_key(analyzer.spec.key) == canonical_key:
            return analyzer.spec
    raise KeyError(key)


def run_registry_analyzer(
    spec: Any,
    context: AnalysisContext,
) -> Report:
    return cast(Report, spec.run(context))


def run_variables_registry_report(
    context: AnalysisContext,
) -> VariablesReport:
    variables_spec = get_registry_analyzer_spec("variables")
    return cast(VariablesReport, run_registry_analyzer(variables_spec, context))


__all__ = [
    "get_cli_dispatch_analyzers",
    "get_registry_analyzer_spec",
    "resolve_selected_analyzers",
    "run_registry_analyzer",
    "run_variables_registry_report",
]
