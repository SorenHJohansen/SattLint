"""Build a live snapshot of sparse per-file debt against current repository metrics."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from .artifact_registry import CURRENT_DEBT_SNAPSHOT_SCHEMA_KIND, CURRENT_DEBT_SNAPSHOT_SCHEMA_VERSION
from .json_helpers import json_mapping as _json_mapping

FILE_DEBT_RATCHET_PATH = Path("artifacts") / "analysis" / "file_debt_ratchet.json"


def _normalize_file_debt_entries(payload: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    raw_files = payload.get("files")
    if not isinstance(raw_files, dict):
        raise ValueError("file_debt_ratchet.json must contain a files object.")

    normalized: dict[str, dict[str, dict[str, Any]]] = {}
    for raw_path, raw_dimensions in sorted(
        cast(dict[object, object], raw_files).items(), key=lambda item: str(item[0])
    ):
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("file_debt_ratchet.json contains an invalid path key.")
        if not isinstance(raw_dimensions, dict) or not raw_dimensions:
            raise ValueError(f"file_debt_ratchet.json entry for {raw_path!r} must be a non-empty object.")
        raw_dimensions_dict = cast(dict[object, object], raw_dimensions)
        normalized_dimensions: dict[str, dict[str, Any]] = {}
        for dimension, dimension_payload in sorted(raw_dimensions_dict.items(), key=lambda item: str(item[0])):
            if isinstance(dimension_payload, dict):
                normalized_dimensions[str(dimension)] = dict(cast(dict[str, Any], dimension_payload))
        normalized[raw_path] = normalized_dimensions
    return normalized


def _load_file_debt_entries(repo_root: Path) -> tuple[dict[str, dict[str, dict[str, Any]]], str | None]:
    ledger_path = repo_root / FILE_DEBT_RATCHET_PATH
    if not ledger_path.exists():
        return {}, f"{FILE_DEBT_RATCHET_PATH.as_posix()} not found"

    try:
        payload = _json_mapping(json.loads(ledger_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"{FILE_DEBT_RATCHET_PATH.as_posix()} could not be read: {exc}"

    if payload is None:
        return {}, f"{FILE_DEBT_RATCHET_PATH.as_posix()} must contain a JSON object"

    try:
        return _normalize_file_debt_entries(payload), None
    except ValueError as exc:
        return {}, str(exc)


def _coverage_basis_points_by_path(coverage_summary_report: Mapping[str, Any] | None) -> dict[str, int]:
    if not isinstance(coverage_summary_report, Mapping) or coverage_summary_report.get("skipped"):
        return {}

    modules = coverage_summary_report.get("modules")
    if not isinstance(modules, list):
        return {}

    coverage_by_path: dict[str, int] = {}
    for module in cast(list[object], modules):
        if not isinstance(module, Mapping):
            continue
        module_mapping = cast(Mapping[str, Any], module)
        path = module_mapping.get("path")
        line_rate = module_mapping.get("line_rate")
        if not isinstance(path, str) or line_rate is None:
            continue
        try:
            coverage_by_path[path] = round(float(line_rate) * 10000)
        except (TypeError, ValueError):
            continue
    return coverage_by_path


def _structural_dimension_snapshot(entry: Mapping[str, Any], *, current_lines: int | None) -> dict[str, Any]:
    target = int(entry.get("target") or 0)
    current_baseline = int(entry.get("current_baseline") or 0)
    status = "missing_runtime_metric"
    delta = None
    if current_lines is not None:
        delta = current_lines - target
        status = "stale" if current_lines <= target else "active"
    return {
        "status": status,
        "current_value": current_lines,
        "current_baseline": current_baseline,
        "target": target,
        "delta_from_target": delta,
        "touch_rule": entry.get("touch_rule"),
        "reason": entry.get("reason"),
    }


def _coverage_dimension_snapshot(entry: Mapping[str, Any], *, basis_points: int | None) -> dict[str, Any]:
    target = int(entry.get("target") or 0)
    current_baseline = int(entry.get("current_baseline") or 0)
    status = "missing_runtime_metric"
    delta = None
    if basis_points is not None:
        delta = basis_points - target
        status = "stale" if basis_points >= target else "active"
    return {
        "status": status,
        "current_value": basis_points,
        "current_baseline": current_baseline,
        "target": target,
        "delta_from_target": delta,
        "touch_rule": entry.get("touch_rule"),
        "reason": entry.get("reason"),
    }


def build_current_debt_snapshot_report(
    repo_root: Path,
    *,
    structural_budget_report: Mapping[str, Any] | None,
    coverage_summary_report: Mapping[str, Any] | None,
) -> dict[str, Any]:
    entries, load_error = _load_file_debt_entries(repo_root)
    structural_counts_raw = None
    if isinstance(structural_budget_report, Mapping):
        structural_counts_raw = structural_budget_report.get("current_file_line_counts")
    structural_counts = (
        {
            str(path): int(count)
            for path, count in cast(Mapping[object, object], structural_counts_raw).items()
            if isinstance(count, int)
        }
        if isinstance(structural_counts_raw, Mapping)
        else {}
    )
    coverage_by_path = _coverage_basis_points_by_path(coverage_summary_report)

    files: dict[str, dict[str, Any]] = {}
    stale_count = 0
    active_count = 0
    missing_runtime_metric_count = 0
    policy_only_count = 0
    dimension_count = 0

    for rel_path, dimensions in entries.items():
        file_snapshot: dict[str, Any] = {}
        if "structural" in dimensions:
            dimension_count += 1
            snapshot = _structural_dimension_snapshot(
                dimensions["structural"],
                current_lines=structural_counts.get(rel_path),
            )
            file_snapshot["structural"] = snapshot
            if snapshot["status"] == "stale":
                stale_count += 1
            elif snapshot["status"] == "active":
                active_count += 1
            else:
                missing_runtime_metric_count += 1
        if "coverage" in dimensions:
            dimension_count += 1
            snapshot = _coverage_dimension_snapshot(
                dimensions["coverage"],
                basis_points=coverage_by_path.get(rel_path),
            )
            file_snapshot["coverage"] = snapshot
            if snapshot["status"] == "stale":
                stale_count += 1
            elif snapshot["status"] == "active":
                active_count += 1
            else:
                missing_runtime_metric_count += 1
        if "typing" in dimensions:
            dimension_count += 1
            policy_only_count += 1
            file_snapshot["typing"] = {
                "status": "policy_only",
                "touch_rule": dimensions["typing"].get("touch_rule"),
                "reason": dimensions["typing"].get("reason"),
            }
        files[rel_path] = file_snapshot

    skipped = load_error is not None
    return {
        "kind": CURRENT_DEBT_SNAPSHOT_SCHEMA_KIND,
        "schema_version": CURRENT_DEBT_SNAPSHOT_SCHEMA_VERSION,
        "generated_by": "sattlint.devtools.current_debt_snapshot",
        "skipped": skipped,
        "skip_reason": load_error,
        "ledger_path": FILE_DEBT_RATCHET_PATH.as_posix(),
        "summary": {
            "file_count": len(files),
            "dimension_count": dimension_count,
            "active_count": active_count,
            "stale_count": stale_count,
            "missing_runtime_metric_count": missing_runtime_metric_count,
            "policy_only_count": policy_only_count,
        },
        "sources": {
            "structural_budget_report": None
            if not isinstance(structural_budget_report, Mapping)
            else ("skipped" if structural_budget_report.get("skipped") else "current"),
            "coverage_summary_report": None
            if not isinstance(coverage_summary_report, Mapping)
            else ("skipped" if coverage_summary_report.get("skipped") else "current"),
        },
        "files": files,
    }


__all__ = [
    "CURRENT_DEBT_SNAPSHOT_SCHEMA_KIND",
    "CURRENT_DEBT_SNAPSHOT_SCHEMA_VERSION",
    "build_current_debt_snapshot_report",
]
