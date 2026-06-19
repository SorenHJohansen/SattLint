"""Validation helpers for serialized SattLine graphics files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, cast

from lark import Tree
from lark.exceptions import LarkError

from sattline_parser.api import build_lark_parser, read_text_with_fallback
from sattline_parser.models.ast_model import GraphicsBinding, SourceSpan
from sattline_parser.transformer.sl_transformer import SLTransformer

_RECORD_FAMILY_CODE = "5"
_PICTURE_DISPLAY_SUBTYPE = "2"
_RECORD_TERMINATOR = "0"
_COMPOSITE_RECORD_FAMILIES = frozenset({"1", "2", "4", "5"})
_KEEP_SHAPE_VALUES = {"t", "f"}
_BINDING_LINE_RE = re.compile(r"(?<!\S)(Var|Expr|Lit)\s+(\S+)\s+(-?\d+)\s+")
_GRAPHICS_EXPR_KEYWORDS = {
    "and": "AND",
    "or": "OR",
    "not": "NOT",
    "if": "IF",
    "then": "THEN",
    "else": "ELSE",
    "elsif": "ELSIF",
    "endif": "ENDIF",
    "true": "True",
    "false": "False",
}
_GRAPHICS_EXPR_KEYWORD_RE = re.compile(
    r"\b(" + "|".join(sorted(_GRAPHICS_EXPR_KEYWORDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


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
    subtype: Literal["2"] = _PICTURE_DISPLAY_SUBTYPE
    path_row_lines: tuple[int, ...] = ()
    path_rows: tuple[PictureDisplayPathRow, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphicsCompositeRecord:
    record_index: int
    record_start_line: int
    record_end_line: int
    family_code: str


@lru_cache(maxsize=1)
def _graphics_expression_parser() -> Any:
    return build_lark_parser(start="expression")


def _unwrap_expression_root(node: object) -> object:
    if isinstance(node, Tree):
        tree = cast(Tree[object], node)
        children = cast(list[object], tree.children)
        if tree.data == "expression" and len(children) == 1:
            return children[0]
        return cast(object, tree)
    return node


def _offset_source_spans(node: object, *, line_offset: int, column_offset: int) -> None:
    seen: set[int] = set()

    def visit(current: object) -> None:
        current_id = id(current)

        if isinstance(current, dict):
            if current_id in seen:
                return
            seen.add(current_id)
            mapping = cast(dict[str, object], current)
            span = mapping.get("span")
            if isinstance(span, SourceSpan):
                mapping["span"] = SourceSpan(
                    line=line_offset + span.line - 1,
                    column=(column_offset + span.column - 1) if span.line == 1 else span.column,
                )
            for value in mapping.values():
                visit(value)
            return

        if isinstance(current, list):
            if current_id in seen:
                return
            seen.add(current_id)
            for value in cast(list[object], current):
                visit(value)
            return

        if isinstance(current, tuple):
            if current_id in seen:
                return
            seen.add(current_id)
            for value in cast(tuple[object, ...], current):
                visit(value)
            return

        children = getattr(current, "children", None)
        if isinstance(children, list):
            if current_id in seen:
                return
            seen.add(current_id)
            for value in cast(list[object], children):
                visit(value)
            return
        if isinstance(children, tuple):
            if current_id in seen:
                return
            seen.add(current_id)
            for value in cast(tuple[object, ...], children):
                visit(value)
            return

        node_dict = getattr(current, "__dict__", None)
        if isinstance(node_dict, dict):
            if current_id in seen:
                return
            seen.add(current_id)
            for value in cast(dict[str, object], node_dict).values():
                visit(value)

    visit(node)


def _coerce_graphics_literal(payload: str) -> object:
    lowered = payload.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"[+-]?\d+", payload):
        return int(payload)
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[Ee][+-]?\d+)?", payload):
        return float(payload)
    return payload


def _normalize_graphics_expression(payload: str) -> str:
    return _GRAPHICS_EXPR_KEYWORD_RE.sub(
        lambda match: _GRAPHICS_EXPR_KEYWORDS[match.group(0).casefold()],
        payload,
    )


def _parse_graphics_binding_match(
    row_text: str,
    *,
    line: int,
    match: re.Match[str],
) -> tuple[GraphicsBinding | None, tuple[GraphicsValidationMessage, ...]]:
    kind = match.group(1).casefold()
    raw_length = int(match.group(3))
    tail = row_text[match.end() :]
    if raw_length < 0:
        return None, ()

    raw_payload = tail[:raw_length] if raw_length <= len(tail) else tail
    payload = raw_payload.rstrip()
    if not payload:
        return None, ()

    payload_column = match.end() + 1
    span = SourceSpan(line=line, column=payload_column)
    if kind == "lit":
        return GraphicsBinding(kind=kind, raw_text=payload, value=_coerce_graphics_literal(payload), span=span), ()
    if kind == "var":
        return (
            GraphicsBinding(
                kind=kind,
                raw_text=payload,
                value={"var_name": payload, "span": span},
                span=span,
            ),
            (),
        )

    try:
        normalized_payload = _normalize_graphics_expression(payload)
        parsed = _unwrap_expression_root(
            SLTransformer().transform(_graphics_expression_parser().parse(normalized_payload))
        )
        _offset_source_spans(parsed, line_offset=line, column_offset=payload_column)
    except (LarkError, RuntimeError, TypeError, ValueError) as exc:
        return (
            GraphicsBinding(kind=kind, raw_text=payload, value=payload, span=span),
            (
                GraphicsValidationMessage(
                    severity="warning",
                    message=f"Could not parse graphics expression {payload!r}: {exc}",
                    line=line,
                    column=payload_column,
                    length=len(payload),
                ),
            ),
        )

    return GraphicsBinding(kind=kind, raw_text=payload, value=parsed, span=span), ()


def _parse_graphics_binding_line(
    row_text: str,
    *,
    line: int,
) -> tuple[tuple[GraphicsBinding, ...], tuple[GraphicsValidationMessage, ...]]:
    bindings: list[GraphicsBinding] = []
    messages: list[GraphicsValidationMessage] = []

    for match in _BINDING_LINE_RE.finditer(row_text):
        binding, binding_messages = _parse_graphics_binding_match(row_text, line=line, match=match)
        if binding is not None:
            bindings.append(binding)
        messages.extend(binding_messages)

    return tuple(bindings), tuple(messages)


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
