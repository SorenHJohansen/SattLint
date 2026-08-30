# pyright: reportPrivateUsage=false
"""PictureDisplay runtime-tree construction and placeholder correlation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import BasePicture, FrameModule, ModuleTypeDef, ModuleTypeInstance, SingleModule

from ._picture_display_path_runtime_helpers import (
    CompositeRecordOccurrence,
    RuntimeModuleNode,
    RuntimeTree,
    _candidate_moduletype_defs,
    _candidate_moduletype_index,
    _common_suffix_length,
    _CompositePlaceholder,
    _index_runtime_tree,
    _is_local_moduletype_def,
    _local_moduletype_defs,
    _same_origin_file_stem,
    consume_name,
    find_best_suffix_node,
    find_nearest_descendant,
    find_node,
    find_parent_node,
    find_suffix_nodes,
)
from .graphics_validation import GraphicsCompositeRecord
from .resolution.common import select_moduletype_def_strict

__all__ = [
    "CompositeRecordOccurrence",
    "RuntimeModuleNode",
    "RuntimeTree",
    "_candidate_moduletype_defs",
    "_candidate_moduletype_index",
    "_common_suffix_length",
    "_file_stem_casefold",
    "_index_runtime_tree",
    "_is_local_moduletype_def",
    "_local_moduletype_defs",
    "_same_origin_file_stem",
    "build_runtime_tree",
    "collect_concrete_composite_placeholders",
    "consume_name",
    "correlate_composite_records",
    "find_best_suffix_node",
    "find_nearest_descendant",
    "find_node",
    "find_parent_node",
    "find_suffix_nodes",
]

if TYPE_CHECKING:
    from .models.project_graph import ProjectGraph


def _file_stem_casefold(file_name: str | None) -> str | None:
    if not file_name:
        return None
    try:
        return Path(file_name).stem.casefold()
    except (TypeError, ValueError):
        return file_name.rsplit(".", 1)[0].casefold()


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
    except ValueError:
        return None


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


def collect_concrete_composite_placeholders(  # noqa: PLR0915
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
        if moduletype_key in active_moduletype_keys:  # pragma: no cover
            return  # pragma: no cover

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
    ) -> None:
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
        visit_local_moduletype_def(moduletype)
    visit_moduledef(base_picture.moduledef, root_path, parent_step_adjustment=0)
    return tuple(placeholders)


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
