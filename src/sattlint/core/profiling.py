"""Profiler-gated run diagnostics recording.

Replaces the former opt-in ``telemetry`` config option. Run diagnostics are
recorded only when profiling is active for the current invocation
(``SATTLINT_PROFILE`` or ``SATTLINT_PROFILE_ANALYZERS``), never through a
persistent config setting. The recorder writes one JSONL event per operation to
the profiling log under the cache directory.
"""

from __future__ import annotations

import contextlib
import json
import os
import stat
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from .. import cache as cache_module
from .timings import NamedTimings, PhaseTiming, TimingBottleneck

APP_PROFILE_KIND = "sattlint.app.profile"
APP_PROFILE_SCHEMA_VERSION = 1
PROFILE_LOG_MAX_BYTES = 8 * 1024 * 1024
_SESSION_ID = uuid4().hex

_PROFILE_DIRECTORY_MODE = 0o700
_PROFILE_LOG_MODE = 0o600
_PROFILE_ENV_NAMES = ("SATTLINT_PROFILE", "SATTLINT_PROFILE_ANALYZERS")
_PROFILE_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
# A symlinked or otherwise replaced log path must never be followed. The flag
# is absent on platforms that do not support it; the regular-file check after
# the open still rejects a directory or device there.
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def is_profiling_enabled() -> bool:
    """Whether profiling is active for the current invocation."""
    return any(os.environ.get(name, "").strip().casefold() in _PROFILE_TRUE_VALUES for name in _PROFILE_ENV_NAMES)


def profiling_log_path() -> Path | None:
    """The JSONL diagnostics log path, or ``None`` when the cache is unusable."""
    cache_dir = cache_module.get_cache_dir_or_none()
    return None if cache_dir is None else cache_dir / "profile" / "profile.jsonl"


def _ensure_owner_only_mode(path: Path, mode: int) -> None:
    """Narrow an existing path to *mode*; a missing path is left to its creator."""
    try:
        if path.stat().st_mode & 0o777 & ~mode:
            path.chmod(mode)
    except OSError:
        return


def _open_profile_log(path: Path) -> int | None:
    """Open a regular profile log without following a symlink.

    Returns ``None`` when the path is a symlink, a directory, a device, or
    otherwise cannot be opened. The descriptor is owner-only so a write never
    widens the file mode a replaced path might have brought in.
    """
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | _O_NOFOLLOW, _PROFILE_LOG_MODE)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            return None
        with contextlib.suppress(OSError):
            os.fchmod(fd, _PROFILE_LOG_MODE)
    except OSError:
        os.close(fd)
        return None
    return fd


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
            line = json.dumps(event, ensure_ascii=True, sort_keys=True, default=str)
        except (TypeError, ValueError):
            return
        self._append_event(f"{line}\n".encode())

    def _append_event(self, payload: bytes) -> None:
        """Append one encoded event, rotating or truncating a log at the cap.

        Profiling is diagnostic output, so every filesystem step here is
        best-effort: a failed rotation or append never reaches the run. The log
        is opened without following a symlink and must be a regular file, so a
        replaced path cannot redirect the write elsewhere.
        """
        path = self._path
        if path is None or len(payload) > PROFILE_LOG_MAX_BYTES:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True, mode=_PROFILE_DIRECTORY_MODE)
            _ensure_owner_only_mode(path.parent, _PROFILE_DIRECTORY_MODE)
            fd = _open_profile_log(path)
            if fd is None:
                return
            try:
                current_size = os.fstat(fd).st_size
            finally:
                os.close(fd)
            if current_size and current_size + len(payload) > PROFILE_LOG_MAX_BYTES:
                self._rotate_log()
            fd = _open_profile_log(path)
            if fd is None:
                return
            try:
                os.write(fd, payload)
            finally:
                os.close(fd)
        except OSError:
            return

    def _rotate_log(self) -> None:
        path = self._path
        if path is None:
            return
        rotated = path.with_name(f"{path.name}.1")
        try:
            os.replace(path, rotated)
        except OSError:
            with contextlib.suppress(OSError):
                os.truncate(path, 0)
            return
        _ensure_owner_only_mode(rotated, _PROFILE_LOG_MODE)


def create_profiler() -> ProfileRecorder:
    """Return an active recorder when profiling is enabled, otherwise a no-op."""
    if not is_profiling_enabled():
        return ProfileRecorder(None)
    return ProfileRecorder(profiling_log_path())


__all__ = [
    "APP_PROFILE_KIND",
    "APP_PROFILE_SCHEMA_VERSION",
    "PROFILE_LOG_MAX_BYTES",
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
