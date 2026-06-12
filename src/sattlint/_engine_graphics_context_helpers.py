"""Shared graphics path and source-context helpers for engine syntax flows."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeGuard

from lark.exceptions import UnexpectedInput

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.api import read_text_with_fallback
from sattline_parser.grammar.parser_decode import is_compressed, preprocess_sl_text
from sattline_parser.models.ast_model import BasePicture

from ._validation_shared import ValidationNotice
from .models.project_graph import ProjectGraph
from .picture_display_paths import (
    PictureDisplayOccurrence,
    diagnose_picture_display_paths,
    format_picture_display_path_diagnostic,
)
from .validation import validate_transformed_basepicture

if TYPE_CHECKING:
    from ._engine_syntax_helpers import CodeMode


class _HasStringValue(Protocol):
    value: str


def _has_string_value(mode: object) -> TypeGuard[_HasStringValue]:
    return isinstance(getattr(mode, "value", None), str)


def _normalized_mode_value(mode: object | None) -> str | None:
    if mode is None:
        return None

    if isinstance(mode, str):
        mode_text = mode.strip().lower()
        return mode_text or None

    if _has_string_value(mode):
        mode_text = mode.value.strip().lower()
        return mode_text or None

    return None


def resolve_graphics_companion_path(
    source_path: Path,
    *,
    mode: CodeMode | str | None = None,
) -> Path | None:
    target_path = Path(source_path)
    if target_path.suffix.lower() in {".g", ".y"}:
        return target_path

    resolved_mode = _normalized_mode_value(mode)
    if resolved_mode == "official" or target_path.suffix.lower() == ".x":
        candidate_extensions = (".y",)
    else:
        candidate_extensions = (".g", ".y")

    for extension in candidate_extensions:
        candidate = target_path.with_suffix(extension)
        if candidate.exists():
            return candidate

    return None


def picture_display_path_warnings(
    base_picture: BasePicture,
    occurrences: tuple[PictureDisplayOccurrence, ...],
    *,
    graph: ProjectGraph | None = None,
) -> tuple[ValidationNotice, ...]:
    diagnostics = diagnose_picture_display_paths(base_picture, occurrences, graph=graph)
    return tuple(
        ValidationNotice(
            message=format_picture_display_path_diagnostic(diagnostic),
            line=diagnostic.path_row.span.line,
            column=diagnostic.path_row.span.column,
            length=len(diagnostic.path_row.raw_text),
        )
        for diagnostic in diagnostics
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
        source_text = read_text_with_fallback(source_path)
        if is_compressed(source_text):
            source_text, _ = preprocess_sl_text(source_text)
        basepic = parser_core_parse_source_text(source_text)
        validate_transformed_basepicture(
            basepic,
            allow_old_state_assignment=source_path.suffix.lower() in {".x", ".z"},
            allow_unresolved_external_datatypes=source_path.suffix.lower() in {".x", ".z"},
        )
        return basepic
    except (OSError, SyntaxError, UnexpectedInput, ValueError, RuntimeError):
        return None
