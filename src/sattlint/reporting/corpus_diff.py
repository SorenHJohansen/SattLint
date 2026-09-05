"""Corpus differential reporting helpers (Phase 21).

Compare two corpus finding sets and surface the before/after diff: added
findings, removed findings, and per-rule count changes.  Findings are
identified by their stable finding id (rule id / kind), so the diff is
reviewable even when rule sets change between versions.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CountChange:
    finding_id: str
    before: int
    after: int


@dataclass(frozen=True, slots=True)
class CorpusDiff:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    count_changes: tuple[CountChange, ...]

    def is_empty(self) -> bool:
        return not self.added and not self.removed and not self.count_changes


def diff_corpus_findings(
    baseline: Iterable[str] | Counter[str] | dict[str, int],
    current: Iterable[str] | Counter[str] | dict[str, int],
) -> CorpusDiff:
    """Diff two corpus finding-id collections.

    ``baseline``/``current`` may be sequences of finding ids or
    ``{finding_id: count}`` mappings.  Finding identity is the stable rule id /
    kind, so the diff isolates added/removed findings and count changes.
    """
    baseline_counts = Counter(baseline)
    current_counts = Counter(current)

    all_ids = set(baseline_counts) | set(current_counts)
    added = sorted(
        finding_id
        for finding_id in all_ids
        if baseline_counts.get(finding_id, 0) == 0 and current_counts.get(finding_id, 0) > 0
    )
    removed = sorted(
        finding_id
        for finding_id in all_ids
        if baseline_counts.get(finding_id, 0) > 0 and current_counts.get(finding_id, 0) == 0
    )
    count_changes = tuple(
        CountChange(finding_id=finding_id, before=baseline_counts[finding_id], after=current_counts[finding_id])
        for finding_id in sorted(all_ids)
        if baseline_counts.get(finding_id, 0) != current_counts.get(finding_id, 0)
        and baseline_counts.get(finding_id, 0) > 0
        and current_counts.get(finding_id, 0) > 0
    )

    return CorpusDiff(added=tuple(added), removed=tuple(removed), count_changes=count_changes)


__all__ = ["CorpusDiff", "CountChange", "diff_corpus_findings"]
