"""Headless CLI command tests (project, analyzers, analyze, findings, show)."""

from __future__ import annotations

import argparse
import io
import json
import logging
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast

import pytest
from sattline_parser.models.ast_model import BasePicture

from sattlint import cache as cache_module
from sattlint.analyzers.catalog import get_selectable_analyzers
from sattlint.application import checks as checks_module
from sattlint.application import checks_records
from sattlint.application.checks import (
    ChecksAnalyzerResult,
    ChecksRunResult,
    ChecksTargetResult,
    TargetLoadFailure,
)
from sattlint.application.findings import AnalysisFinding
from sattlint.cli import _findings as findings_module
from sattlint.cli import _output as output_module
from sattlint.cli import commands as commands_module
from sattlint.cli import entry as entry_module
from sattlint.cli._findings import (
    FindingFilters,
    filter_findings,
    flat_findings,
    group_findings,
    resolve_run,
)
from sattlint.cli._output import CliError
from sattlint.cli._project import project_payload
from sattlint.cli.entry import build_cli_parser, run_cli
from sattlint.config.types import ConfigDict
from sattlint.core.progress import AnalysisProgressEvent, ProgressPhase, parse_progress_line
from sattlint.models.project_graph import ProjectGraph
from sattlint.project.io import load_project
from sattlint.runs import RunAnalyzerRecord, RunRecord, RunSummary, RunTargetRecord

# Captured before the shared fixture isolates the cache location per test.
_REAL_CACHE_DIR_LOCATION = cache_module.cache_dir_location

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _isolate_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sattlint.cli._project.config_path_location", lambda: tmp_path / "config.toml")


