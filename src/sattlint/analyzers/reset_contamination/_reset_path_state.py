"""Internal helpers for reset contamination path-state collection."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sattline_parser.models.ast_model import Variable

WriteKey = tuple[str, str]
WriteEntry = tuple[Variable, str]
WriteMap = dict[WriteKey, WriteEntry]

_PATH_FRONTIER_LIMIT = 64
_LOG = logging.getLogger("SattLint")


def _empty_write_map() -> WriteMap:
    return {}


@dataclass
class _PathState:
    reset_state: str = "unknown"
    run_writes: WriteMap = field(default_factory=_empty_write_map)
    reset_writes: WriteMap = field(default_factory=_empty_write_map)

    def clone(self) -> _PathState:
        return _PathState(
            reset_state=self.reset_state,
            run_writes=dict(self.run_writes),
            reset_writes=dict(self.reset_writes),
        )


@dataclass(slots=True)
class _PathCollectionDebug:
    enabled: bool = False
    trace_fn: Callable[..., None] | None = None

    def emit(self, action: str, **data: Any) -> None:
        if not self.enabled:
            return
        details = ", ".join(f"{key}={data[key]!r}" for key in sorted(data))
        if details:
            _LOG.debug("reset-contamination %s: %s", action, details)
        else:
            _LOG.debug("reset-contamination %s", action)
        if self.trace_fn is not None:
            self.trace_fn(f"reset-contamination-{action}", **data)


def _merge_reset_states(left: str, right: str) -> str | None:
    if left == right:
        return left
    if left == "unknown":
        return right
    if right == "unknown":
        return left
    return None


def _path_state_fingerprint(
    state: _PathState,
) -> tuple[
    str,
    tuple[tuple[WriteKey, str, str], ...],
    tuple[tuple[WriteKey, str, str], ...],
]:
    return (
        state.reset_state,
        _write_map_fingerprint(state.run_writes),
        _write_map_fingerprint(state.reset_writes),
    )


def _write_map_fingerprint(bucket: WriteMap) -> tuple[tuple[WriteKey, str, str], ...]:
    return tuple(
        sorted(
            (
                key,
                entry[0].name.casefold(),
                entry[1],
            )
            for key, entry in bucket.items()
        )
    )


def _compact_path_states(
    states: list[_PathState],
    *,
    limit: int = _PATH_FRONTIER_LIMIT,
    debug: _PathCollectionDebug | None = None,
    site: str,
) -> list[_PathState]:
    if not states:
        return []

    distinct: dict[
        tuple[str, tuple[tuple[WriteKey, str, str], ...], tuple[tuple[WriteKey, str, str], ...]],
        _PathState,
    ] = {}
    for state in states:
        distinct.setdefault(_path_state_fingerprint(state), state)

    exact_states = list(distinct.values())
    if len(exact_states) <= limit:
        if debug is not None:
            debug.emit(
                "path-state-compaction",
                site=site,
                input_count=len(states),
                exact_count=len(exact_states),
                output_count=len(exact_states),
                duplicate_count=len(states) - len(exact_states),
                overflow_merged=False,
                limit=limit,
            )
        return exact_states

    overflow_states = _compress_path_state_overflow(exact_states)
    if debug is not None:
        debug.emit(
            "path-state-compaction",
            site=site,
            input_count=len(states),
            exact_count=len(exact_states),
            output_count=len(overflow_states),
            duplicate_count=len(states) - len(exact_states),
            overflow_merged=True,
            limit=limit,
        )
    return overflow_states


def _compress_path_state_overflow(states: list[_PathState]) -> list[_PathState]:
    grouped: dict[str, _PathState] = {}
    for state in states:
        existing = grouped.get(state.reset_state)
        if existing is None:
            grouped[state.reset_state] = state.clone()
            continue
        existing.run_writes.update(state.run_writes)
        existing.reset_writes.update(state.reset_writes)
    return list(grouped.values())


def _merge_parallel_branch_results(
    branch_results: list[list[_PathState]],
    *,
    limit: int = _PATH_FRONTIER_LIMIT,
    debug: _PathCollectionDebug | None = None,
) -> list[_PathState]:
    if not branch_results:
        return []

    frontier = _compact_path_states(
        branch_results[0],
        limit=limit,
        debug=debug,
        site="parallel-branch:0",
    )
    incompatible_count = 0
    if debug is not None:
        debug.emit(
            "parallel-merge-start",
            branch_count=len(branch_results),
            branch_sizes=[len(branch) for branch in branch_results],
            frontier_count=len(frontier),
            limit=limit,
        )

    for branch_index, branch in enumerate(branch_results[1:], start=1):
        branch_frontier = _compact_path_states(
            branch,
            limit=limit,
            debug=debug,
            site=f"parallel-branch:{branch_index}",
        )
        next_frontier: list[_PathState] = []
        for left in frontier:
            for right in branch_frontier:
                merged = _merge_path_state_pair(left, right)
                if merged is None:
                    incompatible_count += 1
                    continue
                next_frontier.append(merged)
        frontier = _compact_path_states(
            next_frontier,
            limit=limit,
            debug=debug,
            site=f"parallel-frontier:{branch_index}",
        )
        if debug is not None:
            debug.emit(
                "parallel-merge-step",
                branch_index=branch_index,
                branch_input_count=len(branch),
                branch_distinct_count=len(branch_frontier),
                candidate_count=len(next_frontier),
                frontier_count=len(frontier),
                incompatible_count=incompatible_count,
            )
        if not frontier:
            break

    if debug is not None:
        debug.emit(
            "parallel-merge-complete",
            branch_count=len(branch_results),
            final_count=len(frontier),
            incompatible_count=incompatible_count,
        )
    return frontier


def _merge_path_state_pair(left: _PathState, right: _PathState) -> _PathState | None:
    merged_reset_state = _merge_reset_states(left.reset_state, right.reset_state)
    if merged_reset_state is None:
        return None
    merged = left.clone()
    merged.reset_state = merged_reset_state
    merged.run_writes.update(right.run_writes)
    merged.reset_writes.update(right.reset_writes)
    return merged


PathState = _PathState
PathCollectionDebug = _PathCollectionDebug
compact_path_states = _compact_path_states
merge_parallel_branch_results = _merge_parallel_branch_results
