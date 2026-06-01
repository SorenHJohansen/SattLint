"""Shared PictureDisplay path correlation and resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sattline_parser.models.ast_model import BasePicture

from ._picture_display_path_runtime import (
    RuntimeModuleNode,
    RuntimeTree,
    build_runtime_tree,
    collect_concrete_composite_placeholders,
    consume_name,
    find_best_suffix_node,
    find_nearest_descendant,
    find_node,
    find_parent_node,
    find_suffix_nodes,
)
from .graphics_validation import (
    PictureDisplayPathRow,
    PictureDisplayRecord,
    is_unimplemented_picture_display_asset_path,
    unimplemented_picture_display_asset_message,
)

if TYPE_CHECKING:
    from .models.project_graph import ProjectGraph


@dataclass(frozen=True, slots=True)
class PictureDisplayOccurrence:
    program_name: str
    declaring_module_path: tuple[str, ...]
    record: PictureDisplayRecord
    parent_step_adjustment: int = 0
    resolution_module_path: tuple[str, ...] | None = None
    resolution_parent_step_adjustment: int | None = None


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


def correlate_picture_display_records(
    base_picture: BasePicture,
    records: tuple[PictureDisplayRecord, ...],
    *,
    graph: ProjectGraph | None = None,
) -> tuple[PictureDisplayOccurrence, ...]:
    placeholders = {
        placeholder.record_index: placeholder
        for placeholder in collect_concrete_composite_placeholders(base_picture, graph=graph)
    }
    return tuple(
        PictureDisplayOccurrence(
            program_name=base_picture.header.name,
            declaring_module_path=placeholder.module_path,
            record=record,
            parent_step_adjustment=placeholder.parent_step_adjustment,
            resolution_module_path=placeholder.resolution_module_path,
            resolution_parent_step_adjustment=placeholder.resolution_parent_step_adjustment,
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
    runtime_trees: dict[str, RuntimeTree] = {}
    for occurrence in occurrences:
        for path_row in occurrence.record.path_rows:
            if path_row.kind != "literal":
                continue
            resolution_module_path = (
                getattr(occurrence, "resolution_module_path", None) or occurrence.declaring_module_path
            )
            resolution_parent_step_adjustment_value = getattr(
                occurrence,
                "resolution_parent_step_adjustment",
                None,
            )
            resolution_parent_step_adjustment = (
                resolution_parent_step_adjustment_value
                if isinstance(resolution_parent_step_adjustment_value, int)
                else occurrence.parent_step_adjustment
            )
            resolution = resolve_picture_display_path(
                path_row.raw_text,
                base_picture=base_picture,
                declaring_module_path=resolution_module_path,
                graph=graph,
                parent_step_adjustment=resolution_parent_step_adjustment,
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
    _runtime_trees: dict[str, RuntimeTree] | None = None,
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
    runtime_tree = _runtime_trees.get(runtime_tree_key) if _runtime_trees is not None else None
    if runtime_tree is None:
        runtime_tree = build_runtime_tree(target_picture, graph=graph)
        if _runtime_trees is not None:
            _runtime_trees[runtime_tree_key] = runtime_tree
    same_program = program_name.casefold() == base_picture.header.name.casefold()
    exact_current = runtime_tree.root if not same_program else find_node(runtime_tree, module_path)
    suffix_current = None
    suffix_candidates: tuple[RuntimeModuleNode, ...] = ()
    if same_program:
        suffix_candidates = find_suffix_nodes(
            runtime_tree,
            module_path,
            exclude_path=module_path if exact_current is not None else None,
        )
        suffix_current = find_best_suffix_node(
            runtime_tree,
            module_path,
            exclude_path=module_path if exact_current is not None else None,
        )

    used_suffix_recovery = False
    current = exact_current
    if current is None and same_program:
        current = suffix_current
        used_suffix_recovery = current is not None
    if current is None:
        return PictureDisplayPathResolution(
            path_text=path_text,
            program_name=program_name,
            declaring_module_path=module_path,
            resolved_module_path=None,
            failure_reason="missing_named_child",
            detail=f"declaring module {'.'.join(module_path)!r} is not present in the resolved module tree",
        )

    resolution = _resolve_picture_display_path_from_current(
        runtime_tree,
        current,
        raw_path,
        path_text=path_text,
        program_name=program_name,
        declaring_module_path=module_path,
        parent_step_adjustment=parent_step_adjustment,
        used_suffix_recovery=used_suffix_recovery,
    )
    if resolution.ok or not same_program or exact_current is None or suffix_current is None:
        return resolution

    retry_parent_step_adjustment = parent_step_adjustment
    retry_used_suffix_recovery = True
    if parent_step_adjustment < 0:
        retry_candidates = (suffix_current,)
    elif resolution.failure_reason == "missing_parent":
        retry_candidates = tuple(
            candidate for candidate in suffix_candidates if len(candidate.path) > len(exact_current.path)
        )
        retry_parent_step_adjustment = -1
        retry_used_suffix_recovery = False
    else:
        return resolution

    for retry_candidate in retry_candidates:
        retry_resolution = _resolve_picture_display_path_from_current(
            runtime_tree,
            retry_candidate,
            raw_path,
            path_text=path_text,
            program_name=program_name,
            declaring_module_path=module_path,
            parent_step_adjustment=retry_parent_step_adjustment,
            used_suffix_recovery=retry_used_suffix_recovery,
        )
        if retry_resolution.ok:
            return retry_resolution

    return resolution


def _resolve_picture_display_path_from_current(
    runtime_tree: RuntimeTree,
    current: RuntimeModuleNode,
    raw_path: str,
    *,
    path_text: str,
    program_name: str,
    declaring_module_path: tuple[str, ...],
    parent_step_adjustment: int,
    used_suffix_recovery: bool,
) -> PictureDisplayPathResolution:
    raw_path = raw_path

    parent_steps = 0
    while raw_path.startswith("-"):
        parent_steps += 1
        raw_path = raw_path[1:]
    if parent_steps:
        effective_parent_step_adjustment = parent_step_adjustment
        if used_suffix_recovery and effective_parent_step_adjustment < 0:
            effective_parent_step_adjustment = 0
        extra_parent_step = 0 if raw_path.startswith("+") and effective_parent_step_adjustment >= 0 else 1
        parent_result = _ascend_parent_steps(
            runtime_tree,
            current,
            steps=max(parent_steps + extra_parent_step + effective_parent_step_adjustment, 0),
            path_text=path_text,
            program_name=program_name,
            declaring_module_path=declaring_module_path,
        )
        if isinstance(parent_result, PictureDisplayPathResolution):
            return parent_result
        current = parent_result

    if raw_path.startswith("0"):
        current = runtime_tree.root
        raw_path = raw_path[1:]

    if not raw_path:
        return PictureDisplayPathResolution(
            path_text=path_text,
            program_name=program_name,
            declaring_module_path=declaring_module_path,
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
                declaring_module_path=declaring_module_path,
            )
            if isinstance(implicit_result, PictureDisplayPathResolution):
                return implicit_result
            current = implicit_result
            continue

        if raw_path.startswith("*"):
            token, raw_path = consume_name(raw_path[1:])
            match = find_nearest_descendant(current, token)
            if match is None:
                return PictureDisplayPathResolution(
                    path_text=path_text,
                    program_name=program_name,
                    declaring_module_path=declaring_module_path,
                    resolved_module_path=None,
                    failure_reason="wildcard_miss",
                    detail=f"wildcard '*{token}' found no descendant under {'.'.join(current.path)!r}",
                )
            current = match
            continue

        token, raw_path = consume_name(raw_path)
        matches = [child for child in current.children if child.name.casefold() == token.casefold()]
        if not matches:
            return PictureDisplayPathResolution(
                path_text=path_text,
                program_name=program_name,
                declaring_module_path=declaring_module_path,
                resolved_module_path=None,
                failure_reason="missing_named_child",
                detail=f"module {token!r} was not found under {'.'.join(current.path)!r}",
            )
        if len(matches) > 1:
            return PictureDisplayPathResolution(
                path_text=path_text,
                program_name=program_name,
                declaring_module_path=declaring_module_path,
                resolved_module_path=None,
                failure_reason="ambiguous_named_child",
                detail=f"module {token!r} is ambiguous under {'.'.join(current.path)!r}",
            )
        current = matches[0]

    return PictureDisplayPathResolution(
        path_text=path_text,
        program_name=program_name,
        declaring_module_path=declaring_module_path,
        resolved_module_path=current.path,
    )


def _descend_implicit_steps(
    current: RuntimeModuleNode,
    *,
    steps: int,
    path_text: str,
    program_name: str,
    declaring_module_path: tuple[str, ...],
) -> RuntimeModuleNode | PictureDisplayPathResolution:
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
    runtime_tree: RuntimeTree,
    current: RuntimeModuleNode,
    *,
    steps: int,
    path_text: str,
    program_name: str,
    declaring_module_path: tuple[str, ...],
) -> RuntimeModuleNode | PictureDisplayPathResolution:
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
        parent = find_parent_node(runtime_tree, current.path)
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


__all__ = [
    "PictureDisplayOccurrence",
    "PictureDisplayPathDiagnostic",
    "PictureDisplayPathResolution",
    "correlate_picture_display_records",
    "diagnose_picture_display_paths",
    "format_picture_display_path_diagnostic",
    "resolve_picture_display_path",
]
