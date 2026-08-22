# pyright: reportPrivateUsage=false
"""Validation helpers for serialized SattLine graphics files."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from sattline_parser.api import read_text_with_fallback
from sattline_parser.models.ast_model import GraphicsBinding, SourceSpan

from ._graphics_validation_bindings import (
    _BINDING_LINE_RE,
    _COMPOSITE_RECORD_FAMILIES,
    _KEEP_SHAPE_VALUES,
    _PICTURE_DISPLAY_SUBTYPE,
    _RECORD_FAMILY_CODE,
    _RECORD_TERMINATOR,
    GraphicsCompositeRecord,
    GraphicsValidationMessage,
    GraphicsValidationResult,
    PictureDisplayPathRow,
    PictureDisplayRecord,
    _parse_graphics_binding_line,
    _parse_graphics_binding_match,
)


def _nonempty_record_lines(lines: list[str], start_index: int, end_index: int) -> list[tuple[int, str]]:
    return [
        (line_index, lines[line_index]) for line_index in range(start_index, end_index) if lines[line_index].strip()
    ]


def _find_record_end(lines: list[str], start_index: int) -> int | None:
    for line_index in range(start_index + 1, len(lines)):
        if lines[line_index].strip() != _RECORD_TERMINATOR:
            continue
        if line_index + 1 >= len(lines) or not lines[line_index + 1].strip():
            return line_index
    return None


def _extract_literal_path(row_text: str) -> str | None:
    parts = row_text.strip().split(None, 1)
    if len(parts) != 2:
        return None

    payload = parts[1].strip()
    if not payload or payload.startswith(("Var ", "Lit ", "None ")):
        return None

    nested_parts = payload.split(None, 1)
    if len(nested_parts) == 2 and nested_parts[0].lstrip("+-").isdigit():
        payload = nested_parts[1].strip()

    return payload or None


def _split_nested_picture_display_payload(payload: str) -> tuple[str | None, str]:
    nested_parts = payload.split(None, 1)
    if len(nested_parts) != 2:
        return None, payload
    nested_index_token, nested_payload = nested_parts
    if not nested_index_token.lstrip("+-").isdigit():
        return None, payload
    return nested_index_token, nested_payload.strip()


def _parse_picture_display_row(
    row_text: str,
    *,
    record_index: int,
    line: int,
) -> PictureDisplayPathRow | None:
    stripped = row_text.strip()
    if not stripped:
        return None

    parts = stripped.split(None, 1)
    if len(parts) != 2:
        return None

    index_token, payload = parts
    index_value = int(index_token) if index_token.lstrip("+-").isdigit() else None
    payload = payload.strip()
    if not payload:
        return None

    binding_payload = payload
    nested_index_token: str | None = None
    binding_match = _BINDING_LINE_RE.match(binding_payload)
    if binding_match is None:
        nested_index_token, binding_payload = _split_nested_picture_display_payload(payload)
        binding_match = _BINDING_LINE_RE.match(binding_payload)
    if binding_match is not None:
        binding_meta = binding_match.group(2).casefold()
        if binding_meta == "invalid":
            if nested_index_token is None:
                return None
            row_kind: Literal["variable", "variable_invalid"] = "variable_invalid"
        elif binding_meta not in {"true", "false"} and not binding_meta.lstrip("+-").isdigit():
            return None
        else:
            row_kind = "variable"
        binding, _binding_messages = _parse_graphics_binding_match(binding_payload, line=line, match=binding_match)
        if binding is None or binding.kind != "var":
            return None
        column = row_text.find(binding.raw_text)
        span = SourceSpan(line=line, column=(column + 1) if column >= 0 else 1)
        return PictureDisplayPathRow(
            record_index=record_index,
            index_token=index_token,
            index_value=index_value,
            kind=row_kind,
            raw_text=binding.raw_text,
            span=span,
        )

    literal_path = _extract_literal_path(row_text)
    if literal_path is None:
        return None
    column = row_text.find(literal_path)
    return PictureDisplayPathRow(
        record_index=record_index,
        index_token=index_token,
        index_value=index_value,
        kind="literal",
        raw_text=literal_path,
        span=SourceSpan(line=line, column=(column + 1) if column >= 0 else 1),
    )


def _extract_picture_display_record(
    record_lines: list[tuple[int, str]],
    *,
    record_index: int,
    record_start_line: int,
    record_end_line: int,
) -> PictureDisplayRecord:
    path_row_lines = tuple(row_line_index + 1 for row_line_index, _row_line in record_lines[5:-2])
    path_rows = tuple(
        row
        for row_line_index, row_line in record_lines[5:-2]
        if (row := _parse_picture_display_row(row_line, record_index=record_index, line=row_line_index + 1)) is not None
    )
    return PictureDisplayRecord(
        record_index=record_index,
        record_start_line=record_start_line,
        record_end_line=record_end_line,
        path_row_lines=path_row_lines,
        path_rows=path_rows,
    )


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


def validate_graphics_text(text: str, file_path: Path) -> GraphicsValidationResult:
    lines = text.splitlines()
    messages: list[GraphicsValidationMessage] = []
    bindings: list[GraphicsBinding] = []
    composite_records: list[GraphicsCompositeRecord] = []
    picture_display_records: list[PictureDisplayRecord] = []

    for line_number, line_text in enumerate(lines, start=1):
        row_bindings, binding_messages = _parse_graphics_binding_line(line_text, line=line_number)
        bindings.extend(row_bindings)
        messages.extend(binding_messages)

    line_index = 0
    record_index = 0

    while line_index < len(lines):
        family_code = lines[line_index].strip()
        if family_code not in _COMPOSITE_RECORD_FAMILIES:
            line_index += 1
            continue

        record_end = _find_record_end(lines, line_index)
        if record_end is None:
            messages.append(
                GraphicsValidationMessage(
                    severity="error",
                    message="Unterminated graphics record; expected trailing '0' line",
                    line=line_index + 1,
                    column=1,
                )
            )
            break

        record_index += 1
        composite_records.append(
            GraphicsCompositeRecord(
                record_index=record_index,
                record_start_line=line_index + 1,
                record_end_line=record_end + 1,
                family_code=family_code,
            )
        )

        if family_code != _RECORD_FAMILY_CODE:
            line_index = record_end + 1
            continue

        record_lines = _nonempty_record_lines(lines, line_index + 1, record_end)
        if len(record_lines) < 6:
            line_index = record_end + 1
            continue

        subtype_line_index, subtype_line = record_lines[3]
        if subtype_line.strip() != _PICTURE_DISPLAY_SUBTYPE:
            line_index = record_end + 1
            continue

        keep_shape_line_index, keep_shape_line = record_lines[-1]
        if keep_shape_line.strip().casefold() not in _KEEP_SHAPE_VALUES:
            messages.append(
                GraphicsValidationMessage(
                    severity="error",
                    message="PictureDisplay record is missing the trailing KeepPictureShape flag",
                    line=subtype_line_index + 1,
                    column=1,
                )
            )
            line_index = record_end + 1
            continue

        picture_display_record = _extract_picture_display_record(
            record_lines,
            record_index=record_index,
            record_start_line=line_index + 1,
            record_end_line=record_end + 1,
        )
        picture_display_records.append(picture_display_record)

        for path_row in picture_display_record.path_rows:
            if path_row.kind != "literal":
                continue
            message = _validate_literal_path(
                file_path,
                path_row.raw_text,
                line=path_row.span.line,
                column=path_row.span.column,
            )
            if message is not None:
                messages.append(message)

        line_index = keep_shape_line_index + 1

    return GraphicsValidationResult(
        messages=tuple(messages),
        bindings=tuple(bindings),
        composite_records=tuple(composite_records),
        picture_display_records=tuple(picture_display_records),
    )


def validate_graphics_file(file_path: Path) -> GraphicsValidationResult:
    text = read_text_with_fallback(file_path)
    return validate_graphics_text(text, file_path)
