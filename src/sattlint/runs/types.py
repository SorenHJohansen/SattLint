"""Typed run-history records persisted by the runs store.

Mirrors the checks pipeline result shape (``application.checks``) without
importing it, keeping the persistence schema independent and versioned.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from ..application.findings import AnalysisFinding, optional_text

RUN_RECORD_SCHEMA_VERSION = 2


def _text_field(payload: Mapping[str, object], key: str, *, default: str = "") -> str:
    """A required text field; a corrupt value rejects the record."""
    value = payload.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"run field {key!r} must be a string")
    return value


def _bool_field(payload: Mapping[str, object], key: str, *, default: bool = False) -> bool:
    value = payload.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"run field {key!r} must be a boolean")
    return value


def _int_field(payload: Mapping[str, object], key: str, *, default: int = 0) -> int:
    value = payload.get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"run field {key!r} must be an integer")
    return value


def _tuple_str(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise ValueError("run field must be a list of strings")
    sequence = cast(Sequence[object], values)
    if not all(isinstance(item, str) for item in sequence):
        raise ValueError("run field must be a list of strings")
    return tuple(cast(Sequence[str], sequence))


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
    skip_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
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
            key=_text_field(payload, "key"),
            name=_text_field(payload, "name"),
            status=_text_field(payload, "status"),
            summary=optional_text(payload.get("summary")),
            report_kind=optional_text(payload.get("report_kind")),
            issue_count=_optional_int_field(payload, "issue_count"),
            findings=findings,
            duration_ms=_optional_float_field(payload, "duration_ms"),
            phase_timings_ms=_phase_timings_value(payload.get("phase_timings_ms")),
            skip_reason=optional_text(payload.get("skip_reason")),
        )


def _optional_int_field(payload: Mapping[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"run field {key!r} must be an integer or null")
    return value


def _optional_float_field(payload: Mapping[str, object], key: str) -> float | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"run field {key!r} must be a number or null")
    return float(value)


@dataclass(frozen=True, slots=True)
class RunModuleRecord:
    name: str
    kind: str = ""
    moduletype_name: str | None = None
    children: tuple[RunModuleRecord, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind,
            "moduletype_name": self.moduletype_name,
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> RunModuleRecord:
        raw_children = payload.get("children")
        children = (
            tuple(
                cls.from_dict(cast(Mapping[str, object], child))
                for child in cast(Sequence[object], raw_children)
                if isinstance(child, Mapping)
            )
            if isinstance(raw_children, (list, tuple))
            else ()
        )
        return cls(
            name=_text_field(payload, "name"),
            kind=_text_field(payload, "kind"),
            moduletype_name=optional_text(payload.get("moduletype_name")),
            children=children,
        )


@dataclass(frozen=True, slots=True)
class RunTargetRecord:
    target_name: str
    is_library: bool = False
    analyzers: tuple[RunAnalyzerRecord, ...] = ()
    stage_timings_ms: dict[str, float] | None = None
    graphics_timings_ms: dict[str, float] | None = None
    module: RunModuleRecord | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "target_name": self.target_name,
            "is_library": self.is_library,
            "analyzers": [analyzer.to_dict() for analyzer in self.analyzers],
            "stage_timings_ms": self.stage_timings_ms,
            "graphics_timings_ms": self.graphics_timings_ms,
            "module": self.module.to_dict() if self.module is not None else None,
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
            target_name=_text_field(payload, "target_name"),
            is_library=_bool_field(payload, "is_library"),
            analyzers=analyzers,
            stage_timings_ms=_timings_dict_value(payload.get("stage_timings_ms")),
            graphics_timings_ms=_timings_dict_value(payload.get("graphics_timings_ms")),
            module=RunModuleRecord.from_dict(cast(Mapping[str, object], payload["module"]))
            if isinstance(payload.get("module"), Mapping)
            else None,
        )


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    started_at: str
    finished_at: str
    project_tag: str
    project_path: str = ""
    selected_analyzers: tuple[str, ...] = ()
    cancelled: bool = False
    targets: tuple[RunTargetRecord, ...] = ()
    project_analyzers: tuple[RunAnalyzerRecord, ...] = ()
    output_lines: tuple[str, ...] = ()

    @property
    def target_count(self) -> int:
        return len(self.targets)

    @property
    def analyzer_count(self) -> int:
        return sum(len(target.analyzers) for target in self.targets) + len(self.project_analyzers)

    @property
    def issue_count(self) -> int:
        return sum(len(analyzer.findings) for target in self.targets for analyzer in target.analyzers) + sum(
            len(analyzer.findings) for analyzer in self.project_analyzers
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": RUN_RECORD_SCHEMA_VERSION,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "project_tag": self.project_tag,
            "project_path": self.project_path,
            "selected_analyzers": list(self.selected_analyzers),
            "cancelled": self.cancelled,
            "targets": [target.to_dict() for target in self.targets],
            "project_analyzers": [analyzer.to_dict() for analyzer in self.project_analyzers],
            "output_lines": list(self.output_lines),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> RunRecord:
        raw_project_analyzers = payload.get("project_analyzers")
        project_analyzers = (
            tuple(
                RunAnalyzerRecord.from_dict(cast(Mapping[str, object], analyzer))
                for analyzer in cast(Sequence[object], raw_project_analyzers)
                if isinstance(analyzer, Mapping)
            )
            if isinstance(raw_project_analyzers, (list, tuple))
            else ()
        )
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
            run_id=_text_field(payload, "run_id"),
            started_at=_text_field(payload, "started_at"),
            finished_at=_text_field(payload, "finished_at"),
            project_tag=_text_field(payload, "project_tag"),
            project_path=_text_field(payload, "project_path"),
            selected_analyzers=_tuple_str(payload.get("selected_analyzers")),
            cancelled=_bool_field(payload, "cancelled"),
            targets=targets,
            project_analyzers=project_analyzers,
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
    project_path: str = ""

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
            project_path=record.project_path,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "project_tag": self.project_tag,
            "target_count": self.target_count,
            "analyzer_count": self.analyzer_count,
            "issue_count": self.issue_count,
            "cancelled": self.cancelled,
            "project_path": self.project_path,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> RunSummary:
        return cls(
            run_id=_text_field(payload, "run_id"),
            started_at=_text_field(payload, "started_at"),
            finished_at=_text_field(payload, "finished_at"),
            project_tag=_text_field(payload, "project_tag"),
            target_count=_int_field(payload, "target_count"),
            analyzer_count=_int_field(payload, "analyzer_count"),
            issue_count=_int_field(payload, "issue_count"),
            cancelled=_bool_field(payload, "cancelled"),
            # Older records and sidecars predate the field; an empty path means unknown.
            project_path=_text_field(payload, "project_path"),
        )


__all__ = [
    "RUN_RECORD_SCHEMA_VERSION",
    "RunAnalyzerRecord",
    "RunRecord",
    "RunSummary",
    "RunTargetRecord",
]
