"""Shared analyzer registry dispatch helpers.

These helpers live outside the ``registry`` package so semantic-layer imports
can execute without triggering registry package initialization.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any, cast

from ..reporting.variables_report import VariablesReport
from .framework import AnalysisContext, Issue, Report


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
    registry_module = _registry_module()

    enabled = tuple(spec for spec in get_enabled_analyzers_fn() if registry_module._is_batch_dispatch_analyzer(spec))
    return resolve_selected_analyzers(
        selected_keys=selected_keys,
        get_enabled_analyzers_fn=lambda: list(enabled),
    )


def get_semantic_contributor_specs() -> tuple[Any, ...]:
    registry_module = _registry_module()

    return tuple(
        analyzer.spec
        for analyzer in registry_module.get_default_analyzer_catalog().analyzers
        if analyzer.spec.enabled
        and (analyzer.spec.semantic_mapping_kind is not None or analyzer.spec.semantic_rule_source is not None)
        and analyzer.spec.key != registry_module.SEMANTIC_LAYER_ANALYZER_KEY
    )


def get_registry_analyzer_spec(key: str) -> Any:
    registry_module = _registry_module()

    canonical_key = registry_module.canonicalize_analyzer_key(key)
    for analyzer in registry_module.get_default_analyzer_catalog().analyzers:
        if _canonical_key(analyzer.spec.key) == canonical_key:
            return analyzer.spec
    raise KeyError(key)


def get_lsp_projection_analyzers() -> tuple[Any, ...]:
    registry_module = _registry_module()

    excluded_keys = {_canonical_key(registry_module.SEMANTIC_LAYER_ANALYZER_KEY), "variables"}
    return tuple(
        analyzer
        for analyzer in registry_module.get_default_analyzer_catalog().analyzers
        if analyzer.delivery.lsp_exposed and _canonical_key(analyzer.spec.key) not in excluded_keys
    )


def run_registry_analyzer(
    spec: Any,
    context: AnalysisContext,
) -> Report:
    return cast(Report, spec.run(context))


def collect_lsp_report_issues(context: AnalysisContext) -> tuple[tuple[str, tuple[Issue, ...]], ...]:
    projected_reports: list[tuple[str, tuple[Issue, ...]]] = []

    for analyzer in get_lsp_projection_analyzers():
        report = run_registry_analyzer(analyzer.spec, context)
        issues = getattr(report, "issues", None)
        if not isinstance(issues, list):
            continue

        report_issues = tuple(issue for issue in cast(list[object], issues) if isinstance(issue, Issue))
        if report_issues:
            projected_reports.append((analyzer.spec.key, report_issues))

    return tuple(projected_reports)


def run_variables_registry_report(
    context: AnalysisContext,
) -> VariablesReport:
    variables_spec = get_registry_analyzer_spec("variables")
    return cast(VariablesReport, run_registry_analyzer(variables_spec, context))


__all__ = [
    "collect_lsp_report_issues",
    "get_cli_dispatch_analyzers",
    "get_lsp_projection_analyzers",
    "get_registry_analyzer_spec",
    "get_semantic_contributor_specs",
    "resolve_selected_analyzers",
    "run_registry_analyzer",
    "run_variables_registry_report",
]
