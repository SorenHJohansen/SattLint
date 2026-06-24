"""Lark transformer that builds the SattLine AST.

Split into responsibility-based mixins for maintainability.
"""

from __future__ import annotations

from typing import Any, TypeGuard, cast

from lark import Token, Transformer, Tree

from sattline_parser.models.ast_model import BasePicture, FloatLiteral, IntLiteral

from ..grammar import constants as const
from . import _module_shared as _module_shared
from ._expressions_mixin import ExpressionsMixin
from ._graphics_interact_mixin import GraphicsInteractMixin
from ._module_assembly_mixin import ModuleAssemblyMixin
from ._module_header_mixin import ModuleHeaderMixin
from ._module_layout_mixin import ModuleLayoutMixin
from ._module_shared import TransformerItem, TransformerTree, tree_children
from ._sfc_mixin import SFCMixin
from ._tokens_mixin import TokensMixin

__all__ = [
    "SLTransformer",
    "_extract_program_name_from_header_lines",
    "_is_tree",
    "_iter_tree_children",
    "_strip_quoted",
    "flatten_items",
    "meta_span",
]

flatten_items = _module_shared.flatten_items
meta_span = _module_shared.meta_span


def _is_tree(node: object) -> TypeGuard[TransformerTree]:
    """Check if node is a Lark Tree."""
    return hasattr(node, "data") and hasattr(node, "children")


def _iter_tree_children(node: object) -> tuple[TransformerItem, ...]:
    """Yield tree children when given a Tree-like node, otherwise return an empty tuple."""
    if not _is_tree(node):
        return ()
    return tuple(tree_children(node))


def _strip_quoted(text: str) -> str:
    """Remove wrapping double quotes and unescape doubled inner quotes."""
    if len(text) >= 2 and text.startswith('"') and text.endswith('"'):
        return text[1:-1].replace('""', '"').rstrip("\n")
    return text


_EXPORTED_HELPERS = (flatten_items, _iter_tree_children, meta_span, _strip_quoted)


def _extract_program_name_from_header_lines(tree: TransformerTree) -> str | None:
    """Extract program name from the program_date_line header string."""
    for child in tree_children(tree):
        if _is_tree(child) and child.data == "program_date_line":
            for token in _iter_tree_children(child):
                raw = _strip_quoted(str(token))
                for field in raw.split(","):
                    name, separator, value = field.partition(":")
                    if separator and name.strip().casefold() == "name":
                        program_name = value.strip()
                        if program_name:
                            return program_name
    return None


