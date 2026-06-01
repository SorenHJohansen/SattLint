"""Reset contamination detection for SattLine modules.

A variable is 'reset contaminated' when it is written during a run condition
(i.e. when a sequence's .Reset flag is False) but not reset across all reset
paths. This means the variable can retain stale state across equipment resets.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
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
from . import _reset_latching as _reset_latching_module
from . import _reset_path_collection as _reset_path_collection_module
from . import _reset_path_state as _reset_path_state_module
from ._reset_path_state import WriteMap
from ._shared_analysis import AnalysisSharedArtifacts
from .variable_utils import same_origin_file_stem

_PathCollectionDebug = _reset_path_state_module.PathCollectionDebug
_PathState = _reset_path_state_module.PathState
_compact_path_states = _reset_path_state_module.compact_path_states
_merge_parallel_branch_results = _reset_path_state_module.merge_parallel_branch_results
_BooleanPathState = _reset_latching_module.BooleanPathState
_all_boolean_paths_cover_false = _reset_latching_module.all_boolean_paths_cover_false
_boolean_path_covers_false = _reset_latching_module.boolean_path_covers_false
_check_for_modulecode_latching = _reset_latching_module.check_for_modulecode_latching
_collect_boolean_seq_block_paths = _reset_latching_module.collect_boolean_seq_block_paths
_collect_boolean_seq_node_paths = _reset_latching_module.collect_boolean_seq_node_paths
_collect_boolean_stmt_block_paths = _reset_latching_module.collect_boolean_stmt_block_paths
_collect_boolean_stmt_paths = _reset_latching_module.collect_boolean_stmt_paths
_emit_branch_latch_issues = _reset_latching_module.emit_branch_latch_issues
_literal_boolean = _reset_latching_module.literal_boolean
_merge_boolean_parallel_branch_results = _reset_latching_module.merge_boolean_parallel_branch_results
_record_boolean_assignment = _reset_latching_module.record_boolean_assignment
_record_boolean_function_call = _reset_latching_module.record_boolean_function_call
_record_boolean_write = _reset_latching_module.record_boolean_write
_scan_seq_nodes_for_latching = _reset_latching_module.scan_seq_nodes_for_latching
_scan_stmt_block_for_latching = _reset_latching_module.scan_stmt_block_for_latching
_scan_stmt_for_latching = _reset_latching_module.scan_stmt_for_latching
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


def _children_of(obj: Any) -> list[Any] | None:
    children = getattr(obj, "children", None)
    return cast(list[Any], children) if isinstance(children, list) else None


def detect_reset_contamination(
    bp: BasePicture,
    issues: list[VariableIssue],
    limit_to_module_path: list[str] | None = None,
    *,
    debug: bool = False,
    trace_fn: Callable[..., None] | None = None,
    shared_artifacts: AnalysisSharedArtifacts | None = None,
) -> None:
    """Scan all SingleModules and ModuleTypeDefs for reset-contaminated variables."""
    root_path = [bp.header.name]
    root_origin = getattr(bp, "origin_file", None)
    path_debug = _PathCollectionDebug(enabled=debug, trace_fn=trace_fn)
    reset_check = partial(_check_for_modulecode, path_debug=path_debug)

    for mod in bp.submodules or []:
        _collect_from_module(
            mod,
            root_path,
            issues,
            limit_to_module_path,
            check_fn=reset_check,
            shared_artifacts=shared_artifacts,
        )

    if limit_to_module_path is not None:
        return

    for mt in bp.moduletype_defs or []:
        if not same_origin_file_stem(getattr(mt, "origin_file", None), root_origin):
            continue
        td_path = [bp.header.name, f"TypeDef:{mt.name}"]
        _check_for_typedef(mt, td_path, issues, check_fn=reset_check, shared_artifacts=shared_artifacts)


def detect_implicit_latching(
    bp: BasePicture,
    issues: list[VariableIssue],
    limit_to_module_path: list[str] | None = None,
    *,
    shared_artifacts: AnalysisSharedArtifacts | None = None,
) -> None:
    """Scan module code for boolean latch patterns across branches and steps."""
    root_path = [bp.header.name]
    root_origin = getattr(bp, "origin_file", None)

    if bp.modulecode is not None and _should_analyze_path(root_path, limit_to_module_path):
        env = _build_local_env(bp, None, bp.localvariables, shared_artifacts=shared_artifacts)
        _check_for_modulecode_latching(bp.modulecode, env, root_path, issues)

    for mod in bp.submodules or []:
        _collect_from_module(
            mod,
            root_path,
            issues,
            limit_to_module_path,
            check_fn=_check_for_modulecode_latching,
            shared_artifacts=shared_artifacts,
        )

    if limit_to_module_path is not None:
        return

    for mt in bp.moduletype_defs or []:
        if not same_origin_file_stem(getattr(mt, "origin_file", None), root_origin):
            continue
        td_path = [bp.header.name, f"TypeDef:{mt.name}"]
        _check_for_typedef(
            mt, td_path, issues, check_fn=_check_for_modulecode_latching, shared_artifacts=shared_artifacts
        )


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
    shared_artifacts: AnalysisSharedArtifacts | None = None,
) -> None:
    if isinstance(mod, SingleModule):
        mod_path = [*path, mod.header.name]
        if _should_analyze_path(mod_path, limit_to_module_path):
            _check_for_single(mod, mod_path, issues, check_fn=check_fn, shared_artifacts=shared_artifacts)
        for child in mod.submodules or []:
            _collect_from_module(
                child,
                mod_path,
                issues,
                limit_to_module_path,
                check_fn=check_fn,
                shared_artifacts=shared_artifacts,
            )
    elif isinstance(mod, FrameModule):
        mod_path = [*path, mod.header.name]
        for child in mod.submodules or []:
            _collect_from_module(
                child,
                mod_path,
                issues,
                limit_to_module_path,
                check_fn=check_fn,
                shared_artifacts=shared_artifacts,
            )


def _build_local_env(
    owner: object,
    moduleparameters: list[Variable] | None,
    localvariables: list[Variable] | None,
    *,
    shared_artifacts: AnalysisSharedArtifacts | None = None,
) -> dict[str, Variable]:
    if shared_artifacts is not None:
        cached = shared_artifacts.local_variable_envs.get(id(owner))
        if cached is not None:
            return cached

    env: dict[str, Variable] = {}
    for var in moduleparameters or []:
        env[var.name.casefold()] = var
    for var in localvariables or []:
        env[var.name.casefold()] = var

    if shared_artifacts is not None:
        shared_artifacts.local_variable_envs[id(owner)] = env
        shared_artifacts.counters.local_env_builds += 1
    return env


def _check_for_single(
    mod: SingleModule,
    path: list[str],
    issues: list[VariableIssue],
    *,
    check_fn: Callable[..., None],
    shared_artifacts: AnalysisSharedArtifacts | None = None,
) -> None:
    if mod.modulecode is None:
        return
    env = _build_local_env(mod, mod.moduleparameters, mod.localvariables, shared_artifacts=shared_artifacts)
    check_fn(mod.modulecode, env, path, issues)


def _check_for_typedef(
    mt: ModuleTypeDef,
    path: list[str],
    issues: list[VariableIssue],
    *,
    check_fn: Callable[..., None],
    shared_artifacts: AnalysisSharedArtifacts | None = None,
) -> None:
    if mt.modulecode is None:
        return
    env = _build_local_env(mt, mt.moduleparameters, mt.localvariables, shared_artifacts=shared_artifacts)
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
