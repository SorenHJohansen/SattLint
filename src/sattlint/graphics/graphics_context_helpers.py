"""Shared graphics path and source-context helpers for engine syntax flows."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from lark.exceptions import UnexpectedInput

from sattlint.parser_api import BasePicture, LoadMode, source_text_for_parse
from sattlint.parser_api import parse_source_text as parser_core_parse_source_text
from sattlint.parser_api import resolve_graphics_companion_path as parser_resolve_graphics_companion_path

from ..models.project_graph import ProjectGraph
from ..validation.policy import validate_basepicture_strict
from ..validation.shared import ValidationNotice
from .picture_display_paths import (
    PictureDisplayOccurrence,
    PictureDisplayPathDiagnostic,
    diagnose_picture_display_paths,
    format_picture_display_path_diagnostic,
)

if TYPE_CHECKING:
    from ..core.syntax import CodeMode


def _parser_load_mode(mode: object | None) -> LoadMode:
    """Map a SattLint code mode value onto the parser's load mode.

    The code mode arrives as ``CodeMode``, its raw text, or nothing at all. An
    unknown value keeps the draft family, which is the permissive default the
    shell always used before the parser owned companion pairing.
    """
    if isinstance(mode, str):
        normalized = mode.strip().casefold()
    else:
        normalized = str(getattr(mode, "value", "") or "").strip().casefold()
    if normalized == "official":
        return LoadMode.OFFICIAL
    return LoadMode.DRAFT


def resolve_graphics_companion_path(
    source_path: Path,
    *,
    mode: CodeMode | str | None = None,
) -> Path | None:
    """Resolve the graphics companion belonging beside ``source_path``.

    The parser owns companion pairing: an official ``.x`` body pairs only with
    ``.y`` and a draft ``.s`` body only with ``.g``, a companion never crosses
    families, stems match ignoring case, and the companion always sits in the
    source file's own directory. A ``.g`` or ``.y`` input resolves to itself.
    """
    return parser_resolve_graphics_companion_path(Path(source_path), mode=_parser_load_mode(mode))


def picture_display_path_diagnostics(
    base_picture: BasePicture,
    occurrences: tuple[PictureDisplayOccurrence, ...],
    *,
    graph: ProjectGraph | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> tuple[PictureDisplayPathDiagnostic, ...]:
    """Diagnose PictureDisplay paths once for both the notices and the analyzer."""
    return diagnose_picture_display_paths(base_picture, occurrences, graph=graph, progress_callback=status_callback)


def picture_display_path_notices(
    diagnostics: tuple[PictureDisplayPathDiagnostic, ...],
) -> tuple[ValidationNotice, ...]:
    return tuple(
        ValidationNotice(
            message=format_picture_display_path_diagnostic(diagnostic),
            line=diagnostic.path_row.span.line,
            column=diagnostic.path_row.span.column,
            length=len(diagnostic.path_row.raw_text),
        )
        for diagnostic in diagnostics
    )


def picture_display_path_warnings(
    base_picture: BasePicture,
    occurrences: tuple[PictureDisplayOccurrence, ...],
    *,
    graph: ProjectGraph | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> tuple[ValidationNotice, ...]:
    return picture_display_path_notices(
        picture_display_path_diagnostics(base_picture, occurrences, graph=graph, status_callback=status_callback)
    )


def graphics_source_context_path(graphics_path: Path) -> Path | None:
    suffix = graphics_path.suffix.lower()
    candidates = (".s", ".x") if suffix == ".g" else (".x", ".s")
    for candidate_suffix in candidates:
        candidate = graphics_path.with_suffix(candidate_suffix)
        if candidate.exists():
            return candidate
    return None


def load_picture_display_source_context(source_path: Path) -> BasePicture | None:
    try:
        source_text = source_text_for_parse(source_path)
        basepic = parser_core_parse_source_text(source_text)
        validate_basepicture_strict(basepic)
        return basepic
    except (OSError, SyntaxError, UnexpectedInput, ValueError, RuntimeError):
        return None
