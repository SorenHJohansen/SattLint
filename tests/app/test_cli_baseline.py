"""Focused CLI tests for the analyze baseline gate and the baseline commands."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from sattlint.application.checks import ChecksAnalyzerResult, ChecksRunResult, ChecksTargetResult
from sattlint.application.findings import AnalysisFinding, Severity
from sattlint.cli.entry import run_cli
from sattlint.runs import RunAnalyzerRecord, RunRecord, RunSummary, RunTargetRecord
from sattlint.runs.baseline import (
    Baseline,
    BaselineEntry,
    load_baseline,
    relative_source_file,
    save_baseline,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _isolate_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sattlint.cli._project.config_path_location", lambda: tmp_path / "config.toml")


def _write_project(tmp_path: Path) -> Path:
    (tmp_path / "programs").mkdir(exist_ok=True)
    project = tmp_path / "demo.slproj"
    project.write_text(
        "\n".join(
            [
                "slproj_version = 2",
                'analyzed_programs_and_libraries = ["Demo"]',
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
    return project.resolve()


def _finding(
    *,
    module_path: tuple[str, ...] = ("Demo", "A"),
    kind: str = "unused",
    message: str = "declared but never read",
    severity: Severity | None = "warning",
    file: str | None = None,
    line: int | None = None,
) -> AnalysisFinding:
    return AnalysisFinding(
        kind=kind,
        message=message,
        module_path=module_path,
        severity=severity,
        file=file,
        line=line,
    )


def _checks_result(*findings: AnalysisFinding) -> ChecksRunResult:
    return ChecksRunResult(
        output_lines=(),
        targets=(
            ChecksTargetResult(
                target_name="Demo",
                is_library=False,
                analyzers=(
                    ChecksAnalyzerResult(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=tuple(findings),
                    ),
                ),
            ),
        ),
        selected_analyzers=("variables",),
        run_id="run-analyze",
    )


def _fake_collect(result: ChecksRunResult) -> object:
    def _collect(*_args: object, **_kwargs: object) -> ChecksRunResult:
        return result

    return _collect


def _run_record(project: Path, *findings: AnalysisFinding) -> RunRecord:
    return RunRecord(
        run_id="run-1",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        project_tag="Demo",
        project_path=str(project),
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
                        findings=tuple(findings),
                    ),
                ),
            ),
        ),
    )


def _install_runs(monkeypatch: pytest.MonkeyPatch, records: list[RunRecord]) -> None:
    summaries = tuple(RunSummary.from_record(record) for record in records)
    by_id = {record.run_id: record for record in records}

    def _load(run_id: str) -> RunRecord | None:
        return by_id.get(run_id)

    monkeypatch.setattr("sattlint.cli._findings.list_runs", lambda: summaries)
    monkeypatch.setattr("sattlint.cli._findings.load_run", _load)


def _baseline_entries(payload: dict[str, object], project_root: Path) -> list[BaselineEntry]:
    findings = cast(list[dict[str, object]], payload["findings"])
    return [
        BaselineEntry(
            identity=cast(str, finding["id"]),
            analyzer=cast(str, finding["analyzer"]),
            kind=cast(str, finding["kind"]),
            severity=cast(Severity, finding["severity"]),
            module_path=tuple(cast(list[str], finding["module_path"])),
            file=relative_source_file(cast(str | None, finding["file"]), project_root),
            line=cast(int | None, finding["line"]),
            message=cast(str, finding["message"]),
        )
        for finding in findings
    ]


def _save_baseline(path: Path, *entries: BaselineEntry) -> None:
    save_baseline(
        Baseline.create(entries, generated_by="sattlint 2026.11.6", created="2026-11-27T10:00:00.000Z"),
        path,
    )


def _analyze(project: Path, *extra: str) -> int:
    return run_cli(["analyze", "--project", str(project), "--format", "json", *extra])


def test_analyze_baseline_passes_when_every_finding_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path)
    finding = _finding(severity="warning", file=str(tmp_path / "programs" / "Demo.s"), line=12)
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(_checks_result(finding)))

    assert _analyze(project, "--fail-on", "none") == 0
    payload = cast(dict[str, object], json.loads(capsys.readouterr().out))
    baseline_path = tmp_path / "baseline.json"
    _save_baseline(baseline_path, *_baseline_entries(payload, project.parent))

    # The warning would fail the default threshold without a baseline.
    code = _analyze(project, "--baseline", str(baseline_path))

    assert code == 0
    payload = cast(dict[str, object], json.loads(capsys.readouterr().out))
    block = cast(dict[str, object], payload["baseline"])
    assert block["unchanged"] == 1
    assert block["added"] == 0
    assert block["moved"] == 0
    assert block["changed"] == 0
    assert block["stale"] == 0
    assert block["entries"] == []


def test_analyze_baseline_fails_on_a_new_finding_by_default(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path)
    baseline_path = tmp_path / "baseline.json"
    _save_baseline(baseline_path)
    finding = _finding(severity="warning", message="new finding")
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(_checks_result(finding)))

    code = _analyze(project, "--baseline", str(baseline_path))

    assert code == 1
    payload = cast(dict[str, object], json.loads(capsys.readouterr().out))
    block = cast(dict[str, object], payload["baseline"])
    assert block["added"] == 1
    entries = cast(list[dict[str, object]], block["entries"])
    assert entries[0]["status"] == "added"
    assert entries[0]["identity"] == cast(list[dict[str, object]], payload["findings"])[0]["id"]


def test_analyze_baseline_prints_counts_after_the_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path)
    baseline_path = tmp_path / "baseline.json"
    _save_baseline(baseline_path)
    finding = _finding(severity="warning", message="new finding")
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(_checks_result(finding)))

    code = run_cli(["analyze", "--project", str(project), "--baseline", str(baseline_path)])

    assert code == 1
    output = capsys.readouterr().out
    assert f"Baseline: {baseline_path}" in output
    assert "Added: 1" in output


def test_analyze_baseline_does_not_fail_on_a_new_info_finding_at_warning(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path)
    baseline_path = tmp_path / "baseline.json"
    _save_baseline(baseline_path)
    finding = _finding(kind="magic_number", message="magic number", severity="info")
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(_checks_result(finding)))

    code = _analyze(project, "--baseline", str(baseline_path), "--fail-on", "warning")

    assert code == 0
    payload = cast(dict[str, object], json.loads(capsys.readouterr().out))
    block = cast(dict[str, object], payload["baseline"])
    assert block["added"] == 1


def test_analyze_baseline_fails_when_a_severity_increase_crosses_the_threshold(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path)
    finding = _finding(severity="warning", file=str(tmp_path / "programs" / "Demo.s"), line=12)
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(_checks_result(finding)))

    assert _analyze(project, "--fail-on", "none") == 0
    payload = cast(dict[str, object], json.loads(capsys.readouterr().out))
    accepted = [replace(entry, severity="info") for entry in _baseline_entries(payload, project.parent)]
    baseline_path = tmp_path / "baseline.json"
    _save_baseline(baseline_path, *accepted)

    code = _analyze(project, "--baseline", str(baseline_path), "--fail-on", "warning")

    assert code == 1
    payload = cast(dict[str, object], json.loads(capsys.readouterr().out))
    block = cast(dict[str, object], payload["baseline"])
    assert block["changed"] == 1
    entries = cast(list[dict[str, object]], block["entries"])
    assert entries[0]["status"] == "changed"
    assert entries[0]["severity"] == "warning"
    assert entries[0]["previous_severity"] == "info"


def test_analyze_baseline_missing_file_is_a_baseline_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path)
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(_checks_result()))
    missing = tmp_path / "missing-baseline.json"

    code = run_cli(["analyze", "--project", str(project), "--baseline", str(missing), "--format", "json"])

    assert code == 2
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] == "baseline_not_found"
    assert str(missing) in error["message"]
    assert "sattlint baseline update" in error["message"]


def test_analyze_baseline_malformed_file_is_a_baseline_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path)
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(_checks_result()))
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text("{not json", encoding="utf-8")

    code = run_cli(["analyze", "--project", str(project), "--baseline", str(baseline_path), "--format", "json"])

    assert code == 2
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "baseline_invalid"


def test_baseline_update_writes_next_to_the_project_and_prunes_stale_entries(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path)
    first = _finding(severity="warning", file=str(tmp_path / "programs" / "Demo.s"), line=12)
    second = _finding(
        severity="warning",
        message="second finding",
        module_path=("Demo", "B"),
        file=str(tmp_path / "programs" / "Demo.s"),
        line=20,
    )
    _install_runs(monkeypatch, [_run_record(project, first, second)])

    code = run_cli(["baseline", "update", "--project", str(project), "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    baseline_path = project.parent / ".sattlint-baseline.json"
    assert payload["command"] == "baseline update"
    assert payload["path"] == str(baseline_path)
    assert payload["entry_count"] == 2
    assert "added" not in payload
    assert baseline_path.exists()

    _install_runs(monkeypatch, [_run_record(project, first)])
    code = run_cli(["baseline", "update", "--project", str(project), "--format", "text"])

    assert code == 0
    output = capsys.readouterr().out
    assert "Entries: 1" in output
    assert "Added: 0" in output
    assert "Pruned: 1" in output
    assert [entry.line for entry in load_baseline(baseline_path).entries] == [12]


def test_baseline_update_counts_a_moved_line_as_neither_added_nor_pruned(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path)
    first = _finding(severity="warning", file=str(tmp_path / "programs" / "Demo.s"), line=12)
    _install_runs(monkeypatch, [_run_record(project, first)])
    assert run_cli(["baseline", "update", "--project", str(project), "--format", "json"]) == 0
    capsys.readouterr()
    baseline_path = project.parent / ".sattlint-baseline.json"

    moved = _finding(severity="warning", file=str(tmp_path / "programs" / "Demo.s"), line=20)
    _install_runs(monkeypatch, [_run_record(project, moved)])
    code = run_cli(["baseline", "update", "--project", str(project), "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["entry_count"] == 1
    assert payload["added"] == 0
    assert payload["pruned"] == 0
    assert [entry.line for entry in load_baseline(baseline_path).entries] == [20]


def test_baseline_update_counts_a_secondary_match_as_neither_added_nor_pruned(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path)
    first = _finding(severity="warning", file=str(tmp_path / "programs" / "Demo.s"), line=12)
    _install_runs(monkeypatch, [_run_record(project, first)])
    assert run_cli(["baseline", "update", "--project", str(project), "--format", "json"]) == 0
    capsys.readouterr()
    baseline_path = project.parent / ".sattlint-baseline.json"
    previous_identity = load_baseline(baseline_path).entries[0].identity

    changed_identity = replace(first, data={"site": "EQ:Other"})
    _install_runs(monkeypatch, [_run_record(project, changed_identity)])
    code = run_cli(["baseline", "update", "--project", str(project), "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["entry_count"] == 1
    assert payload["added"] == 0
    assert payload["pruned"] == 0
    updated = load_baseline(baseline_path).entries[0]
    assert updated.identity != previous_identity
    assert updated.line == 12


def test_baseline_diff_reports_without_writing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path)
    first = _finding(severity="warning", file=str(tmp_path / "programs" / "Demo.s"), line=12)
    _install_runs(monkeypatch, [_run_record(project, first)])
    assert run_cli(["baseline", "update", "--project", str(project), "--format", "json"]) == 0
    capsys.readouterr()
    baseline_path = project.parent / ".sattlint-baseline.json"
    before = baseline_path.read_bytes()

    second = _finding(severity="warning", message="new finding", module_path=("Demo", "B"))
    _install_runs(monkeypatch, [_run_record(project, first, second)])
    code = run_cli(["baseline", "diff", "--project", str(project), "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "baseline diff"
    assert payload["baseline"]["added"] == 1
    assert baseline_path.read_bytes() == before


def test_baseline_file_contains_no_absolute_paths_or_snippets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_project(tmp_path)
    outside = tmp_path.parent / "outside" / "Else.s"
    findings = [
        _finding(severity="warning", file=str(tmp_path / "programs" / "Demo.s"), line=12),
        _finding(
            severity="warning",
            message="outside finding",
            module_path=("Demo", "B"),
            file=str(outside),
            line=4,
        ),
    ]
    _install_runs(monkeypatch, [_run_record(project, *findings)])

    assert run_cli(["baseline", "update", "--project", str(project), "--format", "json"]) == 0
    capsys.readouterr()
    baseline_path = project.parent / ".sattlint-baseline.json"
    text = baseline_path.read_text(encoding="utf-8")

    assert str(tmp_path) not in text
    assert str(outside) not in text
    payload = json.loads(text)
    assert {entry["file"] for entry in payload["entries"]} == {"programs/Demo.s", "Else.s"}
    for entry in payload["entries"]:
        assert not Path(entry["file"]).is_absolute()
        assert "snippet" not in entry
        assert "source" not in entry
