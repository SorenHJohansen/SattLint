"""Focused tests for run-history persistence."""

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from sattlint.application.findings import AnalysisFinding
from sattlint.cli._findings import flat_findings
from sattlint.core.timings import NamedTimings, PhaseTiming
from sattlint.runs import (
    RunAnalyzerRecord,
    RunModuleRecord,
    RunRecord,
    RunSummary,
    RunTargetRecord,
    delete_run,
    finding_acknowledgement_key,
    list_runs,
    load_run,
    load_run_acknowledgements,
    prune_runs,
    save_run,
    save_run_acknowledgements,
)
from sattlint.runs import io as runs_io


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


def _sample_record_with_timings() -> RunRecord:
    return RunRecord(
        run_id="",
        started_at="2026-09-06T10:00:00Z",
        finished_at="2026-09-06T10:05:00Z",
        project_tag="RootProgram",
        targets=(
            RunTargetRecord(
                target_name="RootProgram",
                is_library=False,
                load_duration_ms=812.5,
                stage_timings_ms=NamedTimings.of({"load_or_parse": 12.5, "validate": 3.0}),
                graphics_timings_ms=NamedTimings.of({"correlate-picture-display": 7.25}),
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        phase_timings_ms=(
                            PhaseTiming(phase="scan", duration_ms=4.5),
                            PhaseTiming(phase="report", duration_ms=2.0),
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


def test_run_timings_round_trip_through_the_store(tmp_path: Path) -> None:
    stored = save_run(_sample_record_with_timings(), runs_dir=tmp_path)

    loaded = load_run(stored.run_id, runs_dir=tmp_path)

    assert loaded is not None
    target = loaded.targets[0]
    assert target.load_duration_ms == 812.5
    assert target.stage_timings_ms == {"load_or_parse": 12.5, "validate": 3.0}
    assert target.graphics_timings_ms == {"correlate-picture-display": 7.25}
    assert target.analyzers[0].phase_timings_ms == (
        PhaseTiming(phase="scan", duration_ms=4.5),
        PhaseTiming(phase="report", duration_ms=2.0),
    )

    payload = json.loads((tmp_path / f"{stored.run_id}.json").read_text(encoding="utf-8"))
    target_payload = payload["targets"][0]
    assert target_payload["load_duration_ms"] == 812.5
    assert target_payload["stage_timings_ms"] == {"load_or_parse": 12.5, "validate": 3.0}
    assert target_payload["graphics_timings_ms"] == {"correlate-picture-display": 7.25}
    assert target_payload["analyzers"][0]["phase_timings_ms"] == [
        {"phase": "scan", "duration_ms": 4.5},
        {"phase": "report", "duration_ms": 2.0},
    ]


def test_dict_shaped_timing_payload_from_older_records_still_loads() -> None:
    payload = _sample_record().to_dict()
    targets = cast(list[object], payload["targets"])
    target_payload = cast(dict[str, object], targets[0])
    analyzers = cast(list[object], target_payload["analyzers"])
    analyzer_payload = cast(dict[str, object], analyzers[0])
    target_payload["stage_timings_ms"] = {"load_or_parse": 1.0}
    target_payload["graphics_timings_ms"] = None
    analyzer_payload["phase_timings_ms"] = [{"phase": "scan", "duration_ms": 2.5}]

    restored = RunRecord.from_dict(payload)

    assert restored.targets[0].stage_timings_ms == {"load_or_parse": 1.0}
    assert restored.targets[0].graphics_timings_ms is None
    assert restored.targets[0].analyzers[0].phase_timings_ms == (PhaseTiming(phase="scan", duration_ms=2.5),)


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


def test_acknowledgement_sidecar_round_trips_and_is_removed_with_the_run(tmp_path: Path) -> None:
    record = save_run(_sample_record(), runs_dir=tmp_path)
    keys = frozenset({"a", "b"})

    assert save_run_acknowledgements(record.run_id, keys, runs_dir=tmp_path) is True
    assert load_run_acknowledgements(record.run_id, runs_dir=tmp_path) == keys
    assert (tmp_path / f"{record.run_id}.acknowledged").exists()

    assert delete_run(record.run_id, runs_dir=tmp_path) is True
    assert not (tmp_path / f"{record.run_id}.acknowledged").exists()
    assert load_run_acknowledgements(record.run_id, runs_dir=tmp_path) == frozenset()


def test_empty_acknowledgements_remove_the_sidecar(tmp_path: Path) -> None:
    record = save_run(_sample_record(), runs_dir=tmp_path)
    save_run_acknowledgements(record.run_id, frozenset({"a"}), runs_dir=tmp_path)

    assert save_run_acknowledgements(record.run_id, frozenset(), runs_dir=tmp_path) is True

    assert not (tmp_path / f"{record.run_id}.acknowledged").exists()


def test_acknowledgement_sidecar_ignores_unreadable_payloads(tmp_path: Path) -> None:
    record = save_run(_sample_record(), runs_dir=tmp_path)
    path = tmp_path / f"{record.run_id}.acknowledged"
    path.write_text("not json", encoding="utf-8")

    assert load_run_acknowledgements(record.run_id, runs_dir=tmp_path) == frozenset()

    path.write_text(json.dumps(["keep", 4, None]), encoding="utf-8")
    assert load_run_acknowledgements(record.run_id, runs_dir=tmp_path) == frozenset({"keep"})


def test_prune_runs_removes_acknowledgement_sidecars(tmp_path: Path) -> None:
    records = [
        save_run(
            RunRecord(
                run_id="",
                started_at=f"2026-09-0{index}T10:00:00Z",
                finished_at=f"2026-09-0{index}T10:05:00Z",
                project_tag="RootProgram",
            ),
            runs_dir=tmp_path,
        )
        for index in range(5)
    ]
    for record in records:
        save_run_acknowledgements(record.run_id, frozenset({"a"}), runs_dir=tmp_path)

    prune_runs(tmp_path, limit=2)

    remaining = {summary.run_id for summary in list_runs(runs_dir=tmp_path)}
    sidecars = {path.name[: -len(".acknowledged")] for path in tmp_path.glob("*.acknowledged")}
    assert sidecars == remaining


def test_prune_runs_collects_orphan_acknowledgement_sidecars(tmp_path: Path) -> None:
    orphan_id = "20260101T000000000000Z"
    (tmp_path / f"{orphan_id}.acknowledged").write_text(json.dumps(["a"]), encoding="utf-8")

    prune_runs(tmp_path, limit=5)

    assert not (tmp_path / f"{orphan_id}.acknowledged").exists()


def test_finding_acknowledgement_key_is_stable_and_scoped() -> None:
    finding = AnalysisFinding(
        kind="unused",
        message="declared but never read",
        module_path=("RootProgram", "Idle"),
        data={"site": "SQ:Run"},
    )
    same = AnalysisFinding(
        kind="unused",
        message="declared but never read",
        module_path=("RootProgram", "Idle"),
        data={"site": "SQ:Run"},
    )

    key = finding_acknowledgement_key(target_name="RootProgram", analyzer_key="variables", finding=finding)

    assert key == finding_acknowledgement_key(target_name="RootProgram", analyzer_key="variables", finding=same)
    assert key != finding_acknowledgement_key(target_name="Other", analyzer_key="variables", finding=finding)
    assert key != finding_acknowledgement_key(target_name="RootProgram", analyzer_key="sfc", finding=finding)
    assert key != finding_acknowledgement_key(
        target_name="RootProgram",
        analyzer_key="variables",
        finding=finding,
        declaration_role="localvariable",
    )
    assert key != finding_acknowledgement_key(
        target_name="RootProgram",
        analyzer_key="variables",
        finding=AnalysisFinding(
            kind="unused",
            message="declared but never read",
            module_path=("RootProgram", "Idle"),
            data={"site": "SQ:Run", "previous_sites": ["EQ:Other"]},
        ),
    )


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


def test_prune_runs_removes_old_schema_files(tmp_path: Path) -> None:
    save_run(
        RunRecord(
            run_id="",
            started_at="2026-09-01T10:00:00Z",
            finished_at="2026-09-01T10:05:00Z",
            project_tag="RootProgram",
        ),
        runs_dir=tmp_path,
    )
    old_path = tmp_path / "0000bad.json"
    old_path.write_text(json.dumps({"schema_version": 999, "run_id": "0000bad"}), encoding="utf-8")

    removed = prune_runs(tmp_path, limit=1)

    assert removed == 1
    assert not old_path.exists()


def _record_with_finding(finding: AnalysisFinding) -> RunRecord:
    return RunRecord(
        run_id="run-1",
        started_at="2026-09-06T10:00:00Z",
        finished_at="2026-09-06T10:05:00Z",
        project_tag="Demo",
        targets=(
            RunTargetRecord(
                target_name="Demo",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(finding,),
                    ),
                ),
            ),
        ),
    )


def test_finding_identity_does_not_collide_on_delimiter_text() -> None:
    first = _record_with_finding(
        AnalysisFinding(
            kind="unused",
            rule_id="a\x1fb",
            message="declared but never read",
            module_path=("Demo", "A"),
        )
    )
    second = _record_with_finding(
        AnalysisFinding(
            kind="unused\x1fa",
            rule_id="b",
            message="declared but never read",
            module_path=("Demo", "A"),
        )
    )
    first_parts = ("Demo", "variables", "unused", "a\x1fb", "Demo.A", "", "", "declared but never read", "{}")
    second_parts = ("Demo", "variables", "unused\x1fa", "b", "Demo.A", "", "", "declared but never read", "{}")

    assert "\x1f".join(first_parts) == "\x1f".join(second_parts)
    assert flat_findings(first)[0].id != flat_findings(second)[0].id


def _record_with_output_lines(output_lines: tuple[str, ...]) -> RunRecord:
    return RunRecord(
        run_id="",
        started_at="2026-09-06T10:00:00Z",
        finished_at="2026-09-06T10:05:00Z",
        project_tag="RootProgram",
        output_lines=output_lines,
    )


def test_save_run_truncates_a_huge_output_lines_tuple(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runs_io, "RUN_OUTPUT_LINE_LIMIT", 10)
    monkeypatch.setattr(runs_io, "RUN_OUTPUT_CHAR_LIMIT", 120)
    record = _record_with_output_lines(tuple(f"output line {index} " + "x" * 40 for index in range(50)))

    stored = save_run(record, runs_dir=tmp_path)

    assert stored.truncated is True
    assert stored.truncation_note is not None
    assert "truncated" in stored.truncation_note
    assert len(stored.output_lines) <= 10
    assert sum(len(line) for line in stored.output_lines) <= 120

    loaded = load_run(stored.run_id, runs_dir=tmp_path)
    assert loaded is not None
    assert loaded.output_lines == stored.output_lines
    assert loaded.truncated is True
    summary_payload = json.loads((tmp_path / f"{stored.run_id}.summary").read_text(encoding="utf-8"))
    assert summary_payload["run_id"] == stored.run_id


def test_save_run_truncates_a_long_analyzer_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runs_io, "RUN_ANALYZER_SUMMARY_CHAR_LIMIT", 40)
    record = RunRecord(
        run_id="",
        started_at="2026-09-06T10:00:00Z",
        finished_at="2026-09-06T10:05:00Z",
        project_tag="RootProgram",
        project_analyzers=(
            RunAnalyzerRecord(
                key="variables",
                name="Variable issues",
                status="completed",
                summary="s" * 500,
            ),
        ),
    )

    stored = save_run(record, runs_dir=tmp_path)

    bounded_summary = stored.project_analyzers[0].summary
    assert bounded_summary is not None
    assert len(bounded_summary) == 40
    assert bounded_summary.endswith("[truncated]")
    assert stored.truncated is True
    assert stored.truncation_note is not None
    assert "truncated" in stored.truncation_note

    loaded = load_run(stored.run_id, runs_dir=tmp_path)
    assert loaded is not None
    assert loaded.project_analyzers[0].summary == bounded_summary


def test_save_run_leaves_a_normal_record_untruncated(tmp_path: Path) -> None:
    stored = save_run(_sample_record(), runs_dir=tmp_path)

    assert stored.truncated is False
    assert stored.truncation_note is None

    loaded = load_run(stored.run_id, runs_dir=tmp_path)
    assert loaded is not None
    assert loaded.truncated is False
    assert loaded.truncation_note is None


def test_save_run_drops_output_when_the_record_exceeds_the_byte_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runs_io, "RUN_RECORD_MAX_BYTES", 2200)
    record = _record_with_output_lines(("y" * 6000,))

    stored = save_run(record, runs_dir=tmp_path)

    assert stored.output_lines == ()
    assert stored.truncated is True
    assert stored.truncation_note is not None
    assert "exceeded" in stored.truncation_note
    record_path = tmp_path / f"{stored.run_id}.json"
    assert record_path.stat().st_size <= runs_io.RUN_RECORD_MAX_BYTES

    loaded = load_run(stored.run_id, runs_dir=tmp_path)
    assert loaded is not None
    assert loaded.output_lines == ()
    assert loaded.truncated is True


