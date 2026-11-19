"""Snapshot query identity rules."""

from __future__ import annotations

from pathlib import Path

from sattlint.core.semantic import build_snapshot_from_loaded_project
from sattlint.models.project_graph import ProjectGraph
from sattlint.parser_api import parse_source_text


def _source_text() -> str:
    return """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    A: integer := 0;
    Value: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Value = ABS(A);
ENDDEF (*BasePicture*);
""".strip()


def test_call_signature_query_prefers_the_declared_library(tmp_path: Path) -> None:
    entry_file = tmp_path / "Folder" / "Main.s"
    base_picture = parse_source_text(_source_text())
    graph = ProjectGraph()
    # The loader can name a library differently from its directory; queries
    # must use the declared name, not the enclosing folder.
    graph.index_from_basepic(base_picture, source_path=entry_file.resolve(), library_name="DeclaredLibrary")

    snapshot = build_snapshot_from_loaded_project(
        base_picture,
        graph,
        entry_file=entry_file,
        workspace_root=tmp_path,
    )

    signatures = snapshot.find_call_signatures("abs", source_path=entry_file)

    assert len(signatures) == 1
    assert signatures[0].source_library == "DeclaredLibrary"
