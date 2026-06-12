from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from sattlint.devtools.json_helpers import json_mapping as _json_mapping

from ._coordination_lock_shared import (
    FILE_DEBT_RATCHET_PATH,
    VALID_STATUSES,
    ClaimedFileDebtEntry,
    LockStateEntry,
    claim_matches_path,
    normalize_relative_path,
    split_claim_text,
    unique_claim_paths,
)


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
        if not any(claim_matches_path(claim, rel_path) for claim in normalized_claims):
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


def normalize_status(raw_status: str) -> str:
    normalized = raw_status.strip().casefold()
    return normalized if normalized in VALID_STATUSES else "active"


def normalize_entry(
    raw_entry: Mapping[str, Any],
    *,
    repo_root: Path,
    default_updated_at: str,
) -> LockStateEntry | None:
    workstream_id = str(raw_entry.get("workstream_id") or raw_entry.get("id") or "").strip()
    if not workstream_id:
        return None

    status = normalize_status(str(raw_entry.get("status") or "active"))
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


def normalize_entries(
    raw_entries: Sequence[Mapping[str, Any]],
    *,
    repo_root: Path,
    default_updated_at: str,
) -> list[LockStateEntry]:
    normalized: list[LockStateEntry] = []
    seen_ids: set[str] = set()
    for raw_entry in raw_entries:
        entry = normalize_entry(raw_entry, repo_root=repo_root, default_updated_at=default_updated_at)
        if entry is None:
            continue
        seen_key = entry["workstream_id"].casefold()
        if seen_key in seen_ids:
            continue
        seen_ids.add(seen_key)
        normalized.append(entry)
    return normalized
