"""SARIF export for findings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sattlint.application.findings import AnalysisFinding
from sattlint.cli.entry import build_cli_parser, run_cli
from sattlint.runs import RunAnalyzerRecord, RunRecord, RunScan, RunSummary, RunTargetRecord


@pytest.fixture(autouse=True)
def _isolate_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sattlint.cli._project.config_path_location", lambda: tmp_path / "config.toml")


def _write_project(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "slproj_version = 2",
                'analyzed_programs_and_libraries = ["Demo"]',
                'analyzers = ["variables"]',
                'mode = "official"',
                'program_dir = "."',
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
    return path.resolve()


def _run(*, file: str | None, line: int | None, column: int | None = None, project_path: str = "") -> RunRecord:
    return RunRecord(
        run_id="run-sarif",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        project_tag="Demo",
        project_path=project_path,
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
                        findings=(
                            AnalysisFinding(
                                kind="unused",
                                message="declared but never read",
                                module_path=("Demo", "A"),
                                file=file,
                                line=line,
                                column=column,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def _install(monkeypatch: pytest.MonkeyPatch, record: RunRecord) -> None:
    def _load(_run_id: str) -> RunRecord:
        return record

    summary = RunSummary.from_record(record)
    monkeypatch.setattr("sattlint.cli._findings.list_runs", lambda: (summary,))
    monkeypatch.setattr("sattlint.cli._findings.scan_runs", lambda: RunScan(summaries=(summary,)))
    monkeypatch.setattr("sattlint.cli._findings.load_run", _load)


def test_sarif_is_an_accepted_output_format() -> None:
    parser = build_cli_parser()

    assert parser.parse_args(["analyze", "--format", "sarif"]).format == "sarif"
    assert parser.parse_args(["findings", "--format", "sarif"]).format == "sarif"


def test_sarif_maps_severity_rule_and_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _write_project(tmp_path / ".slproj")
    _install(monkeypatch, _run(file="programs/Demo.s", line=12, column=4))

    code = run_cli(["findings", "--run", "run-sarif", "--format", "sarif"])

    assert code == 0
    document = json.loads(capsys.readouterr().out)
    assert document["version"] == "2.1.0"
    assert document["$schema"].endswith("sarif-2.1.0.json")
    run = document["runs"][0]
    assert run["tool"]["driver"]["name"] == "SattLint"
    assert run["tool"]["driver"]["rules"][0]["id"] == "variables.unused"
    result = run["results"][0]
    assert result["ruleId"] == "variables.unused"
    assert result["level"] == "warning"
    assert result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "programs/Demo.s"
    assert result["locations"][0]["physicalLocation"]["region"] == {"startLine": 12, "startColumn": 4}
    assert project.exists()


def test_sarif_uses_a_project_relative_uri(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _write_project(tmp_path / ".slproj")
    source = tmp_path / "programs" / "Demo.s"
    source.parent.mkdir()
    source.write_text("(* module *)\n", encoding="utf-8")
    _install(monkeypatch, _run(file=str(source), line=1, project_path=str(project)))

    code = run_cli(["findings", "--run", "run-sarif", "--format", "sarif"])

    assert code == 0
    result = json.loads(capsys.readouterr().out)["runs"][0]["results"][0]
    assert result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "programs/Demo.s"


def test_sarif_omits_a_location_rather_than_inventing_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(tmp_path / ".slproj")
    _install(monkeypatch, _run(file=None, line=None))

    code = run_cli(["findings", "--run", "run-sarif", "--format", "sarif"])

    assert code == 0
    result = json.loads(capsys.readouterr().out)["runs"][0]["results"][0]
    assert "locations" not in result


def test_sarif_quiet_writes_only_the_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(tmp_path / ".slproj")
    _install(monkeypatch, _run(file=None, line=None))

    code = run_cli(["findings", "--run", "run-sarif", "--format", "sarif", "--quiet"])

    assert code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out)["version"] == "2.1.0"
