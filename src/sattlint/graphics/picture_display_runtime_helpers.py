"""Shared models and lookup helpers for PictureDisplay runtime resolution."""
# pyright: reportUnusedFunction=false, reportUnusedClass=false

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sattlint.parser_api import BasePicture, ModuleTypeDef, ModuleTypeInstance

from ..resolution.common import select_moduletype_def_strict
from ..utils.casefolding import unit_equal, unit_key

if TYPE_CHECKING:
    from ..models.project_graph import ProjectGraph


type _PathKey = tuple[str, ...]


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
    nodes_by_path: dict[_PathKey, RuntimeModuleNode]
    parents_by_path: dict[_PathKey, RuntimeModuleNode]
    suffix_buckets: dict[_PathKey, tuple[RuntimeModuleNode, ...]]


@dataclass(frozen=True, slots=True)
class CompositeRecordOccurrence:
    record_index: int
    declaring_module_path: tuple[str, ...]
    record_start_line: int
    record_end_line: int
    parent_step_adjustment: int = 0


def _local_moduletype_defs(base_picture: BasePicture) -> tuple[ModuleTypeDef, ...]:
    return tuple(
        moduletype
        for moduletype in base_picture.moduletype_defs or []
        if _is_local_moduletype_def(base_picture, moduletype)
    )


def _is_local_moduletype_def(base_picture: BasePicture, moduletype: ModuleTypeDef) -> bool:
    origin_file = getattr(base_picture, "origin_file", None)
    origin_lib = unit_key(getattr(base_picture, "origin_lib", None) or "")
    if not origin_file and not origin_lib:
        return True
    moduletype_origin_lib = unit_key(moduletype.origin_lib or "")
    if origin_lib and moduletype_origin_lib:
        root_stem = _file_stem_key(origin_file)
        if root_stem and origin_lib == root_stem:
            return moduletype_origin_lib == origin_lib
    return _same_origin_file_stem(moduletype.origin_file, origin_file)


def _same_origin_file_stem(origin_file: str | None, root_origin: str | None) -> bool:
    if not origin_file:
        return True
    if not root_origin:
        return False
    return _file_stem_key(origin_file) == _file_stem_key(root_origin)


def _file_stem_key(file_name: str | None) -> str | None:
    if not file_name:
        return None
    try:
        return unit_key(Path(file_name).stem)
    except (TypeError, ValueError):
        return unit_key(file_name.rsplit(".", 1)[0])


def _moduletype_identity_key(moduletype: ModuleTypeDef) -> tuple[str, str, str]:
    return (
        unit_key(moduletype.origin_lib or ""),
        unit_key(moduletype.name),
        unit_key(moduletype.origin_file or ""),
    )


def _candidate_moduletype_defs(base_picture: BasePicture, graph: ProjectGraph | None) -> tuple[ModuleTypeDef, ...]:
    candidates: list[ModuleTypeDef] = []
    seen: set[tuple[str, str, str]] = set()

    for moduletype in tuple(getattr(base_picture, "moduletype_defs", ()) or ()):
        key = _moduletype_identity_key(moduletype)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(moduletype)

    if graph is not None and graph.moduletype_defs:
        for moduletype in graph.moduletype_defs.values():
            key = _moduletype_identity_key(moduletype)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(moduletype)

    return tuple(candidates)


def _candidate_moduletype_index(
    base_picture: BasePicture,
    graph: ProjectGraph | None,
) -> dict[str, tuple[ModuleTypeDef, ...]]:
    index: dict[str, list[ModuleTypeDef]] = {}
    for moduletype in _candidate_moduletype_defs(base_picture, graph):
        index.setdefault(unit_key(moduletype.name), []).append(moduletype)
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
    matches = list(candidate_moduletype_index.get(unit_key(child.moduletype_name), ()))
    try:
        return select_moduletype_def_strict(
            base_picture,
            child.moduletype_name,
            matches,
            current_library=current_library,
            current_file=current_file,
            unavailable_libraries=(graph.unavailable_libraries if graph is not None else None),
            library_dependencies=(graph.library_dependencies if graph is not None else None),
            source_dependencies=(graph.source_dependencies if graph is not None else None),
        )
    except ValueError:
        return None


def _path_key(path: tuple[str, ...]) -> _PathKey:
    return tuple(unit_key(segment) for segment in path)


def _index_runtime_tree(root: RuntimeModuleNode) -> RuntimeTree:
    nodes_by_path: dict[_PathKey, RuntimeModuleNode] = {}
    parents_by_path: dict[_PathKey, RuntimeModuleNode] = {}
    suffix_buckets: dict[_PathKey, list[RuntimeModuleNode]] = {}

    def visit(node: RuntimeModuleNode, parent: RuntimeModuleNode | None) -> None:
        path_key = _path_key(node.path)
        nodes_by_path[path_key] = node
        if parent is not None:
            parents_by_path[path_key] = parent
        for suffix_length in range(2, len(path_key) + 1):
            suffix_buckets.setdefault(path_key[-suffix_length:], []).append(node)
        for child in node.children:
            visit(child, node)

    visit(root, None)
    return RuntimeTree(
        root=root,
        nodes_by_path=nodes_by_path,
        parents_by_path=parents_by_path,
        suffix_buckets={
            suffix: tuple(sorted(nodes, key=lambda node: (len(node.path), _path_key(node.path))))
            for suffix, nodes in suffix_buckets.items()
        },
    )


def find_node(runtime_tree: RuntimeTree, path: tuple[str, ...]) -> RuntimeModuleNode | None:
    return runtime_tree.nodes_by_path.get(_path_key(path))


def find_parent_node(runtime_tree: RuntimeTree, path: tuple[str, ...]) -> RuntimeModuleNode | None:
    return runtime_tree.parents_by_path.get(_path_key(path))


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
    path_key = _path_key(path)
    exclude_key = _path_key(exclude_path) if exclude_path is not None else None
    matches: list[RuntimeModuleNode] = []
    seen_paths: set[_PathKey] = set()
    for suffix_length in range(len(path_key), 1, -1):
        for candidate in runtime_tree.suffix_buckets.get(path_key[-suffix_length:], ()):
            candidate_key = _path_key(candidate.path)
            if exclude_key is not None and candidate_key == exclude_key:
                continue
            if candidate_key in seen_paths:
                continue
            seen_paths.add(candidate_key)
            matches.append(candidate)
    return tuple(matches)


def _common_suffix_length(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    match_length = 0
    for left_segment, right_segment in zip(reversed(left), reversed(right), strict=False):
        if not unit_equal(left_segment, right_segment):
            break
        match_length += 1
    return match_length


def consume_name(raw_path: str) -> tuple[str, str]:
    index = 0
    while index < len(raw_path) and raw_path[index] not in "+-*":
        index += 1
    return raw_path[:index].strip(), raw_path[index:]


def find_nearest_descendant(node: RuntimeModuleNode, wanted_name: str) -> RuntimeModuleNode | None:
    target = unit_key(wanted_name)
    for child in node.children:
        if unit_key(child.name) == target:
            return child
        match = find_nearest_descendant(child, wanted_name)
        if match is not None:
            return match
    return None
