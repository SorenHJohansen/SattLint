from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeGuard, cast

from sattline_parser.utils.formatter import format_expr

from ..grammar import constants as const
from ..models.ast_model import (
    BasePicture,
    FloatLiteral,
    FrameModule,
    IntLiteral,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
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
from ..resolution.common import resolve_moduletype_def_strict, varname_base
from ..resolution.scope import ScopeContext
from .framework import Issue, SimpleReport
from .sattline_builtins import get_function_signature

ScalarValue = bool | int | float | str
StateMap = dict[tuple[str, ...], ScalarValue | object]
ConditionFact = tuple[str, tuple[str, ...], Any]

_UNKNOWN = object()
_INITIALIZED = object()
_PENDING_PREFIX = ("__pending__",)
_OLD_PREFIX = ("__old__",)


def _is_scalar_value(value: ScalarValue | object) -> TypeGuard[ScalarValue]:
    return isinstance(value, (bool, int, float, str))


@dataclass(frozen=True)
class _ResolvedRef:
    key: tuple[str, ...]
    root_key: tuple[str, ...]
    symbol_key: tuple[str, ...]
    symbol_root_key: tuple[str, ...]
    display_name: str
    base_display_name: str
    state_access: str | None
    is_state_variable: bool


@dataclass(frozen=True)
class _PendingWrite:
    key: tuple[str, ...]
    root_key: tuple[str, ...]
    display_name: str
    sites: tuple[str, ...]


class DataflowAnalyzer:
    def __init__(
        self,
        base_picture: BasePicture,
        unavailable_libraries: set[str] | None = None,
    ) -> None:
        self.bp = base_picture
        self._unavailable_libraries = unavailable_libraries or set()
        self._issues: list[Issue] = []
        self._site_stack: list[str] = []
        self._active_typedefs: set[str] = set()
        self._reported_read_before_write: set[tuple[tuple[str, ...], str, str]] = set()
        self._reported_dead_overwrite: set[tuple[tuple[str, ...], str, str]] = set()
        self._reported_scan_cycle_stale_read: set[tuple[tuple[str, ...], str, str]] = set()
        self._reported_scan_cycle_implicit_new: set[tuple[tuple[str, ...], str, str]] = set()
        self._reported_scan_cycle_temporal_misuse: set[tuple[tuple[str, ...], str, str, str]] = set()

    @property
    def issues(self) -> list[Issue]:
        return self._issues

    def run(self) -> list[Issue]:
        root_path = [self.bp.header.name]
        root_context = ScopeContext(
            env={variable.name.casefold(): variable for variable in self.bp.localvariables or []},
            param_mappings={},
            module_path=root_path.copy(),
            display_module_path=root_path.copy(),
            current_library=getattr(self.bp, "origin_lib", None),
            parent_context=None,
        )
        root_state = self._seed_state({}, root_path, self.bp.localvariables or [])

        self._walk_module_code(self.bp.modulecode, root_context, root_path, root_state)
        self._walk_modules(self.bp.submodules or [], root_context, root_path, root_state)

        for moduletype in self.bp.moduletype_defs or []:
            if not self._is_from_root_origin(getattr(moduletype, "origin_file", None)):
                continue
            typedef_path = [self.bp.header.name, f"TypeDef:{moduletype.name}"]
            typedef_context = ScopeContext(
                env={
                    variable.name.casefold(): variable
                    for variable in [*(moduletype.moduleparameters or []), *(moduletype.localvariables or [])]
                },
                param_mappings={},
                module_path=typedef_path.copy(),
                display_module_path=typedef_path.copy(),
                current_library=moduletype.origin_lib or getattr(self.bp, "origin_lib", None),
                parent_context=None,
            )
            typedef_state = self._seed_state(
                {},
                typedef_path,
                [*(moduletype.moduleparameters or []), *(moduletype.localvariables or [])],
            )
            self._walk_typedef(moduletype, typedef_context, typedef_path, typedef_state)

        return self._issues

    def _walk_typedef(
        self,
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
        self,
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
        self,
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

        if not self._is_from_root_origin(getattr(moduletype, "origin_file", None)):
            return state

        typedef_context = self._build_typedef_context(moduletype, instance, parent_context, child_path)
        typedef_state = self._seed_state(
            state,
            child_path,
            [*(moduletype.moduleparameters or []), *(moduletype.localvariables or [])],
        )
        return self._walk_typedef(moduletype, typedef_context, child_path, typedef_state)

    def _build_single_context(
        self,
        mod: SingleModule,
        parent_context: ScopeContext,
        module_path: list[str],
    ) -> ScopeContext:
        env = {variable.name.casefold(): variable for variable in mod.moduleparameters or []}
        env.update({variable.name.casefold(): variable for variable in mod.localvariables or []})
        return ScopeContext(
            env=env,
            param_mappings=self._build_parameter_mappings(
                mod.parametermappings or [],
                parent_context,
            ),
            module_path=module_path.copy(),
            display_module_path=module_path.copy(),
            current_library=parent_context.current_library,
            parent_context=parent_context,
        )

    def _build_typedef_context(
        self,
        moduletype: ModuleTypeDef,
        instance: ModuleTypeInstance,
        parent_context: ScopeContext,
        module_path: list[str],
    ) -> ScopeContext:
        env = {variable.name.casefold(): variable for variable in moduletype.moduleparameters or []}
        env.update({variable.name.casefold(): variable for variable in moduletype.localvariables or []})
        return ScopeContext(
            env=env,
            param_mappings=self._build_parameter_mappings(
                instance.parametermappings or [],
                parent_context,
            ),
            module_path=module_path.copy(),
            display_module_path=module_path.copy(),
            current_library=moduletype.origin_lib or parent_context.current_library,
            parent_context=parent_context,
        )

    def _build_parameter_mappings(
        self,
        mappings: list[ParameterMapping],
        parent_context: ScopeContext,
    ) -> dict[str, tuple[Variable, str, list[str], list[str]]]:
        resolved: dict[str, tuple[Variable, str, list[str], list[str]]] = {}
        for mapping in mappings:
            if mapping.is_source_global:
                continue
            target_name = varname_base(mapping.target)
            if not target_name:
                continue
            if isinstance(mapping.source, dict) and const.KEY_VAR_NAME in mapping.source:
                full_source = mapping.source[const.KEY_VAR_NAME]
            elif isinstance(mapping.source, str):
                full_source = mapping.source
            else:
                continue
            source_var, field_prefix, decl_path, decl_display_path = parent_context.resolve_variable(full_source)
            if source_var is None:
                continue
            resolved[target_name.casefold()] = (
                source_var,
                field_prefix,
                decl_path,
                decl_display_path,
            )
        return resolved

    def _walk_module_code(
        self,
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
        self,
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
        self,
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
        self,
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
        self,
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
        self,
        obj: Any,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> StateMap:
        if hasattr(obj, "data") and obj.data == const.KEY_STATEMENT:
            current_state = state
            for child in getattr(obj, "children", []):
                current_state = self._analyze_stmt_or_expr(child, context, module_path, current_state)
            return current_state

        if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
            return self._analyze_if_statement(obj, context, module_path, state)

        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
            _assign, target, expr = obj
            current_state = state
            self._report_expression_temporal_hazards(expr, context, module_path, current_state)
            value = self._evaluate_expression(expr, context, module_path, current_state)
            return self._write_target(target, value, context, current_state)

        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
            _call, function_name, args = obj
            current_state = state
            for argument in args or []:
                self._report_expression_temporal_hazards(argument, context, module_path, current_state)
                self._evaluate_expression(argument, context, module_path, current_state)
            return self._apply_call_side_effects(function_name, args or [], context, current_state)

        self._report_expression_temporal_hazards(obj, context, module_path, state)
        self._evaluate_expression(obj, context, module_path, state)
        return state

    def _analyze_if_statement(
        self,
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

    def _report_condition(
        self,
        condition: Any,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> bool | None:
        self._report_expression_temporal_hazards(condition, context, module_path, state)
        result = self._evaluate_condition(condition, context, module_path, state)
        condition_text = self._expr_text(condition)
        if result is True:
            self._add_issue(
                kind="dataflow.condition_always_true",
                message=f"Condition {condition_text!r} is always true at this point.",
                module_path=module_path,
                data={"condition": condition_text, "site": self._site_str()},
            )
        elif result is False:
            self._add_issue(
                kind="dataflow.condition_always_false",
                message=f"Condition {condition_text!r} is always false at this point.",
                module_path=module_path,
                data={"condition": condition_text, "site": self._site_str()},
            )
        return result

    def _evaluate_condition(
        self,
        condition: Any,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> bool | None:
        self_compare = self._self_compare_truth(condition, context)
        if self_compare is not None:
            self._add_issue(
                kind="dataflow.self_compare_condition",
                message=(
                    f"Condition {self._expr_text(condition)!r} compares the same symbol on both sides and collapses to {self_compare}."
                ),
                module_path=module_path,
                data={"condition": self._expr_text(condition), "site": self._site_str()},
            )
            return self_compare

        shortcut = self._logical_shortcut_truth(condition, context)
        if shortcut is not None:
            return shortcut

        value = self._evaluate_expression(condition, context, module_path, state)
        if isinstance(value, bool):
            return value
        return None

    def _logical_shortcut_truth(
        self,
        condition: Any,
        context: ScopeContext,
    ) -> bool | None:
        if not (isinstance(condition, tuple) and condition):
            return None

        operator = condition[0]
        if operator == const.GRAMMAR_VALUE_NOT:
            truth = self._logical_shortcut_truth(condition[1], context)
            return None if truth is None else not truth

        if operator in (const.GRAMMAR_VALUE_AND, const.GRAMMAR_VALUE_OR):
            facts = [
                fact
                for fact in (
                    self._condition_fact(part, context)
                    for part in (condition[1] or [])
                )
                if fact is not None
            ]
            if operator == const.GRAMMAR_VALUE_AND:
                return self._facts_contradict(facts)
            return self._facts_form_tautology(facts)

        return None

    def _condition_fact(
        self,
        expr: Any,
        context: ScopeContext,
    ) -> ConditionFact | None:
        if isinstance(expr, dict) and const.KEY_VAR_NAME in expr:
            resolved = self._resolve_ref(expr, context)
            if resolved is None:
                return None
            return ("bool", resolved.key, True)

        if isinstance(expr, tuple) and expr:
            operator = expr[0]
            if operator == const.GRAMMAR_VALUE_NOT:
                inner = self._condition_fact(expr[1], context)
                return self._negate_condition_fact(inner)

            if operator in (const.KEY_COMPARE, "compare"):
                _compare, left_expr, pairs = expr
                if len(pairs or []) != 1:
                    return None
                comparison_operator, right_expr = pairs[0]
                return self._comparison_fact(left_expr, comparison_operator, right_expr, context)

        return None

    def _negate_condition_fact(
        self,
        fact: ConditionFact | None,
    ) -> ConditionFact | None:
        if fact is None:
            return None

        kind, key, payload = fact
        if kind == "bool":
            return (kind, key, not bool(payload))
        if kind == "compare":
            operator, literal = payload
            if operator == "==":
                return (kind, key, ("<>", literal))
            if operator == "<>":
                return (kind, key, ("==", literal))
        return None

    def _comparison_fact(
        self,
        left_expr: Any,
        operator: str,
        right_expr: Any,
        context: ScopeContext,
    ) -> ConditionFact | None:
        left_ref = self._resolve_ref(left_expr, context)
        right_ref = self._resolve_ref(right_expr, context)
        left_literal = self._static_literal(left_expr)
        right_literal = self._static_literal(right_expr)

        if left_ref is not None and right_ref is None and right_literal is not _UNKNOWN:
            return self._fact_from_ref_and_literal(left_ref, operator, right_literal)

        if right_ref is not None and left_ref is None and left_literal is not _UNKNOWN:
            return self._fact_from_ref_and_literal(
                right_ref,
                self._invert_compare_operator(operator),
                left_literal,
            )

        return None

    def _fact_from_ref_and_literal(
        self,
        resolved: _ResolvedRef,
        operator: str,
        literal: ScalarValue | object,
    ) -> ConditionFact | None:
        if literal is _UNKNOWN:
            return None

        if isinstance(literal, bool) and operator in {"==", "<>"}:
            truth = literal if operator == "==" else not literal
            return ("bool", resolved.key, truth)

        if operator in {"==", "<>"}:
            return ("compare", resolved.key, (operator, literal))

        return None

    def _invert_compare_operator(self, operator: str) -> str:
        return {
            "<": ">",
            ">": "<",
            "<=": ">=",
            ">=": "<=",
        }.get(operator, operator)

    def _facts_contradict(self, facts: list[ConditionFact]) -> bool | None:
        if not facts:
            return None

        bool_truths: dict[tuple[str, ...], set[bool]] = {}
        equals: dict[tuple[str, ...], set[ScalarValue]] = {}
        not_equals: dict[tuple[str, ...], set[ScalarValue]] = {}

        for kind, key, payload in facts:
            if kind == "bool":
                bool_truths.setdefault(key, set()).add(bool(payload))
                continue

            if kind == "compare":
                operator, literal = payload
                if operator == "==":
                    equals.setdefault(key, set()).add(literal)
                elif operator == "<>":
                    not_equals.setdefault(key, set()).add(literal)

        if any(len(values) > 1 for values in bool_truths.values()):
            return False

        for key, equal_values in equals.items():
            if len(equal_values) > 1:
                return False
            if any(value in not_equals.get(key, set()) for value in equal_values):
                return False

        return None

    def _facts_form_tautology(self, facts: list[ConditionFact]) -> bool | None:
        if not facts:
            return None

        bool_truths: dict[tuple[str, ...], set[bool]] = {}
        equals: dict[tuple[str, ...], set[ScalarValue]] = {}
        not_equals: dict[tuple[str, ...], set[ScalarValue]] = {}

        for kind, key, payload in facts:
            if kind == "bool":
                bool_truths.setdefault(key, set()).add(bool(payload))
                continue

            if kind == "compare":
                operator, literal = payload
                if operator == "==":
                    equals.setdefault(key, set()).add(literal)
                elif operator == "<>":
                    not_equals.setdefault(key, set()).add(literal)

        if any(len(values) > 1 for values in bool_truths.values()):
            return True

        for key, equal_values in equals.items():
            if any(value in not_equals.get(key, set()) for value in equal_values):
                return True

        return None

    def _self_compare_truth(
        self,
        condition: Any,
        context: ScopeContext,
    ) -> bool | None:
        if not (isinstance(condition, tuple) and condition and condition[0] in (const.KEY_COMPARE, "compare")):
            return None
        _compare, left, pairs = condition
        if len(pairs or []) != 1:
            return None
        operator, right = pairs[0]
        left_ref = self._resolve_ref(left, context)
        right_ref = self._resolve_ref(right, context)
        if left_ref is None or right_ref is None or left_ref.key != right_ref.key:
            return None
        if operator in ("==", "<=", ">="):
            return True
        if operator in ("<>", "<", ">"):
            return False
        return None

    def _evaluate_expression(
        self,
        expr: Any,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> ScalarValue | object:
        if hasattr(expr, "data") and expr.data == const.KEY_STATEMENT:
            children = getattr(expr, "children", [])
            if children:
                return self._evaluate_expression(children[0], context, module_path, state)
            return _UNKNOWN

        if isinstance(expr, IntLiteral):
            return int(expr)
        if isinstance(expr, FloatLiteral):
            return float(expr)
        if isinstance(expr, bool):
            return expr
        if isinstance(expr, int):
            return expr
        if isinstance(expr, float):
            return expr
        if isinstance(expr, str):
            return expr

        if isinstance(expr, dict) and const.KEY_VAR_NAME in expr:
            resolved = self._resolve_ref(expr, context)
            if resolved is None:
                return _UNKNOWN
            return self._read_resolved_value(resolved, module_path, state)

        if isinstance(expr, tuple) and expr:
            operator = expr[0]

            if operator in (const.KEY_TERNARY, "Ternary"):
                _ternary, branches, else_expr = expr
                branch_values: list[ScalarValue | object] = []
                fallthrough_state = state
                for condition, branch_expr in branches or []:
                    condition_value = self._report_condition(condition, context, module_path, fallthrough_state)
                    if condition_value is False:
                        fallthrough_state = self._assume(condition, False, fallthrough_state, context, module_path)
                        continue
                    true_state = self._assume(condition, True, fallthrough_state, context, module_path)
                    branch_values.append(self._evaluate_expression(branch_expr, context, module_path, true_state))
                    if condition_value is True:
                        return branch_values[-1]
                    fallthrough_state = self._assume(condition, False, fallthrough_state, context, module_path)
                if else_expr is not None:
                    branch_values.append(self._evaluate_expression(else_expr, context, module_path, fallthrough_state))
                return self._coalesce_values(branch_values)

            if operator == const.KEY_FUNCTION_CALL:
                _call, _name, args = expr
                for argument in args or []:
                    self._evaluate_expression(argument, context, module_path, state)
                return _UNKNOWN

            if operator in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND):
                values = [self._evaluate_expression(item, context, module_path, state) for item in expr[1] or []]
                if operator == const.GRAMMAR_VALUE_OR:
                    if any(value is True for value in values):
                        return True
                    if all(value is False for value in values):
                        return False
                else:
                    if any(value is False for value in values):
                        return False
                    if values and all(value is True for value in values):
                        return True
                return _UNKNOWN

            if operator == const.GRAMMAR_VALUE_NOT:
                value = self._evaluate_expression(expr[1], context, module_path, state)
                return (not value) if isinstance(value, bool) else _UNKNOWN

            if operator in (const.KEY_COMPARE, "compare"):
                _compare, left, pairs = expr
                left_value = self._evaluate_expression(left, context, module_path, state)
                if not _is_scalar_value(left_value):
                    return _UNKNOWN
                scalar_left = cast(ScalarValue, left_value)
                results: list[bool] = []
                for symbol, right_expr in pairs or []:
                    right_value = self._evaluate_expression(right_expr, context, module_path, state)
                    if not _is_scalar_value(right_value):
                        return _UNKNOWN
                    scalar_right = cast(ScalarValue, right_value)
                    comparison = self._compare_values(scalar_left, symbol, scalar_right)
                    if comparison is None:
                        return _UNKNOWN
                    results.append(comparison)
                return all(results)

            if operator in (const.KEY_ADD, const.KEY_MUL):
                _tag, left, parts = expr
                value = self._evaluate_expression(left, context, module_path, state)
                if not _is_scalar_value(value):
                    return _UNKNOWN
                scalar_value = cast(ScalarValue, value)
                for symbol, right_expr in parts or []:
                    right_value = self._evaluate_expression(right_expr, context, module_path, state)
                    if not _is_scalar_value(right_value):
                        return _UNKNOWN
                    scalar_right = cast(ScalarValue, right_value)
                    value = self._apply_arithmetic(symbol, scalar_value, scalar_right)
                    if not _is_scalar_value(value):
                        return _UNKNOWN
                    scalar_value = cast(ScalarValue, value)
                return scalar_value

            if operator in (const.KEY_PLUS, const.KEY_MINUS):
                inner = self._evaluate_expression(expr[1], context, module_path, state)
                if not isinstance(inner, (int, float)) or isinstance(inner, bool):
                    return _UNKNOWN
                return inner if operator == const.KEY_PLUS else -inner

        return _UNKNOWN

    def _apply_call_side_effects(
        self,
        function_name: str | None,
        args: list[Any],
        context: ScopeContext,
        state: StateMap,
    ) -> StateMap:
        if not function_name:
            return state

        signature = get_function_signature(function_name)
        if signature is None:
            return state

        next_state = state.copy()
        for index, argument in enumerate(args):
            direction = "in"
            if index < len(signature.parameters):
                direction = signature.parameters[index].direction
            if direction not in {"out", "inout"}:
                continue
            resolved = self._resolve_ref(argument, context)
            if resolved is None:
                continue
            if resolved.state_access == "old":
                self._report_invalid_old_write(
                    resolved,
                    context.module_path,
                    operation=f"{direction} parameter",
                )
                continue
            next_state = self._apply_write_target(
                resolved,
                _UNKNOWN,
                next_state,
                module_path=context.module_path,
                treat_as_root_overwrite=True,
            )
        return next_state

    def _write_target(
        self,
        target: Any,
        value: ScalarValue | object,
        context: ScopeContext,
        state: StateMap,
    ) -> StateMap:
        resolved = self._resolve_ref(target, context)
        if resolved is None:
            return state

        return self._apply_write_target(
            resolved,
            value,
            state,
            module_path=context.module_path,
        )

    def _read_resolved_value(
        self,
        resolved: _ResolvedRef,
        module_path: list[str],
        state: StateMap,
    ) -> ScalarValue | object:
        if resolved.state_access != "old":
            self._consume_pending_reads(state, resolved.symbol_root_key)
        value = state.get(resolved.key, _UNKNOWN)
        if value is _UNKNOWN and resolved.key != resolved.root_key:
            value = state.get(resolved.root_key, _UNKNOWN)

        if value is _UNKNOWN:
            self._report_read_before_write(resolved, module_path)
            return _UNKNOWN

        if value is _INITIALIZED:
            return _UNKNOWN

        return value

    def _report_read_before_write(
        self,
        resolved: _ResolvedRef,
        module_path: list[str],
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, resolved.display_name.casefold())
        if dedupe_key in self._reported_read_before_write:
            return
        self._reported_read_before_write.add(dedupe_key)
        self._add_issue(
            kind="dataflow.read_before_write",
            message=(
                f"Variable reference {resolved.display_name!r} may be read before it is assigned on this path."
            ),
            module_path=module_path,
            data={
                "symbol": resolved.display_name,
                "site": site,
            },
        )

    def _report_dead_overwrite(
        self,
        pending: _PendingWrite,
        resolved: _ResolvedRef,
        module_path: list[str],
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, pending.display_name.casefold())
        if dedupe_key in self._reported_dead_overwrite:
            return
        self._reported_dead_overwrite.add(dedupe_key)
        self._add_issue(
            kind="dataflow.dead_overwrite",
            message=(
                f"Variable reference {pending.display_name!r} is overwritten before its previous value is read."
            ),
            module_path=module_path,
            data={
                "symbol": pending.display_name,
                "site": site,
                "previous_sites": list(pending.sites),
                "overwrite_symbol": resolved.display_name,
            },
        )

    def _report_scan_cycle_stale_read(
        self,
        resolved: _ResolvedRef,
        module_path: list[str],
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, resolved.display_name.casefold())
        if dedupe_key in self._reported_scan_cycle_stale_read:
            return
        self._reported_scan_cycle_stale_read.add(dedupe_key)
        self._add_issue(
            kind="dataflow.scan_cycle_stale_read",
            message=(
                f"State reference {resolved.display_name!r} is read after {resolved.base_display_name!r} "
                "was already written earlier in the same scan; :OLD still refers to the previous scan value."
            ),
            module_path=module_path,
            data={
                "symbol": resolved.display_name,
                "state_symbol": resolved.base_display_name,
                "site": site,
            },
        )

    def _report_scan_cycle_implicit_new(
        self,
        resolved: _ResolvedRef,
        module_path: list[str],
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, resolved.display_name.casefold())
        if dedupe_key in self._reported_scan_cycle_implicit_new:
            return
        self._reported_scan_cycle_implicit_new.add(dedupe_key)
        self._add_issue(
            kind="dataflow.scan_cycle_implicit_new",
            message=(
                f"State reference {resolved.display_name!r} is read after {resolved.base_display_name!r} "
                "was already written earlier in the same scan; use :NEW to make the immediate-update dependency explicit."
            ),
            module_path=module_path,
            data={
                "symbol": resolved.display_name,
                "state_symbol": resolved.base_display_name,
                "site": site,
            },
        )

    def _report_invalid_old_write(
        self,
        resolved: _ResolvedRef,
        module_path: list[str],
        *,
        operation: str,
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, resolved.display_name.casefold(), operation)
        if dedupe_key in self._reported_scan_cycle_temporal_misuse:
            return
        self._reported_scan_cycle_temporal_misuse.add(dedupe_key)
        self._add_issue(
            kind="dataflow.scan_cycle_temporal_misuse",
            message=(
                f"State reference {resolved.display_name!r} cannot be written via {operation}; "
                ":OLD is read-only and always refers to the previous scan."
            ),
            module_path=module_path,
            data={
                "symbol": resolved.display_name,
                "state_symbol": resolved.base_display_name,
                "operation": operation,
                "site": site,
            },
        )

    def _report_expression_temporal_hazards(
        self,
        expr: Any,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> None:
        accesses = self._collect_stateful_refs(expr, context)
        if not accesses:
            return

        grouped: dict[tuple[str, ...], dict[str, list[_ResolvedRef]]] = {}
        for resolved in accesses:
            group = grouped.setdefault(
                resolved.symbol_key,
                {"old": [], "explicit_new": [], "implicit_current": []},
            )
            if resolved.state_access == "old":
                group["old"].append(resolved)
            elif resolved.state_access == "new":
                group["explicit_new"].append(resolved)
            else:
                group["implicit_current"].append(resolved)

        for group in grouped.values():
            sample = next(
                iter(group["old"] or group["explicit_new"] or group["implicit_current"]),
                None,
            )
            if sample is None:
                continue
            if not self._has_pending_write_for_symbol(state, sample):
                continue
            for resolved in group["implicit_current"]:
                self._report_scan_cycle_implicit_new(resolved, module_path)
            if group["old"] and not group["explicit_new"] and not group["implicit_current"]:
                for resolved in group["old"]:
                    self._report_scan_cycle_stale_read(resolved, module_path)

    def _collect_stateful_refs(
        self,
        expr: Any,
        context: ScopeContext,
    ) -> list[_ResolvedRef]:
        collected: list[_ResolvedRef] = []

        def visit(node: Any) -> None:
            if isinstance(node, dict) and const.KEY_VAR_NAME in node:
                resolved = self._resolve_ref(node, context)
                if resolved is not None and resolved.is_state_variable:
                    collected.append(resolved)
                return

            if hasattr(node, "data") and node.data == const.KEY_STATEMENT:  # type: ignore[reportAttributeAccessIssue]
                for child in getattr(node, "children", []):  # type: ignore[reportAttributeAccessIssue]
                    visit(child)
                return

            if isinstance(node, tuple):
                for item in node:
                    visit(item)
                return

            if isinstance(node, list):
                for item in node:
                    visit(item)
                return

            if hasattr(node, "children"):
                for child in getattr(node, "children", []):
                    visit(child)

        visit(expr)
        return collected

    def _apply_write_target(
        self,
        resolved: _ResolvedRef,
        value: ScalarValue | object,
        state: StateMap,
        *,
        module_path: list[str],
        treat_as_root_overwrite: bool = False,
    ) -> StateMap:
        if resolved.state_access == "old":
            self._report_invalid_old_write(resolved, module_path, operation="assignment target")
            return state

        next_state = state.copy()
        whole_symbol_write = treat_as_root_overwrite or resolved.symbol_key == resolved.symbol_root_key

        if whole_symbol_write:
            overwritten = self._pop_pending_writes_for_root(next_state, resolved.symbol_root_key)
            for pending in overwritten:
                self._report_dead_overwrite(pending, resolved, module_path)
        else:
            next_state.pop(self._pending_state_key(resolved.symbol_root_key), None)
            pending_key = self._pending_state_key(resolved.symbol_key)
            pending_write = next_state.pop(pending_key, None)
            if isinstance(pending_write, _PendingWrite):
                self._report_dead_overwrite(pending_write, resolved, module_path)

        next_state = self._invalidate_symbol(next_state, resolved.symbol_root_key)
        next_state[resolved.symbol_key] = _INITIALIZED if value is _UNKNOWN else value
        next_state[self._pending_state_key(resolved.symbol_key)] = _PendingWrite(
            key=resolved.symbol_key,
            root_key=resolved.symbol_root_key,
            display_name=resolved.base_display_name,
            sites=(self._site_str(),),
        )
        return next_state

    def _has_pending_write_for_symbol(
        self,
        state: StateMap,
        resolved: _ResolvedRef,
    ) -> bool:
        for pending in state.values():
            if not isinstance(pending, _PendingWrite):
                continue
            if pending.root_key != resolved.symbol_root_key:
                continue
            if pending.key in {resolved.symbol_key, resolved.symbol_root_key}:
                return True
        return False

    def _consume_pending_reads(
        self,
        state: StateMap,
        root_key: tuple[str, ...],
    ) -> None:
        for pending_key in [
            key
            for key, pending in state.items()
            if self._is_pending_state_key(key)
            and isinstance(pending, _PendingWrite)
            and pending.root_key == root_key
        ]:
            state.pop(pending_key, None)

    def _pop_pending_writes_for_root(
        self,
        state: StateMap,
        root_key: tuple[str, ...],
    ) -> list[_PendingWrite]:
        popped: list[_PendingWrite] = []
        for pending_key in [
            key
            for key, pending in state.items()
            if self._is_pending_state_key(key)
            and isinstance(pending, _PendingWrite)
            and pending.root_key == root_key
        ]:
            pending = state.pop(pending_key, None)
            if isinstance(pending, _PendingWrite):
                popped.append(pending)
        return popped

    def _assume(
        self,
        condition: Any,
        truth: bool,
        state: StateMap,
        context: ScopeContext,
        module_path: list[str],
    ) -> StateMap:
        next_state = state.copy()

        if hasattr(condition, "data") and condition.data == const.KEY_STATEMENT:
            children = getattr(condition, "children", [])
            if children:
                return self._assume(children[0], truth, next_state, context, module_path)
            return next_state

        if isinstance(condition, dict) and const.KEY_VAR_NAME in condition:
            resolved = self._resolve_ref(condition, context)
            if resolved is not None:
                next_state[resolved.key] = truth
            return next_state

        if isinstance(condition, tuple) and condition:
            operator = condition[0]
            if operator == const.GRAMMAR_VALUE_NOT:
                return self._assume(condition[1], not truth, next_state, context, module_path)
            if operator == const.GRAMMAR_VALUE_AND and truth:
                for part in condition[1] or []:
                    next_state = self._assume(part, True, next_state, context, module_path)
                return next_state
            if operator == const.GRAMMAR_VALUE_OR and not truth:
                for part in condition[1] or []:
                    next_state = self._assume(part, False, next_state, context, module_path)
                return next_state
            if operator in (const.KEY_COMPARE, "compare"):
                assumed = self._assume_compare(condition, truth, next_state, context, module_path)
                if assumed is not None:
                    return assumed

        return next_state

    def _assume_compare(
        self,
        condition: tuple[Any, ...],
        truth: bool,
        state: StateMap,
        context: ScopeContext,
        module_path: list[str],
    ) -> StateMap | None:
        _compare, left_expr, pairs = condition
        if len(pairs or []) != 1:
            return None
        operator, right_expr = pairs[0]

        resolved_left = self._resolve_ref(left_expr, context)
        resolved_right = self._resolve_ref(right_expr, context)
        left_value = self._evaluate_expression(left_expr, context, module_path, state)
        right_value = self._evaluate_expression(right_expr, context, module_path, state)

        if resolved_left is not None and right_value is not _UNKNOWN:
            if (truth and operator == "==") or (not truth and operator == "<>"):
                next_state = self._invalidate_symbol(state.copy(), resolved_left.key)
                next_state[resolved_left.key] = right_value
                return next_state

        if resolved_right is not None and left_value is not _UNKNOWN:
            if (truth and operator == "==") or (not truth and operator == "<>"):
                next_state = self._invalidate_symbol(state.copy(), resolved_right.key)
                next_state[resolved_right.key] = left_value
                return next_state

        return None

    def _resolve_ref(self, expr: Any, context: ScopeContext) -> _ResolvedRef | None:
        if not (isinstance(expr, dict) and const.KEY_VAR_NAME in expr):
            return None
        full_name = expr[const.KEY_VAR_NAME]
        variable, field_path, decl_path, _decl_display_path = context.resolve_variable(full_name)
        if variable is None:
            return None
        state_access = expr.get("state") if isinstance(expr.get("state"), str) else None
        symbol_key = self._state_key(decl_path, variable.name, field_path)
        symbol_root_key = self._state_key(decl_path, variable.name, "")
        key = symbol_key
        root_key = symbol_root_key
        if state_access == "old":
            key = self._old_state_key(symbol_key)
            root_key = self._old_state_key(symbol_root_key)
        display_name = full_name if not state_access else f"{full_name}:{state_access.title()}"
        return _ResolvedRef(
            key=key,
            root_key=root_key,
            symbol_key=symbol_key,
            symbol_root_key=symbol_root_key,
            display_name=display_name,
            base_display_name=full_name,
            state_access=state_access,
            is_state_variable=bool(variable.state),
        )

    def _seed_state(
        self,
        state: StateMap,
        module_path: list[str],
        variables: list[Variable],
    ) -> StateMap:
        next_state = state.copy()
        for variable in variables:
            current_key = self._state_key(module_path, variable.name, "")
            old_key = self._old_state_key(current_key)
            value = self._static_literal(variable.init_value)
            if value is _UNKNOWN:
                if variable.init_value is None:
                    continue
                next_state[current_key] = _INITIALIZED
                next_state[old_key] = _INITIALIZED
                continue
            next_state[current_key] = value
            next_state[old_key] = value
        return next_state

    def _invalidate_symbol(
        self,
        state: StateMap,
        key: tuple[str, ...],
    ) -> StateMap:
        next_state = state.copy()
        prefixes = [existing for existing in next_state if existing[: len(key)] == key]
        for existing in prefixes:
            next_state.pop(existing, None)
        return next_state

    def _merge_states(self, states: list[StateMap]) -> StateMap:
        if not states:
            return {}
        merged: StateMap = {}
        value_keys: set[tuple[str, ...]] = set().union(
            *(
                {
                    key
                    for key in state
                    if not self._is_pending_state_key(key)
                }
                for state in states
            )
        )
        pending_keys_per_state = [
            {
                key
                for key in state
                if self._is_pending_state_key(key)
            }
            for state in states
        ]
        for key in value_keys:
            values = [state.get(key, _UNKNOWN) for state in states]
            first = values[0]
            if first is _UNKNOWN:
                continue
            if all(value == first for value in values[1:]):
                merged[key] = first
                continue
            if all(value is not _UNKNOWN for value in values):
                merged[key] = _INITIALIZED

        common_pending_keys = set.intersection(*pending_keys_per_state) if pending_keys_per_state else set()
        for pending_key in common_pending_keys:
            pending_values = [state.get(pending_key) for state in states]
            if not all(isinstance(value, _PendingWrite) for value in pending_values):
                continue
            first_pending = cast(_PendingWrite, pending_values[0])
            merged[pending_key] = _PendingWrite(
                key=first_pending.key,
                root_key=first_pending.root_key,
                display_name=first_pending.display_name,
                sites=tuple(
                    sorted(
                        {
                            site
                            for value in pending_values
                            if isinstance(value, _PendingWrite)
                            for site in value.sites
                        }
                    )
                ),
            )
        return merged

    def _coalesce_values(self, values: list[ScalarValue | object]) -> ScalarValue | object:
        known = [value for value in values if value is not _UNKNOWN]
        if not known:
            return _UNKNOWN
        first = known[0]
        if all(value == first for value in known[1:]) and len(known) == len(values):
            return first
        return _UNKNOWN

    def _compare_values(self, left: ScalarValue, operator: str, right: ScalarValue) -> bool | None:
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

    def _apply_arithmetic(
        self,
        operator: str,
        left: ScalarValue,
        right: ScalarValue,
    ) -> ScalarValue | object:
        if isinstance(left, bool) or isinstance(right, bool):
            return _UNKNOWN
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            return _UNKNOWN
        if operator == "+":
            return left + right
        if operator == "-":
            return left - right
        if operator == "*":
            return left * right
        if operator == "/":
            if right == 0:
                return _UNKNOWN
            return left / right
        return _UNKNOWN

    def _static_literal(self, value: Any) -> ScalarValue | object:
        if isinstance(value, IntLiteral):
            return int(value)
        if isinstance(value, FloatLiteral):
            return float(value)
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return value
        if isinstance(value, str):
            return value
        return _UNKNOWN

    def _state_key(
        self,
        module_path: list[str],
        variable_name: str,
        field_path: str,
    ) -> tuple[str, ...]:
        segments = [segment.casefold() for segment in module_path]
        segments.append(variable_name.casefold())
        if field_path:
            segments.extend(segment.casefold() for segment in field_path.split(".") if segment)
        return tuple(segments)

    def _old_state_key(self, key: tuple[str, ...]) -> tuple[str, ...]:
        return _OLD_PREFIX + key

    def _pending_state_key(self, key: tuple[str, ...]) -> tuple[str, ...]:
        return _PENDING_PREFIX + key

    def _is_pending_state_key(self, key: tuple[str, ...]) -> bool:
        return key[: len(_PENDING_PREFIX)] == _PENDING_PREFIX

    def _expr_text(self, expr: Any) -> str:
        return format_expr(expr).replace("\n", " ").strip()

    def _sequence_node_label(self, node: object) -> str:
        if hasattr(node, "name") and getattr(node, "name", None):  # type: ignore[reportAttributeAccessIssue]
            return f"{type(node).__name__}:{node.name}"  # type: ignore[reportAttributeAccessIssue]
        if isinstance(node, SFCFork):
            return f"SFCFork:{node.target}"
        return type(node).__name__

    def _is_from_root_origin(self, origin_file: str | None) -> bool:
        if not origin_file:
            return True
        root_origin = getattr(self.bp, "origin_file", None)
        if not root_origin:
            return False
        return origin_file.rsplit(".", 1)[0].casefold() == root_origin.rsplit(".", 1)[0].casefold()

    def _site_str(self) -> str:
        return " > ".join(self._site_stack)

    def _push_site(self, label: str) -> None:
        if label:
            self._site_stack.append(label)

    def _pop_site(self) -> None:
        if self._site_stack:
            self._site_stack.pop()

    def _add_issue(
        self,
        *,
        kind: str,
        message: str,
        module_path: list[str],
        data: dict[str, Any] | None = None,
    ) -> None:
        self._issues.append(
            Issue(
                kind=kind,
                message=message,
                module_path=module_path.copy(),
                data=data or None,
            )
        )


def analyze_dataflow(
    base_picture: BasePicture,
    *,
    unavailable_libraries: set[str] | None = None,
) -> SimpleReport:
    analyzer = DataflowAnalyzer(
        base_picture,
        unavailable_libraries=unavailable_libraries,
    )
    return SimpleReport(name=base_picture.header.name, issues=analyzer.run())
