"""Direct impact-analysis command built on structural report collectors."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from sattlint import cli_output
from sattlint.devtools._io import emit_progress
from sattlint.devtools._semble_adapter import search_local_repo
from sattlint.devtools.structural.structural_reports import (
    REPO_ROOT,
    WorkspaceGraphInputs,
    collect_call_graph_report,
    collect_dependency_graph_report,
    collect_impact_analysis_report,
    collect_workspace_graph_inputs,
)
from sattlint.path_sanitizer import sanitize_path_for_report


def _mapping_entries(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    entries: list[dict[str, Any]] = []
    for entry in cast(list[object], value):
        if isinstance(entry, dict):
            entries.append(cast(dict[str, Any], entry))
    return entries


DEFAULT_OUTPUT_FILENAME = "impact_analysis.json"
SEMANTIC_QUERY_TOP_K = 5


_emit_impact_progress = emit_progress


def _normalize_identifier_values(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = raw_value.strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return normalized


def _normalize_entry_file_value(raw_value: str, *, workspace_root: Path) -> str:
    raw_path = Path(raw_value)
    resolved_path = raw_path.resolve() if raw_path.is_absolute() else (workspace_root / raw_path).resolve()
    sanitized = sanitize_path_for_report(resolved_path, repo_root=workspace_root)
    return sanitized or resolved_path.as_posix()


def _normalize_entry_file_values(values: list[str], *, workspace_root: Path) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = raw_value.strip()
        if not value:
            continue
        normalized_value = _normalize_entry_file_value(value, workspace_root=workspace_root)
        key = normalized_value.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(normalized_value)
    return normalized


def _module_ids_for_snapshot(snapshot: Any) -> list[str]:
    root_module = str(getattr(snapshot.base_picture, "name", snapshot.entry_file.stem))
    module_ids = {root_module}
    for definition in getattr(snapshot, "definitions", ()):
        if getattr(definition, "field_path", None) is not None:
            continue
        declaration_module_path = getattr(definition, "declaration_module_path", None) or (root_module,)
        module_ids.add(".".join(str(segment) for segment in declaration_module_path))
    return sorted(module_ids, key=str.casefold)


def _build_entry_file_index(
    graph_inputs: WorkspaceGraphInputs,
    *,
    workspace_root: Path,
) -> dict[str, dict[str, Any]]:
    entry_file_index: dict[str, dict[str, Any]] = {}
    for snapshot in graph_inputs.snapshots:
        sanitized_entry = (
            sanitize_path_for_report(snapshot.entry_file, repo_root=workspace_root) or snapshot.entry_file.as_posix()
        )
        library_ids: list[str] = []
        origin_lib = getattr(snapshot.base_picture, "origin_lib", None)
        if isinstance(origin_lib, str) and origin_lib.strip():
            library_ids.append(origin_lib)
        entry_file_index[sanitized_entry.casefold()] = {
            "entry_file": sanitized_entry,
            "libraries": sorted(set(library_ids), key=str.casefold),
            "modules": _module_ids_for_snapshot(snapshot),
        }
    return entry_file_index


def _build_id_index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["id"]).casefold(): item for item in items if isinstance(item.get("id"), str)}


def _sorted_impacts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: str(item.get("id", "")).casefold())


def _resolve_semantic_query(
    query: str,
    *,
    workspace_root: Path,
    entry_file_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    search_report = search_local_repo(query, repo_root=workspace_root, top_k=SEMANTIC_QUERY_TOP_K)
    if not search_report.available:
        return {
            "status": "unavailable",
            "query": query,
            "backend": search_report.backend,
            "candidate_files": [],
            "selected_entry_files": [],
            "explanation": search_report.explanation,
            "error": search_report.error,
        }

    candidate_files: list[dict[str, Any]] = []
    selected_entry_files: list[str] = []
    seen_entry_files: set[str] = set()
    for match in search_report.results:
        matched_entry = entry_file_index.get(match.file_path.casefold())
        selected_entry_file = None if matched_entry is None else str(matched_entry["entry_file"])
        if selected_entry_file is not None:
            key = selected_entry_file.casefold()
            if key not in seen_entry_files:
                seen_entry_files.add(key)
                selected_entry_files.append(selected_entry_file)
        candidate_files.append(
            {
                "file_path": match.file_path,
                "start_line": match.start_line,
                "end_line": match.end_line,
                "score": match.score,
                "selected_entry_file": selected_entry_file,
            }
        )

    status = "ok"
    if not candidate_files:
        status = "no-results"
    elif not selected_entry_files:
        status = "no-entry-file-matches"
    return {
        "status": status,
        "query": query,
        "backend": search_report.backend,
        "candidate_files": candidate_files,
        "selected_entry_files": selected_entry_files,
        "explanation": search_report.explanation,
    }


def build_impact_analysis_selection(  # noqa: PLR0915
    workspace_root: Path = REPO_ROOT,
    *,
    libraries: list[str] | None = None,
    modules: list[str] | None = None,
    entry_files: list[str] | None = None,
    query: str | None = None,
    include_full_report: bool = False,
    graph_inputs: WorkspaceGraphInputs | None = None,
    dependency_graph_report: dict[str, Any] | None = None,
    call_graph_report: dict[str, Any] | None = None,
    impact_analysis_report: dict[str, Any] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    resolved_workspace_root = workspace_root.resolve()
    requested_libraries = _normalize_identifier_values(list(libraries or []))
    requested_modules = _normalize_identifier_values(list(modules or []))
    requested_entry_files = _normalize_entry_file_values(
        list(entry_files or []), workspace_root=resolved_workspace_root
    )
    normalized_query = "" if query is None else query.strip()
    explicit_target_requested = bool(requested_libraries or requested_modules or requested_entry_files)

    request_payload = {
        "libraries": requested_libraries,
        "modules": requested_modules,
        "entry_files": requested_entry_files,
    }
    if not explicit_target_requested and not normalized_query:
        return {
            "generated_by": "sattlint.devtools.structural.impact_analyzer",
            "report_kind": "impact-analysis-selection",
            "status": "error",
            "workspace_root": sanitize_path_for_report(resolved_workspace_root, repo_root=resolved_workspace_root),
            "requested_targets": request_payload,
            "resolved_targets": {
                "libraries": [],
                "modules": [],
                "entry_files": [],
                "entry_file_expansions": [],
            },
            "selected_impacts": {"libraries": [], "modules": []},
            "snapshot_failures": [],
            "errors": [
                {
                    "selector_kind": "targets",
                    "value": None,
                    "message": "At least one --library, --module, or --entry-file selector is required.",
                }
            ],
        }

    if graph_inputs is None:
        if progress_callback is not None:
            progress_callback("Impact analysis: loading workspace graph inputs")
        resolved_graph_inputs = collect_workspace_graph_inputs(resolved_workspace_root)
    else:
        resolved_graph_inputs = graph_inputs
    resolved_dependency_graph = (
        dependency_graph_report
        if dependency_graph_report is not None
        else (
            progress_callback("Impact analysis: building dependency graph") if progress_callback is not None else None,
            collect_dependency_graph_report(resolved_workspace_root, graph_inputs=resolved_graph_inputs),
        )[1]
    )
    resolved_call_graph = (
        call_graph_report
        if call_graph_report is not None
        else (
            progress_callback("Impact analysis: building call graph") if progress_callback is not None else None,
            collect_call_graph_report(resolved_workspace_root, graph_inputs=resolved_graph_inputs),
        )[1]
    )
    resolved_impact_report = (
        impact_analysis_report
        if impact_analysis_report is not None
        else collect_impact_analysis_report(
            resolved_workspace_root,
            graph_inputs=resolved_graph_inputs,
            dependency_graph_report=resolved_dependency_graph,
            call_graph_report=resolved_call_graph,
        )
    )

    if progress_callback is not None:
        progress_callback("Impact analysis: selecting impacted targets")

    library_index = _build_id_index(list(resolved_impact_report.get("library_impacts", [])))
    module_index = _build_id_index(list(resolved_impact_report.get("module_impacts", [])))
    entry_file_index = _build_entry_file_index(resolved_graph_inputs, workspace_root=resolved_workspace_root)
    semantic_query_report: dict[str, Any] | None = None
    if normalized_query:
        if progress_callback is not None:
            progress_callback("Impact analysis: resolving semantic query")
        semantic_query_report = _resolve_semantic_query(
            normalized_query,
            workspace_root=resolved_workspace_root,
            entry_file_index=entry_file_index,
        )
        for selected_entry_file in list(semantic_query_report.get("selected_entry_files", [])):
            entry_text = str(selected_entry_file).strip()
            if entry_text and entry_text not in requested_entry_files:
                requested_entry_files.append(entry_text)

    selected_library_ids: set[str] = set()
    selected_module_ids: set[str] = set()
    resolved_entry_files: list[str] = []
    entry_file_expansions: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    if normalized_query and semantic_query_report is not None and not explicit_target_requested:
        semantic_status = str(semantic_query_report.get("status", ""))
        if semantic_status == "unavailable":
            errors.append(
                {
                    "selector_kind": "query",
                    "value": normalized_query,
                    "message": "Semantic query could not run because Semble is unavailable.",
                }
            )
        elif semantic_status == "no-results":
            errors.append(
                {
                    "selector_kind": "query",
                    "value": normalized_query,
                    "message": f"Semantic query returned no candidate files: {normalized_query}",
                }
            )
        elif semantic_status == "no-entry-file-matches":
            errors.append(
                {
                    "selector_kind": "query",
                    "value": normalized_query,
                    "message": f"Semantic query matched files, but none mapped to workspace entry files: {normalized_query}",
                }
            )

    for requested_library in requested_libraries:
        impact = library_index.get(requested_library.casefold())
        if impact is None:
            errors.append(
                {
                    "selector_kind": "library",
                    "value": requested_library,
                    "message": f"Unknown library selector: {requested_library}",
                }
            )
            continue
        selected_library_ids.add(str(impact["id"]))

    for requested_module in requested_modules:
        impact = module_index.get(requested_module.casefold())
        if impact is None:
            errors.append(
                {
                    "selector_kind": "module",
                    "value": requested_module,
                    "message": f"Unknown module selector: {requested_module}",
                }
            )
            continue
        selected_module_ids.add(str(impact["id"]))

    for requested_entry_file in requested_entry_files:
        expansion = entry_file_index.get(requested_entry_file.casefold())
        if expansion is None:
            errors.append(
                {
                    "selector_kind": "entry_file",
                    "value": requested_entry_file,
                    "message": f"Unknown entry-file selector: {requested_entry_file}",
                }
            )
            continue
        resolved_entry_files.append(str(expansion["entry_file"]))
        resolved_libraries: list[str] = []
        for library_id in expansion["libraries"]:
            impact = library_index.get(str(library_id).casefold())
            if impact is None:
                continue
            canonical_id = str(impact["id"])
            selected_library_ids.add(canonical_id)
            resolved_libraries.append(canonical_id)
        resolved_modules: list[str] = []
        for module_id in expansion["modules"]:
            impact = module_index.get(str(module_id).casefold())
            if impact is None:
                continue
            canonical_id = str(impact["id"])
            selected_module_ids.add(canonical_id)
            resolved_modules.append(canonical_id)
        entry_file_expansions.append(
            {
                "entry_file": expansion["entry_file"],
                "libraries": sorted(set(resolved_libraries), key=str.casefold),
                "modules": sorted(set(resolved_modules), key=str.casefold),
            }
        )

    selected_library_impacts = _sorted_impacts(
        [
            impact
            for impact in resolved_impact_report.get("library_impacts", [])
            if impact.get("id") in selected_library_ids
        ]
    )
    selected_module_impacts = _sorted_impacts(
        [
            impact
            for impact in resolved_impact_report.get("module_impacts", [])
            if impact.get("id") in selected_module_ids
        ]
    )

    report: dict[str, Any] = {
        "generated_by": "sattlint.devtools.structural.impact_analyzer",
        "report_kind": "impact-analysis-selection",
        "status": "error" if errors else "ok",
        "workspace_root": sanitize_path_for_report(resolved_workspace_root, repo_root=resolved_workspace_root),
        "requested_targets": request_payload,
        "resolved_targets": {
            "libraries": sorted(selected_library_ids, key=str.casefold),
            "modules": sorted(selected_module_ids, key=str.casefold),
            "entry_files": sorted(set(resolved_entry_files), key=str.casefold),
            "entry_file_expansions": sorted(entry_file_expansions, key=lambda item: item["entry_file"].casefold()),
        },
        "selected_impacts": {
            "libraries": selected_library_impacts,
            "modules": selected_module_impacts,
        },
        "snapshot_failures": _mapping_entries(resolved_impact_report.get("snapshot_failures")),
        "errors": errors,
    }
    if semantic_query_report is not None:
        report["semantic_query"] = semantic_query_report
    if include_full_report:
        report["full_report"] = {
            "dependency_graph": resolved_dependency_graph,
            "call_graph": resolved_call_graph,
            "impact_analysis": resolved_impact_report,
        }
    return report


def _write_impact_report(output_dir: Path, report: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / DEFAULT_OUTPUT_FILENAME
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def _parse_impact_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sattlint-impact-analyzer",
        description="Select impacted libraries, modules, and entry files from the structural impact report.",
    )
    parser.add_argument(
        "--workspace-root",
        default=str(REPO_ROOT),
        help="Workspace root to scan for SattLine entry files.",
    )
    parser.add_argument(
        "--library",
        action="append",
        default=[],
        help="Library id to treat as changed. May be provided multiple times.",
    )
    parser.add_argument(
        "--module",
        action="append",
        default=[],
        help="Module id to treat as changed. May be provided multiple times.",
    )
    parser.add_argument(
        "--entry-file",
        action="append",
        default=[],
        help="Entry file path to expand into changed libraries and modules. May be provided multiple times.",
    )
    parser.add_argument(
        "--query",
        default=None,
        help="Optional semantic query that resolves matching entry files before expanding impacted libraries and modules.",
    )
    parser.add_argument(
        "--format",
        choices=("json",),
        default="json",
        help="Output format for stdout.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory that receives impact_analysis.json.",
    )
    parser.add_argument(
        "--include-full-report",
        action="store_true",
        help="Embed the underlying dependency, call-graph, and full impact reports in the JSON output.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Suppress stage progress messages on stderr.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_impact_args(argv)
    workspace_root = Path(args.workspace_root).resolve()
    progress_callback = None if args.no_progress else _emit_impact_progress
    report = build_impact_analysis_selection(
        workspace_root,
        libraries=list(args.library),
        modules=list(args.module),
        entry_files=list(args.entry_file),
        query=None if args.query is None else str(args.query),
        include_full_report=bool(args.include_full_report),
        progress_callback=progress_callback,
    )
    output_error: OSError | None = None

    if args.output_dir:
        try:
            _write_impact_report(Path(args.output_dir).resolve(), report)
        except OSError as exc:
            output_error = exc

    print(cli_output.render_json_output(report))
    if output_error is not None:
        print(f"impact analysis output error: {output_error}", file=sys.stderr, flush=True)
        return 1
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
