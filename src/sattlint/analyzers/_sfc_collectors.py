"""SFC variable-access and step-contract collector classes."""

# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence as SequenceABC
from dataclasses import dataclass
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleCode,
    ModuleTypeDef,
    Sequence,
    SFCAlternative,
    SFCBreak,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Variable,
)

from ..resolution import AccessKind
from ..resolution.paths import CanonicalPath, decorate_segment
from .framework import Issue
from .variables import ScopeContext, VariablesAnalyzer

type ParallelKey = tuple[tuple[str, ...], str, int]


@dataclass
class _ParallelMeta:
    module_path: list[str]
    sequence_name: str
    parallel_id: int


@dataclass(frozen=True)
class StepContract:
    required_enter_writes: tuple[str, ...] = ()
    required_exit_writes: tuple[str, ...] = ()


def _iter_step_phase_statements(
    step: SFCStep,
) -> tuple[tuple[str, SequenceABC[object]], tuple[str, SequenceABC[object]], tuple[str, SequenceABC[object]]]:
    return (
        ("ENTER", step.code.enter or ()),
        ("ACTIVE", step.code.active or ()),
        ("EXIT", step.code.exit or ()),
    )


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
                self._walk_seq_nodes(branch, context.env, path)
            finally:
                self._parallel_stack.pop()
                self._pop_site()
                self._pop_site()

    def _walk_sequence(self, seq: Sequence, context: ScopeContext, path: list[str]) -> None:
        seq_name = getattr(seq, "name", "<unnamed>")
        previous_name = self._current_seq_name
        self._current_seq_name = seq_name
        try:
            for node in seq.code or []:
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
        for phase, statements in _iter_step_phase_statements(step):
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
            self._walk_seq_nodes(nodes or [], context.env, path)
        finally:
            if label is not None:
                self._pop_site()

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

        for node in nodes:
            self._walk_sequence_node(node, context, path, include_site_labels=False)


