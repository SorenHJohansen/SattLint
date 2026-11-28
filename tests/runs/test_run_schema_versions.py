"""Schema-version reporting for stored run records."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sattlint.runs import (
    RUN_RECORD_SCHEMA_VERSION,
    RunRecord,
    list_runs,
    load_run,
    save_run,
    scan_runs,
)


def _write_record(path: Path, run_id: str, *, version: object) -> None:
    payload: dict[str, object] = {
        "schema_version": version,
        "run_id": run_id,
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:00:01Z",
        "project_tag": "RootProgram",
        "project_path": "/work/demo.slproj",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_summary(path: Path, run_id: str, *, version: object | None) -> None:
    payload: dict[str, object] = {
        "run_id": run_id,
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:00:01Z",
        "project_tag": "RootProgram",
        "target_count": 1,
        "analyzer_count": 1,
        "issue_count": 0,
        "cancelled": False,
    }
    if version is not None:
        payload["schema_version"] = version
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("version", [RUN_RECORD_SCHEMA_VERSION - 1, RUN_RECORD_SCHEMA_VERSION + 1])
def test_a_foreign_run_record_is_reported_as_skipped_not_missing(tmp_path: Path, version: int) -> None:
    run_id = "20260101T000000000000Z-foreign"
    _write_record(tmp_path / f"{run_id}.json", run_id, version=version)

    scan = scan_runs(runs_dir=tmp_path)

    assert scan.summaries == ()
    assert len(scan.skipped) == 1
    skipped = scan.skipped[0]
    assert skipped.run_id == run_id
    assert skipped.reason == "unknown_schema"
    assert skipped.project_path == "/work/demo.slproj"
    assert f"version {version}" in skipped.detail
    assert f"reads version {RUN_RECORD_SCHEMA_VERSION}" in skipped.detail
    assert load_run(run_id, runs_dir=tmp_path) is None
    assert list_runs(runs_dir=tmp_path) == ()


@pytest.mark.parametrize(
    "sidecar_version",
    [None, RUN_RECORD_SCHEMA_VERSION - 1, RUN_RECORD_SCHEMA_VERSION + 1],
)
def test_a_sidecar_from_another_version_does_not_mask_a_skipped_record(
    tmp_path: Path,
    sidecar_version: int | None,
) -> None:
    run_id = "20260102T000000000000Z-foreign"
    version = RUN_RECORD_SCHEMA_VERSION + 1
    _write_record(tmp_path / f"{run_id}.json", run_id, version=version)
    _write_summary(tmp_path / f"{run_id}.summary", run_id, version=sidecar_version)

    scan = scan_runs(runs_dir=tmp_path)

    assert scan.summaries == ()
    assert [entry.run_id for entry in scan.skipped] == [run_id]
    assert scan.skipped[0].reason == "unknown_schema"


def test_a_current_record_with_a_current_sidecar_is_listed_normally(tmp_path: Path) -> None:
    stored = save_run(
        RunRecord(
            run_id="",
            started_at="2026-01-03T00:00:00Z",
            finished_at="2026-01-03T00:00:01Z",
            project_tag="RootProgram",
        ),
        runs_dir=tmp_path,
    )

    scan = scan_runs(runs_dir=tmp_path)

    assert [summary.run_id for summary in scan.summaries] == [stored.run_id]
    assert scan.skipped == ()
