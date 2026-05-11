"""Structural pipeline report builders and shared graph inputs."""

from __future__ import annotations

import argparse
import ast as _ast
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sattlint.analyzers.registry import (
    get_actual_cli_analyzer_keys,
    get_actual_lsp_analyzer_keys,
    get_declared_cli_analyzer_keys,
    get_declared_lsp_analyzer_keys,
    get_default_analyzer_catalog,
)
from sattlint.app import VARIABLE_ANALYSES
from sattlint.core.semantic import discover_workspace_sources, load_workspace_snapshot
from sattlint.devtools import _structural_report_architecture as _architecture_module
from sattlint.devtools import _structural_report_budget as _budget_module
from sattlint.devtools import _structural_report_graphics as _graphics_module
from sattlint.devtools import _structural_report_graphs as _graphs_module
from sattlint.devtools._structural_budget_inventory import (
    count_structural_lines,
    iter_structural_markdown_files,
    iter_structural_python_files,
    read_structural_text,
    summarize_structural_budget_metrics,
)
from sattlint.devtools._structural_report_impact import collect_impact_analysis_report
from sattlint.path_sanitizer import sanitize_path_for_report
from sattlint.reporting.variables_report import IssueKind, VariablesReport
from sattlint.resolution.common import resolve_moduletype_def_strict
from sattlint.semantic_analysis import build_variable_semantic_artifacts

ast = _ast

REPO_ROOT = Path(__file__).resolve().parents[3]
STRUCTURAL_ENTRY_ROOTS = (Path("tests") / "fixtures" / "sample_sattline_files",)
PHASE2_ENFORCED_RULE_METADATA_FINDING_IDS = frozenset(
    {
        "rule-acceptance-test-gap",
        "rule-mutation-metadata-gap",
    }
)
PHASE2_ADVISORY_RULE_METADATA_FINDING_IDS = frozenset({"rule-corpus-link-gap"})
_GRAPHICS_LAYOUT_COMPARISON_FIELDS = (
    "invocation.coords",
    "invocation.arguments",
    "invocation.layer",
    "invocation.zoom_limits",
    "invocation.zoomable",
    "moduledef.clipping_origin",
    "moduledef.clipping_size",
    "moduledef.zoom_limits",
    "moduledef.grid",
    "moduledef.zoomable",
)
STRUCTURAL_BUDGET_THRESHOLDS = {
    "source_file_max_lines": 500,
    "test_file_max_lines": 500,
    "function_max_lines": 150,
    "class_method_max_count": 40,
    "duplicate_private_name_min_files": 4,
    "duplicate_private_name_min_length": 5,
}
STRUCTURAL_BUDGET_SETPOINTS = {
    "source_file_max_lines": 500,
    "test_file_max_lines": 500,
}
STRUCTURAL_BUDGET_RATCHET_PATH = Path("artifacts") / "analysis" / "structural_budget_ratchet.json"
FILE_DEBT_RATCHET_PATH = Path("artifacts") / "analysis" / "file_debt_ratchet.json"
FACADE_PRIVATE_BOUNDARY_FILES = frozenset(
    {
        "src/sattlint/app.py",
        "src/sattlint/app_base.py",
        "src/sattlint/editor_api.py",
    }
)


@dataclass(frozen=True, slots=True)
class WorkspaceGraphInputs:
    discovery: Any
    snapshots: list[Any]
    snapshot_failures: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class StructuralReportsBundle:
    structural_budget_report: dict[str, Any]
    architecture_report: dict[str, Any]
    analyzer_registry_report: dict[str, Any]
    graph_inputs: WorkspaceGraphInputs
    dependency_graph_report: dict[str, Any]
    call_graph_report: dict[str, Any]
    graphics_layout_report: dict[str, Any]
    impact_analysis_report: dict[str, Any]


