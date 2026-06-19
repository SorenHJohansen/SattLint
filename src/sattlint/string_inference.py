"""Shared exact string inference with cursor-aware builtin handling."""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnnecessaryIsInstance=false

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
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

from ._validation_type_helpers import is_string_simple_type
from .resolution.common import select_moduletype_def_strict, varname_base, varname_full
from .resolution.scope import ScopeContext

if TYPE_CHECKING:
    from .models.project_graph import ProjectGraph


_MAX_STRING_CANDIDATES = 24
_MAX_CURSOR_POSITIONS = 24
_MAX_FIXED_POINT_PASSES = 8
_MAX_OVERFLOW_EXAMPLES = 8
_STRING_LIMITS: dict[Simple_DataType, int] = {
    Simple_DataType.IDENTSTRING: 15,
    Simple_DataType.TAGSTRING: 30,
    Simple_DataType.STRING: 40,
    Simple_DataType.LINESTRING: 80,
    Simple_DataType.MAXSTRING: 140,
}


@dataclass(frozen=True, slots=True)
class StringProvenanceSegment:
    text: str
    source_kind: str
    source_label: str | None = None
    source_module_path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StringCandidate:
    text: str
    segments: tuple[StringProvenanceSegment, ...] = ()


@dataclass(frozen=True, slots=True)
class StringInferenceResult:
    candidates: tuple[StringCandidate, ...] = ()
    cursor_positions: tuple[int, ...] = ()
    max_length: int | None = None
    unknown_text: bool = False
    unknown_cursor: bool = False
    unknown_max_length: bool = False
    overflow_operations: tuple[str, ...] = ()
    overflow_examples: tuple[str, ...] = ()

    @property
    def texts(self) -> tuple[str, ...]:
        return tuple(candidate.text for candidate in self.candidates)

    @property
    def overflowed(self) -> bool:
        return bool(self.overflow_operations or self.overflow_examples)


@dataclass(frozen=True, slots=True)
class _SlotKey:
    module_path: tuple[str, ...]
    variable_name: str
    field_path: str = ""


@dataclass(frozen=True, slots=True)
class _ResolvedSlot:
    key: _SlotKey
    display_name: str
    decl_module_path: tuple[str, ...]
    variable: Variable


@dataclass(frozen=True, slots=True)
class _IntResult:
    values: tuple[int, ...] = ()
    unknown: bool = False


@dataclass(slots=True)
class _AbstractState:
    string_values: dict[_SlotKey, StringInferenceResult] = field(default_factory=dict)
    int_values: dict[_SlotKey, _IntResult] = field(default_factory=dict)

    def clone(self) -> _AbstractState:
        return _AbstractState(string_values=self.string_values.copy(), int_values=self.int_values.copy())


@dataclass(frozen=True, slots=True)
class _LiteralBinding:
    target_ref: str
    source_literal: object
    source_kind: str


@dataclass(slots=True)
class _ModuleContext:
    path: tuple[str, ...]
    scope: ScopeContext
    node: BasePicture | SingleModule | FrameModule | ModuleTypeDef | ModuleTypeInstance
    literal_bindings: tuple[_LiteralBinding, ...]
    children: tuple[_ModuleContext, ...] = ()


