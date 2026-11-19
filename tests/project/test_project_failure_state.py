"""Typed project failure state and its human-readable rendering."""

from __future__ import annotations

from sattlint.models._validation_notice import ValidationNotice
from sattlint.models.project_graph import ProjectFailure, ProjectGraph
from sattlint.project.loading_support import record_project_failure, record_project_warning
from sattlint.project.support import TargetLoadError


def test_record_project_failure_keeps_the_detail_on_the_typed_record() -> None:
    graph = ProjectGraph()

    record_project_failure(graph, "Program", RuntimeError("unexpected token"))

    failure = graph.failures["program"]
    assert failure.name == "Program"
    assert failure.detail == "unexpected token"


def test_failure_reporting_uses_the_typed_detail() -> None:
    failure = ProjectFailure(
        name="Program",
        message="Program could not be prepared",
        detail="unexpected token",
        line=4,
        column=2,
    )

    message = str(
        TargetLoadError(
            "Program",
            resolved=[],
            missing=[failure.message],
            failures={"program": failure},
        )
    )

    assert "  - Program: unexpected token (line 4, column 2)" in message


def test_project_warning_state_has_a_single_store() -> None:
    graph = ProjectGraph()

    record_project_warning(graph, "Program", ValidationNotice(message="unknown clause"))

    assert graph.warnings == ["Program: unknown clause"]
