"""Condition classification helpers for reset contamination path collection."""

from __future__ import annotations

from typing import Any

from sattlint.parser_api import NotOp, VarRef

from ._reset_path_state import PathState as _PathState


def _varref_casefold(obj: Any) -> str | None:
    if isinstance(obj, VarRef) and obj.name:
        return obj.name.casefold()
    return None


def _is_exact_run_condition(cond: Any, reset_ref_cf: str) -> bool:
    if isinstance(cond, NotOp):
        return _varref_casefold(cond.operand) == reset_ref_cf
    return False


def _is_exact_reset_condition(cond: Any, reset_ref_cf: str, reset_old_vars_cf: set[str]) -> bool:
    if isinstance(cond, NotOp):
        return _varref_casefold(cond.operand) in reset_old_vars_cf
    return _varref_casefold(cond) == reset_ref_cf


def _classify_reset_condition(cond: Any, reset_ref_cf: str, reset_old_vars_cf: set[str]) -> dict[str, bool]:
    positives: set[str] = set()
    negatives: set[str] = set()

    def visit(obj: object, negated: bool) -> None:
        if obj is None:
            return
        if isinstance(obj, VarRef):
            if obj.name:
                name_cf = obj.name.casefold()
                if name_cf == reset_ref_cf or name_cf in reset_old_vars_cf:
                    if negated:
                        negatives.add(name_cf)
                    else:
                        positives.add(name_cf)
            return
        if isinstance(obj, NotOp):
            visit(obj.operand, not negated)

    visit(cond, False)

    return {
        "run": reset_ref_cf in negatives,
        "reset": reset_ref_cf in positives or bool(negatives & reset_old_vars_cf),
        "exact_run": _is_exact_run_condition(cond, reset_ref_cf),
        "exact_reset": _is_exact_reset_condition(cond, reset_ref_cf, reset_old_vars_cf),
    }


def _take_condition_branch(state: _PathState, cond_flags: dict[str, bool]) -> list[_PathState]:
    if cond_flags["run"] and not cond_flags["reset"]:
        return _clone_with_reset_state(state, "run")
    if cond_flags["reset"] and not cond_flags["run"]:
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
