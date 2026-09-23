# pyright: reportPrivateUsage=false
"""Focused unit tests for the Phase 5 parser-backed project loader adapter.

Covers ``sattlint.project.parser_adapter``: graph conversion from a loaded
``SattLineProject``, missing-dependency recording, cycle detection, reverse-
consumer dedup, library naming, ast-only refresh mode, and the hermetic
``load_parser_project`` I/O path. Programs are built schema-only via
``SattLineProject._from_programs`` (no filesystem) except for the I/O
round-trip test, which writes real ``.s`` / ``.l`` fixtures into ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sattline_parser import parse_source_text
from sattline_parser.models.ast_model import BasePicture
from sattline_parser.project import (
    ProjectLoadError,
    SattLineProgram,
    SattLineProject,
)

from sattlint.core.syntax import CodeMode
from sattlint.models.project_graph import ProjectGraph
from sattlint.project.parser_adapter import (
    CircularDependencyError,
    ParserProjectBinding,
    convert_project_into_graph,
    find_code_path,
    find_dependency_path,
    load_parser_project,
    read_dependency_names,
)

_SMALL_PROGRAM = (
    '"SyntaxVersion"\n'
    '"OriginalFileDate"\n'
    '"ProgramDate"\n'
    "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
    "ModuleDef\n"
    "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
    "ENDDEF (*BasePicture*);\n"
)


def _code() -> BasePicture:
    return parse_source_text(_SMALL_PROGRAM)


def _program(name: str, *, dependencies: tuple[str, ...] = (), source_path: Path | None = None) -> SattLineProgram:
    return SattLineProgram(name=name, code=_code(), dependencies=dependencies, source_path=source_path)


def _binding(
    program_dir: Path, *, other_lib_dirs: tuple[Path, ...] = (), abb_lib_dir: Path | None = None
) -> ParserProjectBinding:
    return ParserProjectBinding(
        program_dir=program_dir,
        other_lib_dirs=other_lib_dirs,
        abb_lib_dir=abb_lib_dir,
        mode=CodeMode.DRAFT,
        refresh_mode="full",
    )


def test_binding_roots_orders_dirs_without_none() -> None:
    program_dir = Path("/p")
    lib = Path("/lib")
    binding = _binding(program_dir, other_lib_dirs=(lib,), abb_lib_dir=None)
    assert binding.roots == (program_dir, lib)
    assert binding.parser_mode().value == "draft"


def test_convert_populates_graph_from_registry() -> None:
    tmp = Path("/tmp/base")
    prg = tmp / "prg"
    lib = tmp / "lib"
    a = _program("A", source_path=lib / "A.s")
    b = _program("B", dependencies=("A",), source_path=prg / "B.s")
    project = SattLineProject._from_programs({"A": a, "B": b})
    graph = ProjectGraph()
    convert_project_into_graph(
        project, graph, binding=_binding(prg, other_lib_dirs=(lib,)), root_name="B", strict=False
    )

    assert set(graph.ast_by_name) == {"A", "B"}
    assert graph.ast_by_name["A"] is a.code
    assert graph.ast_by_name["B"] is b.code
    assert graph.source_files == {lib / "A.s", prg / "B.s"}
    assert graph.library_dependencies["prg"] == {"lib"}
    assert graph.missing == []


def test_convert_records_dangling_dependency_as_missing() -> None:
    tmp = Path("/tmp/base")
    prg = tmp / "prg"
    owner = _program("B", dependencies=("MISSING",), source_path=prg / "B.s")
    project = SattLineProject._from_programs({"B": owner})
    graph = ProjectGraph()
    convert_project_into_graph(project, graph, binding=_binding(prg), root_name="B", strict=False)

    assert "missing" in graph.unavailable_libraries
    assert any("MISSING" in entry and "B" in entry for entry in graph.missing)


def test_convert_flags_root_not_loaded_as_missing() -> None:
    prg = Path("/tmp/base/prg")
    a = _program("A", source_path=prg / "A.s")
    project = SattLineProject._from_programs({"A": a})
    graph = ProjectGraph()
    convert_project_into_graph(project, graph, binding=_binding(prg), root_name="R", strict=False)

    assert set(graph.ast_by_name) == {"A"}
    assert "r" in graph.unavailable_libraries
    assert any("'R'" in entry and "B" not in entry for entry in graph.missing)
    assert len(graph.missing) == 1


def test_convert_raises_on_cycle_always() -> None:
    prg = Path("/tmp/base/prg")
    a = _program("A", dependencies=("B",), source_path=prg / "A.s")
    b = _program("B", dependencies=("A",), source_path=prg / "B.s")
    project = SattLineProject._from_programs({"A": a, "B": b})
    graph = ProjectGraph()
    with pytest.raises(CircularDependencyError) as excinfo:
        convert_project_into_graph(project, graph, binding=_binding(prg), root_name="A", strict=False)
    assert excinfo.value.library == "A"


def test_convert_skips_already_present_programs() -> None:
    prg = Path("/tmp/base/prg")
    lib = _program("A", source_path=prg / "A.s")
    owner = _program("B", dependencies=("A",), source_path=prg / "B.s")
    project = SattLineProject._from_programs({"A": lib, "B": owner})
    graph = ProjectGraph()
    convert_project_into_graph(project, graph, binding=_binding(prg), root_name="B", strict=False)
    indexed_before = len(graph.moduletype_defs)

    other = SattLineProject._from_programs({"A": lib, "C": _program("C", dependencies=("A",), source_path=prg / "C.s")})
    convert_project_into_graph(other, graph, binding=_binding(prg), root_name="C", strict=False)

    assert graph.ast_by_name["A"] is lib.code
    assert len(graph.moduletype_defs) == indexed_before
    assert set(graph.ast_by_name) == {"A", "B", "C"}


def test_convert_ast_only_skips_graphics_and_indexing() -> None:
    prg = Path("/tmp/base/prg")
    binding = ParserProjectBinding(
        program_dir=prg,
        other_lib_dirs=(),
        abb_lib_dir=None,
        mode=CodeMode.DRAFT,
        refresh_mode="ast-only",
    )
    a = _program("A", source_path=prg / "A.s")
    project = SattLineProject._from_programs({"A": a})
    graph = ProjectGraph()
    convert_project_into_graph(project, graph, binding=binding, root_name="A", strict=False)

    assert set(graph.ast_by_name) == {"A"}
    assert graph.moduletype_defs == {}
    assert graph.library_dependencies == {}
    assert graph.source_files == set()


def test_load_parser_project_round_trip_hermetic(tmp_path: Path) -> None:
    program_dir = tmp_path / "prg"
    program_dir.mkdir()
    (program_dir / "Main.s").write_text(_SMALL_PROGRAM, encoding="utf-8")
    (program_dir / "Dep.s").write_text(_SMALL_PROGRAM, encoding="utf-8")
    (program_dir / "Main.l").write_text("Dep\n", encoding="utf-8")

    binding = _binding(program_dir)
    project = load_parser_project(binding, ["Main"], strict=False)
    assert "Dep" in project
    assert "Main" in project
    assert project.dependencies_of("Main") == ("Dep",)
    assert project.get("Main").source_path == (program_dir / "Main.s").resolve()

    graph = ProjectGraph()
    convert_project_into_graph(project, graph, binding=binding, root_name="Main", strict=False)
    assert set(graph.ast_by_name) == {"Main", "Dep"}


def test_load_parser_project_strict_raises_on_missing_target(tmp_path: Path) -> None:
    program_dir = tmp_path / "prg"
    program_dir.mkdir()
    (program_dir / "Main.s").write_text(_SMALL_PROGRAM, encoding="utf-8")
    binding = _binding(program_dir)
    with pytest.raises(ProjectLoadError, match="missing code file"):
        load_parser_project(binding, ["Nope"], strict=True)


def test_find_code_and_dependency_paths_and_names(tmp_path: Path) -> None:
    program_dir = tmp_path / "prg"
    program_dir.mkdir()
    (program_dir / "Main.s").write_text(_SMALL_PROGRAM, encoding="utf-8")
    (program_dir / "Dep.s").write_text(_SMALL_PROGRAM, encoding="utf-8")
    (program_dir / "Main.l").write_text("Dep\n", encoding="utf-8")

    binding = _binding(program_dir)
    assert find_code_path(binding, "Main", requester_dir=program_dir) == (program_dir / "Main.s").resolve()
    assert find_dependency_path(binding, "Main", requester_dir=program_dir) == (program_dir / "Main.l").resolve()
    assert read_dependency_names(program_dir / "Main.l") == ("Dep",)
    assert find_code_path(binding, "Nope", requester_dir=program_dir) is None


def test_library_name_falls_through_to_program_root() -> None:
    prg = Path("/tmp/base/prg")
    lib_a = Path("/tmp/base/libA")
    lib_b = Path("/tmp/base/libB")
    abb = Path("/tmp/base/abb")

    def _bound(program_dir: Path) -> ParserProjectBinding:
        return _binding(program_dir, other_lib_dirs=(lib_a, lib_b), abb_lib_dir=abb)

    a = _program("A", source_path=lib_a / "A.s")
    b = _program("B", source_path=lib_b / "B.s")
    c = _program("C", source_path=abb / "C.s")
    root = _program("Root", dependencies=("A", "B", "C"), source_path=prg / "Root.s")
    project = SattLineProject._from_programs({p.name: p for p in (a, b, c, root)})
    graph = ProjectGraph()
    convert_project_into_graph(project, graph, binding=_bound(prg), root_name="Root", strict=False)

    assert graph.library_dependencies["prg"] == {"abb", "liba", "libb"}
