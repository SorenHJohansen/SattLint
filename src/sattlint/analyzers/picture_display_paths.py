from __future__ import annotations

from sattline_parser.models.ast_model import BasePicture

from ..models.project_graph import ProjectGraph
from ..picture_display_paths import diagnose_picture_display_paths, format_picture_display_path_diagnostic
from .framework import Issue, SimpleReport


def analyze_picture_display_paths(
    base_picture: BasePicture,
    *,
    graph: ProjectGraph | None = None,
    analyzed_target_is_library: bool = False,
) -> SimpleReport:
    occurrences = tuple(getattr(base_picture, "graphics_picture_display_occurrences", ()) or ())
    diagnostics = diagnose_picture_display_paths(base_picture, occurrences, graph=graph)
    issues = [
        Issue(
            kind="picture_display_paths.unresolved",
            message=format_picture_display_path_diagnostic(diagnostic),
            module_path=list(diagnostic.occurrence.declaring_module_path),
            severity="info" if analyzed_target_is_library else None,
            data={
                "program_name": diagnostic.occurrence.program_name,
                "path": diagnostic.path_row.raw_text,
                "record_index": diagnostic.occurrence.record.record_index,
                "failure_reason": diagnostic.resolution.failure_reason,
                "detail": diagnostic.resolution.detail,
            },
        )
        for diagnostic in diagnostics
    ]
    return SimpleReport(name=base_picture.header.name, issues=issues)


__all__ = ["analyze_picture_display_paths"]