class SLTransformer(
    TokensMixin,
    ExpressionsMixin,
    SFCMixin,
    ModuleHeaderMixin,
    ModuleAssemblyMixin,
    ModuleLayoutMixin,
    GraphicsInteractMixin,
    Transformer[Any, Any],
):
    """Lark transformer building SattLine AST from parsed grammar.

    Mixins provide grouped method implementations by responsibility:
    - TokensMixin: token coercion and literal conversion
    - ExpressionsMixin: expressions, values, and statements
    - SFCMixin: sequence function chart nodes
    - ModuleHeaderMixin: module headers and invocation argument metadata
    - ModuleAssemblyMixin: module-body normalization and AST assembly
    - ModuleLayoutMixin: layout, coordinates, and ModuleDef parsing
    - GraphicsInteractMixin: graphics and interact object handling
    """

    def __init__(self) -> None:
        super().__init__()

    def _extract_coord_tails(self, nodes: list[TransformerItem]) -> list[object]:
        """Extract coordinate tail annotations from nested node structure."""
        tails: list[object] = []

        def visit(value: object) -> None:
            if value is None or isinstance(value, Token):
                return
            if isinstance(value, IntLiteral | FloatLiteral | int | float | bool):
                return
            if isinstance(value, str):
                tails.append(value)
                return
            if isinstance(value, tuple):
                tuple_value = cast(tuple[object, ...], value)
                if len(tuple_value) == 2 and all(isinstance(item, int | float) for item in tuple_value):
                    return
                tails.append(tuple_value)
                return
            if isinstance(value, dict):
                payload = cast(dict[str, object], value)
                if const.KEY_VAR_NAME in payload:
                    tails.append(payload)
                    return
                for nested in payload.values():
                    visit(nested)
                return
            if isinstance(value, list):
                for nested in cast(list[object], value):
                    visit(nested)
                return
            if _is_tree(value):
                for child in tree_children(value):
                    visit(child)

        for node in nodes:
            visit(node)
        return tails

    def _merge_tails(self, *tail_groups: list[object]) -> list[object]:
        """Merge multiple tail groups into a single flat list."""
        merged: list[object] = []
        for group in tail_groups:
            merged.extend(group)
        return merged

    def _extract_coord_payloads(self, items: list[TransformerItem]) -> tuple[list[object], list[object]]:
        """Extract coordinates and tails from items."""
        coords: list[object] = []
        tails: list[object] = []
        for item in items:
            if isinstance(item, dict) and const.KEY_COORDS in item:
                payload = cast(dict[str, object], item)
                coords.append(payload[const.KEY_COORDS])
                raw_tails = payload.get(const.KEY_TAILS)
                if isinstance(raw_tails, list):
                    tails.extend(cast(list[object], raw_tails))
            elif isinstance(item, tuple):
                coords.append(cast(tuple[object, ...], item))
        return coords, tails

    def _extract_tailed_rule_payload(self, node: object) -> object | None:
        """Extract payload from a tailed grammar rule."""
        if not _is_tree(node):
            return None

        for child in reversed(tree_children(node)):
            if isinstance(child, Token):
                continue
            if _is_tree(child) and getattr(child, "data", None) == const.KEY_ENABLE_EXPRESSION:
                return child
            if isinstance(child, dict | tuple | str):
                return cast(object, child)
        return None

    def _collect_invar_enable_tails(self, nodes: list[TransformerItem]) -> list[object]:
        """Find InVar_ trees and enable-expression tails in nested structure."""
        tails: list[object] = []
        tailed_rules = {
            "format_string_tailed",
            "value_fraction_tailed",
            "width_tailed",
            "assign_colour_tailed",
            "colour_style_tailed",
        }

        def visit(value: object) -> None:
            if value is None:
                return
            if isinstance(value, dict):
                payload = cast(dict[str, object], value)
                if const.KEY_TAIL in payload and payload[const.KEY_TAIL] is not None:
                    tails.append(payload[const.KEY_TAIL])
                if (
                    const.TREE_TAG_ENABLE in payload
                    and const.KEY_TAIL in payload
                    and payload[const.KEY_TAIL] is not None
                ):
                    tails.append(payload[const.KEY_TAIL])
                for nested in payload.values():
                    visit(nested)
                return
            if _is_tree(value):
                data = getattr(value, "data", None)
                if data in (
                    const.GRAMMAR_VALUE_INVAR_PREFIX,
                    const.KEY_ENABLE_EXPRESSION,
                    "invar_tail",
                ):
                    tails.append(value)
                elif data in tailed_rules:
                    payload = self._extract_tailed_rule_payload(value)
                    if payload is not None:
                        tails.append(payload)
                for child in tree_children(value):
                    visit(child)
                return
            if isinstance(value, list):
                for nested in cast(list[object], value):
                    visit(nested)

        for node in nodes:
            visit(node)
        return tails

    def start(self, items: list[TransformerItem]) -> BasePicture:
        """Grammar start -> BasePicture root from parsed program."""
        program_name: str | None = None
        base_picture: BasePicture | None = None
        for item in items:
            if isinstance(item, Tree) and item.data == "header_lines":
                program_name = _extract_program_name_from_header_lines(cast(TransformerTree, item))
            elif isinstance(item, BasePicture):
                base_picture = item
        if base_picture is not None:
            base_picture.program_name = program_name
            return base_picture
        types = ", ".join(type(item).__name__ for item in items)
        raise ValueError(f"start expected a BasePicture; got: {types}")
