"""Condition classification helpers for reset contamination path collection."""

from __future__ import annotations

from dataclasses import dataclass

from sattlint.parser_api import BoolOp, NotOp, VarRef

from ._reset_path_state import PathState as _PathState


@dataclass(frozen=True, slots=True)
class ResetConditionFlags:
    """What one guard guarantees about the reset state of its branch.

    ``run`` and ``reset`` are guarantees, not hints: a flag is set only when
    every way the guard can be true puts the branch in that state. A compound
    guard such as ``Seq.Reset AND Guard`` therefore guarantees the reset state,
    while ``Seq.Reset OR Guard`` guarantees neither.
    """

    run: bool = False
    reset: bool = False
    exact_run: bool = False
    exact_reset: bool = False


def _varref_casefold(node: object) -> str | None:
    if isinstance(node, VarRef) and node.name:
        return node.name.casefold()
    return None


def _is_exact_run_condition(cond: object, reset_ref_cf: str) -> bool:
    if isinstance(cond, NotOp):
        return _varref_casefold(cond.operand) == reset_ref_cf
    return False


def _is_exact_reset_condition(cond: object, reset_ref_cf: str, reset_old_vars_cf: set[str]) -> bool:
    if isinstance(cond, NotOp):
        return _varref_casefold(cond.operand) in reset_old_vars_cf
    return _varref_casefold(cond) == reset_ref_cf


def _atomic_guarantees(
    node: VarRef, negated: bool, reset_ref_cf: str, reset_old_vars_cf: set[str]
) -> tuple[bool, bool]:
    """Return ``(run, reset)`` for one reference, honouring the negation."""
    name_cf = _varref_casefold(node)
    if name_cf == reset_ref_cf:
        return (True, False) if negated else (False, True)
    if name_cf in reset_old_vars_cf:
        return (False, True) if negated else (False, False)
    return (False, False)


def _condition_guarantees(
    cond: object,
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    *,
    negated: bool = False,
) -> tuple[bool, bool]:
    if isinstance(cond, VarRef):
        return _atomic_guarantees(cond, negated, reset_ref_cf, reset_old_vars_cf)
    if isinstance(cond, NotOp):
        operand = cond.operand
        if isinstance(operand, VarRef | NotOp):
            return _condition_guarantees(operand, reset_ref_cf, reset_old_vars_cf, negated=not negated)
        # Negating a compound guard (``NOT (A AND B)``) guarantees nothing:
        # the guard is true whenever any operand is false.
        return (False, False)
    if isinstance(cond, BoolOp):
        results = [
            _condition_guarantees(operand, reset_ref_cf, reset_old_vars_cf, negated=negated)
            for operand in cond.operands
        ]
        if cond.op == "AND":
            return (any(run for run, _reset in results), any(reset for _run, reset in results))
        return (all(run for run, _reset in results), all(reset for _run, reset in results))
    return (False, False)


def _classify_reset_condition(
    cond: object,
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
) -> ResetConditionFlags:
    run, reset = _condition_guarantees(cond, reset_ref_cf, reset_old_vars_cf)
    return ResetConditionFlags(
        run=run,
        reset=reset,
        exact_run=_is_exact_run_condition(cond, reset_ref_cf),
        exact_reset=_is_exact_reset_condition(cond, reset_ref_cf, reset_old_vars_cf),
    )


def _take_condition_branch(state: _PathState, flags: ResetConditionFlags) -> list[_PathState]:
    if flags.run and not flags.reset:
        return _clone_with_reset_state(state, "run")
    if flags.reset and not flags.run:
        return _clone_with_reset_state(state, "reset")
    return [state.clone()]


def _clone_with_reset_state(state: _PathState, reset_state: str) -> list[_PathState]:
    if state.reset_state != "unknown" and state.reset_state != reset_state:
        return []
    clone = state.clone()
    clone.reset_state = reset_state
    return [clone]


def _infer_alternative_states(
    state: _PathState,
    *,
    saw_run: bool,
    saw_reset: bool,
    saw_exact_run: bool,
    saw_exact_reset: bool,
) -> list[_PathState]:
    if saw_exact_run and saw_exact_reset:
        return []
    if saw_exact_run and not saw_reset:
        return _clone_with_reset_state(state, "reset")
    if saw_exact_reset and not saw_run:
        return _clone_with_reset_state(state, "run")
    if saw_run ^ saw_reset:
        if state.reset_state == "unknown":
            return _clone_with_reset_state(state, "run") + _clone_with_reset_state(state, "reset")
        return [state.clone()]
    return [state.clone()]


varref_casefold = _varref_casefold
is_exact_run_condition = _is_exact_run_condition
is_exact_reset_condition = _is_exact_reset_condition
classify_reset_condition = _classify_reset_condition
take_condition_branch = _take_condition_branch
clone_with_reset_state = _clone_with_reset_state
infer_alternative_states = _infer_alternative_states
