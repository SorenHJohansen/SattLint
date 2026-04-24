"""SFC analysis for structural dead paths, write races, and state conflicts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from collections.abc import Sequence as SequenceABC
from dataclasses import dataclass
from itertools import product
from typing import Any, cast

from sattline_parser.utils.formatter import format_expr

from ..grammar import constants as const
from ..models.ast_model import (
    BasePicture,
    FrameModule,
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
    SingleModule,
    Variable,
)
from ..resolution import AccessKind
from ..resolution.paths import CanonicalPath, decorate_segment
from .framework import Issue, SimpleReport
from .variables import ScopeContext, VariablesAnalyzer

type ParallelKey = tuple[tuple[str, ...], str, int]
type StepSet = frozenset[str]
type ExclusiveStepGroup = tuple[str, ...]


@dataclass
class _ParallelMeta:
    module_path: list[str]
    sequence_name: str
    parallel_id: int


@dataclass(frozen=True)
class SfcReachabilityFinding:
    module_path: tuple[str, ...]
    sequence_name: str
    branch_path: tuple[int, ...]
    node_index: int
    node_label: str
    node_type: str
    terminated_by: dict[str, Any]


@dataclass(frozen=True)
class StepContract:
    required_enter_writes: tuple[str, ...] = ()
    required_exit_writes: tuple[str, ...] = ()


def _normalize_step_groups(
    step_groups: Iterable[Iterable[str]] | None,
) -> tuple[ExclusiveStepGroup, ...]:
    if step_groups is None:
        return ()

    groups: list[ExclusiveStepGroup] = []
    for group in step_groups:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in group:
            if not isinstance(item, str):
                continue
            name = item.strip()
            if not name:
                continue
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(name)
        if len(normalized) >= 2:
            groups.append(tuple(normalized))

    return tuple(groups)


def normalize_mutually_exclusive_step_sets(raw: object) -> tuple[ExclusiveStepGroup, ...]:
    if not isinstance(raw, list):
        return ()
    return _normalize_step_groups(group for group in raw if isinstance(group, list | tuple | set))


def get_configured_mutually_exclusive_step_sets(
    config: dict[str, Any] | None,
) -> tuple[ExclusiveStepGroup, ...]:
    if not isinstance(config, dict):
        return ()
    analysis = config.get("analysis", {})
    if not isinstance(analysis, dict):
        return ()
    sfc_config = analysis.get("sfc", {})
    if not isinstance(sfc_config, dict):
        return ()
    return normalize_mutually_exclusive_step_sets(sfc_config.get("mutually_exclusive_steps", []))


def _normalize_step_contract_refs(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return tuple(normalized)


def _normalize_step_contract(raw: object) -> StepContract:
    if not isinstance(raw, dict):
        return StepContract()

    return StepContract(
        required_enter_writes=_normalize_step_contract_refs(raw.get("required_enter_writes", [])),
        required_exit_writes=_normalize_step_contract_refs(raw.get("required_exit_writes", [])),
    )


def normalize_step_contracts(raw: object) -> dict[str, StepContract]:
    if not isinstance(raw, Mapping):
        return {}

    normalized: dict[str, StepContract] = {}
    for step_name, contract_raw in raw.items():
        if not isinstance(step_name, str):
            continue
        name = step_name.strip()
        if not name:
            continue
        contract = _normalize_step_contract(contract_raw)
        if not contract.required_enter_writes and not contract.required_exit_writes:
            continue
        normalized[name.casefold()] = contract
    return normalized


def get_configured_step_contracts(
    config: dict[str, Any] | None,
) -> dict[str, StepContract]:
    if not isinstance(config, dict):
        return {}
    analysis = config.get("analysis", {})
    if not isinstance(analysis, dict):
        return {}
    sfc_config = analysis.get("sfc", {})
    if not isinstance(sfc_config, dict):
        return {}
    return normalize_step_contracts(sfc_config.get("step_contracts", {}))


def _sequence_node_label(node: object) -> str:
    node_name = getattr(node, "name", None)
    if node_name:
        return f"{type(node).__name__}:{node_name}"
    if isinstance(node, SFCFork):
        return f"SFCFork:{node.target}"
    return type(node).__name__


def _inspect_sfc_linear_nodes(
    findings: list[SfcReachabilityFinding],
    nodes: SequenceABC[object] | None,
    module_path: list[str],
    sequence_name: str,
    branch_path: tuple[int, ...] = (),
) -> None:
    terminated_by: dict[str, Any] | None = None
    for index, node in enumerate(nodes or []):
        if terminated_by is not None:
            findings.append(
                SfcReachabilityFinding(
                    module_path=tuple(module_path),
                    sequence_name=sequence_name,
                    branch_path=branch_path,
                    node_index=index,
                    node_label=_sequence_node_label(node),
                    node_type=type(node).__name__,
                    terminated_by=dict(terminated_by),
                )
            )
            continue

        if isinstance(node, SFCBreak):
            terminated_by = {"kind": "SFCBreak"}
            continue

        if isinstance(node, SFCFork):
            terminated_by = {"kind": "SFCFork", "target": node.target}
            continue

        if isinstance(node, SFCAlternative | SFCParallel):
            for branch_index, branch in enumerate(node.branches or []):
                _inspect_sfc_linear_nodes(
                    findings,
                    branch,
                    module_path,
                    sequence_name,
                    (*branch_path, branch_index),
                )
            continue

        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            _inspect_sfc_linear_nodes(findings, node.body, module_path, sequence_name, branch_path)


def _inspect_sfc_modulecode(
    findings: list[SfcReachabilityFinding],
    modulecode: ModuleCode | None,
    module_path: list[str],
) -> None:
    if modulecode is None:
        return
    for sequence in modulecode.sequences or []:
        if isinstance(sequence, Sequence):
            _inspect_sfc_linear_nodes(findings, sequence.code, module_path, sequence.name)


def _walk_sfc_modules(
    findings: list[SfcReachabilityFinding],
    modules: SequenceABC[object] | None,
    module_path: list[str],
) -> None:
    for module in modules or []:
        if isinstance(module, SingleModule):
            child_path = [*module_path, module.header.name]
            _inspect_sfc_modulecode(findings, module.modulecode, child_path)
            _walk_sfc_modules(findings, module.submodules, child_path)
        elif isinstance(module, FrameModule):
            child_path = [*module_path, module.header.name]
            _inspect_sfc_modulecode(findings, getattr(module, "modulecode", None), child_path)
            _walk_sfc_modules(findings, module.submodules, child_path)


def collect_sfc_reachability_findings(
    base_picture: BasePicture,
) -> list[SfcReachabilityFinding]:
    findings: list[SfcReachabilityFinding] = []

    root_path = [base_picture.header.name]
    _inspect_sfc_modulecode(findings, base_picture.modulecode, root_path)
    _walk_sfc_modules(findings, base_picture.submodules, root_path)
    for moduletype in base_picture.moduletype_defs or []:
        if isinstance(moduletype, ModuleTypeDef):
            _inspect_sfc_modulecode(
                findings,
                moduletype.modulecode,
                [base_picture.header.name, f"TypeDef:{moduletype.name}"],
            )

    return findings


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
                    continue

                if isinstance(node, SFCTransition):
                    label = f"TRANS:{node.name or '<unnamed>'}"
                    self._push_site(label)
                    try:
                        self._walk_stmt_or_expr(node.condition, context, path)
                    finally:
                        self._pop_site()
                    continue

                if isinstance(node, SFCAlternative):
                    for index, branch in enumerate(node.branches or []):
                        self._push_site(f"ALT:BRANCH:{index}")
                        try:
                            self._walk_seq_nodes(branch, context.env, path)
                        finally:
                            self._pop_site()
                    continue

                if isinstance(node, SFCParallel):
                    self._walk_parallel_branches(node.branches, context, path)
                    continue

                if isinstance(node, SFCSubsequence):
                    self._push_site(f"SUBSEQ:{getattr(node, 'name', '<unnamed>')}")
                    try:
                        self._walk_seq_nodes(node.body, context.env, path)
                    finally:
                        self._pop_site()
                    continue

                if isinstance(node, SFCTransitionSub):
                    self._push_site(f"TRANS-SUB:{getattr(node, 'name', '<unnamed>')}")
                    try:
                        self._walk_seq_nodes(node.body, context.env, path)
                    finally:
                        self._pop_site()
        finally:
            self._current_seq_name = previous_name

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
            if isinstance(node, SFCStep):
                for stmt in node.code.enter or []:
                    self._walk_stmt_or_expr(stmt, context, path)
                for stmt in node.code.active or []:
                    self._walk_stmt_or_expr(stmt, context, path)
                for stmt in node.code.exit or []:
                    self._walk_stmt_or_expr(stmt, context, path)
            elif isinstance(node, SFCTransition):
                self._walk_stmt_or_expr(node.condition, context, path)
            elif isinstance(node, SFCAlternative):
                for branch in node.branches or []:
                    self._walk_seq_nodes(branch, env, path)
            elif isinstance(node, SFCParallel):
                self._walk_parallel_branches(node.branches, context, path)
            elif isinstance(node, SFCSubsequence | SFCTransitionSub):
                self._walk_seq_nodes(node.body, env, path)


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
        self._push_site(f"{base}:ENTER")
        try:
            _enter_reads, enter_writes = self._capture_block_accesses(
                step.code.enter or [],
                context,
                module_path,
            )
        finally:
            self._pop_site()

        self._push_site(f"{base}:ACTIVE")
        try:
            _active_reads, active_writes = self._capture_block_accesses(
                step.code.active or [],
                context,
                module_path,
            )
        finally:
            self._pop_site()

        self._push_site(f"{base}:EXIT")
        try:
            _exit_reads, exit_writes = self._capture_block_accesses(
                step.code.exit or [],
                context,
                module_path,
            )
        finally:
            self._pop_site()

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


def _expr_text(expr: Any) -> str:
    return " ".join(format_expr(expr).split())


def _signature_sort_key(signature: object) -> str:
    return repr(signature)


def _invert_compare_operator(operator: str) -> str:
    return {
        "<": ">",
        ">": "<",
        "<=": ">=",
        ">=": "<=",
    }.get(operator, operator)


def _signature_literal_value(signature: object) -> bool | int | float | str | None:
    if not isinstance(signature, tuple) or len(signature) != 2:
        return None
    tag, value = signature
    if tag in {"bool", "int", "float", "str"}:
        return value
    return None


def _compare_literal_values(
    left: bool | int | float | str,
    operator: str,
    right: bool | int | float | str,
) -> bool | None:
    try:
        if operator == "==":
            return left == right
        if operator == "<>":
            return left != right
        if operator == "<":
            return left < right  # type: ignore[operator]
        if operator == ">":
            return left > right  # type: ignore[operator]
        if operator == "<=":
            return left <= right  # type: ignore[operator]
        if operator == ">=":
            return left >= right  # type: ignore[operator]
    except TypeError:
        return None
    return None


def _complement_signature(signature: object) -> object:
    if signature == ("bool", True):
        return ("bool", False)
    if signature == ("bool", False):
        return ("bool", True)
    if isinstance(signature, tuple) and signature:
        tag = signature[0]
        if tag == "not" and len(signature) == 2:
            return signature[1]
        if tag == "compare" and len(signature) == 4:
            _tag, operator, left, right = signature
            if operator == "==":
                return ("compare", "<>", left, right)
            if operator == "<>":
                return ("compare", "==", left, right)
            if operator == "<":
                return ("compare", ">=", left, right)
            if operator == ">":
                return ("compare", "<=", left, right)
            if operator == "<=":
                return ("compare", ">", left, right)
            if operator == ">=":
                return ("compare", "<", left, right)
    return ("not", signature)


def _normalize_logical_guard(kind: str, parts: list[object]) -> object:
    flattened: list[object] = []
    for part in parts:
        if isinstance(part, tuple) and len(part) == 2 and part[0] == kind:
            flattened.extend(part[1])
        else:
            flattened.append(part)

    if kind == "and":
        if any(part == ("bool", False) for part in flattened):
            return ("bool", False)
        flattened = [part for part in flattened if part != ("bool", True)]
    else:
        if any(part == ("bool", True) for part in flattened):
            return ("bool", True)
        flattened = [part for part in flattened if part != ("bool", False)]

    normalized: list[object] = []
    seen: set[str] = set()
    for part in flattened:
        complement = _complement_signature(part)
        if repr(complement) in seen:
            return ("bool", False) if kind == "and" else ("bool", True)
        part_key = repr(part)
        if part_key in seen:
            continue
        seen.add(part_key)
        normalized.append(part)

    if not normalized:
        return ("bool", True) if kind == "and" else ("bool", False)
    if len(normalized) == 1:
        return normalized[0]

    normalized.sort(key=_signature_sort_key)
    return (kind, tuple(normalized))


def _normalize_compare_guard(left: Any, operator: str, right: Any) -> object:
    left_signature = _normalize_guard_signature(left)
    right_signature = _normalize_guard_signature(right)

    left_literal = _signature_literal_value(left_signature)
    right_literal = _signature_literal_value(right_signature)
    if left_literal is not None and right_literal is not None:
        folded = _compare_literal_values(left_literal, operator, right_literal)
        if folded is not None:
            return ("bool", folded)

    if left_signature == right_signature:
        if operator in {"==", "<=", ">="}:
            return ("bool", True)
        if operator in {"<>", "<", ">"}:
            return ("bool", False)

    normalized_operator = operator
    if operator in {"==", "<>"}:
        ordered = sorted([left_signature, right_signature], key=_signature_sort_key)
        left_signature, right_signature = ordered
    elif _signature_sort_key(left_signature) > _signature_sort_key(right_signature):
        left_signature, right_signature = right_signature, left_signature
        normalized_operator = _invert_compare_operator(operator)

    return ("compare", normalized_operator, left_signature, right_signature)


def _normalize_guard_signature(expr: Any) -> object:
    if hasattr(expr, "data") and expr.data == const.KEY_STATEMENT:
        children = getattr(expr, "children", [])
        if children:
            return _normalize_guard_signature(children[0])
        return ("text", "")

    if isinstance(expr, bool):
        return ("bool", expr)
    if isinstance(expr, int) and not isinstance(expr, bool):
        return ("int", int(expr))
    if isinstance(expr, float):
        return ("float", float(expr))
    if isinstance(expr, str):
        return ("str", expr)

    if isinstance(expr, dict) and const.KEY_VAR_NAME in expr:
        full_name = expr[const.KEY_VAR_NAME]
        state_access = expr.get("state")
        if isinstance(full_name, str) and full_name:
            if isinstance(state_access, str) and state_access:
                return ("var", full_name.casefold(), state_access.casefold())
            return ("var", full_name.casefold())
        return ("text", _expr_text(expr).casefold())

    if isinstance(expr, tuple) and expr:
        operator = expr[0]

        if operator == const.GRAMMAR_VALUE_NOT:
            return _complement_signature(_normalize_guard_signature(expr[1]))

        if operator in (const.GRAMMAR_VALUE_AND, const.GRAMMAR_VALUE_OR):
            logical_kind = "and" if operator == const.GRAMMAR_VALUE_AND else "or"
            return _normalize_logical_guard(
                logical_kind,
                [_normalize_guard_signature(part) for part in expr[1] or []],
            )

        if operator in (const.KEY_COMPARE, "compare"):
            _compare, left, pairs = expr
            comparisons = [_normalize_compare_guard(left, symbol, right) for symbol, right in pairs or []]
            if not comparisons:
                return _normalize_guard_signature(left)
            if len(comparisons) == 1:
                return comparisons[0]
            return _normalize_logical_guard("and", comparisons)

    return ("text", _expr_text(expr).casefold())


def _guard_constant_truth(signature: object) -> bool | None:
    if isinstance(signature, tuple) and len(signature) == 2 and signature[0] == "bool":
        return bool(signature[1])
    return None


def _collect_transition_logic_issues(base_picture: BasePicture) -> list[Issue]:
    issues: list[Issue] = []

    def inspect_nodes(
        nodes: SequenceABC[object] | None,
        module_path: list[str],
        sequence_name: str,
        branch_path: tuple[int, ...] = (),
    ) -> None:
        duplicate_groups: dict[str, list[dict[str, Any]]] = {}

        for index, node in enumerate(nodes or []):
            if isinstance(node, SFCTransition):
                condition_text = _expr_text(node.condition)
                signature = _normalize_guard_signature(node.condition)
                constant_truth = _guard_constant_truth(signature)
                transition_name = node.name or f"<unnamed:{index + 1}>"
                data = {
                    "sequence": sequence_name,
                    "branch_path": list(branch_path),
                    "transition_name": transition_name,
                    "condition": condition_text,
                    "normalized_guard": repr(signature),
                }
                if constant_truth is True:
                    issues.append(
                        Issue(
                            kind="sfc_transition_always_true",
                            message=(
                                f"Transition {transition_name!r} in sequence {sequence_name!r}{_format_branch_path(branch_path)} "
                                f"has a guard that is always true: {condition_text}."
                            ),
                            module_path=module_path.copy(),
                            data=data,
                        )
                    )
                elif constant_truth is False:
                    issues.append(
                        Issue(
                            kind="sfc_transition_always_false",
                            message=(
                                f"Transition {transition_name!r} in sequence {sequence_name!r}{_format_branch_path(branch_path)} "
                                f"has a guard that is always false: {condition_text}."
                            ),
                            module_path=module_path.copy(),
                            data=data,
                        )
                    )

                duplicate_groups.setdefault(repr(signature), []).append(
                    {
                        "name": transition_name,
                        "condition": condition_text,
                        "normalized_guard": repr(signature),
                    }
                )
                continue

            if isinstance(node, SFCAlternative | SFCParallel):
                for branch_index, branch in enumerate(node.branches or []):
                    inspect_nodes(
                        branch,
                        module_path,
                        sequence_name,
                        (*branch_path, branch_index),
                    )
                continue

            if isinstance(node, SFCSubsequence | SFCTransitionSub):
                inspect_nodes(node.body, module_path, sequence_name, branch_path)

        for duplicates in duplicate_groups.values():
            if len(duplicates) < 2:
                continue
            transition_names = [item["name"] for item in duplicates]
            issues.append(
                Issue(
                    kind="sfc_duplicate_transition_guard",
                    message=(
                        f"Sequence {sequence_name!r}{_format_branch_path(branch_path)} contains transitions with equivalent guards: "
                        f"{', '.join(repr(name) for name in transition_names)}."
                    ),
                    module_path=module_path.copy(),
                    data={
                        "sequence": sequence_name,
                        "branch_path": list(branch_path),
                        "transition_names": transition_names,
                        "conditions": [item["condition"] for item in duplicates],
                        "normalized_guard": duplicates[0]["normalized_guard"],
                    },
                )
            )

    def inspect_modulecode(modulecode: ModuleCode | None, module_path: list[str]) -> None:
        if modulecode is None:
            return
        for sequence in modulecode.sequences or []:
            if isinstance(sequence, Sequence):
                inspect_nodes(sequence.code, module_path, sequence.name)

    def walk_modules(
        modules: SequenceABC[object] | None,
        module_path: list[str],
    ) -> None:
        for module in modules or []:
            if isinstance(module, SingleModule):
                child_path = [*module_path, module.header.name]
                inspect_modulecode(module.modulecode, child_path)
                walk_modules(module.submodules, child_path)
            elif isinstance(module, FrameModule):
                child_path = [*module_path, module.header.name]
                inspect_modulecode(getattr(module, "modulecode", None), child_path)
                walk_modules(module.submodules, child_path)

    root_path = [base_picture.header.name]
    inspect_modulecode(base_picture.modulecode, root_path)
    walk_modules(base_picture.submodules, root_path)
    for moduletype in base_picture.moduletype_defs or []:
        if isinstance(moduletype, ModuleTypeDef):
            inspect_modulecode(
                moduletype.modulecode,
                [base_picture.header.name, f"TypeDef:{moduletype.name}"],
            )

    return issues


def _collect_active_step_sets(nodes: list[object] | None) -> set[StepSet]:
    active_sets: set[StepSet] = set()

    for node in nodes or []:
        if isinstance(node, SFCStep):
            active_sets.add(frozenset({node.name}))
            continue

        if isinstance(node, SFCTransition | SFCFork | SFCBreak):
            continue

        if isinstance(node, SFCAlternative):
            for branch in node.branches or []:
                active_sets.update(_collect_active_step_sets(branch))
            continue

        if isinstance(node, SFCParallel):
            branch_sets: list[set[StepSet]] = []
            for branch in node.branches or []:
                states = _collect_active_step_sets(branch)
                branch_sets.append(states or {frozenset()})

            for branch_combo in product(*branch_sets):
                merged: set[str] = set()
                for state_set in branch_combo:
                    merged.update(state_set)
                if merged:
                    active_sets.add(frozenset(merged))
            continue

        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            active_sets.update(_collect_active_step_sets(node.body))

    return active_sets


def _find_illegal_state_combinations(
    active_step_sets: Iterable[StepSet],
    mutually_exclusive_steps: tuple[ExclusiveStepGroup, ...],
) -> list[tuple[str, ...]]:
    conflicts: dict[tuple[str, ...], None] = {}

    for active_steps in active_step_sets:
        active_keys = {name.casefold() for name in active_steps}
        for group in mutually_exclusive_steps:
            overlap = tuple(name for name in group if name.casefold() in active_keys)
            if len(overlap) >= 2:
                conflicts[overlap] = None

    return sorted(conflicts.keys())


def _collect_illegal_state_combination_issues(
    base_picture: BasePicture,
    mutually_exclusive_steps: tuple[ExclusiveStepGroup, ...],
) -> list[Issue]:
    issues: list[Issue] = []

    def inspect_modulecode(modulecode: ModuleCode | None, module_path: list[str]) -> None:
        if modulecode is None or not mutually_exclusive_steps:
            return

        for sequence in modulecode.sequences or []:
            if not isinstance(sequence, Sequence):
                continue

            conflicts = _find_illegal_state_combinations(
                _collect_active_step_sets(sequence.code or []),
                mutually_exclusive_steps,
            )
            if not conflicts:
                continue

            preview = "; ".join(" + ".join(combo) for combo in conflicts[:4])
            if len(conflicts) > 4:
                preview = f"{preview}; ... (+{len(conflicts) - 4} more)"

            issues.append(
                Issue(
                    kind="sfc_illegal_state_combination",
                    message=(
                        f"Sequence {sequence.name!r} can activate mutually exclusive step combinations: {preview}"
                    ),
                    module_path=module_path.copy(),
                    data={
                        "sequence": sequence.name,
                        "conflicts": [list(combo) for combo in conflicts],
                    },
                )
            )

    def walk_modules(modules: SequenceABC[object] | None, module_path: list[str]) -> None:
        for module in modules or []:
            if isinstance(module, SingleModule):
                child_path = [*module_path, module.header.name]
                inspect_modulecode(module.modulecode, child_path)
                walk_modules(module.submodules, child_path)
            elif isinstance(module, FrameModule):
                child_path = [*module_path, module.header.name]
                inspect_modulecode(getattr(module, "modulecode", None), child_path)
                walk_modules(module.submodules, child_path)

    root_path = [base_picture.header.name]
    inspect_modulecode(base_picture.modulecode, root_path)
    walk_modules(base_picture.submodules, root_path)
    for moduletype in base_picture.moduletype_defs or []:
        if isinstance(moduletype, ModuleTypeDef):
            inspect_modulecode(
                moduletype.modulecode,
                [base_picture.header.name, f"TypeDef:{moduletype.name}"],
            )

    return issues


def _format_branch_path(branch_path: tuple[int, ...]) -> str:
    if not branch_path:
        return ""
    return " branch " + ".".join(str(index + 1) for index in branch_path)


def _format_terminator(terminated_by: dict[str, Any]) -> str:
    terminator = str(terminated_by.get("kind", "an earlier terminating node"))
    target = terminated_by.get("target")
    if target:
        return f"{terminator} targeting {target!r}"
    return terminator


def analyze_sfc(
    base_picture: BasePicture,
    mutually_exclusive_steps: Iterable[Iterable[str]] | None = None,
    step_contracts: Mapping[str, object] | None = None,
) -> SimpleReport:
    collector = _SfcAccessCollector(base_picture)
    collector.run()
    normalized_groups = _normalize_step_groups(mutually_exclusive_steps)
    normalized_step_contracts = normalize_step_contracts(step_contracts)

    issues: list[Issue] = []
    for key, branch_writes in collector.parallel_writes.items():
        conflicts: dict[tuple[str, ...], CanonicalPath] = {}
        branch_ids = sorted(branch_writes.keys())
        for index, left in enumerate(branch_ids):
            for right in branch_ids[index + 1 :]:
                for left_path in branch_writes[left]:
                    for right_path in branch_writes[right]:
                        if _paths_conflict(left_path, right_path):
                            rep = _conflict_rep(left_path, right_path)
                            conflicts.setdefault(rep.key(), rep)

        if not conflicts:
            continue

        meta = collector.parallel_meta.get(key)
        seq_name = meta.sequence_name if meta else "<unnamed>"
        conflict_list = sorted(str(path) for path in conflicts.values())
        preview = ", ".join(conflict_list[:6])
        if len(conflict_list) > 6:
            preview = f"{preview}, ... (+{len(conflict_list) - 6} more)"

        issues.append(
            Issue(
                kind="sfc_parallel_write_race",
                message=(f"Parallel branches in sequence {seq_name!r} write to the same variable(s): {preview}"),
                module_path=meta.module_path if meta else None,
                data={
                    "sequence": seq_name,
                    "parallel_id": meta.parallel_id if meta else None,
                    "conflicts": conflict_list,
                },
            )
        )

    for finding in collect_sfc_reachability_findings(base_picture):
        branch_context = _format_branch_path(finding.branch_path)
        terminator = _format_terminator(finding.terminated_by)
        data = {
            "sequence": finding.sequence_name,
            "branch_path": list(finding.branch_path),
            "node_index": finding.node_index,
            "node_label": finding.node_label,
            "node_type": finding.node_type,
            "terminated_by": dict(finding.terminated_by),
        }
        if finding.node_type in {"SFCTransition", "SFCTransitionSub"}:
            issues.append(
                Issue(
                    kind="sfc_unreachable_transition",
                    message=(
                        f"Transition {finding.node_label!r} in sequence {finding.sequence_name!r}{branch_context} "
                        f"can never fire because {terminator} terminates that path earlier."
                    ),
                    module_path=list(finding.module_path),
                    data=data,
                )
            )
        else:
            issues.append(
                Issue(
                    kind="sfc_unreachable_sequence_node",
                    message=(
                        f"Sequence {finding.sequence_name!r}{branch_context} contains unreachable node "
                        f"{finding.node_label!r} because {terminator} terminates that path earlier."
                    ),
                    module_path=list(finding.module_path),
                    data=data,
                )
            )

    issues.extend(_collect_transition_logic_issues(base_picture))

    issues.extend(_collect_illegal_state_combination_issues(base_picture, normalized_groups))

    if normalized_step_contracts:
        contract_collector = _SfcStepContractCollector(
            base_picture,
            normalized_step_contracts,
        )
        issues.extend(contract_collector.collect())

    return SimpleReport(name=base_picture.header.name, issues=issues)
