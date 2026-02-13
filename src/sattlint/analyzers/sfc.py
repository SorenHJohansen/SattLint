"""SFC analysis for parallel-branch write races."""
from __future__ import annotations

from dataclasses import dataclass

from .framework import Issue, SimpleReport
from .variables import ScopeContext, VariablesAnalyzer
from ..models.ast_model import (
    BasePicture,
    SFCAlternative,
    SFCBreak,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Sequence,
    Variable,
)
from ..resolution import AccessKind
from ..resolution.paths import CanonicalPath, decorate_segment


ParallelKey = tuple[tuple[str, ...], str, int]


@dataclass
class _ParallelMeta:
    module_path: list[str]
    sequence_name: str
    parallel_id: int


class _SfcAccessCollector(VariablesAnalyzer):
    def __init__(self, base_picture: BasePicture, debug: bool = False):
        super().__init__(base_picture, debug=debug, fail_loudly=False)
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
        )

        if kind is not AccessKind.WRITE:
            return

        segs = list(decl_module_path) + [var.name]
        if field_path:
            segs.extend([p for p in field_path.split(".") if p])
        canonical = CanonicalPath(tuple(segs))

        for parallel_key, branch_index in self._parallel_stack:
            branch_writes = self.parallel_writes.setdefault(parallel_key, {})
            branch_writes.setdefault(branch_index, set()).add(canonical)

    def _register_parallel_meta(
        self, key: ParallelKey, module_path: list[str], seq_name: str, parallel_id: int
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

        for i, branch in enumerate(branches or []):
            self._push_site(f"PAR:BLOCK:{parallel_id}")
            self._push_site(f"PAR:BRANCH:{i}")
            self._parallel_stack.append((key, i))
            try:
                self._walk_seq_nodes(branch, context.env, path)
            finally:
                self._parallel_stack.pop()
                self._pop_site()
                self._pop_site()

    def _walk_sequence(
        self, seq: Sequence, context: ScopeContext, path: list[str]
    ) -> None:
        seq_name = getattr(seq, "name", "<unnamed>")
        prev = self._current_seq_name
        self._current_seq_name = seq_name
        try:
            for node in seq.code or []:
                if isinstance(node, SFCStep):
                    base = f"STEP:{node.name}"
                    self._push_site(f"{base}:ENTER")
                    try:
                        for stmt in node.code.enter or []:
                            self._walk_stmt_or_expr(stmt, context, path)
                    finally:
                        self._pop_site()

                    self._push_site(f"{base}:ACTIVE")
                    try:
                        for stmt in node.code.active or []:
                            self._walk_stmt_or_expr(stmt, context, path)
                    finally:
                        self._pop_site()

                    self._push_site(f"{base}:EXIT")
                    try:
                        for stmt in node.code.exit or []:
                            self._walk_stmt_or_expr(stmt, context, path)
                    finally:
                        self._pop_site()

                elif isinstance(node, SFCTransition):
                    label = f"TRANS:{node.name or '<unnamed>'}"
                    self._push_site(label)
                    try:
                        self._walk_stmt_or_expr(node.condition, context, path)
                    finally:
                        self._pop_site()

                elif isinstance(node, SFCAlternative):
                    for i, branch in enumerate(node.branches or []):
                        self._push_site(f"ALT:BRANCH:{i}")
                        try:
                            self._walk_seq_nodes(branch, context.env, path)
                        finally:
                            self._pop_site()

                elif isinstance(node, SFCParallel):
                    self._walk_parallel_branches(node.branches, context, path)

                elif isinstance(node, SFCSubsequence):
                    self._push_site(f"SUBSEQ:{getattr(node, 'name', '<unnamed>')}")
                    try:
                        self._walk_seq_nodes(node.body, context.env, path)
                    finally:
                        self._pop_site()

                elif isinstance(node, SFCTransitionSub):
                    self._push_site(f"TRANS-SUB:{getattr(node, 'name', '<unnamed>')}")
                    try:
                        self._walk_seq_nodes(node.body, context.env, path)
                    finally:
                        self._pop_site()

                elif isinstance(node, (SFCFork, SFCBreak)):
                    continue
        finally:
            self._current_seq_name = prev

    def _walk_seq_nodes(
        self,
        nodes: list[object],
        env: dict[str, Variable],
        path: list[str],
    ) -> None:
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

        for nd in nodes:
            if isinstance(nd, SFCStep):
                for stmt in nd.code.enter or []:
                    self._walk_stmt_or_expr(stmt, context, path)
                for stmt in nd.code.active or []:
                    self._walk_stmt_or_expr(stmt, context, path)
                for stmt in nd.code.exit or []:
                    self._walk_stmt_or_expr(stmt, context, path)
            elif isinstance(nd, SFCTransition):
                self._walk_stmt_or_expr(nd.condition, context, path)
            elif isinstance(nd, SFCAlternative):
                for branch in nd.branches:
                    self._walk_seq_nodes(branch, env, path)
            elif isinstance(nd, SFCParallel):
                self._walk_parallel_branches(nd.branches, context, path)
            elif isinstance(nd, SFCSubsequence):
                self._walk_seq_nodes(nd.body, env, path)
            elif isinstance(nd, SFCTransitionSub):
                self._walk_seq_nodes(nd.body, env, path)


def _paths_conflict(a: CanonicalPath, b: CanonicalPath) -> bool:
    a_key = a.key()
    b_key = b.key()
    if len(a_key) <= len(b_key):
        return b_key[: len(a_key)] == a_key
    return a_key[: len(b_key)] == b_key


def _conflict_rep(a: CanonicalPath, b: CanonicalPath) -> CanonicalPath:
    if len(a.segments) <= len(b.segments):
        return a
    return b


def analyze_sfc(base_picture: BasePicture) -> SimpleReport:
    collector = _SfcAccessCollector(base_picture)
    collector.run()

    issues: list[Issue] = []
    for key, branch_writes in collector.parallel_writes.items():
        conflicts: dict[tuple[str, ...], CanonicalPath] = {}
        branch_ids = sorted(branch_writes.keys())
        for i, left in enumerate(branch_ids):
            for right in branch_ids[i + 1 :]:
                for a in branch_writes[left]:
                    for b in branch_writes[right]:
                        if _paths_conflict(a, b):
                            rep = _conflict_rep(a, b)
                            conflicts.setdefault(rep.key(), rep)

        if not conflicts:
            continue

        meta = collector.parallel_meta.get(key)
        seq_name = meta.sequence_name if meta else "<unnamed>"
        conflict_list = sorted((str(p) for p in conflicts.values()))
        preview = ", ".join(conflict_list[:6])
        if len(conflict_list) > 6:
            preview = f"{preview}, ... (+{len(conflict_list) - 6} more)"

        issues.append(
            Issue(
                kind="sfc_parallel_write_race",
                message=(
                    "Parallel branches in sequence "
                    f"{seq_name!r} write to the same variable(s): {preview}"
                ),
                module_path=meta.module_path if meta else None,
                data={
                    "sequence": seq_name,
                    "parallel_id": meta.parallel_id if meta else None,
                    "conflicts": conflict_list,
                },
            )
        )

    return SimpleReport(name=base_picture.header.name, issues=issues)
