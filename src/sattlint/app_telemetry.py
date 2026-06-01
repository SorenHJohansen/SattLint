from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from .config_io import get_config_path

ConfigDict = dict[str, object]
APP_TELEMETRY_KIND = "sattlint.app.telemetry"
APP_TELEMETRY_SCHEMA_VERSION = 1
_SESSION_ID = uuid4().hex


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


def normalize_named_timings_ms(raw_timings: object, *, scale: float = 1.0) -> dict[str, float]:
    if not isinstance(raw_timings, Mapping):
        return {}

    normalized: dict[str, float] = {}
    for raw_name, raw_duration in cast(Mapping[object, object], raw_timings).items():
        if not isinstance(raw_name, str):
            continue
        duration_ms = _coerce_duration_ms(raw_duration, scale=scale)
        if duration_ms is None:
            continue
        normalized[raw_name] = duration_ms
    return normalized


def normalize_phase_timings_ms(raw_phase_timings: object) -> list[dict[str, object]]:
    if not isinstance(raw_phase_timings, list):
        return []

    normalized: list[dict[str, object]] = []
    for raw_phase in cast(list[object], raw_phase_timings):
        if not isinstance(raw_phase, Mapping):
            continue
        phase_mapping = cast(Mapping[object, object], raw_phase)
        phase_name = phase_mapping.get("phase")
        if not isinstance(phase_name, str) or not phase_name:
            continue
        duration_ms = _coerce_duration_ms(phase_mapping.get("duration_ms"))
        if duration_ms is None:
            continue
        normalized.append({"phase": phase_name, "duration_ms": duration_ms})
    return normalized


def bottleneck_from_named_timings(named_timings_ms: Mapping[str, float], *, kind: str) -> dict[str, object] | None:
    if not named_timings_ms:
        return None
    name, duration_ms = max(named_timings_ms.items(), key=lambda item: (item[1], item[0].casefold()))
    return {"kind": kind, "name": name, "duration_ms": round(max(float(duration_ms), 0.0), 3)}


def bottleneck_from_phase_timings(
    phase_timings_ms: list[dict[str, object]],
    *,
    kind: str,
    extra_fields: Mapping[str, object] | None = None,
) -> dict[str, object] | None:
    if not phase_timings_ms:
        return None

    def _phase_sort_key(phase: dict[str, object]) -> tuple[float, str]:
        duration_ms = _coerce_duration_ms(phase.get("duration_ms")) or 0.0
        phase_name = phase.get("phase")
        return (duration_ms, str(phase_name or "").casefold())

    best_phase = max(
        phase_timings_ms,
        key=_phase_sort_key,
    )
    duration_ms = _coerce_duration_ms(best_phase.get("duration_ms")) or 0.0
    bottleneck: dict[str, object] = {
        "kind": kind,
        "name": str(best_phase.get("phase") or ""),
        "duration_ms": duration_ms,
    }
    if extra_fields:
        bottleneck.update(extra_fields)
    return bottleneck


def _telemetry_config(cfg: ConfigDict) -> Mapping[str, object] | None:
    telemetry = cfg.get("telemetry")
    if not isinstance(telemetry, dict):
        return None
    typed_telemetry = cast(dict[object, object], telemetry)
    if not all(isinstance(key, str) for key in typed_telemetry):
        return None
    return cast(dict[str, object], telemetry)


def telemetry_output_path() -> Path:
    return telemetry_output_path_for_config(get_config_path())


def telemetry_output_path_for_config(config_path: Path) -> Path:
    return Path(config_path).with_name("telemetry.jsonl")


def _resolve_telemetry_path(cfg: ConfigDict) -> Path | None:
    telemetry = _telemetry_config(cfg)
    if telemetry is None or not bool(telemetry.get("enabled", False)):
        return None
    return telemetry_output_path()


class AppTelemetry:
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
            "kind": APP_TELEMETRY_KIND,
            "schema_version": APP_TELEMETRY_SCHEMA_VERSION,
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


def create_app_telemetry(cfg: ConfigDict) -> AppTelemetry:
    return AppTelemetry(_resolve_telemetry_path(cfg))
