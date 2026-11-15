# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
"""Semantic project-graph invariants: indexes key on case-insensitive names."""

from __future__ import annotations

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


def test_datatype_defs_index_folds_case_and_keeps_the_last_definition() -> None:
    graph = ProjectGraph()
    first = DataType(name="HeaderRecord", description=None, datecode=None, var_list=[])
    second = DataType(name="HEADERRECORD", description=None, datecode=None, var_list=[])

    graph.index_from_basepic(_picture("First", first))
    graph.index_from_basepic(_picture("Second", second))

    assert list(graph.datatype_defs) == ["headerrecord"]
    assert graph.datatype_defs["headerrecord"] is second
