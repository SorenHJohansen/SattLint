"""Graphics companion helpers for the engine."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from sattlint.parser_api import BasePicture, GraphicsModel

from ..models.project_graph import EMPTY_GRAPHICS_ATTACHMENTS, GraphicsAttachments, ProjectGraph
from ..project.loading_support import record_project_warning
from ..validation.shared import ValidationNotice
from .graphics_context_helpers import picture_display_path_warnings
from .picture_display_paths import correlate_picture_display_records
from .picture_display_runtime import correlate_composite_records
from .validation import validate_graphics_model


def attach_graphics_companion(
    bp: BasePicture,
    *,
    graphics: GraphicsModel | None,
    companion_path: Path | None,
    code_path: Path,
    graph: ProjectGraph,
    owner_name: str,
    timing_sink: Callable[[str, str, float], None] | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> GraphicsAttachments:
    """Build the SattLint graphics view for one program.

    The parser has already scanned the companion file. This seam converts that
    model into the record shapes analyzers read, correlates records against the
    code picture, and records the workspace-dependent notices. The result is
    returned instead of being written onto the parser's AST.
    """
    if graphics is None or companion_path is None:
        return EMPTY_GRAPHICS_ATTACHMENTS

    def _record_timing(phase_name: str, started_at: float) -> None:
        if timing_sink is None:
            return
        timing_sink(owner_name, phase_name, perf_counter() - started_at)

    validate_started_at = perf_counter()
    result = validate_graphics_model(graphics, companion_path)
    _record_timing("validate-graphics-file", validate_started_at)

    composite_started_at = perf_counter()
    composite_occurrences = correlate_composite_records(bp, result.composite_records, graph=graph)
    _record_timing("correlate-composites", composite_started_at)

    picture_display_started_at = perf_counter()
    picture_display_occurrences = correlate_picture_display_records(
        bp,
        result.picture_display_records,
        graph=graph,
    )
    _record_timing("correlate-picture-display", picture_display_started_at)

    attachments = GraphicsAttachments(
        file_name=companion_path.name,
        bindings=result.bindings,
        messages=result.messages,
        composite_records=result.composite_records,
        composite_occurrences=composite_occurrences,
        picture_display_records=result.picture_display_records,
        picture_display_occurrences=picture_display_occurrences,
    )

    warnings_precomputed: tuple[ValidationNotice, ...] = ()
    if code_path.suffix.lower() not in {".x", ".z"}:
        if status_callback:
            status_callback("computing picture display path warnings")
        warnings_started_at = perf_counter()
        warnings_precomputed = picture_display_path_warnings(
            bp,
            picture_display_occurrences,
            graph=graph,
            status_callback=status_callback,
        )
        _record_timing("picture-display-warnings", warnings_started_at)

    for warning in warnings_precomputed:
        record_project_warning(graph, owner_name, warning)

    for message in result.messages:
        record_project_warning(
            graph,
            owner_name,
            ValidationNotice(
                message=f"graphics validation {message.severity}: {message.message}",
                line=message.line,
                column=message.column,
                length=message.length,
            ),
        )
    return attachments
