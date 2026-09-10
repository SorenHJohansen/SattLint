"""Span-normalized structural normalization for SattLine AST nodes.

The semantic diff compares *meaningful* structure, not exact parse output.
All AST nodes carry ``SourceSpan`` (and layout) fields that differ between two
files purely because of formatting or geometry. This module produces a
canonical, hashable fingerprint of any AST value with those fields stripped, so
two semantically equal snippets normalize to equal fingerprints while genuine
logic changes produce different fingerprints.

Only the external ``sattline_parser`` AST model is understood here; the module
is otherwise generic dataclass traversal.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from typing import cast

_IGNORED_FIELDS = frozenset(
    {
        "span",
        "declaration_span",
        "position",
        "size",
        "invoke_coord",
        "invoke_coord_tails",
        "clipping_bounds",
        "zoom_limits",
        "zoomable",
        "grid",
        "seq_layers",
        "layer_info",
        "enable_tail",
        "datecode",
        "description",
        "trailing_comments",
        "description_comments",
    }
)


def _field_is_ignored(name: str) -> bool:
    return name in _IGNORED_FIELDS


def normalize_ast_value(value: object) -> object:
    """Return a canonical, hashable fingerprint with spans/layout stripped."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, Enum):
        return ("enum", type(value).__name__, value.name)

    if isinstance(value, tuple):
        typed_items = cast(tuple[object, ...], value)
        return ("tuple", tuple(normalize_ast_value(item) for item in typed_items))

    if isinstance(value, list):
        typed_items = cast(list[object], value)
        return ("list", tuple(normalize_ast_value(item) for item in typed_items))

    if isinstance(value, dict):
        typed_items = cast(dict[object, object], value)
        normalized_items = tuple(
            sorted((normalize_ast_value(key), normalize_ast_value(item)) for key, item in typed_items.items())
        )
        return ("dict", normalized_items)

    if is_dataclass(value) and not isinstance(value, type):
        normalized_fields = tuple(
            sorted(
                (field.name, normalize_ast_value(getattr(value, field.name)))
                for field in fields(value)
                if not _field_is_ignored(field.name)
            )
        )
        return ("dc", type(value).__name__, normalized_fields)

    return ("other", type(value).__name__, repr(value))


def _field_value(fields: tuple[tuple[str, object], ...], name: str) -> object | None:
    for field_name, value in fields:
        if field_name == name:
            return value
    return None


def _primitive_shape(value: object) -> object:
    return ("value", type(value).__name__)


def statement_shape(fingerprint: object) -> object:
    """Coarse structural shape of a statement fingerprint.

    Leaf expression values are collapsed to their type so that two statements
    with the same skeleton but different literal/expression values share a
    shape. Equal shapes classify a change as expression-level; differing shapes
    classify it as a statement-level change.
    """
    if not isinstance(fingerprint, tuple):
        return _primitive_shape(fingerprint)
    if not fingerprint:
        return ("value", "tuple")

    typed = cast(tuple[object, ...], fingerprint)
    kind = typed[0]
    if kind == "dc" and len(typed) == 3:
        node_kind = str(typed[1])
        raw_fields = typed[2]
        field_items: tuple[tuple[str, object], ...] = (
            cast(tuple[tuple[str, object], ...], raw_fields) if isinstance(raw_fields, tuple) else ()
        )
        if node_kind == "VarRef":
            return ("varref", _field_value(field_items, "name"))
        if node_kind == "Assignment":
            return (
                "assignment",
                statement_shape(_field_value(field_items, "target")),
                statement_shape(_field_value(field_items, "value")),
            )
        if node_kind == "FuncCallStmt":
            return ("callstmt", statement_shape(_field_value(field_items, "call")))
        if node_kind == "IfStmt":
            return (
                "if",
                statement_shape(_field_value(field_items, "branches")),
                statement_shape(_field_value(field_items, "else_block")),
            )
        if node_kind == "FuncCall":
            raw_args = _field_value(field_items, "args")
            args = cast(tuple[object, ...], raw_args) if isinstance(raw_args, tuple) else ()
            return ("call", _field_value(field_items, "name"), len(args))
        if node_kind in {"BoolOp", "NotOp", "Compare", "BinOp", "UnaryOp", "TernaryOp"}:
            return ("expr", node_kind, statement_shape(_field_value(field_items, "op")))
        return ("dc", node_kind, tuple(statement_shape(value) for _, value in field_items))

    if kind in {"tuple", "list"} and len(typed) == 2:
        raw_items = typed[1]
        items = cast(tuple[object, ...], raw_items) if isinstance(raw_items, tuple) else ()
        return (kind, tuple(statement_shape(value) for value in items))

    if kind == "dict" and len(typed) == 2:
        raw_items = typed[1]
        if not isinstance(raw_items, tuple):
            return ("dict", ())
        items = cast(tuple[tuple[object, object], ...], raw_items)
        return ("dict", tuple(sorted((statement_shape(key), statement_shape(value)) for key, value in items)))

    if kind == "enum":
        return ("enum", typed[1])

    return ("other", kind)
