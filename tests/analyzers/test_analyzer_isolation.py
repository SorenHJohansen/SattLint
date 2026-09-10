# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportAttributeAccessIssue=false
"""Analyzer isolation and ordering tests (Phase R4).

Verifies that each analyzer can run in isolation and that the full suite
produces equivalent results regardless of execution order.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from sattline_parser.models.ast_model import BasePicture, ModuleHeader

from sattlint.analyzers._registry_dispatch import run_registry_analyzer
from sattlint.analyzers.framework import (
    AnalysisContext,
    AnalysisSharedArtifacts,
    Report,
    build_analysis_context,
)
from sattlint.analyzers.registry import get_enabled_analyzers


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _make_base_picture() -> BasePicture:
    return BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )


def _make_context(
    base_picture: BasePicture | None = None,
    shared_artifacts: AnalysisSharedArtifacts | None = None,
) -> AnalysisContext:
    return build_analysis_context(
        base_picture=base_picture or _make_base_picture(),
        shared_artifacts=shared_artifacts,
    )


def _get_enabled_specs() -> list[Any]:
    return get_enabled_analyzers()


def _issues_key(report: Report) -> tuple[str, ...]:
    issues = getattr(report, "issues", None)
    if not isinstance(issues, list):
        return ()
    return tuple(str(getattr(issue, "rule", getattr(issue, "kind", ""))) for issue in cast(list[Any], issues))


# ---------------------------------------------------------------------------
# Isolation tests
# ---------------------------------------------------------------------------


class TestAnalyzerIsolation:
    """Each analyzer without dependencies produces the same result in isolation
    as when run as part of the full suite (with empty shared artifacts)."""

    def test_analyzers_without_requires_run_in_isolation(self) -> None:
        specs = [s for s in _get_enabled_specs() if not getattr(s, "requires", ())]
        context = _make_context()

        for spec in specs:
            report = run_registry_analyzer(spec, context, use_shared_artifacts=False)
            assert hasattr(report, "issues"), f"{spec.key} did not return a Report-like object"

    def test_analyzers_with_requires_raise_without_dependencies(self) -> None:
        specs = [s for s in _get_enabled_specs() if getattr(s, "requires", ())]
        context = _make_context()

        for spec in specs:
            with pytest.raises(RuntimeError, match="requires analyzer results from"):
                run_registry_analyzer(spec, context, use_shared_artifacts=False)

    def test_isolated_result_matches_full_suite_for_independent_analyzers(self) -> None:
        independent_specs = [s for s in _get_enabled_specs() if not getattr(s, "requires", ())]
        context = _make_context()

        isolated_results: dict[str, Report] = {}
        for spec in independent_specs:
            isolated_results[spec.key] = run_registry_analyzer(spec, context, use_shared_artifacts=False)

        full_results: dict[str, Report] = {}
        for spec in independent_specs:
            full_results[spec.key] = run_registry_analyzer(spec, context, use_shared_artifacts=False)

        for spec in independent_specs:
            isolated_issues = _issues_key(isolated_results[spec.key])
            full_issues = _issues_key(full_results[spec.key])
            assert isolated_issues == full_issues, f"{spec.key}: isolated result differs from full suite"


# ---------------------------------------------------------------------------
# Order independence tests
# ---------------------------------------------------------------------------


class TestAnalyzerOrderIndependence:
    """Running all enabled analyzers in different orders produces equivalent
    combined results (for independent analyzers)."""

    def test_two_orderings_produce_equivalent_results(self) -> None:
        independent_specs = [s for s in _get_enabled_specs() if not getattr(s, "requires", ())]
        context = _make_context()

        order_a = independent_specs
        order_b = list(reversed(independent_specs))

        results_a: dict[str, tuple[str, ...]] = {}
        for spec in order_a:
            report = run_registry_analyzer(spec, context, use_shared_artifacts=False)
            results_a[spec.key] = _issues_key(report)

        results_b: dict[str, tuple[str, ...]] = {}
        for spec in order_b:
            report = run_registry_analyzer(spec, context, use_shared_artifacts=False)
            results_b[spec.key] = _issues_key(report)

        for spec in independent_specs:
            assert results_a[spec.key] == results_b[spec.key], f"{spec.key}: result differs between orderings"

    def test_full_suite_order_independence(self) -> None:
        independent_specs = [s for s in _get_enabled_specs() if not getattr(s, "requires", ())]
        context = _make_context()

        all_keys = sorted(s.key for s in independent_specs)

        results_first: dict[str, Report] = {}
        for spec in independent_specs:
            results_first[spec.key] = run_registry_analyzer(spec, context, use_shared_artifacts=False)

        results_second: dict[str, Report] = {}
        for spec in independent_specs:
            results_second[spec.key] = run_registry_analyzer(spec, context, use_shared_artifacts=False)

        for key in all_keys:
            first_issues = _issues_key(results_first[key])
            second_issues = _issues_key(results_second[key])
            assert first_issues == second_issues, f"{key}: re-run produced different results"
