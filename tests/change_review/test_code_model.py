# pyright: reportPrivateUsage=false
"""Tests for the Change Review code model."""

from __future__ import annotations

from sattline_parser.ast import Assignment, IfStmt, VarRef

from sattlint.change_review._code_model import _iter_assignment_targets


def test_assignment_targets_walk_nested_if_branches() -> None:
    statement = IfStmt(
        branches=(
            (
                VarRef(name="Cond"),
                (
                    Assignment(target=VarRef(name="A"), value=1),
                    Assignment(target=VarRef(name="B"), value=2),
                ),
            ),
            (
                VarRef(name="OtherCond"),
                (
                    IfStmt(
                        branches=(
                            (
                                VarRef(name="InnerCond"),
                                (Assignment(target=VarRef(name="C"), value=3),),
                            ),
                        ),
                        else_block=(Assignment(target=VarRef(name="D"), value=4),),
                    ),
                ),
            ),
        ),
        else_block=(Assignment(target=VarRef(name="E"), value=5),),
    )

    assert [target.name for target in _iter_assignment_targets(statement)] == ["A", "B", "C", "D", "E"]
