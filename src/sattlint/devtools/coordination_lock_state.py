from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, TypedDict, cast

from sattlint.devtools import _coordination_lock_paths as lock_paths
from sattlint.devtools.json_helpers import json_mapping as _json_mapping

LEDGER_FILE_NAME = "current-work.md"
LEDGER_TEMPLATE_NAME = "current-work.template.md"
LOCK_STATE_FILE_NAME = "current_work_lock.json"
SUMMARY_FILE_NAME = "current_work_summary.json"
SHARED_COORDINATION_DIR_NAME = "sattlint-ai-coordination"
LOCKFILE_NAME = f"{LOCK_STATE_FILE_NAME}.write.lock"
LOCK_ACQUIRE_TIMEOUT_SECONDS = 5.0
LOCK_ACQUIRE_POLL_INTERVAL_SECONDS = 0.05
FILE_DEBT_RATCHET_PATH = "artifacts/analysis/file_debt_ratchet.json"
ACTIVE_STATUSES = frozenset({"planned", "active", "blocked", "ready-for-merge"})
VALID_STATUSES = ACTIVE_STATUSES | frozenset({"done"})
TASK_CONTRACTS_DIR = Path(".ai/tasks")
HANDOFFS_DIR = Path(".ai/handoffs")
DEPRECATED_LOCK_CLAIM_PATH = f".github/coordination/{LOCK_STATE_FILE_NAME}"
SUPPORTED_STAGE_BRANCH_PREFIXES = ("ai/task-", "test/task-", "review/task-")
STALE_ENTRY_GRACE_PERIOD = timedelta(hours=12)
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
    path: Path
    is_directory: bool


class ClaimedFileDebtEntry(TypedDict):
    path: str
    dimensions: list[str]
    touch_rules: dict[str, str]
    structural_current_baseline: int | None
    structural_target: int | None
    structural_touch_rule: str | None
    reasons: list[str]