class ExactStringInferenceEngine:
    """Infers exact string candidates and cursor positions for module-scoped refs."""

    def __init__(self, base_picture: BasePicture, *, graph: ProjectGraph | None = None):
        self.base_picture = base_picture
        self.graph = graph
        self._moduletype_index = _candidate_moduletype_index(base_picture, graph)
        self._contexts_by_path: dict[tuple[str, ...], _ModuleContext] = {}
        self._execution_contexts: list[_ModuleContext] = []
        self._root_context = self._build_basepicture_context()
        self._collect_contexts(self._root_context)
        for moduletype in self.base_picture.moduletype_defs or []:
            self._collect_contexts(self._build_typedef_root_context(moduletype))
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
        for _ in range(_MAX_FIXED_POINT_PASSES):
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
        context = _ModuleContext(
            path=child_path,
            scope=scope,
            node=resolved_typedef,
            literal_bindings=_literal_bindings_for_mappings(child.parametermappings, "parameter_mapping_literal"),
        )
        context.children = tuple(
            self._build_child_context(context, grandchild) for grandchild in resolved_typedef.submodules or []
        )
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
        if not isinstance(statement, tuple) or not statement:
            return state

        tag = statement[0]
        if tag == const.KEY_ASSIGN and len(statement) == 3:
            target_ref = varname_full(statement[1])
            if not target_ref:
                return state
            target_slot = _resolve_slot(scope, target_ref)
            if target_slot is None:
                return state
            next_state = state.clone()
            int_result = self._eval_int_expr(statement[2], state, scope)
            string_result = self._eval_string_expr(statement[2], state, scope)
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

        if tag == const.KEY_FUNCTION_CALL and len(statement) == 3:
            return self._execute_builtin_call(cast(str, statement[1]), cast(list[object], statement[2]), state, scope)

        if tag == const.GRAMMAR_VALUE_IF and len(statement) == 3:
            branches = cast(list[tuple[object, list[object]]], statement[1])
            else_branch = cast(list[object], statement[2])
            branch_states: list[_AbstractState] = []
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

        if isinstance(expr, dict):
            ref_name = varname_full(expr)
            if not ref_name:
                return _IntResult(unknown=True)
            resolved = _resolve_slot(scope, ref_name)
            if resolved is None:
                return _IntResult(unknown=True)
            return state.int_values.get(resolved.key, _IntResult(unknown=True))

        if isinstance(expr, tuple) and expr:
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


def _read_string_result(state: _AbstractState, slot: _ResolvedSlot) -> StringInferenceResult:
    return state.string_values.get(
        slot.key,
        _unknown_string_result(max_length=_string_capacity_for_datatype(slot.variable.datatype)),
    )


def _merge_state_into(target: _AbstractState, source: _AbstractState) -> None:
    for key, value in source.string_values.items():
        target.string_values[key] = _merge_string_results(target.string_values.get(key, StringInferenceResult()), value)
    for key, value in source.int_values.items():
        target.int_values[key] = _merge_int_results(target.int_values.get(key, _IntResult()), value)


def _merge_string_results(left: StringInferenceResult, right: StringInferenceResult) -> StringInferenceResult:
    candidates = _normalize_candidates([*left.candidates, *right.candidates])
    cursor_positions, cursor_overflow = _normalize_cursor_positions([*left.cursor_positions, *right.cursor_positions])
    return StringInferenceResult(
        candidates=candidates,
        cursor_positions=cursor_positions,
        max_length=_merge_max_lengths(left.max_length, right.max_length),
        unknown_text=left.unknown_text or right.unknown_text or len(candidates) >= _MAX_STRING_CANDIDATES,
        unknown_cursor=left.unknown_cursor or right.unknown_cursor or cursor_overflow,
        unknown_max_length=left.unknown_max_length or right.unknown_max_length,
        overflow_operations=_merge_overflow_operations(left.overflow_operations, right.overflow_operations),
        overflow_examples=_merge_overflow_examples(left.overflow_examples, right.overflow_examples),
    )


def _normalize_candidates(candidates: Iterable[StringCandidate]) -> tuple[StringCandidate, ...]:
    unique = {candidate: None for candidate in candidates if isinstance(candidate, StringCandidate)}
    ordered = sorted(unique.keys(), key=repr)
    return tuple(ordered[:_MAX_STRING_CANDIDATES])


def _normalize_cursor_positions(values: Iterable[int]) -> tuple[tuple[int, ...], bool]:
    unique = sorted({max(value, 1) for value in values if isinstance(value, int)})
    overflow = len(unique) > _MAX_CURSOR_POSITIONS
    return tuple(unique[:_MAX_CURSOR_POSITIONS]), overflow


def _normalize_int_result(result: _IntResult) -> _IntResult:
    values = tuple(sorted({value for value in result.values if isinstance(value, int)}))
    return _IntResult(
        values=values[:_MAX_CURSOR_POSITIONS], unknown=result.unknown or len(values) > _MAX_CURSOR_POSITIONS
    )


def _merge_int_results(left: _IntResult, right: _IntResult) -> _IntResult:
    return _normalize_int_result(
        _IntResult(values=(*left.values, *right.values), unknown=left.unknown or right.unknown)
    )


