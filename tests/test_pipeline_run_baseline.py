# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false
import json

from sattlint.devtools import pipeline

from .test_pipeline_run import _patched_run_command


def test_run_pipeline_baseline_drift_status_skipped_without_baseline(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(pipeline, "_run_command", _patched_run_command)
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0}, "testcases": []},
    )

    summary = pipeline._run_pipeline(tmp_path, trace_target=None, profile="quick")

    assert summary["status"]["tool_statuses"]["baseline_drift"]["status"] == "skipped"
    assert summary["status"]["overall_status"] == "pass"


def test_run_pipeline_fail_on_drift_passes_when_no_new_findings(monkeypatch, tmp_path):
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps({"kind": "sattlint.findings", "schema_version": 1, "finding_count": 0, "findings": []}),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(pipeline, "_run_command", _patched_run_command)
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0}, "testcases": []},
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="quick",
        baseline_findings=baseline_path,
        fail_on_drift=True,
    )

    assert summary["status"]["tool_statuses"]["baseline_drift"]["status"] == "pass"
    assert summary["status"]["overall_status"] == "pass"


def test_run_pipeline_fail_on_drift_fails_when_new_findings_present(monkeypatch, tmp_path):
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps({"kind": "sattlint.findings", "schema_version": 1, "finding_count": 0, "findings": []}),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(
        pipeline,
        "_run_command",
        lambda name, command, cwd=pipeline.REPO_ROOT: pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=1 if name == "pytest" else 0,
            duration_seconds=0.0,
            stdout="[]" if name == "ruff" else "",
            stderr="",
        ),
    )
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0}, "testcases": []},
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="quick",
        baseline_findings=baseline_path,
        fail_on_drift=True,
    )

    assert summary["status"]["tool_statuses"]["baseline_drift"]["status"] == "fail"
    assert "baseline_drift" in summary["status"]["failing_tools"]
    assert summary["status"]["overall_status"] == "fail"
    assert summary["counts"]["baseline_new_findings"] > 0


def test_run_pipeline_fail_on_drift_false_does_not_fail_on_new_findings(monkeypatch, tmp_path):
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps({"kind": "sattlint.findings", "schema_version": 1, "finding_count": 0, "findings": []}),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(
        pipeline,
        "_run_command",
        lambda name, command, cwd=pipeline.REPO_ROOT: pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=1 if name == "pytest" else 0,
            duration_seconds=0.0,
            stdout="[]" if name == "ruff" else "",
            stderr="",
        ),
    )
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0}, "testcases": []},
    )

    summary = pipeline._run_pipeline(
        tmp_path,
        trace_target=None,
        profile="quick",
        baseline_findings=baseline_path,
        fail_on_drift=False,
    )

    assert summary["status"]["tool_statuses"]["baseline_drift"]["status"] == "pass"
    assert "baseline_drift" not in summary["status"]["failing_tools"]


def test_main_save_baseline_copies_findings_json(monkeypatch, tmp_path):
    baseline_dest = tmp_path / "saved" / "baseline.json"

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(pipeline, "_run_command", _patched_run_command)
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0}, "testcases": []},
    )

    exit_code = pipeline.main(
        [
            "--output-dir",
            str(tmp_path),
            "--profile",
            "quick",
            "--save-baseline",
            str(baseline_dest),
        ]
    )

    assert exit_code == 0
    assert baseline_dest.exists()
    saved = json.loads(baseline_dest.read_text(encoding="utf-8"))
    assert saved["kind"] == "sattlint.findings"


def test_main_fail_on_drift_exits_nonzero_when_new_findings(monkeypatch, tmp_path):
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps({"kind": "sattlint.findings", "schema_version": 1, "finding_count": 0, "findings": []}),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "_collect_environment_report", lambda: {"python": {"executable": "python"}})
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(
        pipeline,
        "_run_command",
        lambda name, command, cwd=pipeline.REPO_ROOT: pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=1 if name == "pytest" else 0,
            duration_seconds=0.0,
            stdout="[]" if name == "ruff" else "",
            stderr="",
        ),
    )
    monkeypatch.setattr(pipeline, "_parse_json_lines", lambda raw_output: [])
    monkeypatch.setattr(
        pipeline,
        "_parse_pytest_junit",
        lambda xml_path: {"summary": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0}, "testcases": []},
    )

    exit_code = pipeline.main(
        [
            "--output-dir",
            str(tmp_path),
            "--profile",
            "quick",
            "--baseline-findings",
            str(baseline_path),
            "--fail-on-drift",
        ]
    )

    assert exit_code == 1
