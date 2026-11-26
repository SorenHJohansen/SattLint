"""Static layout facts for module clipping bounds and placed objects.

The parser keeps every drawing coordinate as written: a module's clipping
rectangle, its grid, the placement of its children, and each graphics or
interactor object's coordinate run. This module turns those facts into the
shapes a layout analyzer needs without touching the parser's tree.

Geometry that the source drives from variables is not a static fact. A clipping
corner, an invocation value, or an object coordinate that carries a variable
input or a computed expression tail is skipped rather than compared against its
literal fallback value. An output binding or a literal-only tail leaves the
written value in place, so it stays checkable.

The module-scope walk lives here because the analyzer-owned nested-module walker
is not importable from this layer. It reads typed fields only and never
inspects a parse tree. A text object's ``ConnectionNode`` anchor is a connection
point rather than a drawn element, so it does not extend the checked bounds.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, cast

from sattlint.config.analysis import DEFAULT_MODULE_GRID, DEFAULT_MODULE_GRID_TOLERANCE
from sattlint.parser_api import (
    BasePicture,
    BinOp,
    BoolOp,
    Compare,
    CoordBox,
    CoordPair,
    FrameModule,
    FuncCall,
    GraphObject,
    InteractObject,
    LitStringTail,
    ModuleDef,
    ModuleTypeDef,
    ModuleTypeInstance,
    NotOp,
    SingleModule,
    TernaryOp,
    UnaryOp,
    VarRef,
    VarTail,
)

__all__ = [
    "ModuleLayoutFinding",
    "ModuleLayoutKind",
    "Rect",
    "diagnose_module_layout",
]

type ModuleScope = BasePicture | ModuleTypeDef | SingleModule | FrameModule
type ModuleChild = SingleModule | FrameModule | ModuleTypeInstance

type ModuleLayoutKind = Literal[
    "module_layout.invalid_clipping",
    "module_layout.origo_not_centered_or_corner",
    "module_layout.size_off_grid",
    "module_layout.position_off_grid",
    "module_layout.object_outside_clipping",
]


@dataclass(frozen=True, slots=True)
class Rect:
    """An axis-aligned rectangle in one module's own coordinate space."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @classmethod
    def from_corners(cls, first: CoordPair, second: CoordPair) -> Rect:
        return cls(
            x_min=min(first[0], second[0]),
            y_min=min(first[1], second[1]),
            x_max=max(first[0], second[0]),
            y_max=max(first[1], second[1]),
        )

    @classmethod
    def from_point(cls, point: CoordPair) -> Rect:
        return cls(x_min=point[0], y_min=point[1], x_max=point[0], y_max=point[1])

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    def is_empty(self, tolerance: float) -> bool:
        return self.width <= tolerance or self.height <= tolerance


@dataclass(frozen=True, slots=True)
class ModuleLayoutFinding:
    kind: ModuleLayoutKind
    message: str
    module_path: tuple[str, ...]
    details: dict[str, object]
    line: int | None = None


@dataclass(frozen=True, slots=True)
class _Settings:
    grid: float
    tolerance: float


def diagnose_module_layout(
    base_picture: BasePicture,
    *,
    grid: float = DEFAULT_MODULE_GRID,
    tolerance: float = DEFAULT_MODULE_GRID_TOLERANCE,
    module_type_filter: Callable[[ModuleTypeDef], bool] | None = None,
) -> tuple[ModuleLayoutFinding, ...]:
    """Return the layout findings for one parsed base picture.

    Modules declared in the analyzed unit are checked, including the module
    types declared beside it. A referenced module type from another library is
    not descended into: its own file owns those geometry findings. Pass
    ``module_type_filter`` to decide which declared module types belong to the
    analyzed unit when the picture was merged with its dependencies.
    """
    collector = _LayoutCollector(_Settings(grid=grid, tolerance=tolerance))
    collector.visit_scope(base_picture, (base_picture.header.name,))
    for module_type in base_picture.moduletype_defs or ():
        if module_type_filter is not None and not module_type_filter(module_type):
            continue
        collector.visit_scope(
            module_type,
            (base_picture.header.name, f"TypeDef:{module_type.name}"),
        )
    return tuple(collector.findings)


