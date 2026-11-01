"""Graphics companion helpers for the engine."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from sattline_parser.models.ast_model import BasePicture
from sattline_parser.project import GraphicsModel

from ..models.project_graph import ProjectGraph
from ..project.loading_support import record_project_warning
from ..validation.shared import ValidationNotice
from .graphics_context_helpers import picture_display_path_warnings
from .picture_display_paths import correlate_picture_display_records
from .picture_display_runtime import correlate_composite_records
from .validation import validate_graphics_model


def _clear_attached_graphics_companion(bp: BasePicture) -> bool:
    defaults: tuple[tuple[str, object], ...] = (
        ("graphics_file", None),
        ("graphics_bindings", []),
        ("graphics_messages", []),
        ("graphics_composite_records", []),
        ("graphics_composite_occurrences", []),
        ("graphics_picture_display_records", []),
        ("graphics_picture_display_occurrences", []),
    )
    changed = False
    for attribute, default in defaults:
        if getattr(bp, attribute, default) == default:
            continue
        setattr(bp, attribute, default)
        changed = True
    return changed


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
) -> bool:
    """Attach the parser's graphics model and the SattLint correlation views.

    The parser has already scanned the companion file. This seam converts that
    model into the record shapes analyzers read, correlates records against the
    code picture, and records the workspace-dependent notices.
    """
    if graphics is None or companion_path is None:
        _clear_attached_graphics_companion(bp)
        return False

    def _record_timing(phase_name: str, started_at: float) -> None:
        if timing_sink is None:
            return
        timing_sink(owner_name, phase_name, perf_counter() - started_at)

    validate_started_at = perf_counter()
    result = validate_graphics_model(graphics, companion_path)
    _record_timing("validate-graphics-file", validate_started_at)

    bp.graphics_file = companion_path.name
    bp.graphics_bindings = list(result.bindings)
    bp.graphics_messages = list(result.messages)
    bp.graphics_composite_records = list(result.composite_records)

    composite_started_at = perf_counter()
    bp.graphics_composite_occurrences = list(correlate_composite_records(bp, result.composite_records, graph=graph))
    _record_timing("correlate-composites", composite_started_at)

    bp.graphics_picture_display_records = list(result.picture_display_records)
    picture_display_started_at = perf_counter()
    picture_display_occurrences = correlate_picture_display_records(
        bp,
        result.picture_display_records,
        graph=graph,
    )
    bp.graphics_picture_display_occurrences = list(picture_display_occurrences)
    _record_timing("correlate-picture-display", picture_display_started_at)

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
    return True