def _apply_int_operator(left: _IntResult, operator: str, right: _IntResult) -> _IntResult:
    if not left.values or not right.values:
        return _IntResult(unknown=left.unknown or right.unknown)
    values: list[int] = []
    for left_value in left.values:
        for right_value in right.values:
            if operator == "+":
                values.append(left_value + right_value)
            elif operator == "-":
                values.append(left_value - right_value)
            else:
                return _IntResult(unknown=True)
    return _normalize_int_result(_IntResult(tuple(values), left.unknown or right.unknown))


def _result_for_literal(
    text: str,
    *,
    source_kind: str,
    source_label: str | None,
    source_module_path: tuple[str, ...],
    max_length: int | None,
) -> StringInferenceResult:
    segment = StringProvenanceSegment(
        text=text,
        source_kind=source_kind,
        source_label=source_label,
        source_module_path=source_module_path,
    )
    return _with_end_cursor(
        StringInferenceResult(
            candidates=(StringCandidate(text=text, segments=(segment,)),),
            max_length=max_length,
            unknown_max_length=max_length is None,
        )
    )


def _with_end_cursor(result: StringInferenceResult) -> StringInferenceResult:
    cursor_positions, cursor_overflow = _normalize_cursor_positions(
        len(candidate.text) + 1 for candidate in result.candidates
    )
    return StringInferenceResult(
        candidates=result.candidates,
        cursor_positions=cursor_positions,
        max_length=result.max_length,
        unknown_text=result.unknown_text,
        unknown_cursor=result.unknown_cursor or result.unknown_text or cursor_overflow,
        unknown_max_length=result.unknown_max_length,
        overflow_operations=result.overflow_operations,
        overflow_examples=result.overflow_examples,
    )


def _retarget_string_result(
    source_result: StringInferenceResult,
    *,
    target_result: StringInferenceResult,
) -> StringInferenceResult:
    return StringInferenceResult(
        candidates=source_result.candidates,
        cursor_positions=source_result.cursor_positions,
        max_length=source_result.max_length,
        unknown_text=source_result.unknown_text,
        unknown_cursor=source_result.unknown_cursor,
        unknown_max_length=source_result.unknown_max_length,
        overflow_operations=target_result.overflow_operations,
        overflow_examples=target_result.overflow_examples,
    )


def _set_cursor_positions(result: StringInferenceResult, positions: _IntResult) -> StringInferenceResult:
    valid_positions = positions.values
    if result.max_length is not None:
        valid_positions = tuple(value for value in positions.values if 1 <= value <= result.max_length)
        if not valid_positions:
            return _preserve_unchanged(
                result,
                unknown_text=result.unknown_text,
                unknown_cursor=result.unknown_cursor or positions.unknown,
            )
    cursor_positions, cursor_overflow = _normalize_cursor_positions(valid_positions)
    return StringInferenceResult(
        candidates=result.candidates,
        cursor_positions=cursor_positions,
        max_length=result.max_length,
        unknown_text=result.unknown_text,
        unknown_cursor=result.unknown_cursor or positions.unknown or cursor_overflow,
        unknown_max_length=result.unknown_max_length,
        overflow_operations=result.overflow_operations,
        overflow_examples=result.overflow_examples,
    )