_is_structural_budget_python_path = _budget_module._is_structural_budget_python_path
_collect_facade_private_entrypoints = _budget_module._collect_facade_private_entrypoints
_normalize_file_line_exceptions = _budget_module._normalize_file_line_exceptions
_load_structural_budget_ratchet = _budget_module._load_structural_budget_ratchet
_evaluate_structural_budget_ratchet = _budget_module._evaluate_structural_budget_ratchet
_append_structural_budget_findings = _architecture_module._append_structural_budget_findings
collect_phase2_rule_metadata_gate = _architecture_module.collect_phase2_rule_metadata_gate
collect_analyzer_registry_report = _architecture_module.collect_analyzer_registry_report
_structural_entry_files = _graphs_module._structural_entry_files
_structural_report_discovery = _graphs_module._structural_report_discovery
_accumulate_dependency_graph_snapshot = _graphs_module._accumulate_dependency_graph_snapshot
_iter_snapshot_accesses_by_definition = _graphs_module._iter_snapshot_accesses_by_definition
_accumulate_call_graph_snapshot = _graphs_module._accumulate_call_graph_snapshot
_build_dependency_graph_report = _graphs_module._build_dependency_graph_report
_build_call_graph_report = _graphs_module._build_call_graph_report
_should_emit_snapshot_progress = _graphs_module._should_emit_snapshot_progress
_stream_workspace_graph_reports = _graphs_module._stream_workspace_graph_reports
_serialize_invoke_coord = _graphics_module._serialize_invoke_coord
_serialize_moduledef = _graphics_module._serialize_moduledef
_stable_json_marker = _graphics_module._stable_json_marker
_graphics_field_value = _graphics_module._graphics_field_value
_graphics_layout_group_payload = _graphics_module._graphics_layout_group_payload
_graphics_layout_entry = _graphics_module._graphics_layout_entry
_walk_graphics_layout_children = _graphics_module._walk_graphics_layout_children


def collect_structural_budget_report(
    repo_root: Path = REPO_ROOT,
    *,
    ratchet_path: Path | None = None,
) -> dict[str, Any]:
    return _budget_module.collect_structural_budget_report(repo_root, ratchet_path=ratchet_path)


def collect_architecture_report(
    repo_root: Path = REPO_ROOT,
    *,
    ratchet_path: Path | None = None,
) -> dict[str, Any]:
    return _architecture_module.collect_architecture_report(repo_root, ratchet_path=ratchet_path)


def collect_workspace_graph_inputs(
    workspace_root: Path = REPO_ROOT,
) -> WorkspaceGraphInputs:
    return _graphs_module.collect_workspace_graph_inputs(workspace_root)


