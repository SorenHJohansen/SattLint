"""Headless CLI tests for run history: listing, showing, failures, and pruning."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from sattlint.application.checks import ChecksRunResult, ChecksTargetResult, TargetLoadFailure
from sattlint.application.findings import AnalysisFinding
from sattlint.cli.entry import run_cli
from sattlint.project.io import load_project
from sattlint.runs import (
    RunAnalyzerRecord,
    RunFailure,
    RunRecord,
    RunStatus,
    RunSummary,
    RunTargetRecord,
    list_runs,
    save_run,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _isolate_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sattlint.cli._project.config_path_location", lambda: tmp_path / "config.toml")


def _write_project(root: Path, *, targets: list[str] | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "programs").mkdir(exist_ok=True)
    resolved_targets = ["Demo"] if targets is None else targets
    project = root / "demo.slproj"
    project.write_text(
        "\n".join(
            [
                "slproj_version = 2",
                f"analyzed_programs_and_libraries = {json.dumps(resolved_targets)}",
                'analyzers = ["variables"]',
                'mode = "official"',
                'program_dir = "programs"',
                'ABB_lib_dir = ""',
                'icf_dir = ""',
                "other_lib_dirs = []",
                "",
                "[string_capacities]",
                "identstring = 15",
                "tagstring = 30",
                "string = 40",
                "linestring = 80",
                "maxstring = 140",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return project


def _project_scope(project: Path) -> str:
    return str(load_project(project).path)


def _record(
    *,
    run_id: str,
    project: str = "",
    started_at: str = "2026-01-01T00:00:00Z",
    status: RunStatus = "ok",
    failures: tuple[RunFailure, ...] = (),
    failure_message: str | None = None,
    finding: AnalysisFinding | None = None,
) -> RunRecord:
    findings = () if finding is None else (finding,)
    return RunRecord(
        run_id=run_id,
        started_at=started_at,
        finished_at=started_at,
        project_tag="Demo",
        project_path=project,
        selected_analyzers=("variables",),
        targets=(
            RunTargetRecord(
                target_name="Demo",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=findings,
                    ),
                ),
            ),
        ),
        status=status,
        failures=failures,
        failure_message=failure_message,
    )


def _fake_collect(result: ChecksRunResult) -> Callable[..., ChecksRunResult]:
    def _collect(*_args: object, **_kwargs: object) -> ChecksRunResult:
        return result

    return _collect


def test_runs_list_and_show_report_stored_runs(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path / "project")
    scope = _project_scope(project)
    finding = AnalysisFinding(kind="unused", message="declared but never read", module_path=("Demo",))
    record = save_run(_record(run_id="", project=scope, finding=finding))

    code = run_cli(["runs", "list", "--project", str(project), "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "runs list"
    assert payload["project"] == scope
    assert payload["skipped_count"] == 0
    [run] = payload["runs"]
    assert run["run_id"] == record.run_id
    assert run["status"] == "ok"
    assert run["target_count"] == 1
    assert run["analyzer_count"] == 1
    assert run["finding_count"] == 1

    code = run_cli(["runs", "list", "--project", str(project)])

    assert code == 0
    text = capsys.readouterr().out
    assert record.run_id in text
    assert " ok " in text

    code = run_cli(["runs", "show", record.run_id, "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "runs show"
    assert payload["run"]["run_id"] == record.run_id
    [analyzer] = payload["analyzers"]
    assert analyzer["key"] == "variables"
    assert analyzer["target"] == "Demo"
    assert analyzer["finding_count"] == 1
    assert payload["failures"] == []
    assert payload["failure_reason"] == ""


def test_runs_list_scopes_to_the_project(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path / "project")
    other = _write_project(tmp_path / "other")
    mine = save_run(_record(run_id="", project=_project_scope(project)))
    theirs = save_run(_record(run_id="", project=_project_scope(other)))

    code = run_cli(["runs", "list", "--project", str(project), "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert [run["run_id"] for run in payload["runs"]] == [mine.run_id]
    assert theirs.run_id not in {run["run_id"] for run in payload["runs"]}


def test_latest_findings_refuse_a_newer_failed_run(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path / "project")
    scope = _project_scope(project)
    success = save_run(
        _record(
            run_id="20200101T000000000000Z-ok",
            project=scope,
            finding=AnalysisFinding(kind="unused", message="old finding", module_path=("Demo",)),
        )
    )
    failed = save_run(
        _record(
            run_id="20990101T000000000000Z-failed",
            project=scope,
            status="failed",
            failures=(RunFailure(kind="target", message="root failed", target="Demo"),),
            failure_message="Analysis stopped because 1 target could not be loaded.",
        )
    )

    code = run_cli(["findings", "--project", str(project), "--run", "latest", "--format", "json"])

    assert code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["error"]["code"] == "run_failed"
    assert failed.run_id in payload["error"]["message"]
    assert success.run_id not in payload["error"]["message"]

    code = run_cli(["findings", "--project", str(project), "--run", success.run_id, "--format", "json"])

    assert code == 0
    assert json.loads(capsys.readouterr().out)["run"]["run_id"] == success.run_id


def test_runs_list_and_show_report_a_failed_run(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path / "project")
    scope = _project_scope(project)
    failed = save_run(
        _record(
            run_id="20990101T000000000000Z-failed",
            project=scope,
            status="failed",
            failures=(
                RunFailure(
                    kind="target",
                    message="root module could not be parsed",
                    target="Demo",
                    path="/work/programs/Demo.s",
                    line=12,
                ),
            ),
            failure_message="Analysis stopped because 1 target could not be loaded.",
        )
    )

    code = run_cli(["runs", "list", "--project", str(project), "--format", "json"])

    assert code == 0
    [run] = json.loads(capsys.readouterr().out)["runs"]
    assert run["run_id"] == failed.run_id
    assert run["status"] == "failed"
    assert run["failure_count"] == 1

    code = run_cli(["runs", "show", "latest", "--project", str(project)])

    assert code == 0
    text = capsys.readouterr().out
    assert failed.run_id in text
    assert "Status:    failed" in text
    assert "root module could not be parsed" in text


def test_a_failed_analysis_is_recorded_and_becomes_latest(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path / "project")
    scope = _project_scope(project)
    result = ChecksRunResult(
        output_lines=("Demo: root failed",),
        targets=(),
        selected_analyzers=("variables",),
        failures=(TargetLoadFailure(target_name="Demo", message="root failed"),),
    )
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(result))

    code = run_cli(["analyze", "--project", str(project), "--format", "json"])

    assert code == 2
    capsys.readouterr()

    newest = list_runs()[0]
    assert newest.project_path == scope
    assert newest.status == "failed"
    assert newest.failure_count == 1

    code = run_cli(["findings", "--project", str(project), "--run", "latest", "--format", "json"])

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "run_failed"
    assert newest.run_id in payload["error"]["message"]


def test_a_partial_analysis_stays_out_of_run_history(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path / "project", targets=["Demo", "Other"])
    previous = save_run(_record(run_id="20200101T000000000000Z-ok", project=_project_scope(project)))
    result = ChecksRunResult(
        output_lines=("Demo analyzed", "Other: root failed"),
        targets=(
            ChecksTargetResult(
                target_name="Demo",
                is_library=False,
                analyzers=(),
            ),
        ),
        selected_analyzers=("variables",),
        failures=(TargetLoadFailure(target_name="Other", message="root failed"),),
    )
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(result))

    code = run_cli(["analyze", "--project", str(project), "--format", "json", "--fail-on", "none"])

    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["failed_targets"] == 1

    # A partial run is reported now and kept out of history, so `latest` still
    # resolves to the previous complete run rather than an incomplete result.
    assert [summary.run_id for summary in list_runs()] == [previous.run_id]


def test_runs_list_reports_a_record_with_an_unknown_schema(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path / "project")
    scope = _project_scope(project)
    readable = save_run(_record(run_id="20200101T000000000000Z-ok", project=scope))
    unknown = "20990101T000000000000Z-new"
    (tmp_path / "cache" / "runs" / f"{unknown}.json").write_text(
        json.dumps({"schema_version": 999, "run_id": unknown, "project_path": scope}),
        encoding="utf-8",
    )

    code = run_cli(["runs", "list", "--project", str(project), "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert [run["run_id"] for run in payload["runs"]] == [readable.run_id]
    assert payload["skipped_count"] == 1
    assert payload["skipped"][0]["run_id"] == unknown
    assert payload["skipped"][0]["reason"] == "unknown_schema"

    code = run_cli(["runs", "list", "--project", str(project)])

    assert code == 0
    text = capsys.readouterr().out
    assert "Skipped: 1 record(s)" in text
    assert unknown in text

    code = run_cli(["findings", "--project", str(project), "--run", "latest", "--format", "json"])

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "run_unreadable"
    assert unknown in payload["error"]["message"]


def test_latest_findings_refuse_a_run_listed_from_a_legacy_sidecar_but_unreadable(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path / "project")
    scope = _project_scope(project)
    readable = save_run(_record(run_id="20200101T000000000000Z-ok", project=scope))
    unknown = "20990101T000000000000Z-new"
    runs_dir = tmp_path / "cache" / "runs"
    (runs_dir / f"{unknown}.json").write_text(
        json.dumps({"schema_version": 999, "run_id": unknown, "project_path": scope}),
        encoding="utf-8",
    )
    summary = RunSummary(
        run_id=unknown,
        started_at="2099-01-01T00:00:00Z",
        finished_at="2099-01-01T00:00:00Z",
        project_tag="Demo",
        target_count=1,
        analyzer_count=1,
        issue_count=0,
        cancelled=False,
        project_path=scope,
    )
    (runs_dir / f"{unknown}.summary").write_text(json.dumps(summary.to_dict()), encoding="utf-8")

    code = run_cli(["runs", "list", "--project", str(project), "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert [run["run_id"] for run in payload["runs"]] == [readable.run_id]
    assert payload["skipped_count"] == 1
    assert payload["skipped"][0]["run_id"] == unknown

    code = run_cli(["findings", "--project", str(project), "--run", "latest", "--format", "json"])

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "run_unreadable"
    assert unknown in payload["error"]["message"]

    code = run_cli(["runs", "prune", "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["unreadable"] == 1
    assert payload["removed_run_ids"] == [unknown]

    code = run_cli(["findings", "--project", str(project), "--run", "latest", "--format", "json"])

    assert code == 0
    assert json.loads(capsys.readouterr().out)["run"]["run_id"] == readable.run_id


def test_runs_prune_removes_only_unreadable_records_until_keep_is_given(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "cache" / "runs"
    first = save_run(_record(run_id="20200101T000000000000Z-aaa"))
    second = save_run(_record(run_id="20200102T000000000000Z-bbb"))
    (runs_dir / "20990101T000000000000Z-new.json").write_text(
        json.dumps({"schema_version": 999, "run_id": "20990101T000000000000Z-new"}),
        encoding="utf-8",
    )
    (runs_dir / "20990102T000000000000Z-broken.json").write_text("not json", encoding="utf-8")

    code = run_cli(["runs", "prune", "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["removed"] == 2
    assert payload["unreadable"] == 2
    assert payload["over_limit"] == 0
    assert payload["kept"] == 2
    assert {summary.run_id for summary in list_runs()} == {first.run_id, second.run_id}

    code = run_cli(["runs", "prune", "--keep", "1", "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["removed"] == 1
    assert payload["unreadable"] == 0
    assert payload["over_limit"] == 1
    assert payload["kept"] == 1
    assert [summary.run_id for summary in list_runs()] == [second.run_id]


def test_runs_prune_prints_a_human_summary(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    save_run(_record(run_id="20200101T000000000000Z-aaa"))
    (tmp_path / "cache" / "runs" / "20990101T000000000000Z-new.json").write_text(
        json.dumps({"schema_version": 999, "run_id": "20990101T000000000000Z-new"}),
        encoding="utf-8",
    )

    code = run_cli(["runs", "prune"])

    assert code == 0
    text = capsys.readouterr().out
    assert "Removed: 1 run record(s)" in text
    assert "Kept: 1 readable run record(s)" in text


def test_a_real_failed_analysis_is_stored_and_latest_refuses_it(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path / "project", targets=["Missing"])

    code = run_cli(["analyze", "--project", str(project), "--format", "json"])

    assert code == 2
    capsys.readouterr()

    code = run_cli(["runs", "list", "--project", str(project), "--format", "json"])

    assert code == 0
    runs = json.loads(capsys.readouterr().out)["runs"]
    assert runs and runs[0]["status"] == "failed"

    code = run_cli(["findings", "--project", str(project), "--run", "latest", "--format", "json"])

    assert code == 2
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "run_failed"