def _concatenate_results(
    left: StringInferenceResult,
    right: StringInferenceResult,
    *,
    target_result: StringInferenceResult,
    target_datatype: Simple_DataType | str | None,
) -> StringInferenceResult:
    candidates: list[StringCandidate] = []
    cursor_positions: list[int] = []
    overflow_examples: list[str] = []
    overflowed = False
    target_capacity = _string_capacity_for_datatype(target_datatype)
    for left_candidate in left.candidates:
        for right_candidate in right.candidates:
            moved_left = _substring_from_cursor(left_candidate, left.cursor_positions)
            moved_right = _substring_from_cursor(right_candidate, right.cursor_positions)
            for target_position in target_result.cursor_positions or (1,):
                write_start = max(target_position, 1) - 1
                inserted_segments = _merge_adjacent_segments((*moved_left[1], *moved_right[1]))
                fill_count = max(write_start, 0)
                prefix_text = "" if fill_count == 0 else " " * fill_count
                prefix_segments = () if fill_count == 0 else (_blank_segment(fill_count),)
                combined_text = prefix_text + moved_left[0] + moved_right[0]
                if target_capacity is not None and len(combined_text) > target_capacity:
                    overflowed = True
                    overflow_examples.append(combined_text)
                    continue
                candidates.append(
                    StringCandidate(
                        text=combined_text,
                        segments=_merge_adjacent_segments((*prefix_segments, *inserted_segments)),
                    )
                )
                cursor_positions.append(len(combined_text) + 1)

    if not candidates:
        return _preserve_unchanged(
            target_result,
            max_length=target_capacity,
            unknown_text=left.unknown_text or right.unknown_text,
            unknown_cursor=left.unknown_cursor or right.unknown_cursor or target_result.unknown_cursor,
            overflow_operations=("Concatenate",) if overflowed else (),
            overflow_examples=tuple(overflow_examples),
        )

    normalized_positions, cursor_overflow = _normalize_cursor_positions(cursor_positions)
    carried_operations, carried_examples = _carried_overflow_state(
        target_result,
        operations=("Concatenate",) if overflowed else (),
        examples=tuple(overflow_examples),
    )
    return StringInferenceResult(
        candidates=_normalize_candidates(candidates),
        cursor_positions=normalized_positions,
        max_length=target_capacity,
        unknown_text=left.unknown_text or right.unknown_text,
        unknown_cursor=left.unknown_cursor or right.unknown_cursor or target_result.unknown_cursor or cursor_overflow,
        unknown_max_length=target_capacity is None,
        overflow_operations=carried_operations,
        overflow_examples=carried_examples,
    )


def _insert_string_result(
    target: StringInferenceResult,
    source: StringInferenceResult,
    length_result: _IntResult,
    *,
    target_datatype: Simple_DataType | str | None,
    operation_name: str = "InsertString",
) -> StringInferenceResult:
    if not target.candidates or not source.candidates or not target.cursor_positions or not length_result.values:
        return _preserve_unchanged(
            target,
            max_length=_string_capacity_for_datatype(target_datatype),
            unknown_text=target.unknown_text or source.unknown_text or True,
            unknown_cursor=target.unknown_cursor or source.unknown_cursor or length_result.unknown or True,
        )

    candidates: list[StringCandidate] = []
    cursor_positions: list[int] = []
    overflow_examples: list[str] = []
    overflowed = False
    target_capacity = _string_capacity_for_datatype(target_datatype)
    for target_candidate in target.candidates:
        for cursor_position in target.cursor_positions:
            safe_position = min(max(cursor_position, 1), (target_capacity or len(target_candidate.text) + 1) + 1)
            insert_at = safe_position - 1
            for source_candidate in source.candidates:
                for requested_length in length_result.values:
                    insert_text = source_candidate.text[: max(requested_length, 0)]
                    if target_capacity is not None and insert_at > target_capacity:
                        overflowed = True
                        continue
                    padded_target = target_candidate.text
                    padded_segments = target_candidate.segments
                    if insert_at > len(target_candidate.text):
                        blank_count = insert_at - len(target_candidate.text)
                        if target_capacity is not None and len(target_candidate.text) + blank_count > target_capacity:
                            overflowed = True
                            continue
                        padded_target = target_candidate.text + (" " * blank_count)
                        padded_segments = _merge_adjacent_segments(
                            (*target_candidate.segments, _blank_segment(blank_count))
                        )
                    if target_capacity is not None and len(padded_target) + len(insert_text) > target_capacity:
                        overflowed = True
                        overflow_examples.append(padded_target[:insert_at] + insert_text + padded_target[insert_at:])
                        continue
                    inserted_segments = _slice_segments(source_candidate.segments, 0, len(insert_text))
                    new_segments = _merge_adjacent_segments(
                        (
                            *_slice_segments(padded_segments, 0, insert_at),
                            *inserted_segments,
                            *_slice_segments(padded_segments, insert_at, len(padded_target)),
                        )
                    )
                    new_text = padded_target[:insert_at] + insert_text + padded_target[insert_at:]
                    candidates.append(
                        StringCandidate(
                            text=new_text,
                            segments=new_segments,
                        )
                    )
                    cursor_positions.append(insert_at + len(insert_text) + 1)

    if not candidates:
        return _preserve_unchanged(
            target,
            max_length=target_capacity,
            unknown_text=target.unknown_text or source.unknown_text,
            unknown_cursor=target.unknown_cursor or source.unknown_cursor or length_result.unknown,
            overflow_operations=(operation_name,) if overflowed else (),
            overflow_examples=tuple(overflow_examples),
        )

    normalized_positions, cursor_overflow = _normalize_cursor_positions(cursor_positions)
    carried_operations, carried_examples = _carried_overflow_state(
        target,
        operations=(operation_name,) if overflowed else (),
        examples=tuple(overflow_examples),
    )
    return StringInferenceResult(
        candidates=_normalize_candidates(candidates),
        cursor_positions=normalized_positions,
        max_length=target_capacity,
        unknown_text=target.unknown_text or source.unknown_text,
        unknown_cursor=target.unknown_cursor or source.unknown_cursor or length_result.unknown or cursor_overflow,
        unknown_max_length=target_capacity is None,
        overflow_operations=carried_operations,
        overflow_examples=carried_examples,
    )


