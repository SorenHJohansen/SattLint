import json

import pytest

from sattlint.devtools import observability, review_tool


def test_observability_run_command_handles_exception(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(observability.subprocess, "run", _boom)

    code, stdout, stderr = observability.run_command(["python", "-V"])

    assert code == 1
    assert stdout == ""
    assert "boom" in stderr


def test_observability_get_coverage_metrics_parses_xml(tmp_path, monkeypatch):
    monkeypatch.setattr(observability, "ARTIFACTS_DIR", tmp_path)
    coverage_xml = tmp_path / "coverage.xml"
    coverage_xml.write_text('<coverage line-rate="0.25" branch-rate="0.5" />', encoding="utf-8")

    metrics = observability.get_coverage_metrics()

    assert metrics == {"line_coverage": 25.0, "branch_coverage": 50.0}


def test_observability_get_lint_metrics_counts_warning_and_error(monkeypatch):
    calls = []

    def _fake_run_command(cmd):
        calls.append(cmd)
        if "--fix" in cmd:
            return 0, "", ""
        return 1, "src/demo.py:1:1 warning\nsrc/demo.py:2:1 error\n", ""

    monkeypatch.setattr(observability, "run_command", _fake_run_command)

    metrics = observability.get_lint_metrics()

    assert metrics["ruff_warnings"] == 1
    assert metrics["ruff_errors"] == 1
    assert metrics["ruff_fixable"] == 0
    assert len(calls) == 2


def test_observability_write_and_read_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(observability, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(observability, "OBSERVABILITY_FILE", tmp_path / "observability.json")
    payload = {"coverage": {"line_coverage": 12.5}}

    observability.write_metrics(payload)

    loaded = observability.read_metrics()
    assert loaded == payload


def test_observability_main_writes_and_prints(monkeypatch, capsys):
    payload = {
        "coverage": {"line_coverage": 88.1, "branch_coverage": 77.2},
        "lint": {"ruff_warnings": 2, "ruff_errors": 1},
        "build": {},
        "test": {},
        "timestamp": "now",
    }
    captured = {}
    monkeypatch.setattr(observability, "collect_all_metrics", lambda: payload)
    monkeypatch.setattr(observability, "write_metrics", lambda metrics: captured.setdefault("metrics", metrics))

    exit_code = observability.main()

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert captured["metrics"] == payload
    assert "Line coverage: 88.1%" in stdout
    assert "Lint errors: 1" in stdout


def test_review_tool_run_architecture_lint_parses_violation_count(monkeypatch):
    monkeypatch.setattr(
        review_tool,
        "run_command",
        lambda *_args, **_kwargs: (1, "Found 3 architecture violations:\n", ""),
    )

    result = review_tool.run_architecture_lint()

    assert result["passed"] is False
    assert result["violations"] == 3


def test_review_tool_doc_gardener_exception_is_reported(monkeypatch):
    monkeypatch.setattr(review_tool, "doc_gardener_scan", lambda: (_ for _ in ()).throw(RuntimeError("scan failed")))

    result = review_tool.run_doc_gardener()

    assert result["passed"] is False
    assert "scan failed" in result["error"]


def test_review_tool_run_tests_and_linting_parse_summary(monkeypatch):
    sequence = [
        (1, "5 passed, 2 failed, 3 skipped in 0.12s", ""),
        (1, "src/demo.py:1:1 warning\nsrc/demo.py:2:1 error\n", ""),
    ]

    def _next_result(*_args, **_kwargs):
        return sequence.pop(0)

    monkeypatch.setattr(review_tool, "run_command", _next_result)

    tests_result = review_tool.run_tests()
    lint_result = review_tool.run_linting()

    assert tests_result["passed"] is False
    assert tests_result["failed"] == 2
    assert tests_result["skipped"] == 3
    assert lint_result["warnings"] == 1
    assert lint_result["errors"] == 1


def test_review_tool_run_full_review_writes_report(tmp_path, monkeypatch):
    monkeypatch.setattr(review_tool, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(review_tool, "REVIEW_FILE", tmp_path / "review_report.json")
    monkeypatch.setattr(review_tool, "run_architecture_lint", lambda: {"passed": True, "violations": 0})
    monkeypatch.setattr(
        review_tool,
        "run_doc_gardener",
        lambda: {"passed": True, "findings": 0, "by_severity": {}, "by_category": {}},
    )
    monkeypatch.setattr(review_tool, "run_tests", lambda: {"passed": True, "failed": 0, "skipped": 0})
    monkeypatch.setattr(review_tool, "run_linting", lambda: {"passed": True, "warnings": 0, "errors": 0})
    monkeypatch.setattr(review_tool, "run_format_check", lambda: {"passed": True})
    monkeypatch.setattr(review_tool, "collect_observability", lambda: {"coverage": {"line_coverage": 99.0}})

    report = review_tool.run_full_review()

    assert report["overall_passed"] is True
    assert report["summary"]["tests_failed"] == 0
    assert (tmp_path / "review_report.json").exists()
    disk_report = json.loads((tmp_path / "review_report.json").read_text(encoding="utf-8"))
    assert disk_report["overall_passed"] is True


def test_review_tool_print_review_and_main_exit(monkeypatch, capsys):
    report = {
        "timestamp": "now",
        "overall_passed": False,
        "checks": {
            "architecture": {"passed": False, "violations": 2},
            "documentation": {"passed": True, "findings": 0, "by_severity": {}},
            "tests": {"passed": False, "failed": 1, "skipped": 0},
            "linting": {"passed": True, "warnings": 0, "errors": 0},
            "formatting": {"passed": True},
            "observability": {"coverage": {"line_coverage": 90.0, "branch_coverage": 80.0}},
        },
        "summary": {
            "architecture_violations": 2,
            "doc_findings": 0,
            "tests_passed": False,
            "tests_failed": 1,
            "lint_warnings": 0,
            "lint_errors": 0,
            "format_passed": True,
        },
    }

    review_tool.print_review(report)
    stdout = capsys.readouterr().out
    assert "AGENT REVIEW REPORT" in stdout
    assert "Overall Status: FAIL" in stdout

    monkeypatch.setattr(review_tool, "run_full_review", lambda: report)

    with pytest.raises(SystemExit) as exc:
        review_tool.main()

    assert exc.value.code == 1
