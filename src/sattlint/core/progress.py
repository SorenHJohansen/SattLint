"""Typed analysis progress records shared by the runner, CLI, and shell.

The interactive shell runs an analysis in a child process, so the two sides
need a small, explicit contract. The child encodes one record per stderr line
with a fixed prefix; the parent parses those lines back into the event below
and keeps them out of the human-readable diagnostics stream.

The module lives in ``core`` because the project loader emits loading events
and must not depend on the application layer.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

PROGRESS_PREFIX = "sattlint-progress "
PROGRESS_RECORD_TYPE = "progress"
PROGRESS_SCHEMA_VERSION = 1

__all__ = [
    "PROGRESS_PREFIX",
    "PROGRESS_RECORD_TYPE",
    "PROGRESS_SCHEMA_VERSION",
    "AnalysisProgressEvent",
    "ProgressCallback",
    "ProgressPhase",
    "encode_progress_line",
    "parse_progress_line",
]


class ProgressPhase(StrEnum):
    """The step an analysis run reports."""

    START = "start"
    LOADING = "loading"
    ANALYZING = "analyzing"
    TARGET_COMPLETE = "target-complete"


@dataclass(frozen=True, slots=True)
class AnalysisProgressEvent:
    """One observable step of an analysis run.

    ``target_total`` and ``analyzer_total`` describe the run as a whole, while
    ``target_index`` and ``analyzer_index`` are the 1-based positions of the
    step that is starting. A project-wide analyzer has no target; its position
    uses ``analyzer_index`` against ``project_wide_total``.
    """

    phase: ProgressPhase
    target_total: int = 0
    analyzer_total: int = 0
    project_wide_total: int = 0
    target_index: int = 0
    target_name: str = ""
    analyzer_index: int = 0
    analyzer_name: str = ""
    analyzer_key: str = ""
    project_wide: bool = False


ProgressCallback = Callable[[AnalysisProgressEvent], None]


def _payload(event: AnalysisProgressEvent) -> dict[str, object]:
    return {
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "record_type": PROGRESS_RECORD_TYPE,
        "phase": event.phase.value,
        "target_total": event.target_total,
        "analyzer_total": event.analyzer_total,
        "project_wide_total": event.project_wide_total,
        "target_index": event.target_index,
        "target_name": event.target_name,
        "analyzer_index": event.analyzer_index,
        "analyzer_name": event.analyzer_name,
        "analyzer_key": event.analyzer_key,
        "project_wide": event.project_wide,
    }


def encode_progress_line(event: AnalysisProgressEvent) -> str:
    """Encode one event as a single prefixed stderr line."""
    document = json.dumps(_payload(event), ensure_ascii=False, separators=(",", ":"))
    return f"{PROGRESS_PREFIX}{document}"


def _mapping(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    return cast(Mapping[str, object], value)


def _int_field(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        return 0
    return max(0, value)


def _text_field(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def parse_progress_line(line: str) -> AnalysisProgressEvent | None:
    """Decode a progress line, or return ``None`` for any other line."""
    if not line.startswith(PROGRESS_PREFIX):
        return None
    try:
        raw: object = json.loads(line[len(PROGRESS_PREFIX) :])
    except json.JSONDecodeError:
        return None
    payload = _mapping(raw)
    if payload is None:
        return None
    if payload.get("record_type") != PROGRESS_RECORD_TYPE:
        return None
    if payload.get("schema_version") != PROGRESS_SCHEMA_VERSION:
        return None
    try:
        phase = ProgressPhase(str(payload.get("phase")))
    except ValueError:
        return None
    project_wide = payload.get("project_wide")
    return AnalysisProgressEvent(
        phase=phase,
        target_total=_int_field(payload, "target_total"),
        analyzer_total=_int_field(payload, "analyzer_total"),
        project_wide_total=_int_field(payload, "project_wide_total"),
        target_index=_int_field(payload, "target_index"),
        target_name=_text_field(payload, "target_name"),
        analyzer_index=_int_field(payload, "analyzer_index"),
        analyzer_name=_text_field(payload, "analyzer_name"),
        analyzer_key=_text_field(payload, "analyzer_key"),
        project_wide=project_wide is True,
    )