def _cut_string_result(target: StringInferenceResult, length_result: _IntResult) -> StringInferenceResult:
    if not target.candidates or not target.cursor_positions or not length_result.values:
        return _preserve_unchanged(
            target,
            unknown_text=target.unknown_text or True,
            unknown_cursor=target.unknown_cursor or length_result.unknown or True,
        )

    candidates: list[StringCandidate] = []
    for target_candidate in target.candidates:
        for cursor_position in target.cursor_positions:
            start = min(max(cursor_position, 1), len(target_candidate.text) + 1) - 1
            for requested_length in length_result.values:
                length = max(requested_length, 0)
                end = min(start + length, len(target_candidate.text))
                candidates.append(
                    StringCandidate(
                        text=target_candidate.text[:start] + target_candidate.text[end:],
                        segments=_merge_adjacent_segments(
                            (
                                *_slice_segments(target_candidate.segments, 0, start),
                                *_slice_segments(target_candidate.segments, end, len(target_candidate.text)),
                            )
                        ),
                    )
                )

    return StringInferenceResult(
        candidates=_normalize_candidates(candidates),
        cursor_positions=target.cursor_positions,
        max_length=target.max_length,
        unknown_text=target.unknown_text,
        unknown_cursor=target.unknown_cursor or length_result.unknown,
        unknown_max_length=target.unknown_max_length,
        overflow_operations=target.overflow_operations,
        overflow_examples=target.overflow_examples,
    )


def _put_blanks_result(
    target: StringInferenceResult,
    length_result: _IntResult,
    *,
    target_datatype: Simple_DataType | str | None,
) -> StringInferenceResult:
    if not length_result.values:
        return _preserve_unchanged(
            target,
            max_length=_string_capacity_for_datatype(target_datatype),
            unknown_text=target.unknown_text or True,
            unknown_cursor=target.unknown_cursor or length_result.unknown or True,
        )
    blank_source = _result_for_literal(
        " " * max(max(length_result.values), 0),
        source_kind="builtin",
        source_label="PutBlanks",
        source_module_path=(),
        max_length=max(max(length_result.values), 0),
    )
    return _insert_string_result(
        target,
        blank_source,
        length_result,
        target_datatype=target_datatype,
        operation_name="PutBlanks",
    )


def _extract_string_result(
    source: StringInferenceResult,
    length_result: _IntResult,
    *,
    target_result: StringInferenceResult,
    target_datatype: Simple_DataType | str | None,
    operation_name: str = "ExtractString",
) -> StringInferenceResult:
    if not source.candidates or not source.cursor_positions or not length_result.values:
        return _preserve_unchanged(
            target_result,
            max_length=_string_capacity_for_datatype(target_datatype),
            unknown_text=source.unknown_text or True,
            unknown_cursor=source.unknown_cursor or length_result.unknown or True,
        )
    target_capacity = _string_capacity_for_datatype(target_datatype)
    candidates: list[StringCandidate] = []
    overflow_examples: list[str] = []
    overflowed = False
    for source_candidate in source.candidates:
        for cursor_position in source.cursor_positions:
            start = min(max(cursor_position, 1), len(source_candidate.text) + 1) - 1
            for requested_length in length_result.values:
                length = max(requested_length, 0)
                end = min(start + length, len(source_candidate.text))
                new_text = source_candidate.text[start:end]
                if target_capacity is not None and len(new_text) > target_capacity:
                    overflowed = True
                    overflow_examples.append(new_text)
                    continue
                candidates.append(
                    StringCandidate(
                        text=new_text,
                        segments=_merge_adjacent_segments(_slice_segments(source_candidate.segments, start, end)),
                    )
                )
    if not candidates:
        return _preserve_unchanged(
            target_result,
            max_length=target_capacity,
            unknown_text=source.unknown_text,
            unknown_cursor=source.unknown_cursor or length_result.unknown,
            overflow_operations=(operation_name,) if overflowed else (),
            overflow_examples=tuple(overflow_examples),
        )

    carried_operations, carried_examples = _carried_overflow_state(
        target_result,
        operations=(operation_name,) if overflowed else (),
        examples=tuple(overflow_examples),
    )
    return StringInferenceResult(
        candidates=_normalize_candidates(candidates),
        cursor_positions=(1,),
        max_length=target_capacity,
        unknown_text=source.unknown_text,
        unknown_cursor=source.unknown_cursor or length_result.unknown,
        unknown_max_length=target_capacity is None,
        overflow_operations=carried_operations,
        overflow_examples=carried_examples,
    )


