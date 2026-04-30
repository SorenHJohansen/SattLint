from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattlint.analyzers import symbolic_lite


def test_symbolic_lattice_join_queries_and_summary_export() -> None:
    left = symbolic_lite.PathStateLattice(
        states={
            "always": symbolic_lite.PathState(reachable=True, condition_text="A", is_true=True),
            "unknown": symbolic_lite.PathState(reachable=False, condition_text=None, is_true=None),
        }
    )
    right = symbolic_lite.PathStateLattice(
        states={
            "always": symbolic_lite.PathState(reachable=True, condition_text="B", is_true=False),
            "new": symbolic_lite.PathState(reachable=True, condition_text="C", is_true=True),
        }
    )

    joined = left.join(right)
    joined.add_true_path("true-path", "CondTrue")
    joined.add_false_path("false-path", "CondFalse")
    joined.add_unreachable("dead-path")
    payload = symbolic_lite.build_symbolic_summary(cast(Any, object()))

    assert joined.states["always"] == symbolic_lite.PathState(
        reachable=True,
        condition_text="A",
        is_true=False,
    )
    assert joined.states["new"] == symbolic_lite.PathState(reachable=True, condition_text="C", is_true=True)
    assert joined.is_always_true("true-path") is True
    assert joined.is_always_false("false-path") is True
    assert joined.is_unreachable("dead-path") is True
    assert payload == {
        "kind": "sattlint.symbolic_summary",
        "schema_version": 1,
        "summary": {
            "always_true_count": 0,
            "always_false_count": 0,
            "unreachable_count": 0,
            "total_tracked": 0,
        },
        "always_true": [],
        "always_false": [],
        "unreachable": [],
    }


def test_build_symbolic_summary_reports_true_false_and_unreachable_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    lattice = symbolic_lite.PathStateLattice(
        states={
            "path.true": symbolic_lite.PathState(reachable=True, condition_text="A", is_true=True),
            "path.false": symbolic_lite.PathState(reachable=True, condition_text="B", is_true=False),
            "path.dead": symbolic_lite.PathState(reachable=False, condition_text="C", is_true=None),
        }
    )
    monkeypatch.setattr(symbolic_lite, "PathStateLattice", lambda: lattice)

    payload = symbolic_lite.build_symbolic_summary(cast(Any, SimpleNamespace()))

    assert payload == {
        "kind": "sattlint.symbolic_summary",
        "schema_version": 1,
        "summary": {
            "always_true_count": 1,
            "always_false_count": 1,
            "unreachable_count": 1,
            "total_tracked": 3,
        },
        "always_true": ["path.true"],
        "always_false": ["path.false"],
        "unreachable": ["path.dead"],
    }
