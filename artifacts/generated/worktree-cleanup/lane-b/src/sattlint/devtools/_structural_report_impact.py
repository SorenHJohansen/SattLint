"""Structural impact analysis helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def collect_impact_analysis_report(
    workspace_root: Path,
    *,
    graph_inputs: Any = None,
    dependency_graph_report: dict[str, Any] | None = None,
    call_graph_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module

    resolved_graph_inputs = structural_reports_module._normalize_graph_inputs(
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
    for edge in resolved_dependency_graph.get("edges", []):
        dependency_incoming.setdefault(edge["target"], []).append(edge)

    module_incoming: dict[str, list[dict[str, Any]]] = {}
    for edge in resolved_call_graph.get("edges", []):
        if edge["source"].casefold() == edge["target"].casefold():
            continue
        module_incoming.setdefault(edge["target"], []).append(edge)

    library_impacts = []
    for node in resolved_dependency_graph.get("nodes", []):
        impact = structural_reports_module._collect_reverse_impact(node["id"], dependency_incoming)
        library_impacts.append(
            {
                "id": node["id"],
                "kind": node.get("kind", "library"),
                **impact,
            }
        )

    module_impacts = []
    for node in resolved_call_graph.get("nodes", []):
        impact = structural_reports_module._collect_reverse_impact(
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
        "snapshot_failures": structural_reports_module._dedupe_snapshot_failures(
            resolved_dependency_graph.get("snapshot_failures", []),
            resolved_call_graph.get("snapshot_failures", []),
        ),
    }


__all__ = ["collect_impact_analysis_report"]