def _transform_string_result(
    source: StringInferenceResult,
    transform: Callable[[str], str],
    target_capacity: int | None,
    *,
    operation_name: str,
    target_result: StringInferenceResult,
) -> StringInferenceResult:
    candidates: list[StringCandidate] = []
    overflow_examples: list[str] = []
    overflowed = False
    for candidate in source.candidates:
        transformed_text = transform(candidate.text)
        if target_capacity is not None and len(transformed_text) > target_capacity:
            overflowed = True
            overflow_examples.append(transformed_text)
            continue
        candidates.append(
            StringCandidate(
                text=transformed_text,
                segments=(
                    StringProvenanceSegment(
                        text=transformed_text,
                        source_kind="builtin",
                        source_label="transform",
                        source_module_path=(),
                    ),
                ),
            )
        )
    if not candidates:
        return _preserve_unchanged(
            target_result,
            max_length=target_capacity,
            unknown_text=source.unknown_text,
            unknown_cursor=source.unknown_cursor,
            overflow_operations=(operation_name,) if overflowed else (),
            overflow_examples=tuple(overflow_examples),
        )

    carried_operations, carried_examples = _carried_overflow_state(
        target_result,
        operations=(operation_name,) if overflowed else (),
        examples=tuple(overflow_examples),
    )
    return _with_end_cursor(
        StringInferenceResult(
            candidates=_normalize_candidates(candidates),
            max_length=target_capacity,
            unknown_text=source.unknown_text,
            unknown_cursor=source.unknown_cursor,
            unknown_max_length=target_capacity is None,
            overflow_operations=carried_operations,
            overflow_examples=carried_examples,
        )
    )


def _copy_into_target(
    source_result: StringInferenceResult,
    target_datatype: Simple_DataType | str | None,
    *,
    operation_name: str = "CopyString",
    target_result: StringInferenceResult,
) -> StringInferenceResult:
    target_capacity = _string_capacity_for_datatype(target_datatype)
    overflow_examples = [
        candidate.text
        for candidate in source_result.candidates
        if target_capacity is not None and len(candidate.text) > target_capacity
    ]
    candidates = [
        candidate
        for candidate in source_result.candidates
        if target_capacity is None or len(candidate.text) <= target_capacity
    ]
    if not candidates:
        return _preserve_unchanged(
            target_result,
            max_length=target_capacity,
            unknown_text=source_result.unknown_text,
            unknown_cursor=source_result.unknown_cursor,
            overflow_operations=(operation_name,) if overflow_examples else (),
            overflow_examples=tuple(overflow_examples),
        )

    carried_operations, carried_examples = _carried_overflow_state(
        target_result,
        operations=(operation_name,) if overflow_examples else (),
        examples=tuple(overflow_examples),
    )
    return _with_end_cursor(
        StringInferenceResult(
            candidates=_normalize_candidates(candidates),
            max_length=target_capacity,
            unknown_text=source_result.unknown_text,
            unknown_cursor=source_result.unknown_cursor,
            unknown_max_length=target_capacity is None,
            overflow_operations=carried_operations,
            overflow_examples=carried_examples,
        )
    )


