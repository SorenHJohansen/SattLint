from __future__ import annotations

import re
from collections.abc import Mapping
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


def json_mapping_sequence(value: object) -> list[Mapping[str, Any]]:
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
normalize_relative_path = lock_paths.normalize_relative_path
normalize_claim_path = lock_paths.normalize_claim_path
split_claim_text = partial(lock_paths.split_claim_text, backtick_item_re=BACKTICK_ITEM_RE)
unique_claim_paths = lock_paths.unique_claim_paths
resolve_workspace_path = lock_paths.resolve_workspace_path
resolve_claim_patterns = lock_paths.resolve_claim_patterns
claim_matches_path = lock_paths.claim_matches_path

_parse_updated_at_timestamp = lock_paths.parse_updated_at_timestamp
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


def prune_stale_entries(repo_root: Path, entries: list[LockStateEntry]) -> tuple[list[LockStateEntry], int]:
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
