import builtins
import json
import runpy
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from sattlint.devtools import observability, review_tool


def test_observability_run_command_success(monkeypatch):
    monkeypatch.setattr(
        observability.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )

    code, stdout, stderr = observability.run_command(["python", "-V"])

    assert (code, stdout, stderr) == (0, "ok", "")


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


def test_observability_get_coverage_metrics_defaults_when_missing_root_or_parse_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(observability, "ARTIFACTS_DIR", tmp_path)
    assert observability.get_coverage_metrics() == {"line_coverage": 0.0, "branch_coverage": 0.0}

    coverage_xml = tmp_path / "coverage.xml"
    coverage_xml.write_text("<coverage />", encoding="utf-8")
    monkeypatch.setattr(observability.ElementTree, "parse", lambda _path: SimpleNamespace(getroot=lambda: None))
    assert observability.get_coverage_metrics() == {"line_coverage": 0.0, "branch_coverage": 0.0}

    def _parse_boom(_path):
        raise observability.ElementTree.ParseError("bad xml")

    monkeypatch.setattr(observability.ElementTree, "parse", _parse_boom)
    assert observability.get_coverage_metrics() == {"line_coverage": 0.0, "branch_coverage": 0.0}


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


def test_observability_get_test_metrics_and_build_metrics(monkeypatch):
    assert observability.get_test_metrics() == {
        "test_count": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "duration": 0.0,
    }

    monkeypatch.setattr(observability, "run_command", lambda _cmd: (0, "", ""))
    assert observability.get_build_metrics() == {
        "install_success": True,
        "lint_success": False,
        "test_success": False,
    }

    monkeypatch.setattr(observability, "run_command", lambda _cmd: (1, "", ""))
    assert observability.get_build_metrics() == {
        "install_success": False,
        "lint_success": False,
        "test_success": False,
    }


def test_observability_collect_all_metrics(monkeypatch):
    class _FakeDateTime:
        @staticmethod
        def now(_tz):
            return SimpleNamespace(isoformat=lambda: "2026-05-28T16:00:00+00:00")

    monkeypatch.setattr(observability, "datetime", _FakeDateTime)
    monkeypatch.setattr(observability, "get_test_metrics", lambda: {"tests": 1})
    monkeypatch.setattr(observability, "get_coverage_metrics", lambda: {"line_coverage": 50.0})
    monkeypatch.setattr(observability, "get_lint_metrics", lambda: {"ruff_errors": 0})
    monkeypatch.setattr(observability, "get_build_metrics", lambda: {"install_success": True})

    assert observability.collect_all_metrics() == {
        "timestamp": "2026-05-28T16:00:00Z",
        "test": {"tests": 1},
        "coverage": {"line_coverage": 50.0},
        "lint": {"ruff_errors": 0},
        "build": {"install_success": True},
    }


