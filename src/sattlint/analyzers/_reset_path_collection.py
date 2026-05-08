"""Internal helpers for reset contamination path collection."""

from __future__ import annotations

from typing import Any

from sattline_parser.models.ast_model import (
    ModuleCode,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Variable,
)

from ..grammar import constants as const
from ._reset_path_state import (
    WriteKey,
    WriteMap,
    _compact_path_states,
    _merge_parallel_branch_results,
    _PathCollectionDebug,
    _PathState,
)
from .sattline_builtins import get_function_signature


def _collect_paths_in_modulecode(
    modulecode: ModuleCode,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    states = [_PathState()]

    for eq in modulecode.equations or []:
        states = _collect_stmt_block_paths(
            eq.code or [],
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    for seq in modulecode.sequences or []:
        states = _collect_seq_block_paths(
            seq.code or [],
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    return _compact_path_states(states, debug=path_debug, site="modulecode")


def _collect_seq_block_paths(
    nodes: list[Any],
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    next_states = states
    for node in nodes:
        next_states = _collect_seq_node_paths(
            node,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            next_states,
            path_debug=path_debug,
        )
    return next_states


def _collect_seq_node_paths(
    node: Any,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    if isinstance(node, SFCStep):
        next_states = _collect_stmt_block_paths(
            node.code.enter or [],
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )
        next_states = _collect_stmt_block_paths(
            node.code.active or [],
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            next_states,
            path_debug=path_debug,
        )
        result = _collect_stmt_block_paths(
            node.code.exit or [],
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            next_states,
            path_debug=path_debug,
        )
        result = _compact_path_states(result, debug=path_debug, site=f"seq-node:step:{getattr(node, 'name', '<unnamed>')}")
        if path_debug is not None:
            path_debug.emit(
                "collect-seq-node-paths",
                node_type="step",
                node_name=getattr(node, "name", "<unnamed>"),
                input_count=len(states),
                output_count=len(result),
            )
        return result

    if isinstance(node, SFCTransition):
        return states

    if isinstance(node, SFCAlternative):
        if not node.branches:
            return states
        alternative_states: list[_PathState] = []
        for state in states:
            for branch in node.branches or []:
                alternative_states.extend(
                    _collect_seq_block_paths(
                        branch or [],
                        env,
                        reset_ref_cf,
                        reset_old_vars_cf,
                        [state.clone()],
                        path_debug=path_debug,
                    )
                )
        result = _compact_path_states(
            alternative_states or states,
            debug=path_debug,
            site="seq-node:alternative",
        )
        if path_debug is not None:
            path_debug.emit(
                "collect-seq-node-paths",
                node_type="alternative",
                input_count=len(states),
                branch_count=len(node.branches or []),
                output_count=len(result),
            )
        return result

    if isinstance(node, SFCParallel):
        if not node.branches:
            return states
        parallel_states: list[_PathState] = []
        for state in states:
            branch_results = [
                _collect_seq_block_paths(
                    branch or [],
                    env,
                    reset_ref_cf,
                    reset_old_vars_cf,
                    [state.clone()],
                    path_debug=path_debug,
                )
                for branch in node.branches or []
            ]
            parallel_states.extend(
                _merge_parallel_branch_results(
                    branch_results,
                    debug=path_debug,
                )
            )
        result = _compact_path_states(
            parallel_states or states,
            debug=path_debug,
            site="seq-node:parallel",
        )
        if path_debug is not None:
            path_debug.emit(
                "collect-seq-node-paths",
                node_type="parallel",
                input_count=len(states),
                branch_count=len(node.branches or []),
                output_count=len(result),
            )
        return result

    if isinstance(node, SFCSubsequence):
        result = _collect_seq_block_paths(
            node.body or [],
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )
        if path_debug is not None:
            path_debug.emit(
                "collect-seq-node-paths",
                node_type="subsequence",
                node_name=getattr(node, "name", "<unnamed>"),
                input_count=len(states),
                output_count=len(result),
            )
        return result

    if isinstance(node, SFCTransitionSub):
        result = _collect_seq_block_paths(
            node.body or [],
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )
        if path_debug is not None:
            path_debug.emit(
                "collect-seq-node-paths",
                node_type="transition-sub",
                node_name=getattr(node, "name", "<unnamed>"),
                input_count=len(states),
                output_count=len(result),
            )
        return result

    return states


def _collect_stmt_block_paths(
    stmts: list[Any],
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    return _collect_paths_from_items(
        stmts,
        env,
        reset_ref_cf,
        reset_old_vars_cf,
        states,
        path_debug=path_debug,
    )


def _collect_paths_from_items(
    items: list[Any],
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    next_states = states
    for stmt in items:
        next_states = _collect_stmt_paths(
            stmt,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            next_states,
            path_debug=path_debug,
        )
        next_states = _compact_path_states(next_states, debug=path_debug, site="stmt-items")
    return next_states


def _collect_if_stmt_paths(
    branches: list[tuple[Any, list[Any]]] | None,
    else_block: list[Any] | None,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    branch_outcomes: list[_PathState] = []
    for state in states:
        saw_run = False
        saw_reset = False
        saw_exact_run = False
        saw_exact_reset = False
        branch_matched = False

        for cond, stmts in branches or []:
            cond_flags = _classify_reset_condition(cond, reset_ref_cf, reset_old_vars_cf)
            saw_run = saw_run or cond_flags["run"]
            saw_reset = saw_reset or cond_flags["reset"]
            saw_exact_run = saw_exact_run or cond_flags["exact_run"]
            saw_exact_reset = saw_exact_reset or cond_flags["exact_reset"]

            branch_states = _take_condition_branch(state, cond_flags)
            if not branch_states:
                continue
            branch_matched = True
            branch_outcomes.extend(
                _collect_stmt_block_paths(
                    stmts or [],
                    env,
                    reset_ref_cf,
                    reset_old_vars_cf,
                    branch_states,
                    path_debug=path_debug,
                )
            )

        fallback_states = _infer_alternative_states(
            state,
            saw_run=saw_run,
            saw_reset=saw_reset,
            saw_exact_run=saw_exact_run,
            saw_exact_reset=saw_exact_reset,
        )
        if else_block:
            if fallback_states:
                branch_outcomes.extend(
                    _collect_stmt_block_paths(
                        else_block or [],
                        env,
                        reset_ref_cf,
                        reset_old_vars_cf,
                        fallback_states,
                        path_debug=path_debug,
                    )
                )
        elif fallback_states or not branch_matched:
            branch_outcomes.extend(fallback_states or [state.clone()])
    result = _compact_path_states(branch_outcomes or states, debug=path_debug, site="if-stmt")
    if path_debug is not None:
        path_debug.emit(
            "collect-if-stmt-paths",
            input_count=len(states),
            branch_count=len(branches or []),
            output_count=len(result),
            has_else=else_block is not None,
        )
    return result


def _collect_assignment_paths(
    target: Any,
    expr: Any,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    assigned_states: list[_PathState] = []
    for state in states:
        next_state = state.clone()
        _record_mode_write(target, env, next_state)
        assigned_states.extend(
            _collect_stmt_paths(
                expr,
                env,
                reset_ref_cf,
                reset_old_vars_cf,
                [next_state],
                path_debug=path_debug,
            )
        )
    return _compact_path_states(assigned_states, debug=path_debug, site="assignment")


def _collect_function_call_paths(
    fn_name: str,
    args: list[Any] | None,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    call_states: list[_PathState] = []
    for state in states:
        next_state = state.clone()
        _record_mode_function_call_writes(fn_name, args or [], env, next_state)
        arg_states = _collect_paths_from_items(
            list(args or []),
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            [next_state],
            path_debug=path_debug,
        )
        call_states.extend(arg_states)
    result = _compact_path_states(
        call_states,
        debug=path_debug,
        site=f"function-call:{fn_name.casefold()}",
    )
    if path_debug is not None:
        path_debug.emit(
            "collect-function-call-paths",
            function_name=fn_name,
            input_count=len(states),
            arg_count=len(args or []),
            output_count=len(result),
        )
    return result


def _collect_stmt_paths(
    obj: Any,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    if obj is None:
        return states
    if hasattr(obj, "data") and obj.data == const.KEY_STATEMENT:
        return _collect_paths_from_items(
            list(getattr(obj, "children", [])),
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
        _, branches, else_block = obj
        return _collect_if_stmt_paths(
            branches,
            else_block,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
        _, target, expr = obj
        return _collect_assignment_paths(
            target,
            expr,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
        _, fn_name, args = obj
        return _collect_function_call_paths(
            fn_name,
            args,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_TERNARY, "Ternary"):
        _, branches, else_expr = obj
        next_states = states
        for cond, then_expr in branches or []:
            next_states = _collect_stmt_paths(
                cond,
                env,
                reset_ref_cf,
                reset_old_vars_cf,
                next_states,
                path_debug=path_debug,
            )
            next_states = _collect_stmt_paths(
                then_expr,
                env,
                reset_ref_cf,
                reset_old_vars_cf,
                next_states,
                path_debug=path_debug,
            )
        if else_expr is not None:
            next_states = _collect_stmt_paths(
                else_expr,
                env,
                reset_ref_cf,
                reset_old_vars_cf,
                next_states,
                path_debug=path_debug,
            )
        return next_states

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_COMPARE, "compare"):
        _, left, pairs = obj
        next_states = _collect_stmt_paths(
            left,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )
        for _sym, rhs in pairs or []:
            next_states = _collect_stmt_paths(
                rhs,
                env,
                reset_ref_cf,
                reset_old_vars_cf,
                next_states,
                path_debug=path_debug,
            )
        return next_states

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_ADD, const.KEY_MUL):
        _, left, parts = obj
        next_states = _collect_stmt_paths(
            left,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )
        for _opval, rhs in parts or []:
            next_states = _collect_stmt_paths(
                rhs,
                env,
                reset_ref_cf,
                reset_old_vars_cf,
                next_states,
                path_debug=path_debug,
            )
        return next_states

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_PLUS, const.KEY_MINUS):
        return _collect_stmt_paths(
            obj[1],
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, tuple) and obj and obj[0] in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND):
        return _collect_paths_from_items(
            list(obj[1] or []),
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_NOT:
        return _collect_stmt_paths(
            obj[1],
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if isinstance(obj, list):
        return _collect_paths_from_items(
            obj,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    if hasattr(obj, "children"):
        return _collect_paths_from_items(
            list(getattr(obj, "children", [])),
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            path_debug=path_debug,
        )

    return states


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


def _varref_casefold(obj: Any) -> str | None:
    if not isinstance(obj, dict) or const.KEY_VAR_NAME not in obj:
        return None
    full = obj[const.KEY_VAR_NAME]
    if not isinstance(full, str) or not full:
        return None
    return full.casefold()


def _take_condition_branch(state: _PathState, cond_flags: dict[str, bool]) -> list[_PathState]:
    if cond_flags["run"] and not cond_flags["reset"]:
        return _clone_with_reset_state(state, "run")
    if cond_flags["reset"] and not cond_flags["run"]:
        return _clone_with_reset_state(state, "reset")
    return [state.clone()]


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


def _clone_with_reset_state(state: _PathState, reset_state: str) -> list[_PathState]:
    if state.reset_state != "unknown" and state.reset_state != reset_state:
        return []
    clone = state.clone()
    clone.reset_state = reset_state
    return [clone]


def _path_covers_write(reset_writes: WriteMap, key: WriteKey) -> bool:
    var_key, _field_key = key
    return key in reset_writes or (var_key, "") in reset_writes


def _record_mode_write(target: Any, env: dict[str, Variable], state: _PathState) -> None:
    bucket = state.reset_writes if state.reset_state == "reset" else state.run_writes
    _record_write(target, env, bucket)


def _record_mode_function_call_writes(
    fn_name: str,
    args: list[Any],
    env: dict[str, Variable],
    state: _PathState,
) -> None:
    bucket = state.reset_writes if state.reset_state == "reset" else state.run_writes
    _record_function_call_writes(fn_name, args, env, bucket)


def _split_var_ref(full_ref: str) -> tuple[str, str]:
    if not full_ref:
        return "", ""
    if "." not in full_ref:
        return full_ref, ""
    base, field_path = full_ref.split(".", 1)
    return base, field_path


def _record_write(target: Any, env: dict[str, Variable], out: WriteMap) -> None:
    if not isinstance(target, dict) or const.KEY_VAR_NAME not in target:
        return
    full_ref = target[const.KEY_VAR_NAME]
    if not isinstance(full_ref, str) or not full_ref:
        return
    base, field_path = _split_var_ref(full_ref)
    if not base:
        return
    var = env.get(base.casefold())
    if var is None:
        return
    field_path = field_path or ""
    out[(var.name.casefold(), field_path.casefold())] = (var, field_path)


def _record_function_call_writes(
    fn_name: str,
    args: list[Any],
    env: dict[str, Variable],
    out: WriteMap,
) -> None:
    sig = get_function_signature(fn_name)
    if sig is None:
        return
    for idx, arg in enumerate(args):
        if idx >= len(sig.parameters):
            break
        direction = sig.parameters[idx].direction
        if direction not in ("out", "inout"):
            continue
        if isinstance(arg, dict) and const.KEY_VAR_NAME in arg:
            _record_write(arg, env, out)


classify_reset_condition = _classify_reset_condition
clone_with_reset_state = _clone_with_reset_state
collect_assignment_paths = _collect_assignment_paths
collect_function_call_paths = _collect_function_call_paths
collect_if_stmt_paths = _collect_if_stmt_paths
collect_paths_from_items = _collect_paths_from_items
collect_paths_in_modulecode = _collect_paths_in_modulecode
collect_seq_block_paths = _collect_seq_block_paths
collect_seq_node_paths = _collect_seq_node_paths
collect_stmt_block_paths = _collect_stmt_block_paths
collect_stmt_paths = _collect_stmt_paths
infer_alternative_states = _infer_alternative_states
is_exact_reset_condition = _is_exact_reset_condition
is_exact_run_condition = _is_exact_run_condition
path_covers_write = _path_covers_write
record_function_call_writes = _record_function_call_writes
record_mode_function_call_writes = _record_mode_function_call_writes
record_mode_write = _record_mode_write
record_write = _record_write
split_var_ref = _split_var_ref
take_condition_branch = _take_condition_branch
varref_casefold = _varref_casefold
