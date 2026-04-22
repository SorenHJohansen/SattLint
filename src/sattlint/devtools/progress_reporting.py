"""Utilities for live progress reporting in developer tooling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any, Callable


@dataclass(slots=True)
class ProgressStage:
    key: str
    label: str
    status: str = "pending"
    started_at: float | None = None
    ended_at: float | None = None
    duration_seconds: float | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": self.duration_seconds,
            "detail": self.detail,
        }


class ProgressReporter:
    def __init__(
        self,
        *,
        kind: str,
        title: str,
        output_dir: Path,
        write_json: Callable[[Path, dict[str, Any]], None],
        stages: list[tuple[str, str]],
        canonical_command: str | None = None,
        filename: str = "progress.json",
        emit_stdout: bool = True,
    ) -> None:
        self.kind = kind
        self.title = title
        self.output_dir = output_dir
        self._write_json = write_json
        self._emit_stdout = emit_stdout
        self._path = output_dir / filename
        self._created_at = time.time()
        self._updated_at = self._created_at
        self._completed_at: float | None = None
        self._overall_status = "running"
        self._canonical_command = canonical_command
        self._stages = [ProgressStage(key=key, label=label) for key, label in stages]
        self._stage_index = {stage.key: index for index, stage in enumerate(self._stages)}
        self._active_stage_key: str | None = None
        self._write()

    def start_stage(self, key: str, *, detail: str | None = None) -> None:
        stage = self._stage(key)
        if stage.started_at is None:
            stage.started_at = time.time()
        stage.status = "running"
        stage.detail = detail
        self._active_stage_key = key
        index = self._stage_index[key] + 1
        if self._emit_stdout:
            suffix = f" ({detail})" if detail else ""
            print(f"[{index}/{len(self._stages)}] {self.title}: {stage.label}{suffix}", flush=True)
        self._write()

    def complete_stage(self, key: str, *, detail: str | None = None) -> None:
        stage = self._stage(key)
        ended_at = time.time()
        if stage.started_at is None:
            stage.started_at = ended_at
        stage.ended_at = ended_at
        stage.duration_seconds = round(ended_at - stage.started_at, 3)
        stage.status = "completed"
        if detail is not None:
            stage.detail = detail
        if self._active_stage_key == key:
            self._active_stage_key = None
        if self._emit_stdout:
            duration = f" in {stage.duration_seconds:.3f}s" if stage.duration_seconds is not None else ""
            suffix = f" ({stage.detail})" if stage.detail else ""
            print(f"    completed {stage.label}{duration}{suffix}", flush=True)
        self._write()

    def skip_stage(self, key: str, *, detail: str | None = None) -> None:
        stage = self._stage(key)
        stage.status = "skipped"
        stage.detail = detail
        if self._emit_stdout:
            suffix = f" ({detail})" if detail else ""
            print(f"    skipped {stage.label}{suffix}", flush=True)
        self._write()

    def fail_stage(self, key: str, *, detail: str | None = None) -> None:
        stage = self._stage(key)
        ended_at = time.time()
        if stage.started_at is None:
            stage.started_at = ended_at
        stage.ended_at = ended_at
        stage.duration_seconds = round(ended_at - stage.started_at, 3)
        stage.status = "failed"
        if detail is not None:
            stage.detail = detail
        if self._active_stage_key == key:
            self._active_stage_key = None
        self._overall_status = "failed"
        if self._emit_stdout:
            suffix = f" ({stage.detail})" if stage.detail else ""
            print(f"    failed {stage.label}{suffix}", flush=True)
        self._write()

    def finalize(self, *, overall_status: str) -> None:
        self._completed_at = time.time()
        self._overall_status = overall_status
        self._write()

    def to_dict(self) -> dict[str, Any]:
        completed_count = sum(stage.status == "completed" for stage in self._stages)
        skipped_count = sum(stage.status == "skipped" for stage in self._stages)
        failed_count = sum(stage.status == "failed" for stage in self._stages)
        return {
            "kind": self.kind,
            "title": self.title,
            "canonical_command": self._canonical_command,
            "overall_status": self._overall_status,
            "created_at": self._created_at,
            "updated_at": self._updated_at,
            "completed_at": self._completed_at,
            "active_stage": self._active_stage_payload(),
            "stage_count": len(self._stages),
            "completed_stage_count": completed_count,
            "skipped_stage_count": skipped_count,
            "failed_stage_count": failed_count,
            "stages": [stage.to_dict() for stage in self._stages],
        }

    def _active_stage_payload(self) -> dict[str, Any] | None:
        if self._active_stage_key is None:
            return None
        stage = self._stage(self._active_stage_key)
        return {
            "key": stage.key,
            "label": stage.label,
            "detail": stage.detail,
        }

    def _stage(self, key: str) -> ProgressStage:
        index = self._stage_index.get(key)
        if index is None:
            raise KeyError(f"Unknown progress stage: {key}")
        return self._stages[index]

    def _write(self) -> None:
        self._updated_at = time.time()
        self._write_json(self._path, self.to_dict())


__all__ = ["ProgressReporter", "ProgressStage"]