class _SfcStepContractCollector(VariablesAnalyzer):
    def __init__(
        self,
        base_picture: BasePicture,
        step_contracts: dict[str, StepContract],
        debug: bool = False,
    ):
        super().__init__(base_picture, debug=debug, fail_loudly=False)
        self._step_contracts = step_contracts
        self.contract_issues: list[Issue] = []
        self._captured_reads: set[CanonicalPath] | None = None
        self._captured_writes: set[CanonicalPath] | None = None

    def _mark_ref_access(
        self,
        full_ref: str,
        context: ScopeContext,
        path: list[str],
        kind: AccessKind,
        *,
        is_ui_read: bool = False,
    ) -> None:
        variable, field_path, decl_module_path, _decl_display = context.resolve_variable(full_ref)
        if variable is None:
            return

        canonical_path = self._canonical_path(
            decl_module_path,
            variable,
            field_path or None,
        )

        if kind is AccessKind.READ and self._captured_reads is not None:
            self._captured_reads.add(canonical_path)
        if kind is AccessKind.WRITE and self._captured_writes is not None:
            self._captured_writes.add(canonical_path)

        super()._mark_ref_access(
            full_ref,
            context,
            path,
            kind,
            is_ui_read=is_ui_read,
        )

    def collect(self) -> list[Issue]:
        root_context = self.context_builder.build_for_basepicture()
        root_path = [self.bp.header.name]
        self._walk_modulecode_contracts(self.bp.modulecode, root_context, root_path)
        self._walk_submodule_contracts(self.bp.submodules or [], root_context, root_path)
        self._walk_typedef_contracts(root_context)
        return self.contract_issues

    def _capture_block_accesses(
        self,
        statements: SequenceABC[object] | None,
        context: ScopeContext,
        path: list[str],
    ) -> tuple[set[CanonicalPath], set[CanonicalPath]]:
        previous_reads = self._captured_reads
        previous_writes = self._captured_writes
        self._captured_reads = set()
        self._captured_writes = set()
        try:
            for statement in statements or []:
                self._walk_stmt_or_expr(statement, context, path)
            return set(self._captured_reads), set(self._captured_writes)
        finally:
            self._captured_reads = previous_reads
            self._captured_writes = previous_writes

    def _resolve_contract_refs(
        self,
        refs: tuple[str, ...],
        context: ScopeContext,
    ) -> dict[CanonicalPath, str]:
        resolved: dict[CanonicalPath, str] = {}
        for ref in refs:
            variable, field_path, decl_module_path, _decl_display = context.resolve_variable(ref)
            if variable is None:
                continue
            canonical_path = self._canonical_path(
                decl_module_path,
                variable,
                field_path or None,
            )
            resolved.setdefault(canonical_path, ref)
        return resolved

    def _walk_modulecode_contracts(
        self,
        modulecode: ModuleCode | None,
        context: ScopeContext,
        module_path: list[str],
    ) -> None:
        if modulecode is None:
            return
        for sequence in modulecode.sequences or []:
            if isinstance(sequence, Sequence):
                self._walk_sequence_contracts(sequence, context, module_path)

    def _walk_sequence_contracts(
        self,
        sequence: Sequence,
        context: ScopeContext,
        module_path: list[str],
    ) -> None:
        self._walk_sequence_nodes(
            sequence.code or [],
            context,
            module_path,
            state=set(),
            sequence_name=sequence.name,
        )

    def _walk_sequence_nodes(
        self,
        nodes: SequenceABC[object],
        context: ScopeContext,
        module_path: list[str],
        state: set[CanonicalPath],
        *,
        sequence_name: str,
    ) -> set[CanonicalPath]:
        current_state = set(state)
        terminated = False

        for node in nodes:
            if terminated:
                continue

            if isinstance(node, SFCStep):
                current_state = self._walk_step_contracts(
                    node,
                    context,
                    module_path,
                    current_state,
                    sequence_name=sequence_name,
                )
                continue

            if isinstance(node, SFCTransition):
                continue

            if isinstance(node, SFCAlternative):
                branch_states = [
                    self._walk_sequence_nodes(
                        branch or [],
                        context,
                        module_path,
                        set(current_state),
                        sequence_name=sequence_name,
                    )
                    for branch in (node.branches or [])
                ]
                current_state = self._merge_contract_states(branch_states, current_state)
                continue

            if isinstance(node, SFCParallel):
                branch_states = [
                    self._walk_sequence_nodes(
                        branch or [],
                        context,
                        module_path,
                        set(current_state),
                        sequence_name=sequence_name,
                    )
                    for branch in (node.branches or [])
                ]
                current_state = self._merge_contract_states(branch_states, current_state)
                continue

            if isinstance(node, SFCSubsequence):
                current_state = self._walk_sequence_nodes(
                    node.body or [],
                    context,
                    module_path,
                    current_state,
                    sequence_name=sequence_name,
                )
                continue

            if isinstance(node, SFCTransitionSub):
                current_state = self._walk_sequence_nodes(
                    node.body or [],
                    context,
                    module_path,
                    current_state,
                    sequence_name=sequence_name,
                )
                continue

            if isinstance(node, SFCBreak | SFCFork):
                terminated = True

        return current_state

    def _merge_contract_states(
        self,
        branch_states: list[set[CanonicalPath]],
        fallback: set[CanonicalPath],
    ) -> set[CanonicalPath]:
        merged = set(fallback)
        for branch_state in branch_states:
            merged.update(branch_state)
        return merged

    def _walk_step_contracts(
        self,
        step: SFCStep,
        context: ScopeContext,
        module_path: list[str],
        incoming_state: set[CanonicalPath],
        *,
        sequence_name: str,
    ) -> set[CanonicalPath]:
        contract = self._step_contracts.get(step.name.casefold())

        base = f"STEP:{step.name}"
        phase_writes: dict[str, set[CanonicalPath]] = {
            "ENTER": set(),
            "ACTIVE": set(),
            "EXIT": set(),
        }
        for phase, statements in _iter_step_phase_statements(step):
            self._push_site(f"{base}:{phase}")
            try:
                _reads, writes = self._capture_block_accesses(
                    statements,
                    context,
                    module_path,
                )
            finally:
                self._pop_site()
            phase_writes[phase] = writes

        enter_writes = phase_writes["ENTER"]
        active_writes = phase_writes["ACTIVE"]
        exit_writes = phase_writes["EXIT"]

        next_state = set(incoming_state)
        next_state.update(enter_writes)
        next_state.update(active_writes)
        next_state.update(exit_writes)

        if contract is None:
            return next_state

        required_enter = self._resolve_contract_refs(
            contract.required_enter_writes,
            context,
        )
        required_exit = self._resolve_contract_refs(
            contract.required_exit_writes,
            context,
        )

        missing_enter = [label for path, label in required_enter.items() if path not in enter_writes]
        if missing_enter:
            self.contract_issues.append(
                Issue(
                    kind="sfc_missing_step_enter_contract",
                    message=(
                        f"Step {step.name!r} in sequence {sequence_name!r} is missing required enter writes: "
                        + ", ".join(missing_enter)
                    ),
                    module_path=module_path.copy(),
                    data={
                        "sequence": sequence_name,
                        "step": step.name,
                        "missing_enter_writes": missing_enter,
                    },
                )
            )

        leaked_state = [
            label for path, label in required_enter.items() if path in incoming_state and path not in enter_writes
        ]
        if leaked_state:
            self.contract_issues.append(
                Issue(
                    kind="sfc_step_state_leakage",
                    message=(
                        f"Step {step.name!r} in sequence {sequence_name!r} can inherit stale state from earlier steps because "
                        f"its required enter writes are missing for: {', '.join(leaked_state)}"
                    ),
                    module_path=module_path.copy(),
                    data={
                        "sequence": sequence_name,
                        "step": step.name,
                        "leaked_state": leaked_state,
                    },
                )
            )

        missing_exit = [label for path, label in required_exit.items() if path not in exit_writes]
        if missing_exit:
            self.contract_issues.append(
                Issue(
                    kind="sfc_missing_step_exit_contract",
                    message=(
                        f"Step {step.name!r} in sequence {sequence_name!r} is missing required exit writes: "
                        + ", ".join(missing_exit)
                    ),
                    module_path=module_path.copy(),
                    data={
                        "sequence": sequence_name,
                        "step": step.name,
                        "missing_exit_writes": missing_exit,
                    },
                )
            )

        for path in required_exit:
            if path in exit_writes:
                next_state.discard(path)

        return next_state

    def _walk_submodule_contracts(
        self,
        modules: SequenceABC[Any] | None,
        parent_context: ScopeContext,
        parent_path: list[str],
    ) -> None:
        for module in modules or []:
            module_obj: Any = module
            header = getattr(module_obj, "header", None)
            child_name = getattr(header, "name", None)
            if not isinstance(child_name, str):
                continue

            child_path = [*parent_path, child_name]
            child_display_path = [*parent_context.display_module_path, child_name]

            if hasattr(module_obj, "moduleparameters") and hasattr(module_obj, "localvariables"):
                single_module = cast(Any, module_obj)
                child_context = self.context_builder.build_for_single(
                    single_module,
                    parent_context,
                    module_path=child_path,
                    display_module_path=child_display_path,
                )
                self._walk_modulecode_contracts(
                    single_module.modulecode,
                    child_context,
                    child_path,
                )
                self._walk_submodule_contracts(
                    single_module.submodules or [],
                    child_context,
                    child_path,
                )
                continue

            if hasattr(module_obj, "submodules"):
                frame_module = cast(Any, module_obj)
                frame_context = self._repath_context(
                    parent_context,
                    module_path=child_path,
                    display_module_path=child_display_path,
                )
                self._walk_modulecode_contracts(
                    getattr(frame_module, "modulecode", None),
                    frame_context,
                    child_path,
                )
                self._walk_submodule_contracts(
                    frame_module.submodules or [],
                    frame_context,
                    child_path,
                )

    def _walk_typedef_contracts(self, root_context: ScopeContext) -> None:
        for moduletype in self.bp.moduletype_defs or []:
            if not isinstance(moduletype, ModuleTypeDef):
                continue

            module_path = [self.bp.header.name, f"TypeDef:{moduletype.name}"]
            display_path = [*root_context.display_module_path, f"TypeDef:{moduletype.name}"]
            env: dict[str, Variable] = {}
            for variable in moduletype.moduleparameters or []:
                env[variable.name.casefold()] = variable
            for variable in moduletype.localvariables or []:
                env[variable.name.casefold()] = variable

            typedef_context = ScopeContext(
                env=env,
                param_mappings={},
                module_path=module_path,
                display_module_path=display_path,
                current_library=root_context.current_library,
                parent_context=root_context,
            )
            self._walk_modulecode_contracts(
                moduletype.modulecode,
                typedef_context,
                module_path,
            )
