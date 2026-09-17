"""Read-before-write collection inside the variables analyzer.

Merges the former ``signal-lifecycle`` read-before-write and ``data-dependency``
initialization-order checks into one lifecycle finding: a local value (same-module
declaration, not a module parameter, no initializer) that is read before any known
write in the same module scope.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ...reporting.variables_report import IssueKind, VariableIssue
from ..shared._dependency_usage_facts import FactRef, StatementFact, collect_statement_facts


def collect_read_before_write_issues(self: Any) -> None:
    """Append ``IssueKind.READ_BEFORE_WRITE`` issues for reads before any write."""
    if getattr(self, "_limit_to_module_path", None) is not None:
        return

    facts = collect_statement_facts(
        self.bp,
        unavailable_libraries=getattr(self, "_unavailable_libraries", None) or set(),
        analyzed_target_is_library=bool(getattr(self, "_analyzed_target_is_library", False)),
    )
    facts_by_module: dict[tuple[str, ...], list[StatementFact]] = defaultdict(list)
    for fact in facts:
        facts_by_module[fact.module_path].append(fact)

    for module_path, module_facts in facts_by_module.items():
        _analyze_module(self, module_path, module_facts)


def _analyze_module(
    self: Any,
    module_path: tuple[str, ...],
    module_facts: list[StatementFact],
) -> None:
    initialized_roots: set[tuple[str, ...]] = set()
    sites_by_read: dict[tuple[str, ...], set[str]] = defaultdict(set)
    display_by_read: dict[tuple[str, ...], str] = {}

    for fact in module_facts:
        for read in fact.reads:
            if _is_read_before_write(read, module_path, initialized_roots):
                sites_by_read[read.root_key].add(fact.site)
                display_by_read[read.root_key] = read.display_name
        for write in fact.writes:
            initialized_roots.add(write.root_key)

    for root_key in sorted(sites_by_read):
        _report_issue(self, module_path, root_key, display_by_read[root_key], sites_by_read[root_key])


def _is_read_before_write(
    read: FactRef,
    module_path: tuple[str, ...],
    initialized_roots: set[tuple[str, ...]],
) -> bool:
    if read.decl_module_path != module_path:
        return False
    if read.is_moduleparameter or read.has_initializer:
        return False
    return read.root_key not in initialized_roots


def _report_issue(
    self: Any,
    module_path: tuple[str, ...],
    root_key: tuple[str, ...],
    display_name: str,
    sites: set[str],
) -> None:
    sorted_sites = sorted(sites)
    issue = VariableIssue(
        kind=IssueKind.READ_BEFORE_WRITE,
        module_path=list(module_path),
        variable=None,
        role=f"read before any write in {', '.join(sorted_sites)}",
        site=sorted_sites[0],
        context=display_name,
    )
    self._append_issue(issue)


__all__ = ["collect_read_before_write_issues"]
