"""Run-history persistence (JSON records under the cache dir)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from ..cache import get_cache_dir
from .types import RUN_RECORD_SCHEMA_VERSION, RunRecord, RunSummary

DEFAULT_RUN_HISTORY_LIMIT = 50

_RUN_JSON_SUFFIX = ".json"


def get_runs_dir() -> Path:
    return get_cache_dir() / "runs"


def _run_path(runs_dir: Path, run_id: str) -> Path:
    return runs_dir / f"{run_id}{_RUN_JSON_SUFFIX}"


def _generate_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def save_run(record: RunRecord, *, runs_dir: Path | None = None) -> RunRecord:
    """Persist a run record and return the stored record (with generated id)."""
    resolved_runs_dir = get_runs_dir() if runs_dir is None else runs_dir
    resolved_runs_dir.mkdir(parents=True, exist_ok=True)

    stored_record = record
    if not stored_record.run_id:
        stored_record = RunRecord(
            run_id=_generate_run_id(),
            started_at=record.started_at,
            finished_at=record.finished_at,
            project_tag=record.project_tag,
            selected_analyzers=record.selected_analyzers,
            selected_issue_kinds=record.selected_issue_kinds,
            cancelled=record.cancelled,
            targets=record.targets,
        )

    payload = stored_record.to_dict()
    path = _run_path(resolved_runs_dir, stored_record.run_id)
    try:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
    except (OSError, TypeError, ValueError):
        return stored_record

    return stored_record


def prune_runs(runs_dir: Path | None, *, limit: int) -> int:
    """Delete the oldest run files beyond *limit*, returning the count removed."""
    resolved_runs_dir = get_runs_dir() if runs_dir is None else runs_dir
    summaries = list_runs(runs_dir=resolved_runs_dir)
    if limit < 0 or len(summaries) <= limit:
        return 0

    removed = 0
    for summary in reversed(summaries[limit:]):
        path = _run_path(resolved_runs_dir, summary.run_id)
        try:
            path.unlink()
        except OSError:
            continue
        removed += 1
    return removed


def list_runs(*, runs_dir: Path | None = None) -> tuple[RunSummary, ...]:
    """List persisted runs newest-first."""
    resolved_runs_dir = get_runs_dir() if runs_dir is None else runs_dir
    if not resolved_runs_dir.exists():
        return ()

    summaries: list[RunSummary] = []
    for path in sorted(resolved_runs_dir.glob(f"*{_RUN_JSON_SUFFIX}"), key=lambda p: p.name, reverse=True):
        record = _load_run_file(path)
        if record is not None:
            summaries.append(RunSummary.from_record(record))
    return tuple(summaries)


def load_run(run_id: str, *, runs_dir: Path | None = None) -> RunRecord | None:
    resolved_runs_dir = get_runs_dir() if runs_dir is None else runs_dir
    return _load_run_file(_run_path(resolved_runs_dir, run_id))


def _load_run_file(path: Path) -> RunRecord | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    payload_map = cast(dict[str, object], payload)
    if payload_map.get("schema_version") != RUN_RECORD_SCHEMA_VERSION:
        return None
    return RunRecord.from_dict(payload_map)


__all__ = [
    "DEFAULT_RUN_HISTORY_LIMIT",
    "get_runs_dir",
    "list_runs",
    "load_run",
    "prune_runs",
    "save_run",
]
