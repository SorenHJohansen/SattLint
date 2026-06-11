"""Structural impact analysis helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast


def _mapping_entries(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    entries: list[dict[str, Any]] = []
    for entry in cast(list[object], value):
        if isinstance(entry, dict):
            entries.append(cast(dict[str, Any], entry))
    return entries


def _dedupe_snapshot_failures(*failure_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    failures: list[dict[str, Any]] = []
    for items in failure_lists:
        for item in items:
            marker = repr(sorted(item.items()))
            if marker in seen:
                continue
            seen.add(marker)
            failures.append(item)
    return failures


def _collect_reverse_impact(
    node_id: str,
    incoming_edges: dict[str, list[dict[str, Any]]],
    *,
    list_fields: tuple[str, ...] = (),
    count_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    direct_dependents: set[str] = set()
    direct_entry_files: set[str] = set()
    direct_list_values: dict[str, set[str]] = {field: set() for field in list_fields}
    direct_count_values: dict[str, int] = dict.fromkeys(count_fields, 0)

    for edge in incoming_edges.get(node_id, []):
        direct_dependents.add(edge["source"])
        direct_entry_files.update(edge.get("entries", []))
        for field in list_fields:
            direct_list_values[field].update(edge.get(field, []))
        for field in count_fields:
            direct_count_values[field] += int(edge.get(field, 0))

    transitive_dependents: set[str] = set()
    transitive_entry_files: set[str] = set()
    transitive_list_values: dict[str, set[str]] = {field: set() for field in list_fields}
    transitive_count_values: dict[str, int] = dict.fromkeys(count_fields, 0)
    pending = [node_id]
    visited_targets: set[str] = set()

    while pending:
        target = pending.pop()
        target_key = target.casefold()
        if target_key in visited_targets:
            continue
        visited_targets.add(target_key)
        for edge in incoming_edges.get(target, []):
            source = edge["source"]
            transitive_dependents.add(source)
            transitive_entry_files.update(edge.get("entries", []))
            for field in list_fields:
                transitive_list_values[field].update(edge.get(field, []))
            for field in count_fields:
                transitive_count_values[field] += int(edge.get(field, 0))
            pending.append(source)

    impact = {
        "direct_dependents": sorted(direct_dependents, key=str.casefold),
        "transitive_dependents": sorted(transitive_dependents, key=str.casefold),
        "direct_entry_files": sorted(direct_entry_files, key=str.casefold),
        "transitive_entry_files": sorted(transitive_entry_files, key=str.casefold),
        "direct_dependent_count": len(direct_dependents),
        "transitive_dependent_count": len(transitive_dependents),
    }
    for field in list_fields:
        direct_values = sorted(direct_list_values[field], key=str.casefold)
        transitive_values = sorted(transitive_list_values[field], key=str.casefold)
        impact[f"direct_{field}"] = direct_values
        impact[f"transitive_{field}"] = transitive_values
        impact[f"direct_{field[:-1]}_count"] = len(direct_values)
        impact[f"transitive_{field[:-1]}_count"] = len(transitive_values)
    for field in count_fields:
        impact[f"direct_{field}"] = direct_count_values[field]
        impact[f"transitive_{field}"] = transitive_count_values[field]
    return impact


def collect_impact_analysis_report(
    workspace_root: Path,
    *,
    graph_inputs: Any = None,
    dependency_graph_report: dict[str, Any] | None = None,
    call_graph_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module  # noqa: PLC0415

    resolved_graph_inputs = structural_reports_module.normalize_graph_inputs(
        graph_inputs, workspace_root=workspace_root
    )
    resolved_dependency_graph = (
        dependency_graph_report
        if dependency_graph_report is not None
        else structural_reports_module.collect_dependency_graph_report(
            workspace_root, graph_inputs=resolved_graph_inputs
        )
    )
    resolved_call_graph = (
        call_graph_report
        if call_graph_report is not None
        else structural_reports_module.collect_call_graph_report(workspace_root, graph_inputs=resolved_graph_inputs)
    )

    dependency_incoming: dict[str, list[dict[str, Any]]] = {}
    for edge in _mapping_entries(resolved_dependency_graph.get("edges")):
        dependency_incoming.setdefault(edge["target"], []).append(edge)

    module_incoming: dict[str, list[dict[str, Any]]] = {}
    for edge in _mapping_entries(resolved_call_graph.get("edges")):
        if edge["source"].casefold() == edge["target"].casefold():
            continue
        module_incoming.setdefault(edge["target"], []).append(edge)

    library_impacts: list[dict[str, Any]] = []
    for node in _mapping_entries(resolved_dependency_graph.get("nodes")):
        impact = _collect_reverse_impact(node["id"], dependency_incoming)
        library_impacts.append(
            {
                "id": node["id"],
                "kind": node.get("kind", "library"),
                **impact,
            }
        )

    module_impacts: list[dict[str, Any]] = []
    for node in _mapping_entries(resolved_call_graph.get("nodes")):
        impact = _collect_reverse_impact(
            node["id"],
            module_incoming,
            list_fields=("symbols",),
            count_fields=("reads", "writes", "access_count"),
        )
        module_impacts.append(
            {
                "id": node["id"],
                "kind": node.get("kind", "module"),
                **impact,
            }
        )

    return {
        "generated_by": "sattlint.devtools.pipeline",
        "report_kind": "impact-analysis",
        "workspace_root": structural_reports_module.sanitize_path_for_report(workspace_root, repo_root=workspace_root),
        "library_impacts": library_impacts,
        "module_impacts": module_impacts,
        "snapshot_failures": _dedupe_snapshot_failures(
            _mapping_entries(resolved_dependency_graph.get("snapshot_failures")),
            _mapping_entries(resolved_call_graph.get("snapshot_failures")),
        ),
    }


__all__ = ["collect_impact_analysis_report"]
