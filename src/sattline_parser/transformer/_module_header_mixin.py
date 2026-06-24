"""Module header parsing helpers for the SattLine transformer."""

# ruff: noqa: N802

from __future__ import annotations

from typing import Any, cast

from lark import Token, Tree

from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import ModuleHeader

from ._module_shared import TransformerItem, TransformerTree, float_tuple, meta_span, v_args


def _normalize_module_header_tail(value: object) -> object:
    if not isinstance(value, Tree):
        return value

    tree_value = cast(Tree[object], value)
    if tree_value.data not in (
        const.GRAMMAR_VALUE_INVAR_PREFIX,
        const.GRAMMAR_VALUE_OUTVAR_PREFIX,
        "invar_tail",
    ):
        return cast(object, tree_value)
    if len(tree_value.children) != 1:
        return cast(object, tree_value)

    child = tree_value.children[0]
    if isinstance(child, Token):
        return cast(object, tree_value)
    return cast(object, child)


def _collect_module_header_argument_tails(value: object) -> list[object]:
    tails: list[object] = []

    def visit(node: object) -> None:
        if node is None or isinstance(node, Token):
            return
        if isinstance(node, dict):
            payload = cast(dict[str, object], node)
            if const.TREE_TAG_ENABLE in payload:
                return
            tail_obj = payload.get(const.KEY_TAIL)
            if tail_obj is not None:
                tails.append(_normalize_module_header_tail(tail_obj))
                return
            assign_payload = payload.get(const.KEY_ASSIGN)
            if assign_payload is not None:
                visit(assign_payload)
                return
            for nested in payload.values():
                visit(nested)
            return
        if isinstance(node, Tree):
            tree_node = cast(Tree[object], node)
            data = tree_node.data
            if data in (
                const.GRAMMAR_VALUE_INVAR_PREFIX,
                const.GRAMMAR_VALUE_OUTVAR_PREFIX,
                const.KEY_ENABLE_EXPRESSION,
                "invar_tail",
            ):
                tails.append(_normalize_module_header_tail(cast(object, tree_node)))
                return
            for child in cast(list[object], tree_node.children):
                visit(child)
            return
        if isinstance(node, list):
            for nested in cast(list[object], node):
                visit(nested)
            return
        if isinstance(node, tuple):
            for nested in cast(tuple[object, ...], node):
                visit(nested)

    visit(value)
    return tails


class ModuleHeaderMixin:
    """Mixin providing module header and argument transformation methods."""

    def IGNOREMAXMODULE(self, _: object) -> str:
        """Grammar IGNOREMAXMODULE terminal -> string marker."""
        return const.GRAMMAR_VALUE_IGNOREMAXMODULE

    def LAYERMODULE(self, _: object) -> str:
        """Grammar LAYERMODULE terminal -> string marker."""
        return const.GRAMMAR_VALUE_LAYERMODULE

    def argument(self, items: list[TransformerItem]) -> TransformerItem | None:
        """Grammar argument rule -> pass through single non-Token child."""
        for it in items:
            if not isinstance(it, Token):
                return it
        return None

    def arguments(self, items: list[TransformerItem]) -> TransformerTree:
        """Grammar arguments -> Tree of non-Token argument items."""
        return Tree(
            const.TREE_TAG_ARGUMENTS,
            cast(list[Any], [it for it in items if not isinstance(it, Token)]),
        )

    @v_args(meta=True)
    def module_header(self, meta: Any, items: list[TransformerItem]) -> ModuleHeader:  # noqa: PLR0915
        """Grammar module_header -> ModuleHeader with position, arguments, layer, enable."""
        name = None
        coords5: tuple[float, float, float, float, float] | None = None
        coord_tails: list[Any] = []
        args_trees: list[TransformerTree] = []
        invocation_arguments: list[str] = []
        layer = None
        enable_val = True
        zoom_limits = None
        zoomable = False
        enable_tail: object | None = None

        for it in items:
            if isinstance(it, str) and name is None:
                name = it
            elif isinstance(it, dict) and const.TREE_TAG_INVOKE_COORD in it:
                mapping = cast(dict[str, object], it)
                raw = mapping[const.TREE_TAG_INVOKE_COORD]
                coords = float_tuple(raw, 5)
                if coords is not None:
                    coords5 = cast(tuple[float, float, float, float, float], coords)
                    tails = mapping.get(const.KEY_TAILS)
                    if isinstance(tails, list):
                        coord_tails = [_normalize_module_header_tail(tail) for tail in cast(list[Any], tails)]
            elif isinstance(it, tuple):
                coords = float_tuple(cast(tuple[object, ...], it), 5)
                if coords is not None:
                    coords5 = cast(tuple[float, float, float, float, float], coords)
            if isinstance(it, Tree) and it.data == const.TREE_TAG_ARGUMENTS:
                args_trees.append(cast(TransformerTree, it))

        if coords5 is None:
            raise ValueError("module_header missing invoke_coord")

        for tree in args_trees:
            for child in tree.children:
                if isinstance(child, int) and layer is None:
                    layer = child
                elif isinstance(child, dict):
                    payload = cast(dict[str, object], child)
                    if const.TREE_TAG_ENABLE in payload:
                        enable_obj = payload[const.TREE_TAG_ENABLE]
                        if isinstance(enable_obj, bool):
                            enable_val = enable_obj
                        tail_obj = payload.get(const.KEY_TAIL)
                        if tail_obj is not None:
                            enable_tail = tail_obj
                    elif const.GRAMMAR_VALUE_ZOOMLIMITS in payload:
                        zoom_limits_obj = payload[const.GRAMMAR_VALUE_ZOOMLIMITS]
                        zoom_limits_pair = float_tuple(zoom_limits_obj, 2)
                        if zoom_limits_pair is not None:
                            zoom_limits = cast(tuple[float, float], zoom_limits_pair)
                    elif const.GRAMMAR_VALUE_ZOOMABLE in payload:
                        zoomable = True
                    else:
                        coord_tails.extend(_collect_module_header_argument_tails(payload))
                elif isinstance(child, str):
                    invocation_arguments.append(child)

        return ModuleHeader(
            name=name or "",
            invoke_coord=coords5,
            declaration_span=meta_span(meta),
            invocation_arguments=tuple(invocation_arguments),
            zoomable=zoomable,
            layer_info=(str(layer) if layer is not None else None),
            enable=enable_val,
            zoom_limits=zoom_limits,
            enable_tail=enable_tail,
            invoke_coord_tails=coord_tails,
        )


__all__ = ["ModuleHeaderMixin"]
