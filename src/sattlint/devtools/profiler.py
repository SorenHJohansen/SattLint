"""Workspace profiling helpers for direct devtools execution."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol

from sattlint.analyzers.framework import AnalysisContext
from sattlint.analyzers.registry import get_default_analyzer_catalog
from sattlint.core.semantic import discover_workspace_sources, load_workspace_snapshot
from sattlint.path_sanitizer import sanitize_path_for_report
from sattlint.semantic_analysis import build_variable_semantic_artifacts

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_FILENAME = "profiler_report.json"


class _IssueReport(Protocol):
    issues: list[Any]


def _duration_ms(start: float, end: float) -> float:
    return round((end - start) * 1000, 3)


def _sanitize_repo_path(path: Path, *, workspace_root: Path) -> str:
    return sanitize_path_for_report(path, repo_root=workspace_root) or path.as_posix()


def _stderr_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _entry_sort_key(entry: dict[str, Any]) -> tuple[float, str]:
    return (-float(entry.get("total_duration_ms") or 0.0), str(entry.get("entry_file") or "").casefold())


def _analyzer_sort_key(entry: dict[str, Any]) -> tuple[float, str]:
    return (-float(entry.get("total_duration_ms") or 0.0), str(entry.get("key") or "").casefold())


def _phase_sort_key(entry: dict[str, Any]) -> tuple[float, str]:
    return (-float(entry.get("duration_ms") or 0.0), str(entry.get("phase") or "").casefold())


def _selected_analyzer_specs(analyzer_keys: Sequence[str] | None) -> list[Any]:
    catalog = get_default_analyzer_catalog()
    enabled = [analyzer.spec for analyzer in catalog.analyzers if analyzer.spec.enabled]
    if not analyzer_keys:
        return enabled

    requested = {key.casefold() for key in analyzer_keys if key.strip()}
    return [spec for spec in enabled if spec.key.casefold() in requested]


def _profile_snapshot_analyzers(
    snapshot: Any,
    *,
    timer: Callable[[], float],
    analyzer_keys: Sequence[str] | None,
) -> tuple[list[dict[str, Any]], float]:
    context = AnalysisContext(
        base_picture=snapshot.base_picture,
        graph=getattr(snapshot, "project_graph", None),
    )
    records: list[dict[str, Any]] = []
    total_duration_ms = 0.0
    for spec in _selected_analyzer_specs(analyzer_keys):
        start = timer()
        report = spec.run(context)
        end = timer()
        duration_ms = _duration_ms(start, end)
        total_duration_ms = round(total_duration_ms + duration_ms, 3)
        issues = getattr(report, "issues", [])
        issue_count = len(issues) if isinstance(issues, list) else 0
        records.append(
            {
                "key": spec.key,
                "name": spec.name,
                "issue_count": issue_count,
                "duration_ms": duration_ms,
            }
        )
    return records, total_duration_ms


def _aggregate_analyzer_bottlenecks(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    for entry in entries:
        for analyzer in entry.get("analyzers", []):
            key = str(analyzer.get("key") or "")
            if not key:
                continue
            record = totals.setdefault(
                key.casefold(),
                {
                    "key": key,
                    "name": analyzer.get("name") or key,
                    "entry_count": 0,
                    "issue_count": 0,
                    "total_duration_ms": 0.0,
                    "max_duration_ms": 0.0,
                },
            )
            duration_ms = float(analyzer.get("duration_ms") or 0.0)
            record["entry_count"] = int(record["entry_count"]) + 1
            record["issue_count"] = int(record["issue_count"]) + int(analyzer.get("issue_count") or 0)
            record["total_duration_ms"] = round(float(record["total_duration_ms"]) + duration_ms, 3)
            record["max_duration_ms"] = round(max(float(record["max_duration_ms"]), duration_ms), 3)

    aggregated = list(totals.values())
    for record in aggregated:
        entry_count = max(int(record["entry_count"]), 1)
        record["avg_duration_ms"] = round(float(record["total_duration_ms"]) / entry_count, 3)
    return sorted(aggregated, key=_analyzer_sort_key)


def profile_workspace(
    workspace_root: Path = REPO_ROOT,
    *,
    max_files: int | None = None,
    analyzer_keys: Sequence[str] | None = None,
    timer: Callable[[], float] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    resolved_workspace_root = workspace_root.resolve()
    clock = timer or time.perf_counter

    if progress_callback is not None:
        progress_callback("Profiler: discovering workspace sources")
    discover_start = clock()
    discovery = discover_workspace_sources(resolved_workspace_root)
    discover_end = clock()
    discovery_duration_ms = _duration_ms(discover_start, discover_end)

    selected_program_files = list(discovery.program_files)
    if max_files is not None:
        selected_program_files = selected_program_files[: max(max_files, 0)]

    entry_records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    load_total_ms = 0.0
    analyzer_total_ms = 0.0

    for index, entry_file in enumerate(selected_program_files, start=1):
        sanitized_entry = _sanitize_repo_path(entry_file, workspace_root=resolved_workspace_root)
        if progress_callback is not None:
            progress_callback(f"Profiler: loading {index}/{len(selected_program_files)} {sanitized_entry}")

        load_start = clock()
        try:
            snapshot = load_workspace_snapshot(
                entry_file,
                workspace_root=resolved_workspace_root,
                discovery=discovery,
                collect_variable_diagnostics=False,
                _analysis_provider=build_variable_semantic_artifacts,
            )
        except Exception as exc:
            load_end = clock()
            duration_ms = _duration_ms(load_start, load_end)
            load_total_ms = round(load_total_ms + duration_ms, 3)
            failures.append(
                {
                    "entry_file": sanitized_entry,
                    "duration_ms": duration_ms,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            )
            if progress_callback is not None:
                progress_callback(
                    f"Profiler: failed {index}/{len(selected_program_files)} {sanitized_entry} ({type(exc).__name__})"
                )
            continue

        load_end = clock()
        load_duration_ms = _duration_ms(load_start, load_end)
        load_total_ms = round(load_total_ms + load_duration_ms, 3)

        if progress_callback is not None:
            progress_callback(f"Profiler: analyzing {index}/{len(selected_program_files)} {sanitized_entry}")
        analyzer_records, analyzer_duration_ms = _profile_snapshot_analyzers(
            snapshot,
            timer=clock,
            analyzer_keys=analyzer_keys,
        )
        analyzer_total_ms = round(analyzer_total_ms + analyzer_duration_ms, 3)
        entry_records.append(
            {
                "entry_file": sanitized_entry,
                "definition_count": len(getattr(snapshot, "definitions", [])),
                "analyzers": analyzer_records,
                "load_duration_ms": load_duration_ms,
                "analysis_duration_ms": analyzer_duration_ms,
                "total_duration_ms": round(load_duration_ms + analyzer_duration_ms, 3),
            }
        )

    phase_timings = [
        {"phase": "discovery", "duration_ms": discovery_duration_ms},
        {"phase": "snapshot-loading", "duration_ms": load_total_ms},
        {"phase": "analyzer-run", "duration_ms": analyzer_total_ms},
    ]
    total_duration_ms = round(sum(float(phase["duration_ms"]) for phase in phase_timings), 3)

    status = "ok"
    if failures and not entry_records:
        status = "error"
    elif failures:
        status = "partial"

    slowest_entries = sorted(entry_records, key=_entry_sort_key)[:10]
    slowest_analyzers = _aggregate_analyzer_bottlenecks(entry_records)[:10]
    slowest_phases = sorted(phase_timings, key=_phase_sort_key)

    return {
        "generated_by": "sattlint.devtools.profiler",
        "report_kind": "workspace-profile",
        "status": status,
        "workspace_root": _sanitize_repo_path(resolved_workspace_root, workspace_root=resolved_workspace_root),
        "summary": {
            "program_file_count": len(discovery.program_files),
            "profiled_entry_count": len(selected_program_files),
            "successful_entry_count": len(entry_records),
            "snapshot_failure_count": len(failures),
            "analyzer_count": len(_selected_analyzer_specs(analyzer_keys)),
            "total_duration_ms": total_duration_ms,
        },
        "source_files": {
            "program_files": [
                _sanitize_repo_path(path, workspace_root=resolved_workspace_root) for path in selected_program_files
            ],
            "dependency_file_count": len(discovery.dependency_files),
        },
        "phase_timings": phase_timings,
        "entries": sorted(entry_records, key=lambda item: str(item["entry_file"]).casefold()),
        "bottlenecks": {
            "slowest_entries": slowest_entries,
            "slowest_analyzers": slowest_analyzers,
            "slowest_phases": slowest_phases,
        },
        "snapshot_failures": failures,
    }


def _render_text_report(report: dict[str, Any]) -> str:
    lines = [
        "SattLint workspace profile",
        f"Status: {report['status']}",
        f"Workspace root: {report['workspace_root']}",
        f"Program files: {report['summary']['program_file_count']}",
        f"Profiled entries: {report['summary']['profiled_entry_count']}",
        f"Total duration: {report['summary']['total_duration_ms']} ms",
        "",
        "Phase timings:",
    ]
    for phase in report.get("phase_timings", []):
        lines.append(f"- {phase['phase']}: {phase['duration_ms']} ms")

    lines.append("")
    lines.append("Slowest entries:")
    slowest_entries = report.get("bottlenecks", {}).get("slowest_entries", [])
    if not slowest_entries:
        lines.append("- none")
    for entry in slowest_entries:
        lines.append(f"- {entry['entry_file']}: {entry['total_duration_ms']} ms")

    lines.append("")
    lines.append("Slowest analyzers:")
    slowest_analyzers = report.get("bottlenecks", {}).get("slowest_analyzers", [])
    if not slowest_analyzers:
        lines.append("- none")
    for analyzer in slowest_analyzers:
        lines.append(
            f"- {analyzer['key']}: total {analyzer['total_duration_ms']} ms, avg {analyzer['avg_duration_ms']} ms"
        )
    return "\n".join(lines)


def _write_report(output_dir: Path, report: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / DEFAULT_OUTPUT_FILENAME
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sattlint-profiler",
        description="Profile workspace snapshot loading and analyzer execution for SattLine entry files.",
    )
    parser.add_argument(
        "--workspace-root",
        default=str(REPO_ROOT),
        help="Workspace root to scan for entry files.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Optional cap on profiled entry files.",
    )
    parser.add_argument(
        "--analyzer",
        action="append",
        default=[],
        help="Optional analyzer key to include. May be provided multiple times.",
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
        help="Optional directory that receives profiler_report.json.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Suppress progress messages on stderr.",
    )
    return parser.parse_args(list(argv) if argv is not None else sys.argv[1:])


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    progress_callback = None if args.no_progress else _stderr_progress
    report = profile_workspace(
        Path(args.workspace_root).resolve(),
        max_files=args.max_files,
        analyzer_keys=list(args.analyzer),
        progress_callback=progress_callback,
    )
    if args.output_dir:
        _write_report(Path(args.output_dir).resolve(), report)

    if args.format == "text":
        print(_render_text_report(report))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] in {"ok", "partial"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
