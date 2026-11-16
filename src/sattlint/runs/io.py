"""Run-history persistence (JSON records under the cache dir)."""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from .. import cache as cache_module
from .types import RUN_RECORD_SCHEMA_VERSION, RunRecord, RunSummary

DEFAULT_RUN_HISTORY_LIMIT = 50

_RUN_JSON_SUFFIX = ".json"
_SUMMARY_SUFFIX = ".summary"


def get_runs_dir() -> Path:
    return cache_module.get_cache_dir() / "runs"


def runs_dir_location() -> Path:
    """The run-history directory path without creating it."""
    return cache_module.cache_dir_location() / "runs"


def get_runs_dir_or_none() -> Path | None:
    """The run-history directory, or ``None`` when the cache is unusable."""
    cache_dir = cache_module.get_cache_dir_or_none()
    return None if cache_dir is None else cache_dir / "runs"


def _run_path(runs_dir: Path, run_id: str) -> Path:
    return runs_dir / f"{run_id}{_RUN_JSON_SUFFIX}"


def _summary_path(runs_dir: Path, run_id: str) -> Path:
    return runs_dir / f"{run_id}{_SUMMARY_SUFFIX}"


def _generate_run_id() -> str:
    """A sortable run id that stays unique when the clock repeats.

    The microsecond timestamp alone collides on a stepped or frozen clock, so a
    short random suffix keeps two runs in the same microsecond apart.
    """
    return f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:6]}"


def save_run(record: RunRecord, *, runs_dir: Path | None = None) -> RunRecord:
    """Persist a run record and return the stored record (with generated id)."""
    resolved_runs_dir = get_runs_dir() if runs_dir is None else runs_dir
    resolved_runs_dir.mkdir(parents=True, exist_ok=True)

    stored_record = record
    if not stored_record.run_id or _run_path(resolved_runs_dir, stored_record.run_id).exists():
        # A frozen or stepped clock can repeat an id, and a caller may pass an
        # id that is already stored. Never overwrite an existing run.
        run_id = _generate_run_id()
        while _run_path(resolved_runs_dir, run_id).exists():
            run_id = _generate_run_id()
        stored_record = replace(record, run_id=run_id)

    payload = stored_record.to_dict()
    _atomic_write_json(_run_path(resolved_runs_dir, stored_record.run_id), payload)

    _write_summary(resolved_runs_dir, RunSummary.from_record(stored_record))
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
        _remove_summary(resolved_runs_dir, summary.run_id)
        removed += 1
    return removed


def list_runs(*, runs_dir: Path | None = None) -> tuple[RunSummary, ...]:
    """List persisted runs newest-first.

    Summaries are read from small per-run sidecar files so a run with a large
    finding set is not fully parsed just to populate the run list. Runs written
    before the sidecar existed are parsed once and backfilled.
    """
    resolved_runs_dir = get_runs_dir() if runs_dir is None else runs_dir
    if not resolved_runs_dir.exists():
        return ()

    summaries: list[RunSummary] = []
    for path in sorted(resolved_runs_dir.glob(f"*{_RUN_JSON_SUFFIX}"), key=lambda p: p.name, reverse=True):
        run_id = path.name[: -len(_RUN_JSON_SUFFIX)]
        summary = _load_summary(resolved_runs_dir, run_id)
        if summary is None:
            record = _load_run_file(path)
            if record is None:
                continue
            summary = RunSummary.from_record(record)
            _write_summary(resolved_runs_dir, summary)
        summaries.append(summary)
    return tuple(summaries)


def load_run(run_id: str, *, runs_dir: Path | None = None) -> RunRecord | None:
    resolved_runs_dir = get_runs_dir() if runs_dir is None else runs_dir
    return _load_run_file(_run_path(resolved_runs_dir, run_id))


def delete_run(run_id: str, *, runs_dir: Path | None = None) -> bool:
    """Delete a persisted run by id, returning True when a file was removed."""
    resolved_runs_dir = get_runs_dir() if runs_dir is None else runs_dir
    path = _run_path(resolved_runs_dir, run_id)
    if not path.exists():
        return False
    try:
        path.unlink()
    except OSError:
        return False
    _remove_summary(resolved_runs_dir, run_id)
    return True


def _load_summary(runs_dir: Path, run_id: str) -> RunSummary | None:
    path = _summary_path(runs_dir, run_id)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return RunSummary.from_dict(cast(dict[str, object], payload))


def _atomic_write_json(path: Path, payload: object) -> None:
    """Write JSON through a unique temp file and an atomic replace.

    A crash mid-write then leaves the previous record (or no record) instead of
    a truncated one that no pruner can recognise.
    """
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except (OSError, TypeError, ValueError):
        with contextlib.suppress(OSError):
            temp_path.unlink()
        raise


def _write_summary(runs_dir: Path, summary: RunSummary) -> None:
    try:
        _atomic_write_json(_summary_path(runs_dir, summary.run_id), summary.to_dict())
    except (OSError, TypeError, ValueError):
        return


def _remove_summary(runs_dir: Path, run_id: str) -> None:
    try:
        _summary_path(runs_dir, run_id).unlink()
    except OSError:
        return


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
    "delete_run",
    "get_runs_dir",
    "get_runs_dir_or_none",
    "list_runs",
    "load_run",
    "prune_runs",
    "runs_dir_location",
    "save_run",
]
