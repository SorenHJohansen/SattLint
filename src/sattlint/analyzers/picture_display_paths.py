from __future__ import annotations

from sattline_parser.models.ast_model import BasePicture

from ..graphics.picture_display_paths import diagnose_picture_display_paths, format_picture_display_path_diagnostic
from ..models.project_graph import ProjectGraph
from .framework import Issue, SimpleReport


def _is_library_suppressed(diagnostic: object, *, analyzed_target_is_library: bool) -> bool:
    if not analyzed_target_is_library:
        return False
    resolution = getattr(diagnostic, "resolution", None)
    failure_reason = getattr(resolution, "failure_reason", None)
    if failure_reason == "missing_program":
        return True
    return failure_reason == "missing_parent"


def analyze_picture_display_paths(
    base_picture: BasePicture,
    *,
    graph: ProjectGraph | None = None,
    analyzed_target_is_library: bool = False,
) -> SimpleReport:
    occurrences = tuple(getattr(base_picture, "graphics_picture_display_occurrences", ()) or ())
    diagnostics = diagnose_picture_display_paths(base_picture, occurrences, graph=graph)
    issues: list[Issue] = []
    for diagnostic in diagnostics:
        if _is_library_suppressed(diagnostic, analyzed_target_is_library=analyzed_target_is_library):
            continue
        module_path = list(diagnostic.occurrence.declaring_module_path)
        is_above_base = (
            diagnostic.resolution.failure_reason == "missing_parent"
            and diagnostic.resolution.detail == "path stepped above BasePicture"
        )
        kind = "picture_display_paths.above_base" if is_above_base else "picture_display_paths.unresolved"
        issues.append(
            Issue(
                kind=kind,
                message=(
                    f"PictureDisplay path {diagnostic.path_row.raw_text!r} escapes above the base picture "
                    "of the declaring module."
                    if is_above_base
                    else format_picture_display_path_diagnostic(diagnostic)
                ),
                module_path=module_path,
                data={
                    "program_name": diagnostic.occurrence.program_name,
                    "path": diagnostic.path_row.raw_text,
                    "record_index": diagnostic.occurrence.record.record_index,
                    "failure_reason": diagnostic.resolution.failure_reason,
                    "detail": diagnostic.resolution.detail,
                    "site": ".".join(module_path),
                    "context": diagnostic.path_row.raw_text,
                },
            )
        )
    return SimpleReport(name=base_picture.header.name, issues=issues)


__all__ = ["analyze_picture_display_paths"]
