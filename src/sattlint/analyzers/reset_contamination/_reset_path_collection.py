"""Path collection entry point for reset contamination."""

from __future__ import annotations

from sattlint.parser_api import ModuleCode, Variable

from ._reset_path_collection_sequence import collect_seq_block_paths as _collect_seq_block_paths
from ._reset_path_state import PathCollectionDebug as _PathCollectionDebug
from ._reset_path_state import PathState as _PathState
from ._reset_path_state import compact_path_states as _compact_path_states
from ._reset_path_stmt_handlers import collect_stmt_block_paths as _collect_stmt_block_paths
from ._reset_path_writes import path_covers_write as _path_covers_write


def collect_paths_in_modulecode(
    modulecode: ModuleCode,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    *,
    path_debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    states = [_PathState()]

    for eq in modulecode.equationblocks or []:
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
            collect_stmt_block_paths=_collect_stmt_block_paths,
            path_debug=path_debug,
        )

    return _compact_path_states(states, debug=path_debug, site="modulecode")


path_covers_write = _path_covers_write

__all__ = ["collect_paths_in_modulecode", "path_covers_write"]
