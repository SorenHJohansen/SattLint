"""Derived pipeline report builders for incremental planning and performance."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict, cast

from sattlint.analysis_catalog import get_default_analyzer_catalog
from sattlint.path_sanitizer import sanitize_path_for_report

from .artifact_registry import (
    INCREMENTAL_ANALYSIS_SCHEMA_KIND,
    INCREMENTAL_ANALYSIS_SCHEMA_VERSION,
    PERFORMANCE_BUDGET_SCHEMA_KIND,
    PERFORMANCE_BUDGET_SCHEMA_VERSION,
    PROFILING_SUMMARY_SCHEMA_KIND,
    PROFILING_SUMMARY_SCHEMA_VERSION,
)

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

ReportMapping = Mapping[str, object]


class _PhaseSummary(TypedDict):
    phase: str
    event_count: int
    span_ms: float


def _mapping_list(value: object) -> list[ReportMapping]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    result: list[ReportMapping] = []
    for item in items:
        if isinstance(item, Mapping):
            result.append(cast(ReportMapping, item))
    return result


def _mapping_dict(value: object) -> dict[str, ReportMapping]:
    if not isinstance(value, Mapping):
        return {}
    entries = cast(Mapping[object, object], value)
    result: dict[str, ReportMapping] = {}
    for key, item in entries.items():
        if isinstance(key, str) and isinstance(item, Mapping):
            result[key] = cast(ReportMapping, item)
    return result


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _to_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


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
    analyzers = _mapping_list(analyzer_report.get("analyzers"))
    incremental_analyzers = sorted(
        str(analyzer.get("key") or "") for analyzer in analyzers if analyzer.get("supports_incremental") is True
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

    timing_summary = _mapping_dict(trace_report.get("timing_summary"))
    events = _mapping_list(trace_report.get("events"))
    total_duration_ms = round(max((_to_float(event.get("time_offset_ms")) for event in events), default=0.0), 3)

    phases: list[_PhaseSummary] = sorted(
        [
            _PhaseSummary(
                phase=phase,
                event_count=_to_int(stats.get("event_count")),
                span_ms=_to_float(stats.get("span_ms")),
            )
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

    total_duration_ms = _to_float(profiling_summary_report.get("total_duration_ms"))
    phases = _mapping_list(profiling_summary_report.get("phases"))
    over_budget_phases = [
        {
            "phase": str(phase.get("phase") or "unknown"),
            "span_ms": _to_float(phase.get("span_ms")),
            "event_count": _to_int(phase.get("event_count")),
        }
        for phase in phases
        if _to_float(phase.get("span_ms")) > phase_budget_ms
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
