from __future__ import annotations

from typing import Any, cast

from sattline_parser.models.ast_model import (
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
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
)

from ..grammar import constants as const
from ..resolution.common import resolve_moduletype_def_strict
from ..resolution.scope import ScopeContext
from ._dataflow_common import StateMap
from ._dataflow_scope_support import _DataflowScopeSupportMixin
from .ast_node_helpers import (
    object_tuple as _object_tuple,
)
from .ast_node_helpers import (
    sequence_as_list as _sequence_as_list,
)
from .ast_node_helpers import (
    statement_children as _statement_children,
)


class _DataflowTraversalMixin(_DataflowScopeSupportMixin):
    def _walk_root_scope(self: Any) -> None:
        root_path = [self.bp.header.name]
        root_variables = list(self.bp.localvariables or [])
        root_context = self._build_scope_context(
            root_variables,
            param_mappings={},
            module_path=root_path,
            current_library=getattr(self.bp, "origin_lib", None),
            parent_context=None,
        )
        root_state = self._seed_state({}, root_path, root_variables)
        root_state = self._walk_module_code(self.bp.modulecode, root_context, root_path, root_state)
        self._final_root_state = self._walk_modules(self.bp.submodules or [], root_context, root_path, root_state)

    def run(self: Any) -> list[Any]:
        self._walk_root_scope()

        for moduletype in self._iter_root_typedefs():
            typedef_path = [self.bp.header.name, f"TypeDef:{moduletype.name}"]
            typedef_context, typedef_state = self._build_typedef_seed(moduletype, typedef_path)
            self._walk_typedef(moduletype, typedef_context, typedef_path, typedef_state)

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
            next_state = self._walk_module_code(moduletype.modulecode, context, module_path, state)
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
                child_state = self._walk_module_code(child.modulecode, child_context, child_path, child_state)
                current_state = self._walk_modules(child.submodules or [], child_context, child_path, child_state)
                continue

            if isinstance(child, FrameModule):
                frame_context = ScopeContext(
                    env=parent_context.env,
                    param_mappings=parent_context.param_mappings,
                    module_path=child_path.copy(),
                    display_module_path=child_path.copy(),
                    current_library=parent_context.current_library,
                    parent_context=parent_context,
                )
                frame_state = self._walk_module_code(child.modulecode, frame_context, child_path, current_state)
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
    ) -> StateMap:
        if modulecode is None:
            return state

        current_state = state
        for sequence in modulecode.sequences or []:
            self._push_site(f"SEQ:{getattr(sequence, 'name', '<unnamed>')}")
            try:
                current_state = self._walk_sequence(sequence, context, module_path, current_state)
            finally:
                self._pop_site()

        for equation in modulecode.equations or []:
            self._push_site(f"EQ:{getattr(equation, 'name', '<unnamed>')}")
            try:
                current_state = self._analyze_block(equation.code or [], context, module_path, current_state)
            finally:
                self._pop_site()

        return current_state

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
        )

    def _walk_sequence_nodes(
        self: Any,
        nodes: list[Any],
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
        *,
        sequence_name: str,
        branch_path: tuple[int, ...],
    ) -> StateMap:
        current_state = state
        terminated_by: dict[str, Any] | None = None

        for index, node in enumerate(nodes):
            if terminated_by is not None:
                self._add_issue(
                    kind="dataflow.unreachable_sequence_node",
                    message=(
                        f"Sequence node {self._sequence_node_label(node)!r} is unreachable because "
                        f"execution is terminated earlier by {terminated_by['kind']}."
                    ),
                    module_path=module_path,
                    data={
                        "sequence": sequence_name,
                        "branch_path": list(branch_path),
                        "node_index": index,
                        "node_label": self._sequence_node_label(node),
                        "terminated_by": terminated_by,
                        "site": self._site_str(),
                    },
                )
                continue

            if isinstance(node, SFCStep):
                current_state = self._walk_sequence_step(node, context, module_path, current_state)
                continue

            if isinstance(node, SFCTransition):
                label = f"TRANS:{node.name or '<unnamed>'}"
                self._push_site(label)
                try:
                    self._report_condition(node.condition, context, module_path, current_state)
                finally:
                    self._pop_site()
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
                            )
                        )
                    finally:
                        self._pop_site()
                current_state = self._merge_states(branch_states or [current_state])
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
                            )
                        )
                    finally:
                        self._pop_site()
                current_state = self._merge_states(branch_states or [current_state])
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
                    )
                finally:
                    self._pop_site()
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
                    )
                finally:
                    self._pop_site()
                continue

            if isinstance(node, SFCBreak):
                terminated_by = {"kind": "SFCBreak"}
                continue

            if isinstance(node, SFCFork):
                terminated_by = {"kind": "SFCFork", "target": node.target}
                continue

        return current_state

    def _walk_sequence_step(
        self: Any,
        step: SFCStep,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> StateMap:
        current_state = state
        base = f"STEP:{step.name}"
        self._push_site(f"{base}:ENTER")
        try:
            current_state = self._analyze_block(step.code.enter or [], context, module_path, current_state)
        finally:
            self._pop_site()

        self._push_site(f"{base}:ACTIVE")
        try:
            current_state = self._analyze_block(step.code.active or [], context, module_path, current_state)
        finally:
            self._pop_site()

        self._push_site(f"{base}:EXIT")
        try:
            current_state = self._analyze_block(step.code.exit or [], context, module_path, current_state)
        finally:
            self._pop_site()

        return current_state

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
        statement_children = _statement_children(obj)
        if statement_children is not None:
            current_state = state
            for child in statement_children:
                current_state = self._analyze_stmt_or_expr(child, context, module_path, current_state)
            return current_state

        tuple_node = _object_tuple(obj)
        if tuple_node is not None and tuple_node and tuple_node[0] == const.GRAMMAR_VALUE_IF:
            return self._analyze_if_statement(cast(tuple[Any, ...], tuple_node), context, module_path, state)

        if tuple_node is not None and tuple_node and tuple_node[0] == const.KEY_ASSIGN and len(tuple_node) >= 3:
            target = tuple_node[1]
            expr = tuple_node[2]
            current_state = state
            self._report_expression_temporal_hazards(expr, context, module_path, current_state)
            value = self._evaluate_expression(expr, context, module_path, current_state)
            return self._write_target(target, value, context, current_state)

        if tuple_node is not None and tuple_node and tuple_node[0] == const.KEY_FUNCTION_CALL:
            function_name = tuple_node[1] if len(tuple_node) > 1 else None
            args = _sequence_as_list(tuple_node[2] if len(tuple_node) > 2 else None)
            current_state = state
            for argument in args:
                self._report_expression_temporal_hazards(argument, context, module_path, current_state)
                self._evaluate_expression(argument, context, module_path, current_state)
            return self._apply_call_side_effects(function_name, args, context, current_state)

        self._report_expression_temporal_hazards(obj, context, module_path, state)
        self._evaluate_expression(obj, context, module_path, state)
        return state

    def _analyze_if_statement(
        self: Any,
        statement: tuple[Any, ...],
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> StateMap:
        _if_tag, branches, else_block = statement
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
            self._push_site(f"{branch_label}:BRANCH:{index}")
            try:
                branch_state = self._analyze_block(statements or [], context, module_path, assumed_true_state)
            finally:
                self._pop_site()
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
            self._push_site("ELSE:BRANCH")
            try:
                reachable_states.append(self._analyze_block(else_block or [], context, module_path, fallthrough_state))
            finally:
                self._pop_site()
        else:
            reachable_states.append(fallthrough_state)

        return self._merge_states(reachable_states)


DataflowTraversalMixin = _DataflowTraversalMixin
