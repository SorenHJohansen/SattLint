"""Read-before-write collection inside the variables analyzer.

Merges the former ``signal-lifecycle`` read-before-write and ``data-dependency``
initialization-order checks into one lifecycle finding: a local value (same-module
declaration, not a module parameter, no initializer) that is read before any known
write in the same module scope.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from ...reporting.variables_report import IssueKind, VariableIssue
from ...resolution import AccessKind
from ..shared._dependency_usage_facts import FactRef, StatementFact, collect_statement_facts
from ..shared.instance_paths import collect_instance_paths

if TYPE_CHECKING:
    from . import VariablesAnalyzer


def collect_read_before_write_issues(self: VariablesAnalyzer) -> None:
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

    local_writes = {write.key for fact in facts for write in fact.writes if write.decl_module_path == fact.module_path}
    supplied_writes = {
        event.canonical_path.key()
        for event in self.access_graph.events
        if event.kind is AccessKind.WRITE and event.canonical_path.key() not in local_writes
    }
    supplied_writes.update(
        write.key for fact in facts for write in fact.writes if write.decl_module_path != fact.module_path
    )
    instance_paths = collect_instance_paths(self.bp)
    for module_path, module_facts in facts_by_module.items():
        context_path = module_path
        if len(module_path) > 1 and module_path[1].startswith("TypeDef:"):
            name = module_path[1].removeprefix("TypeDef:").casefold()
            for instance_path in instance_paths.get(name, []):
                candidate = (*instance_path, *module_path[2:])
                if candidate in self.contexts_by_module_path:
                    context_path = candidate
                    break
        _analyze_module(self, module_path, module_facts, supplied_writes, context_path)


def _analyze_module(
    self: VariablesAnalyzer,
    module_path: tuple[str, ...],
    module_facts: list[StatementFact],
    supplied_writes: set[tuple[str, ...]],
    context_path: tuple[str, ...],
) -> None:
    initialized_roots: set[tuple[str, ...]] = set()
    local_writes = {write.key for fact in module_facts for write in fact.writes}
    sites_by_read: dict[tuple[str, ...], set[str]] = defaultdict(set)
    display_by_read: dict[tuple[str, ...], str] = {}
    context = self.contexts_by_module_path.get(context_path)

    for fact in module_facts:
        for read in fact.reads:
            if _is_read_before_write(read, module_path, initialized_roots):
                if any(read.key[: len(key)] == key for key in supplied_writes):
                    continue
                if context is not None and not any(read.key[: len(key)] == key for key in local_writes):
                    variable, _, _, _ = context.resolve_variable(read.base_display_name)
                    if variable is not None:
                        usage = self.get_usage(variable)
                        if any(kind == "write" for _, kind in usage.usage_locations):
                            continue
                        if any(
                            read.field_path.casefold() == field.casefold()
                            or read.field_path.casefold().startswith(f"{field.casefold()}.")
                            for field in usage.field_writes
                        ):
                            continue
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
    self: VariablesAnalyzer,
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
    self.append_issue(issue)


__all__ = ["collect_read_before_write_issues"]
