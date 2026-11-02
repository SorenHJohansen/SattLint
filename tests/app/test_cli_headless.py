# pyright: reportPrivateUsage=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportArgumentType=false, reportIndexIssue=false
"""Headless CLI command tests (project, analyzers, analyze, findings, show)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sattlint.analyzers.catalog import get_default_cli_analyzers
from sattlint.application import checks as checks_module
from sattlint.application.checks import ChecksAnalyzerResult, ChecksRunResult, ChecksTargetResult
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
from sattlint.runs import RunAnalyzerRecord, RunRecord, RunSummary, RunTargetRecord

pytestmark = pytest.mark.unit


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


def _run_record(*findings: Any) -> RunRecord:
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
) -> Any:
    data = {"site": site} if site is not None else {}
    return AnalysisFinding(kind=kind, message=message, module_path=module_path, data=data, rule_id=rule_id)


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


def test_usage_error_returns_two(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code = run_cli(["analyze", "--bogus"], config_path=tmp_path / "config.toml")
    assert code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_analyzers_list_json(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code = run_cli(["analyzers", "list", "--format", "json"], config_path=tmp_path / "config.toml")
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    keys = {entry["key"] for entry in payload["analyzers"]}
    assert payload["schema_version"] == 1
    assert {"variables", "dataflow", "icf"} <= keys
    assert all("default" in entry for entry in payload["analyzers"])


def test_project_show_resolves_paths(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    code = run_cli(
        ["project", "show", "--project", str(project), "--format", "json"], config_path=tmp_path / "config.toml"
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["project"]["path"] == str(project.resolve())
    assert payload["project"]["targets"] == ["Demo"]
    assert payload["project"]["paths"]["program_dir"] == str((tmp_path / "programs").resolve())


def test_project_validate_reports_errors(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    project = _write_project(tmp_path, program_dir="missing")
    code = run_cli(
        ["project", "validate", "--project", str(project), "--format", "json"],
        config_path=tmp_path / "config.toml",
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    messages = " ".join(error["message"] for error in payload["errors"])
    assert "program_dir" in messages
    assert "Demo" in messages


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
    monkeypatch.setattr("sattlint.cli._findings.list_runs", lambda: (summary,))
    monkeypatch.setattr("sattlint.cli._findings.load_run", lambda _run_id: record)

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
        config_path=tmp_path / "config.toml",
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
    monkeypatch.setattr("sattlint.cli._findings.list_runs", lambda: (summary,))
    monkeypatch.setattr("sattlint.cli._findings.load_run", lambda _run_id: record)

    code = run_cli(["show", finding_id, "--format", "json"], config_path=tmp_path / "config.toml")

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
    monkeypatch.setattr("sattlint.cli._findings.list_runs", lambda: (summary,))
    monkeypatch.setattr("sattlint.cli._findings.load_run", lambda _run_id: record)

    code = run_cli(["show", "f_missing", "--format", "json"], config_path=tmp_path / "config.toml")

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "finding_not_found"


def _checks_result(*findings: Any) -> ChecksRunResult:
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
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", lambda *_args, **_kwargs: result)

    code = run_cli(
        ["analyze", "--project", str(project), "--format", "json", "--fail-on", "none"],
        config_path=tmp_path / "config.toml",
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "run-analyze"
    assert payload["summary"]["findings"] == 1
    assert payload["findings"][0]["module"] == "Demo.A"

    code = run_cli(
        ["analyze", "--project", str(project), "--format", "json"],
        config_path=tmp_path / "config.toml",
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
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", lambda *_args, **_kwargs: result)

    code = run_cli(
        ["analyze", "--project", str(project), "--module", "Demo.A", "--format", "json"],
        config_path=tmp_path / "config.toml",
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
        config_path=tmp_path / "config.toml",
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

    code = run_cli(["project", "show"], config_path=tmp_path / "config.toml")

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

    code = run_cli(
        ["project", "show", "--project", str(tmp_path), "--format", "json"], config_path=tmp_path / "config.toml"
    )
    assert code == 0
    capsys.readouterr()

    second = tmp_path / "second.slproj"
    second.write_text((tmp_path / "demo.slproj").read_text(encoding="utf-8"), encoding="utf-8")
    code = run_cli(
        ["project", "show", "--project", str(tmp_path), "--format", "json"],
        config_path=tmp_path / "config.toml",
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "project_ambiguous"


def test_project_show_reports_missing_project(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code = run_cli(
        ["project", "show", "--project", str(tmp_path / "absent.slproj"), "--format", "json"],
        config_path=tmp_path / "config.toml",
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "project_not_found"


def test_analyzers_list_text(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code = run_cli(["analyzers", "list"], config_path=tmp_path / "config.toml")
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
    monkeypatch.setattr("sattlint.cli._findings.list_runs", lambda: (summary,))
    monkeypatch.setattr("sattlint.cli._findings.load_run", lambda _run_id: record)

    code = run_cli(
        ["findings", "--module", "Demo.A", "--exact-module"],
        config_path=tmp_path / "config.toml",
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Demo.A:" in out
    assert "Demo.A.Sub" not in out

    code = run_cli(["findings", "--format", "ndjson"], config_path=tmp_path / "config.toml")
    assert code == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(lines) == 2
    assert {line["module"] for line in lines} == {"Demo.A", "Demo.A.Sub"}

    output = tmp_path / "findings.json"
    code = run_cli(
        ["findings", "--limit", "1", "--format", "json", "--output", str(output)],
        config_path=tmp_path / "config.toml",
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
    monkeypatch.setattr("sattlint.cli._findings.list_runs", lambda: ())
    code = run_cli(["findings", "--format", "json"], config_path=tmp_path / "config.toml")
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
    monkeypatch.setattr("sattlint.cli._findings.list_runs", lambda: (summary,))
    monkeypatch.setattr("sattlint.cli._findings.load_run", lambda _run_id: record)

    code = run_cli(["show", finding_id], config_path=tmp_path / "config.toml")
    assert code == 0
    out = capsys.readouterr().out
    assert "Site:" in out
    assert "Demo.A" in out

    code = run_cli(["show", finding_id, "--format", "markdown"], config_path=tmp_path / "config.toml")
    assert code == 0
    out = capsys.readouterr().out
    assert out.startswith("# unused: Demo.A")
    assert "**Finding:**" in out


def test_analyze_text_ndjson_and_cancelled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    result = _checks_result(_finding(module_path=("Demo", "A")))
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", lambda *_args, **_kwargs: result)

    code = run_cli(
        ["analyze", "--project", str(project), "--format", "text", "--fail-on", "none"],
        config_path=tmp_path / "config.toml",
    )
    assert code == 0
    assert "Findings: 1" in capsys.readouterr().out

    code = run_cli(
        ["analyze", "--project", str(project), "--format", "ndjson", "--fail-on", "none"],
        config_path=tmp_path / "config.toml",
    )
    assert code == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [line["module"] for line in lines] == ["Demo.A"]

    cancelled = ChecksRunResult(output_lines=(), targets=(), selected_analyzers=("variables",), cancelled=True)
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", lambda *_args, **_kwargs: cancelled)
    code = run_cli(["analyze", "--project", str(project)], config_path=tmp_path / "config.toml")
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
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", lambda *_args, **_kwargs: preflight)
    code = run_cli(
        ["analyze", "--project", str(project), "--format", "json"],
        config_path=tmp_path / "config.toml",
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "analysis_preflight_failed"

    no_analyzers = ChecksRunResult(output_lines=(), targets=(), selected_analyzers=())
    monkeypatch.setattr("sattlint.cli.commands.collect_checks_result", lambda *_args, **_kwargs: no_analyzers)
    code = run_cli(
        ["analyze", "--project", str(project), "--format", "json"],
        config_path=tmp_path / "config.toml",
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "no_analyzers"


def test_analyze_unknown_target_returns_json_error(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path)
    code = run_cli(
        ["analyze", "--project", str(project), "--target", "Nope", "--format", "json"],
        config_path=tmp_path / "config.toml",
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "unknown_target"


def test_run_cli_internal_error_is_masked(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    def _explode(_args: Any) -> int:
        raise RuntimeError("boom")

    code = run_cli(
        ["analyzers", "list", "--format", "json"],
        config_path=tmp_path / "config.toml",
        command_handlers={"analyzers": _explode},
    )
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
    monkeypatch.setattr("sattlint.cli._findings.list_runs", lambda: (summary,))
    monkeypatch.setattr("sattlint.cli._findings.load_run", lambda run_id: record if run_id.startswith("run-") else None)

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
        {"analyzed_programs_and_libraries": ["Demo"]},
        [spec.key],
        use_cache=False,
        persist_run=True,
        iter_loaded_projects_fn=lambda _cfg: iter(()),
        get_enabled_analyzers_fn=lambda: [spec],
        target_is_library_fn=lambda *_args: False,
        self_check_fn=lambda _cfg: True,
    )

    assert result.run_id is not None
    assert (tmp_path / "runs" / f"{result.run_id}.json").exists()


def test_project_validate_reports_optional_directory_errors(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = tmp_path / "demo.slproj"
    project.write_text(
        "\n".join(
            [
                "slproj_version = 1",
                'analyzed_programs_and_libraries = ["Demo"]',
                'mode = "draft"',
                'program_dir = "programs"',
                'ABB_lib_dir = ""',
                'icf_dir = ""',
                'other_lib_dirs = ["missing-lib"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "programs" / "Demo.s").write_text("", encoding="utf-8")

    code = run_cli(
        ["project", "validate", "--project", str(project), "--format", "json"],
        config_path=tmp_path / "config.toml",
    )

    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    key_paths = {error["key_path"] for error in payload["errors"]}
    assert "other_lib_dirs[0]" in key_paths
