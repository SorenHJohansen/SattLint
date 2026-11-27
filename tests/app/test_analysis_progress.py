"""The progress wire format shared by the analysis child and its parent."""

from __future__ import annotations

import json

import pytest

from sattlint.core.progress import (
    PROGRESS_PREFIX,
    AnalysisProgressEvent,
    ProgressPhase,
    encode_progress_line,
    parse_progress_line,
)


def test_progress_record_round_trips_every_field() -> None:
    event = AnalysisProgressEvent(
        phase=ProgressPhase.ANALYZING,
        target_total=3,
        analyzer_total=4,
        project_wide_total=1,
        target_index=2,
        target_name="TargetB",
        analyzer_index=3,
        analyzer_name="Variable issues",
        analyzer_key="variables",
        project_wide=False,
    )

    line = encode_progress_line(event)

    assert line.startswith(PROGRESS_PREFIX)
    assert "\n" not in line
    assert parse_progress_line(line) == event


def test_human_output_lines_are_not_progress_records() -> None:
    assert parse_progress_line("=== Target: TargetA ===") is None
    assert parse_progress_line("") is None


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        json.dumps([]),
        json.dumps({"record_type": "finding", "phase": "start"}),
        json.dumps({"record_type": "progress", "phase": "unknown"}),
        json.dumps({"record_type": "progress", "schema_version": 0, "phase": "start"}),
        json.dumps({"record_type": "progress", "schema_version": 1}),
    ],
)
def test_malformed_progress_records_are_ignored(payload: str) -> None:
    assert parse_progress_line(f"{PROGRESS_PREFIX}{payload}") is None
