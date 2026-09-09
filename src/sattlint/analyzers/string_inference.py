"""Exact string inference engine with cursor-aware builtin semantics.

Builds a module-scope context tree and solves exact string candidate values
(plus the cursor positions that drive builtin writes) via fixed-point
iteration. Cursor-aware builtin semantics live in `_string_operations.py`;
the shared value/state models live in `_string_models.py`.
"""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnnecessaryIsInstance=false, reportPrivateUsage=false

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import (
    Assignment,
    BinOp,
    FuncCall,
    FuncCallStmt,
    IfStmt,
    TernaryOp,
    UnaryOp,
    VarRef,
)

from ..resolution.common import select_moduletype_def_strict, varname_base, varname_full
from ..resolution.scope import ScopeContext
from ..validation.type_helpers import is_string_simple_type
from ._string_models import (
    _MAX_CONTEXT_BUILD_DEPTH,
    _MAX_FIXED_POINT_PASSES,
    _STRING_LIMITS,
    StringCandidate,
    StringInferenceResult,
    StringProvenanceSegment,
    _AbstractState,
    _IntResult,
    _LiteralBinding,
    _ModuleContext,
    _noop_progress,
    _ResolvedSlot,
    _SlotKey,
    _string_capacity_for_datatype,
)
from ._string_operations import (
    _apply_int_operator,
    _concatenate_results,
    _copy_into_target,
    _cut_string_result,
    _extract_string_result,
    _insert_string_result,
    _merge_int_results,
    _merge_state_into,
    _merge_string_results,
    _normalize_int_result,
    _put_blanks_result,
    _read_string_result,
    _result_for_literal,
    _retarget_string_result,
    _set_cursor_positions,
    _transform_string_result,
    _unknown_string_result,
    _with_end_cursor,
)

if TYPE_CHECKING:
    from ..models.project_graph import ProjectGraph

__all__ = ["ExactStringInferenceEngine", "StringCandidate", "StringInferenceResult", "StringProvenanceSegment"]


log = logging.getLogger("SattLint")


