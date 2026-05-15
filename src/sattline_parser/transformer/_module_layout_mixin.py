"""Module layout and module-definition helpers for the SattLine transformer."""

# ruff: noqa: N802

from __future__ import annotations

from typing import Any, cast

from lark import Token, Tree

from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import GraphObject, InteractObject, ModuleDef

from ._module_shared import TransformerItem, TransformerTree, _coord_pair


class _ModuleLayoutMixin:
    """Mixin providing module layout and ModuleDef transformation methods."""

    def origo_coord(self, items: list[TransformerItem]) -> list[TransformerItem]:
        """Grammar origo_coord -> coordinate values list."""
        return items

    def size(self, items: list[TransformerItem]) -> list[TransformerItem]:
        """Grammar size -> size values list."""
        return items

    def coordinates(self, items: list[TransformerItem]) -> dict[str, object]:
        """Grammar coordinates -> dict with (x,y) and optional coordinate tails."""
        items_filtered = [value for value in items if not isinstance(value, Token)]
        nums = [float(value) for value in items_filtered if isinstance(value, int | float)]
        if len(nums) < 2:
            raise ValueError(f"coordinates missing REAL values (got {len(nums)})")
        tails = self._extract_coord_tails(cast(list[Any], items))  # type: ignore[attr-defined]
        return {
            const.KEY_COORDS: (nums[0], nums[1]),
            const.KEY_TAILS: tails or None,
        }

    def origo_size_pair(self, items: list[TransformerItem]) -> dict[str, object]:
        """Grammar origo_size_pair -> dict with two coordinate pairs and tails."""
        coords: list[tuple[float, float]] = []
        tails: list[Any] = []
        for it in items:
            if isinstance(it, dict) and const.KEY_COORDS in it:
                payload = cast(dict[str, object], it)
                coord = _coord_pair(payload[const.KEY_COORDS])
                if coord is not None:
                    coords.append(coord)
                    raw_tails = payload.get(const.KEY_TAILS)
                    if isinstance(raw_tails, list):
                        tails.extend(cast(list[Any], raw_tails))
            elif isinstance(it, Tree) and it.data == const.TREE_TAG_COORDINATES:
                tree = cast(TransformerTree, it)
                nums = [float(x) for x in tree.children if isinstance(x, int | float)]
                if len(nums) >= 2:
                    coords.append((nums[0], nums[1]))
            elif isinstance(it, tuple):
                coord = _coord_pair(cast(tuple[object, ...], it))
                if coord is not None:
                    coords.append(coord)
        if len(coords) != 2:
            raise ValueError(f"origo_size_pair expected 2 coordinate pairs, found {len(coords)}")
        return {
            const.KEY_COORDS: (coords[0], coords[1]),
            const.KEY_TAILS: tails or None,
        }

    def invoke_coord(self, items: list[TransformerItem]) -> dict[str, object]:
        """Grammar invoke_coord -> dict with 5-tuple and coordinate tails."""
        items_filtered = [value for value in items if not isinstance(value, Token)]
        nums = [float(value) for value in items_filtered if isinstance(value, int | float)]
        if len(nums) < 5:
            raise ValueError(f"invoke_coord expected 5 REALs, found {len(nums)}")
        tails = self._extract_coord_tails(cast(list[Any], items))  # type: ignore[attr-defined]
        return {
            const.TREE_TAG_INVOKE_COORD: tuple(nums[:5]),
            const.KEY_TAILS: tails or None,
        }

    def coord_invar_tail(self, items: list[TransformerItem]) -> TransformerItem:
        """Grammar coord_invar_tail -> connected variable value."""
        for it in items:
            if not isinstance(it, Token):
                return it
        raise ValueError("coord_invar_tail expected connected variable or value")

    def coord_clippingbounds(self, items: list[TransformerItem]) -> TransformerTree:
        """Grammar coord_clippingbounds -> Tree of clipping specification."""
        return Tree(const.GRAMMAR_VALUE_CLIPPINGBOUNDS, cast(list[Any], items))

    def clippingbounds(self, items: list[TransformerItem]) -> dict[str, object]:
        """Grammar clippingbounds -> dict with clipping values and tails."""
        payload = items[-1]
        if isinstance(payload, dict) and const.KEY_COORDS in payload:
            payload_dict = cast(dict[str, object], payload)
            return {
                const.GRAMMAR_VALUE_CLIPPINGBOUNDS: payload_dict[const.KEY_COORDS],
                const.KEY_TAILS: payload_dict.get(const.KEY_TAILS) or None,
            }
        return {const.GRAMMAR_VALUE_CLIPPINGBOUNDS: payload}

    def seq_layers(self, items: list[TransformerItem]) -> dict[str, object]:
        """Grammar seq_layers -> dict with sequence layer mapping."""
        return {const.KEY_SEQ_LAYERS: items[-1]}

    def zoomlimits(self, items: list[TransformerItem]) -> dict[str, tuple[TransformerItem, TransformerItem]]:
        """Grammar zoomlimits -> dict with min/max zoom values."""
        return {const.GRAMMAR_VALUE_ZOOMLIMITS: (items[-2], items[-1])}

    def ZOOMABLE(self, _: object) -> dict[str, bool]:
        """Grammar ZOOMABLE -> dict marking module as zoomable."""
        return {const.GRAMMAR_VALUE_ZOOMABLE: True}

    def grid(self, items: list[TransformerItem]) -> float:
        """Grammar grid -> float grid spacing value."""
        nums: list[float] = []
        for value in items:
            if isinstance(value, Token):
                continue
            if isinstance(value, int | float | str):
                try:
                    nums.append(float(value))
                except ValueError as exc:
                    raise ValueError(f"grid expected a numeric value; got {type(value).__name__}: {value!r}") from exc
                continue
            raise ValueError(f"grid expected a numeric value; got {type(value).__name__}: {value!r}")

        if not nums:
            types = ", ".join(type(x).__name__ for x in items)
            raise ValueError(f"grid expected at least one numeric value; got: {types}")

        return nums[-1]

    def moduledef_opts_seq(self, items: list[TransformerItem]) -> TransformerTree:
        """Grammar moduledef_opts_seq -> Tree with merged option dict."""
        merged: dict[str, object] = {}
        for payload in items:
            if isinstance(payload, dict):
                merged.update(cast(dict[str, object], payload))
        return Tree(const.TREE_TAG_MODULEDEF_OPTS_SEQ, cast(list[Any], [merged]))

    def moduledef(self, items: list[TransformerItem]) -> ModuleDef:
        """Grammar moduledef -> ModuleDef with graphics, layout, and interact objects."""
        module_def = ModuleDef()
        for it in items:
            if isinstance(it, dict) and const.GRAMMAR_VALUE_CLIPPINGBOUNDS in it:
                payload = cast(dict[str, object], it)
                clipping_bounds = payload[const.GRAMMAR_VALUE_CLIPPINGBOUNDS]
                if isinstance(clipping_bounds, tuple):
                    clipping_tuple = cast(tuple[object, ...], clipping_bounds)
                    if len(clipping_tuple) == 2:
                        module_def.clipping_bounds = cast(
                            tuple[tuple[float, float], tuple[float, float]],
                            clipping_tuple,
                        )
                tails = payload.get(const.KEY_TAILS)
                if isinstance(tails, list) and tails:
                    module_def_any = cast(Any, module_def)
                    properties = cast(dict[str, list[Any]], module_def_any.properties)
                    property_tails = properties.setdefault(const.KEY_TAILS, [])
                    property_tails.extend(cast(list[Any], tails))
            elif isinstance(it, tuple):
                clipping_tuple = cast(tuple[object, ...], it)
                if len(clipping_tuple) == 2 and all(isinstance(t, tuple) for t in clipping_tuple):
                    module_def.clipping_bounds = cast(
                        tuple[tuple[float, float], tuple[float, float]],
                        clipping_tuple,
                    )
            elif isinstance(it, list) and it:
                if isinstance(it[0], GraphObject):
                    module_def.graph_objects = cast(list[GraphObject], it)
                elif isinstance(it[0], InteractObject):
                    module_def.interact_objects = cast(list[InteractObject], it)
            elif isinstance(it, dict):
                payload = cast(dict[str, object], it)
                if const.GRAMMAR_VALUE_ZOOMLIMITS in payload:
                    zoom_limits = _coord_pair(payload[const.GRAMMAR_VALUE_ZOOMLIMITS])
                    if zoom_limits is not None:
                        module_def.zoom_limits = zoom_limits
                if const.GRAMMAR_VALUE_ZOOMABLE in payload:
                    zoomable = payload[const.GRAMMAR_VALUE_ZOOMABLE]
                    if isinstance(zoomable, bool):
                        module_def.zoomable = zoomable
                if const.GRAMMAR_VALUE_GRID in payload and payload[const.GRAMMAR_VALUE_GRID] is not None:
                    grid_value = payload[const.GRAMMAR_VALUE_GRID]
                    if isinstance(grid_value, int | float | str):
                        module_def.grid = float(grid_value)
                if const.KEY_SEQ_LAYERS in payload:
                    module_def.seq_layers = payload[const.KEY_SEQ_LAYERS]
        return module_def


__all__ = ["_ModuleLayoutMixin"]
