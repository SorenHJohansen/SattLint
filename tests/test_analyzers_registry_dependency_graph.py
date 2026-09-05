# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false
"""Tests for construction-time analyzer dependency graph validation (Phase 7)."""

from __future__ import annotations

from typing import Any, cast

import pytest

from sattlint.analyzers.framework import AnalyzerSpec
from sattlint.analyzers.registry import (
    AnalyzerDependencyGraphError,
    deterministic_dependency_order,
    validate_analyzer_dependencies,
)


def _spec(key: str, *, requires: tuple[str, ...] = ()) -> AnalyzerSpec:
    return AnalyzerSpec(
        key=key,
        name=key,
        description=key,
        run=lambda _context: cast(Any, key),
        requires=requires,
    )


def test_valid_registry_yields_deterministic_dependency_order() -> None:
    specs = (
        _spec("a"),
        _spec("b", requires=("a",)),
        _spec("c"),
        _spec("d", requires=("b", "c")),
    )

    validate_analyzer_dependencies(specs)
    first = deterministic_dependency_order(specs)
    second = deterministic_dependency_order(specs)

    assert [spec.key for spec in first] == ["a", "b", "c", "d"]
    assert first == second


def test_duplicate_keys_are_rejected() -> None:
    specs = (_spec("a"), _spec("a"))

    with pytest.raises(AnalyzerDependencyGraphError, match="duplicate analyzer key 'a'"):
        validate_analyzer_dependencies(specs)


def test_colliding_canonical_keys_are_rejected() -> None:
    # "config_drift" canonicalizes to "config-drift"; a second analyzer with the
    # canonical key collides.
    specs = (_spec("config_drift"), _spec("config-drift"))

    with pytest.raises(AnalyzerDependencyGraphError, match="collide on canonical key 'config-drift'"):
        validate_analyzer_dependencies(specs)


def test_unknown_required_analyzer_is_rejected() -> None:
    specs = (_spec("a"), _spec("b", requires=("missing-analyzer",)))

    with pytest.raises(AnalyzerDependencyGraphError, match="requires unknown analyzer 'missing-analyzer'"):
        validate_analyzer_dependencies(specs)


def test_self_dependency_is_rejected() -> None:
    specs = (_spec("a", requires=("a",)),)

    with pytest.raises(AnalyzerDependencyGraphError, match="depends on itself"):
        validate_analyzer_dependencies(specs)


def test_dependency_cycle_is_rejected() -> None:
    specs = (
        _spec("a", requires=("b",)),
        _spec("b", requires=("a",)),
    )

    with pytest.raises(AnalyzerDependencyGraphError, match="dependency cycle"):
        validate_analyzer_dependencies(specs)


def test_dependency_cycle_via_transitive_edge_is_rejected() -> None:
    specs = (
        _spec("a", requires=("b",)),
        _spec("b", requires=("c",)),
        _spec("c", requires=("a",)),
    )

    with pytest.raises(AnalyzerDependencyGraphError, match="dependency cycle"):
        validate_analyzer_dependencies(specs)


def test_multiple_invalid_conditions_are_reported_together() -> None:
    specs = (
        _spec("a", requires=("ghost",)),
        _spec("b", requires=("b",)),
    )

    with pytest.raises(AnalyzerDependencyGraphError) as excinfo:
        validate_analyzer_dependencies(specs)

    message = str(excinfo.value)
    assert "requires unknown analyzer 'ghost'" in message
    assert "depends on itself" in message
