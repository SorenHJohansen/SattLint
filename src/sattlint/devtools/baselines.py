"""Helpers for comparing normalized finding collections against a baseline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sattlint.contracts import FindingCollection, FindingRecord

ANALYSIS_DIFF_SCHEMA_KIND = "sattlint.analysis_diff"
ANALYSIS_DIFF_SCHEMA_VERSION = 1


def load_finding_collection(path: Path) -> FindingCollection:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return FindingCollection.from_dict(payload)


def _finding_sort_key(finding: FindingRecord) -> tuple[str, int, str, str, str]:
    return (
        finding.location.path or "",
        finding.location.line or 0,
        finding.rule_id,
        finding.message,
        finding.fingerprint or "",
    )


def _finding_anchor(finding: FindingRecord) -> tuple[str, str | None, int | None, str | None]:
    return (
        finding.rule_id,
        finding.location.path,
        finding.location.line,
        finding.location.symbol,
    )


def _group_by_fingerprint(findings: tuple[FindingRecord, ...]) -> dict[str, list[FindingRecord]]:
    grouped: dict[str, list[FindingRecord]] = {}
    for finding in sorted(findings, key=_finding_sort_key):
        fingerprint = finding.fingerprint or ""
        grouped.setdefault(fingerprint, []).append(finding)
    return grouped


def _group_by_anchor(findings: list[FindingRecord]) -> dict[tuple[str, str | None, int | None, str | None], list[FindingRecord]]:
    grouped: dict[tuple[str, str | None, int | None, str | None], list[FindingRecord]] = {}
    for finding in sorted(findings, key=_finding_sort_key):
        grouped.setdefault(_finding_anchor(finding), []).append(finding)
    return grouped


def _change_details(baseline: FindingRecord, current: FindingRecord) -> dict[str, Any]:
    changed_fields: list[str] = []
    for field_name in (
        "id",
        "message",
        "severity",
        "confidence",
        "source",
        "analyzer",
        "artifact",
        "detail",
        "suggestion",
    ):
        if getattr(baseline, field_name) != getattr(current, field_name):
            changed_fields.append(field_name)
    if baseline.location != current.location:
        changed_fields.append("location")
    if baseline.data != current.data:
        changed_fields.append("data")
    return {
        "changed_fields": changed_fields,
        "baseline_fingerprint": baseline.fingerprint,
        "current_fingerprint": current.fingerprint,
    }


def build_analysis_diff_report(
    *,
    baseline: FindingCollection,
    current: FindingCollection,
    baseline_label: str = "baseline",
    current_label: str = "current",
) -> dict[str, Any]:
    baseline_by_fingerprint = _group_by_fingerprint(baseline.findings)
    current_by_fingerprint = _group_by_fingerprint(current.findings)

    unchanged: list[FindingRecord] = []
    remaining_baseline: list[FindingRecord] = []
    remaining_current: list[FindingRecord] = []

    for fingerprint in sorted(set(baseline_by_fingerprint) | set(current_by_fingerprint)):
        baseline_matches = baseline_by_fingerprint.get(fingerprint, [])
        current_matches = current_by_fingerprint.get(fingerprint, [])
        matched_count = min(len(baseline_matches), len(current_matches))
        unchanged.extend(current_matches[:matched_count])
        remaining_baseline.extend(baseline_matches[matched_count:])
        remaining_current.extend(current_matches[matched_count:])

    baseline_by_anchor = _group_by_anchor(remaining_baseline)
    current_by_anchor = _group_by_anchor(remaining_current)

    changed: list[dict[str, Any]] = []
    resolved: list[FindingRecord] = []
    new: list[FindingRecord] = []

    for anchor in sorted(set(baseline_by_anchor) | set(current_by_anchor)):
        baseline_matches = baseline_by_anchor.get(anchor, [])
        current_matches = current_by_anchor.get(anchor, [])
        matched_count = min(len(baseline_matches), len(current_matches))

        for baseline_finding, current_finding in zip(
            baseline_matches[:matched_count],
            current_matches[:matched_count],
            strict=False,
        ):
            changed.append(
                {
                    "baseline": baseline_finding.to_dict(),
                    "current": current_finding.to_dict(),
                    "change": _change_details(baseline_finding, current_finding),
                }
            )

        resolved.extend(baseline_matches[matched_count:])
        new.extend(current_matches[matched_count:])

    unchanged_payload = [finding.to_dict() for finding in sorted(unchanged, key=_finding_sort_key)]
    new_payload = [finding.to_dict() for finding in sorted(new, key=_finding_sort_key)]
    resolved_payload = [finding.to_dict() for finding in sorted(resolved, key=_finding_sort_key)]
    changed_payload = sorted(
        changed,
        key=lambda item: (
            item["current"]["location"]["path"] or item["baseline"]["location"]["path"] or "",
            item["current"]["location"]["line"] or item["baseline"]["location"]["line"] or 0,
            item["current"]["rule_id"],
        ),
    )

    return {
        "kind": ANALYSIS_DIFF_SCHEMA_KIND,
        "schema_version": ANALYSIS_DIFF_SCHEMA_VERSION,
        "baseline": {
            "label": baseline_label,
            "finding_count": len(baseline.findings),
        },
        "current": {
            "label": current_label,
            "finding_count": len(current.findings),
        },
        "summary": {
            "new_count": len(new_payload),
            "resolved_count": len(resolved_payload),
            "changed_count": len(changed_payload),
            "unchanged_count": len(unchanged_payload),
        },
        "findings": {
            "new": new_payload,
            "resolved": resolved_payload,
            "changed": changed_payload,
            "unchanged": unchanged_payload,
        },
    }


__all__ = [
    "ANALYSIS_DIFF_SCHEMA_KIND",
    "ANALYSIS_DIFF_SCHEMA_VERSION",
    "build_analysis_diff_report",
    "load_finding_collection",
]