def utc_now_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _json_mapping_sequence(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    entries: list[Mapping[str, Any]] = []
    for item in cast(list[object], value):
        entry = _json_mapping(item)
        if entry is not None:
            entries.append(entry)
    return entries


coordination_dir = lock_paths.coordination_dir
git_common_dir = lock_paths.git_common_dir
shared_coordination_dir = partial(
    lock_paths.shared_coordination_dir,
    shared_coordination_dir_name=SHARED_COORDINATION_DIR_NAME,
)
ledger_path = partial(lock_paths.ledger_path, ledger_file_name=LEDGER_FILE_NAME)
template_path = partial(lock_paths.template_path, ledger_template_name=LEDGER_TEMPLATE_NAME)
legacy_lock_state_path = partial(lock_paths.legacy_lock_state_path, lock_state_file_name=LOCK_STATE_FILE_NAME)
lock_state_path = partial(
    lock_paths.lock_state_path,
    shared_coordination_dir_name=SHARED_COORDINATION_DIR_NAME,
    lock_state_file_name=LOCK_STATE_FILE_NAME,
)
summary_path = partial(lock_paths.summary_path, summary_file_name=SUMMARY_FILE_NAME)
display_path = lock_paths.display_path
_parse_attached_worktree_branches = lock_paths.parse_attached_worktree_branches
_attached_worktree_branches = lock_paths.attached_worktree_branches
_task_contract_path_for_workstream = partial(
    lock_paths.task_contract_path_for_workstream,
    task_contracts_dir=TASK_CONTRACTS_DIR,
)
_handoff_path_for_workstream = partial(
    lock_paths.handoff_path_for_workstream,
    handoffs_dir=HANDOFFS_DIR,
)
_expected_workstream_branches = partial(
    lock_paths.expected_workstream_branches,
    supported_stage_branch_prefixes=SUPPORTED_STAGE_BRANCH_PREFIXES,
)
_parse_updated_at_timestamp = lock_paths.parse_updated_at_timestamp
_entry_has_supporting_artifact = partial(
    lock_paths.entry_has_supporting_artifact,
    task_contract_path_for_workstream=_task_contract_path_for_workstream,
    handoff_path_for_workstream=_handoff_path_for_workstream,
)
_entry_is_stale = partial(
    lock_paths.entry_is_stale,
    entry_has_supporting_artifact=_entry_has_supporting_artifact,
    expected_workstream_branches=_expected_workstream_branches,
    parse_updated_at_timestamp=_parse_updated_at_timestamp,
    deprecated_lock_claim_path=DEPRECATED_LOCK_CLAIM_PATH,
    stale_entry_grace_period=STALE_ENTRY_GRACE_PERIOD,
)


def _prune_stale_entries(repo_root: Path, entries: list[LockStateEntry]) -> tuple[list[LockStateEntry], int]:
    attached_worktree_branches = _attached_worktree_branches(repo_root)
    now = datetime.now(UTC)
    return lock_paths.prune_stale_entries(
        repo_root,
        entries,
        attached_worktree_branches=attached_worktree_branches,
        now=now,
        active_statuses=ACTIVE_STATUSES,
        entry_is_stale=_entry_is_stale,
    )


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
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


normalize_relative_path = lock_paths.normalize_relative_path
normalize_claim_path = lock_paths.normalize_claim_path
split_claim_text = partial(lock_paths.split_claim_text, backtick_item_re=BACKTICK_ITEM_RE)
unique_claim_paths = lock_paths.unique_claim_paths
resolve_workspace_path = lock_paths.resolve_workspace_path
resolve_claim_patterns = lock_paths.resolve_claim_patterns


def load_file_debt_state(repo_root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    ratchet_path = repo_root / FILE_DEBT_RATCHET_PATH
    if not ratchet_path.exists():
        return {}

    try:
        payload = _json_mapping(json.loads(ratchet_path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if payload is None:
        return {}
    raw_files = payload.get("files", {})
    if not isinstance(raw_files, dict):
        return {}

    normalized: dict[str, dict[str, dict[str, Any]]] = {}
    for raw_path, raw_dimensions in cast(Mapping[object, object], raw_files).items():
        if not isinstance(raw_dimensions, Mapping):
            continue
        raw_dimensions_mapping = cast(Mapping[str, Any], raw_dimensions)
        rel_path = normalize_relative_path(str(raw_path))
        if not rel_path:
            continue
        dimensions: dict[str, dict[str, Any]] = {}
        for dimension in ("structural", "typing", "coverage"):
            raw_dimension = raw_dimensions_mapping.get(dimension)
            if isinstance(raw_dimension, Mapping):
                dimensions[dimension] = dict(cast(Mapping[str, Any], raw_dimension))
        if dimensions:
            normalized[rel_path] = dimensions
    return normalized


_claim_matches_path = lock_paths.claim_matches_path


def _effective_structural_touch_rule(structural: Mapping[str, Any]) -> str | None:
    raw_touch_rule = structural.get("touch_rule")
    if raw_touch_rule is None:
        return None
    touch_rule = str(raw_touch_rule)
    try:
        baseline = int(structural["current_baseline"])
        target = int(structural["target"])
    except (KeyError, TypeError, ValueError):
        return touch_rule
    if baseline > target and touch_rule == "must_not_grow":
        return "must_shrink"
    if baseline <= target:
        return "must_meet_target"
    return touch_rule


def claimed_file_debt_entries(
    repo_root: Path,
    claimed_paths: list[str] | tuple[str, ...],
) -> list[ClaimedFileDebtEntry]:
    normalized_claims = unique_claim_paths(claimed_paths, repo_root=repo_root)
    if not normalized_claims:
        return []

    matches: list[ClaimedFileDebtEntry] = []
    for rel_path, dimensions in sorted(load_file_debt_state(repo_root).items()):
        if not any(_claim_matches_path(claim, rel_path) for claim in normalized_claims):
            continue
        structural = dimensions.get("structural")
        touch_rules: dict[str, str] = {}
        for dimension, raw_dimension in sorted(dimensions.items()):
            if raw_dimension.get("touch_rule") is None:
                continue
            if dimension == "structural":
                touch_rule = _effective_structural_touch_rule(raw_dimension)
            else:
                touch_rule = str(raw_dimension.get("touch_rule"))
            if touch_rule is None:
                continue
            touch_rules[dimension] = touch_rule
        reasons = [
            str(reason).strip()
            for reason in (dimension.get("reason") for dimension in dimensions.values())
            if str(reason).strip()
        ]
        matches.append(
            {
                "path": rel_path,
                "dimensions": sorted(dimensions),
                "touch_rules": touch_rules,
                "structural_current_baseline": (
                    int(structural["current_baseline"]) if structural and "current_baseline" in structural else None
                ),
                "structural_target": int(structural["target"]) if structural and "target" in structural else None,
                "structural_touch_rule": (
                    _effective_structural_touch_rule(structural) if structural is not None else None
                ),
                "reasons": reasons,
            }
        )
    return matches


def claimed_oversized_structural_debt_entries(
    repo_root: Path,
    claimed_paths: list[str] | tuple[str, ...],
) -> list[ClaimedFileDebtEntry]:
    oversized: list[ClaimedFileDebtEntry] = []
    for entry in claimed_file_debt_entries(repo_root, claimed_paths):
        baseline = entry["structural_current_baseline"]
        target = entry["structural_target"]
        if baseline is None or target is None:
            continue
        if baseline > target:
            oversized.append(entry)
    return oversized


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

    raw_claims: object = raw_entry.get("claimed_paths") or raw_entry.get("claims") or []
    if isinstance(raw_claims, str):
        claim_items = split_claim_text(raw_claims)
    elif isinstance(raw_claims, list):
        claim_items = [str(item) for item in cast(list[object], raw_claims)]
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
    normalized_entries = _json_mapping_sequence(cast(object, raw_entries_obj))
    return _normalize_entries(normalized_entries, repo_root=repo_root, default_updated_at=default_updated_at)


def _write_lock_state_files(repo_root: Path, entries: list[LockStateEntry]) -> list[LockStateEntry]:
    repo_root = repo_root.resolve()
    normalized_entries = _normalize_entries(entries, repo_root=repo_root, default_updated_at=utc_now_timestamp())
    normalized_entries, _ = _prune_stale_entries(repo_root, normalized_entries)
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
        pruned_entries, dropped_entries = _prune_stale_entries(repo_root, entries)
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
    "FILE_DEBT_RATCHET_PATH",
    "LEDGER_FILE_NAME",
    "LEDGER_TEMPLATE_NAME",
    "LOCK_STATE_FILE_NAME",
    "SUMMARY_FILE_NAME",
    "ClaimPattern",
    "ClaimedFileDebtEntry",
    "LockStateEntry",
    "claimed_file_debt_entries",
    "claimed_oversized_structural_debt_entries",
    "coordination_dir",
    "display_path",
    "git_common_dir",
    "ledger_path",
    "legacy_lock_state_path",
    "load_file_debt_state",
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
