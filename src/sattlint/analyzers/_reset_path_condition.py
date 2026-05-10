"""Condition classification helpers for reset contamination path collection."""

from __future__ import annotations

from typing import Any

from ..grammar import constants as const
from ._reset_path_state import _PathState


def _varref_casefold(obj: Any) -> str | None:
    if not isinstance(obj, dict) or const.KEY_VAR_NAME not in obj:
        return None
    full = obj[const.KEY_VAR_NAME]
    if not isinstance(full, str) or not full:
        return None
    return full.casefold()


def _is_exact_run_condition(cond: Any, reset_ref_cf: str) -> bool:
    return (
        isinstance(cond, tuple)
        and len(cond) == 2
        and cond[0] == const.GRAMMAR_VALUE_NOT
        and _varref_casefold(cond[1]) == reset_ref_cf
    )


def _is_exact_reset_condition(cond: Any, reset_ref_cf: str, reset_old_vars_cf: set[str]) -> bool:
    if _varref_casefold(cond) == reset_ref_cf:
        return True
    return (
        isinstance(cond, tuple)
        and len(cond) == 2
        and cond[0] == const.GRAMMAR_VALUE_NOT
        and _varref_casefold(cond[1]) in reset_old_vars_cf
    )


def _classify_reset_condition(cond: Any, reset_ref_cf: str, reset_old_vars_cf: set[str]) -> dict[str, bool]:
    positives: set[str] = set()
    negatives: set[str] = set()

    def visit(obj: Any, negated: bool) -> None:
        if obj is None:
            return
        if isinstance(obj, dict) and const.KEY_VAR_NAME in obj:
            full = obj[const.KEY_VAR_NAME]
            if isinstance(full, str) and full:
                name_cf = full.casefold()
                if name_cf == reset_ref_cf or name_cf in reset_old_vars_cf:
                    if negated:
                        negatives.add(name_cf)
                    else:
                        positives.add(name_cf)
            return
        if isinstance(obj, tuple) and obj:
            if obj[0] == const.GRAMMAR_VALUE_NOT:
                visit(obj[1], not negated)
                return
            for item in obj[1:]:
                visit(item, negated)
            return
        if isinstance(obj, list):
            for item in obj:
                visit(item, negated)
            return
        if hasattr(obj, "children"):
            for child in getattr(obj, "children", []):
                visit(child, negated)

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
