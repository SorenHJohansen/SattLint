from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any, TypedDict

LEDGER_FILE_NAME = "current-work.md"
LEDGER_TEMPLATE_NAME = "current-work.template.md"
LOCK_STATE_FILE_NAME = "current_work_lock.json"
SUMMARY_FILE_NAME = "current_work_summary.json"
SHARED_COORDINATION_DIR_NAME = "sattlint-ai-coordination"
LOCKFILE_NAME = f"{LOCK_STATE_FILE_NAME}.write.lock"
LOCK_ACQUIRE_TIMEOUT_SECONDS = 5.0
LOCK_ACQUIRE_POLL_INTERVAL_SECONDS = 0.05
ACTIVE_STATUSES = frozenset({"planned", "active", "blocked", "ready-for-merge"})
VALID_STATUSES = ACTIVE_STATUSES | frozenset({"done"})
WORKSTREAM_RE = re.compile(r"^### Workstream\s+(?P<id>.+?)\s*$")
FIELD_RE = re.compile(r"^-\s+(?P<field>[A-Za-z][A-Za-z\-/ ]+):\s*(?P<value>.*)$")
BACKTICK_ITEM_RE = re.compile(r"`([^`]+)`")


class LockStateEntry(TypedDict):
    workstream_id: str
    owner: str
    status: str
    claimed_paths: list[str]
    updated_at: str
    first_validation: str


class ClaimPattern(TypedDict):
    raw: str
    path: Path
    is_directory: bool


def utc_now_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def coordination_dir(repo_root: Path) -> Path:
    return repo_root / ".github" / "coordination"


@cache
def git_common_dir(repo_root: Path) -> Path:
    resolved_repo_root = repo_root.resolve()
    completed = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=resolved_repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return (resolved_repo_root / ".git").resolve()

    raw_value = completed.stdout.strip() or ".git"
    path = Path(raw_value)
    if not path.is_absolute():
        path = (resolved_repo_root / path).resolve()
    return path.resolve()


def shared_coordination_dir(repo_root: Path) -> Path:
    return git_common_dir(repo_root) / SHARED_COORDINATION_DIR_NAME


def ledger_path(repo_root: Path) -> Path:
    return coordination_dir(repo_root) / LEDGER_FILE_NAME


def template_path(repo_root: Path) -> Path:
    return coordination_dir(repo_root) / LEDGER_TEMPLATE_NAME


def legacy_lock_state_path(repo_root: Path) -> Path:
    return coordination_dir(repo_root) / LOCK_STATE_FILE_NAME


def lock_state_path(repo_root: Path) -> Path:
    return shared_coordination_dir(repo_root) / LOCK_STATE_FILE_NAME


def summary_path(repo_root: Path) -> Path:
    return coordination_dir(repo_root) / SUMMARY_FILE_NAME


def display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


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
    deadline = time.monotonic() + LOCK_ACQUIRE_TIMEOUT_SECONDS
    lock_fd: int | None = None
    while lock_fd is None:
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, str(os.getpid()).encode("utf-8"))
        except FileExistsError as exc:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out acquiring coordination lock {lock_path.as_posix()}.") from exc
            time.sleep(LOCK_ACQUIRE_POLL_INTERVAL_SECONDS)
    try:
        yield
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


def normalize_relative_path(raw_path: str) -> str:
    normalized = raw_path.strip().strip("`'\"")
    normalized = normalized.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def normalize_claim_path(raw_path: str, *, repo_root: Path | None = None) -> str:
    normalized = normalize_relative_path(raw_path)
    if not normalized:
        return ""
    is_directory = raw_path.strip().rstrip().endswith(("/", "\\"))
    if not is_directory and repo_root is not None:
        is_directory = (repo_root / normalized).is_dir()
    return f"{normalized}/" if is_directory else normalized


def split_claim_text(raw_claims: str) -> list[str]:
    backtick_items = BACKTICK_ITEM_RE.findall(raw_claims)
    if backtick_items:
        return backtick_items
    return [part.strip() for part in raw_claims.split(",") if part.strip()]


