# pyright: reportPrivateUsage=false
"""Headless CLI command tests (project, analyzers, analyze, findings, show)."""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast

import pytest
from sattline_parser.models.ast_model import BasePicture

from sattlint.analyzers.catalog import get_default_cli_analyzers
from sattlint.application import checks as checks_module
from sattlint.application.checks import (
    ChecksAnalyzerResult,
    ChecksRunResult,
    ChecksTargetResult,
    TargetLoadFailure,
)
from sattlint.application.findings import AnalysisFinding
from sattlint.cli._findings import (
    FindingFilters,
    filter_findings,
    flat_findings,
    group_findings,
    resolve_run,
)
from sattlint.cli._output import CliError
from sattlint.cli.entry import build_cli_parser, run_cli
from sattlint.config.types import ConfigDict
from sattlint.models.project_graph import ProjectGraph
from sattlint.runs import RunAnalyzerRecord, RunRecord, RunSummary, RunTargetRecord

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _isolate_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sattlint.cli._project.get_config_path", lambda: tmp_path / "config.toml")


def _write_project(tmp_path: Path, *, target: str = "Demo", program_dir: str = "programs") -> Path:
    project = tmp_path / "demo.slproj"
    project.write_text(
        "\n".join(
            [
                "slproj_version = 1",
                f'analyzed_programs_and_libraries = ["{target}"]',
                'mode = "official"',
                f'program_dir = "{program_dir}"',
                'ABB_lib_dir = ""',
                'icf_dir = ""',
                "other_lib_dirs = []",
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
    assert all("default" in entry for entry in payload["analyzers"])


def test_project_show_resolves_paths(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    code = run_cli(["project", "show", "--project", str(project), "--format", "json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["project"]["path"] == str(project.resolve())
    assert payload["project"]["targets"] == ["Demo"]
    assert payload["project"]["paths"]["program_dir"] == str((tmp_path / "programs").resolve())


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
    assert "Targets: Demo" in out


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
    assert "* variables" in out
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
    assert len(lines) == 2
    assert {line["module"] for line in lines} == {"Demo.A", "Demo.A.Sub"}

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
    assert [line["module"] for line in lines] == ["Demo.A"]

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
    spec = get_default_cli_analyzers()[0]
    monkeypatch.setattr(checks_module, "get_runs_dir", lambda: tmp_path / "runs")
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
