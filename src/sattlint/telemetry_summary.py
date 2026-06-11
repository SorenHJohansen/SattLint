from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast


def _coerce_duration_ms(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(max(float(value), 0.0), 3)
    if isinstance(value, str):
        try:
            return round(max(float(value), 0.0), 3)
        except ValueError:
            return None
    return None


def _sort_records(records: list[dict[str, Any]], *, key_name: str) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda item: (
            -float(item.get("total_duration_ms") or 0.0),
            -float(item.get("max_duration_ms") or 0.0),
            str(item.get(key_name) or "").casefold(),
        ),
    )


def _mapping_values(raw_mapping: object) -> list[tuple[str, float]]:
    if not isinstance(raw_mapping, Mapping):
        return []

    values: list[tuple[str, float]] = []
    for raw_name, raw_duration in cast(Mapping[object, object], raw_mapping).items():
        if not isinstance(raw_name, str):
            continue
        duration_ms = _coerce_duration_ms(raw_duration)
        if duration_ms is None:
            continue
        values.append((raw_name, duration_ms))
    return values


def _aggregate_named_timings(
    values: list[tuple[str, float]],
    *,
    key_name: str = "name",
    extra_fields_by_name: Mapping[str, Mapping[str, object]] | None = None,
) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    for name, duration_ms in values:
        record = totals.setdefault(
            name,
            {
                key_name: name,
                "count": 0,
                "total_duration_ms": 0.0,
                "max_duration_ms": 0.0,
            },
        )
        record["count"] = int(record["count"]) + 1
        record["total_duration_ms"] = round(float(record["total_duration_ms"]) + duration_ms, 3)
        record["max_duration_ms"] = round(max(float(record["max_duration_ms"]), duration_ms), 3)

    records = _sort_records(list(totals.values()), key_name=key_name)
    if extra_fields_by_name:
        for record in records:
            extras = extra_fields_by_name.get(str(record[key_name]))
            if extras:
                record.update(extras)
    return records