class ExactStringInferenceEngine:
    """Infers exact string candidates and cursor positions for module-scoped refs."""

    def __init__(
        self,
        base_picture: BasePicture,
        *,
        graph: ProjectGraph | None = None,
        progress_callback: Callable[[str], None] | None = None,
        debug: bool = False,
    ):
        self.base_picture = base_picture
        self.graph = graph
        self.debug = debug
        self._context_build_depth = 0
        self._context_build_limit_reported = False
        self._progress_callback: Callable[[str], None] = (
            progress_callback if progress_callback is not None else _noop_progress
        )
        self._moduletype_index = _candidate_moduletype_index(base_picture, graph)
        self._contexts_by_path: dict[tuple[str, ...], _ModuleContext] = {}
        self._execution_contexts: list[_ModuleContext] = []
        if self.debug:
            log.debug(
                "string-inference: building module context tree for root=%s (typedefs=%d)",
                base_picture.header.name,
                len(base_picture.moduletype_defs or []),
            )
        self._root_context = self._build_basepicture_context()
        self._collect_contexts(self._root_context)
        for moduletype in self.base_picture.moduletype_defs or []:
            self._collect_contexts(self._build_typedef_root_context(moduletype))
        if self.debug:
            log.debug(
                "string-inference: context tree built; %d contexts, %d executable",
                len(self._contexts_by_path),
                len(self._execution_contexts),
            )
        self._initial_state = self._build_initial_state()
        self._solved_state: _AbstractState | None = None

    def infer(self, reference: str, *, module_path: tuple[str, ...] | list[str]) -> StringInferenceResult:
        self._ensure_solved()
        context = self._contexts_by_path.get(tuple(segment.casefold() for segment in module_path))
        if context is None:
            return StringInferenceResult()
        resolved = _resolve_slot(context.scope, reference)
        if resolved is None or self._solved_state is None:
            return StringInferenceResult()
        return self._solved_state.string_values.get(
            resolved.key,
            _unknown_string_result(max_length=_string_capacity_for_datatype(resolved.variable.datatype)),
        )

    def _ensure_solved(self) -> None:
        if self._solved_state is not None:
            return
        state = self._initial_state.clone()
        for pass_idx in range(_MAX_FIXED_POINT_PASSES):
            self._progress_callback(f"resolving string values: pass {pass_idx + 1}/{_MAX_FIXED_POINT_PASSES}")
            next_state = state.clone()
            written_string_keys: set[_SlotKey] = set()
            written_int_keys: set[_SlotKey] = set()
            for context in self._execution_contexts:
                updates = self._execute_module_context(context, state)
                for key, value in updates.string_values.items():
                    if key in written_string_keys:
                        next_state.string_values[key] = _merge_string_results(next_state.string_values[key], value)
                    else:
                        next_state.string_values[key] = value
                        written_string_keys.add(key)
                for key, value in updates.int_values.items():
                    if key in written_int_keys:
                        next_state.int_values[key] = _merge_int_results(next_state.int_values[key], value)
                    else:
                        next_state.int_values[key] = value
                        written_int_keys.add(key)
            if next_state == state:
                self._solved_state = next_state
                return
            state = next_state
        self._solved_state = state

    def _build_basepicture_context(self) -> _ModuleContext:
        root_scope = ScopeContext(
            env={variable.name.casefold(): variable for variable in self.base_picture.localvariables or []},
            param_mappings={},
            module_path=[self.base_picture.header.name],
            display_module_path=[self.base_picture.header.name],
            current_library=getattr(self.base_picture, "origin_lib", None),
            parent_context=None,
        )
        root = _ModuleContext(
            path=(self.base_picture.header.name,),
            scope=root_scope,
            node=self.base_picture,
            literal_bindings=(),
        )
        root.children = tuple(self._build_child_context(root, child) for child in self.base_picture.submodules or [])
        return root

    def _build_typedef_root_context(self, moduletype: ModuleTypeDef) -> _ModuleContext:
        typedef_path = (self.base_picture.header.name, f"TypeDef:{moduletype.name}")
        env = {
            variable.name.casefold(): variable
            for variable in [*(moduletype.moduleparameters or []), *(moduletype.localvariables or [])]
        }
        param_keys = {variable.name.casefold() for variable in moduletype.moduleparameters or []}
        scope = ScopeContext(
            env=env,
            param_mappings={},
            module_path=list(typedef_path),
            display_module_path=list(typedef_path),
            moduleparameter_keys=frozenset(param_keys),
            current_library=moduletype.origin_lib or getattr(self.base_picture, "origin_lib", None),
            parent_context=self._root_context.scope,
        )
        context = _ModuleContext(
            path=typedef_path,
            scope=scope,
            node=moduletype,
            literal_bindings=(),
        )
        context.children = tuple(self._build_child_context(context, child) for child in moduletype.submodules or [])
        return context

    def _build_child_context(
        self,
        parent: _ModuleContext,
        child: SingleModule | FrameModule | ModuleTypeInstance,
    ) -> _ModuleContext:
        child_path = (*parent.path, child.header.name)
        if isinstance(child, SingleModule):
            scope = _build_single_scope(child, parent.scope, child_path)
            context = _ModuleContext(
                path=child_path,
                scope=scope,
                node=child,
                literal_bindings=_literal_bindings_for_mappings(child.parametermappings, "parameter_mapping_literal"),
            )
            context.children = tuple(
                self._build_child_context(context, grandchild) for grandchild in child.submodules or []
            )
            return context

        if isinstance(child, FrameModule):
            scope = ScopeContext(
                env={},
                param_mappings={},
                module_path=list(child_path),
                display_module_path=list(child_path),
                current_library=parent.scope.current_library,
                parent_context=parent.scope,
            )
            context = _ModuleContext(path=child_path, scope=scope, node=child, literal_bindings=())
            context.children = tuple(
                self._build_child_context(context, grandchild) for grandchild in child.submodules or []
            )
            return context

        resolved_typedef = _resolve_typedef_for_instance(
            self.base_picture,
            child,
            parent.scope.current_library,
            self._moduletype_index,
        )
        if resolved_typedef is None:
            scope = ScopeContext(
                env={},
                param_mappings={},
                module_path=list(child_path),
                display_module_path=list(child_path),
                current_library=parent.scope.current_library,
                parent_context=parent.scope,
            )
            return _ModuleContext(path=child_path, scope=scope, node=child, literal_bindings=())

        scope = _build_typedef_scope(resolved_typedef, child, parent.scope, child_path)
        self._context_build_depth += 1
        if self.debug:
            log.debug(
                "string-inference: expanding moduletype=%s into %s (depth=%d)",
                resolved_typedef.name,
                ".".join(child_path),
                self._context_build_depth,
            )

        if self._context_build_depth > _MAX_CONTEXT_BUILD_DEPTH:
            if not self._context_build_limit_reported:
                log.warning(
                    "string-inference: typedef expansion deeper than %d at %s; "
                    "possible recursive module-type instantiation (moduletype=%s) - "
                    "stopping expansion",
                    _MAX_CONTEXT_BUILD_DEPTH,
                    ".".join(child_path),
                    resolved_typedef.name,
                )
                self._context_build_limit_reported = True
            self._context_build_depth -= 1
            return _ModuleContext(
                path=child_path,
                scope=scope,
                node=resolved_typedef,
                literal_bindings=_literal_bindings_for_mappings(child.parametermappings, "parameter_mapping_literal"),
            )

        context = _ModuleContext(
            path=child_path,
            scope=scope,
            node=resolved_typedef,
            literal_bindings=_literal_bindings_for_mappings(child.parametermappings, "parameter_mapping_literal"),
        )
        context.children = tuple(
            self._build_child_context(context, grandchild) for grandchild in resolved_typedef.submodules or []
        )
        self._context_build_depth -= 1
        return context

    def _collect_contexts(self, context: _ModuleContext) -> None:
        self._contexts_by_path[tuple(segment.casefold() for segment in context.path)] = context
        if _module_code(context.node) is not None:
            self._execution_contexts.append(context)
        for child in context.children:
            self._collect_contexts(child)

    def _build_initial_state(self) -> _AbstractState:
        state = _AbstractState()
        for context in self._contexts_by_path.values():
            alias_keys = frozenset(context.scope.param_mappings.keys())
            for variable in _declared_variables(context.node):
                if variable.name.casefold() in alias_keys:
                    continue
                slot_key = _declaration_slot(context.path, variable.name)
                init_value = getattr(variable, "init_value", None)
                if isinstance(init_value, str) and is_string_simple_type(variable.datatype):
                    state.string_values[slot_key] = _result_for_literal(
                        init_value,
                        source_kind="initializer",
                        source_label=variable.name,
                        source_module_path=context.path,
                        max_length=_string_capacity_for_datatype(variable.datatype),
                    )
                elif isinstance(init_value, int) and variable.datatype is Simple_DataType.INTEGER:
                    state.int_values[slot_key] = _normalize_int_result(_IntResult((init_value,), False))

            for binding in context.literal_bindings:
                target_key = _local_slot_key(context.path, binding.target_ref)
                if target_key is None:
                    continue
                if isinstance(binding.source_literal, str):
                    state.string_values[target_key] = _result_for_literal(
                        binding.source_literal,
                        source_kind=binding.source_kind,
                        source_label=repr(binding.source_literal),
                        source_module_path=context.path,
                        max_length=_STRING_LIMITS[Simple_DataType.MAXSTRING],
                    )
                elif isinstance(binding.source_literal, int):
                    state.int_values[target_key] = _normalize_int_result(_IntResult((binding.source_literal,), False))
        return state

    def _execute_module_context(self, context: _ModuleContext, state: _AbstractState) -> _AbstractState:
        local_state = state.clone()
        for code_block in _module_code_blocks(context.node):
            local_state = self._execute_statement_list(code_block, local_state, context.scope)
        changed_strings = {
            key: value for key, value in local_state.string_values.items() if state.string_values.get(key) != value
        }
        changed_ints = {
            key: value for key, value in local_state.int_values.items() if state.int_values.get(key) != value
        }
        return _AbstractState(string_values=changed_strings, int_values=changed_ints)

    def _execute_statement_list(
        self,
        statements: list[object] | tuple[object, ...],
        state: _AbstractState,
        scope: ScopeContext,
    ) -> _AbstractState:
        current = state
        for statement in statements:
            current = self._execute_statement(statement, current, scope)
        return current

    def _execute_statement(self, statement: object, state: _AbstractState, scope: ScopeContext) -> _AbstractState:
        if isinstance(statement, list):
            return self._execute_statement_list(statement, state, scope)
        if isinstance(statement, Assignment):
            return self._execute_assignment(statement.target, statement.value, state, scope)

        if isinstance(statement, FuncCallStmt):
            return self._execute_builtin_call(
                statement.call.name,
                list(statement.call.args),
                state,
                scope,
            )

        if isinstance(statement, IfStmt):
            branch_states: list[_AbstractState] = []
            for _condition, branch_body in statement.branches:
                branch_states.append(self._execute_statement_list(list(branch_body), state.clone(), scope))
            if statement.else_block:
                branch_states.append(self._execute_statement_list(list(statement.else_block), state.clone(), scope))
            if not branch_states:
                return state
            merged = branch_states[0].clone()
            for branch_state in branch_states[1:]:
                _merge_state_into(merged, branch_state)
            return merged

        if not isinstance(statement, tuple) or not statement:
            return state

        tag = statement[0]
        if tag == const.KEY_ASSIGN and len(statement) == 3:
            return self._execute_assignment(statement[1], statement[2], state, scope)

        if tag == const.KEY_FUNCTION_CALL and len(statement) == 3:
            return self._execute_builtin_call(cast(str, statement[1]), cast(list[object], statement[2]), state, scope)

        if tag == const.GRAMMAR_VALUE_IF and len(statement) == 3:
            branches = cast(list[tuple[object, list[object]]], statement[1])
            else_branch = cast(list[object], statement[2])
            branch_states = []
            for _condition, branch_body in branches:
                branch_states.append(self._execute_statement_list(branch_body, state.clone(), scope))
            if else_branch:
                branch_states.append(self._execute_statement_list(else_branch, state.clone(), scope))
            if not branch_states:
                return state
            merged = branch_states[0].clone()
            for branch_state in branch_states[1:]:
                _merge_state_into(merged, branch_state)
            return merged

        return state

    def _execute_assignment(
        self,
        target_node: object,
        value_node: object,
        state: _AbstractState,
        scope: ScopeContext,
    ) -> _AbstractState:
        target_ref = varname_full(target_node)
        if not target_ref:
            return state
        target_slot = _resolve_slot(scope, target_ref)
        if target_slot is None:
            return state
        next_state = state.clone()
        int_result = self._eval_int_expr(value_node, state, scope)
        string_result = self._eval_string_expr(value_node, state, scope)
        target_is_string = is_string_simple_type(target_slot.variable.datatype)
        target_is_integer = target_slot.variable.datatype is Simple_DataType.INTEGER
        if target_is_string or (
            target_slot.key.field_path
            and (string_result.candidates or string_result.unknown_text)
            and not int_result.values
        ):
            next_state.string_values[target_slot.key] = _with_end_cursor(
                _retarget_string_result(string_result, target_result=_read_string_result(state, target_slot))
            )
            return next_state
        if int_result.values or (int_result.unknown and target_is_integer):
            next_state.int_values[target_slot.key] = int_result
            return next_state
        if string_result.candidates or string_result.unknown_text:
            next_state.string_values[target_slot.key] = _with_end_cursor(string_result)
            return next_state
        return next_state

    def _execute_builtin_call(
        self,
        raw_name: str,
        args: list[object],
        state: _AbstractState,
        scope: ScopeContext,
    ) -> _AbstractState:
        name = raw_name.casefold()
        next_state = state.clone()

        if name in {"clearstring", "setstringpos", "cutstring"}:
            return self._execute_cursor_or_trim_builtin(name, args, state, scope, next_state)
        if name in {"copystring", "copystringnosort", "concatenate"}:
            return self._execute_copy_or_concatenate_builtin(name, args, state, scope, next_state)
        if name in {"insertstring", "putblanks", "extractstring"}:
            return self._execute_length_transform_builtin(name, args, state, scope, next_state)
        if name in {"nationaluppercase", "nationallowercase"}:
            return self._execute_national_case_builtin(name, args, state, scope, next_state)

        return next_state

    def _execute_cursor_or_trim_builtin(
        self,
        name: str,
        args: list[object],
        state: _AbstractState,
        scope: ScopeContext,
        next_state: _AbstractState,
    ) -> _AbstractState:

        if name == "clearstring" and len(args) >= 1:
            target_slot = _resolve_target_arg(scope, args[0])
            if target_slot is not None:
                target_result = _read_string_result(state, target_slot)
                next_state.string_values[target_slot.key] = StringInferenceResult(
                    candidates=(StringCandidate(text=""),),
                    cursor_positions=(1,),
                    max_length=_string_capacity_for_datatype(target_slot.variable.datatype),
                    overflow_operations=target_result.overflow_operations,
                    overflow_examples=target_result.overflow_examples,
                )
            return next_state

        if name == "setstringpos" and len(args) >= 2:
            target_slot = _resolve_target_arg(scope, args[0])
            if target_slot is not None:
                target_result = _read_string_result(state, target_slot)
                positions = self._eval_int_expr(args[1], state, scope)
                next_state.string_values[target_slot.key] = _set_cursor_positions(target_result, positions)
            return next_state

        if name == "cutstring" and len(args) >= 2:
            target_slot = _resolve_target_arg(scope, args[0])
            if target_slot is not None:
                target_result = _read_string_result(state, target_slot)
                length_result = self._eval_int_expr(args[1], state, scope)
                next_state.string_values[target_slot.key] = _cut_string_result(target_result, length_result)
            return next_state

        return next_state

    def _execute_copy_or_concatenate_builtin(
        self,
        name: str,
        args: list[object],
        state: _AbstractState,
        scope: ScopeContext,
        next_state: _AbstractState,
    ) -> _AbstractState:

        if name in {"copystring", "copystringnosort"} and len(args) >= 2:
            target_slot = _resolve_target_arg(scope, args[1])
            if target_slot is not None:
                source_result = self._eval_string_expr(args[0], state, scope)
                next_state.string_values[target_slot.key] = _copy_into_target(
                    source_result,
                    target_slot.variable.datatype,
                    operation_name="CopyString" if name == "copystring" else "CopyStringNoSort",
                    target_result=_read_string_result(state, target_slot),
                )
            return next_state

        if name == "concatenate" and len(args) >= 3:
            target_slot = _resolve_target_arg(scope, args[2])
            if target_slot is not None:
                left = self._eval_string_expr(args[0], state, scope)
                right = self._eval_string_expr(args[1], state, scope)
                target_result = _read_string_result(state, target_slot)
                next_state.string_values[target_slot.key] = _concatenate_results(
                    left,
                    right,
                    target_result=target_result,
                    target_datatype=target_slot.variable.datatype,
                )
            return next_state

        return next_state

    def _execute_length_transform_builtin(
        self,
        name: str,
        args: list[object],
        state: _AbstractState,
        scope: ScopeContext,
        next_state: _AbstractState,
    ) -> _AbstractState:
        if name == "insertstring" and len(args) >= 3:
            target_slot = _resolve_target_arg(scope, args[0])
            if target_slot is not None:
                target_result = _read_string_result(state, target_slot)
                source_result = self._eval_string_expr(args[1], state, scope)
                length_result = self._eval_int_expr(args[2], state, scope)
                next_state.string_values[target_slot.key] = _insert_string_result(
                    target_result,
                    source_result,
                    length_result,
                    target_datatype=target_slot.variable.datatype,
                    operation_name="InsertString",
                )
            return next_state

        if name == "putblanks" and len(args) >= 2:
            target_slot = _resolve_target_arg(scope, args[0])
            if target_slot is not None:
                target_result = _read_string_result(state, target_slot)
                length_result = self._eval_int_expr(args[1], state, scope)
                next_state.string_values[target_slot.key] = _put_blanks_result(
                    target_result,
                    length_result,
                    target_datatype=target_slot.variable.datatype,
                )
            return next_state

        if name == "extractstring" and len(args) >= 3:
            target_slot = _resolve_target_arg(scope, args[0])
            if target_slot is not None:
                target_result = _read_string_result(state, target_slot)
                source_result = self._eval_string_expr(args[1], state, scope)
                length_result = self._eval_int_expr(args[2], state, scope)
                next_state.string_values[target_slot.key] = _extract_string_result(
                    source_result,
                    length_result,
                    target_result=target_result,
                    target_datatype=target_slot.variable.datatype,
                    operation_name="ExtractString",
                )
            return next_state

        return next_state

    def _execute_national_case_builtin(
        self,
        name: str,
        args: list[object],
        state: _AbstractState,
        scope: ScopeContext,
        next_state: _AbstractState,
    ) -> _AbstractState:
        if len(args) >= 2:
            target_slot = _resolve_target_arg(scope, args[1])
            if target_slot is not None:
                source_result = self._eval_string_expr(args[0], state, scope)
                target_capacity = _string_capacity_for_datatype(target_slot.variable.datatype)
                if name == "nationaluppercase":
                    next_state.string_values[target_slot.key] = _transform_string_result(
                        source_result,
                        str.upper,
                        target_capacity,
                        operation_name="NationalUpperCase",
                        target_result=_read_string_result(state, target_slot),
                    )
                else:
                    next_state.string_values[target_slot.key] = _transform_string_result(
                        source_result,
                        str.lower,
                        target_capacity,
                        operation_name="NationalLowerCase",
                        target_result=_read_string_result(state, target_slot),
                    )
            return next_state

        return next_state

    def _eval_string_expr(self, expr: object, state: _AbstractState, scope: ScopeContext) -> StringInferenceResult:
        if isinstance(expr, str):
            return _result_for_literal(
                expr,
                source_kind="literal",
                source_label=repr(expr),
                source_module_path=tuple(scope.module_path),
                max_length=len(expr),
            )

        if isinstance(expr, VarRef):
            ref_name = varname_full(expr)
            if not ref_name:
                return _unknown_string_result()
            resolved = _resolve_slot(scope, ref_name)
            if resolved is None:
                return _unknown_string_result()
            return _read_string_result(state, resolved)

        if isinstance(expr, TernaryOp):
            merged = StringInferenceResult()
            for _condition, branch_expr in expr.branches:
                merged = _merge_string_results(merged, self._eval_string_expr(branch_expr, state, scope))
            if expr.else_expr is not None:
                merged = _merge_string_results(merged, self._eval_string_expr(expr.else_expr, state, scope))
            return merged

        if isinstance(expr, dict):
            ref_name = varname_full(expr)
            if not ref_name:
                return _unknown_string_result()
            resolved = _resolve_slot(scope, ref_name)
            if resolved is None:
                return _unknown_string_result()
            return _read_string_result(state, resolved)

        if isinstance(expr, tuple) and expr:
            tag = expr[0]
            if tag == const.KEY_TERNARY and len(expr) == 3:
                merged = StringInferenceResult()
                for _condition, branch_expr in cast(list[tuple[object, object]], expr[1]):
                    merged = _merge_string_results(merged, self._eval_string_expr(branch_expr, state, scope))
                merged = _merge_string_results(merged, self._eval_string_expr(expr[2], state, scope))
                return merged

            return _unknown_string_result()

        return _unknown_string_result()

    def _eval_int_expr(self, expr: object, state: _AbstractState, scope: ScopeContext) -> _IntResult:
        if isinstance(expr, bool):
            return _IntResult()
        if isinstance(expr, int):
            return _normalize_int_result(_IntResult((expr,), False))

        if isinstance(expr, VarRef):
            ref_name = varname_full(expr)
            if not ref_name:
                return _IntResult(unknown=True)
            resolved = _resolve_slot(scope, ref_name)
            if resolved is None:
                return _IntResult(unknown=True)
            return state.int_values.get(resolved.key, _IntResult(unknown=True))

        if isinstance(expr, FuncCall):
            name = expr.name.casefold()
            args = list(expr.args)
            if name == "stringlength" and args:
                source = self._eval_string_expr(args[0], state, scope)
                values = tuple(len(candidate.text) for candidate in source.candidates)
                return _normalize_int_result(_IntResult(values, source.unknown_text))
            if name == "getstringpos" and args:
                source = self._eval_string_expr(args[0], state, scope)
                return _normalize_int_result(_IntResult(source.cursor_positions, source.unknown_cursor))
            if name == "maxstringlength" and args:
                source = self._eval_string_expr(args[0], state, scope)
                if source.max_length is None:
                    return _IntResult(unknown=source.unknown_max_length)
                return _normalize_int_result(_IntResult((source.max_length,), source.unknown_max_length))

        if isinstance(expr, BinOp):
            result = self._eval_int_expr(expr.left, state, scope)
            if expr.op == "-":
                tail = self._eval_int_expr(expr.right, state, scope)
                result = _apply_int_operator(result, "-", tail)
            else:
                tail = self._eval_int_expr(expr.right, state, scope)
                result = _apply_int_operator(result, expr.op, tail)
            return result

        if isinstance(expr, UnaryOp):
            if expr.op == "-":
                source = self._eval_int_expr(expr.operand, state, scope)
                return _normalize_int_result(
                    _IntResult(tuple(-value for value in source.values), source.unknown),
                )
            if expr.op == "+":
                return self._eval_int_expr(expr.operand, state, scope)

        if isinstance(expr, TernaryOp):
            merged = _IntResult()
            for _condition, branch_expr in expr.branches:
                merged = _merge_int_results(merged, self._eval_int_expr(branch_expr, state, scope))
            if expr.else_expr is not None:
                merged = _merge_int_results(merged, self._eval_int_expr(expr.else_expr, state, scope))
            return merged

        if isinstance(expr, dict):
            ref_name = varname_full(expr)
            if not ref_name:
                return _IntResult(unknown=True)
            resolved = _resolve_slot(scope, ref_name)
            if resolved is None:
                return _IntResult(unknown=True)
            return state.int_values.get(resolved.key, _IntResult(unknown=True))

        if isinstance(expr, tuple) and expr:
            return self._eval_int_tuple_expr(expr, state, scope)

        return _IntResult(unknown=True)

    def _eval_int_tuple_expr(self, expr: tuple[object, ...], state: _AbstractState, scope: ScopeContext) -> _IntResult:
        tag = expr[0]
        if tag == const.KEY_FUNCTION_CALL and len(expr) == 3:
            name = cast(str, expr[1]).casefold()
            args = cast(list[object], expr[2])
            if name == "stringlength" and args:
                source = self._eval_string_expr(args[0], state, scope)
                values = tuple(len(candidate.text) for candidate in source.candidates)
                return _normalize_int_result(_IntResult(values, source.unknown_text))
            if name == "getstringpos" and args:
                source = self._eval_string_expr(args[0], state, scope)
                return _normalize_int_result(_IntResult(source.cursor_positions, source.unknown_cursor))
            if name == "maxstringlength" and args:
                source = self._eval_string_expr(args[0], state, scope)
                if source.max_length is None:
                    return _IntResult(unknown=source.unknown_max_length)
                return _normalize_int_result(_IntResult((source.max_length,), source.unknown_max_length))

        if tag == const.KEY_ADD and len(expr) == 3:
            result = self._eval_int_expr(expr[1], state, scope)
            for operator, tail_expr in cast(list[tuple[str, object]], expr[2]):
                tail = self._eval_int_expr(tail_expr, state, scope)
                result = _apply_int_operator(result, operator, tail)
            return result

        if tag == const.KEY_MINUS and len(expr) == 2:
            source = self._eval_int_expr(expr[1], state, scope)
            return _normalize_int_result(
                _IntResult(tuple(-value for value in source.values), source.unknown),
            )

        if tag == const.KEY_PLUS and len(expr) == 2:
            return self._eval_int_expr(expr[1], state, scope)

        if tag == const.KEY_TERNARY and len(expr) == 3:
            merged = _IntResult()
            for _condition, branch_expr in cast(list[tuple[object, object]], expr[1]):
                merged = _merge_int_results(merged, self._eval_int_expr(branch_expr, state, scope))
            merged = _merge_int_results(merged, self._eval_int_expr(expr[2], state, scope))
            return merged

        return _IntResult(unknown=True)