def test_save_run_drops_findings_to_fit_the_record_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cap = 32 * 1024
    monkeypatch.setattr(runs_io, "RUN_RECORD_MAX_BYTES", cap)
    findings = tuple(
        AnalysisFinding(kind="unused", message=f"finding {index} " + "x" * 2000, module_path=("Demo",))
        for index in range(200)
    )
    record = RunRecord(
        run_id="",
        started_at="2026-09-06T10:00:00Z",
        finished_at="2026-09-06T10:05:00Z",
        project_tag="Demo",
        targets=(
            RunTargetRecord(
                target_name="Demo",
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        issue_count=len(findings),
                        findings=findings,
                    ),
                ),
            ),
        ),
    )

    stored = save_run(record, runs_dir=tmp_path)

    record_path = tmp_path / f"{stored.run_id}.json"
    assert record_path.stat().st_size <= cap
    assert stored.truncated is True
    assert stored.truncation_note is not None
    analyzer = stored.targets[0].analyzers[0]
    stored_count = len(analyzer.findings)
    assert 0 < stored_count < len(findings)
    assert analyzer.issue_count == len(findings)
    assert f"stored {stored_count} of {len(findings)} findings" in stored.truncation_note

    loaded = load_run(stored.run_id, runs_dir=tmp_path)
    assert loaded is not None
    assert len(loaded.targets[0].analyzers[0].findings) == stored_count
    assert loaded.targets[0].analyzers[0].issue_count == len(findings)
    assert loaded.truncated is True


def test_legacy_run_records_default_truncation_fields() -> None:
    payload = _sample_record().to_dict()
    payload.pop("truncated")
    payload.pop("truncation_note")

    restored = RunRecord.from_dict(payload)

    assert restored.truncated is False
    assert restored.truncation_note is None


def test_legacy_run_record_without_truncation_fields_still_loads(tmp_path: Path) -> None:
    run_id = "20260906T100000000000Z"
    payload = _sample_record().to_dict()
    payload["run_id"] = run_id
    payload.pop("truncated")
    payload.pop("truncation_note")
    (tmp_path / f"{run_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_run(run_id, runs_dir=tmp_path)

    assert loaded is not None
    assert loaded.truncated is False
    assert loaded.truncation_note is None
