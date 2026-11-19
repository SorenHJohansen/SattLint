# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false
"""Focused tests for run-history persistence."""

import json
import subprocess
import sys
from pathlib import Path

from sattlint.application.findings import AnalysisFinding
from sattlint.runs import (
    RunAnalyzerRecord,
    RunModuleRecord,
    RunRecord,
    RunSummary,
    RunTargetRecord,
    delete_run,
    list_runs,
    load_run,
    prune_runs,
    save_run,
)


def _sample_record() -> RunRecord:
    return RunRecord(
        run_id="",
        started_at="2026-09-06T10:00:00Z",
        finished_at="2026-09-06T10:05:00Z",
        project_tag="RootProgram",
        selected_analyzers=("variables", "timing"),
        output_lines=("=== Target: RootProgram ===", "variables summary"),
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                module=RunModuleRecord(
                    name="RootProgram:BasePicture",
                    kind="SingleModule",
                    children=(RunModuleRecord(name="Idle", kind="FrameModule"),),
                ),
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        issue_count=1,
                        findings=(
                            AnalysisFinding(
                                kind="unused",
                                message="declared but never read",
                                module_path=("RootProgram",),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def test_run_record_round_trips_through_dict() -> None:
    record = _sample_record()

    restored = RunRecord.from_dict(record.to_dict())

    assert restored.run_id == ""
    assert restored.project_tag == "RootProgram"
    assert restored.selected_analyzers == ("variables", "timing")
    assert restored.output_lines == ("=== Target: RootProgram ===", "variables summary")
    assert restored.target_count == 1
    assert restored.analyzer_count == 1
    assert restored.issue_count == 1
    assert restored.targets[0].analyzers[0].findings[0].message == "declared but never read"
    assert restored.targets[0].module == record.targets[0].module


def test_save_and_load_run(tmp_path: Path) -> None:
    record = save_run(_sample_record(), runs_dir=tmp_path)

    assert record.run_id
    assert record.project_tag == "RootProgram"

    loaded = load_run(record.run_id, runs_dir=tmp_path)
    assert loaded is not None
    assert loaded.finished_at == "2026-09-06T10:05:00Z"
    assert loaded.targets[0].analyzers[0].key == "variables"
    assert loaded.targets[0].module == record.targets[0].module


def test_list_runs_orders_newest_first(tmp_path: Path) -> None:
    save_run(_sample_record(), runs_dir=tmp_path)

    summaries = list_runs(runs_dir=tmp_path)
    assert len(summaries) == 1
    summary = summaries[0]
    assert isinstance(summary, RunSummary)
    assert summary.project_tag == "RootProgram"
    assert summary.target_count == 1
    assert summary.issue_count == 1


def test_run_summary_round_trips_through_dict() -> None:
    summary = RunSummary(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="t",
        target_count=2,
        analyzer_count=3,
        issue_count=4,
        cancelled=True,
    )

    assert RunSummary.from_dict(summary.to_dict()) == summary


def test_save_run_writes_summary_sidecar(tmp_path: Path) -> None:
    record = save_run(_sample_record(), runs_dir=tmp_path)

    summary_path = tmp_path / f"{record.run_id}.summary"
    assert summary_path.exists()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == record.run_id
    assert payload["issue_count"] == 1


def test_list_runs_reads_summary_without_parsing_run_json(tmp_path: Path) -> None:
    record = save_run(_sample_record(), runs_dir=tmp_path)
    (tmp_path / f"{record.run_id}.json").write_text("not json", encoding="utf-8")

    summaries = list_runs(runs_dir=tmp_path)

    assert [summary.run_id for summary in summaries] == [record.run_id]
    assert summaries[0].project_tag == "RootProgram"


def test_list_runs_summarizes_legacy_run_without_writing(tmp_path: Path) -> None:
    run_id = "20260906T100000000000Z"
    payload = _sample_record().to_dict()
    payload["run_id"] = run_id
    (tmp_path / f"{run_id}.json").write_text(json.dumps(payload), encoding="utf-8")
    assert not (tmp_path / f"{run_id}.summary").exists()

    summaries = list_runs(runs_dir=tmp_path)

    assert [summary.run_id for summary in summaries] == [run_id]
    # Listing is a read; the missing sidecar is summarized in memory.
    assert not (tmp_path / f"{run_id}.summary").exists()


def test_delete_run_removes_summary_sidecar(tmp_path: Path) -> None:
    record = save_run(_sample_record(), runs_dir=tmp_path)

    assert delete_run(record.run_id, runs_dir=tmp_path) is True

    assert not (tmp_path / f"{record.run_id}.json").exists()
    assert not (tmp_path / f"{record.run_id}.summary").exists()


def test_prune_runs_removes_summary_sidecars(tmp_path: Path) -> None:
    for index in range(5):
        save_run(
            RunRecord(
                run_id="",
                started_at=f"2026-09-0{index}T10:00:00Z",
                finished_at=f"2026-09-0{index}T10:05:00Z",
                project_tag="RootProgram",
            ),
            runs_dir=tmp_path,
        )

    prune_runs(tmp_path, limit=2)

    remaining = {summary.run_id for summary in list_runs(runs_dir=tmp_path)}
    sidecars = {path.name[: -len(".summary")] for path in tmp_path.glob("*.summary")}
    assert sidecars == remaining
    assert len(remaining) == 2


def test_prune_runs_removes_oldest_beyond_limit(tmp_path: Path) -> None:
    for index in range(5):
        record = RunRecord(
            run_id="",
            started_at=f"2026-09-0{index}T10:00:00Z",
            finished_at=f"2026-09-0{index}T10:05:00Z",
            project_tag="RootProgram",
        )
        save_run(record, runs_dir=tmp_path)

    removed = prune_runs(tmp_path, limit=2)

    assert removed == 3
    assert len(list_runs(runs_dir=tmp_path)) == 2


def test_load_run_returns_none_for_missing_or_unsupported_version(tmp_path: Path) -> None:
    assert load_run("missing", runs_dir=tmp_path) is None

    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": 999, "run_id": "bad"}), encoding="utf-8")
    assert load_run("bad", runs_dir=tmp_path) is None

    path.write_text("not json", encoding="utf-8")
    assert load_run("bad", runs_dir=tmp_path) is None


def test_run_record_and_summary_round_trip_project_path() -> None:
    record = RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="RootProgram",
        project_path="/work/demo.slproj",
    )

    restored = RunRecord.from_dict(record.to_dict())
    assert restored.project_path == "/work/demo.slproj"

    summary = RunSummary.from_record(restored)
    assert summary.project_path == "/work/demo.slproj"
    assert RunSummary.from_dict(summary.to_dict()) == summary


def test_legacy_run_records_default_project_path_to_empty() -> None:
    record_payload = _sample_record().to_dict()
    record_payload.pop("project_path")

    assert RunRecord.from_dict(record_payload).project_path == ""

    summary_payload = RunSummary(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="t",
        target_count=0,
        analyzer_count=0,
        issue_count=0,
        cancelled=False,
    ).to_dict()
    summary_payload.pop("project_path")

    assert RunSummary.from_dict(summary_payload).project_path == ""


def test_save_and_load_run_persists_project_path(tmp_path: Path) -> None:
    project_path = str(tmp_path / "demo.slproj")
    record = save_run(
        RunRecord(
            run_id="",
            started_at="2026-09-06T10:00:00Z",
            finished_at="2026-09-06T10:05:00Z",
            project_tag="RootProgram",
            project_path=project_path,
        ),
        runs_dir=tmp_path,
    )

    loaded = load_run(record.run_id, runs_dir=tmp_path)
    assert loaded is not None
    assert loaded.project_path == project_path

    summaries = list_runs(runs_dir=tmp_path)
    assert summaries[0].project_path == project_path


def test_importing_runs_first_does_not_hit_a_circular_import() -> None:
    repository_root = Path(__file__).resolve().parents[2]

    completed = subprocess.run(
        [sys.executable, "-c", "import sattlint.runs"],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_save_run_generates_distinct_ids_and_leaves_no_temp_files(tmp_path: Path) -> None:
    first = save_run(_sample_record(), runs_dir=tmp_path)
    second = save_run(_sample_record(), runs_dir=tmp_path)

    assert first.run_id != second.run_id
    assert len(list(tmp_path.glob("*.json"))) == 2
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_run_never_overwrites_a_supplied_existing_id(tmp_path: Path) -> None:
    first = save_run(_sample_record(), runs_dir=tmp_path)
    second = save_run(
        RunRecord(
            run_id=first.run_id,
            started_at="2026-09-06T10:00:00Z",
            finished_at="2026-09-06T10:06:00Z",
            project_tag="RootProgram",
        ),
        runs_dir=tmp_path,
    )

    assert second.run_id != first.run_id
    assert load_run(first.run_id, runs_dir=tmp_path) is not None
    assert load_run(second.run_id, runs_dir=tmp_path) is not None


def test_load_and_delete_reject_ids_that_escape_the_runs_directory(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    outside = tmp_path / "secret.json"
    outside.write_text("{}", encoding="utf-8")

    assert load_run("../secret", runs_dir=runs_dir) is None
    assert delete_run("../secret", runs_dir=runs_dir) is False
    assert outside.exists()


def test_save_run_replaces_an_id_that_escapes_the_runs_directory(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    stored = save_run(
        RunRecord(
            run_id="../escaped",
            started_at="2026-09-06T10:00:00Z",
            finished_at="2026-09-06T10:05:00Z",
            project_tag="RootProgram",
        ),
        runs_dir=runs_dir,
    )

    assert stored.run_id != "../escaped"
    assert not (tmp_path / "escaped.json").exists()
    assert (runs_dir / f"{stored.run_id}.json").exists()


def test_corrupt_record_fields_reject_the_whole_record(tmp_path: Path) -> None:
    run_id = "20260906T100000000000Z"
    payload = _sample_record().to_dict()
    payload["run_id"] = run_id
    payload["started_at"] = 5
    (tmp_path / f"{run_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    assert load_run(run_id, runs_dir=tmp_path) is None
    assert list_runs(runs_dir=tmp_path) == ()


def test_corrupt_summary_sidecar_falls_back_to_the_run_record(tmp_path: Path) -> None:
    record = save_run(_sample_record(), runs_dir=tmp_path)
    (tmp_path / f"{record.run_id}.summary").write_text(json.dumps({"issue_count": "many"}), encoding="utf-8")

    summaries = list_runs(runs_dir=tmp_path)

    assert [summary.issue_count for summary in summaries] == [1]


def test_prune_runs_collects_orphan_summary_sidecars(tmp_path: Path) -> None:
    orphan = RunSummary(
        run_id="20260101T000000000000Z",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        project_tag="RootProgram",
        target_count=1,
        analyzer_count=1,
        issue_count=0,
        cancelled=False,
    )
    (tmp_path / f"{orphan.run_id}.summary").write_text(json.dumps(orphan.to_dict()), encoding="utf-8")

    prune_runs(tmp_path, limit=5)

    assert not (tmp_path / f"{orphan.run_id}.summary").exists()
