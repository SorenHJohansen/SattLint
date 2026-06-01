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


_LoweredPath = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _CompositePlaceholder:
    record_index: int
    module_path: tuple[str, ...]
    moduletype_name: str | None = None
    moduletype_relative_path: tuple[str, ...] = ()
    parent_step_adjustment: int = 0
    resolution_module_path: tuple[str, ...] | None = None
    resolution_parent_step_adjustment: int | None = None


@dataclass(frozen=True, slots=True)
class RuntimeModuleNode:
    name: str
    path: tuple[str, ...]
    current_library: str | None
    current_file: str | None
    resolved_moduletype_name: str | None = None
    children: tuple[RuntimeModuleNode, ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeTree:
    root: RuntimeModuleNode
    nodes_by_path: dict[_LoweredPath, RuntimeModuleNode]
    parents_by_path: dict[_LoweredPath, RuntimeModuleNode]
    suffix_buckets: dict[_LoweredPath, tuple[RuntimeModuleNode, ...]]


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
    local_instance_resolution_paths: dict[tuple[str, tuple[str, ...]], tuple[tuple[str, ...], int]] = {}
    candidate_moduletype_index = _candidate_moduletype_index(base_picture, graph)
    record_index = 0
    root_path = (base_picture.header.name,)

    def visit_moduledef(
        moduledef: object,
        path: tuple[str, ...],
        *,
        parent_step_adjustment: int,
        moduletype_name: str | None = None,
        moduletype_relative_path: tuple[str, ...] = (),
        resolution_module_path: tuple[str, ...] | None = None,
        resolution_parent_step_adjustment: int | None = None,
    ) -> None:
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
                    moduletype_name=moduletype_name,
                    moduletype_relative_path=moduletype_relative_path,
                    parent_step_adjustment=parent_step_adjustment,
                    resolution_module_path=resolution_module_path,
                    resolution_parent_step_adjustment=resolution_parent_step_adjustment,
                )
            )

    def _local_instance_key(moduletype_name: str, relative_path: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
        return (moduletype_name.casefold(), tuple(segment.casefold() for segment in relative_path))

    def register_local_instance_path(
        moduletype_name: str,
        *,
        relative_path: tuple[str, ...],
        instance_path: tuple[str, ...],
        parent_step_adjustment: int,
    ) -> None:
        key = _local_instance_key(moduletype_name, relative_path)
        local_instance_resolution_paths.setdefault(key, (instance_path, parent_step_adjustment))

    def register_local_instance_resolution_paths(
        moduletype: ModuleTypeDef,
        *,
        instance_path: tuple[str, ...],
    ) -> None:
        def visit_template_moduledef(
            moduledef: object, *, relative_path: tuple[str, ...], current_path: tuple[str, ...]
        ) -> None:
            graph_objects = getattr(moduledef, "graph_objects", None)
            if not isinstance(graph_objects, list):
                return
            for graph_object in cast(list[object], graph_objects):
                graph_object_type = getattr(graph_object, "type", None)
                if not isinstance(graph_object_type, str):
                    continue
                if graph_object_type.casefold() != const.GRAMMAR_VALUE_COMPOSITEOBJECT.casefold():
                    continue
                register_local_instance_path(
                    moduletype.name,
                    relative_path=relative_path,
                    instance_path=current_path,
                    parent_step_adjustment=-1,
                )
                break

        def visit_template_child(
            child: SingleModule | FrameModule, *, relative_path: tuple[str, ...], current_path: tuple[str, ...]
        ) -> None:
            for nested in child.submodules or []:
                if not isinstance(nested, SingleModule | FrameModule):
                    continue
                visit_template_child(
                    nested,
                    relative_path=(*relative_path, nested.header.name),
                    current_path=(*current_path, nested.header.name),
                )
            visit_template_moduledef(child.moduledef, relative_path=relative_path, current_path=current_path)

        visit_template_moduledef(moduletype.moduledef, relative_path=(), current_path=instance_path)
        for nested in moduletype.submodules or []:
            if not isinstance(nested, SingleModule | FrameModule):
                continue
            visit_template_child(
                nested,
                relative_path=(nested.header.name,),
                current_path=(*instance_path, nested.header.name),
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

        resolved_moduletype = _resolve_runtime_moduletype(
            base_picture,
            child,
            current_library=current_library,
            current_file=current_file,
            graph=graph,
            candidate_moduletype_index=candidate_moduletype_index,
        )

        if resolved_moduletype is None:
            return

        if _is_local_moduletype_def(base_picture, resolved_moduletype):
            register_local_instance_resolution_paths(resolved_moduletype, instance_path=path)
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

    def visit_local_moduletype_def(
        moduletype: ModuleTypeDef,
        *,
        active_moduletype_keys: set[tuple[str, str, str]],
    ) -> None:
        moduletype_key = (
            (moduletype.origin_lib or getattr(base_picture, "origin_lib", None) or "").casefold(),
            moduletype.name.casefold(),
            (moduletype.origin_file or getattr(base_picture, "origin_file", None) or "").casefold(),
        )
        if moduletype_key in active_moduletype_keys:
            return

        nested_keys = set(active_moduletype_keys)
        nested_keys.add(moduletype_key)
        moduletype_path = (*root_path, moduletype.name)

        def resolution_context(relative_path: tuple[str, ...]) -> tuple[tuple[str, ...] | None, int | None]:
            return local_instance_resolution_paths.get(
                _local_instance_key(moduletype.name, relative_path), (None, None)
            )

        def visit_template_moduledef(
            moduledef: object, *, relative_path: tuple[str, ...], current_path: tuple[str, ...]
        ) -> None:
            resolution_module_path, resolution_parent_step_adjustment = resolution_context(relative_path)
            visit_moduledef(
                moduledef,
                current_path,
                parent_step_adjustment=0,
                moduletype_name=moduletype.name,
                moduletype_relative_path=relative_path,
                resolution_module_path=resolution_module_path,
                resolution_parent_step_adjustment=resolution_parent_step_adjustment,
            )

        def visit_template_child(
            child: SingleModule | FrameModule, *, relative_path: tuple[str, ...], current_path: tuple[str, ...]
        ) -> None:
            for nested in child.submodules or []:
                if not isinstance(nested, SingleModule | FrameModule):
                    continue
                visit_template_child(
                    nested,
                    relative_path=(*relative_path, nested.header.name),
                    current_path=(*current_path, nested.header.name),
                )
            visit_template_moduledef(child.moduledef, relative_path=relative_path, current_path=current_path)

        for nested in moduletype.submodules or []:
            if not isinstance(nested, SingleModule | FrameModule):
                continue
            visit_template_child(
                nested,
                relative_path=(nested.header.name,),
                current_path=(*moduletype_path, nested.header.name),
            )
        visit_template_moduledef(moduletype.moduledef, relative_path=(), current_path=moduletype_path)

    for child in base_picture.submodules or []:
        visit_runtime_child(
            child,
            path=(*root_path, child.header.name),
            current_library=getattr(base_picture, "origin_lib", None),
            current_file=getattr(base_picture, "origin_file", None),
            active_moduletype_keys=set(),
            parent_step_adjustment=0,
        )
    for moduletype in _local_moduletype_defs(base_picture):
        visit_local_moduletype_def(moduletype, active_moduletype_keys=set())
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


def build_runtime_tree(base_picture: BasePicture, *, graph: ProjectGraph | None) -> RuntimeTree:
    root_path = (base_picture.header.name,)
    current_library = getattr(base_picture, "origin_lib", None)
    current_file = getattr(base_picture, "origin_file", None)
    candidate_moduletype_index = _candidate_moduletype_index(base_picture, graph)
    children = [
        *[
            _build_moduletype_node(
                base_picture,
                moduletype,
                path=(*root_path, moduletype.name),
                graph=graph,
                active_moduletype_keys=set(),
                candidate_moduletype_index=candidate_moduletype_index,
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
                candidate_moduletype_index=candidate_moduletype_index,
            )
            for child in base_picture.submodules or []
        ],
    ]
    return _index_runtime_tree(
        RuntimeModuleNode(
            name=base_picture.header.name,
            path=root_path,
            current_library=current_library,
            current_file=current_file,
            resolved_moduletype_name=None,
            children=tuple(children),
        )
    )


def _build_moduletype_node(
    base_picture: BasePicture,
    moduletype: ModuleTypeDef,
    *,
    path: tuple[str, ...],
    graph: ProjectGraph | None,
    active_moduletype_keys: set[tuple[str, str, str]],
    candidate_moduletype_index: dict[str, tuple[ModuleTypeDef, ...]],
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
            candidate_moduletype_index=candidate_moduletype_index,
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
    candidate_moduletype_index: dict[str, tuple[ModuleTypeDef, ...]],
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
                candidate_moduletype_index=candidate_moduletype_index,
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

    resolved_moduletype = _resolve_runtime_moduletype(
        base_picture,
        child,
        current_library=current_library,
        current_file=current_file,
        graph=graph,
        candidate_moduletype_index=candidate_moduletype_index,
    )

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
            candidate_moduletype_index=candidate_moduletype_index,
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


def _candidate_moduletype_index(
    base_picture: BasePicture,
    graph: ProjectGraph | None,
) -> dict[str, tuple[ModuleTypeDef, ...]]:
    index: dict[str, list[ModuleTypeDef]] = {}
    for moduletype in _candidate_moduletype_defs(base_picture, graph):
        index.setdefault(moduletype.name.casefold(), []).append(moduletype)
    return {name: tuple(matches) for name, matches in index.items()}


def _resolve_runtime_moduletype(
    base_picture: BasePicture,
    child: ModuleTypeInstance,
    *,
    current_library: str | None,
    current_file: str | None,
    graph: ProjectGraph | None,
    candidate_moduletype_index: dict[str, tuple[ModuleTypeDef, ...]],
) -> ModuleTypeDef | None:
    matches = list(candidate_moduletype_index.get(child.moduletype_name.casefold(), ()))
    try:
        return select_moduletype_def_strict(
            base_picture,
            child.moduletype_name,
            matches,
            current_library=current_library,
            current_file=current_file,
            unavailable_libraries=(graph.unavailable_libraries if graph is not None else None),
        )
    except Exception:
        return None


def _lowered_path(path: tuple[str, ...]) -> _LoweredPath:
    return tuple(segment.casefold() for segment in path)


def _index_runtime_tree(root: RuntimeModuleNode) -> RuntimeTree:
    nodes_by_path: dict[_LoweredPath, RuntimeModuleNode] = {}
    parents_by_path: dict[_LoweredPath, RuntimeModuleNode] = {}
    suffix_buckets: dict[_LoweredPath, list[RuntimeModuleNode]] = {}

    def visit(node: RuntimeModuleNode, parent: RuntimeModuleNode | None) -> None:
        lowered_path = _lowered_path(node.path)
        nodes_by_path[lowered_path] = node
        if parent is not None:
            parents_by_path[lowered_path] = parent
        for suffix_length in range(2, len(lowered_path) + 1):
            suffix_buckets.setdefault(lowered_path[-suffix_length:], []).append(node)
        for child in node.children:
            visit(child, node)

    visit(root, None)
    return RuntimeTree(
        root=root,
        nodes_by_path=nodes_by_path,
        parents_by_path=parents_by_path,
        suffix_buckets={
            suffix: tuple(sorted(nodes, key=lambda node: (len(node.path), _lowered_path(node.path))))
            for suffix, nodes in suffix_buckets.items()
        },
    )


def find_node(runtime_tree: RuntimeTree, path: tuple[str, ...]) -> RuntimeModuleNode | None:
    return runtime_tree.nodes_by_path.get(_lowered_path(path))


def find_parent_node(runtime_tree: RuntimeTree, path: tuple[str, ...]) -> RuntimeModuleNode | None:
    return runtime_tree.parents_by_path.get(_lowered_path(path))


def find_best_suffix_node(
    runtime_tree: RuntimeTree,
    path: tuple[str, ...],
    *,
    exclude_path: tuple[str, ...] | None = None,
) -> RuntimeModuleNode | None:
    matches = find_suffix_nodes(runtime_tree, path, exclude_path=exclude_path)
    if not matches:
        return None
    best_match = matches[0]
    best_suffix_length = _common_suffix_length(best_match.path, path)
    best_path_length = len(best_match.path)
    for candidate in matches[1:]:
        candidate_suffix_length = _common_suffix_length(candidate.path, path)
        if candidate_suffix_length < best_suffix_length:
            break
        if len(candidate.path) == best_path_length:
            return None
    return best_match


def find_suffix_nodes(
    runtime_tree: RuntimeTree,
    path: tuple[str, ...],
    *,
    exclude_path: tuple[str, ...] | None = None,
) -> tuple[RuntimeModuleNode, ...]:
    lowered_path = _lowered_path(path)
    lowered_exclude_path = _lowered_path(exclude_path) if exclude_path is not None else None
    matches: list[RuntimeModuleNode] = []
    seen_paths: set[_LoweredPath] = set()
    for suffix_length in range(len(lowered_path), 1, -1):
        for candidate in runtime_tree.suffix_buckets.get(lowered_path[-suffix_length:], ()):
            lowered_candidate_path = _lowered_path(candidate.path)
            if lowered_exclude_path is not None and lowered_candidate_path == lowered_exclude_path:
                continue
            if lowered_candidate_path in seen_paths:
                continue
            seen_paths.add(lowered_candidate_path)
            matches.append(candidate)
    return tuple(matches)


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