class _LayoutCollector:
    def __init__(self, settings: _Settings) -> None:
        self._settings = settings
        self.findings: list[ModuleLayoutFinding] = []

    def visit_scope(self, scope: ModuleScope, path: tuple[str, ...]) -> None:
        module_def = scope.moduledef
        if module_def is None:
            return
        grid = _effective_grid(module_def, self._settings)
        clip = self._check_clipping(module_def, path, grid)
        self._check_objects(module_def, clip, path)
        for child in scope.submodules or ():
            self._visit_child(child, parent_grid=grid, parent_path=path)

    def _visit_child(self, child: ModuleChild, *, parent_grid: float, parent_path: tuple[str, ...]) -> None:
        child_path = (*parent_path, child.header.name)
        self._check_placement(child, parent_grid=parent_grid, path=child_path)
        if isinstance(child, ModuleTypeInstance):
            return
        self.visit_scope(child, child_path)

    def _check_clipping(self, module_def: ModuleDef, path: tuple[str, ...], grid: float) -> Rect | None:
        clipping = module_def.clipping
        if clipping is None or _any_dynamic_tail(clipping.tails):
            return None

        bounds = clipping.bounds
        rect = Rect.from_corners(bounds[0], bounds[1])
        line = clipping.span.line if clipping.span is not None else None
        if rect.is_empty(self._settings.tolerance):
            self._add(
                "module_layout.invalid_clipping",
                f"Clipping bounds {_format_rect(rect)} have no area.",
                path,
                _bounds_data(rect, grid),
                line,
            )
            return None

        if not _origin_is_centered_or_at_bottom_left(rect, self._settings.tolerance):
            self._add(
                "module_layout.origo_not_centered_or_corner",
                (
                    "Module origin is neither at the clipping center nor at the bottom-left corner: "
                    f"{_format_rect(rect)}."
                ),
                path,
                _bounds_data(rect, grid),
                line,
            )

        off_grid_axes = _off_grid_size_axes(rect, grid, self._settings.tolerance)
        if off_grid_axes:
            self._add(
                "module_layout.size_off_grid",
                f"Clipping {_join_axes(off_grid_axes)} {_is_not_multiple(off_grid_axes)} of the {grid:g} grid.",
                path,
                _bounds_data(rect, grid),
                line,
            )
        return rect

    def _check_placement(self, child: ModuleChild, *, parent_grid: float, path: tuple[str, ...]) -> None:
        header = child.header
        if _any_dynamic_tail(header.invoke_coord_tails):
            return

        x, y, _, width, height = header.invoke_coord
        line = header.declaration_span.line if header.declaration_span is not None else None
        data: dict[str, object] = {
            "position": [x, y],
            "size": [width, height],
            "grid": parent_grid,
        }

        off_grid_position = _off_grid_position_axes(x, y, parent_grid, self._settings.tolerance)
        if off_grid_position:
            self._add(
                "module_layout.position_off_grid",
                (
                    f"Module position {_join_axes(off_grid_position)} "
                    f"{_is_not_aligned(off_grid_position)} to the {parent_grid:g} grid."
                ),
                path,
                data,
                line,
            )

        off_grid_size = _off_grid_value_axes(width, height, parent_grid, self._settings.tolerance)
        if off_grid_size:
            self._add(
                "module_layout.size_off_grid",
                f"Module {_join_axes(off_grid_size)} {_is_not_multiple(off_grid_size)} of the {parent_grid:g} grid.",
                path,
                data,
                line,
            )

    def _check_objects(self, module_def: ModuleDef, clip: Rect | None, path: tuple[str, ...]) -> None:
        if clip is None:
            return
        for graph_object in module_def.graph_objects or ():
            bounds = _graph_object_bounds(graph_object)
            if bounds is not None and _is_fully_outside(bounds, clip, self._settings.tolerance):
                self._add_object(graph_object, "graph", bounds, clip, path)
        for interact_object in module_def.interact_objects or ():
            bounds = _interact_object_bounds(interact_object)
            if bounds is not None and _is_fully_outside(bounds, clip, self._settings.tolerance):
                self._add_object(interact_object, "interactor", bounds, clip, path)

    def _add_object(
        self,
        obj: GraphObject | InteractObject,
        object_class: str,
        bounds: Rect,
        clip: Rect,
        path: tuple[str, ...],
    ) -> None:
        line = obj.span.line if obj.span is not None else None
        self._add(
            "module_layout.object_outside_clipping",
            f"{obj.type} lies entirely outside the module clipping bounds.",
            path,
            {
                "object_type": obj.type,
                "object_class": object_class,
                "bounds": _bounds_list(bounds),
                "clipping_bounds": _bounds_list(clip),
            },
            line,
        )

    def _add(
        self,
        kind: ModuleLayoutKind,
        message: str,
        path: tuple[str, ...],
        details: dict[str, object],
        line: int | None,
    ) -> None:
        self.findings.append(
            ModuleLayoutFinding(
                kind=kind,
                message=message,
                module_path=path,
                details=details,
                line=line,
            )
        )


def _effective_grid(module_def: ModuleDef, settings: _Settings) -> float:
    written = module_def.grid
    if written is None or written <= 0:
        return settings.grid
    return written


