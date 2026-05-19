"""Stable workspace quality metrics built from existing analyzer seams."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

from sattlint.analyzers.cyclomatic_complexity import analyze_cyclomatic_complexity
from sattlint.analyzers.modules import analyze_version_drift
from sattlint.devtools.structural_reports import REPO_ROOT, WorkspaceGraphInputs, collect_workspace_graph_inputs
from sattlint.path_sanitizer import sanitize_path_for_report
from sattlint.tracing import collect_ast_summary

DEFAULT_OUTPUT_FILENAME = "metrics_dashboard.json"


def _string_entries(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(entry) for entry in cast(list[object], value)]


def _emit_metrics_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _sanitize_repo_path(path: Path, *, workspace_root: Path) -> str:
    return sanitize_path_for_report(path, repo_root=workspace_root) or path.as_posix()


def _serialize_complexity_issue(issue: Any, *, entry_file: str) -> dict[str, Any]:
    data = dict(getattr(issue, "data", {}) or {})
    module_path = list(getattr(issue, "module_path", []) or [])
    return {
        "entry_file": entry_file,
        "kind": getattr(issue, "kind", "unknown"),
        "module_path": module_path,
        "scope": data.get("scope"),
        "sequence": data.get("sequence"),
        "step": data.get("step"),
        "complexity": int(data.get("complexity") or 0),
        "threshold": int(data.get("threshold") or 0),
        "message": getattr(issue, "message", ""),
    }


def _serialize_version_drift_issue(issue: Any, *, entry_file: str) -> dict[str, Any]:
    data = dict(getattr(issue, "data", {}) or {})
    return {
        "entry_file": entry_file,
        "module_name": data.get("module_name"),
        "total_found": int(data.get("total_found") or 0),
        "unique_variants": int(data.get("unique_variants") or 0),
        "location_preview": list(data.get("location_preview") or []),
        "upgrade_notes": list(data.get("upgrade_notes") or []),
        "message": getattr(issue, "message", ""),
    }


def _complexity_sort_key(item: dict[str, Any]) -> tuple[int, str, str]:
    return (
        -int(item.get("complexity") or 0),
        str(item.get("entry_file") or "").casefold(),
        ".".join(_string_entries(item.get("module_path"))).casefold(),
    )


def _drift_sort_key(item: dict[str, Any]) -> tuple[int, str, str]:
    return (
        -int(item.get("unique_variants") or 0),
        str(item.get("module_name") or "").casefold(),
        str(item.get("entry_file") or "").casefold(),
    )


def build_metrics_dashboard(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: WorkspaceGraphInputs | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    resolved_workspace_root = workspace_root.resolve()
    if graph_inputs is None:
        if progress_callback is not None:
            progress_callback("Metrics dashboard: loading workspace graph inputs")
        resolved_graph_inputs = collect_workspace_graph_inputs(resolved_workspace_root)
    else:
        resolved_graph_inputs = graph_inputs

    snapshots = sorted(
        resolved_graph_inputs.snapshots,
        key=lambda snapshot: _sanitize_repo_path(
            snapshot.entry_file, workspace_root=resolved_workspace_root
        ).casefold(),
    )

    aggregate_structure = {
        "datatype_definition_count": 0,
        "moduletype_definition_count": 0,
        "root_localvariable_count": 0,
        "submodule_count": 0,
        "single_module_count": 0,
        "frame_module_count": 0,
        "moduletype_instance_count": 0,
        "moduleparameter_count": 0,
        "module_localvariable_count": 0,
        "sequence_count": 0,
        "equation_count": 0,
    }
    entry_metrics: list[dict[str, Any]] = []
    complexity_findings: list[dict[str, Any]] = []
    drift_findings: list[dict[str, Any]] = []

    for index, snapshot in enumerate(snapshots, start=1):
        entry_file = _sanitize_repo_path(snapshot.entry_file, workspace_root=resolved_workspace_root)
        if progress_callback is not None:
            progress_callback(f"Metrics dashboard: analyzing {index}/{len(snapshots)} {entry_file}")

        structure_summary = collect_ast_summary(snapshot.base_picture)
        for key, value in structure_summary.items():
            aggregate_structure[key] = int(aggregate_structure.get(key, 0)) + int(value)

        complexity_report = analyze_cyclomatic_complexity(snapshot.base_picture)
        drift_report = analyze_version_drift(snapshot.base_picture)
        serialized_complexity = [
            _serialize_complexity_issue(issue, entry_file=entry_file)
            for issue in getattr(complexity_report, "issues", [])
        ]
        serialized_drift = [
            _serialize_version_drift_issue(issue, entry_file=entry_file)
            for issue in getattr(drift_report, "issues", [])
        ]
        complexity_findings.extend(serialized_complexity)
        drift_findings.extend(serialized_drift)
        entry_metrics.append(
            {
                "entry_file": entry_file,
                "definition_count": len(getattr(snapshot, "definitions", [])),
                "structure": structure_summary,
                "complexity_issue_count": len(serialized_complexity),
                "version_drift_issue_count": len(serialized_drift),
            }
        )

    sorted_complexity = sorted(complexity_findings, key=_complexity_sort_key)
    sorted_drift = sorted(drift_findings, key=_drift_sort_key)

    module_issue_count = sum(1 for finding in sorted_complexity if finding["kind"] == "module.cyclomatic_complexity")
    step_issue_count = sum(1 for finding in sorted_complexity if finding["kind"] == "step.cyclomatic_complexity")
    status = "ok"
    if resolved_graph_inputs.snapshot_failures and not snapshots:
        status = "error"
    elif resolved_graph_inputs.snapshot_failures:
        status = "partial"

    return {
        "generated_by": "sattlint.devtools.metrics_dashboard",
        "report_kind": "metrics-dashboard",
        "status": status,
        "workspace_root": _sanitize_repo_path(resolved_workspace_root, workspace_root=resolved_workspace_root),
        "summary": {
            "program_file_count": len(resolved_graph_inputs.discovery.program_files),
            "snapshot_count": len(snapshots),
            "snapshot_failure_count": len(resolved_graph_inputs.snapshot_failures),
            "complexity_issue_count": len(sorted_complexity),
            "version_drift_issue_count": len(sorted_drift),
        },
        "metrics": {
            "workspace": {
                "program_file_count": len(resolved_graph_inputs.discovery.program_files),
                "dependency_file_count": len(resolved_graph_inputs.discovery.dependency_files),
                "snapshot_count": len(snapshots),
                "snapshot_failure_count": len(resolved_graph_inputs.snapshot_failures),
            },
            "structure": aggregate_structure,
            "complexity": {
                "issue_count": len(sorted_complexity),
                "module_issue_count": module_issue_count,
                "step_issue_count": step_issue_count,
                "max_complexity": max((finding["complexity"] for finding in sorted_complexity), default=0),
                "top_findings": sorted_complexity[:10],
            },
            "version_drift": {
                "issue_count": len(sorted_drift),
                "affected_module_count": len({str(item.get("module_name") or "").casefold() for item in sorted_drift}),
                "max_unique_variants": max((finding["unique_variants"] for finding in sorted_drift), default=0),
                "modules": sorted_drift,
            },
        },
        "entries": entry_metrics,
        "snapshot_failures": list(resolved_graph_inputs.snapshot_failures),
    }


def _render_text_report(report: dict[str, Any]) -> str:
    complexity = report["metrics"]["complexity"]
    version_drift = report["metrics"]["version_drift"]
    structure = report["metrics"]["structure"]
    lines = [
        "SattLint metrics dashboard",
        f"Status: {report['status']}",
        f"Workspace root: {report['workspace_root']}",
        f"Snapshots: {report['summary']['snapshot_count']}",
        f"Complexity issues: {complexity['issue_count']}",
        f"Version drift issues: {version_drift['issue_count']}",
        "",
        "Structure totals:",
        f"- Submodules: {structure['submodule_count']}",
        f"- Sequences: {structure['sequence_count']}",
        f"- Equations: {structure['equation_count']}",
        "",
        "Top complexity findings:",
    ]
    if not complexity["top_findings"]:
        lines.append("- none")
    for finding in complexity["top_findings"]:
        module_label = ".".join(str(segment) for segment in finding["module_path"]) or "<root>"
        lines.append(
            f"- {finding['entry_file']} :: {module_label} -> {finding['complexity']} (threshold {finding['threshold']})"
        )

    lines.append("")
    lines.append("Version drift:")
    if not version_drift["modules"]:
        lines.append("- none")
    for item in version_drift["modules"][:10]:
        lines.append(
            f"- {item['module_name']}: {item['unique_variants']} variants across {item['total_found']} instances"
        )
    return "\n".join(lines)


def _write_metrics_report(output_dir: Path, report: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / DEFAULT_OUTPUT_FILENAME
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def _parse_metrics_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sattlint-metrics-dashboard",
        description="Build a stable JSON and text dashboard from existing SattLint analyzer metrics.",
    )
    parser.add_argument(
        "--workspace-root",
        default=str(REPO_ROOT),
        help="Workspace root to scan for entry files.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format for stdout.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory that receives metrics_dashboard.json.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Suppress progress messages on stderr.",
    )
    return parser.parse_args(list(argv) if argv is not None else sys.argv[1:])


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_metrics_args(argv)
    progress_callback = None if args.no_progress else _emit_metrics_progress
    report = build_metrics_dashboard(
        Path(args.workspace_root).resolve(),
        progress_callback=progress_callback,
    )
    if args.output_dir:
        _write_metrics_report(Path(args.output_dir).resolve(), report)

    if args.format == "text":
        print(_render_text_report(report))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] in {"ok", "partial"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