def _module_code(
    node: BasePicture | SingleModule | FrameModule | ModuleTypeDef | ModuleTypeInstance,
) -> ModuleCode | None:
    return getattr(node, "modulecode", None)


def _module_code_blocks(
    node: BasePicture | SingleModule | FrameModule | ModuleTypeDef | ModuleTypeInstance,
) -> tuple[list[object], ...]:
    module_code = _module_code(node)
    if module_code is None:
        return ()
    blocks: list[list[object]] = []
    for equation in module_code.equations or []:
        if isinstance(equation, Equation):
            blocks.append(list(equation.code or []))
    for sequence in module_code.sequences or []:
        if isinstance(sequence, Sequence):
            blocks.append(list(sequence.code or []))
    return tuple(blocks)


def _declared_variables(
    node: BasePicture | SingleModule | FrameModule | ModuleTypeDef | ModuleTypeInstance,
) -> tuple[Variable, ...]:
    declared: list[Variable] = []
    for attribute in ("moduleparameters", "localvariables"):
        values = getattr(node, attribute, None)
        if isinstance(values, list):
            declared.extend(variable for variable in values if isinstance(variable, Variable))
    return tuple(declared)


def _candidate_moduletype_index(
    base_picture: BasePicture,
    graph: ProjectGraph | None,
) -> dict[str, tuple[ModuleTypeDef, ...]]:
    index: dict[str, list[ModuleTypeDef]] = {}
    seen: set[tuple[str, str, str]] = set()
    candidates = [*(base_picture.moduletype_defs or [])]
    if graph is not None:
        candidates.extend(graph.moduletype_defs.values())
    for moduletype in candidates:
        identity = (
            moduletype.name.casefold(),
            (moduletype.origin_lib or "").casefold(),
            (moduletype.origin_file or "").casefold(),
        )
        if identity in seen:
            continue
        seen.add(identity)
        index.setdefault(moduletype.name.casefold(), []).append(moduletype)
    return {key: tuple(value) for key, value in index.items()}