def test_observability_write_and_read_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(observability, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(observability, "OBSERVABILITY_FILE", tmp_path / "observability.json")
    payload = {"coverage": {"line_coverage": 12.5}}

    observability.write_metrics(payload)

    loaded = observability.read_metrics()
    assert loaded == payload


def test_observability_read_metrics_returns_empty_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(observability, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(observability, "OBSERVABILITY_FILE", tmp_path / "observability.json")

    assert observability.read_metrics() == {}


def test_observability_module_main_guard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    runpy.run_module("sattlint.devtools.observability", run_name="__main__")

    assert (tmp_path / "artifacts" / "observability.json").exists()


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


def test_observability_main_returns_failure_when_output_write_fails(monkeypatch, capsys):
    payload = {
        "coverage": {"line_coverage": 88.1, "branch_coverage": 77.2},
        "lint": {"ruff_warnings": 2, "ruff_errors": 1},
        "build": {},
        "test": {},
        "timestamp": "now",
    }
    monkeypatch.setattr(observability, "collect_all_metrics", lambda: payload)
    monkeypatch.setattr(
        observability,
        "write_metrics",
        lambda metrics: (_ for _ in ()).throw(PermissionError("read-only filesystem")),
    )

    exit_code = observability.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Observability metrics written to" not in captured.out
    assert "Line coverage: 88.1%" in captured.out
    assert "Lint errors: 1" in captured.out
    assert "Observability metrics write error: read-only filesystem" in captured.err


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


def test_review_tool_run_command_success_and_exception(monkeypatch):
    monkeypatch.setattr(review_tool.shutil, "which", lambda tool_name: f"/usr/bin/{tool_name}")
    monkeypatch.setattr(
        review_tool.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )

    assert review_tool.run_command(["python", "-V"]) == (0, "ok", "")

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(review_tool.subprocess, "run", _boom)
    assert review_tool.run_command(["python", "-V"]) == (1, "", "boom")


def test_review_tool_doc_gardener_success_is_reported(monkeypatch):
    monkeypatch.setattr(
        review_tool,
        "doc_gardener_scan",
        lambda: {"total_findings": 0, "by_severity": {"Low": 0}, "by_category": {"dead_link": 0}},
    )

    result = review_tool.run_doc_gardener()

    assert result == {"passed": True, "findings": 0, "by_severity": {"Low": 0}, "by_category": {"dead_link": 0}}


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


def test_review_tool_run_full_review_reports_output_write_error(tmp_path, monkeypatch):
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
    monkeypatch.setattr(builtins, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("locked")))

    report = review_tool.run_full_review()

    assert report["overall_passed"] is True
    assert report["output_error"] == "locked"
    assert not (tmp_path / "review_report.json").exists()


def test_review_tool_format_and_observability_helpers(monkeypatch):
    monkeypatch.setattr(review_tool, "run_command", lambda *_args, **_kwargs: (0, "formatted", ""))
    assert review_tool.run_format_check() == {"passed": True, "stdout": "formatted", "stderr": ""}

    payload = {"coverage": {"line_coverage": 91.2}}
    monkeypatch.setattr(review_tool, "collect_all_metrics", lambda: payload)
    assert review_tool.collect_observability() == payload


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


def test_review_tool_main_reports_output_write_error(monkeypatch, capsys):
    report = {
        "timestamp": "now",
        "overall_passed": True,
        "output_error": "locked",
        "checks": {
            "architecture": {"passed": True, "violations": 0},
            "documentation": {"passed": True, "findings": 0, "by_severity": {}},
            "tests": {"passed": True, "failed": 0, "skipped": 0},
            "linting": {"passed": True, "warnings": 0, "errors": 0},
            "formatting": {"passed": True},
            "observability": {"coverage": {"line_coverage": 90.0, "branch_coverage": 80.0}},
        },
        "summary": {
            "architecture_violations": 0,
            "doc_findings": 0,
            "tests_passed": True,
            "tests_failed": 0,
            "lint_warnings": 0,
            "lint_errors": 0,
            "format_passed": True,
        },
    }
    monkeypatch.setattr(review_tool, "run_full_review", lambda: report)

    with pytest.raises(SystemExit) as exc:
        review_tool.main()

    captured = capsys.readouterr()
    assert exc.value.code == 1
    assert "Overall Status: PASS" in captured.out
    assert "Full report written to" not in captured.out
    assert "Review report write error: locked" in captured.err


def test_review_tool_print_review_handles_severity_and_non_numeric_coverage(capsys):
    report = {
        "timestamp": "now",
        "overall_passed": True,
        "checks": {
            "architecture": {"passed": True, "violations": 0},
            "documentation": {"passed": True, "findings": 1, "by_severity": {"High": 1}},
            "tests": {"passed": True, "failed": 0, "skipped": 0},
            "linting": {"passed": True, "warnings": 0, "errors": 0},
            "formatting": {"passed": True},
            "observability": {"coverage": {"line_coverage": "n/a", "branch_coverage": None}},
        },
        "summary": {
            "architecture_violations": 0,
            "doc_findings": 1,
            "tests_passed": True,
            "tests_failed": 0,
            "lint_warnings": 0,
            "lint_errors": 0,
            "format_passed": True,
        },
    }

    review_tool.print_review(report)

    stdout = capsys.readouterr().out
    assert "By Severity: {'High': 1}" in stdout
    assert "Line Coverage: 0.0%" in stdout
    assert "Branch Coverage: 0.0%" in stdout


def test_review_tool_module_main_guard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sattlint.devtools.doc_gardener.run_scan",
        lambda: {
            "total_findings": 0,
            "by_severity": {},
            "by_category": {},
        },
    )
    monkeypatch.setattr(
        "sattlint.devtools.observability.collect_all_metrics", lambda: {"coverage": {"line_coverage": 99.0}}
    )

    def _fake_run(cmd, capture_output, text, check, cwd=None):
        rendered = " ".join(cmd)
        if "pytest" in rendered:
            return SimpleNamespace(returncode=0, stdout="5 passed, 0 failed, 0 skipped in 0.12s", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(shutil, "which", lambda tool_name: f"/usr/bin/{tool_name}")
    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr(sys, "argv", ["review_tool.py"])

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("sattlint.devtools.review_tool", run_name="__main__")

    assert exc.value.code == 0
    assert (tmp_path / "artifacts" / "review_report.json").exists()
