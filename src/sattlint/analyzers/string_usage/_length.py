"""Length-only string analysis for procedure overflow and value ranges.

Only lengths and cursor positions are tracked, never the text itself, so a
module with thousands of string operations stays cheap. A finding is emitted
only when every operand length is known from literals, initializers, mappings,
or a modelled string procedure.
"""

from __future__ import annotations

from typing import cast

from sattlint.parser_api import (
    Assignment,
    FuncCall,
    FuncCallStmt,
    IfStmt,
    ModuleTypeInstance,
    ScalarDatatype,
)

from ...core.call_signatures import CallSignature, resolve_call_signature
from ...resolution.common import varname_full
from .._string_models import StringSlotKey
from ..shared._string_capacity import is_string_datatype
from ..shared.statement_sites import iter_statement_sites
from ..string_contexts import (
    StringModuleContext,
    declared_variables,
    module_code,
    resolve_string_slot,
    resolve_string_target,
)
from ._length_expr import LengthExpressionEvaluator
from ._length_model import (
    IntValue,
    LengthAnalysisResult,
    LengthState,
    LengthValue,
    OverflowFact,
    join_int,
    join_length,
    normalize_int,
    normalize_length,
    unknown_length,
)
from ._model import SlotTypes, display_path

_MAX_PASSES = 8


