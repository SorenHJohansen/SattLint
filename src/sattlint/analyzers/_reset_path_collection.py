"""Internal helpers for reset contamination path collection."""

from __future__ import annotations

from typing import Any

from sattline_parser.models.ast_model import (
    ModuleCode,
    Variable,
)

from ._reset_path_collection_sequence import collect_seq_block_paths as _collect_seq_block_paths_impl
from ._reset_path_collection_sequence import collect_seq_node_paths as _collect_seq_node_paths_impl
from ._reset_path_condition import (
    classify_reset_condition as _classify_reset_condition,
)
from ._reset_path_condition import (
    clone_with_reset_state as _clone_with_reset_state,
)
from ._reset_path_condition import (
    infer_alternative_states as _infer_alternative_states,
)
from ._reset_path_condition import (
    is_exact_reset_condition as _is_exact_reset_condition,
)
from ._reset_path_condition import (
    is_exact_run_condition as _is_exact_run_condition,
)
from ._reset_path_condition import (
    take_condition_branch as _take_condition_branch,
)
from ._reset_path_condition import (
    varref_casefold as _varref_casefold,
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
from ._reset_path_stmt_handlers import (
    collect_assignment_paths as _collect_assignment_paths,
)
from ._reset_path_stmt_handlers import (
    collect_function_call_paths as _collect_function_call_paths,
)
from ._reset_path_stmt_handlers import (
    collect_if_stmt_paths as _collect_if_stmt_paths,
)
from ._reset_path_stmt_handlers import (
    collect_paths_from_items as _collect_paths_from_items,
)
from ._reset_path_stmt_handlers import (
    collect_stmt_block_paths as _collect_stmt_block_paths,
)
from ._reset_path_stmt_handlers import (
    collect_stmt_paths as _collect_stmt_paths,
)
from ._reset_path_writes import (
    path_covers_write as _path_covers_write,
)
from ._reset_path_writes import (
    record_function_call_writes as _record_function_call_writes,
)
from ._reset_path_writes import (
    record_mode_function_call_writes as _record_mode_function_call_writes,
)
from ._reset_path_writes import (
    record_mode_write as _record_mode_write,
)
from ._reset_path_writes import (
    record_write as _record_write,
)
from ._reset_path_writes import (
    split_var_ref as _split_var_ref,
)


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
    return _collect_seq_block_paths_impl(
        nodes,
        env,
        reset_ref_cf,
        reset_old_vars_cf,
        states,
        collect_stmt_block_paths=_collect_stmt_block_paths,
        path_debug=path_debug,
    )


def _collect_seq_node_paths(
    node: Any,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    states: list[_PathState],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    return _collect_seq_node_paths_impl(
        node,
        env,
        reset_ref_cf,
        reset_old_vars_cf,
        states,
        collect_stmt_block_paths=_collect_stmt_block_paths,
        path_debug=path_debug,
    )


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