def _resolve_typedef_for_instance(
    base_picture: BasePicture,
    instance: ModuleTypeInstance,
    current_library: str | None,
    moduletype_index: dict[str, tuple[ModuleTypeDef, ...]],
) -> ModuleTypeDef | None:
    matches = list(moduletype_index.get(instance.moduletype_name.casefold(), ()))
    if not matches:
        return None
    try:
        return select_moduletype_def_strict(
            base_picture,
            instance.moduletype_name,
            matches,
            current_library=current_library,
            current_file=None,
        )
    except ValueError:
        return None


def _build_single_scope(mod: SingleModule, parent_scope: ScopeContext, module_path: tuple[str, ...]) -> ScopeContext:
    env = {
        variable.name.casefold(): variable for variable in [*(mod.moduleparameters or []), *(mod.localvariables or [])]
    }
    param_keys = {variable.name.casefold() for variable in mod.moduleparameters or []}
    param_mappings = _field_aware_param_mappings(mod.parametermappings, parent_scope, param_keys)
    return ScopeContext(
        env=env,
        param_mappings=param_mappings,
        module_path=list(module_path),
        display_module_path=list(module_path),
        moduleparameter_keys=frozenset(param_keys),
        current_library=parent_scope.current_library,
        parent_context=parent_scope,
    )


