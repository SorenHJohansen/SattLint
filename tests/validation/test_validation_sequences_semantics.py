# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false
"""Sequence semantics validation tests for ``validation/sequences.py``.

Covers sequence label collection (flat and nested), label counting, parallel
branch trailers, and STATE-vs-non-STATE variable-reference checks.
"""

from __future__ import annotations

import pytest
from sattline_parser.models.ast_model import (
    SFCBreak,
    SFCCodeBlocks,
    SFCFork,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    Simple_DataType,
    Variable,
)
from sattline_parser.models.expressions import VarRef

from sattlint.resolution.type_graph import TypeGraph
from sattlint.validation.sequences import (
    collect_sequence_label_counts,
    collect_sequence_labels,
    parallel_branch_trailer,
    validate_variable_refs,
)
from sattlint.validation.shared import StructuralValidationError

TYPE_GRAPH = TypeGraph.from_datatypes([])


def _step(name: str) -> SFCStep:
    return SFCStep(kind="step", name=name, code=SFCCodeBlocks(active=[], exit=[]))


def test_collect_sequence_labels_flat() -> None:
    labels: dict[str, str] = {}
    collect_sequence_labels(
        [_step("Run"), SFCTransition(name="Go", condition=VarRef("Proceed"))],
        labels,
        "ctx",
    )
    assert labels == {"run": "Run", "go": "Go"}


def test_collect_sequence_labels_nested() -> None:
    labels: dict[str, str] = {}
    collect_sequence_labels([SFCSubsequence(name="Nested", body=[_step("Run")])], labels, "ctx")
    assert labels == {"nested": "Nested", "run": "Run"}


def test_collect_sequence_label_counts() -> None:
    counts: dict[str, int] = {}
    collect_sequence_label_counts([_step("Run"), _step("Run")], counts)
    assert counts == {"run": 2}


def test_parallel_branch_trailer() -> None:
    assert parallel_branch_trailer(SFCTransition(name="X", condition=VarRef("Y"))) == "SEQTRANSITION"
    assert parallel_branch_trailer(SFCFork(targets=("Done",))) == "SEQFORK"
    assert parallel_branch_trailer(SFCBreak()) == "SEQBREAK"
    assert parallel_branch_trailer(_step("Run")) is None


def test_variable_refs_reject_old_on_non_state_variable() -> None:
    env = {
        name.casefold(): Variable(name=name, datatype=Simple_DataType.BOOLEAN, state=name == "StateWord")
        for name in ("Counter", "StateWord")
    }
    with pytest.raises(StructuralValidationError, match="non-STATE variable"):
        validate_variable_refs(VarRef(name="Counter", state="old"), env, TYPE_GRAPH, "ctx")


def test_variable_refs_accept_state_variable() -> None:
    env = {"stateword": Variable(name="StateWord", datatype=Simple_DataType.BOOLEAN, state=True)}
    validate_variable_refs(VarRef(name="StateWord", state="old"), env, TYPE_GRAPH, "ctx")


def test_variable_refs_ignore_plain_ref() -> None:
    env = {"counter": Variable(name="Counter", datatype=Simple_DataType.INTEGER)}
    validate_variable_refs(VarRef(name="Counter"), env, TYPE_GRAPH, "ctx")
