"""Differential analysis helpers for cross-version and cross-config comparisons."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sattlint.contracts import FindingCollection, FindingRecord

DIFFERENTIAL_SCHEMA_KIND = "sattlint.differential"
DIFFERENTIAL_SCHEMA_VERSION = 1


@dataclass
class DifferentialResult:
    baseline_label: str
    current_label: str
    added: list[FindingRecord]
    removed: list[FindingRecord]
    surviving: list[FindingRecord]
    config_drift: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": DIFFERENTIAL_SCHEMA_KIND,
            "schema_version": DIFFERENTIAL_SCHEMA_VERSION,
            "summary": {
                "baseline": self.baseline_label,
                "current": self.current_label,
                "added_count": len(self.added),
                "removed_count": len(self.removed),
                "surviving_count": len(self.surviving),
                "config_drift_count": len(self.config_drift),
            },
            "findings": {
                "added": [f.to_dict() for f in self.added],
                "removed": [f.to_dict() for f in self.removed],
                "surviving": [f.to_dict() for f in self.surviving],
            },
            "config_drift": self.config_drift,
        }


def build_differential_report(
    baseline: FindingCollection,
    current: FindingCollection,
    *,
    baseline_label: str = "baseline",
    current_label: str = "current",
    config_keys: list[str] | None = None,
) -> DifferentialResult:
    """Build a differential report comparing two analysis runs."""
    baseline_fps = {f.fingerprint for f in baseline.findings if f.fingerprint}
    current_fps = {f.fingerprint for f in current.findings if f.fingerprint}

    added = [f for f in current.findings if f.fingerprint and f.fingerprint not in baseline_fps]
    removed = [f for f in baseline.findings if f.fingerprint and f.fingerprint not in current_fps]
    surviving = [f for f in current.findings if f.fingerprint and f.fingerprint in baseline_fps]

    config_drift: list[str] = []
    if config_keys:
        baseline_by_key: dict[str, list[str]] = {}
        current_by_key: dict[str, list[str]] = {}

        for f in baseline.findings:
            if f.rule_id:
                baseline_by_key.setdefault(f.rule_id, []).append(f.severity or "")
        for f in current.findings:
            if f.rule_id:
                current_by_key.setdefault(f.rule_id, []).append(f.severity or "")

        for key in set(list(baseline_by_key) + list(current_by_key)):
            if baseline_by_key.get(key) != current_by_key.get(key):
                config_drift.append(key)

    return DifferentialResult(
        baseline_label=baseline_label,
        current_label=current_label,
        added=added,
        removed=removed,
        surviving=surviving,
        config_drift=config_drift,
    )


__all__ = [
    "DIFFERENTIAL_SCHEMA_KIND",
    "DIFFERENTIAL_SCHEMA_VERSION",
    "DifferentialResult",
    "build_differential_report",
]
