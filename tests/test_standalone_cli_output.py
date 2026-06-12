# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false
from __future__ import annotations

import json

import pytest

from sattlint.devtools import corpus, doc_gardener, layer_linter, observability, release_smoke, review_tool


def test_corpus_main_supports_json_summary_output(monkeypatch, tmp_path, capsys):
    class _FakeSuite:
        passed = True

        def to_dict(self) -> dict[str, object]:
            return {
                "summary": {"case_count": 1, "failed_count": 0},
                "findings_schema": {"kind": "schema", "schema_version": 1},
            }

    monkeypatch.setattr(corpus, "run_corpus_suite", lambda *_args, **_kwargs: _FakeSuite())
    monkeypatch.setattr(corpus, "_write_json", lambda *_args, **_kwargs: None)

    exit_code = corpus.main(
        [
            "--output-dir",
            str(tmp_path / "out"),
            "--manifest-dir",
            str(tmp_path / "manifests"),
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["case_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["findings_schema"] == {"kind": "schema", "schema_version": 1}


def test_doc_gardener_main_supports_json_summary_output(monkeypatch, capsys):
    monkeypatch.setattr(
        doc_gardener,
        "run_scan",
        lambda: {
            "total_findings": 1,
            "by_severity": {"High": 1},
            "by_category": {"stale": 1},
            "findings": [
                {
                    "file": "docs/demo.md",
                    "line": 4,
                    "severity": "High",
                    "category": "stale",
                    "message": "stale heading",
                }
            ],
        },
    )

    exit_code = doc_gardener.main(["--check-only", "--format", "json"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["check_only"] is True
    assert payload["total_findings"] == 1
    assert payload["findings"][0]["file"] == "docs/demo.md"


def test_observability_main_supports_json_summary_output(monkeypatch, capsys):
    metrics = {
        "coverage": {"line_coverage": 88.1, "branch_coverage": 77.2},
        "lint": {"ruff_errors": 1, "ruff_fixable": 1},
        "build": {},
        "test": {},
        "timestamp": "now",
    }
    monkeypatch.setattr(observability, "collect_all_metrics", lambda: metrics)
    monkeypatch.setattr(observability, "write_metrics", lambda _metrics: None)

    exit_code = observability.main(["--format", "json"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["metrics"] == metrics
    assert payload["metrics_file"] == observability.OBSERVABILITY_FILE.as_posix()


def test_layer_linter_main_supports_json_summary_output(monkeypatch, capsys):
    violation = layer_linter.ArchViolation("src/demo.py", 7, "invalid import")
    monkeypatch.setattr(layer_linter, "collect_architecture_violations", lambda *_args, **_kwargs: [violation])

    with pytest.raises(SystemExit) as exc_info:
        layer_linter.main(["--format", "json"])

    payload = json.loads(capsys.readouterr().out)

    assert exc_info.value.code == 1
    assert payload["status"] == "fail"
    assert payload["violation_count"] == 1
    assert payload["violations"][0]["file"] == "src/demo.py"


def test_review_tool_main_supports_json_summary_output(monkeypatch, capsys):
    report = {
        "timestamp": "now",
        "overall_passed": True,
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
    monkeypatch.setattr(review_tool, "run_full_review", lambda **_kwargs: report)

    with pytest.raises(SystemExit) as exc_info:
        review_tool.main(["--format", "json"])

    payload = json.loads(capsys.readouterr().out)

    assert exc_info.value.code == 0
    assert payload["overall_passed"] is True
    assert payload["report_path"] == review_tool.REVIEW_FILE.as_posix()


def test_release_smoke_supports_json_summary_output(monkeypatch, tmp_path):
    status_report = {
        "overall_status": "pass",
        "failing_steps": [],
        "pending_steps": [],
        "status_report": "artifacts/release-smoke/status.json",
        "summary_report": "artifacts/release-smoke/summary.json",
    }
    summary_report = {
        "kind": release_smoke.SUMMARY_SCHEMA_KIND,
        "status": {"overall_status": "pass", "failing_steps": [], "pending_steps": []},
        "steps": [],
    }
    emitted: list[str] = []

    monkeypatch.setattr(
        release_smoke,
        "execute_release_smoke",
        lambda **_kwargs: (status_report, summary_report),
    )
    monkeypatch.setattr(release_smoke, "write_json_artifact", lambda *_args, **_kwargs: None)

    exit_code = release_smoke.run_release_smoke(
        wheel=tmp_path / "dist.whl",
        sample_file=tmp_path / "sample.s",
        output_dir=tmp_path / "artifacts" / "release-smoke",
        output_format="json",
        emit_output_fn=emitted.append,
    )

    assert exit_code == 0
    assert emitted
    assert json.loads(emitted[0]) == summary_report
