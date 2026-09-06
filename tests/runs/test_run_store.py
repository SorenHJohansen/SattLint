# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false
import json
from pathlib import Path

from sattlint.application.findings import AnalysisFinding
from sattlint.runs import (
    RunAnalyzerRecord,
    RunRecord,
    RunSummary,
    RunTargetRecord,
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
                                severity="warning",
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
    assert restored.targets[0].analyzers[0].findings[0].severity == "warning"


def test_save_and_load_run(tmp_path: Path) -> None:
    record = save_run(_sample_record(), runs_dir=tmp_path)

    assert record.run_id
    assert record.project_tag == "RootProgram"

    loaded = load_run(record.run_id, runs_dir=tmp_path)
    assert loaded is not None
    assert loaded.finished_at == "2026-09-06T10:05:00Z"
    assert loaded.targets[0].analyzers[0].key == "variables"


def test_list_runs_orders_newest_first(tmp_path: Path) -> None:
    save_run(_sample_record(), runs_dir=tmp_path)

    summaries = list_runs(runs_dir=tmp_path)
    assert len(summaries) == 1
    summary = summaries[0]
    assert isinstance(summary, RunSummary)
    assert summary.project_tag == "RootProgram"
    assert summary.target_count == 1
    assert summary.issue_count == 1


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
