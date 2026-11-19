# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
"""Semantic project-graph invariants: indexes key on case-insensitive identity."""

from __future__ import annotations

from pathlib import Path

from sattline_parser.models.ast_model import BasePicture, DataType, ModuleHeader

from sattlint.models.project_graph import ProjectGraph


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _picture(name: str, datatype: DataType) -> BasePicture:
    return BasePicture(
        header=_hdr(name),
        datatype_defs=[datatype],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )


def _record(name: str) -> DataType:
    return DataType(name=name, description=None, datecode=None, var_list=[])


def test_datatype_defs_keep_same_name_records_from_different_libraries() -> None:
    graph = ProjectGraph()
    first = _record("HeaderRecord")
    second = _record("HEADERRECORD")

    graph.index_from_basepic(
        _picture("First", first),
        source_path=Path("first.s"),
        library_name="LibraryA",
    )
    graph.index_from_basepic(
        _picture("Second", second),
        source_path=Path("second.s"),
        library_name="LibraryB",
    )

    assert graph.datatype_defs[("librarya", "headerrecord", "first.s")] is first
    assert graph.datatype_defs[("libraryb", "headerrecord", "second.s")] is second


def test_datatype_defs_last_definition_wins_for_the_same_origin() -> None:
    graph = ProjectGraph()
    first = _record("HeaderRecord")
    second = _record("HEADERRECORD")

    graph.index_from_basepic(_picture("First", first), source_path=Path("Shared.s"), library_name="LibraryA")
    graph.index_from_basepic(_picture("Second", second), source_path=Path("Shared.s"), library_name="LibraryA")

    assert list(graph.datatype_defs) == [("librarya", "headerrecord", "shared.s")]
    assert graph.datatype_defs[("librarya", "headerrecord", "shared.s")] is second
