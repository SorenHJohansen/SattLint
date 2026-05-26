"""Private runtime-tree helpers for PictureDisplay path resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import BasePicture, FrameModule, ModuleTypeDef, ModuleTypeInstance, SingleModule

from .graphics_validation import GraphicsCompositeRecord
from .resolution.common import select_moduletype_def_strict

if TYPE_CHECKING:
    from .models.project_graph import ProjectGraph


@dataclass(frozen=True, slots=True)
class _CompositePlaceholder:
    record_index: int
    module_path: tuple[str, ...]
    moduletype_name: str | None = None
    moduletype_relative_path: tuple[str, ...] = ()
    parent_step_adjustment: int = 0


@dataclass(frozen=True, slots=True)
class RuntimeModuleNode:
    name: str
    path: tuple[str, ...]
    current_library: str | None
    current_file: str | None
    resolved_moduletype_name: str | None = None
    children: tuple[RuntimeModuleNode, ...] = ()


@dataclass(frozen=True, slots=True)
class CompositeRecordOccurrence:
    record_index: int
    declaring_module_path: tuple[str, ...]
    record_start_line: int
    record_end_line: int
    parent_step_adjustment: int = 0


def correlate_composite_records(
    base_picture: BasePicture,
    records: tuple[GraphicsCompositeRecord, ...],
    *,
    graph: ProjectGraph | None = None,
) -> tuple[CompositeRecordOccurrence, ...]:
    placeholders = {
        placeholder.record_index: placeholder
        for placeholder in collect_concrete_composite_placeholders(base_picture, graph=graph)
    }
    return tuple(
        CompositeRecordOccurrence(
            record_index=record.record_index,
            declaring_module_path=placeholder.module_path,
            record_start_line=record.record_start_line,
            record_end_line=record.record_end_line,
            parent_step_adjustment=placeholder.parent_step_adjustment,
        )
        for record in records
        if (placeholder := placeholders.get(record.record_index)) is not None
    )


def collect_concrete_composite_placeholders(
    base_picture: BasePicture,
    *,
    graph: ProjectGraph | None,
) -> tuple[_CompositePlaceholder, ...]:
    placeholders: list[_CompositePlaceholder] = []
    record_index = 0
    root_path = (base_picture.header.name,)

    def visit_moduledef(moduledef: object, path: tuple[str, ...], *, parent_step_adjustment: int) -> None:
        nonlocal record_index
        graph_objects = getattr(moduledef, "graph_objects", None)
        if not isinstance(graph_objects, list):
            return
        typed_graph_objects = cast(list[object], graph_objects)
        for graph_object in typed_graph_objects:
            object_type = getattr(graph_object, "type", None)
            if (
                not isinstance(object_type, str)
                or object_type.casefold() != const.GRAMMAR_VALUE_COMPOSITEOBJECT.casefold()
            ):
                continue
            record_index += 1
            placeholders.append(
                _CompositePlaceholder(
                    record_index=record_index,
                    module_path=path,
                    parent_step_adjustment=parent_step_adjustment,
                )
            )

    def visit_runtime_child(
        child: SingleModule | FrameModule | ModuleTypeInstance,
        *,
        path: tuple[str, ...],
        current_library: str | None,
        current_file: str | None,
        active_moduletype_keys: set[tuple[str, str, str]],
        parent_step_adjustment: int,
    ) -> None:
        if isinstance(child, SingleModule | FrameModule):
            for nested in child.submodules or []:
                visit_runtime_child(
                    nested,
                    path=(*path, nested.header.name),
                    current_library=current_library,
                    current_file=current_file,
                    active_moduletype_keys=active_moduletype_keys.copy(),
                    parent_step_adjustment=parent_step_adjustment,
                )
            visit_moduledef(child.moduledef, path, parent_step_adjustment=parent_step_adjustment)
            return

        matches = [
            moduletype
            for moduletype in _candidate_moduletype_defs(base_picture, graph)
            if moduletype.name.casefold() == child.moduletype_name.casefold()
        ]
        try:
            resolved_moduletype = select_moduletype_def_strict(
                base_picture,
                child.moduletype_name,
                matches,
                current_library=current_library,
                current_file=current_file,
                unavailable_libraries=(graph.unavailable_libraries if graph is not None else None),
            )
        except Exception:
            resolved_moduletype = None

        if resolved_moduletype is None:
            return

        moduletype_key = (
            (resolved_moduletype.origin_lib or current_library or "").casefold(),
            resolved_moduletype.name.casefold(),
            (resolved_moduletype.origin_file or current_file or "").casefold(),
        )
        if moduletype_key in active_moduletype_keys:
            return

        nested_keys = set(active_moduletype_keys)
        nested_keys.add(moduletype_key)
        child_parent_step_adjustment = (
            -1 if _is_local_moduletype_def(base_picture, resolved_moduletype) else parent_step_adjustment
        )
        for nested in resolved_moduletype.submodules or []:
            visit_runtime_child(
                nested,
                path=(*path, nested.header.name),
                current_library=resolved_moduletype.origin_lib or current_library,
                current_file=resolved_moduletype.origin_file or current_file,
                active_moduletype_keys=nested_keys.copy(),
                parent_step_adjustment=child_parent_step_adjustment,
            )
        visit_moduledef(
            resolved_moduletype.moduledef,
            path,
            parent_step_adjustment=child_parent_step_adjustment,
        )

    for child in base_picture.submodules or []:
        visit_runtime_child(
            child,
            path=(*root_path, child.header.name),
            current_library=getattr(base_picture, "origin_lib", None),
            current_file=getattr(base_picture, "origin_file", None),
            active_moduletype_keys=set(),
            parent_step_adjustment=0,
        )
    visit_moduledef(base_picture.moduledef, root_path, parent_step_adjustment=0)
    return tuple(placeholders)


def _local_moduletype_defs(base_picture: BasePicture) -> tuple[ModuleTypeDef, ...]:
    return tuple(
        moduletype
        for moduletype in base_picture.moduletype_defs or []
        if _is_local_moduletype_def(base_picture, moduletype)
    )


def _is_local_moduletype_def(base_picture: BasePicture, moduletype: ModuleTypeDef) -> bool:
    origin_file = getattr(base_picture, "origin_file", None)
    origin_lib = (getattr(base_picture, "origin_lib", None) or "").casefold()
    if not origin_file and not origin_lib:
        return True
    moduletype_origin_lib = (moduletype.origin_lib or "").casefold()
    if origin_lib and moduletype_origin_lib:
        root_stem = _file_stem_casefold(origin_file)
        if root_stem and origin_lib == root_stem:
            return moduletype_origin_lib == origin_lib
    return _same_origin_file_stem(moduletype.origin_file, origin_file)


def _same_origin_file_stem(origin_file: str | None, root_origin: str | None) -> bool:
    if not origin_file:
        return True
    if not root_origin:
        return False
    return _file_stem_casefold(origin_file) == _file_stem_casefold(root_origin)


def _file_stem_casefold(file_name: str | None) -> str | None:
    if not file_name:
        return None
    try:
        return Path(file_name).stem.casefold()
    except Exception:
        return file_name.rsplit(".", 1)[0].casefold()


def build_runtime_tree(base_picture: BasePicture, *, graph: ProjectGraph | None) -> RuntimeModuleNode:
    root_path = (base_picture.header.name,)
    current_library = getattr(base_picture, "origin_lib", None)
    current_file = getattr(base_picture, "origin_file", None)
    children = [
        *[
            _build_moduletype_node(
                base_picture,
                moduletype,
                path=(*root_path, moduletype.name),
                graph=graph,
                active_moduletype_keys=set(),
            )
            for moduletype in _local_moduletype_defs(base_picture)
        ],
        *[
            _build_runtime_child(
                base_picture,
                child,
                path=(*root_path, child.header.name),
                graph=graph,
                current_library=current_library,
                current_file=current_file,
                active_moduletype_keys=set(),
            )
            for child in base_picture.submodules or []
        ],
    ]
    return RuntimeModuleNode(
        name=base_picture.header.name,
        path=root_path,
        current_library=current_library,
        current_file=current_file,
        resolved_moduletype_name=None,
        children=tuple(children),
    )


def _build_moduletype_node(
    base_picture: BasePicture,
    moduletype: ModuleTypeDef,
    *,
    path: tuple[str, ...],
    graph: ProjectGraph | None,
    active_moduletype_keys: set[tuple[str, str, str]],
) -> RuntimeModuleNode:
    children = tuple(
        _build_runtime_child(
            base_picture,
            child,
            path=(*path, child.header.name),
            graph=graph,
            current_library=moduletype.origin_lib or base_picture.origin_lib,
            current_file=moduletype.origin_file or base_picture.origin_file,
            active_moduletype_keys=active_moduletype_keys.copy(),
        )
        for child in moduletype.submodules or []
    )
    return RuntimeModuleNode(
        name=path[-1],
        path=path,
        current_library=moduletype.origin_lib or base_picture.origin_lib,
        current_file=moduletype.origin_file or base_picture.origin_file,
        resolved_moduletype_name=None,
        children=children,
    )


def _build_runtime_child(
    base_picture: BasePicture,
    child: SingleModule | FrameModule | ModuleTypeInstance,
    *,
    path: tuple[str, ...],
    graph: ProjectGraph | None,
    current_library: str | None,
    current_file: str | None,
    active_moduletype_keys: set[tuple[str, str, str]],
) -> RuntimeModuleNode:
    if isinstance(child, SingleModule | FrameModule):
        children = tuple(
            _build_runtime_child(
                base_picture,
                nested,
                path=(*path, nested.header.name),
                graph=graph,
                current_library=current_library,
                current_file=current_file,
                active_moduletype_keys=active_moduletype_keys.copy(),
            )
            for nested in child.submodules or []
        )
        return RuntimeModuleNode(
            name=child.header.name,
            path=path,
            current_library=current_library,
            current_file=current_file,
            resolved_moduletype_name=None,
            children=children,
        )

    matches = [
        moduletype
        for moduletype in _candidate_moduletype_defs(base_picture, graph)
        if moduletype.name.casefold() == child.moduletype_name.casefold()
    ]
    try:
        resolved_moduletype = select_moduletype_def_strict(
            base_picture,
            child.moduletype_name,
            matches,
            current_library=current_library,
            current_file=current_file,
            unavailable_libraries=(graph.unavailable_libraries if graph is not None else None),
        )
    except Exception:
        resolved_moduletype = None

    if resolved_moduletype is None:
        return RuntimeModuleNode(
            name=child.header.name,
            path=path,
            current_library=current_library,
            current_file=current_file,
            resolved_moduletype_name=None,
            children=(),
        )

    moduletype_key = (
        (resolved_moduletype.origin_lib or current_library or "").casefold(),
        resolved_moduletype.name.casefold(),
        (resolved_moduletype.origin_file or current_file or "").casefold(),
    )
    if moduletype_key in active_moduletype_keys:
        return RuntimeModuleNode(
            name=child.header.name,
            path=path,
            current_library=resolved_moduletype.origin_lib or current_library,
            current_file=resolved_moduletype.origin_file or current_file,
            resolved_moduletype_name=resolved_moduletype.name,
            children=(),
        )

    nested_keys = set(active_moduletype_keys)
    nested_keys.add(moduletype_key)
    children = tuple(
        _build_runtime_child(
            base_picture,
            nested,
            path=(*path, nested.header.name),
            graph=graph,
            current_library=resolved_moduletype.origin_lib or current_library,
            current_file=resolved_moduletype.origin_file or current_file,
            active_moduletype_keys=nested_keys.copy(),
        )
        for nested in resolved_moduletype.submodules or []
    )
    return RuntimeModuleNode(
        name=child.header.name,
        path=path,
        current_library=resolved_moduletype.origin_lib or current_library,
        current_file=resolved_moduletype.origin_file or current_file,
        resolved_moduletype_name=resolved_moduletype.name,
        children=children,
    )


def _candidate_moduletype_defs(base_picture: BasePicture, graph: ProjectGraph | None) -> tuple[ModuleTypeDef, ...]:
    if graph is not None and graph.moduletype_defs:
        return tuple(graph.moduletype_defs.values())
    return tuple(base_picture.moduletype_defs or [])


def find_node(root: RuntimeModuleNode, path: tuple[str, ...]) -> RuntimeModuleNode | None:
    lowered_path = tuple(segment.casefold() for segment in path)
    if tuple(segment.casefold() for segment in root.path) == lowered_path:
        return root
    for child in root.children:
        match = find_node(child, path)
        if match is not None:
            return match
    return None


def find_best_suffix_node(root: RuntimeModuleNode, path: tuple[str, ...]) -> RuntimeModuleNode | None:
    best_match: RuntimeModuleNode | None = None
    best_suffix_length = 0
    best_path_length = 0
    ambiguous = False
    for candidate in _iter_runtime_nodes(root):
        suffix_length = _common_suffix_length(candidate.path, path)
        if suffix_length < 2:
            continue
        if suffix_length > best_suffix_length:
            best_match = candidate
            best_suffix_length = suffix_length
            best_path_length = len(candidate.path)
            ambiguous = False
            continue
        if suffix_length == best_suffix_length:
            if best_match is not None and len(candidate.path) < best_path_length:
                best_match = candidate
                best_path_length = len(candidate.path)
                ambiguous = False
                continue
            if best_match is not None and len(candidate.path) > best_path_length:
                continue
            ambiguous = True
    if ambiguous:
        return None
    return best_match


def _iter_runtime_nodes(root: RuntimeModuleNode) -> tuple[RuntimeModuleNode, ...]:
    nodes = [root]
    for child in root.children:
        nodes.extend(_iter_runtime_nodes(child))
    return tuple(nodes)


def _common_suffix_length(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    match_length = 0
    for left_segment, right_segment in zip(reversed(left), reversed(right), strict=False):
        if left_segment.casefold() != right_segment.casefold():
            break
        match_length += 1
    return match_length


def consume_name(raw_path: str) -> tuple[str, str]:
    index = 0
    while index < len(raw_path) and raw_path[index] not in "+-*":
        index += 1
    return raw_path[:index].strip(), raw_path[index:]


def find_nearest_descendant(node: RuntimeModuleNode, wanted_name: str) -> RuntimeModuleNode | None:
    target = wanted_name.casefold()
    for child in node.children:
        if child.name.casefold() == target:
            return child
        match = find_nearest_descendant(child, wanted_name)
        if match is not None:
            return match
    return None