def _graph_object_bounds(obj: GraphObject) -> Rect | None:
    properties = obj.properties
    if _has_dynamic_coordinate_tails(properties.get("coord_tails")):
        return None

    rects: list[Rect] = []
    coords = properties.get("coords")
    if coords is not None:
        rects.append(_rect_from_coord_geometry(coords))

    points = properties.get("points")
    if points:
        if any(_any_dynamic_tail(point.x_tails) or _any_dynamic_tail(point.y_tails) for point in points):
            return None
        rects.append(
            Rect(
                x_min=min(point.x for point in points),
                y_min=min(point.y for point in points),
                x_max=max(point.x for point in points),
                y_max=max(point.y for point in points),
            )
        )

    segment_point = properties.get("segment_point")
    if segment_point is not None:
        rects.append(Rect.from_point(segment_point))

    return _union(rects)


def _interact_object_bounds(obj: InteractObject) -> Rect | None:
    properties = obj.properties
    if _has_dynamic_coordinate_tails(properties.get("coord_tails")):
        return None

    coords = properties.get("coords")
    if not coords:
        return None
    return _union([_rect_from_coord_geometry(item) for item in coords])


def _rect_from_coord_geometry(coords: CoordPair | CoordBox) -> Rect:
    first, second = coords
    if isinstance(first, tuple):
        return Rect.from_corners(first, cast(CoordPair, second))
    pair = cast(CoordPair, coords)
    return Rect.from_corners(pair, pair)


#: Expression shapes that compute a coordinate at run time. A bare literal, a
#: ``LitStringTail``, and an ``OutVar_`` binding all leave the written geometry
#: in place.
_DYNAMIC_TAIL_TYPES = (VarRef, BoolOp, NotOp, Compare, BinOp, UnaryOp, FuncCall, TernaryOp)


def _tail_is_dynamic(tail: object) -> bool:
    if isinstance(tail, VarTail):
        return tail.direction == "in" and not isinstance(tail.value, LitStringTail) and tail.bound_name is not None
    return isinstance(tail, _DYNAMIC_TAIL_TYPES)


def _any_dynamic_tail(tails: Sequence[object]) -> bool:
    return any(_tail_is_dynamic(tail) for tail in tails)


def _has_dynamic_coordinate_tails(groups: Sequence[Sequence[object]] | None) -> bool:
    if groups is None:
        return False
    return any(_any_dynamic_tail(group) for group in groups)


def _union(rects: list[Rect]) -> Rect | None:
    if not rects:
        return None
    return Rect(
        x_min=min(rect.x_min for rect in rects),
        y_min=min(rect.y_min for rect in rects),
        x_max=max(rect.x_max for rect in rects),
        y_max=max(rect.y_max for rect in rects),
    )


def _origin_is_centered_or_at_bottom_left(rect: Rect, tolerance: float) -> bool:
    centered = abs(rect.x_min + rect.x_max) <= tolerance and abs(rect.y_min + rect.y_max) <= tolerance
    bottom_left = abs(rect.x_min) <= tolerance and abs(rect.y_min) <= tolerance
    return centered or bottom_left


def _off_grid_position_axes(x: float, y: float, grid: float, tolerance: float) -> list[str]:
    axes: list[str] = []
    if _off_grid(x, grid, tolerance):
        axes.append(f"x = {x:g}")
    if _off_grid(y, grid, tolerance):
        axes.append(f"y = {y:g}")
    return axes


def _off_grid_size_axes(rect: Rect, grid: float, tolerance: float) -> list[str]:
    return _off_grid_value_axes(rect.width, rect.height, grid, tolerance)


def _off_grid_value_axes(width: float, height: float, grid: float, tolerance: float) -> list[str]:
    axes: list[str] = []
    if _off_grid(width, grid, tolerance):
        axes.append(f"width {width:g}")
    if _off_grid(height, grid, tolerance):
        axes.append(f"height {height:g}")
    return axes


def _off_grid(value: float, grid: float, tolerance: float) -> bool:
    if grid <= 0:
        return False
    return abs(value - round(value / grid) * grid) > tolerance


def _is_fully_outside(bounds: Rect, clip: Rect, tolerance: float) -> bool:
    return (
        bounds.x_max < clip.x_min - tolerance
        or bounds.x_min > clip.x_max + tolerance
        or bounds.y_max < clip.y_min - tolerance
        or bounds.y_min > clip.y_max + tolerance
    )


def _join_axes(axes: list[str]) -> str:
    if len(axes) == 1:
        return axes[0]
    return " and ".join(axes)


def _is_not_multiple(axes: list[str]) -> str:
    return "is not a multiple" if len(axes) == 1 else "are not multiples"


def _is_not_aligned(axes: list[str]) -> str:
    return "is not aligned" if len(axes) == 1 else "are not aligned"


def _format_rect(rect: Rect) -> str:
    return f"({rect.x_min:g}, {rect.y_min:g}) to ({rect.x_max:g}, {rect.y_max:g})"


def _bounds_list(rect: Rect) -> list[float]:
    return [rect.x_min, rect.y_min, rect.x_max, rect.y_max]


def _bounds_data(rect: Rect, grid: float) -> dict[str, object]:
    return {"clipping_bounds": _bounds_list(rect), "grid": grid}
