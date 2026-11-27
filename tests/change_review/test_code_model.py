# pyright: reportPrivateUsage=false
"""Tests for the Change Review code model."""

from __future__ import annotations

from pathlib import Path

from sattline_parser.ast import (
    Assignment,
    BasePicture,
    IfStmt,
    MappingSource,
    ModuleHeader,
    ModuleTypeInstance,
    ParameterMapping,
    VarRef,
)

from sattlint.change_review._code_model import _iter_assignment_targets, build_code_model
from sattlint.core.semantic import build_source_snapshot_from_basepicture


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


def test_connection_only_instance_is_kept_when_typedef_is_unavailable(tmp_path: Path) -> None:
    header = ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))
    instance = ModuleTypeInstance(
        header=ModuleHeader(name="Valve", invoke_coord=(0.0, 0.0, 0.0, 0.5, 0.5)),
        moduletype_name="ExternalValveType",
        parametermappings=[
            ParameterMapping(
                target=VarRef(name="Open"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=False,
                source=VarRef(name="StartCmd"),
            )
        ],
    )
    base_picture = BasePicture(
        header=header,
        submodules=[instance],
        modulecode=None,
        moduledef=None,
    )
    snapshot = build_source_snapshot_from_basepicture(
        base_picture,
        tmp_path / "Demo.s",
        workspace_root=tmp_path,
    )

    model = build_code_model(snapshot, include_dependency_modules=False)
    instance_model = next(module for module in model.modules if module.module_path == ("Root", "Valve"))

    assert instance_model.statements == ()
    assert [(connection.target, connection.source_name) for connection in instance_model.connections] == [
        ("Open", "StartCmd")
    ]
