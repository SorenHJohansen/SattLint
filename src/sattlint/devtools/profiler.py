"""Workspace profiling helpers for direct devtools execution."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sattlint import app as app_module
from sattlint import config as config_module
from sattlint.analyzers.framework import AnalysisContext
from sattlint.analyzers.registry import canonicalize_analyzer_key, get_default_analyzer_catalog
from sattlint.app_analysis import source_paths_for_current_target
from sattlint.core.semantic import (
    discover_workspace_sources,
    load_workspace_snapshot,
)
from sattlint.path_sanitizer import sanitize_path_for_report
from sattlint.semantic_analysis import build_variable_semantic_artifacts

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_FILENAME = "profiler_report.json"


def _duration_ms(start: float, end: float) -> float:
    return round((end - start) * 1000, 3)


def _sanitize_repo_path(path: Path, *, workspace_root: Path) -> str:
    return sanitize_path_for_report(path, repo_root=workspace_root) or path.as_posix()


def _emit_profiler_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _entry_sort_key(entry: dict[str, Any]) -> tuple[float, str]:
    return (-float(entry.get("total_duration_ms") or 0.0), str(entry.get("entry_file") or "").casefold())


def _analyzer_sort_key(entry: dict[str, Any]) -> tuple[float, str]:
    return (-float(entry.get("total_duration_ms") or 0.0), str(entry.get("key") or "").casefold())


def _phase_sort_key(entry: dict[str, Any]) -> tuple[float, str]:
    return (-float(entry.get("duration_ms") or 0.0), str(entry.get("phase") or "").casefold())


def _choose_target_entry_file(source_paths: set[Path], *, target_name: str) -> Path | None:
    if not source_paths:
        return None

    target_key = target_name.casefold()
    stem_matches = sorted(
        (path for path in source_paths if path.stem.casefold() == target_key), key=lambda path: path.as_posix()
    )
    if stem_matches:
        return stem_matches[0]

    return sorted(source_paths, key=lambda path: path.as_posix())[0]


def _selected_analyzer_specs(analyzer_keys: Sequence[str] | None) -> list[Any]:
    catalog = get_default_analyzer_catalog()
    enabled = [analyzer.spec for analyzer in catalog.analyzers if analyzer.spec.enabled]
    if not analyzer_keys:
        return enabled

    requested = {canonicalize_analyzer_key(key) for key in analyzer_keys if key.strip()}
    return [spec for spec in enabled if spec.key.casefold() in requested]


def _profile_definition_count(base_picture: Any) -> int:
    return len(getattr(base_picture, "datatype_defs", ()) or ()) + len(
        getattr(base_picture, "moduletype_defs", ()) or ()
    )


def _build_profile_report(
    *,
    workspace_root: Path,
    program_files: Sequence[Path],
    dependency_file_count: int,
    entry_records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    phase_timings: list[dict[str, Any]],
    analyzer_keys: Sequence[str] | None,
    configured_target: dict[str, Any] | None = None,
) -> dict[str, Any]:
    total_duration_ms = round(sum(float(phase["duration_ms"]) for phase in phase_timings), 3)
    status = "ok"
    if failures and not entry_records:
        status = "error"
    elif failures:
        status = "partial"

    report = {
        "generated_by": "sattlint.devtools.profiler",
        "report_kind": "workspace-profile",
        "status": status,
        "workspace_root": _sanitize_repo_path(workspace_root, workspace_root=workspace_root),
        "summary": {
            "program_file_count": len(program_files),
            "profiled_entry_count": len(program_files),
            "successful_entry_count": len(entry_records),
            "snapshot_failure_count": len(failures),
            "analyzer_count": len(_selected_analyzer_specs(analyzer_keys)),
            "total_duration_ms": total_duration_ms,
        },
        "source_files": {
            "program_files": [_sanitize_repo_path(path, workspace_root=workspace_root) for path in program_files],
            "dependency_file_count": dependency_file_count,
        },
        "phase_timings": phase_timings,
        "entries": sorted(entry_records, key=lambda item: str(item["entry_file"]).casefold()),
        "bottlenecks": {
            "slowest_entries": sorted(entry_records, key=_entry_sort_key)[:10],
            "slowest_analyzers": _aggregate_analyzer_bottlenecks(entry_records)[:10],
            "slowest_phases": sorted(phase_timings, key=_phase_sort_key),
        },
        "snapshot_failures": failures,
    }
    if configured_target is not None:
        report["configured_target"] = configured_target
    return report


def _profile_configured_target(
    *,
    config_path: Path | None,
    target_name: str | None,
    timer: Callable[[], float],
    analyzer_keys: Sequence[str] | None,
    progress_callback: Callable[[str], None] | None,
) -> dict[str, Any]:
    resolved_config_path = (config_path or config_module.get_config_path()).resolve()
    cfg, _created_default = config_module.load_config(resolved_config_path)
    selected_target_name = target_name or str(cfg.get("analyzed_targets", [""])[0] or "")
    workspace_root = Path(str(cfg["program_dir"]))

    if progress_callback is not None:
        progress_callback(f"Profiler: loading configured target {selected_target_name or '<default>'}")

    load_start = timer()
    try:
        project_bp, graph = app_module.load_project(
            cfg,
            target_name=target_name,
        )
        resolved_target_name = str(getattr(project_bp.header, "name", selected_target_name or ""))
        entry_file = _choose_target_entry_file(
            source_paths_for_current_target(project_bp, graph),
            target_name=resolved_target_name,
        )
        if entry_file is None:
            raise RuntimeError(f"Could not resolve a source file for target {resolved_target_name!r}")
        resolved_workspace_root = workspace_root.resolve()
        resolved_entry_file = entry_file.resolve()
        profiled_target = SimpleNamespace(
            entry_file=resolved_entry_file,
            base_picture=project_bp,
            project_graph=graph,
            definitions_count=_profile_definition_count(project_bp),
        )
    except Exception as exc:
        load_end = timer()
        entry_label = target_name or selected_target_name or "<configured-target>"
        phase_timings = [
            {"phase": "configured-target-loading", "duration_ms": _duration_ms(load_start, load_end)},
            {"phase": "analyzer-run", "duration_ms": 0.0},
        ]
        return _build_profile_report(
            workspace_root=workspace_root.resolve(),
            program_files=[],
            dependency_file_count=0,
            entry_records=[],
            failures=[
                {
                    "entry_file": entry_label,
                    "duration_ms": _duration_ms(load_start, load_end),
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            ],
            phase_timings=phase_timings,
            analyzer_keys=analyzer_keys,
            configured_target={
                "target": entry_label,
                "config_path": sanitize_path_for_report(resolved_config_path, repo_root=REPO_ROOT)
                or resolved_config_path.as_posix(),
            },
        )

    load_end = timer()
    load_duration_ms = _duration_ms(load_start, load_end)
    sanitized_entry = _sanitize_repo_path(profiled_target.entry_file, workspace_root=resolved_workspace_root)

    if progress_callback is not None:
        progress_callback(f"Profiler: analyzing configured target {resolved_target_name}")
    analyzer_records, analyzer_duration_ms = _profile_snapshot_analyzers(
        profiled_target,
        timer=timer,
        analyzer_keys=analyzer_keys,
    )

    phase_timings = [
        {"phase": "configured-target-loading", "duration_ms": load_duration_ms},
        {"phase": "analyzer-run", "duration_ms": analyzer_duration_ms},
    ]
    return _build_profile_report(
        workspace_root=resolved_workspace_root,
        program_files=[profiled_target.entry_file],
        dependency_file_count=0,
        entry_records=[
            {
                "entry_file": sanitized_entry,
                "definition_count": profiled_target.definitions_count,
                "analyzers": analyzer_records,
                "load_duration_ms": load_duration_ms,
                "analysis_duration_ms": analyzer_duration_ms,
                "total_duration_ms": round(load_duration_ms + analyzer_duration_ms, 3),
            }
        ],
        failures=[],
        phase_timings=phase_timings,
        analyzer_keys=analyzer_keys,
        configured_target={
            "target": resolved_target_name,
            "config_path": sanitize_path_for_report(resolved_config_path, repo_root=REPO_ROOT)
            or resolved_config_path.as_posix(),
        },
    )


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
        issues: object = getattr(report, "issues", None)
        issue_count = len(cast(list[object], issues)) if isinstance(issues, list) else 0
        record: dict[str, Any] = {
            "key": spec.key,
            "name": spec.name,
            "issue_count": issue_count,
            "duration_ms": duration_ms,
        }
        phase_timings = getattr(report, "phase_timings", None)
        if isinstance(phase_timings, list):
            normalized_phase_timings: list[dict[str, Any]] = []
            for raw_phase in cast(list[object], phase_timings):
                if not isinstance(raw_phase, dict):
                    continue
                phase_mapping = cast(dict[str, object], raw_phase)
                phase_name = str(phase_mapping.get("phase") or "")
                if not phase_name:
                    continue
                raw_duration = phase_mapping.get("duration_ms")
                if isinstance(raw_duration, (int, float)):
                    duration_value = float(raw_duration)
                elif isinstance(raw_duration, str):
                    try:
                        duration_value = float(raw_duration)
                    except ValueError:
                        duration_value = 0.0
                else:
                    duration_value = 0.0
                normalized_phase_timings.append(
                    {
                        "phase": phase_name,
                        "duration_ms": round(duration_value, 3),
                    }
                )
            if normalized_phase_timings:
                record["phase_timings"] = normalized_phase_timings
        records.append(record)
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
    config_path: Path | None = None,
    target_name: str | None = None,
    timer: Callable[[], float] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    resolved_workspace_root = workspace_root.resolve()
    clock = timer or time.perf_counter

    if config_path is not None or target_name is not None:
        return _profile_configured_target(
            config_path=config_path,
            target_name=target_name,
            timer=clock,
            analyzer_keys=analyzer_keys,
            progress_callback=progress_callback,
        )

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
    return _build_profile_report(
        workspace_root=resolved_workspace_root,
        program_files=selected_program_files,
        dependency_file_count=len(discovery.dependency_files),
        entry_records=entry_records,
        failures=failures,
        phase_timings=phase_timings,
        analyzer_keys=analyzer_keys,
    )


def _render_text_report(report: dict[str, Any]) -> str:
    lines = [
        "SattLint workspace profile",
        f"Status: {report['status']}",
        f"Workspace root: {report['workspace_root']}",
        f"Program files: {report['summary']['program_file_count']}",
        f"Profiled entries: {report['summary']['profiled_entry_count']}",
        f"Total duration: {report['summary']['total_duration_ms']} ms",
        "",
    ]
    configured_target = report.get("configured_target")
    if isinstance(configured_target, dict):
        configured_target_info = cast(dict[str, str], configured_target)
        lines.extend(
            [
                f"Configured target: {configured_target_info.get('target', '')}",
                f"Config path: {configured_target_info.get('config_path', '')}",
            ]
        )
    lines.extend(
        [
            "Phase timings:",
        ]
    )
    for phase in report.get("phase_timings", []):
        lines.append(f"- {phase['phase']}: {phase['duration_ms']} ms")

    lines.append("")
    lines.append("Slowest entries:")
    slowest_entries = report.get("bottlenecks", {}).get("slowest_entries", [])
    if not slowest_entries:
        lines.append("- none")
    for entry in slowest_entries:
        lines.append(f"- {entry['entry_file']}: {entry['total_duration_ms']} ms")
        for analyzer in entry.get("analyzers", []):
            phase_timings = analyzer.get("phase_timings", [])
            if not phase_timings:
                continue
            lines.append(f"  - {analyzer['key']} phases:")
            for phase in phase_timings:
                lines.append(f"    - {phase['phase']}: {phase['duration_ms']} ms")

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


def _write_profiler_report(output_dir: Path, report: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / DEFAULT_OUTPUT_FILENAME
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def _parse_profiler_args(argv: Sequence[str] | None) -> argparse.Namespace:
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
        "--config",
        default=None,
        help="Optional SattLint config path. When provided, profile one configured target instead of scanning a workspace.",
    )
    parser.add_argument(
        "--target",
        default=None,
        help="Optional configured target name to profile from the selected config.",
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
    args = _parse_profiler_args(argv)
    progress_callback = None if args.no_progress else _emit_profiler_progress
    report = profile_workspace(
        Path(args.workspace_root).resolve(),
        max_files=args.max_files,
        analyzer_keys=list(args.analyzer),
        config_path=Path(args.config).resolve() if args.config else None,
        target_name=args.target,
        progress_callback=progress_callback,
    )
    output_error: OSError | None = None
    if args.output_dir:
        try:
            _write_profiler_report(Path(args.output_dir).resolve(), report)
        except OSError as exc:
            output_error = exc

    if args.format == "text":
        print(_render_text_report(report))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    if output_error is not None:
        print(f"profiler output error: {output_error}", file=sys.stderr, flush=True)
        return 1
    return 0 if report["status"] in {"ok", "partial"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
