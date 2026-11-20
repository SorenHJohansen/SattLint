"""Profiler-gated run diagnostics recording.

Replaces the former opt-in ``telemetry`` config option. Run diagnostics are
recorded only when profiling is active for the current invocation
(``SATTLINT_PROFILE`` or ``SATTLINT_PROFILE_ANALYZERS``), never through a
persistent config setting. The recorder writes one JSONL event per operation to
the profiling log under the cache directory.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from .. import cache as cache_module
from .timings import NamedTimings, PhaseTiming, TimingBottleneck

APP_PROFILE_KIND = "sattlint.app.profile"
APP_PROFILE_SCHEMA_VERSION = 1
_SESSION_ID = uuid4().hex

_PROFILE_ENV_NAMES = ("SATTLINT_PROFILE", "SATTLINT_PROFILE_ANALYZERS")
_PROFILE_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def is_profiling_enabled() -> bool:
    """Whether profiling is active for the current invocation."""
    return any(os.environ.get(name, "").strip().casefold() in _PROFILE_TRUE_VALUES for name in _PROFILE_ENV_NAMES)


def profiling_log_path() -> Path | None:
    """The JSONL diagnostics log path, or ``None`` when the cache is unusable."""
    cache_dir = cache_module.get_cache_dir_or_none()
    return None if cache_dir is None else cache_dir / "profile" / "profile.jsonl"


def _coerce_duration_ms(value: object, *, scale: float = 1.0) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(max(float(value) * scale, 0.0), 3)
    if isinstance(value, str):
        try:
            return round(max(float(value) * scale, 0.0), 3)
        except ValueError:
            return None
    return None


def normalize_named_timings_ms(raw_timings: object, *, scale: float = 1.0) -> NamedTimings:
    if not isinstance(raw_timings, Mapping):
        return NamedTimings()

    normalized: dict[str, float] = {}
    for raw_name, raw_duration in cast(Mapping[object, object], raw_timings).items():
        if not isinstance(raw_name, str):
            continue
        duration_ms = _coerce_duration_ms(raw_duration, scale=scale)
        if duration_ms is None:
            continue
        normalized[raw_name] = duration_ms
    return NamedTimings.of(normalized)


def normalize_phase_timings_ms(raw_phase_timings: object) -> tuple[PhaseTiming, ...]:
    if not isinstance(raw_phase_timings, (list, tuple)):
        return ()

    normalized: list[PhaseTiming] = []
    for raw_phase in cast(Sequence[object], raw_phase_timings):
        if isinstance(raw_phase, PhaseTiming):
            if raw_phase.phase:
                normalized.append(raw_phase)
            continue
        if not isinstance(raw_phase, Mapping):
            continue
        phase_mapping = cast(Mapping[object, object], raw_phase)
        phase_name = phase_mapping.get("phase")
        if not isinstance(phase_name, str) or not phase_name:
            continue
        duration_ms = _coerce_duration_ms(phase_mapping.get("duration_ms"))
        if duration_ms is None:
            continue
        normalized.append(PhaseTiming(phase=phase_name, duration_ms=duration_ms))
    return tuple(normalized)


def bottleneck_from_named_timings(named_timings_ms: Mapping[str, float], *, kind: str) -> TimingBottleneck | None:
    if not named_timings_ms:
        return None
    name, duration_ms = max(named_timings_ms.items(), key=lambda item: (item[1], item[0].casefold()))
    return TimingBottleneck(kind=kind, name=name, duration_ms=round(max(float(duration_ms), 0.0), 3))


def bottleneck_from_phase_timings(
    phase_timings_ms: Sequence[PhaseTiming],
    *,
    kind: str,
    analyzer_key: str | None = None,
) -> TimingBottleneck | None:
    """Return the slowest phase with its recorded duration.

    The comparison and the reported value use the recorded milliseconds as-is:
    rounding first would make a near tie fall back to the name ordering and
    would report a duration the phase did not record.
    """
    if not phase_timings_ms:
        return None

    best_phase = max(phase_timings_ms, key=lambda phase: (phase.duration_ms, phase.phase.casefold()))
    return TimingBottleneck(
        kind=kind,
        name=best_phase.phase,
        duration_ms=best_phase.duration_ms,
        analyzer_key=analyzer_key,
    )


class ProfileRecorder:
    """Appends one JSONL diagnostics event per operation while profiling."""

    def __init__(self, path: Path | None) -> None:
        self._path = path

    @property
    def enabled(self) -> bool:
        return self._path is not None

    def emit(
        self,
        *,
        operation: str,
        target_name: str,
        duration_ms: float,
        success: bool | None = None,
        cancelled: bool = False,
        payload: Mapping[str, object] | None = None,
    ) -> None:
        if self._path is None:
            return

        event: dict[str, object] = {
            "kind": APP_PROFILE_KIND,
            "schema_version": APP_PROFILE_SCHEMA_VERSION,
            "session_id": _SESSION_ID,
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "operation": operation,
            "target_name": target_name,
            "duration_ms": round(max(duration_ms, 0.0), 3),
        }
        if cancelled:
            event["cancelled"] = True
        elif success is not None:
            event["success"] = success
        if payload:
            event["payload"] = dict(payload)

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=True, sort_keys=True, default=str))
                handle.write("\n")
        except (OSError, TypeError, ValueError):
            return


def create_profiler() -> ProfileRecorder:
    """Return an active recorder when profiling is enabled, otherwise a no-op."""
    if not is_profiling_enabled():
        return ProfileRecorder(None)
    return ProfileRecorder(profiling_log_path())


__all__ = [
    "APP_PROFILE_KIND",
    "APP_PROFILE_SCHEMA_VERSION",
    "NamedTimings",
    "PhaseTiming",
    "ProfileRecorder",
    "TimingBottleneck",
    "bottleneck_from_named_timings",
    "bottleneck_from_phase_timings",
    "create_profiler",
    "is_profiling_enabled",
    "normalize_named_timings_ms",
    "normalize_phase_timings_ms",
    "profiling_log_path",
]
