"""Graphics and interact mixin for SLTransformer.

Handles graphics object construction, coordinate handling, interact object building,
and layout specification.
"""

from __future__ import annotations

from typing import cast

from lark import Token, Tree

from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import GraphObject, InteractObject


class _GraphicsInteractMixin:
    """Mixin providing graphics and interact object transformation methods."""

    def text_object(self, items) -> GraphObject:
        """Grammar text_object -> GraphObject (TEXTOBJECT with text and coordinates)."""
        go = GraphObject(const.GRAMMAR_VALUE_TEXTOBJECT)

        # Coordinates ((x,y),(w,h))
        coord_payloads, coord_tails = self._extract_coord_payloads(items)  # type: ignore[attr-defined]
        for it in coord_payloads:
            if isinstance(it, tuple) and len(it) == 2 and all(isinstance(t, tuple) for t in it):
                go.properties[const.KEY_COORDS] = it
                break

        # Collect tails (Enable_/InVar_ etc.) across the object
        tails = self._merge_tails(coord_tails, self._collect_invar_enable_tails(items))  # type: ignore[attr-defined]
        if tails:
            go.properties[const.KEY_TAILS] = tails

        # Pair each VARNAME with the nearest preceding top-level text (STRING or text_content)
        text_vars: list[str] = []

        def _extract_text_from_node(node) -> str:
            if isinstance(node, str):
                return node
            if hasattr(node, "data") and getattr(node, "data", None) == const.TREE_TAG_TEXT_CONTENT:
                for ch in getattr(node, "children", []):
                    if isinstance(ch, str):
                        return ch
            raise ValueError(
                f"_extract_text_from_node expected a str or a 'text_content' node; got {type(node).__name__}"
            )

        for i, it in enumerate(items):
            if isinstance(it, Token) and it.type == const.TOKEN_VARNAME:
                j = i - 1
                while j >= 0:
                    prev = items[j]
                    s = _extract_text_from_node(prev)
                    if s:
                        text_vars.append(s)
                        break
                    j -= 1

        if text_vars:
            go.properties["text_vars"] = text_vars
        return go

    def text_content(self, items) -> str:
        """Grammar text_content -> string (unwrap TEXT content)."""
        for it in items:
            if isinstance(it, str):
                return it
        types = ", ".join(type(x).__name__ for x in items)
        raise ValueError(f"text_content expected a str; got: {types}")

    def rectangle_object(self, items) -> GraphObject:
        """Grammar rectangle_object -> GraphObject (RECTANGLEOBJECT)."""
        go = GraphObject(const.GRAMMAR_VALUE_RECTANGLEOBJECT)
        coord_payloads, coord_tails = self._extract_coord_payloads(items)  # type: ignore[attr-defined]
        for it in coord_payloads:
            if isinstance(it, tuple) and len(it) == 2 and all(isinstance(t, tuple) for t in it):
                go.properties[const.KEY_COORDS] = it
                break
        tails = self._merge_tails(coord_tails, self._collect_invar_enable_tails(items))  # type: ignore[attr-defined]
        if tails:
            go.properties[const.KEY_TAILS] = tails
        return go

    def line_object(self, items) -> GraphObject:
        """Grammar line_object -> GraphObject (LINEOBJECT)."""
        go = GraphObject(const.GRAMMAR_VALUE_LINEOBJECT)
        coord_payloads, coord_tails = self._extract_coord_payloads(items)  # type: ignore[attr-defined]
        for it in coord_payloads:
            if isinstance(it, tuple) and len(it) == 2 and all(isinstance(t, tuple) for t in it):
                go.properties[const.KEY_COORDS] = it
                break
        tails = self._merge_tails(coord_tails, self._collect_invar_enable_tails(items))  # type: ignore[attr-defined]
        if tails:
            go.properties[const.KEY_TAILS] = tails
        return go

    def oval_object(self, items) -> GraphObject:
        """Grammar oval_object -> GraphObject (OVALOBJECT)."""
        go = GraphObject(const.GRAMMAR_VALUE_OVALOBJECT)
        coord_payloads, coord_tails = self._extract_coord_payloads(items)  # type: ignore[attr-defined]
        for it in coord_payloads:
            if isinstance(it, tuple) and len(it) == 2 and all(isinstance(t, tuple) for t in it):
                go.properties[const.KEY_COORDS] = it
                break
        tails = self._merge_tails(coord_tails, self._collect_invar_enable_tails(items))  # type: ignore[attr-defined]
        if tails:
            go.properties[const.KEY_TAILS] = tails
        return go

    def polygon_object(self, items) -> GraphObject:
        """Grammar polygon_object -> GraphObject (POLYGONOBJECT)."""
        go = GraphObject(const.GRAMMAR_VALUE_POLYGONOBJECT)
        _coord_payloads, coord_tails = self._extract_coord_payloads(items)  # type: ignore[attr-defined]
        tails = self._merge_tails(coord_tails, self._collect_invar_enable_tails(items))  # type: ignore[attr-defined]
        if tails:
            go.properties[const.KEY_TAILS] = tails
        return go

    def segment_object(self, items) -> GraphObject:
        """Grammar segment_object -> GraphObject (SEGMENTOBJECT)."""
        go = GraphObject(const.GRAMMAR_VALUE_SEGMENTOBJECT)
        coord_payloads, coord_tails = self._extract_coord_payloads(items)  # type: ignore[attr-defined]
        for it in coord_payloads:
            if isinstance(it, tuple) and len(it) == 2 and all(isinstance(t, tuple) for t in it):
                go.properties[const.KEY_COORDS] = it
                break
        tails = self._merge_tails(coord_tails, self._collect_invar_enable_tails(items))  # type: ignore[attr-defined]
        if tails:
            go.properties[const.KEY_TAILS] = tails
        return go

    def composite_object(self, items) -> GraphObject:
        """Grammar composite_object -> GraphObject (COMPOSITEOBJECT)."""
        go = GraphObject(const.GRAMMAR_VALUE_COMPOSITEOBJECT)
        _coord_payloads, coord_tails = self._extract_coord_payloads(items)  # type: ignore[attr-defined]
        tails = self._merge_tails(coord_tails, self._collect_invar_enable_tails(items))  # type: ignore[attr-defined]
        if tails:
            go.properties[const.KEY_TAILS] = tails
        return go

    def graph_object(self, items) -> GraphObject:
        """Grammar graph_object -> GraphObject with optional layer."""
        obj = None
        layer = None
        for it in items:
            if isinstance(it, GraphObject) and obj is None:
                obj = it
            elif isinstance(it, int):
                layer = it

        if obj is None:
            types = ", ".join(type(x).__name__ for x in items)
            raise ValueError(f"graph_object expected a GraphObject in items; got: {types}")

        if layer is not None:
            obj.properties["layer"] = layer

        return obj

    def graph_objects(self, items) -> list[GraphObject]:
        """Grammar graph_objects -> list of GraphObjects."""
        return [it for it in items if isinstance(it, GraphObject)]

    def interact_objects(self, items):
        """Grammar interact_objects -> list of InteractObjects."""
        out = []
        for it in items:
            if isinstance(it, InteractObject):
                out.append(it)
            elif isinstance(it, Tree) and it.children:
                for child in it.children:
                    if isinstance(child, InteractObject):
                        out.append(child)
        return out

    def combutproc_item(self, items) -> InteractObject:
        """Grammar combutproc_item -> InteractObject (COMBUTPROC with coordinates and procedure)."""
        props = {}
        coords = []
        proc = None
        _coord_payloads, coord_tails = self._extract_coord_payloads(items)  # type: ignore[attr-defined]
        for it in items:
            if isinstance(it, tuple):
                coords.append(it)
            elif isinstance(it, dict) and const.KEY_COORDS in it:
                coords.append(it[const.KEY_COORDS])
            elif isinstance(it, dict) and const.KEY_PROCEDURE_CALL in it:
                proc = it[const.KEY_PROCEDURE_CALL]
            elif isinstance(it, list):
                for sub in it:
                    if isinstance(sub, dict) and const.KEY_PROCEDURE_CALL in sub:
                        proc = sub[const.KEY_PROCEDURE_CALL]
        props[const.KEY_COORDS] = coords or None
        if proc:
            props[const.KEY_PROCEDURE] = proc
        tails = self._merge_tails(coord_tails, self._collect_invar_enable_tails(items))  # type: ignore[attr-defined]
        if tails:
            props[const.KEY_TAILS] = tails
        return InteractObject(type=const.GRAMMAR_VALUE_COMBUTPROC, properties=props)

    def procedure_call(self, items):
        """Grammar procedure_call -> dict with procedure call details."""
        name = None
        args = []
        for it in items:
            if isinstance(it, Token) and it.type == const.KEY_NAME and name is None:
                name = it.value
            else:
                args.append(it)
        return {const.KEY_PROCEDURE_CALL: {const.KEY_NAME: name, const.KEY_ARGS: args}}

    def invar(self, items):
        """Grammar invar -> connected_variable or variable reference."""
        for it in items:
            if not isinstance(it, Token):
                return it
        raise ValueError(f"invar expected a connected_variable child; got: {items}")

    def enable(self, items):
        """Grammar enable -> ENABLE_PREFIX '=' BOOL (invar | enable_expression)."""
        val = None
        tail = None
        for it in items:
            if isinstance(it, bool):
                val = it
            elif not isinstance(it, Token):
                tail = it
        return {
            const.TREE_TAG_ENABLE: bool(val) if val is not None else True,
            const.KEY_TAIL: tail,
        }

    def enable_expression(self, items):
        """Grammar enable_expression -> expression within enable context."""
        for it in items:
            if not isinstance(it, Token):
                return it
        raise ValueError(f"enable_expression expected an expression child; got: {items}")

    def interact_simple_item(self, items) -> InteractObject:
        """Grammar interact_simple_item -> InteractObject (button, checkbox, textbox, etc.)."""
        itype = None
        coords = []
        body = []
        for it in items:
            if isinstance(it, Token) and itype is None:
                itype = it.value
            elif isinstance(it, tuple):
                coords.append(it)
            elif isinstance(it, dict) and const.KEY_COORDS in it:
                coords.append(it[const.KEY_COORDS])
            elif isinstance(it, Tree) and it.data == const.TREE_TAG_INTERACT_BODY_SEQ:
                tree = cast(Tree, it)
                for child in tree.children:
                    body.append(child)
            elif isinstance(it, list):
                for child in it:
                    body.append(child)
        props = {const.KEY_COORDS: coords or None, const.KEY_BODY: body or None}
        tails = self._collect_invar_enable_tails(items)  # type: ignore[attr-defined]
        if tails:
            props[const.KEY_TAILS] = tails
        return InteractObject(type=itype or const.KEY_INTERACT, properties=props)

    def interact_assign_variable_tailed(self, items):
        """Grammar interact_assign_variable_tailed -> variable assignment with tail."""
        name = None
        val = None
        tail = None
        for it in items:
            if isinstance(it, str) and name is None:
                name = it
            elif not isinstance(it, Token) and val is None:
                val = it
            elif not isinstance(it, Token):
                tail = it
        return {const.KEY_NAME: name, const.KEY_VALUE: val, const.KEY_TAIL: tail}

    def interact_assign_variable_plain(self, items):
        """Grammar interact_assign_variable_plain -> variable assignment without tail."""
        name = None
        val = None
        for it in items:
            if isinstance(it, str) and name is None:
                name = it
            elif not isinstance(it, Token) and val is None:
                val = it
        return {const.KEY_NAME: name, const.KEY_VALUE: val, const.KEY_TAIL: None}

    def interact_assign_variable(self, items):
        """Grammar interact_assign_variable -> assignment payload wrapper."""
        for it in items:
            if isinstance(it, dict) and const.KEY_NAME in it:
                return {const.KEY_ASSIGN: it}
        raise ValueError(f"interact_assign_variable expected an assignment payload; got: {items}")

    def interact_flag(self, items) -> dict:
        """Grammar interact_flag -> flag with name, optional extra, and tail."""
        name = None
        extra = None
        tail = None
        for it in items:
            if isinstance(it, Token) and it.type == const.KEY_NAME and name is None:
                name = it.value
            elif isinstance(it, Token) and it.type in (
                const.KEY_STRING,
                const.KEY_SIGNED_INT,
            ):
                extra = it.value
            elif not isinstance(it, Token):
                tail = it
        return {const.KEY_NAME: name, const.KEY_EXTRA: extra, const.KEY_TAIL: tail}

    def interact_value_line(self, items):
        """Grammar interact_value_line -> list of interact value items."""
        return list(items)

    def layer_info(self, items) -> int:
        """Grammar layer_info -> int layer number."""
        for it in items:
            if isinstance(it, int):
                return it
        raise ValueError(f"layer_info expected an int; got: {items}")

    def seq_control_opt(self, items) -> Tree:
        """Grammar seq_control_opt -> Tree of optional SEQ_CONTROL/SEQTIMER."""
        return Tree(const.KEY_SEQ_CONTROL_OPS, items)

    def codeblock_coord(self, items) -> tuple[float, float]:
        """Grammar codeblock_coord -> (x, y) coordinate pair."""
        # Filter out Tokens first
        items_filtered = [v for v in items if not isinstance(v, Token)]
        if len(items_filtered) < 2:
            raise ValueError(f"codeblock_coord expected 2 coordinate values; got {len(items_filtered)}")
        return (float(items_filtered[0]), float(items_filtered[1]))

    def objsizedef(self, items) -> tuple[float, float]:
        """Grammar objsizedef -> (width, height) size pair."""
        # Filter out Tokens first
        items_filtered = [v for v in items if not isinstance(v, Token)]
        if len(items_filtered) < 2:
            raise ValueError(f"objsizedef expected 2 size values; got {len(items_filtered)}")
        return (float(items_filtered[0]), float(items_filtered[1]))

    def two_layers(self, items) -> dict[str, float]:
        """Grammar two_layers -> dict with top and bottom layer values."""
        layers: dict[str, float] = {}
        for it in items:
            if isinstance(it, dict):
                layers.update(it)
        return layers
