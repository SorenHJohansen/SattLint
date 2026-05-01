from __future__ import annotations

import json
from types import SimpleNamespace

from sattlint.devtools import structural_reports


def _write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_collect_structural_budget_report_detects_markdown_budget_offenders(tmp_path):
    oversized_markdown = "\n".join(f"- item {index}" for index in range(520))
    _write(tmp_path / "docs" / "guide.md", oversized_markdown)

    report = structural_reports.collect_structural_budget_report(tmp_path)

    assert report["markdown_files_over_budget"] == [{"path": "docs/guide.md", "line_count": 520}]
    assert report["summary"]["markdown_file_max_lines"] == 520
    assert report["metrics"]["markdown_file_over_budget_count"] == 1
    assert report["metrics"]["markdown_file_max_lines"] == 520


def test_collect_architecture_report_includes_markdown_budget_findings(monkeypatch):
    empty_catalog = SimpleNamespace(analyzers=[], rules=[])
    monkeypatch.setattr(
        structural_reports,
        "collect_structural_budget_report",
        lambda *_args, **_kwargs: {
            "thresholds": dict(structural_reports.STRUCTURAL_BUDGET_THRESHOLDS),
            "source_files_over_budget": [],
            "test_files_over_budget": [],
            "markdown_files_over_budget": [{"path": "docs/guide.md", "line_count": 600}],
            "functions_over_budget": [],
            "classes_over_budget": [],
            "repeated_private_names": [],
            "facade_private_entrypoints": [],
            "metrics": {},
            "ratchet": {
                "status": "pass",
                "path": "ratchet.json",
                "expected_metrics": {},
                "current_metrics": {},
                "regressions": [],
            },
            "scan_failures": [],
        },
    )
    monkeypatch.setattr(structural_reports, "get_default_analyzer_catalog", lambda: empty_catalog)
    monkeypatch.setattr(structural_reports, "get_declared_cli_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "get_actual_cli_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "get_declared_lsp_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "get_actual_lsp_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "VARIABLE_ANALYSES", {})

    report = structural_reports.collect_architecture_report()

    assert any(finding["id"] == "structural-markdown-file-budget" for finding in report["findings"])


def test_collect_structural_budget_report_tracks_markdown_max_lines_under_threshold(tmp_path):
    _write(tmp_path / "README.md", "line 1\nline 2\n")

    report = structural_reports.collect_structural_budget_report(tmp_path)

    assert report["markdown_files_over_budget"] == []
    assert report["summary"]["markdown_file_max_lines"] == 2
    assert report["metrics"]["markdown_file_max_lines"] == 2


def test_collect_structural_budget_report_allows_documented_markdown_file_exception(tmp_path):
    _write(tmp_path / "docs" / "roadmap.md", "\n".join(f"# section {index}" for index in range(530)))
    _write(
        tmp_path / "artifacts" / "analysis" / "structural_budget_ratchet.json",
        json.dumps(
            {
                "kind": "sattlint.structural_budget_ratchet",
                "schema_version": 3,
                "metrics": {},
                "file_line_exceptions": {
                    "docs/roadmap.md": {
                        "max_lines": 530,
                        "reason": "Roadmap owner document remains centralized pending breakdown into smaller plans.",
                    }
                },
            },
            indent=2,
        ),
    )

    report = structural_reports.collect_structural_budget_report(tmp_path)

    assert report["markdown_files_over_budget"] == []
    assert report["ratchet"]["status"] == "pass"
    assert report["line_limit_exceptions"] == [
        {
            "path": "docs/roadmap.md",
            "line_count": 530,
            "max_lines": 530,
            "reason": "Roadmap owner document remains centralized pending breakdown into smaller plans.",
            "status": "pass",
        }
    ]
