"""Validation helpers for serialized SattLine graphics files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_RECORD_FAMILY_CODE = "5"
_PICTURE_DISPLAY_SUBTYPE = "2"
_RECORD_TERMINATOR = "0"
_KEEP_SHAPE_VALUES = {"t", "f"}


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

    @property
    def errors(self) -> tuple[GraphicsValidationMessage, ...]:
        return tuple(message for message in self.messages if message.severity == "error")

    @property
    def warnings(self) -> tuple[GraphicsValidationMessage, ...]:
        return tuple(message for message in self.messages if message.severity == "warning")


def _nonempty_record_lines(lines: list[str], start_index: int, end_index: int) -> list[tuple[int, str]]:
    return [
        (line_index, lines[line_index])
        for line_index in range(start_index, end_index)
        if lines[line_index].strip()
    ]


def _find_record_end(lines: list[str], start_index: int) -> int | None:
    for line_index in range(start_index + 1, len(lines)):
        if lines[line_index].strip() == _RECORD_TERMINATOR:
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
        if any(candidate.exists() for candidate in _candidate_asset_paths(file_path, asset_name)):
            return None
        return GraphicsValidationMessage(
            severity="warning",
            message=f"PictureDisplay asset {stripped!r} could not be verified from this workspace",
            line=line,
            column=column,
            length=len(stripped),
        )

    return None


def validate_graphics_text(text: str, file_path: Path) -> GraphicsValidationResult:
    lines = text.splitlines()
    messages: list[GraphicsValidationMessage] = []
    line_index = 0

    while line_index < len(lines):
        if lines[line_index].strip() != _RECORD_FAMILY_CODE:
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

        for row_line_index, row_line in record_lines[5:-2]:
            literal_path = _extract_literal_path(row_line)
            if literal_path is None:
                continue
            column = row_line.find(literal_path)
            message = _validate_literal_path(
                file_path,
                literal_path,
                line=row_line_index + 1,
                column=(column + 1) if column >= 0 else 1,
            )
            if message is not None:
                messages.append(message)

        line_index = keep_shape_line_index + 1

    return GraphicsValidationResult(messages=tuple(messages))


def validate_graphics_file(file_path: Path) -> GraphicsValidationResult:
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = file_path.read_text(encoding="cp1252")
    return validate_graphics_text(text, file_path)
