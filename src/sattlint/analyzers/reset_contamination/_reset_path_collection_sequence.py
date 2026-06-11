"""Sequence-path traversal helpers for reset contamination analysis."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sattline_parser.models.ast_model import (
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Variable,
)

from ._reset_path_state import (
    PathCollectionDebug as _PathCollectionDebug,
)
from ._reset_path_state import (
    PathState as _PathState,
)
from ._reset_path_state import (
    compact_path_states as _compact_path_states,
)
from ._reset_path_state import (
    merge_parallel_branch_results as _merge_parallel_branch_results,
)


def collect_seq_block_paths(
    nodes: list[Any],
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    collect_stmt_block_paths: Callable[..., list[_PathState]],
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    next_states = states
    for node in nodes:
        next_states = collect_seq_node_paths(
            node,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            next_states,
            collect_stmt_block_paths=collect_stmt_block_paths,
            path_debug=path_debug,
        )
    return next_states


def _handle_seq_step(
    node: SFCStep,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    collect_stmt_block_paths: Callable[..., list[_PathState]],
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    next_states = collect_stmt_block_paths(
        node.code.enter or [],
        env,
        reset_ref_cf,
        reset_old_vars_cf,
        states,
        path_debug=path_debug,
    )
    next_states = collect_stmt_block_paths(
        node.code.active or [],
        env,
        reset_ref_cf,
        reset_old_vars_cf,
        next_states,
        path_debug=path_debug,
    )
    result = collect_stmt_block_paths(
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


def _handle_seq_alternative(
    node: SFCAlternative,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    collect_stmt_block_paths: Callable[..., list[_PathState]],
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    if not node.branches:
        return states
    alternative_states: list[_PathState] = []
    for state in states:
        for branch in node.branches or []:
            alternative_states.extend(
                collect_seq_block_paths(
                    branch or [],
                    env,
                    reset_ref_cf,
                    reset_old_vars_cf,
                    [state.clone()],
                    collect_stmt_block_paths=collect_stmt_block_paths,
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


def _handle_seq_parallel(
    node: SFCParallel,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    collect_stmt_block_paths: Callable[..., list[_PathState]],
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    if not node.branches:
        return states
    parallel_states: list[_PathState] = []
    for state in states:
        branch_results = [
            collect_seq_block_paths(
                branch or [],
                env,
                reset_ref_cf,
                reset_old_vars_cf,
                [state.clone()],
                collect_stmt_block_paths=collect_stmt_block_paths,
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


def collect_seq_node_paths(
    node: Any,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    collect_stmt_block_paths: Callable[..., list[_PathState]],
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    if isinstance(node, SFCStep):
        return _handle_seq_step(
            node,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            collect_stmt_block_paths=collect_stmt_block_paths,
            path_debug=path_debug,
        )

    if isinstance(node, SFCTransition):
        return states

    if isinstance(node, SFCAlternative):
        return _handle_seq_alternative(
            node,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            collect_stmt_block_paths=collect_stmt_block_paths,
            path_debug=path_debug,
        )

    if isinstance(node, SFCParallel):
        return _handle_seq_parallel(
            node,
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            collect_stmt_block_paths=collect_stmt_block_paths,
            path_debug=path_debug,
        )

    if isinstance(node, SFCSubsequence):
        result = collect_seq_block_paths(
            node.body or [],
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            collect_stmt_block_paths=collect_stmt_block_paths,
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
        result = collect_seq_block_paths(
            node.body or [],
            env,
            reset_ref_cf,
            reset_old_vars_cf,
            states,
            collect_stmt_block_paths=collect_stmt_block_paths,
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


__all__ = ["collect_seq_block_paths", "collect_seq_node_paths"]