def unique_claim_paths(values: list[str] | tuple[str, ...], *, repo_root: Path | None = None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = normalize_claim_path(raw_value, repo_root=repo_root)
        if not value:
            continue
        seen_key = value.casefold()
        if seen_key in seen:
            continue
        seen.add(seen_key)
        normalized.append(value)
    return normalized


def resolve_workspace_path(raw_path: str, cwd: Path) -> Path:
    path = Path(normalize_relative_path(raw_path))
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def resolve_claim_patterns(claimed_paths: list[str] | tuple[str, ...], cwd: Path) -> list[ClaimPattern]:
    patterns: list[ClaimPattern] = []
    for raw_path in claimed_paths:
        normalized = normalize_claim_path(raw_path, repo_root=cwd)
        if not normalized:
            continue
        patterns.append(
            {
                "raw": normalized,
                "path": resolve_workspace_path(normalized, cwd),
                "is_directory": normalized.endswith("/"),
            }
        )
    return patterns


def _normalize_status(raw_status: str) -> str:
    normalized = raw_status.strip().casefold()
    return normalized if normalized in VALID_STATUSES else "active"


def _split_workstream_blocks(text: str) -> tuple[list[str], list[list[str]]]:
    prefix: list[str] = []
    blocks: list[list[str]] = []
    current_block: list[str] | None = None

    for raw_line in text.splitlines(keepends=True):
        if WORKSTREAM_RE.match(raw_line.rstrip()):
            if current_block is not None:
                blocks.append(current_block)
            current_block = [raw_line]
            continue
        if current_block is None:
            prefix.append(raw_line)
            continue
        current_block.append(raw_line)

    if current_block is not None:
        blocks.append(current_block)
    return prefix, blocks


def _normalize_entry(
    raw_entry: Mapping[str, Any],
    *,
    repo_root: Path,
    default_updated_at: str,
) -> LockStateEntry | None:
    workstream_id = str(raw_entry.get("workstream_id") or raw_entry.get("id") or "").strip()
    if not workstream_id:
        return None

    status = _normalize_status(str(raw_entry.get("status") or "active"))
    if status == "done":
        return None

    raw_claims = raw_entry.get("claimed_paths") or raw_entry.get("claims") or []
    if isinstance(raw_claims, str):
        claim_items = split_claim_text(raw_claims)
    elif isinstance(raw_claims, list):
        claim_items = [str(item) for item in raw_claims]
    else:
        claim_items = []
    claimed_paths = unique_claim_paths(claim_items, repo_root=repo_root)
    if not claimed_paths:
        return None

    owner = str(raw_entry.get("owner") or "unknown").strip() or "unknown"
    first_validation = str(raw_entry.get("first_validation") or raw_entry.get("validation") or "").strip()
    updated_at = str(raw_entry.get("updated_at") or raw_entry.get("updated") or default_updated_at).strip()
    return {
        "workstream_id": workstream_id,
        "owner": owner,
        "status": status,
        "claimed_paths": claimed_paths,
        "updated_at": updated_at or default_updated_at,
        "first_validation": first_validation,
    }


def _normalize_entries(
    raw_entries: Sequence[Mapping[str, Any]],
    *,
    repo_root: Path,
    default_updated_at: str,
) -> list[LockStateEntry]:
    normalized: list[LockStateEntry] = []
    seen_ids: set[str] = set()
    for raw_entry in raw_entries:
        entry = _normalize_entry(raw_entry, repo_root=repo_root, default_updated_at=default_updated_at)
        if entry is None:
            continue
        seen_key = entry["workstream_id"].casefold()
        if seen_key in seen_ids:
            continue
        seen_ids.add(seen_key)
        normalized.append(entry)
    return normalized


def parse_markdown_ledger(
    text: str,
    *,
    repo_root: Path,
    default_updated_at: str | None = None,
) -> tuple[list[LockStateEntry], int]:
    resolved_updated_at = default_updated_at or utc_now_timestamp()
    _, blocks = _split_workstream_blocks(text)
    raw_entries: list[dict[str, Any]] = []
    dropped_done = 0

    for block in blocks:
        heading = block[0].rstrip()
        workstream_match = WORKSTREAM_RE.match(heading)
        if workstream_match is None:
            continue
        entry: dict[str, Any] = {"workstream_id": workstream_match.group("id").strip()}
        for raw_line in block[1:]:
            field_match = FIELD_RE.match(raw_line.lstrip().rstrip())
            if field_match is None:
                continue
            field = field_match.group("field").strip().casefold().replace(" ", "_")
            entry[field] = field_match.group("value").strip()
        if _normalize_status(str(entry.get("status") or "active")) == "done":
            dropped_done += 1
        raw_entries.append(
            {
                "workstream_id": entry.get("workstream_id", ""),
                "owner": entry.get("owner", "unknown"),
                "status": entry.get("status", "active"),
                "claims": entry.get("claims", ""),
                "updated_at": entry.get("updated", resolved_updated_at),
                "first_validation": entry.get("first_validation", ""),
            }
        )

    return (
        _normalize_entries(raw_entries, repo_root=repo_root, default_updated_at=resolved_updated_at),
        dropped_done,
    )


def _load_state_entries(repo_root: Path, state_file: Path, *, default_updated_at: str) -> list[LockStateEntry]:
    payload = json.loads(state_file.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        raw_entries = payload.get("workstreams", [])
    elif isinstance(payload, list):
        raw_entries = payload
    else:
        raise ValueError(f"Unsupported lock-state payload in {state_file}.")
    if not isinstance(raw_entries, list):
        raise ValueError(f"Lock-state workstreams must be a list in {state_file}.")
    return _normalize_entries(raw_entries, repo_root=repo_root, default_updated_at=default_updated_at)


def _write_lock_state_files(repo_root: Path, entries: list[LockStateEntry]) -> list[LockStateEntry]:
    repo_root = repo_root.resolve()
    normalized_entries = _normalize_entries(entries, repo_root=repo_root, default_updated_at=utc_now_timestamp())
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


def load_lock_state(repo_root: Path, *, sync_markdown_if_newer: bool = True) -> list[LockStateEntry]:
    repo_root = repo_root.resolve()
    default_updated_at = utc_now_timestamp()
    state_file = lock_state_path(repo_root)
    legacy_state_file = legacy_lock_state_path(repo_root)

    if state_file.exists():
        return _load_state_entries(repo_root, state_file, default_updated_at=default_updated_at)

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
    normalized_entry = _normalize_entry(raw_entry, repo_root=repo_root, default_updated_at=updated_at)
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


__all__ = [
    "ACTIVE_STATUSES",
    "LEDGER_FILE_NAME",
    "LEDGER_TEMPLATE_NAME",
    "LOCK_STATE_FILE_NAME",
    "SUMMARY_FILE_NAME",
    "ClaimPattern",
    "LockStateEntry",
    "coordination_dir",
    "display_path",
    "git_common_dir",
    "ledger_path",
    "legacy_lock_state_path",
    "load_lock_state",
    "lock_state_path",
    "migrate_current_work_ledger",
    "normalize_claim_path",
    "normalize_relative_path",
    "parse_markdown_ledger",
    "resolve_claim_patterns",
    "resolve_workspace_path",
    "shared_coordination_dir",
    "split_claim_text",
    "summary_path",
    "template_path",
    "unique_claim_paths",
    "upsert_workstream",
    "utc_now_timestamp",
    "write_lock_state",
]
