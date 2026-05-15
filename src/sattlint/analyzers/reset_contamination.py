"""Reset contamination detection for SattLine modules.

A variable is 'reset contaminated' when it is written during a run condition
(i.e. when a sequence's .Reset flag is False) but not reset across all reset
paths. This means the variable can retain stale state across equipment resets.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from itertools import product
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
    Variable,
)

from ..grammar import constants as const
from ..reporting.variables_report import IssueKind, VariableIssue
from ..resolution.common import path_startswith_casefold
from ..types import VariableId
from . import _reset_path_collection as _reset_path_collection_module
from . import _reset_path_state as _reset_path_state_module
from ._reset_path_state import WriteKey, WriteMap
from .variable_utils import same_origin_file_stem

_PathCollectionDebug = _reset_path_state_module.PathCollectionDebug
_PathState = _reset_path_state_module.PathState
_compact_path_states = _reset_path_state_module.compact_path_states
_merge_parallel_branch_results = _reset_path_state_module.merge_parallel_branch_results
_classify_reset_condition = _reset_path_collection_module.classify_reset_condition
_clone_with_reset_state = _reset_path_collection_module.clone_with_reset_state
_collect_assignment_paths = _reset_path_collection_module.collect_assignment_paths
_collect_function_call_paths = _reset_path_collection_module.collect_function_call_paths
_collect_if_stmt_paths = _reset_path_collection_module.collect_if_stmt_paths
_collect_paths_from_items = _reset_path_collection_module.collect_paths_from_items
_collect_paths_in_modulecode = _reset_path_collection_module.collect_paths_in_modulecode
_collect_seq_block_paths = _reset_path_collection_module.collect_seq_block_paths
_collect_seq_node_paths = _reset_path_collection_module.collect_seq_node_paths
_collect_stmt_block_paths = _reset_path_collection_module.collect_stmt_block_paths
_collect_stmt_paths = _reset_path_collection_module.collect_stmt_paths
_infer_alternative_states = _reset_path_collection_module.infer_alternative_states
_is_exact_reset_condition = _reset_path_collection_module.is_exact_reset_condition
_is_exact_run_condition = _reset_path_collection_module.is_exact_run_condition
_path_covers_write = _reset_path_collection_module.path_covers_write
_record_function_call_writes = _reset_path_collection_module.record_function_call_writes
_record_mode_function_call_writes = _reset_path_collection_module.record_mode_function_call_writes
_record_mode_write = _reset_path_collection_module.record_mode_write
_record_write = _reset_path_collection_module.record_write
_split_var_ref = _reset_path_collection_module.split_var_ref
_take_condition_branch = _reset_path_collection_module.take_condition_branch
_varref_casefold = _reset_path_collection_module.varref_casefold

type _StmtBranch = tuple[Any, list[Any]]
type _IfTuple = tuple[str, list[_StmtBranch] | None, list[Any] | None]
type _AssignTuple = tuple[str, Any, Any]
type _FunctionCallTuple = tuple[str, str, list[Any] | None]


def _new_boolean_write_map() -> dict[WriteKey, tuple[Variable, str]]:
    return {}


def _children_of(obj: Any) -> list[Any] | None:
    children = getattr(obj, "children", None)
    return cast(list[Any], children) if isinstance(children, list) else None


@dataclass
class _BooleanPathState:
    true_writes: dict[WriteKey, tuple[Variable, str]] = field(default_factory=_new_boolean_write_map)
    false_writes: dict[WriteKey, tuple[Variable, str]] = field(default_factory=_new_boolean_write_map)

    def clone(self) -> _BooleanPathState:
        return _BooleanPathState(
            true_writes=dict(self.true_writes),
            false_writes=dict(self.false_writes),
        )


def detect_reset_contamination(
    bp: BasePicture,
    issues: list[VariableIssue],
    limit_to_module_path: list[str] | None = None,
    *,
    debug: bool = False,
    trace_fn: Callable[..., None] | None = None,
) -> None:
    """Scan all SingleModules and ModuleTypeDefs for reset-contaminated variables."""
    root_path = [bp.header.name]
    root_origin = getattr(bp, "origin_file", None)
    path_debug = _PathCollectionDebug(enabled=debug, trace_fn=trace_fn)
    reset_check = partial(_check_for_modulecode, path_debug=path_debug)

    for mod in bp.submodules or []:
        _collect_from_module(mod, root_path, issues, limit_to_module_path, check_fn=reset_check)

    if limit_to_module_path is not None:
        return

    for mt in bp.moduletype_defs or []:
        if not same_origin_file_stem(getattr(mt, "origin_file", None), root_origin):
            continue
        td_path = [bp.header.name, f"TypeDef:{mt.name}"]
        _check_for_typedef(mt, td_path, issues, check_fn=reset_check)


def detect_implicit_latching(
    bp: BasePicture,
    issues: list[VariableIssue],
    limit_to_module_path: list[str] | None = None,
) -> None:
    """Scan module code for boolean latch patterns across branches and steps."""
    root_path = [bp.header.name]
    root_origin = getattr(bp, "origin_file", None)

    if bp.modulecode is not None and _should_analyze_path(root_path, limit_to_module_path):
        env = _build_local_env(None, bp.localvariables)
        _check_for_modulecode_latching(bp.modulecode, env, root_path, issues)

    for mod in bp.submodules or []:
        _collect_from_module(mod, root_path, issues, limit_to_module_path, check_fn=_check_for_modulecode_latching)

    if limit_to_module_path is not None:
        return

    for mt in bp.moduletype_defs or []:
        if not same_origin_file_stem(getattr(mt, "origin_file", None), root_origin):
            continue
        td_path = [bp.header.name, f"TypeDef:{mt.name}"]
        _check_for_typedef(mt, td_path, issues, check_fn=_check_for_modulecode_latching)


def is_from_root_origin(origin_file: str | None, root_origin: str | None) -> bool:
    return same_origin_file_stem(origin_file, root_origin)


def _should_analyze_path(path: list[str], limit_to_module_path: list[str] | None) -> bool:
    if limit_to_module_path is None:
        return True
    return path_startswith_casefold(limit_to_module_path, path) or path_startswith_casefold(path, limit_to_module_path)


def _collect_from_module(
    mod: SingleModule | FrameModule | ModuleTypeInstance,
    path: list[str],
    issues: list[VariableIssue],
    limit_to_module_path: list[str] | None,
    *,
    check_fn: Callable[..., None],
) -> None:
    if isinstance(mod, SingleModule):
        mod_path = [*path, mod.header.name]
        if _should_analyze_path(mod_path, limit_to_module_path):
            _check_for_single(mod, mod_path, issues, check_fn=check_fn)
        for child in mod.submodules or []:
            _collect_from_module(child, mod_path, issues, limit_to_module_path, check_fn=check_fn)
    elif isinstance(mod, FrameModule):
        mod_path = [*path, mod.header.name]
        for child in mod.submodules or []:
            _collect_from_module(child, mod_path, issues, limit_to_module_path, check_fn=check_fn)


def _build_local_env(
    moduleparameters: list[Variable] | None,
    localvariables: list[Variable] | None,
) -> dict[str, Variable]:
    env: dict[str, Variable] = {}
    for var in moduleparameters or []:
        env[var.name.casefold()] = var
    for var in localvariables or []:
        env[var.name.casefold()] = var
    return env


def _check_for_single(
    mod: SingleModule, path: list[str], issues: list[VariableIssue], *, check_fn: Callable[..., None]
) -> None:
    if mod.modulecode is None:
        return
    env = _build_local_env(mod.moduleparameters, mod.localvariables)
    check_fn(mod.modulecode, env, path, issues)


def _check_for_typedef(
    mt: ModuleTypeDef, path: list[str], issues: list[VariableIssue], *, check_fn: Callable[..., None]
) -> None:
    if mt.modulecode is None:
        return
    env = _build_local_env(mt.moduleparameters, mt.localvariables)
    check_fn(mt.modulecode, env, path, issues)


def _check_for_modulecode(
    modulecode: ModuleCode,
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> None:
    sequences = list(modulecode.sequences or [])
    if not sequences:
        return

    var_refs = _collect_var_refs(modulecode)
    for seq in sequences:
        seq_name = getattr(seq, "name", "")
        if not seq_name:
            continue
        reset_ref = f"{seq_name}.Reset"
        reset_ref_cf = reset_ref.casefold()
        if reset_ref_cf not in var_refs:
            continue

        reset_old_vars = _collect_reset_old_vars(modulecode, reset_ref_cf)
        reset_old_cf = {name.casefold() for name in reset_old_vars}
        path_states = _collect_paths_in_modulecode(
            modulecode,
            env,
            reset_ref_cf,
            reset_old_cf,
            path_debug=path_debug,
        )
        if path_debug is not None:
            path_debug.emit(
                "modulecode-path-summary",
                module_path=path,
                sequence_name=seq_name,
                path_count=len(path_states),
                reset_path_count=sum(1 for state in path_states if state.reset_state == "reset"),
                run_write_count=sum(len(state.run_writes) for state in path_states),
            )

        run_writes: WriteMap = {}
        for state in path_states:
            run_writes.update(state.run_writes)

        if not run_writes:
            continue

        reset_paths = [state for state in path_states if state.reset_state == "reset"]

        for key, (var, field_path) in sorted(run_writes.items(), key=lambda item: (item[0][0], item[0][1])):
            var_key, _field_key = key
            if var_key in reset_old_cf:
                continue
            if reset_paths and all(_path_covers_write(state.reset_writes, key) for state in reset_paths):
                continue

            issues.append(
                VariableIssue(
                    kind=IssueKind.RESET_CONTAMINATION,
                    module_path=path.copy(),
                    variable=var,
                    role="localvariable",
                    field_path=field_path or None,
                    sequence_name=seq_name,
                    reset_variable=VariableId(reset_ref),
                )
            )


def _check_for_modulecode_latching(
    modulecode: ModuleCode,
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
) -> None:
    seen: set[tuple[tuple[str, ...], str, str]] = set()

    for eq in modulecode.equations or []:
        eq_name = getattr(eq, "name", "<unnamed>")
        _scan_stmt_block_for_latching(
            eq.code or [],
            env,
            path,
            issues,
            seen,
            site=f"EQ:{eq_name}",
        )

    for seq in modulecode.sequences or []:
        seq_name = getattr(seq, "name", "<unnamed>")
        _scan_seq_nodes_for_latching(
            seq.code or [],
            env,
            path,
            issues,
            seen,
            site=f"SEQ:{seq_name}",
            sequence_name=seq_name,
        )


def _collect_var_refs(modulecode: ModuleCode) -> set[str]:
    refs: set[str] = set()

    def visit(obj: Any) -> None:
        if obj is None:
            return
        if isinstance(obj, dict) and const.KEY_VAR_NAME in obj:
            full = cast(dict[str, object], obj).get(const.KEY_VAR_NAME)
            if isinstance(full, str) and full:
                refs.add(full.casefold())
            return
        if isinstance(obj, list):
            for item in cast(list[Any], obj):
                visit(item)
            return
        if isinstance(obj, SFCStep):
            for stmt in obj.code.enter or []:
                visit(stmt)
            for stmt in obj.code.active or []:
                visit(stmt)
            for stmt in obj.code.exit or []:
                visit(stmt)
            return
        if isinstance(obj, SFCTransition):
            visit(obj.condition)
            return
        if isinstance(obj, SFCAlternative | SFCParallel):
            for branch in obj.branches or []:
                for item in branch or []:
                    visit(item)
            return
        if isinstance(obj, SFCSubsequence | SFCTransitionSub):
            for item in obj.body or []:
                visit(item)
            return
        if isinstance(obj, tuple):
            for item in cast(tuple[Any, ...], obj):
                visit(item)
            return
        children = _children_of(obj)
        if children is not None:
            for child in children:
                visit(child)

    for seq in modulecode.sequences or []:
        for node in seq.code or []:
            visit(node)
    for eq in modulecode.equations or []:
        for stmt in eq.code or []:
            visit(stmt)

    return refs


def _scan_stmt_block_for_latching(
    stmts: list[Any],
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
    seen: set[tuple[tuple[str, ...], str, str]],
    *,
    site: str,
    sequence_name: str | None = None,
) -> None:
    for stmt in stmts:
        _scan_stmt_for_latching(
            stmt,
            env,
            path,
            issues,
            seen,
            site=site,
            sequence_name=sequence_name,
        )


def _scan_stmt_for_latching(
    obj: Any,
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
    seen: set[tuple[tuple[str, ...], str, str]],
    *,
    site: str,
    sequence_name: str | None = None,
) -> None:
    if obj is None:
        return
    if hasattr(obj, "data") and obj.data == const.KEY_STATEMENT:
        for child in _children_of(obj) or []:
            _scan_stmt_for_latching(
                child,
                env,
                path,
                issues,
                seen,
                site=site,
                sequence_name=sequence_name,
            )
        return
    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
        _, branches, else_block = cast(_IfTuple, obj)
        branch_states: list[tuple[str, list[_BooleanPathState]]] = []
        for index, (_cond, branch_stmts) in enumerate(branches or []):
            label = "IF" if index == 0 else f"ELSIF:{index}"
            states = _collect_boolean_stmt_block_paths(
                branch_stmts or [],
                env,
                [_BooleanPathState()],
            )
            branch_states.append((label, states or [_BooleanPathState()]))
            _scan_stmt_block_for_latching(
                branch_stmts or [],
                env,
                path,
                issues,
                seen,
                site=f"{site} > {label}",
                sequence_name=sequence_name,
            )
        else_states = (
            _collect_boolean_stmt_block_paths(else_block or [], env, [_BooleanPathState()])
            if else_block
            else [_BooleanPathState()]
        )
        if else_block:
            _scan_stmt_block_for_latching(
                else_block or [],
                env,
                path,
                issues,
                seen,
                site=f"{site} > ELSE",
                sequence_name=sequence_name,
            )

        for label, states in branch_states:
            alternative_states = [
                alt_state
                for other_label, other_states in branch_states
                if other_label != label
                for alt_state in other_states
            ]
            alternative_states.extend(else_states)
            _emit_branch_latch_issues(
                states,
                alternative_states or [_BooleanPathState()],
                path,
                issues,
                seen,
                site=f"{site} > {label}",
                role_prefix="implicit latch across alternative paths",
                sequence_name=sequence_name,
            )
        return
    if isinstance(obj, list):
        for item in cast(list[Any], obj):
            _scan_stmt_for_latching(
                item,
                env,
                path,
                issues,
                seen,
                site=site,
                sequence_name=sequence_name,
            )
        return
    children = _children_of(obj)
    if children is not None:
        for child in children:
            _scan_stmt_for_latching(
                child,
                env,
                path,
                issues,
                seen,
                site=site,
                sequence_name=sequence_name,
            )


def _scan_seq_nodes_for_latching(
    nodes: list[Any],
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
    seen: set[tuple[tuple[str, ...], str, str]],
    *,
    site: str,
    sequence_name: str | None = None,
) -> None:
    for node in nodes:
        if isinstance(node, SFCStep):
            step_site = f"{site} > STEP:{node.name}"
            entry_states = _collect_boolean_stmt_block_paths(
                node.code.enter or [],
                env,
                [_BooleanPathState()],
            )
            active_states = _collect_boolean_stmt_block_paths(
                node.code.active or [],
                env,
                entry_states or [_BooleanPathState()],
            )
            exit_states = _collect_boolean_stmt_block_paths(
                node.code.exit or [],
                env,
                [_BooleanPathState()],
            )
            _emit_branch_latch_issues(
                active_states or [_BooleanPathState()],
                exit_states or [_BooleanPathState()],
                path,
                issues,
                seen,
                site=step_site,
                role_prefix="implicit latch across step exit",
                sequence_name=sequence_name,
            )
            _scan_stmt_block_for_latching(
                node.code.enter or [],
                env,
                path,
                issues,
                seen,
                site=f"{step_site}:ENTER",
                sequence_name=sequence_name,
            )
            _scan_stmt_block_for_latching(
                node.code.active or [],
                env,
                path,
                issues,
                seen,
                site=f"{step_site}:ACTIVE",
                sequence_name=sequence_name,
            )
            _scan_stmt_block_for_latching(
                node.code.exit or [],
                env,
                path,
                issues,
                seen,
                site=f"{step_site}:EXIT",
                sequence_name=sequence_name,
            )
            continue
        if isinstance(node, SFCAlternative):
            branch_states: list[tuple[str, list[_BooleanPathState]]] = []
            for index, branch in enumerate(node.branches or []):
                label = f"ALT:{index + 1}"
                states = _collect_boolean_seq_block_paths(
                    branch or [],
                    env,
                    [_BooleanPathState()],
                )
                branch_states.append((label, states or [_BooleanPathState()]))
                _scan_seq_nodes_for_latching(
                    branch or [],
                    env,
                    path,
                    issues,
                    seen,
                    site=f"{site} > {label}",
                    sequence_name=sequence_name,
                )
            for label, states in branch_states:
                alternative_states = [
                    alt_state
                    for other_label, other_states in branch_states
                    if other_label != label
                    for alt_state in other_states
                ]
                _emit_branch_latch_issues(
                    states,
                    alternative_states or [_BooleanPathState()],
                    path,
                    issues,
                    seen,
                    site=f"{site} > {label}",
                    role_prefix="implicit latch across SFC alternatives",
                    sequence_name=sequence_name,
                )
            continue
        if isinstance(node, SFCParallel):
            for index, branch in enumerate(node.branches or []):
                _scan_seq_nodes_for_latching(
                    branch or [],
                    env,
                    path,
                    issues,
                    seen,
                    site=f"{site} > PAR:{index + 1}",
                    sequence_name=sequence_name,
                )
            continue
        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            _scan_seq_nodes_for_latching(
                node.body or [],
                env,
                path,
                issues,
                seen,
                site=site,
                sequence_name=sequence_name,
            )


def _emit_branch_latch_issues(
    branch_states: list[_BooleanPathState],
    alternative_states: list[_BooleanPathState],
    path: list[str],
    issues: list[VariableIssue],
    seen: set[tuple[tuple[str, ...], str, str]],
    *,
    site: str,
    role_prefix: str,
    sequence_name: str | None,
) -> None:
    true_writes: WriteMap = {}
    for state in branch_states:
        true_writes.update(state.true_writes)

    for key, (var, field_path) in sorted(true_writes.items(), key=lambda item: (item[0][0], item[0][1])):
        if _all_boolean_paths_cover_false(alternative_states, key):
            continue
        issue_key = (tuple(path), key[0], site.casefold())
        if issue_key in seen:
            continue
        seen.add(issue_key)
        issues.append(
            VariableIssue(
                kind=IssueKind.IMPLICIT_LATCH,
                module_path=path.copy(),
                variable=var,
                role=f"{role_prefix} at {site}",
                field_path=field_path or None,
                sequence_name=sequence_name,
                site=site,
            )
        )


def _all_boolean_paths_cover_false(states: list[_BooleanPathState], key: WriteKey) -> bool:
    return bool(states) and all(_boolean_path_covers_false(state.false_writes, key) for state in states)


def _boolean_path_covers_false(false_writes: WriteMap, key: WriteKey) -> bool:
    var_key, _field_key = key
    return key in false_writes or (var_key, "") in false_writes


def _collect_boolean_stmt_block_paths(
    stmts: list[Any],
    env: dict[str, Variable],
    states: list[_BooleanPathState],
) -> list[_BooleanPathState]:
    next_states = states
    for stmt in stmts:
        next_states = _collect_boolean_stmt_paths(stmt, env, next_states)
    return next_states


def _collect_boolean_stmt_paths(
    obj: Any,
    env: dict[str, Variable],
    states: list[_BooleanPathState],
) -> list[_BooleanPathState]:
    if obj is None:
        return states
    if hasattr(obj, "data") and obj.data == const.KEY_STATEMENT:
        next_states = states
        for child in _children_of(obj) or []:
            next_states = _collect_boolean_stmt_paths(child, env, next_states)
        return next_states

    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
        _, branches, else_block = cast(_IfTuple, obj)
        branch_states: list[_BooleanPathState] = []
        for state in states:
            for _cond, branch_stmts in branches or []:
                branch_states.extend(
                    _collect_boolean_stmt_block_paths(
                        branch_stmts or [],
                        env,
                        [state.clone()],
                    )
                )
            if else_block:
                branch_states.extend(
                    _collect_boolean_stmt_block_paths(
                        else_block or [],
                        env,
                        [state.clone()],
                    )
                )
            else:
                branch_states.append(state.clone())
        return branch_states or states

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
        _, target, expr = cast(_AssignTuple, obj)
        assigned_states: list[_BooleanPathState] = []
        for state in states:
            next_state = state.clone()
            _record_boolean_assignment(target, expr, env, next_state)
            assigned_states.append(next_state)
        return assigned_states or states

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
        _, fn_name, args = cast(_FunctionCallTuple, obj)
        call_states: list[_BooleanPathState] = []
        for state in states:
            next_state = state.clone()
            _record_boolean_function_call(fn_name, args or [], env, next_state)
            call_states.append(next_state)
        return call_states or states

    if isinstance(obj, list):
        next_states = states
        for item in cast(list[Any], obj):
            next_states = _collect_boolean_stmt_paths(item, env, next_states)
        return next_states

    children = _children_of(obj)
    if children is not None:
        next_states = states
        for child in children:
            next_states = _collect_boolean_stmt_paths(child, env, next_states)
        return next_states

    return states


def _collect_boolean_seq_block_paths(
    nodes: list[Any],
    env: dict[str, Variable],
    states: list[_BooleanPathState],
) -> list[_BooleanPathState]:
    next_states = states
    for node in nodes:
        next_states = _collect_boolean_seq_node_paths(node, env, next_states)
    return next_states


def _collect_boolean_seq_node_paths(
    node: Any,
    env: dict[str, Variable],
    states: list[_BooleanPathState],
) -> list[_BooleanPathState]:
    if isinstance(node, SFCStep):
        next_states = _collect_boolean_stmt_block_paths(node.code.enter or [], env, states)
        next_states = _collect_boolean_stmt_block_paths(node.code.active or [], env, next_states)
        return _collect_boolean_stmt_block_paths(node.code.exit or [], env, next_states)

    if isinstance(node, SFCTransition):
        return states

    if isinstance(node, SFCAlternative):
        if not node.branches:
            return states
        alternative_states: list[_BooleanPathState] = []
        for state in states:
            for branch in node.branches or []:
                alternative_states.extend(
                    _collect_boolean_seq_block_paths(
                        branch or [],
                        env,
                        [state.clone()],
                    )
                )
        return alternative_states or states

    if isinstance(node, SFCParallel):
        if not node.branches:
            return states
        parallel_states: list[_BooleanPathState] = []
        for state in states:
            branch_results = [
                _collect_boolean_seq_block_paths(
                    branch or [],
                    env,
                    [state.clone()],
                )
                for branch in node.branches or []
            ]
            parallel_states.extend(_merge_boolean_parallel_branch_results(branch_results))
        return parallel_states or states

    if isinstance(node, SFCSubsequence | SFCTransitionSub):
        return _collect_boolean_seq_block_paths(node.body or [], env, states)

    return states


def _merge_boolean_parallel_branch_results(
    branch_results: list[list[_BooleanPathState]],
) -> list[_BooleanPathState]:
    if not branch_results:
        return []

    merged_states: list[_BooleanPathState] = []
    for combo in product(*branch_results):
        merged = combo[0].clone()
        for branch_state in combo[1:]:
            merged.true_writes.update(branch_state.true_writes)
            merged.false_writes.update(branch_state.false_writes)
        merged_states.append(merged)
    return merged_states


def _record_boolean_assignment(
    target: Any,
    expr: Any,
    env: dict[str, Variable],
    state: _BooleanPathState,
) -> None:
    bool_value = _literal_boolean(expr)
    if bool_value is None:
        return
    _record_boolean_write(target, env, state.true_writes if bool_value else state.false_writes)


def _record_boolean_function_call(
    fn_name: str,
    args: list[Any],
    env: dict[str, Variable],
    state: _BooleanPathState,
) -> None:
    if fn_name.casefold() != "setbooleanvalue" or len(args) < 2:
        return
    bool_value = _literal_boolean(args[1])
    if bool_value is None:
        return
    _record_boolean_write(args[0], env, state.true_writes if bool_value else state.false_writes)


def _literal_boolean(expr: Any) -> bool | None:
    if isinstance(expr, bool):
        return expr
    return None


def _collect_reset_old_vars(modulecode: ModuleCode, reset_ref_cf: str) -> set[str]:
    reset_old_vars: set[str] = set()

    def visit(obj: Any) -> None:
        if obj is None:
            return
        if hasattr(obj, "data") and obj.data == const.KEY_STATEMENT:
            for child in _children_of(obj) or []:
                visit(child)
            return
        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
            _, target, expr = cast(_AssignTuple, obj)
            if (
                (
                    isinstance(expr, dict)
                    and const.KEY_VAR_NAME in expr
                    and isinstance(cast(dict[str, object], expr).get(const.KEY_VAR_NAME), str)
                    and cast(str, cast(dict[str, object], expr).get(const.KEY_VAR_NAME)).casefold() == reset_ref_cf
                )
                and isinstance(target, dict)
                and const.KEY_VAR_NAME in target
            ):
                target_name = cast(dict[str, object], target).get(const.KEY_VAR_NAME)
                if isinstance(target_name, str) and target_name:
                    reset_old_vars.add(target_name)
            visit(expr)
            return
        if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
            _, branches, else_block = cast(_IfTuple, obj)
            for cond, stmts in branches or []:
                visit(cond)
                for stmt in stmts or []:
                    visit(stmt)
            for stmt in else_block or []:
                visit(stmt)
            return
        if isinstance(obj, list):
            for item in cast(list[Any], obj):
                visit(item)
            return
        if isinstance(obj, SFCStep):
            for stmt in obj.code.enter or []:
                visit(stmt)
            for stmt in obj.code.active or []:
                visit(stmt)
            for stmt in obj.code.exit or []:
                visit(stmt)
            return
        if isinstance(obj, SFCTransition):
            visit(obj.condition)
            return
        if isinstance(obj, SFCAlternative | SFCParallel):
            for branch in obj.branches or []:
                for item in branch or []:
                    visit(item)
            return
        if isinstance(obj, SFCSubsequence | SFCTransitionSub):
            for item in obj.body or []:
                visit(item)
            return
        if isinstance(obj, tuple):
            for item in cast(tuple[Any, ...], obj):
                visit(item)
            return
        children = _children_of(obj)
        if children is not None:
            for child in children:
                visit(child)

    for seq in modulecode.sequences or []:
        for node in seq.code or []:
            visit(node)
    for eq in modulecode.equations or []:
        for stmt in eq.code or []:
            visit(stmt)

    return reset_old_vars


def _record_boolean_write(target: Any, env: dict[str, Variable], out: WriteMap) -> None:
    if not isinstance(target, dict) or const.KEY_VAR_NAME not in target:
        return
    full_ref = cast(dict[str, object], target).get(const.KEY_VAR_NAME)
    if not isinstance(full_ref, str) or not full_ref:
        return
    base, field_path = _split_var_ref(full_ref)
    if not base or field_path:
        return
    var = env.get(base.casefold())
    if var is None or var.datatype_text.casefold() != "boolean":
        return
    out[(var.name.casefold(), "")] = (var, "")
