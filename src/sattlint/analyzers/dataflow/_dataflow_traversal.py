from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sattlint.parser_api import (
    Assignment,
    FrameModule,
    FuncCallStmt,
    IfStmt,
    ModuleCode,
    ModuleDef,
    ModuleTypeDef,
    ModuleTypeInstance,
    ProcedureCall,
    Sequence,
    SFCAlternative,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
    VarRef,
    VarTail,
    walk,
)

from ...core.call_signatures import resolve_call_signature
from ...resolution.common import resolve_moduletype_def_strict
from ...resolution.scope import ScopeContext
from ._dataflow_common import PendingWrite, StateMap
from ._dataflow_scope_support import DataflowScopeSupportMixin


@dataclass(frozen=True, slots=True)
class _StepStates:
    """State snapshots around an SFC step's exit code.

    A step's ``EXITCODE`` runs only after the outgoing transition fires, so the
    guard is evaluated against ``guard``, while the next step starts from
    ``after_exit``.
    """

    guard: StateMap
    after_exit: StateMap


class _DataflowTraversalMixin(DataflowScopeSupportMixin):
    def _walk_root_scope(self: Any) -> None:
        root_path = [self.bp.header.name]
        root_variables = list(self.bp.localvariables or [])
        root_context = self._build_scope_context(
            root_variables,
            param_mappings={},
            module_path=root_path,
            current_library=getattr(self.bp, "origin_lib", None),
            parent_context=None,
            children=self.bp.submodules or [],
        )
        root_state = self._seed_state({}, root_path, root_variables)
        root_state = self._walk_module_code(
            self.bp.modulecode,
            root_context,
            root_path,
            root_state,
            getattr(self.bp, "moduledef", None),
        )
        self._final_root_state = self._walk_modules(self.bp.submodules or [], root_context, root_path, root_state)

    def run(self: Any) -> list[Any]:
        self._walk_root_scope()

        for moduletype in self._iter_root_typedefs():
            typedef_path = [self.bp.header.name, f"TypeDef:{moduletype.name}"]
            typedef_context, typedef_state = self._build_typedef_seed(moduletype, typedef_path)
            self._walk_typedef(moduletype, typedef_context, typedef_path, typedef_state)

        from ._dataflow_non_state_sites import collect_non_state_multi_site_issues  # noqa: PLC0415

        collect_non_state_multi_site_issues(self)

        return self._issues

    def _walk_typedef(
        self: Any,
        moduletype: ModuleTypeDef,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> StateMap:
        typedef_key = moduletype.name.casefold()
        if typedef_key in self._active_typedefs:
            return state
        self._active_typedefs.add(typedef_key)
        try:
            next_state = self._walk_module_code(
                moduletype.modulecode,
                context,
                module_path,
                state,
                moduletype.moduledef,
            )
            return self._walk_modules(moduletype.submodules or [], context, module_path, next_state)
        finally:
            self._active_typedefs.discard(typedef_key)

    def _walk_modules(
        self: Any,
        children: list[SingleModule | FrameModule | ModuleTypeInstance],
        parent_context: ScopeContext,
        parent_path: list[str],
        state: StateMap,
    ) -> StateMap:
        current_state = state
        for child in children:
            child_path = [*parent_path, child.header.name]
            if isinstance(child, SingleModule):
                child_context = self._build_single_context(child, parent_context, child_path)
                child_state = self._seed_state(
                    current_state,
                    child_path,
                    [*(child.moduleparameters or []), *(child.localvariables or [])],
                )
                child_state = self._walk_module_code(
                    child.modulecode,
                    child_context,
                    child_path,
                    child_state,
                    child.moduledef,
                )
                current_state = self._walk_modules(child.submodules or [], child_context, child_path, child_state)
                continue

            if isinstance(child, FrameModule):
                frame_context = ScopeContext(
                    env={},
                    param_mappings={},
                    module_path=child_path.copy(),
                    display_module_path=child_path.copy(),
                    current_library=parent_context.current_library,
                    parent_context=parent_context,
                )
                frame_context.submodule_mapped_source_keys.update(
                    self._child_mapped_source_keys(child.submodules or [], frame_context)
                )
                frame_state = self._walk_module_code(
                    child.modulecode,
                    frame_context,
                    child_path,
                    current_state,
                    child.moduledef,
                )
                current_state = self._walk_modules(child.submodules or [], frame_context, child_path, frame_state)
                continue

            current_state = self._walk_moduletype_instance(child, parent_context, child_path, current_state)

        return current_state

    def _walk_moduletype_instance(
        self: Any,
        instance: ModuleTypeInstance,
        parent_context: ScopeContext,
        child_path: list[str],
        state: StateMap,
    ) -> StateMap:
        try:
            moduletype = resolve_moduletype_def_strict(
                self.bp,
                instance.moduletype_name,
                current_library=parent_context.current_library,
                unavailable_libraries=self._unavailable_libraries,
            )
        except ValueError:
            return state

        if not self._is_from_root_origin(
            getattr(moduletype, "origin_file", None),
            getattr(moduletype, "origin_lib", None),
        ):
            return state

        typedef_context = self._build_typedef_context(moduletype, instance, parent_context, child_path)
        typedef_state = self._seed_state(
            state,
            child_path,
            [*(moduletype.moduleparameters or []), *(moduletype.localvariables or [])],
        )
        return self._walk_typedef(moduletype, typedef_context, child_path, typedef_state)

    def _walk_module_code(
        self: Any,
        modulecode: ModuleCode | None,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
        moduledef: ModuleDef | None = None,
    ) -> StateMap:
        state = self._invalidate_interaction_writes(state, moduledef, context)
        if modulecode is None:
            return state

        current_state = state
        # Every equation block's writes are invalidated before any sequence runs, so
        # the whole set is applied in one pass instead of one pass per root.
        equation_roots: set[tuple[str, ...]] = set()
        for equation in modulecode.equationblocks or []:
            equation_roots.update(self._active_write_roots(equation.code or [], context))
        current_state = self._invalidate_symbols(current_state, equation_roots)
        for sequence in modulecode.sequences or []:
            self._push_site(f"SQ:{getattr(sequence, 'name', '<unnamed>')}")
            try:
                current_state = self._walk_sequence(sequence, context, module_path, current_state)
            finally:
                self._pop_site()

        for equation in modulecode.equationblocks or []:
            self._push_site(f"EQ:{getattr(equation, 'name', '<unnamed>')}")
            try:
                current_state = self._analyze_block(equation.code or [], context, module_path, current_state)
            finally:
                self._pop_site()

        return current_state

    def _invalidate_interaction_writes(
        self: Any,
        state: StateMap,
        moduledef: ModuleDef | None,
        context: ScopeContext,
    ) -> StateMap:
        """Forget constant facts for variables an interact object writes.

        An ``OutVar_`` tail is written by the operator at runtime, so a value
        seeded from the initializer is not a fact the guard can rely on.
        """
        if moduledef is None:
            return state
        next_state = state
        for interact_object in moduledef.interact_objects or []:
            for event in walk(interact_object, prune=lambda node: isinstance(node, ProcedureCall)):
                node = event.node
                if not isinstance(node, VarTail) or node.direction != "out":
                    continue
                name = node.bound_name
                if not name:
                    continue
                resolved = self._resolve_ref(VarRef(name=name), context)
                if resolved is None:
                    continue
                next_state = self._invalidate_symbol(next_state, resolved.symbol_root_key)
                next_state.pop(self._pending_state_key(resolved.symbol_root_key), None)
                self._invalidate_constant_traces(next_state, resolved.symbol_root_key)
        return next_state

    def _walk_sequence(
        self: Any,
        sequence: Sequence,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> StateMap:
        return self._walk_sequence_nodes(
            sequence.code or [],
            context,
            module_path,
            state,
            sequence_name=sequence.name,
            branch_path=(),
            pending_guard_state=None,
        )

    def _walk_sequence_nodes(  # noqa: PLR0915
        self: Any,
        nodes: list[Any],
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
        *,
        sequence_name: str,
        branch_path: tuple[int, ...],
        pending_guard_state: StateMap | None,
    ) -> StateMap:
        current_state = state
        terminated_by: dict[str, Any] | None = None
        guard_state: StateMap | None = pending_guard_state

        for node in nodes:
            if terminated_by is not None:
                continue

            if isinstance(node, SFCStep):
                step_states = self._walk_sequence_step(node, context, module_path, current_state)
                current_state = step_states.after_exit
                guard_state = step_states.guard
                if isinstance(node.fork, SFCFork):
                    terminated_by = {"kind": "SFCFork", "targets": list(node.fork.targets)}
                continue

            if isinstance(node, SFCTransition):
                label = f"TRANS:{node.name or '<unnamed>'}"
                self._push_site(label)
                try:
                    condition_state = current_state if guard_state is None else guard_state
                    guard_state = None
                    self._report_condition(
                        node.condition, context, module_path, self._external_scan_state(context, condition_state)
                    )
                finally:
                    self._pop_site()
                if isinstance(node.fork, SFCFork):
                    terminated_by = {"kind": "SFCFork", "targets": list(node.fork.targets)}
                continue

            if isinstance(node, SFCAlternative):
                branch_states: list[StateMap] = []
                for branch_index, branch in enumerate(node.branches or []):
                    self._push_site(f"ALT:BRANCH:{branch_index}")
                    try:
                        branch_states.append(
                            self._walk_sequence_nodes(
                                branch,
                                context,
                                module_path,
                                current_state.copy(),
                                sequence_name=sequence_name,
                                branch_path=(*branch_path, branch_index),
                                pending_guard_state=guard_state,
                            )
                        )
                    finally:
                        self._pop_site()
                current_state = self._merge_states(branch_states or [current_state])
                guard_state = None
                continue

            if isinstance(node, SFCParallel):
                branch_states = []
                for branch_index, branch in enumerate(node.branches or []):
                    self._push_site(f"PAR:BRANCH:{branch_index}")
                    try:
                        branch_states.append(
                            self._walk_sequence_nodes(
                                branch,
                                context,
                                module_path,
                                current_state.copy(),
                                sequence_name=sequence_name,
                                branch_path=(*branch_path, branch_index),
                                pending_guard_state=guard_state,
                            )
                        )
                    finally:
                        self._pop_site()
                current_state = self._merge_states(branch_states or [current_state])
                guard_state = None
                continue

            if isinstance(node, SFCSubsequence):
                self._push_site(f"SUBSEQ:{getattr(node, 'name', '<unnamed>')}")
                try:
                    current_state = self._walk_sequence_nodes(
                        node.body or [],
                        context,
                        module_path,
                        current_state,
                        sequence_name=sequence_name,
                        branch_path=branch_path,
                        pending_guard_state=guard_state,
                    )
                finally:
                    self._pop_site()
                guard_state = None
                continue

            if isinstance(node, SFCTransitionSub):
                self._push_site(f"TRANS-SUB:{getattr(node, 'name', '<unnamed>')}")
                try:
                    current_state = self._walk_sequence_nodes(
                        node.body or [],
                        context,
                        module_path,
                        current_state,
                        sequence_name=sequence_name,
                        branch_path=branch_path,
                        pending_guard_state=guard_state,
                    )
                finally:
                    self._pop_site()
                guard_state = None
                continue

        return current_state

    def _walk_sequence_step(
        self: Any,
        step: SFCStep,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> _StepStates:
        current_state = state
        base = f"STEP:{step.name}"
        self._push_site(f"{base}:ENTER")
        try:
            current_state = self._analyze_block(
                step.code.enter or [],
                context,
                module_path,
                self._clear_write_effect_state(current_state),
            )
        finally:
            self._pop_site()

        active_state = self._external_scan_state(context, current_state)
        for root_key in self._active_write_roots(step.code.active or [], context):
            active_state = self._invalidate_symbol(active_state, root_key)
        self._push_site(f"{base}:ACTIVE")
        try:
            current_state = self._analyze_block(
                step.code.active or [],
                context,
                module_path,
                self._clear_write_effect_state(active_state),
            )
        finally:
            self._pop_site()

        guard_state = current_state
        self._push_site(f"{base}:EXIT")
        try:
            current_state = self._analyze_block(
                step.code.exit or [],
                context,
                module_path,
                self._clear_write_effect_state(current_state),
            )
        finally:
            self._pop_site()

        return _StepStates(guard=guard_state, after_exit=current_state)

    def _external_scan_state(self: Any, context: ScopeContext, state: StateMap) -> StateMap:
        # A parameter written by code outside this scope can change between scans, so
        # every non-constant parameter in the scope chain loses its tracked value,
        # along with the sources its submodules map in. They are collected first and
        # dropped in one pass: testing them one by one scanned the whole state once
        # per key.
        external_keys: set[tuple[str, ...]] = set()
        scope: ScopeContext | None = context
        while scope is not None:
            for name in scope.moduleparameter_keys | scope.param_mappings.keys():
                variable, _, _, _ = scope.resolve_variable(name)
                if variable is None or variable.const:
                    continue
                resolved = self._resolve_ref(VarRef(name=name), scope)
                if resolved is not None:
                    external_keys.add(resolved.symbol_key)
            external_keys.update(scope.submodule_mapped_source_keys)
            scope = scope.parent_context
        return self._invalidate_symbols(state, external_keys)

    def _active_write_roots(self: Any, statements: list[object], context: ScopeContext) -> set[tuple[str, ...]]:
        roots: set[tuple[str, ...]] = set()
        pending: list[object] = list(statements)
        while pending:
            statement = pending.pop()
            if isinstance(statement, IfStmt):
                for _condition, branch in statement.branches:
                    pending.extend(branch)
                pending.extend(statement.else_block or [])
                continue
            if isinstance(statement, Assignment):
                resolved = self._resolve_ref(statement.target, context)
                if resolved is not None:
                    roots.add(resolved.symbol_root_key)
                continue
            if isinstance(statement, FuncCallStmt):
                signature = resolve_call_signature(statement.call.name)
                if signature is None:
                    continue
                for parameter, argument in zip(signature.parameters, statement.call.args, strict=False):
                    if not parameter.is_output:
                        continue
                    resolved = self._resolve_ref(argument, context)
                    if resolved is not None:
                        roots.add(resolved.symbol_root_key)
        return roots

    def _analyze_block(
        self: Any,
        statements: list[Any],
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> StateMap:
        current_state = state
        for statement in statements:
            current_state = self._analyze_stmt_or_expr(statement, context, module_path, current_state)
        return current_state

    def _analyze_stmt_or_expr(
        self: Any,
        obj: object,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> StateMap:
        if isinstance(obj, IfStmt):
            return self._analyze_if_statement(obj, context, module_path, state)

        if isinstance(obj, Assignment):
            current_state = state
            self._report_expression_temporal_hazards(obj.value, context, module_path, current_state)
            value = self._evaluate_expression(obj.value, context, module_path, current_state)
            return self._write_target(obj.target, value, context, current_state)

        if isinstance(obj, FuncCallStmt):
            current_state = state
            self._report_expression_temporal_hazards(obj.call, context, module_path, current_state)
            # Expression evaluation applies signature-driven output writes, so
            # the statement path must not apply them a second time (a repeated
            # write would report the first write as a dead overwrite).
            self._evaluate_expression(obj.call, context, module_path, current_state)
            return current_state

        self._report_expression_temporal_hazards(obj, context, module_path, state)
        self._evaluate_expression(obj, context, module_path, state)
        return state

    def _analyze_if_statement(
        self: Any,
        statement: IfStmt,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> StateMap:
        branches = list(statement.branches)
        else_block = statement.else_block
        reachable_states: list[StateMap] = []
        fallthrough_state = state

        for index, (condition, statements) in enumerate(branches or []):
            branch_label = "IF" if index == 0 else "ELSIF"
            condition_value = self._report_condition(condition, context, module_path, fallthrough_state)
            condition_text = self._expr_text(condition)

            if condition_value is False:
                self._add_issue(
                    kind="dataflow.unreachable_branch",
                    message=(
                        f"{branch_label} branch is unreachable because condition {condition_text!r} is always false at this point."
                    ),
                    module_path=module_path,
                    data={
                        "branch": branch_label,
                        "branch_index": index,
                        "condition": condition_text,
                        "site": self._site_str(),
                    },
                )
                fallthrough_state = self._assume(condition, False, fallthrough_state, context, module_path)
                continue

            assumed_true_state = self._assume(condition, True, fallthrough_state, context, module_path)
            if condition_value is None:
                self._conditional_entry_writes.append(
                    {value for value in fallthrough_state.values() if isinstance(value, PendingWrite)}
                )
            self._push_site(f"{branch_label}:BRANCH:{index}")
            try:
                branch_state = self._analyze_block(statements or [], context, module_path, assumed_true_state)
            finally:
                self._pop_site()
                if condition_value is None:
                    self._conditional_entry_writes.pop()
            reachable_states.append(branch_state)

            if condition_value is True:
                for unreachable_index in range(index + 1, len(branches or [])):
                    later_label = "ELSIF"
                    self._add_issue(
                        kind="dataflow.unreachable_branch",
                        message=(
                            f"{later_label} branch is unreachable because a previous condition {condition_text!r} is always true at this point."
                        ),
                        module_path=module_path,
                        data={
                            "branch": later_label,
                            "branch_index": unreachable_index,
                            "trigger_condition": condition_text,
                            "site": self._site_str(),
                        },
                    )
                if else_block:
                    self._add_issue(
                        kind="dataflow.unreachable_branch",
                        message=(
                            f"ELSE branch is unreachable because a previous condition {condition_text!r} is always true at this point."
                        ),
                        module_path=module_path,
                        data={
                            "branch": "ELSE",
                            "trigger_condition": condition_text,
                            "site": self._site_str(),
                        },
                    )
                return self._merge_states(reachable_states)

            fallthrough_state = self._assume(condition, False, fallthrough_state, context, module_path)

        if else_block is not None:
            self._conditional_entry_writes.append(
                {value for value in fallthrough_state.values() if isinstance(value, PendingWrite)}
            )
            self._push_site("ELSE:BRANCH")
            try:
                reachable_states.append(self._analyze_block(else_block or [], context, module_path, fallthrough_state))
            finally:
                self._pop_site()
                self._conditional_entry_writes.pop()
        else:
            reachable_states.append(fallthrough_state)

        return self._merge_states(reachable_states)


DataflowTraversalMixin = _DataflowTraversalMixin