def _write_project(
    tmp_path: Path,
    *,
    target: str = "Demo",
    program_dir: str = "programs",
    targets: list[str] | None = None,
    analyzers: list[str] | None = None,
    capacities: dict[str, int] | None = None,
) -> Path:
    project = tmp_path / "demo.slproj"
    resolved_targets = [target] if targets is None else targets
    resolved_analyzers = ["variables"] if analyzers is None else analyzers
    resolved_capacities = capacities or {
        "identstring": 15,
        "tagstring": 30,
        "string": 40,
        "linestring": 80,
        "maxstring": 140,
    }
    project.write_text(
        "\n".join(
            [
                "slproj_version = 2",
                f"analyzed_programs_and_libraries = {json.dumps(resolved_targets)}",
                f"analyzers = {json.dumps(resolved_analyzers)}",
                'mode = "official"',
                f'program_dir = "{program_dir}"',
                'ABB_lib_dir = ""',
                'icf_dir = ""',
                "other_lib_dirs = []",
                "",
                "[string_capacities]",
                *(f"{key} = {value}" for key, value in resolved_capacities.items()),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return project


def _run_record(*findings: AnalysisFinding) -> RunRecord:
    return RunRecord(
        run_id="run-1",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        project_tag="Demo",
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


def _finding(
    *,
    module_path: tuple[str, ...],
    kind: str = "unused",
    message: str = "declared but never read",
    site: str | None = None,
    rule_id: str | None = None,
) -> AnalysisFinding:
    data = {"site": site} if site is not None else {}
    return AnalysisFinding(kind=kind, message=message, module_path=module_path, data=data, rule_id=rule_id)


def _fake_list_runs(*summaries: RunSummary) -> Callable[[], tuple[RunSummary, ...]]:
    def _list_runs() -> tuple[RunSummary, ...]:
        return summaries

    return _list_runs


def _fake_load_run(record: RunRecord | None) -> Callable[[str], RunRecord | None]:
    def _load_run(_run_id: str) -> RunRecord | None:
        return record

    return _load_run


def _fake_collect(result: ChecksRunResult) -> Callable[..., ChecksRunResult]:
    def _collect(*_args: object, **_kwargs: object) -> ChecksRunResult:
        return result

    return _collect


def _no_loaded_projects(_cfg: ConfigDict, **_kwargs: object) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
    return iter(())


def _target_is_not_library(*_args: object) -> bool:
    return False


def _self_check_ok(_cfg: ConfigDict) -> bool:
    return True


def test_build_cli_parser_exposes_headless_commands() -> None:
    parser = build_cli_parser()
    args = parser.parse_args(["analyze", "--format", "json"])
    assert args.command == "analyze"
    assert args.format == "json"
    project_args = parser.parse_args(["project", "show", "--format", "json"])
    assert project_args.command == "project"
    assert project_args.project_command == "show"


def test_cli_version_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        build_cli_parser().parse_args(["--version"])
    assert exc_info.value.code == 0
    assert "sattlint" in capsys.readouterr().out


def test_usage_error_returns_two(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["analyze", "--bogus"])
    assert code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_usage_error_honors_json_format_in_any_position(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["analyze", "--bogus", "--format", "json"])
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "usage_error"

    code = run_cli(["analyze", "--format=json", "--bogus"])
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "usage_error"


def test_analyzers_list_json(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code = run_cli(["analyzers", "list", "--format", "json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    keys = {entry["key"] for entry in payload["analyzers"]}
    assert payload["schema_version"] == 1
    assert {"variables", "dataflow", "icf"} <= keys
    assert all("cli_exposed" not in entry for entry in payload["analyzers"])


def test_project_show_resolves_paths(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    code = run_cli(["project", "show", "--project", str(project), "--format", "json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["project"]["path"] == str(project.resolve())
    assert payload["project"]["slproj_version"] == 2
    assert payload["project"]["targets"] == ["Demo"]
    assert payload["project"]["string_capacities"] == {
        "identstring": 15,
        "tagstring": 30,
        "string": 40,
        "linestring": 80,
        "maxstring": 140,
    }
    assert payload["project"]["paths"]["program_dir"] == str((tmp_path / "programs").resolve())


def test_project_show_reports_the_projects_own_capacity_values(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(
        tmp_path,
        capacities={"identstring": 10, "tagstring": 20, "string": 25, "linestring": 60, "maxstring": 100},
    )

    code = run_cli(["project", "show", "--project", str(project), "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["project"]["string_capacities"] == {
        "identstring": 10,
        "tagstring": 20,
        "string": 25,
        "linestring": 60,
        "maxstring": 100,
    }


def test_project_validate_subcommand_is_gone(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code = run_cli(["project", "validate"])
    assert code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_findings_filters_and_groups(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    record = _run_record(
        _finding(module_path=("Demo", "A"), site="EQ:One"),
        _finding(module_path=("Demo", "A", "Sub"), site="EQ:Two"),
        _finding(module_path=("Demo", "B"), kind="shadowing"),
    )
    summary = RunSummary.from_record(record)
    monkeypatch.setattr("sattlint.cli._findings.list_runs", _fake_list_runs(summary))
    monkeypatch.setattr("sattlint.cli._findings.load_run", _fake_load_run(record))

    code = run_cli(
        [
            "findings",
            "--run",
            "latest",
            "--module",
            "Demo.A",
            "--group-by",
            "module",
            "--format",
            "json",
        ],
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["matched"] == 2
    assert payload["groups"] == [
        {"key": "Demo.A", "group_by": "module", "count": 1, "finding_ids": [payload["findings"][0]["id"]]},
        {
            "key": "Demo.A.Sub",
            "group_by": "module",
            "count": 1,
            "finding_ids": [payload["findings"][1]["id"]],
        },
    ]


def test_show_finding_by_stable_id(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    record = _run_record(_finding(module_path=("Demo", "A")))
    summary = RunSummary.from_record(record)
    finding_id = flat_findings(record)[0].id
    monkeypatch.setattr("sattlint.cli._findings.list_runs", _fake_list_runs(summary))
    monkeypatch.setattr("sattlint.cli._findings.load_run", _fake_load_run(record))

    code = run_cli(["show", finding_id, "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["finding"]["id"] == finding_id
    assert payload["finding"]["module"] == "Demo.A"


def test_show_unknown_finding_returns_two(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    record = _run_record(_finding(module_path=("Demo", "A")))
    summary = RunSummary.from_record(record)
    monkeypatch.setattr("sattlint.cli._findings.list_runs", _fake_list_runs(summary))
    monkeypatch.setattr("sattlint.cli._findings.load_run", _fake_load_run(record))

    code = run_cli(["show", "f_missing", "--format", "json"])

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "finding_not_found"


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


def test_analyze_json_output_and_fail_on(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    result = _checks_result(_finding(module_path=("Demo", "A")))
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(result))

    code = run_cli(
        ["analyze", "--project", str(project), "--format", "json", "--fail-on", "none"],
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "run-analyze"
    assert payload["summary"]["findings"] == 1
    assert payload["findings"][0]["module"] == "Demo.A"

    code = run_cli(
        ["analyze", "--project", str(project), "--format", "json"],
    )
    assert code == 1


def test_analyze_module_filter_can_hide_findings(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    result = _checks_result(_finding(module_path=("Demo", "B")))
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(result))

    code = run_cli(
        ["analyze", "--project", str(project), "--module", "Demo.A", "--format", "json"],
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"] == []
    assert payload["summary"]["total_findings"] == 1


def test_analyze_unknown_analyzer_returns_json_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)

    code = run_cli(
        ["analyze", "--project", str(project), "--analyzer", "not-real", "--format", "json"],
    )

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "unknown_analyzer"


def test_analyze_requires_an_analyzer_selection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path, analyzers=[])
    result = _checks_result(_finding(module_path=("Demo", "A")))
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(result))

    code = run_cli(["analyze", "--project", str(project), "--format", "json"])

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "no_analyzers"
    message = payload["error"]["message"]
    assert "No analyzers selected" in message
    assert "variables" in message
    assert "sfc" in message
    assert "variables" in payload["error"]["details"]["available"]


def test_analyze_uses_the_project_analyzer_list(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path, analyzers=["variables", "sfc"])
    result = _checks_result(_finding(module_path=("Demo", "A")))
    seen: dict[str, object] = {}

    def _collect(_cfg: object, keys: object, **_kwargs: object) -> ChecksRunResult:
        seen["keys"] = keys
        return result

    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _collect)

    code = run_cli(["analyze", "--project", str(project), "--format", "json", "--fail-on", "none"])

    assert code == 0
    assert seen["keys"] == ["variables", "sfc"]
    capsys.readouterr()


def test_analyze_cli_analyzer_overrides_the_project_list(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path, analyzers=["variables", "sfc"])
    result = _checks_result(_finding(module_path=("Demo", "A")))
    seen: dict[str, object] = {}

    def _collect(_cfg: object, keys: object, **_kwargs: object) -> ChecksRunResult:
        seen["keys"] = keys
        return result

    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _collect)

    code = run_cli(
        ["analyze", "--project", str(project), "--analyzer", "dataflow", "--format", "json", "--fail-on", "none"]
    )

    assert code == 0
    assert seen["keys"] == ["dataflow"]
    capsys.readouterr()


def test_analyze_no_cache_keeps_the_parsed_graph(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """``--no-cache`` discards analyzer reports; it must not force a re-parse."""
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    result = _checks_result(_finding(module_path=("Demo", "A")))
    seen: dict[str, object] = {}

    def _collect(_cfg: object, _keys: object, **kwargs: object) -> ChecksRunResult:
        seen.update(kwargs)
        return result

    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _collect)

    code = run_cli(["analyze", "--project", str(project), "--no-cache", "--format", "json", "--fail-on", "none"])

    assert code == 0
    assert seen["use_cache"] is False
    assert seen["refresh_ast"] is False
    capsys.readouterr()


def test_analyze_refresh_ast_rebuilds_the_parsed_graph(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    result = _checks_result(_finding(module_path=("Demo", "A")))
    seen: dict[str, object] = {}

    def _collect(_cfg: object, _keys: object, **kwargs: object) -> ChecksRunResult:
        seen.update(kwargs)
        return result

    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _collect)

    code = run_cli(["analyze", "--project", str(project), "--refresh-ast", "--format", "json", "--fail-on", "none"])

    assert code == 0
    assert seen["refresh_ast"] is True
    assert seen["use_cache"] is True
    capsys.readouterr()


def test_parser_rejects_review_subcommand() -> None:
    with pytest.raises(CliError):
        build_cli_parser().parse_args(["review"])


def test_project_show_text_and_discovery(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    (tmp_path / ".slproj").write_text(project.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = run_cli(["project", "show"])

    assert code == 0
    out = capsys.readouterr().out
    assert "Project:" in out
    assert "Version:   2" in out
    assert "Targets:   Demo" in out
    assert "Analyzers: variables" in out
    assert "String capacities:" in out
    for line in (
        "  identstring: 15",
        "  tagstring: 30",
        "  string: 40",
        "  linestring: 80",
        "  maxstring: 140",
    ):
        assert line in out
    assert "Analysis: (defaults)" in out
    assert "Config:  " in out


def test_project_show_text_marks_a_missing_user_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)

    code = run_cli(["project", "show", "--project", str(project)])

    assert code == 0
    out = capsys.readouterr().out
    assert f"Config:  {tmp_path / 'config.toml'} (missing)" in out


def test_project_show_accepts_directory_and_reports_ambiguous(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    _write_project(tmp_path)

    code = run_cli(["project", "show", "--project", str(tmp_path), "--format", "json"])
    assert code == 0
    capsys.readouterr()

    second = tmp_path / "second.slproj"
    second.write_text((tmp_path / "demo.slproj").read_text(encoding="utf-8"), encoding="utf-8")
    code = run_cli(
        ["project", "show", "--project", str(tmp_path), "--format", "json"],
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "project_ambiguous"


def test_project_show_rejects_a_non_table_analysis(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    project.write_text(project.read_text(encoding="utf-8") + "analysis = 'nope'\n", encoding="utf-8")

    code = run_cli(["project", "show", "--project", str(project), "--format", "json"])

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "project_invalid"
    assert "analysis" in payload["error"]["message"]


def test_project_show_reports_missing_project(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code = run_cli(
        ["project", "show", "--project", str(tmp_path / "absent.slproj"), "--format", "json"],
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "project_not_found"


def test_analyzers_list_text(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code = run_cli(["analyzers", "list"])
    assert code == 0
    out = capsys.readouterr().out
    assert out.startswith("Analyzers (select with --analyzer KEY):\n")
    assert "Key" in out and "Category" in out and "Name" in out
    assert "  variables " in out
    assert "correctness" in out


def test_findings_exact_module_text_ndjson_and_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    record = _run_record(
        _finding(module_path=("Demo", "A")),
        _finding(module_path=("Demo", "A", "Sub")),
    )
    summary = RunSummary.from_record(record)
    monkeypatch.setattr("sattlint.cli._findings.list_runs", _fake_list_runs(summary))
    monkeypatch.setattr("sattlint.cli._findings.load_run", _fake_load_run(record))

    code = run_cli(
        ["findings", "--module", "Demo.A", "--exact-module"],
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Demo.A:" in out
    assert "Demo.A.Sub" not in out

    code = run_cli(["findings", "--format", "ndjson"])
    assert code == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[0]["record_type"] == "envelope"
    assert lines[0]["run"]["run_id"] == record.run_id
    findings = [line for line in lines if line["record_type"] == "finding"]
    assert {line["module"] for line in findings} == {"Demo.A", "Demo.A.Sub"}

    output = tmp_path / "findings.json"
    code = run_cli(
        ["findings", "--limit", "1", "--format", "json", "--output", str(output)],
    )
    assert code == 0
    assert capsys.readouterr().out == ""
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"]["matched"] == 2
    assert payload["summary"]["findings"] == 1


def test_findings_without_runs_returns_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("sattlint.cli._findings.list_runs", _fake_list_runs())
    code = run_cli(["findings", "--format", "json"])
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "no_runs"


def test_show_text_and_markdown(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    record = _run_record(
        _finding(
            module_path=("Demo", "A"),
            message="declared but never read",
            site="EQ:Control",
        )
    )
    summary = RunSummary.from_record(record)
    finding_id = flat_findings(record)[0].id
    monkeypatch.setattr("sattlint.cli._findings.list_runs", _fake_list_runs(summary))
    monkeypatch.setattr("sattlint.cli._findings.load_run", _fake_load_run(record))

    code = run_cli(["show", finding_id])
    assert code == 0
    out = capsys.readouterr().out
    assert "Site:" in out
    assert "Demo.A" in out

    code = run_cli(["show", finding_id, "--format", "markdown"])
    assert code == 0
    out = capsys.readouterr().out
    assert out.startswith("# Unused variable: Demo.A")
    assert "**Finding:**" in out


def test_analyze_text_ndjson_and_cancelled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    result = _checks_result(_finding(module_path=("Demo", "A")))
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(result))

    code = run_cli(
        ["analyze", "--project", str(project), "--format", "text", "--fail-on", "none"],
    )
    assert code == 0
    assert "Findings: 1" in capsys.readouterr().out

    code = run_cli(
        ["analyze", "--project", str(project), "--format", "ndjson", "--fail-on", "none"],
    )
    assert code == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[0]["record_type"] == "envelope"
    assert [line["module"] for line in lines if line["record_type"] == "finding"] == ["Demo.A"]

    cancelled = ChecksRunResult(output_lines=(), targets=(), selected_analyzers=("variables",), cancelled=True)
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(cancelled))
    code = run_cli(["analyze", "--project", str(project)])
    assert code == 130


def test_analyze_preflight_and_no_analyzers_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    preflight = ChecksRunResult(
        output_lines=("self-check failed",),
        targets=(),
        selected_analyzers=("variables",),
    )
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(preflight))
    code = run_cli(
        ["analyze", "--project", str(project), "--format", "json"],
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "analysis_preflight_failed"

    no_analyzers = ChecksRunResult(output_lines=(), targets=(), selected_analyzers=())
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(no_analyzers))
    code = run_cli(
        ["analyze", "--project", str(project), "--format", "json"],
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "no_analyzers"


def test_analyze_target_load_failure_is_not_reported_as_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    result = _checks_result(_finding(module_path=("Demo", "A")))
    failed = ChecksRunResult(
        output_lines=("loader diagnostic",),
        targets=result.targets,
        selected_analyzers=result.selected_analyzers,
        failures=(TargetLoadFailure(target_name="Broken", message="root failed"),),
    )
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(failed))

    code = run_cli(["analyze", "--project", str(project), "--format", "json"])

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "target_load_failed"
    assert payload["error"]["details"] == {"Broken": "root failed"}


def test_analyze_json_failure_stderr_stays_machine_readable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    base = _checks_result(_finding(module_path=("Demo", "A")))
    failed = ChecksRunResult(
        output_lines=("loader diagnostic",),
        targets=base.targets,
        selected_analyzers=base.selected_analyzers,
        failures=(TargetLoadFailure(target_name="Broken", message="root failed"),),
    )

    def collect(*_args: object, **_kwargs: object) -> ChecksRunResult:
        logging.getLogger("SattLint").error("loader traceback detail")
        return failed

    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", collect)

    code = run_cli(["analyze", "--project", str(project), "--format", "json"])

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "target_load_failed"


def test_analyze_unknown_target_returns_json_error(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    code = run_cli(
        ["analyze", "--project", str(project), "--target", "Nope", "--format", "json"],
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "unknown_target"


def test_run_cli_internal_error_is_masked(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def _explode(_args: argparse.Namespace) -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr("sattlint.cli.entry.commands.command_analyzers_list", _explode)

    code = run_cli(["analyzers", "list", "--format", "json"])
    assert code == 3
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "internal_error"
    assert "boom" in payload["error"]["message"]


def test_findings_differing_only_in_data_payload_stay_separate() -> None:
    first = AnalysisFinding(
        kind="read_before_write",
        message="read before write",
        module_path=("Demo", "A"),
        data={"site": "IF Start THEN", "previous": "IF First THEN"},
    )
    second = AnalysisFinding(
        kind="read_before_write",
        message="read before write",
        module_path=("Demo", "A"),
        data={"site": "IF Start THEN", "previous": "IF Second THEN"},
    )

    findings = flat_findings(_run_record(first, second))

    assert len(findings) == 2
    previous = [finding.finding.data["previous"] for finding in findings]
    assert "IF First THEN" in previous
    assert "IF Second THEN" in previous


def test_finding_filters_and_all_groupings() -> None:
    record = _run_record(
        _finding(module_path=("Demo", "A"), kind="unused"),
        _finding(module_path=("Demo", "B"), kind="shadowing"),
        _finding(module_path=("Other", "A"), kind="unused", rule_id="rule-1"),
    )
    findings = flat_findings(record)

    selected = filter_findings(
        findings,
        FindingFilters(
            targets=("Demo",),
            analyzers=("variables",),
            modules=("Demo",),
            kinds=("unused",),
        ),
    )
    assert [finding.module for finding in selected] == ["Demo.A"]

    by_rule = filter_findings(findings, FindingFilters(rules=("rule-1",)))
    assert [finding.module for finding in by_rule] == ["Other.A"]

    # Analyzers rarely set a rule ID, so the filter falls back to the kind.
    by_kind_as_rule = filter_findings(findings, FindingFilters(rules=("unused",)))
    assert [finding.module for finding in by_kind_as_rule] == ["Demo.A"]
    by_kind_mixed = filter_findings(findings, FindingFilters(rules=("rule-1", "shadowing")))
    assert [finding.module for finding in by_kind_mixed] == ["Demo.B", "Other.A"]

    assert group_findings(findings, "none") == []
    assert {group["key"] for group in group_findings(findings, "analyzer")} == {"variables"}
    assert {group["key"] for group in group_findings(findings, "kind")} == {"unused", "shadowing"}


def test_resolve_run_supports_prefix_and_rejects_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _run_record(_finding(module_path=("Demo", "A")))
    summary = RunSummary.from_record(record)
    monkeypatch.setattr("sattlint.cli._findings.list_runs", _fake_list_runs(summary))
    monkeypatch.setattr(
        "sattlint.cli._findings.load_run", _fake_load_run(record if record.run_id.startswith("run-") else None)
    )

    assert resolve_run("run").run_id == "run-1"
    with pytest.raises(CliError) as exc_info:
        resolve_run("missing")
    assert exc_info.value.code == "run_not_found"


def test_collect_run_checks_result_records_saved_run_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    spec = get_selectable_analyzers()[0]
    monkeypatch.setattr(checks_records, "get_runs_dir_or_none", lambda: tmp_path / "runs")
    result = checks_module.collect_run_checks_result(
        cast(ConfigDict, {"analyzed_programs_and_libraries": ["Demo"]}),
        [spec.key],
        use_cache=False,
        persist_run=True,
        iter_loaded_projects_fn=_no_loaded_projects,
        get_enabled_analyzers_fn=lambda: [spec],
        target_is_library_fn=_target_is_not_library,
        self_check_fn=_self_check_ok,
    )

    assert result.run_id is not None
    assert (tmp_path / "runs" / f"{result.run_id}.json").exists()


def test_analyze_reports_analyzer_failures_with_exit_two(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    failed_target = ChecksTargetResult(
        target_name="Demo",
        is_library=False,
        analyzers=(
            ChecksAnalyzerResult(
                key="variables",
                name="Variable issues",
                status="failed",
                summary="Variable issues failed: boom",
            ),
        ),
    )
    failed_per_run = ChecksTargetResult(
        target_name="ICF configuration",
        is_library=False,
        analyzers=(
            ChecksAnalyzerResult(
                key="icf",
                name="ICF configuration",
                status="failed",
                summary="ICF configuration failed: boom",
            ),
        ),
        is_pseudo=True,
    )
    result = ChecksRunResult(
        output_lines=("Analyzing Demo: Variable issues (variables)",),
        targets=(failed_target, failed_per_run),
        selected_analyzers=("variables", "icf"),
    )
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(result))

    code = run_cli(["analyze", "--project", str(project), "--format", "json", "--fail-on", "none"])

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "analyzer_failed"
    assert payload["error"]["details"] == {
        "Variable issues": "Variable issues failed: boom",
        "ICF configuration": "ICF configuration failed: boom",
    }


def test_analyze_analyzer_failure_text_mode_writes_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    result = ChecksRunResult(
        output_lines=("Analyzing Demo: Variable issues (variables)", "Variable issues failed: boom"),
        targets=(
            ChecksTargetResult(
                target_name="Demo",
                is_library=False,
                analyzers=(
                    ChecksAnalyzerResult(
                        key="variables",
                        name="Variable issues",
                        status="failed",
                        summary="Variable issues failed: boom",
                    ),
                ),
            ),
        ),
        selected_analyzers=("variables",),
    )
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(result))

    code = run_cli(["analyze", "--project", str(project), "--fail-on", "none"])

    assert code == 2
    err = capsys.readouterr().err
    assert "Variable issues failed: boom" in err
    assert "1 analyzer(s) failed: Variable issues" in err


def test_analyze_without_configured_targets_fails_preflight_without_running(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path, targets=[])

    def _fail_start(*_args: object, **_kwargs: object) -> ChecksRunResult:
        pytest.fail("analysis must not start without targets")

    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fail_start)

    code = run_cli(["analyze", "--project", str(project), "--format", "json"])

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "no_targets"
    assert payload["error"]["message"] == "No analysis targets are configured."


def test_analyze_self_check_failure_names_the_preflight(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    preflight = ChecksRunResult(
        output_lines=("❌ Self-check failed. Analysis aborted before the checks pipeline started.",),
        targets=(),
        selected_analyzers=("variables",),
    )
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(preflight))

    code = run_cli(["analyze", "--project", str(project), "--format", "text"])

    assert code == 2
    err = capsys.readouterr().err
    assert "Self-check failed" in err
    assert "Analysis aborted before the checks pipeline started" in err
    assert "['" not in err


def test_analyze_summary_counts_only_loaded_targets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    result = ChecksRunResult(
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
                        findings=(),
                    ),
                ),
            ),
            ChecksTargetResult(
                target_name="ICF configuration",
                is_library=False,
                analyzers=(
                    ChecksAnalyzerResult(
                        key="icf",
                        name="ICF configuration",
                        status="completed",
                        findings=(),
                    ),
                ),
                is_pseudo=True,
            ),
        ),
        selected_analyzers=("variables", "icf"),
    )
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(result))

    code = run_cli(["analyze", "--project", str(project), "--format", "json", "--fail-on", "none"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["targets"] == 1


def test_emit_text_survives_a_non_utf8_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    class _AsciiStream:
        encoding = "ascii"

        def __init__(self) -> None:
            self.buffer = io.BytesIO()

        def write(self, text: str) -> int:
            raise UnicodeEncodeError("ascii", text, 0, len(text), "ordinal not in range(128)")

        def flush(self) -> None:
            return None

    stream = _AsciiStream()
    monkeypatch.setattr(sys, "stdout", stream)

    output_module.emit_text(["café"])

    assert stream.buffer.getvalue().decode("utf-8") == "café\n"


def test_emit_ndjson_streams_each_record_before_the_next_is_produced(monkeypatch: pytest.MonkeyPatch) -> None:
    writes: list[str] = []

    class _Stream:
        def write(self, text: str) -> int:
            writes.append(text)
            return len(text)

        def flush(self) -> None:
            return None

    def records() -> Iterator[dict[str, object]]:
        yield {"record": 1}
        assert writes == ['{"record":1}\n']
        yield {"record": 2}

    monkeypatch.setattr(sys, "stdout", _Stream())

    output_module.emit_ndjson(records())

    assert writes == ['{"record":1}\n', '{"record":2}\n']


def test_json_error_envelope_uses_the_document_formatting(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["analyze", "--format", "json", "--bogus"])

    assert code == 2
    err = capsys.readouterr().err
    assert err == json.dumps(json.loads(err), indent=2, ensure_ascii=False) + "\n"


def test_project_payload_reports_paths_without_creating_them(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    blocked_cache = tmp_path / "blocked-cache"
    blocked_cache.write_text("not a directory", encoding="utf-8")
    blocked_config = tmp_path / "blocked-config"
    blocked_config.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("XDG_CACHE_HOME", str(blocked_cache))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(blocked_config))
    monkeypatch.setattr(cache_module, "cache_dir_location", _REAL_CACHE_DIR_LOCATION)

    project = load_project(_write_project(tmp_path))
    payload = project_payload(project)

    assert payload["cache_dir"] == str(blocked_cache / "sattlint")
    assert payload["runs_dir"] == str(blocked_cache / "sattlint" / "runs")
    assert payload["review_output_dir"] == str(blocked_config / "sattlint" / "change-review")
    assert payload["config"]["exists"] is False
    assert payload["string_capacities"]["string"] == 40


def test_analyze_all_targets_failed_is_a_load_failure_not_a_preflight_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    failed = ChecksRunResult(
        output_lines=("loader diagnostic",),
        targets=(),
        selected_analyzers=("variables",),
        failures=(TargetLoadFailure(target_name="Demo", message="root failed"),),
    )
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(failed))

    code = run_cli(["analyze", "--project", str(project), "--format", "json"])

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "target_load_failed"


def test_resolve_run_latest_falls_back_to_a_readable_record(monkeypatch: pytest.MonkeyPatch) -> None:
    summaries = [
        RunSummary.from_record(RunRecord(run_id=run_id, started_at="s", finished_at="f", project_tag="p"))
        for run_id in ("newest", "older")
    ]
    monkeypatch.setattr(findings_module, "list_runs", lambda: tuple(summaries))

    def _load(run_id: str) -> RunRecord | None:
        if run_id == "newest":
            return None
        return RunRecord(run_id=run_id, started_at="s", finished_at="f", project_tag="p")

    monkeypatch.setattr(findings_module, "load_run", _load)

    record = resolve_run("latest")

    assert record.run_id == "older"


def test_resolve_run_reports_ambiguous_prefix_and_rejects_an_empty_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summaries = [
        RunSummary.from_record(RunRecord(run_id=run_id, started_at="s", finished_at="f", project_tag="p"))
        for run_id in ("abc1", "abc2")
    ]
    monkeypatch.setattr(findings_module, "list_runs", lambda: tuple(summaries))

    with pytest.raises(CliError) as ambiguous:
        resolve_run("abc")
    assert ambiguous.value.code == "run_ambiguous"

    with pytest.raises(CliError) as empty:
        resolve_run("   ")
    assert empty.value.code == "run_invalid"


def test_resolve_run_latest_prefers_the_current_project(monkeypatch: pytest.MonkeyPatch) -> None:
    summaries = [
        RunSummary.from_record(
            RunRecord(run_id="other", started_at="s", finished_at="f", project_tag="p", project_path="/p/other.slproj")
        ),
        RunSummary.from_record(
            RunRecord(run_id="mine", started_at="s", finished_at="f", project_tag="p", project_path="/p/mine.slproj")
        ),
    ]
    monkeypatch.setattr(findings_module, "list_runs", lambda: tuple(summaries))

    def _load(run_id: str) -> RunRecord:
        return RunRecord(
            run_id=run_id, started_at="s", finished_at="f", project_tag="p", project_path=f"/p/{run_id}.slproj"
        )

    monkeypatch.setattr(findings_module, "load_run", _load)

    assert resolve_run("latest", project_path="/p/mine.slproj").run_id == "mine"
    assert resolve_run("latest").run_id == "other"


def test_resolve_run_latest_rejects_a_project_with_no_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    summaries = [
        RunSummary.from_record(
            RunRecord(run_id="other", started_at="s", finished_at="f", project_tag="p", project_path="/p/other.slproj")
        )
    ]
    monkeypatch.setattr(findings_module, "list_runs", lambda: tuple(summaries))

    with pytest.raises(CliError) as error:
        resolve_run("latest", project_path="/p/mine.slproj")

    assert error.value.code == "no_runs_for_project"


def test_analyze_output_write_failure_is_a_user_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    monkeypatch.setattr(
        "sattlint.cli.commands.collect_checks_result",
        _fake_collect(_checks_result(_finding(module_path=("Demo", "A")))),
    )
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")

    code = run_cli(
        ["analyze", "--project", str(project), "--format", "json", "--output", str(blocked / "out.json")],
    )

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "output_write_failed"


def test_analyze_failure_removes_a_stale_output_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    artifact = tmp_path / "findings.json"
    artifact.write_text('{"stale": true}', encoding="utf-8")
    failed = ChecksRunResult(
        output_lines=(),
        targets=(),
        selected_analyzers=("variables",),
        failures=(TargetLoadFailure(target_name="Demo", message="boom"),),
    )
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", _fake_collect(failed))

    code = run_cli(["analyze", "--project", str(project), "--format", "json", "--output", str(artifact)])

    assert code == 2
    assert not artifact.exists()


def test_findings_grouped_text_uses_human_labels(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    record = _run_record(_finding(module_path=("Demo", "A"), kind="unused"))
    summary = RunSummary.from_record(record)
    monkeypatch.setattr("sattlint.cli._findings.list_runs", _fake_list_runs(summary))
    monkeypatch.setattr("sattlint.cli._findings.load_run", _fake_load_run(record))

    code = run_cli(["findings", "--group-by", "kind"])

    assert code == 0
    out = capsys.readouterr().out
    assert "Unused variable (1)" in out
    assert "unused (1)" not in out


def test_closed_pipe_exits_141(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Sink:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    def _broken(_args: argparse.Namespace) -> int:
        raise BrokenPipeError

    sink = _Sink()
    monkeypatch.setattr(sys, "stdout", sink)
    monkeypatch.setattr(entry_module, "_dispatch_analyzers", _broken)

    assert run_cli(["analyzers", "list"]) == 141
    assert sink.closed is True


def test_project_show_quiet_suppresses_config_warnings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text('program_dirr = "typo"\n', encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_dir))

    code = run_cli(["project", "show", "--project", str(project), "--quiet"])

    assert code == 0
    assert "Config warning" not in capsys.readouterr().err


def test_project_analyzer_findings_survive_without_a_phantom_target() -> None:
    record = RunRecord(
        run_id="r1",
        started_at="s",
        finished_at="f",
        project_tag="Demo",
        project_analyzers=(
            RunAnalyzerRecord(
                key="icf",
                name="ICF configuration",
                status="completed",
                findings=(AnalysisFinding(kind="icf_drift", message="drift", module_path=("Demo",)),),
            ),
        ),
    )

    flat = flat_findings(record)

    assert [finding.analyzer_key for finding in flat] == ["icf"]
    assert [finding.target for finding in flat] == [""]
    assert record.targets == ()
    assert record.issue_count == 1


def test_findings_rejects_a_blank_module_filter(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["findings", "--module", ""])

    assert code == 2
    assert "--module must not be empty." in capsys.readouterr().err


def test_analyze_rejects_a_blank_filter_value(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["analyze", "--target", "  "])

    assert code == 2
    assert "--target must not be empty." in capsys.readouterr().err


def test_findings_rejects_a_negative_limit(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["findings", "--limit", "-3"])

    assert code == 2
    assert "must be zero or greater" in capsys.readouterr().err


def test_exact_module_requires_a_module_filter(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["findings", "--exact-module"])

    assert code == 2
    assert "--exact-module requires --module." in capsys.readouterr().err


def test_blank_project_value_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["project", "show", "--project", ""])

    assert code == 2
    assert "--project must not be empty." in capsys.readouterr().err


def test_repeated_format_flag_uses_the_last_value(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["analyzers", "list", "--format", "json", "--format", "text"])

    assert code == 0
    out = capsys.readouterr().out
    assert not out.lstrip().startswith("{")
    assert "Variable issues" in out


def test_usage_error_fallback_uses_the_last_format_flag(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["analyze", "--format", "json", "--format", "text", "--bogus"])

    assert code == 2
    assert capsys.readouterr().err.startswith("sattlint: ")


def test_analyze_progress_flag_is_parsed() -> None:
    args = build_cli_parser().parse_args(["analyze", "--progress", "--analyzer", "variables"])

    assert args.progress is True


def test_analyze_progress_writer_emits_a_parseable_record(
    capsys: pytest.CaptureFixture[str],
) -> None:
    writer = commands_module.stderr_progress_writer()
    writer(
        AnalysisProgressEvent(
            phase=ProgressPhase.LOADING,
            target_total=2,
            target_index=1,
            target_name="Demo",
        )
    )

    captured = capsys.readouterr()
    event = parse_progress_line(captured.err.strip())

    assert captured.out == ""
    assert event is not None
    assert (event.phase, event.target_index, event.target_total, event.target_name) == (
        ProgressPhase.LOADING,
        1,
        2,
        "Demo",
    )
