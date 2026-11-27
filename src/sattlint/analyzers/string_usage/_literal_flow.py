"""Literal and constant string lengths, without dataflow.

The analyzers only claim what the source states outright: a literal, or a local
whose writes in the same module are literals. A value is never carried across a
module boundary, a parameter mapping, or a branch, and nothing is iterated to a
fixed point. One module's analysis is therefore proportional to its own
statements, which is what keeps a large project's run to seconds.

The cost of that choice is deliberate: a length that only a whole-program
analysis could know is not reported.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace

from sattlint.parser_api import Assignment, FuncCall, FuncCallStmt, IfStmt, ModuleCode

from ...resolution.common import varname_full
from .._string_models import StringSlot, StringSlotKey
from ..shared._string_capacity import is_string_datatype
from ..shared.statement_sites import iter_statement_sites
from ..string_contexts import (
    StringModuleContext,
    declared_variables,
    module_code,
    resolve_string_slot,
    resolve_string_target,
)
from ._model import OverflowFact, SlotTypes, statement_path

__all__ = ["LiteralFlowResult", "analyze_literal_flow"]


@dataclass(frozen=True, slots=True)
class LiteralFlowResult:
    """What one literal pass could and could not establish."""

    facts: tuple[OverflowFact, ...] = ()
    #: The longest literal written to each slot in its own module.
    observed: Mapping[StringSlotKey, int] = field(default_factory=dict[StringSlotKey, int])
    #: Slots that received a value this pass cannot know.
    tainted: frozenset[StringSlotKey] = frozenset()


@dataclass(slots=True)
class _ModuleRun:
    """One module's literal knowledge."""

    context: StringModuleContext
    types: SlotTypes
    known: dict[StringSlotKey, int]
    observed: dict[StringSlotKey, int]
    tainted: set[StringSlotKey]
    facts: dict[OverflowFact, None]


def analyze_literal_flow(
    contexts: Iterable[StringModuleContext],
    *,
    types: SlotTypes,
) -> LiteralFlowResult:
    observed: dict[StringSlotKey, int] = {}
    tainted: set[StringSlotKey] = set()
    facts: dict[OverflowFact, None] = {}
    for context in contexts:
        run = _ModuleRun(
            context=context,
            types=types,
            known={},
            observed=observed,
            tainted=tainted,
            facts=facts,
        )
        _seed_declarations(run)
        code = module_code(context.node)
        if code is not None:
            _execute_code(code, run)
    return LiteralFlowResult(
        facts=tuple(sorted(facts, key=_fact_order)),
        observed=dict(observed),
        tainted=frozenset(tainted),
    )


def _fact_order(fact: OverflowFact) -> tuple[object, ...]:
    return (fact.module_path, fact.site, fact.operation, fact.target, fact.length)


def _seed_declarations(run: _ModuleRun) -> None:
    context = run.context
    for variable in declared_variables(context.node):
        if not is_string_datatype(variable.datatype):
            continue
        slot = resolve_string_slot(context.scope, variable.name)
        if slot is None or not run.types.is_string(slot):
            continue
        init_value = variable.init_value
        if isinstance(init_value, str):
            run.known[slot.key] = len(init_value)
            _observe(run, slot.key, len(init_value))
    for binding in context.literal_bindings:
        target = resolve_string_target(context.scope, binding.target_ref)
        if target is None or not run.types.is_string(target):
            continue
        if isinstance(binding.source_literal, str):
            run.known[target.key] = len(binding.source_literal)
            _observe(run, target.key, len(binding.source_literal))


def _observe(run: _ModuleRun, key: StringSlotKey, length: int) -> None:
    run.observed[key] = max(run.observed.get(key, 0), length)


def _execute_code(code: ModuleCode, run: _ModuleRun) -> set[StringSlotKey]:
    written: set[StringSlotKey] = set()
    for event in iter_statement_sites(code):
        written |= _execute_statement(event.node, run, event.site)
    return written


def _execute_statements(statements: Sequence[object], run: _ModuleRun, site: str) -> set[StringSlotKey]:
    written: set[StringSlotKey] = set()
    for statement in statements:
        written |= _execute_statement(statement, run, site)
    return written


def _execute_statement(statement: object, run: _ModuleRun, site: str) -> set[StringSlotKey]:
    if isinstance(statement, Assignment):
        return _execute_assignment(statement, run, site)
    if isinstance(statement, FuncCallStmt):
        return _execute_call(statement.call, run, site)
    if isinstance(statement, IfStmt):
        return _execute_if(statement, run, site)
    return set()


def _execute_if(statement: IfStmt, run: _ModuleRun, site: str) -> set[StringSlotKey]:
    written: set[StringSlotKey] = set()
    for _condition, body in statement.branches:
        branch = replace(run, known=dict(run.known))
        written |= _execute_statements(list(body), branch, site)
    if statement.else_block:
        branch = replace(run, known=dict(run.known))
        written |= _execute_statements(list(statement.else_block), branch, site)
    # A value that only one branch wrote is not the module's value afterwards.
    for key in written:
        run.known.pop(key, None)
    return written


def _execute_assignment(statement: Assignment, run: _ModuleRun, site: str) -> set[StringSlotKey]:
    target = resolve_string_target(run.context.scope, statement.target)
    if target is None or not run.types.is_string(target):
        return set()
    length = _known_length(statement.value, run)
    if length is None:
        return _forget(run, target)
    if not isinstance(statement.value, str):
        # A literal assignment is the literal check's finding, not this pass's.
        _record(
            run, target, site=site, operation="Assignment", length=length, source=varname_full(statement.value) or None
        )
    run.known[target.key] = length
    _observe(run, target.key, length)
    return {target.key}


