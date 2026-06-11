"""SFC variable-access and step-contract collector classes."""

from __future__ import annotations

from collections.abc import Sequence as SequenceABC
from dataclasses import dataclass
from typing import Any

from sattline_parser.models.ast_model import (
    BasePicture,
    Sequence,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Variable,
)

from ...resolution import AccessKind
from ...resolution.paths import CanonicalPath, decorate_segment
from ..variables import ScopeContext, VariablesAnalyzer

__all__ = ["_SfcAccessCollector"]

type ParallelKey = tuple[tuple[str, ...], str, int]


@dataclass
class _ParallelMeta:
    module_path: list[str]
    sequence_name: str
    parallel_id: int


def iter_step_phase_statements(
    step: SFCStep,
) -> tuple[tuple[str, SequenceABC[object]], tuple[str, SequenceABC[object]], tuple[str, SequenceABC[object]]]:
    return (
        ("ENTER", step.code.enter or ()),
        ("ACTIVE", step.code.active or ()),
        ("EXIT", step.code.exit or ()),
    )


class _SfcAccessCollector(VariablesAnalyzer):
    def __init__(self, base_picture: BasePicture, debug: bool = False, **kwargs: Any):
        kwargs.setdefault("fail_loudly", False)
        super().__init__(base_picture, debug=debug, **kwargs)
        self.parallel_writes: dict[ParallelKey, dict[int, set[CanonicalPath]]] = {}
        self.parallel_meta: dict[ParallelKey, _ParallelMeta] = {}
        self._parallel_counter = 0
        self._parallel_stack: list[tuple[ParallelKey, int]] = []
        self._current_seq_name = "<unnamed>"

    def _record_access(
        self,
        kind: AccessKind,
        canonical_path: CanonicalPath,
        context: ScopeContext,
        syntactic_ref: str,
    ) -> None:
        super()._record_access(kind, canonical_path, context, syntactic_ref)
        if kind is not AccessKind.WRITE:
            return
        for parallel_key, branch_index in self._parallel_stack:
            branch_writes = self.parallel_writes.setdefault(parallel_key, {})
            branch_writes.setdefault(branch_index, set()).add(canonical_path)

    def _mark_ref_access(
        self,
        full_ref: str,
        context: ScopeContext,
        path: list[str],
        kind: AccessKind,
        *,
        is_ui_read: bool = False,
    ) -> None:
        var, field_path, decl_module_path, _decl_display = context.resolve_variable(full_ref)
        if var is None:
            return

        self.usage_tracker.mark_ref_access(
            variable=var,
            field_path=field_path,
            decl_module_path=decl_module_path,
            context=context,
            path=path,
            kind=kind,
            syntactic_ref=full_ref,
            ui_read=is_ui_read,
        )

        if kind is not AccessKind.WRITE:
            return

        segments = [*list(decl_module_path), var.name]
        if field_path:
            segments.extend(part for part in field_path.split(".") if part)
        canonical = CanonicalPath(tuple(segments))

        for parallel_key, branch_index in self._parallel_stack:
            branch_writes = self.parallel_writes.setdefault(parallel_key, {})
            branch_writes.setdefault(branch_index, set()).add(canonical)

    def _register_parallel_meta(
        self,
        key: ParallelKey,
        module_path: list[str],
        seq_name: str,
        parallel_id: int,
    ) -> None:
        if key not in self.parallel_meta:
            self.parallel_meta[key] = _ParallelMeta(
                module_path=module_path.copy(),
                sequence_name=seq_name,
                parallel_id=parallel_id,
            )

    def _walk_parallel_branches(
        self,
        branches: list[list[object]] | None,
        context: ScopeContext,
        path: list[str],
    ) -> None:
        self._parallel_counter += 1
        parallel_id = self._parallel_counter
        key: ParallelKey = (tuple(path), self._current_seq_name, parallel_id)
        self._register_parallel_meta(key, path, self._current_seq_name, parallel_id)

        for index, branch in enumerate(branches or []):
            self._push_site(f"PAR:BLOCK:{parallel_id}")
            self._push_site(f"PAR:BRANCH:{index}")
            self._parallel_stack.append((key, index))
            try:
                self._walk_seq_nodes(branch, context.env, path, context)
            finally:
                self._parallel_stack.pop()
                self._pop_site()
                self._pop_site()

    def _walk_sequence(self, sequence: Sequence, context: ScopeContext, path: list[str]) -> None:
        seq_name = getattr(sequence, "name", "<unnamed>")
        previous_name = self._current_seq_name
        self._current_seq_name = seq_name
        try:
            for node in sequence.code or []:
                self._walk_sequence_node(node, context, path, include_site_labels=True)
        finally:
            self._current_seq_name = previous_name

    def _walk_sequence_node(
        self,
        node: object,
        context: ScopeContext,
        path: list[str],
        *,
        include_site_labels: bool,
    ) -> None:
        if isinstance(node, SFCStep):
            self._walk_step_node(node, context, path, include_site_labels=include_site_labels)
            return

        if isinstance(node, SFCTransition):
            self._walk_transition_node(node, context, path, include_site_labels=include_site_labels)
            return

        if isinstance(node, SFCAlternative):
            for index, branch in enumerate(node.branches or []):
                self._walk_branch_node(
                    branch,
                    context,
                    path,
                    label=f"ALT:BRANCH:{index}" if include_site_labels else None,
                )
            return

        if isinstance(node, SFCParallel):
            self._walk_parallel_branches(node.branches, context, path)
            return

        if isinstance(node, SFCSubsequence):
            self._walk_branch_node(
                node.body,
                context,
                path,
                label=f"SUBSEQ:{getattr(node, 'name', '<unnamed>')}" if include_site_labels else None,
            )
            return

        if isinstance(node, SFCTransitionSub):
            self._walk_branch_node(
                node.body,
                context,
                path,
                label=f"TRANS-SUB:{getattr(node, 'name', '<unnamed>')}" if include_site_labels else None,
            )

    def _walk_step_node(
        self,
        step: SFCStep,
        context: ScopeContext,
        path: list[str],
        *,
        include_site_labels: bool,
    ) -> None:
        base = f"STEP:{step.name}"
        for phase, statements in iter_step_phase_statements(step):
            if include_site_labels:
                self._push_site(f"{base}:{phase}")
            try:
                for statement in statements:
                    self._walk_stmt_or_expr(statement, context, path)
            finally:
                if include_site_labels:
                    self._pop_site()

    def _walk_transition_node(
        self,
        transition: SFCTransition,
        context: ScopeContext,
        path: list[str],
        *,
        include_site_labels: bool,
    ) -> None:
        if include_site_labels:
            self._push_site(f"TRANS:{transition.name or '<unnamed>'}")
        try:
            self._walk_stmt_or_expr(transition.condition, context, path)
        finally:
            if include_site_labels:
                self._pop_site()

    def _walk_branch_node(
        self,
        nodes: list[object] | None,
        context: ScopeContext,
        path: list[str],
        *,
        label: str | None,
    ) -> None:
        if label is not None:
            self._push_site(label)
        try:
            self._walk_seq_nodes(nodes or [], context.env, path, context)
        finally:
            if label is not None:
                self._pop_site()

    def _walk_seq_nodes(
        self,
        nodes: list[object],
        env: dict[str, Variable],
        path: list[str],
        context: ScopeContext,
    ) -> None:
        del context
        display_path: list[str] = []
        if path:
            display_path.append(decorate_segment(path[0], "BP"))
            display_path.extend(path[1:])
        context = ScopeContext(
            env=env,
            param_mappings={},
            module_path=path.copy(),
            display_module_path=display_path,
            parent_context=None,
        )

        for node in nodes:
            self._walk_sequence_node(node, context, path, include_site_labels=False)
