"""Graphics validation record models and binding parsing helpers."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal, cast

from lark import Tree
from lark.exceptions import LarkError
from sattline_parser.api import build_lark_parser
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


def _offset_source_spans(node: object, *, line_offset: int, column_offset: int) -> object:
    seen: set[int] = set()

    def offset_span(span: object) -> object:
        if not isinstance(span, SourceSpan):
            return span
        return SourceSpan(
            line=line_offset + span.line - 1,
            column=(column_offset + span.column - 1) if span.line == 1 else span.column,
        )

    def visit(current: Any) -> Any:
        current_id = id(current)
        if current_id in seen:
            return current
        seen.add(current_id)
        return _offset_source_spans_inner(current, line_offset=line_offset, column_offset=column_offset)

    def _offset_source_spans_inner(current: Any, *, line_offset: int, column_offset: int) -> Any:
        if isinstance(current, dict):
            mapping = cast(dict[str, Any], current)
            raw_span = mapping.get("span")
            if isinstance(raw_span, SourceSpan):
                mapping["span"] = offset_span(raw_span)
            for key, value in mapping.items():
                if key != "span":
                    mapping[key] = visit(value)
            return current  # pyright: ignore[reportUnknownVariableType]

        if isinstance(current, list):
            for index, value in enumerate(cast(list[Any], current)):
                cast(list[Any], current)[index] = visit(value)
            return current  # pyright: ignore[reportUnknownVariableType]

        if isinstance(current, tuple):
            return tuple(visit(value) for value in cast(tuple[Any, ...], current))

        if isinstance(current, Tree):
            tree = cast(Tree[Any], current)
            for index, value in enumerate(cast(list[Any], tree.children)):
                cast(list[Any], tree.children)[index] = visit(value)
            return current  # pyright: ignore[reportUnknownVariableType]

        children = getattr(current, "children", None)
        if isinstance(children, list | tuple):
            raw_children = cast(list[Any] | tuple[Any, ...], children)
            rebuilt_children = [visit(value) for value in raw_children]
            if all(new is old for new, old in zip(rebuilt_children, raw_children, strict=True)):
                return current
            try:
                current.children = rebuilt_children
            except (AttributeError, TypeError):
                return current
            return current

        if dataclasses.is_dataclass(current) and not isinstance(current, type):
            field_map: dict[str, Any] = {}
            changed = False
            for field in dataclasses.fields(current):
                value = getattr(current, field.name)
                offset_value = offset_span(value) if field.name == "span" else visit(value)
                if offset_value is not value:
                    changed = True
                field_map[field.name] = offset_value
            if not changed:
                return current
            try:
                return dataclasses.replace(current, **field_map)
            except TypeError:
                return current

        node_dict = getattr(current, "__dict__", None)
        if isinstance(node_dict, dict):
            for key, value in cast(dict[str, Any], node_dict).items():
                cast(dict[str, Any], node_dict)[key] = visit(value)
            return current

        return current

    return visit(node)


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
        parsed = _offset_source_spans(parsed, line_offset=line, column_offset=payload_column)
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


__all__ = [
    "GraphicsCompositeRecord",
    "GraphicsValidationMessage",
    "GraphicsValidationResult",
    "PictureDisplayPathRow",
    "PictureDisplayRecord",
    "_normalize_graphics_expression",
    "_offset_source_spans",
    "_parse_graphics_binding_line",
    "_parse_graphics_binding_match",
    "_unwrap_expression_root",
]
