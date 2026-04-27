"""Derived pipeline report builders for incremental planning and performance."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sattlint.analyzers.registry import get_default_analyzer_catalog
from sattlint.path_sanitizer import sanitize_path_for_report

INCREMENTAL_ANALYSIS_SCHEMA_KIND = "sattlint.incremental_analysis"
INCREMENTAL_ANALYSIS_SCHEMA_VERSION = 1

PROFILING_SUMMARY_SCHEMA_KIND = "sattlint.profiling_summary"
PROFILING_SUMMARY_SCHEMA_VERSION = 1

PERFORMANCE_BUDGET_SCHEMA_KIND = "sattlint.performance_budget"
PERFORMANCE_BUDGET_SCHEMA_VERSION = 1

_FULL_FALLBACK_PREFIXES = (
    "src/sattline_parser/",
    "src/sattlint/core/",
    "src/sattlint/editor_api.py",
    "src/sattlint/engine.py",
    "src/sattlint/validation.py",
    "src/sattlint/devtools/",
    "src/sattlint_lsp/",
    "vscode/",
)
_ANALYZER_SOURCE_PREFIX = "src/sattlint/analyzers/"
_PROGRAM_SUFFIXES = (".s", ".x", ".l", ".z")


def _default_analyzer_report() -> dict[str, Any]:
    return get_default_analyzer_catalog().to_report(generated_by="sattlint.devtools.derived_reports")


def _normalize_changed_files(changed_files: list[str] | None, *, repo_root: Path) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_path in changed_files or []:
        path = Path(raw_path)
        if not path.is_absolute():
            path = (repo_root / path).resolve()
        sanitized = sanitize_path_for_report(path, repo_root=repo_root) or path.as_posix()
        sanitized = sanitized.replace("\\", "/")
        if sanitized in seen:
            continue
        seen.add(sanitized)
        normalized.append(sanitized)
    return sorted(normalized)


def build_incremental_analysis_report(
    changed_files: list[str] | None,
    *,
    repo_root: Path,
    analyzer_registry_report: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    normalized_changed_files = _normalize_changed_files(changed_files, repo_root=repo_root)
    if not normalized_changed_files:
        return None

    analyzer_report = analyzer_registry_report or _default_analyzer_report()
    analyzers = analyzer_report.get("analyzers") or []
    incremental_analyzers = sorted(
        str(analyzer.get("key") or "")
        for analyzer in analyzers
        if analyzer.get("supports_incremental") is True
    )
    non_incremental_analyzers = sorted(
        str(analyzer.get("key") or "")
        for analyzer in analyzers
        if analyzer.get("key") and analyzer.get("supports_incremental") is not True
    )

    fallback_reasons: list[str] = []
    mode = "none"

    if any(path.startswith(_FULL_FALLBACK_PREFIXES) for path in normalized_changed_files):
        fallback_reasons.append("shared semantic or pipeline code changed")
        mode = "full"
    elif any(path.startswith(_ANALYZER_SOURCE_PREFIX) for path in normalized_changed_files):
        fallback_reasons.append("analyzer implementation changed")
        mode = "full"
    elif any(path.endswith(_PROGRAM_SUFFIXES) or "/fixtures/corpus/" in path for path in normalized_changed_files):
        mode = "mixed" if non_incremental_analyzers else "incremental"
        if non_incremental_analyzers:
            fallback_reasons.append("non-incremental analyzers still require full execution")

    return {
        "kind": INCREMENTAL_ANALYSIS_SCHEMA_KIND,
        "schema_version": INCREMENTAL_ANALYSIS_SCHEMA_VERSION,
        "changed_files": normalized_changed_files,
        "mode": mode,
        "impacted_analyzers": incremental_analyzers if mode in {"incremental", "mixed"} else [],
        "fallback_analyzers": non_incremental_analyzers if mode == "mixed" else [],
        "fallback_reasons": fallback_reasons,
        "summary": {
            "changed_file_count": len(normalized_changed_files),
            "impacted_analyzer_count": len(incremental_analyzers if mode in {"incremental", "mixed"} else []),
            "fallback_analyzer_count": len(non_incremental_analyzers if mode == "mixed" else []),
        },
    }


def build_profiling_summary_report(
    trace_report: dict[str, Any] | None,
    *,
    slow_phase_threshold_ms: float,
) -> dict[str, Any] | None:
    if trace_report is None:
        return None

    timing_summary = dict(trace_report.get("timing_summary") or {})
    events = list(trace_report.get("events") or [])
    total_duration_ms = round(max((float(event.get("time_offset_ms") or 0.0) for event in events), default=0.0), 3)

    phases = sorted(
        [
            {
                "phase": phase,
                "event_count": int(stats.get("event_count") or 0),
                "span_ms": float(stats.get("span_ms") or 0.0),
            }
            for phase, stats in timing_summary.items()
        ],
        key=lambda item: (-item["span_ms"], item["phase"]),
    )
    slow_phases = [phase for phase in phases if phase["span_ms"] >= slow_phase_threshold_ms]

    return {
        "kind": PROFILING_SUMMARY_SCHEMA_KIND,
        "schema_version": PROFILING_SUMMARY_SCHEMA_VERSION,
        "source_file": trace_report.get("source_file"),
        "basepicture_name": trace_report.get("basepicture_name"),
        "slow_phase_threshold_ms": round(float(slow_phase_threshold_ms), 3),
        "total_duration_ms": total_duration_ms,
        "phases": phases,
        "slow_phases": slow_phases,
        "summary": {
            "phase_count": len(phases),
            "slow_phase_count": len(slow_phases),
            "total_duration_ms": total_duration_ms,
        },
    }


def build_performance_budget_report(
    profiling_summary_report: dict[str, Any] | None,
    *,
    total_budget_ms: float,
    phase_budget_ms: float,
) -> dict[str, Any] | None:
    if profiling_summary_report is None:
        return None

    total_duration_ms = float(profiling_summary_report.get("total_duration_ms") or 0.0)
    over_budget_phases = [
        {
            "phase": str(phase.get("phase") or "unknown"),
            "span_ms": float(phase.get("span_ms") or 0.0),
            "event_count": int(phase.get("event_count") or 0),
        }
        for phase in profiling_summary_report.get("phases") or []
        if float(phase.get("span_ms") or 0.0) > phase_budget_ms
    ]
    total_duration_exceeded = total_duration_ms > total_budget_ms
    violation_count = len(over_budget_phases) + (1 if total_duration_exceeded else 0)

    return {
        "kind": PERFORMANCE_BUDGET_SCHEMA_KIND,
        "schema_version": PERFORMANCE_BUDGET_SCHEMA_VERSION,
        "total_budget_ms": round(float(total_budget_ms), 3),
        "phase_budget_ms": round(float(phase_budget_ms), 3),
        "total_duration_ms": round(total_duration_ms, 3),
        "total_duration_exceeded": total_duration_exceeded,
        "over_budget_phases": over_budget_phases,
        "violation_count": violation_count,
        "status": "fail" if violation_count else "pass",
    }


__all__ = [
    "INCREMENTAL_ANALYSIS_SCHEMA_KIND",
    "INCREMENTAL_ANALYSIS_SCHEMA_VERSION",
    "PERFORMANCE_BUDGET_SCHEMA_KIND",
    "PERFORMANCE_BUDGET_SCHEMA_VERSION",
    "PROFILING_SUMMARY_SCHEMA_KIND",
    "PROFILING_SUMMARY_SCHEMA_VERSION",
    "build_incremental_analysis_report",
    "build_performance_budget_report",
    "build_profiling_summary_report",
]