def _forget(run: _ModuleRun, target: StringSlot) -> set[StringSlotKey]:
    run.known.pop(target.key, None)
    run.tainted.add(target.key)
    return {target.key}


def _known_length(expression: object, run: _ModuleRun) -> int | None:
    if isinstance(expression, str):
        return len(expression)
    slot = resolve_string_target(run.context.scope, expression)
    if slot is None:
        return None
    return run.known.get(slot.key)


def _literal_int(expression: object) -> int | None:
    if isinstance(expression, int) and not isinstance(expression, bool) and expression >= 0:
        return expression
    return None


def _argument_slot(args: Sequence[object], index: int, run: _ModuleRun) -> StringSlot | None:
    if index >= len(args):
        return None
    slot = resolve_string_target(run.context.scope, args[index])
    if slot is None or not run.types.is_string(slot):
        return None
    return slot


def _execute_call(call: FuncCall, run: _ModuleRun, site: str) -> set[StringSlotKey]:
    name = call.name.casefold()
    args = list(call.args)
    handler = _CALL_HANDLERS.get(name)
    if handler is not None:
        return handler(args, run, site)
    # A procedure this pass does not model may write anything into its string
    # arguments, so their values stop being known.
    written: set[StringSlotKey] = set()
    for index in range(len(args)):
        slot = _argument_slot(args, index, run)
        if slot is not None:
            written |= _forget(run, slot)
    return written


def _record(
    run: _ModuleRun,
    target: StringSlot,
    *,
    site: str,
    operation: str,
    length: int,
    source: str | None = None,
) -> None:
    capacity = run.types.capacity(target)
    if capacity is None or length <= capacity:
        return
    run.facts[
        OverflowFact(
            module_path=statement_path(run.context),
            site=site,
            operation=operation,
            target=target.display_name,
            capacity=capacity,
            length=length,
            source=source,
        )
    ] = None


def _clear_string(args: Sequence[object], run: _ModuleRun, site: str) -> set[StringSlotKey]:
    target = _argument_slot(args, 0, run)
    if target is None:
        return set()
    run.known[target.key] = 0
    _observe(run, target.key, 0)
    return {target.key}


def _write_fixed_length(
    args: Sequence[object],
    run: _ModuleRun,
    site: str,
    *,
    operation: str,
    count_index: int,
) -> set[StringSlotKey]:
    target = _argument_slot(args, 0, run)
    if target is None:
        return set()
    count = _literal_int(args[count_index]) if count_index < len(args) else None
    if count is None:
        return _forget(run, target)
    _record(run, target, site=site, operation=operation, length=count)
    run.known[target.key] = count
    _observe(run, target.key, count)
    return {target.key}


def _read_only(args: Sequence[object], run: _ModuleRun, site: str) -> set[StringSlotKey]:
    return set()


def _insert_string(args: Sequence[object], run: _ModuleRun, site: str) -> set[StringSlotKey]:
    target = _argument_slot(args, 0, run)
    if target is None:
        return set()
    source_length = _known_length(args[1], run) if len(args) > 1 else None
    position = _literal_int(args[2]) if len(args) > 2 else None
    if source_length is None or position is None:
        return _forget(run, target)
    length = max(run.known.get(target.key, 0), position + source_length)
    _record(run, target, site=site, operation="InsertString", length=length)
    run.known[target.key] = length
    _observe(run, target.key, length)
    return {target.key}


def _put_blanks(args: Sequence[object], run: _ModuleRun, site: str) -> set[StringSlotKey]:
    return _write_fixed_length(args, run, site, operation="PutBlanks", count_index=1)


def _extract_string(args: Sequence[object], run: _ModuleRun, site: str) -> set[StringSlotKey]:
    return _write_fixed_length(args, run, site, operation="ExtractString", count_index=2)


def _integer_to_string(args: Sequence[object], run: _ModuleRun, site: str) -> set[StringSlotKey]:
    return _write_fixed_length(args, run, site, operation="IntegerToString", count_index=2)


def _copy_string(args: Sequence[object], run: _ModuleRun, site: str) -> set[StringSlotKey]:
    target = _argument_slot(args, 1, run)
    if target is None:
        return set()
    length = _known_length(args[0], run) if args else None
    if length is None:
        return _forget(run, target)
    _record(run, target, site=site, operation="CopyString", length=length, source=varname_full(args[0]) or None)
    run.known[target.key] = length
    _observe(run, target.key, length)
    return {target.key}


def _concatenate(args: Sequence[object], run: _ModuleRun, site: str) -> set[StringSlotKey]:
    target = _argument_slot(args, 2, run)
    if target is None:
        return set()
    left = _known_length(args[0], run) if len(args) > 0 else None
    right = _known_length(args[1], run) if len(args) > 1 else None
    if left is None or right is None:
        return _forget(run, target)
    length = left + right
    _record(run, target, site=site, operation="Concatenate", length=length)
    run.known[target.key] = length
    _observe(run, target.key, length)
    return {target.key}


_CALL_HANDLERS = {
    "clearstring": _clear_string,
    "setstringpos": _read_only,
    "getstringpos": _read_only,
    "stringlength": _read_only,
    "maxstringlength": _read_only,
    "insertstring": _insert_string,
    "putblanks": _put_blanks,
    "extractstring": _extract_string,
    "integertostring": _integer_to_string,
    "integerstring": _integer_to_string,
    "copystring": _copy_string,
    "copyvariable": _copy_string,
    "copyvarnosort": _copy_string,
    "concatenate": _concatenate,
}
