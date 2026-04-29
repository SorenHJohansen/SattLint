"""Lark transformer that builds the SattLine AST.

Split into responsibility-based mixins for maintainability.
"""

from __future__ import annotations

import re
from typing import Any, cast

from lark import Token, Transformer, Tree

__all__ = ["SLTransformer"]

from sattline_parser.models.ast_model import BasePicture, FloatLiteral, IntLiteral, SourceSpan

from ..grammar import constants as const
from ._expressions_mixin import _ExpressionsMixin
from ._graphics_interact_mixin import _GraphicsInteractMixin
from ._modules_mixin import _ModulesMixin
from ._sfc_mixin import _SFCMixin
from ._tokens_mixin import _TokensMixin


def _meta_span(meta: Any) -> SourceSpan | None:
    """Extract source span from Lark meta."""
    line = getattr(meta, "line", None)
    column = getattr(meta, "column", None)
    if line is None or column is None:
        return None
    return SourceSpan(line=int(line), column=int(column))


def _strip_quoted(s: str) -> str:
    """Strip quotes and unescape from a quoted string."""
    inner = s[1:-1] if len(s) >= 2 and s[0] == '"' and s[-1] == '"' else s
    return inner.replace('""', '"').rstrip("\n")


def _flatten_items(items):
    """Yield flat stream of items from possibly nested lists and Trees."""
    for it in items:
        if isinstance(it, list):
            yield from _flatten_items(it)
        elif isinstance(it, Tree) and it.data in (
            const.TREE_TAG_BASE_MODULE_BODY,
            const.TREE_TAG_MODULE_BODY,
        ):
            tree = cast(Tree, it)
            yield from _flatten_items(tree.children)
        else:
            yield it


def _is_tree(node: Any) -> bool:
    """Check if node is a Lark Tree."""
    return hasattr(node, "data") and hasattr(node, "children")


def _iter_tree_children(node: Any):
    """Iterate over children of a Tree node."""
    if _is_tree(node):
        yield from getattr(node, "children", [])


_PROGRAM_NAME_RE = re.compile(r",\s*name:\s*(\S+)", re.IGNORECASE)


def _extract_program_name_from_header_lines(tree: Tree) -> str | None:
    """Extract program name from the program_date_line header string."""
    for child in tree.children:
        if isinstance(child, Tree) and child.data == "program_date_line":
            for token in child.children:
                raw = str(token).strip('"')
                m = _PROGRAM_NAME_RE.search(raw)
                if m:
                    return m.group(1).strip()
    return None


class SLTransformer(_TokensMixin, _ExpressionsMixin, _SFCMixin, _ModulesMixin, _GraphicsInteractMixin, Transformer):
    """Lark transformer building SattLine AST from parsed grammar.

    Mixins provide grouped method implementations by responsibility:
    - _TokensMixin: token coercion and literal conversion
    - _ExpressionsMixin: expressions, values, and statements
    - _SFCMixin: sequence function chart nodes
    - _ModulesMixin: module definitions and layout
    - _GraphicsInteractMixin: graphics and interact object handling
    """

    def __init__(self):
        super().__init__()

    def _extract_coord_tails(self, nodes: list[Any]) -> list[Any]:
        """Extract coordinate tail annotations from nested node structure."""
        tails: list[Any] = []

        def visit(x: Any):
            if x is None or isinstance(x, Token):
                return
            if isinstance(x, IntLiteral | FloatLiteral | int | float | bool):
                return
            if isinstance(x, str):
                tails.append(x)
                return
            if isinstance(x, tuple):
                if len(x) == 2 and all(isinstance(v, int | float) for v in x):
                    return
                tails.append(x)
                return
            if isinstance(x, dict):
                if const.KEY_VAR_NAME in x:
                    tails.append(x)
                    return
                for value in x.values():
                    visit(value)
                return
            if isinstance(x, list):
                for value in x:
                    visit(value)
                return
            if _is_tree(x):
                for child in getattr(x, "children", []):
                    visit(child)

        for node in nodes:
            visit(node)
        return tails

    def _merge_tails(self, *tail_groups: list[Any]) -> list[Any]:
        """Merge multiple tail groups into a single flat list."""
        merged: list[Any] = []
        for group in tail_groups:
            for tail in group or []:
                merged.append(tail)
        return merged

    def _extract_coord_payloads(self, items: list[Any]) -> tuple[list[Any], list[Any]]:
        """Extract coordinates and tails from items."""
        coords: list[Any] = []
        tails: list[Any] = []
        for it in items:
            if isinstance(it, dict) and const.KEY_COORDS in it:
                coords.append(it[const.KEY_COORDS])
                tails.extend(it.get(const.KEY_TAILS) or [])
            elif isinstance(it, tuple):
                coords.append(it)
        return coords, tails

    def _extract_tailed_rule_payload(self, node: Any) -> Any | None:
        """Extract payload from a tailed grammar rule."""
        if not _is_tree(node):
            return None

        for child in reversed(getattr(node, "children", [])):
            if isinstance(child, Token):
                continue
            if _is_tree(child) and getattr(child, "data", None) == const.KEY_ENABLE_EXPRESSION:
                return child
            if isinstance(child, dict | tuple | str):
                return child
        return None

    def _collect_invar_enable_tails(self, nodes: list[Any]) -> list[Any]:
        """Find InVar_ trees and enable-expression tails in nested structure."""
        tails: list[Any] = []
        tailed_rules = {
            "format_string_tailed",
            "value_fraction_tailed",
            "width_tailed",
            "assign_colour_tailed",
            "colour_style_tailed",
        }

        def visit(x: Any):
            if x is None:
                return
            if isinstance(x, dict):
                if const.KEY_TAIL in x and x[const.KEY_TAIL] is not None:
                    tails.append(x[const.KEY_TAIL])
                if const.TREE_TAG_ENABLE in x and const.KEY_TAIL in x and x[const.KEY_TAIL] is not None:
                    tails.append(x[const.KEY_TAIL])
                for v in x.values():
                    visit(v)
                return
            if _is_tree(x):
                data = getattr(x, "data", None)
                if data in (
                    const.GRAMMAR_VALUE_INVAR_PREFIX,
                    const.KEY_ENABLE_EXPRESSION,
                    "invar_tail",
                ):
                    tails.append(x)
                elif data in tailed_rules:
                    payload = self._extract_tailed_rule_payload(x)
                    if payload is not None:
                        tails.append(payload)
                for ch in getattr(x, "children", []):
                    visit(ch)
                return
            if isinstance(x, list):
                for y in x:
                    visit(y)
                return

        for n in nodes:
            visit(n)
        return tails

    # ---------- top-level ----------

    def start(self, items) -> BasePicture:
        """Grammar start -> BasePicture root from parsed program."""
        program_name: str | None = None
        bp: BasePicture | None = None
        for it in items:
            if isinstance(it, Tree) and it.data == "header_lines":
                program_name = _extract_program_name_from_header_lines(it)
            elif isinstance(it, BasePicture):
                bp = it
        if bp is not None:
            bp.program_name = program_name
            return bp
        types = ", ".join(type(x).__name__ for x in items)
        raise ValueError(f"start expected a BasePicture; got: {types}")
