# pyright: reportPrivateUsage=false
"""Graphics bindings must contribute references and calls to the semantic index."""

from __future__ import annotations

from pathlib import Path

from sattline_parser.models.ast_model import BasePicture, ModuleHeader, Simple_DataType, Variable
from sattline_parser.models.expressions import FuncCall, VarRef

from sattlint.core.semantic import build_snapshot_from_loaded_project
from sattlint.parser_api import GraphicsBinding, SourceSpan
from tests.helpers.graphics_attachments_support import graph_with_attachments, graphics_attachments


def test_graphics_binding_references_and_calls_are_indexed(tmp_path: Path) -> None:
    bp = BasePicture(
        header=ModuleHeader(name="Demo", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        name="Demo",
        localvariables=[Variable(name="Flow", datatype=Simple_DataType.INTEGER)],
        origin_file="Demo.s",
        origin_lib="DemoLib",
    )
    bindings = (
        GraphicsBinding(
            kind="var",
            raw_text="Flow",
            value=VarRef(name="Flow", span=SourceSpan(10, 14, 3, 7)),
            span=SourceSpan(10, 14, 3, 7),
        ),
        GraphicsBinding(
            kind="expr",
            raw_text="GetTime()",
            value=FuncCall(name="GetTime", args=(), span=SourceSpan(20, 29, 4, 3)),
            span=SourceSpan(20, 29, 4, 3),
        ),
    )
    graph = graph_with_attachments(bp, graphics_attachments(file_name="Demo.g", bindings=bindings))

    snapshot = build_snapshot_from_loaded_project(
        bp,
        graph,
        entry_file=tmp_path / "Demo.s",
        workspace_root=tmp_path,
    )

    references = snapshot.find_references_to("Flow")
    assert [(reference.line, reference.text) for reference in references] == [(3, "Flow")]
    assert [call.name for call in snapshot.call_signatures] == ["GetTime"]
