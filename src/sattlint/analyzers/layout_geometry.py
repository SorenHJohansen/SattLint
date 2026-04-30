from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeInstance,
    SingleModule,
)

from ..grammar import constants as const
from ..reporting.variables_report import IssueKind, VariableIssue

_Rect = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class _PlacedRect:
    label: str
    rect: _Rect


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


def _normalize_rect(coords: object) -> _Rect | None:
    if isinstance(coords, list):
        if len(coords) == 1:
            return _normalize_rect(coords[0])
        if len(coords) == 2 and all(isinstance(point, tuple) and len(point) == 2 for point in coords):
            return _point_pair_to_rect(coords[0], coords[1])
        return None

    if isinstance(coords, tuple) and len(coords) == 2:
        first, second = coords
        if isinstance(first, tuple) and len(first) == 2 and isinstance(second, tuple) and len(second) == 2:
            return _point_pair_to_rect(first, second)
    return None


def _module_rect(child: SingleModule | FrameModule | ModuleTypeInstance) -> _PlacedRect | None:
    x, y, _rotation, width, height = child.header.invoke_coord
    rect = _point_pair_to_rect((x, y), (x + width, y + height))
    if rect is None:
        return None
    return _PlacedRect(label=f"module '{child.header.name}'", rect=rect)


def _collect_object_rects(objects: list[object], *, category: str) -> list[_PlacedRect]:
    rects: list[_PlacedRect] = []
    for index, obj in enumerate(objects, start=1):
        properties = getattr(obj, "properties", {}) or {}
        rect = _normalize_rect(properties.get(const.KEY_COORDS))
        if rect is None:
            continue
        object_type = getattr(obj, "type", category)
        rects.append(_PlacedRect(label=f"{category} {object_type} #{index}", rect=rect))
    return rects


def _rects_overlap(left: _Rect, right: _Rect) -> bool:
    return left[0] < right[2] and right[0] < left[2] and left[1] < right[3] and right[1] < left[3]


def _append_overlap_issues(
    issues: list[VariableIssue],
    path: list[str],
    rects: list[_PlacedRect],
) -> None:
    for left, right in combinations(rects, 2):
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
