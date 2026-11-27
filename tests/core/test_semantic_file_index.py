# pyright: reportPrivateUsage=false
"""Reference lookups separate same-named files from different libraries."""

from __future__ import annotations

from pathlib import Path

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.models.ast_model import BasePicture, ModuleHeader

from sattlint.core._semantic_snapshot import ReferenceOccurrence, SymbolDefinition
from sattlint.core.semantic import build_source_snapshot_from_basepicture


def _header(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))


def _definition(module: str) -> SymbolDefinition:
    return SymbolDefinition(
        canonical_path=f"{module}.Value",
        kind="local",
        datatype="integer",
        declaration_module_path=(module,),
        display_module_path=(module,),
    )


def test_same_named_files_in_different_libraries_do_not_cross_resolve(tmp_path: Path) -> None:
    base_picture = BasePicture(header=_header("Main"), modulecode=None, moduledef=None)
    snapshot = build_source_snapshot_from_basepicture(
        base_picture,
        tmp_path / "LibraryA" / "Main.s",
        workspace_root=tmp_path,
    )
    first = _definition("First")
    second = _definition("Second")
    snapshot._definitions_by_key[("first", "value")] = first
    snapshot._definitions_by_key[("second", "value")] = second
    snapshot._references_by_source[("librarya", "main.s")] = (
        ReferenceOccurrence(
            line=1,
            column=1,
            text="Value",
            source_file="Main.s",
            source_library="LibraryA",
            segment_texts=("Value",),
            definition_keys=(("first", "value"),),
        ),
    )
    snapshot._references_by_source[("libraryb", "main.s")] = (
        ReferenceOccurrence(
            line=1,
            column=1,
            text="Value",
            source_file="Main.s",
            source_library="LibraryB",
            segment_texts=("Value",),
            definition_keys=(("second", "value"),),
        ),
    )

    from_library_a = snapshot.find_definitions_at(tmp_path / "LibraryA" / "Main.s", 1, 1)
    from_library_b = snapshot.find_definitions_at(tmp_path / "LibraryB" / "Main.s", 1, 1)

    assert [definition.canonical_path for definition in from_library_a] == ["First.Value"]

    assert [definition.canonical_path for definition in from_library_b] == ["Second.Value"]


def test_reference_occurrences_are_indexed_under_the_owning_library(tmp_path: Path) -> None:
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Counter: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Counter = Counter + 1;
ENDDEF (*BasePicture*);
"""
    base_picture = parser_core_parse_source_text(code)
    snapshot = build_source_snapshot_from_basepicture(
        base_picture,
        tmp_path / "LibraryA" / "Main.s",
        workspace_root=tmp_path,
    )

    assert set(snapshot._references_by_source) == {("librarya", "main.s")}
    assert snapshot._references_by_file == {"main.s": snapshot._references_by_source[("librarya", "main.s")]}
