from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import TypeGuard, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeInstance,
    SingleModule,
)

from ..grammar import constants as const
from ..reporting.variables_report import IssueKind, VariableIssue

_Rect = tuple[float, float, float, float]
_Point = tuple[float, float]
_PointPair = tuple[_Point, _Point]


@dataclass(frozen=True, slots=True)
class _PlacedRect:
    label: str
    rect: _Rect
    layer: str | None = None


def _path_key(path: list[str]) -> tuple[str, ...]:
    return tuple(segment.casefold() for segment in path)


def _path_relation(path: list[str], limit_to_module_path: list[str] | None) -> str:
    if limit_to_module_path is None:
        return "within"

    path_key = _path_key(path)
    limit_key = _path_key(limit_to_module_path)
    if path_key[: len(limit_key)] == limit_key:
        return "within"
    if limit_key[: len(path_key)] == path_key:
        return "ancestor"
    return "unrelated"


def _point_pair_to_rect(first: tuple[float, float], second: tuple[float, float]) -> _Rect | None:
    left = min(float(first[0]), float(second[0]))
    right = max(float(first[0]), float(second[0]))
    top = min(float(first[1]), float(second[1]))
    bottom = max(float(first[1]), float(second[1]))
    if right <= left or bottom <= top:
        return None
    return (left, top, right, bottom)


def _is_point(value: object) -> TypeGuard[_Point]:
    if not isinstance(value, tuple):
        return False
    coords = cast(tuple[object, ...], value)
    return (
        len(coords) == 2
        and all(isinstance(coord, int | float) for coord in coords)
    )


def _is_point_pair(value: object) -> TypeGuard[_PointPair]:
    if not isinstance(value, tuple):
        return False
    pair = cast(tuple[object, ...], value)
    return (
        len(pair) == 2
        and _is_point(pair[0])
        and _is_point(pair[1])
    )


def _normalize_rect(coords: object) -> _Rect | None:
    if isinstance(coords, list):
        items = cast(list[object], coords)
        if len(items) == 1:
            return _normalize_rect(items[0])
        if len(items) == 2 and _is_point(items[0]) and _is_point(items[1]):
            return _point_pair_to_rect(items[0], items[1])
        return None

    if _is_point_pair(coords):
        first, second = coords
        return _point_pair_to_rect(first, second)
    return None


def _normalize_layer(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clip_rect(child: SingleModule | FrameModule | ModuleTypeInstance) -> _Rect | None:
    moduledef = getattr(child, "moduledef", None)
    clipping_bounds = getattr(moduledef, "clipping_bounds", None)
    if clipping_bounds is None:
        return None
    local_rect = _normalize_rect(clipping_bounds)
    if local_rect is None:
        return None

    x, y, _rotation, width, height = child.header.invoke_coord
    return _point_pair_to_rect(
        (x + (local_rect[0] * width), y + (local_rect[1] * height)),
        (x + (local_rect[2] * width), y + (local_rect[3] * height)),
    )


def _module_rect(child: SingleModule | FrameModule | ModuleTypeInstance) -> _PlacedRect | None:
    rect = _clip_rect(child)
    if rect is None:
        x, y, _rotation, width, height = child.header.invoke_coord
        rect = _point_pair_to_rect((x, y), (x + width, y + height))
    if rect is None:
        return None
    return _PlacedRect(
        label=f"module '{child.header.name}'",
        rect=rect,
        layer=_normalize_layer(getattr(child.header, "layer_info", None)),
    )


def _collect_object_rects(objects: list[object], *, category: str) -> list[_PlacedRect]:
    rects: list[_PlacedRect] = []
    for index, obj in enumerate(objects, start=1):
        properties = getattr(obj, "properties", {}) or {}
        rect = _normalize_rect(properties.get(const.KEY_COORDS))
        if rect is None:
            continue
        object_type = getattr(obj, "type", category)
        rects.append(
            _PlacedRect(
                label=f"{category} {object_type} #{index}",
                rect=rect,
                layer=_normalize_layer(properties.get("layer")),
            )
        )
    return rects


def _rects_overlap(left: _Rect, right: _Rect) -> bool:
    return left[0] < right[2] and right[0] < left[2] and left[1] < right[3] and right[1] < left[3]


def _append_overlap_issues(
    issues: list[VariableIssue],
    path: list[str],
    rects: list[_PlacedRect],
) -> None:
    for left, right in combinations(rects, 2):
        if left.layer is not None and right.layer is not None and left.layer != right.layer:
            continue
        if not _rects_overlap(left.rect, right.rect):
            continue
        issues.append(
            VariableIssue(
                kind=IssueKind.LAYOUT_OVERLAP,
                module_path=path.copy(),
                variable=None,
                role=f"{left.label} overlaps {right.label}",
            )
        )


def _scan_container(
    issues: list[VariableIssue],
    path: list[str],
    moduledef: object | None,
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance] | None,
    *,
    limit_to_module_path: list[str] | None,
) -> None:
    relation = _path_relation(path, limit_to_module_path)
    if relation == "unrelated":
        return

    if relation == "within":
        sibling_rects = [rect for child in submodules or [] if (rect := _module_rect(child)) is not None]
        _append_overlap_issues(issues, path, sibling_rects)

        if moduledef is not None:
            object_rects = _collect_object_rects(
                getattr(moduledef, "graph_objects", []) or [],
                category="graph object",
            )
            object_rects.extend(
                _collect_object_rects(
                    getattr(moduledef, "interact_objects", []) or [],
                    category="interact object",
                )
            )
            _append_overlap_issues(issues, path, object_rects)

    for child in submodules or []:
        _scan_container(
            issues,
            [*path, child.header.name],
            getattr(child, "moduledef", None),
            getattr(child, "submodules", None),
            limit_to_module_path=limit_to_module_path,
        )


def collect_layout_overlap_issues(
    base_picture: BasePicture,
    *,
    limit_to_module_path: list[str] | None = None,
) -> list[VariableIssue]:
    issues: list[VariableIssue] = []
    root_path = [base_picture.header.name]
    _scan_container(
        issues,
        root_path,
        base_picture.moduledef,
        base_picture.submodules,
        limit_to_module_path=limit_to_module_path,
    )

    for typedef in base_picture.moduletype_defs or []:
        typedef_path = [base_picture.header.name, f"TypeDef:{typedef.name}"]
        _scan_container(
            issues,
            typedef_path,
            typedef.moduledef,
            typedef.submodules,
            limit_to_module_path=limit_to_module_path,
        )

    return issues
