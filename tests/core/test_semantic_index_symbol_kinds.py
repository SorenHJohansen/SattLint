"""Symbol kinds for module parameters and locals in the semantic index."""

from __future__ import annotations

from pathlib import Path

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ScalarDatatype,
    SingleModule,
    Variable,
)

from sattlint.core.semantic import build_source_snapshot_from_basepicture


def _header(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))


def _variable(name: str) -> Variable:
    return Variable(name=name, datatype=ScalarDatatype.INTEGER)


def test_module_parameters_and_locals_keep_their_symbol_kinds(tmp_path: Path) -> None:
    worker = SingleModule(
        header=_header("Worker"),
        moduleparameters=[_variable("Input")],
        localvariables=[_variable("Local")],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    worker_type = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[_variable("Input")],
        localvariables=[_variable("Local")],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    instance = ModuleTypeInstance(
        header=_header("Inner"),
        moduletype_name="WorkerType",
        parametermappings=[],
    )
    base_picture = BasePicture(
        header=_header("Root"),
        moduletype_defs=[worker_type],
        submodules=[worker, instance],
        modulecode=None,
        moduledef=None,
    )

    snapshot = build_source_snapshot_from_basepicture(
        base_picture,
        tmp_path / "Root.s",
        workspace_root=tmp_path,
    )

    kinds = {definition.canonical_path: definition.kind for definition in snapshot.definitions}
    assert kinds["Root.Worker.Input"] == "parameter"
    assert kinds["Root.Worker.Local"] == "local"
    assert kinds["Root.Inner.Input"] == "parameter"
    assert kinds["Root.Inner.Local"] == "local"