def _build_typedef_scope(
    moduletype: ModuleTypeDef,
    instance: ModuleTypeInstance,
    parent_scope: ScopeContext,
    module_path: tuple[str, ...],
) -> ScopeContext:
    env = {
        variable.name.casefold(): variable
        for variable in [*(moduletype.moduleparameters or []), *(moduletype.localvariables or [])]
    }
    param_keys = {variable.name.casefold() for variable in moduletype.moduleparameters or []}
    param_mappings = _field_aware_param_mappings(instance.parametermappings, parent_scope, param_keys)
    return ScopeContext(
        env=env,
        param_mappings=param_mappings,
        module_path=list(module_path),
        display_module_path=list(module_path),
        moduleparameter_keys=frozenset(param_keys),
        current_library=moduletype.origin_lib or parent_scope.current_library,
        parent_context=parent_scope,
    )


def _field_aware_param_mappings(
    mappings: list[ParameterMapping] | None,
    parent_scope: ScopeContext,
    param_keys: set[str],
) -> dict[str, tuple[Variable, str, list[str], list[str]]]:
    resolved: dict[str, tuple[Variable, str, list[str], list[str]]] = {}
    for parameter_mapping in mappings or []:
        target_name = varname_base(parameter_mapping.target)
        if not target_name or parameter_mapping.is_source_global:
            continue
        target_key = target_name.casefold()
        if target_key not in param_keys:
            continue
        full_source = varname_full(parameter_mapping.source)
        if not full_source:
            continue
        source_var, source_field_prefix, source_decl_path, source_decl_display_path = parent_scope.resolve_variable(
            full_source
        )
        if source_var is None:
            continue
        resolved[target_key] = (source_var, source_field_prefix, source_decl_path, source_decl_display_path)
    return resolved


