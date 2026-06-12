from __future__ import annotations

from pathlib import Path
from typing import Any

from ._coordination_lock_shared import FIELD_RE, WORKSTREAM_RE, LockStateEntry, utc_now_timestamp
from .coordination_tasks import normalize_entries, normalize_status


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
        if normalize_status(str(entry.get("status") or "active")) == "done":
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
        normalize_entries(raw_entries, repo_root=repo_root, default_updated_at=resolved_updated_at),
        dropped_done,
    )
