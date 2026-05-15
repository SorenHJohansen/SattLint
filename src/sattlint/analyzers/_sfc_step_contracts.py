"""SFC step-contract data and collector helpers."""

from __future__ import annotations

from collections.abc import Sequence as SequenceABC
from dataclasses import dataclass
from typing import Any

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleCode,
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
from ..resolution.paths import CanonicalPath
from ._sfc_collectors import iter_step_phase_statements
from .framework import Issue
from .variables import ScopeContext, VariablesAnalyzer


@dataclass(frozen=True)
class StepContract:
    required_enter_writes: tuple[str, ...] = ()
    required_exit_writes: tuple[str, ...] = ()


class _SfcStepContractCollector(VariablesAnalyzer):
    def __init__(
        self, base_picture: BasePicture, step_contracts: dict[str, StepContract], debug: bool = False, **kwargs: Any
    ):
        kwargs.setdefault("fail_loudly", False)
        super().__init__(base_picture, debug=debug, **kwargs)
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
        for phase, statements in iter_step_phase_statements(step):
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
                child_context = self.context_builder.build_for_single(
                    module_obj,
                    parent_context,
                    module_path=child_path,
                    display_module_path=child_display_path,
                )
                self._walk_modulecode_contracts(
                    module_obj.modulecode,
                    child_context,
                    child_path,
                )
                self._walk_submodule_contracts(
                    module_obj.submodules or [],
                    child_context,
                    child_path,
                )
                continue

            if hasattr(module_obj, "submodules"):
                frame_context = self._repath_context(
                    parent_context,
                    module_path=child_path,
                    display_module_path=child_display_path,
                )
                self._walk_modulecode_contracts(
                    getattr(module_obj, "modulecode", None),
                    frame_context,
                    child_path,
                )
                self._walk_submodule_contracts(
                    module_obj.submodules or [],
                    frame_context,
                    child_path,
                )

    def _walk_typedef_contracts(self, root_context: ScopeContext) -> None:
        for moduletype in self.bp.moduletype_defs or []:
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


__all__ = ["StepContract", "_SfcStepContractCollector"]
