from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

from ._coordination_lock_shared import (
    LOCKFILE_NAME,
    LockStateEntry,
    coordination_dir,
    display_path,
    json_mapping_sequence,
    ledger_path,
    legacy_lock_state_path,
    lock_state_path,
    prune_stale_entries,
    shared_coordination_dir,
    utc_now_timestamp,
)
from .coordination_ledger import parse_markdown_ledger
from .coordination_tasks import normalize_entries, normalize_entry


def _write_text_atomically(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


@contextmanager
def _hold_lock(repo_root: Path):
    shared_dir = shared_coordination_dir(repo_root)
    shared_dir.mkdir(parents=True, exist_ok=True)
    lock_path = shared_dir / LOCKFILE_NAME
    deadline = time.monotonic() + 5.0
    lock_fd: int | None = None
    while lock_fd is None:
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, str(os.getpid()).encode("utf-8"))
        except FileExistsError as exc:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out acquiring coordination lock {lock_path.as_posix()}.") from exc
            time.sleep(0.05)
    try:
        yield
    finally:
        os.close(lock_fd)
        try:
            current_pid_text = lock_path.read_text(encoding="utf-8").strip()
        except OSError:
            current_pid_text = ""
        if current_pid_text == str(os.getpid()):
            lock_path.unlink(missing_ok=True)


def _load_state_entries(repo_root: Path, state_file: Path, *, default_updated_at: str) -> list[LockStateEntry]:
    try:
        payload: object = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if isinstance(payload, dict):
        raw_entries_obj: object = cast(dict[str, Any], payload).get("workstreams", [])
    elif isinstance(payload, list):
        raw_entries_obj = cast(list[object], payload)
    else:
        raise ValueError(f"Unsupported lock-state payload in {state_file}.")
    if not isinstance(raw_entries_obj, list):
        raise ValueError(f"Lock-state workstreams must be a list in {state_file}.")
    normalized_entries = json_mapping_sequence(cast(object, raw_entries_obj))
    return normalize_entries(normalized_entries, repo_root=repo_root, default_updated_at=default_updated_at)


def _write_lock_state_files(repo_root: Path, entries: list[LockStateEntry]) -> list[LockStateEntry]:
    repo_root = repo_root.resolve()
    normalized_entries = normalize_entries(entries, repo_root=repo_root, default_updated_at=utc_now_timestamp())
    normalized_entries, _ = prune_stale_entries(repo_root, normalized_entries)
    coordination_dir(repo_root).mkdir(parents=True, exist_ok=True)
    shared_coordination_dir(repo_root).mkdir(parents=True, exist_ok=True)
    state_file = lock_state_path(repo_root)
    _write_text_atomically(state_file, json.dumps({"workstreams": normalized_entries}, indent=2) + "\n")
    ledger_path(repo_root).unlink(missing_ok=True)

    legacy_state_file = legacy_lock_state_path(repo_root)
    if legacy_state_file != state_file and legacy_state_file.exists():
        legacy_state_file.unlink()
    return normalized_entries


def write_lock_state(repo_root: Path, entries: list[LockStateEntry]) -> list[LockStateEntry]:
    repo_root = repo_root.resolve()
    with _hold_lock(repo_root):
        return _write_lock_state_files(repo_root, entries)


def load_lock_state(repo_root: Path) -> list[LockStateEntry]:
    repo_root = repo_root.resolve()
    default_updated_at = utc_now_timestamp()
    state_file = lock_state_path(repo_root)
    legacy_state_file = legacy_lock_state_path(repo_root)

    if state_file.exists():
        entries = _load_state_entries(repo_root, state_file, default_updated_at=default_updated_at)
        pruned_entries, dropped_entries = prune_stale_entries(repo_root, entries)
        if dropped_entries:
            return write_lock_state(repo_root, pruned_entries)
        return pruned_entries

    if legacy_state_file.exists():
        entries = _load_state_entries(repo_root, legacy_state_file, default_updated_at=default_updated_at)
        return write_lock_state(repo_root, entries)

    return []


def _load_existing_entries_for_update(repo_root: Path, *, default_updated_at: str) -> list[LockStateEntry]:
    state_file = lock_state_path(repo_root)
    if state_file.exists():
        return _load_state_entries(repo_root, state_file, default_updated_at=default_updated_at)

    legacy_state_file = legacy_lock_state_path(repo_root)
    if legacy_state_file.exists():
        return _load_state_entries(repo_root, legacy_state_file, default_updated_at=default_updated_at)
    return []


def upsert_workstream(
    repo_root: Path,
    *,
    workstream_id: str,
    owner: str,
    status: str,
    claimed_paths: list[str] | tuple[str, ...],
    first_validation: str,
) -> LockStateEntry:
    repo_root = repo_root.resolve()
    updated_at = utc_now_timestamp()
    raw_entry = {
        "workstream_id": workstream_id,
        "owner": owner,
        "status": status,
        "claimed_paths": list(claimed_paths),
        "updated_at": updated_at,
        "first_validation": first_validation,
    }
    normalized_entry = normalize_entry(raw_entry, repo_root=repo_root, default_updated_at=updated_at)
    if normalized_entry is None:
        raise ValueError("Cannot write a done or empty workstream entry to the active lock state.")

    with _hold_lock(repo_root):
        existing = [
            entry
            for entry in _load_existing_entries_for_update(repo_root, default_updated_at=updated_at)
            if entry["workstream_id"].casefold() != workstream_id.casefold()
        ]
        _write_lock_state_files(repo_root, [normalized_entry, *existing])
    return normalized_entry


def migrate_current_work_ledger(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    source_file = ledger_path(repo_root)
    source_relative = source_file.relative_to(repo_root).as_posix() if source_file.exists() else None

    if source_file.exists():
        entries, dropped_done = parse_markdown_ledger(
            source_file.read_text(encoding="utf-8"),
            repo_root=repo_root,
        )
    else:
        entries = []
        dropped_done = 0

    normalized_entries = write_lock_state(repo_root, entries)
    source_file.unlink(missing_ok=True)
    return {
        "source": source_relative,
        "lock_state": display_path(lock_state_path(repo_root), repo_root),
        "active_workstream_count": len(normalized_entries),
        "dropped_done_workstream_count": dropped_done,
    }