def summarize_telemetry_file(path: Path) -> dict[str, Any]:  # noqa: PLR0915
    telemetry_path = Path(path)
    if not telemetry_path.exists():
        raise FileNotFoundError(telemetry_path)

    operation_totals: dict[str, dict[str, Any]] = {}
    stage_values: list[tuple[str, float]] = []
    graphics_values: list[tuple[str, float]] = []
    analyzer_values: list[tuple[str, float]] = []
    analyzer_phase_values: list[tuple[str, float]] = []
    analyzer_phase_meta: dict[str, dict[str, object]] = {}
    variable_phase_values: list[tuple[str, float]] = []
    malformed_lines: list[int] = []
    event_count = 0

    for line_number, raw_line in enumerate(telemetry_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            malformed_lines.append(line_number)
            continue
        if not isinstance(event, dict):
            malformed_lines.append(line_number)
            continue

        event_mapping = cast(Mapping[object, object], event)
        raw_payload = event_mapping.get("payload")
        payload: Mapping[object, object] = (
            cast(Mapping[object, object], raw_payload)
            if isinstance(raw_payload, Mapping)
            else cast(Mapping[object, object], {})
        )
        raw_operation = event_mapping.get("operation")
        operation = raw_operation if isinstance(raw_operation, str) and raw_operation else "unknown"
        duration_ms = _coerce_duration_ms(event_mapping.get("duration_ms")) or 0.0
        event_count += 1

        operation_record = operation_totals.setdefault(
            operation,
            {
                "operation": operation,
                "count": 0,
                "total_duration_ms": 0.0,
                "max_duration_ms": 0.0,
                "failure_count": 0,
                "cancelled_count": 0,
            },
        )
        operation_record["count"] = int(operation_record["count"]) + 1
        operation_record["total_duration_ms"] = round(float(operation_record["total_duration_ms"]) + duration_ms, 3)
        operation_record["max_duration_ms"] = round(max(float(operation_record["max_duration_ms"]), duration_ms), 3)
        if event_mapping.get("success") is False:
            operation_record["failure_count"] = int(operation_record["failure_count"]) + 1
        if bool(event_mapping.get("cancelled", False)):
            operation_record["cancelled_count"] = int(operation_record["cancelled_count"]) + 1

        stage_values.extend(_mapping_values(payload.get("stage_timings_ms")))
        graphics_values.extend(_mapping_values(payload.get("graphics_timings_ms")))
        analyzer_values.extend(_mapping_values(payload.get("analyzer_timings_ms")))

        raw_variable_phases = payload.get("phase_timings_ms")
        if isinstance(raw_variable_phases, list):
            for raw_phase in cast(list[object], raw_variable_phases):
                if not isinstance(raw_phase, Mapping):
                    continue
                phase_mapping = cast(Mapping[object, object], raw_phase)
                phase_name = phase_mapping.get("phase")
                if not isinstance(phase_name, str):
                    continue
                duration = _coerce_duration_ms(phase_mapping.get("duration_ms"))
                if duration is None:
                    continue
                variable_phase_values.append((phase_name, duration))

        raw_analyzer_phases = payload.get("analyzer_phase_timings_ms")
        if isinstance(raw_analyzer_phases, Mapping):
            for raw_analyzer_key, raw_phase_timings in cast(Mapping[object, object], raw_analyzer_phases).items():
                if not isinstance(raw_analyzer_key, str) or not isinstance(raw_phase_timings, list):
                    continue
                for raw_phase in cast(list[object], raw_phase_timings):
                    if not isinstance(raw_phase, Mapping):
                        continue
                    phase_mapping = cast(Mapping[object, object], raw_phase)
                    phase_name = phase_mapping.get("phase")
                    if not isinstance(phase_name, str):
                        continue
                    duration = _coerce_duration_ms(phase_mapping.get("duration_ms"))
                    if duration is None:
                        continue
                    composite_name = f"{raw_analyzer_key}:{phase_name}"
                    analyzer_phase_values.append((composite_name, duration))
                    analyzer_phase_meta[composite_name] = {
                        "analyzer_key": raw_analyzer_key,
                        "phase": phase_name,
                    }

    operations = _sort_records(list(operation_totals.values()), key_name="operation")
    for record in operations:
        record["average_duration_ms"] = round(float(record["total_duration_ms"]) / max(int(record["count"]), 1), 3)

    return {
        "path": str(telemetry_path),
        "event_count": event_count,
        "malformed_line_count": len(malformed_lines),
        "malformed_lines": malformed_lines,
        "operations": operations,
        "slowest_stage_timings": _aggregate_named_timings(stage_values),
        "slowest_graphics_phases": _aggregate_named_timings(graphics_values),
        "slowest_analyzers": _aggregate_named_timings(analyzer_values),
        "slowest_analyzer_phases": _aggregate_named_timings(
            analyzer_phase_values,
            extra_fields_by_name=analyzer_phase_meta,
        ),
        "slowest_variable_phases": _aggregate_named_timings(variable_phase_values),
    }


def render_text_summary(summary: dict[str, Any]) -> str:
    lines = [
        f"Telemetry summary: {summary['path']}",
        f"Events: {summary['event_count']} valid, {summary['malformed_line_count']} malformed",
    ]

    sections: list[tuple[str, list[dict[str, Any]], str]] = [
        ("Operations", cast(list[dict[str, Any]], summary.get("operations", [])), "operation"),
        ("Slowest stages", cast(list[dict[str, Any]], summary.get("slowest_stage_timings", [])), "name"),
        (
            "Slowest graphics phases",
            cast(list[dict[str, Any]], summary.get("slowest_graphics_phases", [])),
            "name",
        ),
        ("Slowest analyzers", cast(list[dict[str, Any]], summary.get("slowest_analyzers", [])), "name"),
        (
            "Slowest analyzer phases",
            cast(list[dict[str, Any]], summary.get("slowest_analyzer_phases", [])),
            "name",
        ),
        (
            "Slowest variable-analysis phases",
            cast(list[dict[str, Any]], summary.get("slowest_variable_phases", [])),
            "name",
        ),
    ]

    for title, records, key_name in sections:
        lines.append("")
        lines.append(title + ":")
        if not records:
            lines.append("  none")
            continue
        for record in records[:5]:
            label = str(record.get(key_name) or "unknown")
            lines.append(
                f"  - {label}: total={record.get('total_duration_ms', 0.0)}ms max={record.get('max_duration_ms', 0.0)}ms count={record.get('count', 0)}"
            )

    malformed_lines = cast(list[int], summary.get("malformed_lines", []))
    if malformed_lines:
        lines.append("")
        lines.append("Malformed lines:")
        lines.append("  - " + ", ".join(str(line_number) for line_number in malformed_lines[:10]))

    return "\n".join(lines)
