"""Helpers for attaching SattLint graphics data to tests.

Graphics records, bindings, and correlations live on ``ProjectGraph`` in
production. Tests that exercise the graphics-aware analyzers build the same
handoff instead of writing attributes onto the parser's AST.
"""

from __future__ import annotations

from collections.abc import Iterable

from sattlint.graphics.picture_display_paths import PictureDisplayOccurrence
from sattlint.graphics.validation import GraphicsCompositeRecord, PictureDisplayRecord
from sattlint.models.project_graph import GraphicsAttachments, ProjectGraph
from sattlint.parser_api import BasePicture, GraphicsBinding


def graphics_attachments(
    *,
    file_name: str | None = None,
    bindings: Iterable[GraphicsBinding] = (),
    composite_records: Iterable[GraphicsCompositeRecord] = (),
    picture_display_records: Iterable[PictureDisplayRecord] = (),
    picture_display_occurrences: Iterable[PictureDisplayOccurrence] = (),
) -> GraphicsAttachments:
    return GraphicsAttachments(
        file_name=file_name,
        bindings=tuple(bindings),
        composite_records=tuple(composite_records),
        picture_display_records=tuple(picture_display_records),
        picture_display_occurrences=tuple(picture_display_occurrences),
    )


def graph_with_attachments(base_picture: BasePicture, attachments: GraphicsAttachments) -> ProjectGraph:
    program_name = base_picture.name or base_picture.header.name
    graph = ProjectGraph(ast_by_name={program_name: base_picture})
    graph.graphics_attachments[program_name] = attachments
    return graph


__all__ = ["graph_with_attachments", "graphics_attachments"]
