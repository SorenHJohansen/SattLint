from __future__ import annotations

import json
from pathlib import Path

from sattlint import telemetry_summary


def test_summarize_telemetry_file_aggregates_bottleneck_sections(tmp_path: Path) -> None:
    telemetry_path = tmp_path / "telemetry.jsonl"
    telemetry_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "kind": "sattlint.app.telemetry",
                        "operation": "ast-refresh",
                        "duration_ms": 90.0,
                        "payload": {
                            "stage_timings_ms": {"load_or_parse": 60.0, "validate": 20.0},
                            "graphics_timings_ms": {"validate-graphics-file": 35.0},
                        },
                    }
                ),
                json.dumps(
                    {
                        "kind": "sattlint.app.telemetry",
                        "operation": "checks",
                        "duration_ms": 45.0,
                        "payload": {
                            "analyzer_timings_ms": {"variables": 22.0, "state-inference": 8.0},
                            "analyzer_phase_timings_ms": {
                                "variables": [
                                    {"phase": "collect", "duration_ms": 6.0},
                                    {"phase": "report", "duration_ms": 9.0},
                                ]
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "kind": "sattlint.app.telemetry",
                        "operation": "variable-analysis",
                        "duration_ms": 30.0,
                        "payload": {
                            "phase_timings_ms": [
                                {"phase": "collector", "duration_ms": 4.0},
                                {"phase": "report", "duration_ms": 7.0},
                            ]
                        },
                    }
                ),
                "not-json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = telemetry_summary.summarize_telemetry_file(telemetry_path)

    assert summary["event_count"] == 3
    assert summary["malformed_line_count"] == 1
    assert summary["operations"][0]["operation"] == "ast-refresh"
    assert summary["slowest_stage_timings"][0]["name"] == "load_or_parse"
    assert summary["slowest_graphics_phases"][0]["name"] == "validate-graphics-file"
    assert summary["slowest_analyzers"][0]["name"] == "variables"
    assert summary["slowest_analyzer_phases"][0]["analyzer_key"] == "variables"
    assert summary["slowest_analyzer_phases"][0]["phase"] == "report"
    assert summary["slowest_variable_phases"][0]["name"] == "report"


def test_render_text_summary_lists_major_sections(tmp_path: Path) -> None:
    summary = {
        "path": str(tmp_path / "telemetry.jsonl"),
        "event_count": 2,
        "malformed_line_count": 0,
        "malformed_lines": [],
        "operations": [{"operation": "checks", "count": 1, "total_duration_ms": 12.0, "max_duration_ms": 12.0}],
        "slowest_stage_timings": [
            {"name": "load_or_parse", "count": 1, "total_duration_ms": 8.0, "max_duration_ms": 8.0}
        ],
        "slowest_graphics_phases": [],
        "slowest_analyzers": [{"name": "variables", "count": 1, "total_duration_ms": 5.0, "max_duration_ms": 5.0}],
        "slowest_analyzer_phases": [],
        "slowest_variable_phases": [{"name": "report", "count": 1, "total_duration_ms": 3.0, "max_duration_ms": 3.0}],
    }

    rendered = telemetry_summary.render_text_summary(summary)

    assert "Telemetry summary:" in rendered
    assert "Operations:" in rendered
    assert "Slowest stages:" in rendered
    assert "load_or_parse" in rendered
    assert "variables" in rendered
    assert "report" in rendered
