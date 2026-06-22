"""Stable dispatch facade for registry-backed analysis entrypoints.

Non-analyzer layers should import registry-backed analyzer selection and
execution through this module rather than depending on analyzer-internal
dispatch helpers directly.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from typing import Any, cast

from .analyzers._registry_dispatch import (
    get_cli_dispatch_analyzers as _get_cli_dispatch_analyzers,
)
from .analyzers._registry_dispatch import (
    get_lsp_projection_analyzers as _get_lsp_projection_analyzers,
)
from .analyzers._registry_dispatch import (
    get_registry_analyzer_spec as _get_registry_analyzer_spec,
)
from .analyzers._registry_dispatch import (
    get_semantic_contributor_specs as _get_semantic_contributor_specs,
)
from .analyzers._registry_dispatch import run_registry_analyzer as _run_registry_analyzer
from .analyzers.framework import AnalysisContext, Issue, Report
from .reporting.variables_report import VariablesReport


def get_cli_dispatch_analyzers(
    *,
    selected_keys: Collection[str] | None,
    get_enabled_analyzers_fn: Callable[[], list[Any]],
) -> tuple[Any, ...]:
    return _get_cli_dispatch_analyzers(
        selected_keys=selected_keys,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
    )


def get_semantic_contributor_specs() -> tuple[Any, ...]:
    return _get_semantic_contributor_specs()


def get_registry_analyzer_spec(key: str) -> Any:
    return _get_registry_analyzer_spec(key)


def get_lsp_projection_analyzers() -> tuple[Any, ...]:
    return _get_lsp_projection_analyzers()


def collect_lsp_report_issues(context: AnalysisContext) -> tuple[tuple[str, tuple[Issue, ...]], ...]:
    projected_reports: list[tuple[str, tuple[Issue, ...]]] = []

    for analyzer in _get_lsp_projection_analyzers():
        report = _run_registry_analyzer(analyzer.spec, context)
        issues = getattr(report, "issues", None)
        if not isinstance(issues, list):
            continue

        report_issues = tuple(issue for issue in cast(list[object], issues) if isinstance(issue, Issue))
        if report_issues:
            projected_reports.append((analyzer.spec.key, report_issues))

    return tuple(projected_reports)


def run_variables_registry_report(
    context: AnalysisContext,
    *,
    include_dependency_moduletype_usage: bool | None = None,
) -> VariablesReport:
    variables_spec = _get_registry_analyzer_spec("variables")
    overrides = (
        None
        if include_dependency_moduletype_usage is None
        else {"include_dependency_moduletype_usage": include_dependency_moduletype_usage}
    )
    return cast(VariablesReport, _run_registry_analyzer(variables_spec, context, overrides=overrides))


def run_registry_analyzer(
    spec: Any,
    context: AnalysisContext,
    *,
    overrides: Mapping[str, object] | None = None,
    use_shared_artifacts: bool = False,
) -> Report:
    return _run_registry_analyzer(
        spec,
        context,
        overrides=overrides,
        use_shared_artifacts=use_shared_artifacts,
    )


__all__ = [
    "collect_lsp_report_issues",
    "get_cli_dispatch_analyzers",
    "get_lsp_projection_analyzers",
    "get_registry_analyzer_spec",
    "get_semantic_contributor_specs",
    "run_registry_analyzer",
    "run_variables_registry_report",
]
