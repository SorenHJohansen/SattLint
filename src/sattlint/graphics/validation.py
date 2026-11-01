"""Graphics companion validation for the SattLint view of a program.

The parser owns companion scanning: bindings, composite records, picture
display records, and the structural messages those scans produce. This module
turns the parser's ``GraphicsModel`` into the record shapes the analyzers
consume and adds the checks that need the local workspace: literal
PictureDisplay asset verification and the not-implemented asset warnings.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sattline_parser.api import parse_graphics_file, parse_graphics_text
from sattline_parser.models.ast_model import GraphicsBinding, SourceSpan
from sattline_parser.project import GraphicsCompositeRecord as ParserGraphicsCompositeRecord
from sattline_parser.project import GraphicsModel, GraphicsPathRow, GraphicsPictureDisplayRecord

__all__ = [
    "GraphicsCompositeRecord",
    "GraphicsValidationMessage",
    "GraphicsValidationResult",
    "PictureDisplayPathRow",
    "PictureDisplayRecord",
    "is_unimplemented_picture_display_asset_path",
    "unimplemented_picture_display_asset_message",
    "validate_graphics_file",
    "validate_graphics_model",
    "validate_graphics_text",
]


@dataclass(frozen=True, slots=True)
class GraphicsValidationMessage:
    severity: Literal["error", "warning"]
    message: str
    line: int
    column: int
    length: int = 1


@dataclass(frozen=True, slots=True)
class GraphicsValidationResult:
    messages: tuple[GraphicsValidationMessage, ...] = ()
    bindings: tuple[GraphicsBinding, ...] = ()
    composite_records: tuple[GraphicsCompositeRecord, ...] = ()
    picture_display_records: tuple[PictureDisplayRecord, ...] = ()

    @property
    def errors(self) -> tuple[GraphicsValidationMessage, ...]:
        return tuple(message for message in self.messages if message.severity == "error")

    @property
    def warnings(self) -> tuple[GraphicsValidationMessage, ...]:
        return tuple(message for message in self.messages if message.severity == "warning")


@dataclass(frozen=True, slots=True)
class PictureDisplayPathRow:
    record_index: int
    index_token: str
    index_value: int | None
    kind: Literal["literal", "variable", "variable_invalid"]
    raw_text: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class PictureDisplayRecord:
    record_index: int
    record_start_line: int
    record_end_line: int
    path_row_lines: tuple[int, ...] = ()
    path_rows: tuple[PictureDisplayPathRow, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphicsCompositeRecord:
    record_index: int
    record_start_line: int
    record_end_line: int
    family_code: str


def _candidate_asset_paths(file_path: Path, asset_name: str) -> tuple[Path, ...]:
    normalized_name = asset_name.replace("\\", "/")
    basename = Path(normalized_name).name
    candidates: list[Path] = []
    seen: set[str] = set()

    for parent in (file_path.parent, *file_path.parents):
        for candidate in (
            parent / normalized_name,
            parent / basename,
            parent / "scr" / normalized_name,
            parent / "scr" / basename,
        ):
            key = candidate.as_posix().casefold()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)

    return tuple(candidates)


def is_unimplemented_picture_display_asset_path(path_text: str) -> bool:
    stripped = path_text.strip()
    if not stripped:
        return False
    if stripped.casefold().startswith("scr:"):
        stripped = stripped[4:].strip()
    lowered = stripped.casefold()
    return lowered.endswith(".wmf") or lowered.endswith(".emf")


def unimplemented_picture_display_asset_message() -> str:
    return ".emf and .wmf resolution is not implemented"


def _validate_literal_path(
    file_path: Path,
    path_text: str,
    *,
    line: int,
    column: int,
) -> GraphicsValidationMessage | None:
    stripped = path_text.strip()
    if not stripped:
        return GraphicsValidationMessage(
            severity="error",
            message="PictureDisplay contains an empty literal path",
            line=line,
            column=column,
        )

    if stripped.casefold().startswith("scr:"):
        asset_name = stripped[4:].strip()
        if not asset_name:
            return GraphicsValidationMessage(
                severity="error",
                message="PictureDisplay asset path must include a file name after 'scr:'",
                line=line,
                column=column,
                length=len(stripped),
            )
        if is_unimplemented_picture_display_asset_path(stripped):
            return GraphicsValidationMessage(
                severity="warning",
                message=unimplemented_picture_display_asset_message(),
                line=line,
                column=column,
                length=len(stripped),
            )
        if any(candidate.exists() for candidate in _candidate_asset_paths(file_path, asset_name)):
            return None
        return GraphicsValidationMessage(
            severity="warning",
            message=f"PictureDisplay asset {stripped!r} could not be verified from this workspace",
            line=line,
            column=column,
            length=len(stripped),
        )

    if is_unimplemented_picture_display_asset_path(stripped):
        return GraphicsValidationMessage(
            severity="warning",
            message=unimplemented_picture_display_asset_message(),
            line=line,
            column=column,
            length=len(stripped),
        )

    return None


def _picture_display_path_row(row: GraphicsPathRow) -> PictureDisplayPathRow:
    return PictureDisplayPathRow(
        record_index=row.record_index,
        index_token=row.index_token,
        index_value=row.index_value,
        kind=row.kind,
        raw_text=row.raw_text,
        span=row.span,
    )


def _picture_display_record(record: GraphicsPictureDisplayRecord) -> PictureDisplayRecord:
    path_rows = tuple(_picture_display_path_row(row) for row in record.path_rows)
    return PictureDisplayRecord(
        record_index=record.record_index,
        record_start_line=record.start_line,
        record_end_line=record.end_line,
        path_row_lines=record.path_row_lines,
        path_rows=path_rows,
    )


def _composite_record(record: ParserGraphicsCompositeRecord) -> GraphicsCompositeRecord:
    return GraphicsCompositeRecord(
        record_index=record.record_index,
        record_start_line=record.start_line,
        record_end_line=record.end_line,
        family_code=record.family_code,
    )


def validate_graphics_model(model: GraphicsModel, file_path: Path) -> GraphicsValidationResult:
    """Convert a parser graphics model into the SattLint view.

    The conversion keeps the parser's order and messages, then verifies literal
    PictureDisplay asset paths against the workspace that contains ``file_path``.
    """
    messages = [
        GraphicsValidationMessage(
            severity=message.severity,
            message=message.message,
            line=message.line,
            column=message.column,
            length=message.length,
        )
        for message in model.messages
    ]
    picture_display_records = tuple(_picture_display_record(record) for record in model.picture_display_records)
    for record in picture_display_records:
        for path_row in record.path_rows:
            if path_row.kind != "literal":
                continue
            asset_message = _validate_literal_path(
                file_path,
                path_row.raw_text,
                line=path_row.span.line,
                column=path_row.span.column,
            )
            if asset_message is not None:
                messages.append(asset_message)

    return GraphicsValidationResult(
        messages=tuple(messages),
        bindings=model.bindings,
        composite_records=tuple(_composite_record(record) for record in model.composite_records),
        picture_display_records=picture_display_records,
    )


def validate_graphics_text(text: str, file_path: Path) -> GraphicsValidationResult:
    return validate_graphics_model(parse_graphics_text(text), file_path)


def validate_graphics_file(file_path: Path) -> GraphicsValidationResult:
    return validate_graphics_model(parse_graphics_file(file_path), file_path)