def _literal_bindings_for_mappings(
    mappings: list[ParameterMapping] | None,
    source_kind: str,
) -> tuple[_LiteralBinding, ...]:
    literal_bindings: list[_LiteralBinding] = []
    for mapping in mappings or []:
        target_ref = varname_full(mapping.target)
        if not target_ref or mapping.source_literal is None:
            continue
        literal_bindings.append(
            _LiteralBinding(
                target_ref=target_ref,
                source_literal=mapping.source_literal,
                source_kind=source_kind,
            )
        )
    return tuple(literal_bindings)


def _declaration_slot(module_path: tuple[str, ...], variable_name: str) -> _SlotKey:
    return _SlotKey(
        module_path=tuple(segment.casefold() for segment in module_path),
        variable_name=variable_name.casefold(),
        field_path="",
    )


def _local_slot_key(module_path: tuple[str, ...], ref_name: str) -> _SlotKey | None:
    if not ref_name:
        return None
    base_name, _, field_path = ref_name.partition(".")
    return _SlotKey(
        module_path=tuple(segment.casefold() for segment in module_path),
        variable_name=base_name.casefold(),
        field_path=field_path.casefold(),
    )


def _resolve_slot(scope: ScopeContext, ref_name: str) -> _ResolvedSlot | None:
    variable, field_path, decl_path, _decl_display = scope.resolve_variable(ref_name)
    if variable is None:
        return None
    slot_key = _SlotKey(
        module_path=tuple(segment.casefold() for segment in decl_path),
        variable_name=variable.name.casefold(),
        field_path=field_path.casefold(),
    )
    display_name = variable.name if not field_path else f"{variable.name}.{field_path}"
    return _ResolvedSlot(key=slot_key, display_name=display_name, decl_module_path=tuple(decl_path), variable=variable)


def _resolve_target_arg(scope: ScopeContext, arg: object) -> _ResolvedSlot | None:
    ref_name = varname_full(arg)
    if not ref_name:
        return None
    return _resolve_slot(scope, ref_name)
