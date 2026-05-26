"""Shared PictureDisplay path correlation and resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import BasePicture, FrameModule, ModuleTypeDef, ModuleTypeInstance, SingleModule

from .graphics_validation import (
    PictureDisplayPathRow,
    PictureDisplayRecord,
    is_unimplemented_picture_display_asset_path,
    unimplemented_picture_display_asset_message,
)
from .resolution.common import select_moduletype_def_strict

if TYPE_CHECKING:
    from .models.project_graph import ProjectGraph


@dataclass(frozen=True, slots=True)
class PictureDisplayOccurrence:
    program_name: str
    declaring_module_path: tuple[str, ...]
    record: PictureDisplayRecord
    parent_step_adjustment: int = 0


@dataclass(frozen=True, slots=True)
class PictureDisplayPathResolution:
    path_text: str
    program_name: str
    declaring_module_path: tuple[str, ...]
    resolved_module_path: tuple[str, ...] | None
    failure_reason: str | None = None
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.resolved_module_path is not None and self.failure_reason is None


@dataclass(frozen=True, slots=True)
class PictureDisplayPathDiagnostic:
    occurrence: PictureDisplayOccurrence
    path_row: PictureDisplayPathRow
    resolution: PictureDisplayPathResolution


def format_picture_display_path_diagnostic(diagnostic: PictureDisplayPathDiagnostic) -> str:
    module_path = ".".join(diagnostic.occurrence.declaring_module_path) or diagnostic.occurrence.program_name
    detail = diagnostic.resolution.detail or diagnostic.resolution.failure_reason or "unknown failure"
    return (
        f"PictureDisplay in module {module_path!r} path {diagnostic.path_row.raw_text!r} "
        f"could not be resolved: {detail}"
    )


@dataclass(frozen=True, slots=True)
class _CompositePlaceholder:
    record_index: int
    module_path: tuple[str, ...]
    moduletype_name: str | None = None
    moduletype_relative_path: tuple[str, ...] = ()
    parent_step_adjustment: int = 0


@dataclass(frozen=True, slots=True)
class _RuntimeModuleNode:
    name: str
    path: tuple[str, ...]
    current_library: str | None
    current_file: str | None
    resolved_moduletype_name: str | None = None
    children: tuple[_RuntimeModuleNode, ...] = ()


def correlate_picture_display_records(
    base_picture: BasePicture,
    records: tuple[PictureDisplayRecord, ...],
    *,
    graph: ProjectGraph | None = None,
) -> tuple[PictureDisplayOccurrence, ...]:
    placeholders = {
        placeholder.record_index: placeholder
        for placeholder in _collect_concrete_composite_placeholders(base_picture, graph=graph)
    }
    return tuple(
        PictureDisplayOccurrence(
            program_name=base_picture.header.name,
            declaring_module_path=placeholder.module_path,
            record=record,
            parent_step_adjustment=placeholder.parent_step_adjustment,
        )
        for record in records
        if (placeholder := placeholders.get(record.record_index)) is not None
    )


def diagnose_picture_display_paths(
    base_picture: BasePicture,
    occurrences: tuple[PictureDisplayOccurrence, ...],
    *,
    graph: ProjectGraph | None = None,
) -> tuple[PictureDisplayPathDiagnostic, ...]:
    diagnostics: list[PictureDisplayPathDiagnostic] = []
    runtime_trees: dict[str, _RuntimeModuleNode] = {}
    for occurrence in occurrences:
        for path_row in occurrence.record.path_rows:
            if path_row.kind != "literal":
                continue
            resolution = resolve_picture_display_path(
                path_row.raw_text,
                base_picture=base_picture,
                declaring_module_path=occurrence.declaring_module_path,
                graph=graph,
                parent_step_adjustment=occurrence.parent_step_adjustment,
                _runtime_trees=runtime_trees,
            )
            if resolution.ok:
                continue
            diagnostics.append(
                PictureDisplayPathDiagnostic(
                    occurrence=occurrence,
                    path_row=path_row,
                    resolution=resolution,
                )
            )
    return tuple(diagnostics)


def resolve_picture_display_path(
    path_text: str,
    *,
    base_picture: BasePicture,
    declaring_module_path: tuple[str, ...] | list[str],
    graph: ProjectGraph | None = None,
    parent_step_adjustment: int = 0,
    _runtime_trees: dict[str, _RuntimeModuleNode] | None = None,
) -> PictureDisplayPathResolution:
    stripped = path_text.strip()
    module_path = tuple(str(segment) for segment in declaring_module_path)
    if not stripped:
        return PictureDisplayPathResolution(
            path_text=path_text,
            program_name=base_picture.header.name,
            declaring_module_path=module_path,
            resolved_module_path=module_path,
        )

    if is_unimplemented_picture_display_asset_path(stripped):
        return PictureDisplayPathResolution(
            path_text=path_text,
            program_name=base_picture.header.name,
            declaring_module_path=module_path,
            resolved_module_path=None,
            failure_reason="unimplemented_asset",
            detail=unimplemented_picture_display_asset_message(),
        )

    program_name, raw_path = _split_program_prefix(stripped, default_program=base_picture.header.name)
    target_picture = _resolve_program_picture(program_name, base_picture=base_picture, graph=graph)
    if target_picture is None:
        return PictureDisplayPathResolution(
            path_text=path_text,
            program_name=program_name,
            declaring_module_path=module_path,
            resolved_module_path=None,
            failure_reason="missing_program",
            detail=f"program unit {program_name!r} is not loaded",
        )

    runtime_tree_key = program_name.casefold()
    root = _runtime_trees.get(runtime_tree_key) if _runtime_trees is not None else None
    if root is None:
        root = _build_runtime_tree(target_picture, graph=graph)
        if _runtime_trees is not None:
            _runtime_trees[runtime_tree_key] = root
    current = root if program_name.casefold() != base_picture.header.name.casefold() else _find_node(root, module_path)
    if current is None and program_name.casefold() == base_picture.header.name.casefold():
        current = _find_best_suffix_node(root, module_path)
    if current is None:
        return PictureDisplayPathResolution(
            path_text=path_text,
            program_name=program_name,
            declaring_module_path=module_path,
            resolved_module_path=None,
            failure_reason="missing_named_child",
            detail=f"declaring module {'.'.join(module_path)!r} is not present in the resolved module tree",
        )

    parent_steps = 0
    while raw_path.startswith("-"):
        parent_steps += 1
        raw_path = raw_path[1:]
    if parent_steps:
        parent_result = _ascend_parent_steps(
            root,
            current,
            steps=max(parent_steps + 1 + parent_step_adjustment, 0),
            path_text=path_text,
            program_name=program_name,
            declaring_module_path=module_path,
        )
        if isinstance(parent_result, PictureDisplayPathResolution):
            return parent_result
        current = parent_result

    if raw_path.startswith("0"):
        current = root
        raw_path = raw_path[1:]

    if not raw_path:
        return PictureDisplayPathResolution(
            path_text=path_text,
            program_name=program_name,
            declaring_module_path=module_path,
            resolved_module_path=current.path,
        )

    while raw_path:
        if raw_path.startswith("+"):
            plus_count = 0
            while plus_count < len(raw_path) and raw_path[plus_count] == "+":
                plus_count += 1
            raw_path = raw_path[plus_count:]

            # A single leading '+' is the separator before an explicit child name.
            # Additional '+' markers represent implicit single-child descent steps.
            implicit_steps = plus_count - 1 if raw_path and raw_path[0] not in "+-*" else plus_count
            implicit_result = _descend_implicit_steps(
                current,
                steps=implicit_steps,
                path_text=path_text,
                program_name=program_name,
                declaring_module_path=module_path,
            )
            if isinstance(implicit_result, PictureDisplayPathResolution):
                return implicit_result
            current = implicit_result
            continue

        if raw_path.startswith("*"):
            token, raw_path = _consume_name(raw_path[1:])
            match = _find_nearest_descendant(current, token)
            if match is None:
                return PictureDisplayPathResolution(
                    path_text=path_text,
                    program_name=program_name,
                    declaring_module_path=module_path,
                    resolved_module_path=None,
                    failure_reason="wildcard_miss",
                    detail=f"wildcard '*{token}' found no descendant under {'.'.join(current.path)!r}",
                )
            current = match
            continue

        token, raw_path = _consume_name(raw_path)
        matches = [child for child in current.children if child.name.casefold() == token.casefold()]
        if not matches:
            return PictureDisplayPathResolution(
                path_text=path_text,
                program_name=program_name,
                declaring_module_path=module_path,
                resolved_module_path=None,
                failure_reason="missing_named_child",
                detail=f"module {token!r} was not found under {'.'.join(current.path)!r}",
            )
        if len(matches) > 1:
            return PictureDisplayPathResolution(
                path_text=path_text,
                program_name=program_name,
                declaring_module_path=module_path,
                resolved_module_path=None,
                failure_reason="ambiguous_named_child",
                detail=f"module {token!r} is ambiguous under {'.'.join(current.path)!r}",
            )
        current = matches[0]

    return PictureDisplayPathResolution(
        path_text=path_text,
        program_name=program_name,
        declaring_module_path=module_path,
        resolved_module_path=current.path,
    )


def _descend_implicit_steps(
    current: _RuntimeModuleNode,
    *,
    steps: int,
    path_text: str,
    program_name: str,
    declaring_module_path: tuple[str, ...],
) -> _RuntimeModuleNode | PictureDisplayPathResolution:
    for _ in range(steps):
        child_count = len(current.children)
        if child_count == 0:
            return PictureDisplayPathResolution(
                path_text=path_text,
                program_name=program_name,
                declaring_module_path=declaring_module_path,
                resolved_module_path=None,
                failure_reason="missing_named_child",
                detail=f"implicit '+' descent has no child under {'.'.join(current.path)!r}",
            )
        current = current.children[0]
    return current


def _ascend_parent_steps(
    root: _RuntimeModuleNode,
    current: _RuntimeModuleNode,
    *,
    steps: int,
    path_text: str,
    program_name: str,
    declaring_module_path: tuple[str, ...],
) -> _RuntimeModuleNode | PictureDisplayPathResolution:
    for _ in range(steps):
        if len(current.path) <= 1:
            return PictureDisplayPathResolution(
                path_text=path_text,
                program_name=program_name,
                declaring_module_path=declaring_module_path,
                resolved_module_path=None,
                failure_reason="missing_parent",
                detail="path stepped above BasePicture",
            )
        parent = _find_node(root, current.path[:-1])
        if parent is None:
            return PictureDisplayPathResolution(
                path_text=path_text,
                program_name=program_name,
                declaring_module_path=declaring_module_path,
                resolved_module_path=None,
                failure_reason="missing_parent",
                detail=f"could not resolve parent of {'.'.join(current.path)!r}",
            )
        current = parent
    return current


def _split_program_prefix(path_text: str, *, default_program: str) -> tuple[str, str]:
    prefix, delimiter, remainder = path_text.partition(":")
    if not delimiter:
        return default_program, path_text
    if not prefix.strip():
        return default_program, remainder
    return prefix.strip(), remainder.strip()


def _resolve_program_picture(
    program_name: str,
    *,
    base_picture: BasePicture,
    graph: ProjectGraph | None,
) -> BasePicture | None:
    if program_name.casefold() == base_picture.header.name.casefold():
        return base_picture
    if graph is None:
        return None
    for candidate_name, candidate in graph.ast_by_name.items():
        if candidate_name.casefold() == program_name.casefold():
            return candidate
    return None


def _collect_concrete_composite_placeholders(
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
    origin_file = (base_picture.origin_file or "").casefold()
    origin_lib = (base_picture.origin_lib or "").casefold()
    if not origin_file and not origin_lib:
        return tuple(base_picture.moduletype_defs or [])
    return tuple(
        moduletype
        for moduletype in base_picture.moduletype_defs or []
        if (moduletype.origin_file or "").casefold() == origin_file
        and (moduletype.origin_lib or "").casefold() == origin_lib
    )


def _is_local_moduletype_def(base_picture: BasePicture, moduletype: ModuleTypeDef) -> bool:
    origin_file = (base_picture.origin_file or "").casefold()
    origin_lib = (base_picture.origin_lib or "").casefold()
    if not origin_file and not origin_lib:
        return True
    return (moduletype.origin_file or "").casefold() == origin_file and (
        moduletype.origin_lib or ""
    ).casefold() == origin_lib


def _build_runtime_tree(base_picture: BasePicture, *, graph: ProjectGraph | None) -> _RuntimeModuleNode:
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
    return _RuntimeModuleNode(
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
) -> _RuntimeModuleNode:
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
    return _RuntimeModuleNode(
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
) -> _RuntimeModuleNode:
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
        return _RuntimeModuleNode(
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
        return _RuntimeModuleNode(
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
        return _RuntimeModuleNode(
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
    return _RuntimeModuleNode(
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


def _find_node(root: _RuntimeModuleNode, path: tuple[str, ...]) -> _RuntimeModuleNode | None:
    lowered_path = tuple(segment.casefold() for segment in path)
    if tuple(segment.casefold() for segment in root.path) == lowered_path:
        return root
    for child in root.children:
        match = _find_node(child, path)
        if match is not None:
            return match
    return None


def _find_best_suffix_node(root: _RuntimeModuleNode, path: tuple[str, ...]) -> _RuntimeModuleNode | None:
    best_match: _RuntimeModuleNode | None = None
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


def _iter_runtime_nodes(root: _RuntimeModuleNode) -> tuple[_RuntimeModuleNode, ...]:
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


def _consume_name(raw_path: str) -> tuple[str, str]:
    index = 0
    while index < len(raw_path) and raw_path[index] not in "+-*":
        index += 1
    return raw_path[:index].strip(), raw_path[index:]


def _find_nearest_descendant(node: _RuntimeModuleNode, wanted_name: str) -> _RuntimeModuleNode | None:
    target = wanted_name.casefold()
    for child in node.children:
        if child.name.casefold() == target:
            return child
        match = _find_nearest_descendant(child, wanted_name)
        if match is not None:
            return match
    return None


__all__ = [
    "PictureDisplayOccurrence",
    "PictureDisplayPathDiagnostic",
    "PictureDisplayPathResolution",
    "correlate_picture_display_records",
    "diagnose_picture_display_paths",
    "format_picture_display_path_diagnostic",
    "resolve_picture_display_path",
]
