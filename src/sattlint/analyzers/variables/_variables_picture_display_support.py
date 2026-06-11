"""PictureDisplay context helpers for variable analysis."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    GraphicsBinding,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)

from ..._picture_display_path_runtime import CompositeRecordOccurrence, correlate_composite_records
from ...graphics_validation import GraphicsCompositeRecord
from ...picture_display_paths import PictureDisplayOccurrence
from ...resolution import AccessKind, decorate_segment
from ...resolution.common import resolve_moduletype_def_strict
from ...resolution.scope import ScopeContext

if TYPE_CHECKING:
    from . import VariablesAnalyzer


_GRAPHICS_EXPR_FALLBACK_IDENTIFIER_RE = re.compile(r"(?<![\w.])([^\W\d]\w*(?:\.[^\W\d]\w*)*)(?![\w.])", re.UNICODE)
_GRAPHICS_EXPR_FALLBACK_IGNORED = {"and", "or", "not", "if", "then", "else", "elsif", "endif", "true", "false"}


def build_typedef_root_context(
    self: VariablesAnalyzer,
    moduletype: ModuleTypeDef,
    path: list[str],
) -> ScopeContext:
    display_path = [decorate_segment(path[0], "BP"), decorate_segment(path[1], "TD")]
    env = {variable.name.lower(): variable for variable in moduletype.moduleparameters or []}
    env.update({variable.name.lower(): variable for variable in moduletype.localvariables or []})
    context = ScopeContext(
        env=env,
        param_mappings={},
        module_path=path.copy(),
        display_module_path=display_path,
        moduleparameter_keys=frozenset(variable.name.casefold() for variable in (moduletype.moduleparameters or [])),
        current_library=moduletype.origin_lib,
        parent_context=None,
    )
    self._contexts_by_module_path[tuple(path)] = context
    return context


def _resolve_root_owned_typedef(self: VariablesAnalyzer, typedef_name: str) -> ModuleTypeDef | None:
    return next(
        (
            candidate
            for candidate in self.bp.moduletype_defs or []
            if candidate.name.casefold() == typedef_name.casefold()
            and self._is_from_root_origin(
                getattr(candidate, "origin_file", None),
                getattr(candidate, "origin_lib", None),
            )
        ),
        None,
    )


def _build_child_picture_display_context(
    self: VariablesAnalyzer,
    current_context: ScopeContext,
    child: SingleModule | FrameModule | ModuleTypeInstance,
    child_path: list[str],
) -> tuple[ScopeContext, ModuleTypeDef | SingleModule | FrameModule]:
    if isinstance(child, SingleModule):
        child_display_path = [*current_context.display_module_path, decorate_segment(child.header.name, "SM")]
        diverted_context_issues = self.context_builder.issues
        self.context_builder.issues = []
        try:
            child_context = self.context_builder.build_for_single(
                child,
                current_context,
                module_path=child_path,
                display_module_path=child_display_path,
            )
        finally:
            self.context_builder.issues = diverted_context_issues
        return child_context, child

    if isinstance(child, FrameModule):
        child_display_path = [*current_context.display_module_path, decorate_segment(child.header.name, "FM")]
        child_context = self.repath_context(
            current_context,
            module_path=child_path,
            display_module_path=child_display_path,
        )
        return child_context, child

    child_display_path = [
        *current_context.display_module_path,
        decorate_segment(child.header.name, "MT", moduletype_name=child.moduletype_name),
    ]
    diverted_context_issues = self.context_builder.issues
    self.context_builder.issues = []
    try:
        resolved_moduletype = resolve_moduletype_def_strict(
            self.bp,
            child.moduletype_name,
            current_library=current_context.current_library,
            unavailable_libraries=self.unavailable_libraries,
        )
        child_context = self.context_builder.build_for_typedef(
            resolved_moduletype,
            child,
            current_context,
            module_path=child_path,
            display_module_path=child_display_path,
        )
    finally:
        self.context_builder.issues = diverted_context_issues
    return child_context, resolved_moduletype


def seed_picture_display_context(self: VariablesAnalyzer, module_path: list[str]) -> ScopeContext | None:
    context = self.contexts_by_module_path.get(tuple(module_path))
    if context is None:
        context = _seed_runtime_picture_display_context(self, module_path)
    typedef_module_path = module_path.copy()
    if context is None and len(module_path) >= 2 and not module_path[1].startswith("TypeDef:"):
        typedef_module_path = [module_path[0], f"TypeDef:{module_path[1]}", *module_path[2:]]
        context = self.contexts_by_module_path.get(tuple(typedef_module_path))
    if context is not None:
        return context

    if len(typedef_module_path) < 2 or not typedef_module_path[1].startswith("TypeDef:"):
        return None

    moduletype = _resolve_root_owned_typedef(self, typedef_module_path[1].removeprefix("TypeDef:"))
    if moduletype is None:
        return None

    current_path = [typedef_module_path[0], typedef_module_path[1]]
    current_context = self.contexts_by_module_path.get(tuple(current_path))
    if current_context is None:
        current_context = build_typedef_root_context(self, moduletype, current_path)

    current_node: ModuleTypeDef | SingleModule | FrameModule = moduletype
    for segment in typedef_module_path[2:]:
        child = next(
            (nested for nested in current_node.submodules or [] if nested.header.name.casefold() == segment.casefold()),
            None,
        )
        if child is None:
            return None

        child_path = [*current_path, child.header.name]
        child_context = self.contexts_by_module_path.get(tuple(child_path))
        if child_context is None:
            child_context, current_node = _build_child_picture_display_context(
                self,
                current_context,
                child,
                child_path,
            )
            self._contexts_by_module_path[tuple(child_path)] = child_context
        else:
            if isinstance(child, ModuleTypeInstance):
                current_node = resolve_moduletype_def_strict(
                    self.bp,
                    child.moduletype_name,
                    current_library=current_context.current_library,
                    unavailable_libraries=self.unavailable_libraries,
                )
            else:
                current_node = child

        current_context = child_context
        current_path = child_path

    return current_context


def _seed_runtime_picture_display_context(self: VariablesAnalyzer, module_path: list[str]) -> ScopeContext | None:
    if not module_path or module_path[0].casefold() != self.bp.header.name.casefold():
        return None

    root_path = [self.bp.header.name]
    current_context = self.contexts_by_module_path.get(tuple(root_path))
    if current_context is None:
        current_context = self.context_builder.build_for_basepicture()
        self._contexts_by_module_path[tuple(root_path)] = current_context

    current_node: BasePicture | ModuleTypeDef | SingleModule | FrameModule = self.bp
    current_path = root_path

    for segment in module_path[1:]:
        child = next(
            (nested for nested in current_node.submodules or [] if nested.header.name.casefold() == segment.casefold()),
            None,
        )
        if child is None:
            return None

        child_path = [*current_path, child.header.name]
        child_context = self.contexts_by_module_path.get(tuple(child_path))
        if child_context is None:
            child_context, next_node = _build_child_picture_display_context(
                self,
                current_context,
                child,
                child_path,
            )
            self._contexts_by_module_path[tuple(child_path)] = child_context
        else:
            if isinstance(child, ModuleTypeInstance):
                next_node = resolve_moduletype_def_strict(
                    self.bp,
                    child.moduletype_name,
                    current_library=current_context.current_library,
                    unavailable_libraries=self.unavailable_libraries,
                )
            else:
                next_node = child

        current_context = child_context
        current_node = next_node
        current_path = child_path

    return current_context


def record_picture_display_variable_occurrences(self: VariablesAnalyzer) -> None:
    occurrences = cast(
        tuple[PictureDisplayOccurrence, ...],
        tuple(getattr(self.bp, "graphics_picture_display_occurrences", ()) or ()),
    )
    if not occurrences:
        return

    marked_count = 0
    for occurrence in occurrences:
        module_path = [str(segment) for segment in occurrence.declaring_module_path]
        context = seed_picture_display_context(self, module_path)
        if context is None:
            continue
        path_row_lines: set[int] = set(
            cast(tuple[int, ...], tuple(getattr(occurrence.record, "path_row_lines", ()) or ()))
        )

        for binding in cast(tuple[GraphicsBinding, ...], tuple(getattr(self.bp, "graphics_bindings", ()) or ())):
            span = binding.span
            if span is None:
                continue
            if not (occurrence.record.record_start_line <= span.line <= occurrence.record.record_end_line):
                continue
            if span.line in path_row_lines:
                continue
            marked_count += _mark_graphics_binding_in_context(self, binding, context, module_path)

        for row in getattr(occurrence.record, "path_rows", ()) or ():
            if row.index_value is None and row.index_token and row.index_token.casefold() != "none":
                self._mark_ref_access(
                    row.index_token,
                    context,
                    module_path,
                    AccessKind.READ,
                    is_ui_read=True,
                )
                marked_count += 1
            if row.kind != "variable":
                continue
            self._mark_ref_access(
                row.raw_text,
                context,
                module_path,
                AccessKind.READ,
                is_ui_read=True,
            )
            marked_count += 1

    self._trace(
        "graphics-picture-display-variable-paths",
        occurrence_count=len(occurrences),
        marked_count=marked_count,
    )


def _mark_graphics_expr_fallback_reads(
    self: VariablesAnalyzer,
    expr_text: str,
    context: ScopeContext,
    module_path: list[str],
) -> int:
    marked_count = 0
    seen_candidates: set[str] = set()
    for match in _GRAPHICS_EXPR_FALLBACK_IDENTIFIER_RE.finditer(expr_text):
        candidate = match.group(1)
        if not candidate:
            continue
        if candidate.casefold() in _GRAPHICS_EXPR_FALLBACK_IGNORED:
            continue
        trailing = expr_text[match.end() :].lstrip()
        if trailing.startswith("("):
            continue
        candidate_key = candidate.casefold()
        if candidate_key in seen_candidates:
            continue
        seen_candidates.add(candidate_key)
        self._mark_ref_access(
            candidate,
            context,
            module_path,
            AccessKind.READ,
            is_ui_read=True,
        )
        marked_count += 1
    return marked_count


def _mark_graphics_binding_in_context(
    self: VariablesAnalyzer,
    binding: object,
    context: ScopeContext,
    module_path: list[str],
) -> int:
    kind = getattr(binding, "kind", None)
    if kind not in {"var", "expr"}:
        return 0
    value = getattr(binding, "value", None)
    if kind == "expr" and isinstance(value, str):
        return _mark_graphics_expr_fallback_reads(self, value, context, module_path)
    self._walk_stmt_or_expr(value, context, module_path, is_ui_read=True)
    return 1


def record_graphics_binding_occurrences(self: VariablesAnalyzer) -> None:
    graphics_bindings = cast(
        tuple[GraphicsBinding, ...],
        tuple(getattr(self.bp, "graphics_bindings", ()) or ()),
    )
    if not graphics_bindings:
        return

    root_path = [self.bp.header.name]
    root_context = self.contexts_by_module_path.get(tuple(root_path))
    if root_context is None:
        root_context = self.context_builder.build_for_basepicture()
        self._contexts_by_module_path[tuple(root_path)] = root_context

    occurrences = cast(
        tuple[CompositeRecordOccurrence, ...],
        tuple(getattr(self.bp, "graphics_composite_occurrences", ()) or ()),
    )
    if not occurrences:
        composite_records = cast(
            tuple[GraphicsCompositeRecord, ...],
            tuple(getattr(self.bp, "graphics_composite_records", ()) or ()),
        )
        if composite_records:
            occurrences = correlate_composite_records(self.bp, composite_records)

    matched_binding_ids: set[int] = set()
    marked_count = 0
    for occurrence in occurrences:
        module_path = [str(segment) for segment in occurrence.declaring_module_path]
        context = seed_picture_display_context(self, module_path)
        if context is None:
            continue
        for binding in graphics_bindings:
            span = getattr(binding, "span", None)
            if span is None:
                continue
            if not (occurrence.record_start_line <= span.line <= occurrence.record_end_line):
                continue
            binding_id = id(binding)
            if binding_id in matched_binding_ids:
                continue
            marked_count += _mark_graphics_binding_in_context(self, binding, context, module_path)
            matched_binding_ids.add(binding_id)

    for binding in graphics_bindings:
        binding_id = id(binding)
        if binding_id in matched_binding_ids:
            continue
        marked_count += _mark_graphics_binding_in_context(self, binding, root_context, root_path)

    self._trace(
        "graphics-binding-occurrences",
        occurrence_count=len(occurrences),
        binding_count=len(graphics_bindings),
        marked_count=marked_count,
    )
