"""Typed run-history records persisted by the runs store.

Mirrors the checks pipeline result shape (``application.checks``) without
importing it, keeping the persistence schema independent and versioned.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from ..application.findings import AnalysisFinding

RUN_RECORD_SCHEMA_VERSION = 1


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _tuple_str(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(str(item) for item in cast(Sequence[object], values) if item)


def _optional_tuple_str(values: object) -> tuple[str, ...] | None:
    if values is None:
        return None
    return _tuple_str(values)


def _phase_timings_value(values: object) -> tuple[dict[str, object], ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    result: list[dict[str, object]] = []
    for item in cast(Sequence[object], values):
        if not isinstance(item, Mapping):
            continue
        result.append({str(key): value for key, value in cast(Mapping[object, object], item).items()})
    return tuple(result)


def _timings_dict_value(values: object) -> dict[str, float] | None:
    if not isinstance(values, Mapping):
        return None
    normalized: dict[str, float] = {}
    for key, value in cast(Mapping[object, object], values).items():
        if not isinstance(key, str) or isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            normalized[key] = float(value)
    return normalized or None


@dataclass(frozen=True, slots=True)
class RunAnalyzerRecord:
    key: str
    name: str
    status: str
    summary: str | None = None
    report_kind: str | None = None
    issue_count: int | None = None
    findings: tuple[AnalysisFinding, ...] = ()
    duration_ms: float | None = None
    phase_timings_ms: tuple[dict[str, object], ...] = ()
    selected_issue_kinds: tuple[str, ...] | None = None
    skip_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "report_kind": self.report_kind,
            "issue_count": self.issue_count,
            "findings": [finding.to_dict() for finding in self.findings],
            "duration_ms": self.duration_ms,
            "phase_timings_ms": [dict(phase) for phase in self.phase_timings_ms],
            "selected_issue_kinds": None if self.selected_issue_kinds is None else list(self.selected_issue_kinds),
            "skip_reason": self.skip_reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> RunAnalyzerRecord:
        raw_findings = payload.get("findings")
        findings = (
            tuple(
                AnalysisFinding.from_dict(cast(Mapping[str, object], finding))
                for finding in cast(Sequence[object], raw_findings)
                if isinstance(finding, Mapping)
            )
            if isinstance(raw_findings, (list, tuple))
            else ()
        )
        return cls(
            key=str(payload.get("key") or ""),
            name=str(payload.get("name") or ""),
            status=str(payload.get("status") or ""),
            summary=_optional_str(payload.get("summary")),
            report_kind=_optional_str(payload.get("report_kind")),
            issue_count=_optional_int(payload.get("issue_count")),
            findings=findings,
            duration_ms=_optional_float(payload.get("duration_ms")),
            phase_timings_ms=_phase_timings_value(payload.get("phase_timings_ms")),
            selected_issue_kinds=_optional_tuple_str(payload.get("selected_issue_kinds")),
            skip_reason=_optional_str(payload.get("skip_reason")),
        )


def _optional_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _optional_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


@dataclass(frozen=True, slots=True)
class RunTargetRecord:
    target_name: str
    is_library: bool = False
    analyzers: tuple[RunAnalyzerRecord, ...] = ()
    stage_timings_ms: dict[str, float] | None = None
    graphics_timings_ms: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_name": self.target_name,
            "is_library": self.is_library,
            "analyzers": [analyzer.to_dict() for analyzer in self.analyzers],
            "stage_timings_ms": self.stage_timings_ms,
            "graphics_timings_ms": self.graphics_timings_ms,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> RunTargetRecord:
        raw_analyzers = payload.get("analyzers")
        analyzers = (
            tuple(
                RunAnalyzerRecord.from_dict(cast(Mapping[str, object], analyzer))
                for analyzer in cast(Sequence[object], raw_analyzers)
                if isinstance(analyzer, Mapping)
            )
            if isinstance(raw_analyzers, (list, tuple))
            else ()
        )
        return cls(
            target_name=str(payload.get("target_name") or ""),
            is_library=bool(payload.get("is_library", False)),
            analyzers=analyzers,
            stage_timings_ms=_timings_dict_value(payload.get("stage_timings_ms")),
            graphics_timings_ms=_timings_dict_value(payload.get("graphics_timings_ms")),
        )


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    started_at: str
    finished_at: str
    project_tag: str
    selected_analyzers: tuple[str, ...] = ()
    selected_issue_kinds: tuple[str, ...] | None = None
    cancelled: bool = False
    targets: tuple[RunTargetRecord, ...] = ()
    output_lines: tuple[str, ...] = ()

    @property
    def target_count(self) -> int:
        return len(self.targets)

    @property
    def analyzer_count(self) -> int:
        return sum(len(target.analyzers) for target in self.targets)

    @property
    def issue_count(self) -> int:
        return sum(len(analyzer.findings) for target in self.targets for analyzer in target.analyzers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RUN_RECORD_SCHEMA_VERSION,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "project_tag": self.project_tag,
            "selected_analyzers": list(self.selected_analyzers),
            "selected_issue_kinds": None if self.selected_issue_kinds is None else list(self.selected_issue_kinds),
            "cancelled": self.cancelled,
            "targets": [target.to_dict() for target in self.targets],
            "output_lines": list(self.output_lines),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> RunRecord:
        raw_targets = payload.get("targets")
        targets = (
            tuple(
                RunTargetRecord.from_dict(cast(Mapping[str, object], target))
                for target in cast(Sequence[object], raw_targets)
                if isinstance(target, Mapping)
            )
            if isinstance(raw_targets, (list, tuple))
            else ()
        )
        return cls(
            run_id=str(payload.get("run_id") or ""),
            started_at=str(payload.get("started_at") or ""),
            finished_at=str(payload.get("finished_at") or ""),
            project_tag=str(payload.get("project_tag") or ""),
            selected_analyzers=_tuple_str(payload.get("selected_analyzers")),
            selected_issue_kinds=_optional_tuple_str(payload.get("selected_issue_kinds")),
            cancelled=bool(payload.get("cancelled", False)),
            targets=targets,
            output_lines=_tuple_str(payload.get("output_lines")),
        )


@dataclass(frozen=True, slots=True)
class RunSummary:
    run_id: str
    started_at: str
    finished_at: str
    project_tag: str
    target_count: int
    analyzer_count: int
    issue_count: int
    cancelled: bool

    @classmethod
    def from_record(cls, record: RunRecord) -> RunSummary:
        return cls(
            run_id=record.run_id,
            started_at=record.started_at,
            finished_at=record.finished_at,
            project_tag=record.project_tag,
            target_count=record.target_count,
            analyzer_count=record.analyzer_count,
            issue_count=record.issue_count,
            cancelled=record.cancelled,
        )


__all__ = [
    "RUN_RECORD_SCHEMA_VERSION",
    "RunAnalyzerRecord",
    "RunRecord",
    "RunSummary",
    "RunTargetRecord",
]