class LengthAnalyzer(LengthExpressionEvaluator):
    def __init__(self, *, types: SlotTypes) -> None:
        self._types = types

    def analyze(self, contexts: tuple[StringModuleContext, ...]) -> LengthAnalysisResult:
        state = self._initial_state(contexts)
        facts_by_pass: list[dict[OverflowFact, None]] = []
        previous_strings = state.strings.copy()
        converged = False
        for _pass_index in range(_MAX_PASSES):
            next_state, pass_facts = self._run_pass(contexts, state)
            facts_by_pass.append(pass_facts)
            strings_stable = next_state.strings == previous_strings
            facts_stable = len(facts_by_pass) >= 2 and facts_by_pass[-1] == facts_by_pass[-2]
            if next_state == state:
                converged = True
                state = next_state
                break
            state = next_state
            previous_strings = state.strings.copy()
            if strings_stable and facts_stable:
                converged = True
                break
        stable: set[OverflowFact]
        if converged:
            stable = set(facts_by_pass[-1]) if facts_by_pass else set()
        elif len(facts_by_pass) >= 2:
            stable = set(facts_by_pass[-2]) & set(facts_by_pass[-1])
        else:
            stable = set(facts_by_pass[-1]) if facts_by_pass else set()
        ordered = sorted(
            stable,
            key=lambda fact: (fact.module_path, fact.site, fact.operation, fact.target, fact.length),
        )
        return LengthAnalysisResult(state=state, overflow_facts=tuple(ordered), incomplete=not converged)

    def _initial_state(self, contexts: tuple[StringModuleContext, ...]) -> LengthState:
        state = LengthState()
        for context in contexts:
            aliases = frozenset(context.scope.param_mappings)
            for variable in declared_variables(context.node):
                if variable.name.casefold() in aliases:
                    continue
                slot = resolve_string_slot(context.scope, variable.name)
                if slot is None:
                    continue
                if is_string_datatype(variable.datatype):
                    init_value = variable.init_value
                    if isinstance(init_value, str):
                        state.strings[slot.key] = normalize_length(
                            (len(init_value),),
                            (len(init_value) + 1,),
                        )
                    else:
                        state.strings[slot.key] = unknown_length()
                elif variable.datatype is ScalarDatatype.INTEGER:
                    init_value = variable.init_value
                    if isinstance(init_value, int) and not isinstance(init_value, bool):
                        state.ints[slot.key] = normalize_int((init_value,))
                    else:
                        state.ints[slot.key] = IntValue()
            for binding in context.literal_bindings:
                target = resolve_string_target(context.scope, binding.target_ref)
                if target is None:
                    continue
                if isinstance(binding.source_literal, str):
                    state.strings[target.key] = normalize_length(
                        (len(binding.source_literal),),
                        (len(binding.source_literal) + 1,),
                    )
                elif isinstance(binding.source_literal, int) and not isinstance(binding.source_literal, bool):
                    state.ints[target.key] = normalize_int((binding.source_literal,))
        self._mark_unresolved_instance_targets(contexts, state)
        return state

    def _mark_unresolved_instance_targets(
        self,
        contexts: tuple[StringModuleContext, ...],
        state: LengthState,
    ) -> None:
        """A library we cannot see may write through any parameter it receives."""
        for context in contexts:
            if not isinstance(context.node, ModuleTypeInstance) or context.scope.env:
                continue
            for mapping in context.node.parametermappings or []:
                target = resolve_string_target(context.scope, mapping.source)
                if target is None:
                    continue
                if target.key in state.strings:
                    state.strings[target.key] = LengthValue(written=True)
                if target.key in state.ints:
                    state.ints[target.key] = IntValue()

    def _run_pass(
        self,
        contexts: tuple[StringModuleContext, ...],
        state: LengthState,
    ) -> tuple[LengthState, dict[OverflowFact, None]]:
        next_state = state.clone()
        facts: dict[OverflowFact, None] = {}
        written_strings: set[StringSlotKey] = set()
        written_ints: set[StringSlotKey] = set()
        for context in contexts:
            updates, context_facts = self._execute_context(context, state)
            for fact in context_facts:
                facts[fact] = None
            for key, value in updates.strings.items():
                if key in written_strings:
                    next_state.strings[key] = join_length(next_state.strings[key], value)
                else:
                    next_state.strings[key] = value
                    written_strings.add(key)
            for key, value in updates.ints.items():
                if key in written_ints:
                    next_state.ints[key] = join_int(next_state.ints[key], value)
                else:
                    next_state.ints[key] = value
                    written_ints.add(key)
        return next_state, facts

    def _execute_context(
        self,
        context: StringModuleContext,
        state: LengthState,
    ) -> tuple[LengthState, list[OverflowFact]]:
        code = module_code(context.node)
        if code is None:
            return LengthState(), []
        local = state.clone()
        facts: list[OverflowFact] = []
        for event in iter_statement_sites(code):
            local, statement_facts = self._execute_statement(event.node, local, context, event.site)
            facts.extend(statement_facts)
        changed_strings = {key: value for key, value in local.strings.items() if state.strings.get(key) != value}
        changed_ints = {key: value for key, value in local.ints.items() if state.ints.get(key) != value}
        return LengthState(strings=changed_strings, ints=changed_ints), facts

    def _execute_statements(
        self,
        statements: list[object],
        state: LengthState,
        context: StringModuleContext,
        site: str,
    ) -> tuple[LengthState, list[OverflowFact]]:
        current = state
        facts: list[OverflowFact] = []
        for statement in statements:
            current, statement_facts = self._execute_statement(statement, current, context, site)
            facts.extend(statement_facts)
        return current, facts

    def _execute_statement(
        self,
        statement: object,
        state: LengthState,
        context: StringModuleContext,
        site: str,
    ) -> tuple[LengthState, list[OverflowFact]]:
        if isinstance(statement, (list, tuple)):
            nested = cast("list[object] | tuple[object, ...]", statement)
            return self._execute_statements(list(nested), state, context, site)

        if isinstance(statement, Assignment):
            return self._execute_assignment(statement, state, context, site)

        if isinstance(statement, FuncCallStmt):
            return self._execute_call(statement.call, state, context, site)

        if isinstance(statement, IfStmt):
            branches: list[LengthState] = []
            facts: list[OverflowFact] = []
            for _condition, body in statement.branches:
                branch_state, branch_facts = self._execute_statements(list(body), state.clone(), context, site)
                branches.append(branch_state)
                facts.extend(branch_facts)
            if statement.else_block:
                else_state, else_facts = self._execute_statements(
                    list(statement.else_block), state.clone(), context, site
                )
                branches.append(else_state)
                facts.extend(else_facts)
            else:
                # The false path leaves every value as it was.
                branches.append(state.clone())
            if not branches:
                return state, facts
            merged = branches[0].clone()
            for branch in branches[1:]:
                for key, value in branch.strings.items():
                    merged.strings[key] = join_length(merged.strings.get(key, unknown_length()), value)
                for key, value in branch.ints.items():
                    merged.ints[key] = join_int(merged.ints.get(key, IntValue()), value)
            return merged, facts

        return state, []

    def _execute_assignment(
        self,
        statement: Assignment,
        state: LengthState,
        context: StringModuleContext,
        site: str,
    ) -> tuple[LengthState, list[OverflowFact]]:
        target = resolve_string_target(context.scope, statement.target)
        if target is None or not self._types.is_string(target):
            return state, []
        value = self._eval_string_expr(statement.value, state, context.scope)
        capacity = self._types.capacity(target)
        next_state = state.clone()
        if capacity is not None and value.known:
            overflowed = [length for length in value.lengths if length > capacity]
            if overflowed:
                if isinstance(statement.value, str):
                    # The static literal check owns this finding. Keep the slot
                    # unknown so later operations do not trust a truncated value.
                    next_state.strings[target.key] = unknown_length(written=True)
                    return next_state, []
                fact = OverflowFact(
                    module_path=display_path(context.path),
                    site=site,
                    operation="Assignment",
                    target=target.display_name,
                    capacity=capacity,
                    length=max(overflowed),
                    source=varname_full(statement.value),
                )
                return next_state, [fact]
        next_state.strings[target.key] = LengthValue(
            lengths=value.lengths,
            cursors=tuple(length + 1 for length in value.lengths),
            unknown=value.unknown,
            written=True,
        )
        return next_state, []

    def _execute_call(
        self,
        call: FuncCall,
        state: LengthState,
        context: StringModuleContext,
        site: str,
    ) -> tuple[LengthState, list[OverflowFact]]:
        name = call.name.casefold()
        args = list(call.args)
        next_state = state.clone()
        facts: list[OverflowFact] = []

        if name == "clearstring" and args:
            return self._write_clear(args[0], next_state, context), facts
        if name == "setstringpos" and len(args) >= 2:
            return self._write_cursor(args[0], args[1], next_state, context), facts
        if name == "cutstring" and len(args) >= 2:
            return self._write_cut(args[0], args[1], next_state, context), facts
        if name == "putblanks" and len(args) >= 2:
            return self._write_insert(
                args[0],
                args[1],
                None,
                next_state,
                context,
                site,
                "PutBlanks",
            )
        if name == "insertstring" and len(args) >= 3:
            return self._write_insert(
                args[0],
                args[2],
                args[1],
                next_state,
                context,
                site,
                "InsertString",
            )
        if name == "concatenate" and len(args) >= 3:
            return self._write_concatenate(args[0], args[1], args[2], next_state, context, site)
        if name in {"copystring", "copystringnosort"} and len(args) >= 2:
            return self._write_copy(args[0], args[1], next_state, context, site, call.name)
        if name in {"copyvariable", "copyvarnosort"} and len(args) >= 2:
            source = resolve_string_target(context.scope, args[0])
            target = resolve_string_target(context.scope, args[1])
            if (
                source is None
                or target is None
                or not self._types.is_string(source)
                or not self._types.is_string(target)
            ):
                return next_state, facts
            return self._write_copy(args[0], args[1], next_state, context, site, call.name)
        if name == "extractstring" and len(args) >= 3:
            return self._write_extract(args[0], args[1], args[2], next_state, context, site)
        if name in {"nationaluppercase", "nationallowercase"} and len(args) >= 2:
            return self._write_unknown(args[1], next_state, context), facts
        if name in {"integertostring", "realtostring"}:
            return self._write_number_text(call, next_state, context, site)

        return self._mark_unknown_call_targets(call, next_state, context), facts

    def _mark_unknown_call_targets(
        self,
        call: FuncCall,
        state: LengthState,
        context: StringModuleContext,
    ) -> LengthState:
        signature = resolve_call_signature(call.name)
        next_state = state
        for index, argument in enumerate(call.args):
            writes_argument = True
            if signature is not None and index < len(signature.parameters):
                writes_argument = signature.parameters[index].is_output
            if not writes_argument:
                continue
            target = resolve_string_target(context.scope, argument)
            if target is not None and self._types.is_string(target):
                next_state = self._write_unknown(argument, next_state, context)
        return next_state

    def _write_clear(
        self,
        target_arg: object,
        state: LengthState,
        context: StringModuleContext,
    ) -> LengthState:
        target = resolve_string_target(context.scope, target_arg)
        if target is None or not self._types.is_string(target):
            return state
        next_state = state.clone()
        next_state.strings[target.key] = normalize_length((0,), (1,))
        return next_state

    def _write_cursor(
        self,
        target_arg: object,
        position_arg: object,
        state: LengthState,
        context: StringModuleContext,
    ) -> LengthState:
        target = resolve_string_target(context.scope, target_arg)
        if target is None or not self._types.is_string(target):
            return state
        position = self._eval_int_expr(position_arg, state, context.scope)
        current = state.strings.get(target.key, unknown_length())
        if not position.known or not current.known:
            next_state = state.clone()
            next_state.strings[target.key] = LengthValue(
                lengths=current.lengths,
                cursors=current.cursors,
                unknown=True,
                written=current.written,
            )
            return next_state
        capacity = self._types.capacity(target)
        positions = tuple(value if capacity is None else min(max(value, 1), capacity + 1) for value in position.values)
        next_state = state.clone()
        next_state.strings[target.key] = normalize_length(
            current.lengths,
            positions,
            written=current.written,
        )
        return next_state

    def _write_cut(
        self,
        target_arg: object,
        length_arg: object,
        state: LengthState,
        context: StringModuleContext,
    ) -> LengthState:
        target = resolve_string_target(context.scope, target_arg)
        if target is None or not self._types.is_string(target):
            return state
        requested = self._eval_int_expr(length_arg, state, context.scope)
        current = state.strings.get(target.key, unknown_length())
        if not requested.known or not current.known:
            return state
        lengths: list[int] = []
        cursors: list[int] = []
        for length in current.lengths:
            for cursor in current.cursors:
                for amount in requested.values:
                    start = min(max(cursor, 1), length + 1) - 1
                    end = min(start + max(amount, 0), length)
                    lengths.append(length - (end - min(start, length)))
                    cursors.append(cursor)
        next_state = state.clone()
        next_state.strings[target.key] = normalize_length(lengths, cursors)
        return next_state

    def _write_insert(
        self,
        target_arg: object,
        length_arg: object,
        source_arg: object | None,
        state: LengthState,
        context: StringModuleContext,
        site: str,
        operation: str,
    ) -> tuple[LengthState, list[OverflowFact]]:
        target = resolve_string_target(context.scope, target_arg)
        if target is None or not self._types.is_string(target):
            return state, []
        capacity = self._types.capacity(target)
        current = state.strings.get(target.key, unknown_length())
        requested = self._eval_int_expr(length_arg, state, context.scope)
        source = self._eval_string_expr(source_arg, state, context.scope) if source_arg is not None else None
        if capacity is None or not current.known or not requested.known:
            return self._write_unknown(target_arg, state, context), []
        if source is not None and not source.known:
            return self._write_unknown(target_arg, state, context), []

        lengths: list[int] = []
        cursors: list[int] = []
        overflowed: list[int] = []
        source_lengths: tuple[int | None, ...] = source.lengths if source is not None else (None,)
        for length in current.lengths:
            for cursor in current.cursors:
                start = min(max(cursor, 1), length + 1) - 1
                for amount in requested.values:
                    for source_length in source_lengths:
                        insert_length = max(amount, 0)
                        if source_length is not None:
                            insert_length = min(insert_length, source_length)
                        new_length = start + insert_length if start >= length else length + insert_length
                        if new_length > capacity:
                            overflowed.append(new_length)
                            continue
                        lengths.append(new_length)
                        cursors.append(start + insert_length + 1)
        next_state = state.clone()
        if overflowed:
            # A failed procedure leaves the target unchanged. Keeping that value
            # lets the next pass reproduce the same finding instead of erasing it.
            fact = OverflowFact(
                module_path=display_path(context.path),
                site=site,
                operation=operation,
                target=target.display_name,
                capacity=capacity,
                length=max(overflowed),
                source=varname_full(source_arg) if source_arg is not None else None,
            )
            return next_state, [fact]
        next_state.strings[target.key] = normalize_length(lengths, cursors)
        return next_state, []

    def _write_concatenate(
        self,
        left_arg: object,
        right_arg: object,
        target_arg: object,
        state: LengthState,
        context: StringModuleContext,
        site: str,
    ) -> tuple[LengthState, list[OverflowFact]]:
        target = resolve_string_target(context.scope, target_arg)
        if target is None or not self._types.is_string(target):
            return state, []
        capacity = self._types.capacity(target)
        left = self._eval_string_expr(left_arg, state, context.scope)
        right = self._eval_string_expr(right_arg, state, context.scope)
        current = state.strings.get(target.key, unknown_length())
        if capacity is None or not left.known or not right.known or not current.known:
            return self._write_unknown(target_arg, state, context), []

        lengths: list[int] = []
        cursors: list[int] = []
        overflowed: list[int] = []
        for result_cursor in current.cursors:
            write_start = min(max(result_cursor, 1), capacity + 1) - 1
            for left_length in left.lengths:
                for left_cursor in left.cursors:
                    moved_left = max(0, left_length - (min(max(left_cursor, 1), left_length + 1) - 1))
                    for right_length in right.lengths:
                        for right_cursor in right.cursors:
                            moved_right = max(0, right_length - (min(max(right_cursor, 1), right_length + 1) - 1))
                            new_length = write_start + moved_left + moved_right
                            if new_length > capacity:
                                overflowed.append(new_length)
                                continue
                            lengths.append(new_length)
                            cursors.append(new_length + 1)
        next_state = state.clone()
        if overflowed:
            # A failed procedure leaves the target unchanged. Keeping that value
            # lets the next pass reproduce the same finding instead of erasing it.
            fact = OverflowFact(
                module_path=display_path(context.path),
                site=site,
                operation="Concatenate",
                target=target.display_name,
                capacity=capacity,
                length=max(overflowed),
                source=varname_full(left_arg),
            )
            return next_state, [fact]
        next_state.strings[target.key] = normalize_length(lengths, cursors)
        return next_state, []

    def _write_copy(
        self,
        source_arg: object,
        target_arg: object,
        state: LengthState,
        context: StringModuleContext,
        site: str,
        operation: str,
    ) -> tuple[LengthState, list[OverflowFact]]:
        target = resolve_string_target(context.scope, target_arg)
        if target is None or not self._types.is_string(target):
            return state, []
        capacity = self._types.capacity(target)
        source = self._eval_string_expr(source_arg, state, context.scope)
        if capacity is None or not source.known:
            return self._write_unknown(target_arg, state, context), []
        next_state = state.clone()
        overflowed = [length for length in source.lengths if length > capacity]
        if overflowed:
            # A failed procedure leaves the target unchanged. Keeping that value
            # lets the next pass reproduce the same finding instead of erasing it.
            fact = OverflowFact(
                module_path=display_path(context.path),
                site=site,
                operation=operation,
                target=target.display_name,
                capacity=capacity,
                length=max(overflowed),
                source=varname_full(source_arg),
            )
            return next_state, [fact]
        next_state.strings[target.key] = normalize_length(
            source.lengths,
            tuple(length + 1 for length in source.lengths),
        )
        return next_state, []

    def _write_extract(
        self,
        target_arg: object,
        source_arg: object,
        length_arg: object,
        state: LengthState,
        context: StringModuleContext,
        site: str,
    ) -> tuple[LengthState, list[OverflowFact]]:
        target = resolve_string_target(context.scope, target_arg)
        if target is None or not self._types.is_string(target):
            return state, []
        capacity = self._types.capacity(target)
        source = self._eval_string_expr(source_arg, state, context.scope)
        requested = self._eval_int_expr(length_arg, state, context.scope)
        if capacity is None or not source.known or not requested.known:
            return self._write_unknown(target_arg, state, context), []
        lengths: list[int] = []
        overflowed: list[int] = []
        for length in source.lengths:
            for cursor in source.cursors:
                start = min(max(cursor, 1), length + 1) - 1
                for amount in requested.values:
                    extracted = min(max(amount, 0), max(0, length - start))
                    if extracted > capacity:
                        overflowed.append(extracted)
                    else:
                        lengths.append(extracted)
        next_state = state.clone()
        if overflowed:
            # A failed procedure leaves the target unchanged. Keeping that value
            # lets the next pass reproduce the same finding instead of erasing it.
            fact = OverflowFact(
                module_path=display_path(context.path),
                site=site,
                operation="ExtractString",
                target=target.display_name,
                capacity=capacity,
                length=max(overflowed),
                source=varname_full(source_arg),
            )
            return next_state, [fact]
        next_state.strings[target.key] = normalize_length(lengths, (1,))
        return next_state, []

    def _write_number_text(
        self,
        call: FuncCall,
        state: LengthState,
        context: StringModuleContext,
        site: str,
    ) -> tuple[LengthState, list[OverflowFact]]:
        """Locate the output and width from the built-in signature.

        The width is a minimum field width, so a value longer than the width is
        also possible. Reporting only when the width itself exceeds the target
        capacity keeps the finding certain.
        """
        signature = resolve_call_signature(call.name)
        if signature is None:
            return self._mark_unknown_call_targets(call, state, context), []
        target_index = _parameter_index(signature, "string", direction="out")
        width_index = _parameter_index(signature, "width", direction="in")
        args = list(call.args)
        if target_index is None or width_index is None or len(args) <= max(target_index, width_index):
            return self._mark_unknown_call_targets(call, state, context), []
        return self._write_integer_text(
            args[target_index],
            args[width_index],
            state,
            context,
            site,
            call.name,
        )

    def _write_integer_text(
        self,
        target_arg: object,
        width_arg: object,
        state: LengthState,
        context: StringModuleContext,
        site: str,
        operation: str,
    ) -> tuple[LengthState, list[OverflowFact]]:
        target = resolve_string_target(context.scope, target_arg)
        if target is None or not self._types.is_string(target):
            return state, []
        capacity = self._types.capacity(target)
        width = self._eval_int_expr(width_arg, state, context.scope)
        if capacity is None or not width.known:
            return self._write_unknown(target_arg, state, context), []
        lengths = [max(value, 0) for value in width.values]
        overflowed = [length for length in lengths if length > capacity]
        next_state = state.clone()
        if overflowed:
            # A failed procedure leaves the target unchanged. Keeping that value
            # lets the next pass reproduce the same finding instead of erasing it.
            fact = OverflowFact(
                module_path=display_path(context.path),
                site=site,
                operation=operation,
                target=target.display_name,
                capacity=capacity,
                length=max(overflowed),
            )
            return next_state, [fact]
        next_state.strings[target.key] = normalize_length(lengths, (length + 1 for length in lengths))
        return next_state, []

    def _write_unknown(
        self,
        target_arg: object,
        state: LengthState,
        context: StringModuleContext,
    ) -> LengthState:
        target = resolve_string_target(context.scope, target_arg)
        if target is None or not self._types.is_string(target):
            return state
        next_state = state.clone()
        next_state.strings[target.key] = unknown_length(written=True)
        return next_state


def _parameter_index(signature: CallSignature, name: str, *, direction: str) -> int | None:
    for index, parameter in enumerate(signature.parameters):
        if parameter.name.casefold() == name and parameter.direction == direction:
            return index
    return None


__all__ = [
    "IntValue",
    "LengthAnalysisResult",
    "LengthAnalyzer",
    "LengthState",
    "LengthValue",
    "OverflowFact",
    "join_int",
    "join_length",
    "normalize_int",
    "normalize_length",
    "unknown_length",
]