def collect_dependency_graph_report(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: WorkspaceGraphInputs | tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    return _graphs_module.collect_dependency_graph_report(workspace_root, graph_inputs=graph_inputs)


def collect_call_graph_report(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: WorkspaceGraphInputs | tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    return _graphs_module.collect_call_graph_report(workspace_root, graph_inputs=graph_inputs)


def collect_graphics_layout_report(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: WorkspaceGraphInputs | tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    return _graphics_module.collect_graphics_layout_report(workspace_root, graph_inputs=graph_inputs)


def collect_structural_reports(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: WorkspaceGraphInputs | tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> StructuralReportsBundle:
    structural_budget_report = collect_structural_budget_report(workspace_root)
    architecture_report = collect_architecture_report()
    analyzer_registry_report = collect_analyzer_registry_report()
    if graph_inputs is None:
        resolved_graph_inputs, dependency_graph_report, call_graph_report = _stream_workspace_graph_reports(
            workspace_root,
            progress_callback=progress_callback,
        )
    else:
        resolved_graph_inputs = _normalize_graph_inputs(graph_inputs, workspace_root=workspace_root)
        dependency_graph_report = collect_dependency_graph_report(
            workspace_root,
            graph_inputs=resolved_graph_inputs,
        )
        call_graph_report = collect_call_graph_report(
            workspace_root,
            graph_inputs=resolved_graph_inputs,
        )
    graphics_layout_report = collect_graphics_layout_report(
        workspace_root,
        graph_inputs=resolved_graph_inputs,
    )
    impact_analysis_report = collect_impact_analysis_report(
        workspace_root,
        graph_inputs=resolved_graph_inputs,
        dependency_graph_report=dependency_graph_report,
        call_graph_report=call_graph_report,
    )
    return StructuralReportsBundle(
        structural_budget_report=structural_budget_report,
        architecture_report=architecture_report,
        analyzer_registry_report=analyzer_registry_report,
        graph_inputs=resolved_graph_inputs,
        dependency_graph_report=dependency_graph_report,
        call_graph_report=call_graph_report,
        graphics_layout_report=graphics_layout_report,
        impact_analysis_report=impact_analysis_report,
    )


def _normalize_graph_inputs(
    graph_inputs: WorkspaceGraphInputs | tuple[Any, list[Any], list[dict[str, Any]]] | None,
    *,
    workspace_root: Path,
) -> WorkspaceGraphInputs:
    if graph_inputs is None:
        return collect_workspace_graph_inputs(workspace_root)
    if isinstance(graph_inputs, WorkspaceGraphInputs):
        return graph_inputs
    discovery, snapshots, failures = graph_inputs
    return WorkspaceGraphInputs(
        discovery=discovery,
        snapshots=list(snapshots),
        snapshot_failures=list(failures),
    )


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
    direct_count_values = dict.fromkeys(count_fields, 0)

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
    transitive_count_values = dict.fromkeys(count_fields, 0)
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


def _parse_ratchet_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check the structural budget ratchet against the current repository metrics."
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Repository root to scan for structural budget metrics",
    )
    parser.add_argument(
        "--ratchet-path",
        default=None,
        help="Optional override path for the structural budget ratchet JSON file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the ratchet status payload as JSON instead of the human-readable summary",
    )
    return parser.parse_args(list(argv) if argv is not None else sys.argv[1:])


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_ratchet_args(argv)
    repo_root = Path(args.repo_root).resolve()
    ratchet_path = None if args.ratchet_path is None else Path(args.ratchet_path).resolve()

    report = collect_structural_budget_report(repo_root, ratchet_path=ratchet_path)
    ratchet = report["ratchet"]

    if args.json:
        print(json.dumps(ratchet, indent=2))
    else:
        print(f"Structural ratchet: {ratchet['status']}")
        print(f"Ratchet file: {ratchet['path']}")
        regressions = ratchet.get("regressions", [])
        if regressions:
            print("Regressions:")
            for regression in regressions:
                if "metric" in regression:
                    print(f"  - {regression['metric']}: {regression['actual']} > {regression['expected_max']}")
                else:
                    print(
                        f"  - {regression['path']}: {regression['actual']} > {regression['expected_max']}"
                        f" ({regression['reason']})"
                    )
        else:
            print("Regressions: []")

    return 0 if ratchet["status"] == "pass" else 1


__all__ = [
    "VARIABLE_ANALYSES",
    "IssueKind",
    "StructuralReportsBundle",
    "VariablesReport",
    "WorkspaceGraphInputs",
    "ast",
    "build_variable_semantic_artifacts",
    "collect_analyzer_registry_report",
    "collect_architecture_report",
    "collect_call_graph_report",
    "collect_dependency_graph_report",
    "collect_graphics_layout_report",
    "collect_impact_analysis_report",
    "collect_phase2_rule_metadata_gate",
    "collect_structural_reports",
    "collect_workspace_graph_inputs",
    "count_structural_lines",
    "discover_workspace_sources",
    "get_actual_cli_analyzer_keys",
    "get_actual_lsp_analyzer_keys",
    "get_declared_cli_analyzer_keys",
    "get_declared_lsp_analyzer_keys",
    "get_default_analyzer_catalog",
    "iter_structural_markdown_files",
    "iter_structural_python_files",
    "load_workspace_snapshot",
    "main",
    "read_structural_text",
    "resolve_moduletype_def_strict",
    "sanitize_path_for_report",
    "summarize_structural_budget_metrics",
]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