def _unknown_string_result(
    *,
    max_length: int | None = None,
    unknown_text: bool = True,
    unknown_cursor: bool = True,
) -> StringInferenceResult:
    return StringInferenceResult(
        max_length=max_length,
        unknown_text=unknown_text,
        unknown_cursor=unknown_cursor,
        unknown_max_length=max_length is None,
    )


def _preserve_unchanged(
    result: StringInferenceResult,
    *,
    max_length: int | None = None,
    unknown_text: bool,
    unknown_cursor: bool,
    overflow_operations: Iterable[str] = (),
    overflow_examples: Iterable[str] = (),
) -> StringInferenceResult:
    carried_operations, carried_examples = _carried_overflow_state(
        result,
        operations=tuple(overflow_operations),
        examples=tuple(overflow_examples),
    )
    return StringInferenceResult(
        candidates=result.candidates,
        cursor_positions=result.cursor_positions,
        max_length=result.max_length if max_length is None else max_length,
        unknown_text=unknown_text,
        unknown_cursor=unknown_cursor,
        unknown_max_length=result.unknown_max_length if max_length is None else False,
        overflow_operations=carried_operations,
        overflow_examples=carried_examples,
    )


def _merge_max_lengths(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)


def _string_capacity_for_datatype(datatype: Simple_DataType | str | None) -> int | None:
    if isinstance(datatype, Simple_DataType):
        return _STRING_LIMITS.get(datatype)
    return None


def _merge_overflow_operations(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for operation in group:
            key = operation.casefold()
            if not operation or key in seen:
                continue
            seen.add(key)
            merged.append(operation)
    return tuple(merged)


def _merge_overflow_examples(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for example in group:
            if not example or example in seen:
                continue
            seen.add(example)
            merged.append(example)
            if len(merged) >= _MAX_OVERFLOW_EXAMPLES:
                return tuple(merged)
    return tuple(merged)


def _carried_overflow_state(
    result: StringInferenceResult,
    *,
    operations: tuple[str, ...] = (),
    examples: tuple[str, ...] = (),
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (
        _merge_overflow_operations(result.overflow_operations, operations),
        _merge_overflow_examples(result.overflow_examples, examples),
    )


def _blank_segment(blank_count: int) -> StringProvenanceSegment:
    return StringProvenanceSegment(text=" " * blank_count, source_kind="builtin", source_label="blank_fill")


def _substring_from_cursor(
    candidate: StringCandidate,
    cursor_positions: tuple[int, ...],
) -> tuple[str, tuple[StringProvenanceSegment, ...]]:
    if not cursor_positions:
        return "", ()
    start = min(max(cursor_positions[0], 1), len(candidate.text) + 1) - 1
    return candidate.text[start:], _slice_segments(candidate.segments, start, len(candidate.text))


def _slice_segments(
    segments: tuple[StringProvenanceSegment, ...],
    start: int,
    end: int,
) -> tuple[StringProvenanceSegment, ...]:
    if start >= end:
        return ()
    index = 0
    sliced: list[StringProvenanceSegment] = []
    for segment in segments:
        next_index = index + len(segment.text)
        if next_index <= start:
            index = next_index
            continue
        if index >= end:
            break
        take_start = max(start - index, 0)
        take_end = min(end - index, len(segment.text))
        if take_start < take_end:
            sliced.append(
                StringProvenanceSegment(
                    text=segment.text[take_start:take_end],
                    source_kind=segment.source_kind,
                    source_label=segment.source_label,
                    source_module_path=segment.source_module_path,
                )
            )
        index = next_index
    return tuple(sliced)


def _merge_adjacent_segments(segments: tuple[StringProvenanceSegment, ...]) -> tuple[StringProvenanceSegment, ...]:
    merged: list[StringProvenanceSegment] = []
    for segment in segments:
        if not segment.text:
            continue
        if merged and _same_segment_origin(merged[-1], segment):
            previous = merged[-1]
            merged[-1] = StringProvenanceSegment(
                text=previous.text + segment.text,
                source_kind=previous.source_kind,
                source_label=previous.source_label,
                source_module_path=previous.source_module_path,
            )
            continue
        merged.append(segment)
    return tuple(merged)


def _same_segment_origin(left: StringProvenanceSegment, right: StringProvenanceSegment) -> bool:
    return (
        left.source_kind == right.source_kind
        and left.source_label == right.source_label
        and left.source_module_path == right.source_module_path
    )
