from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _load_repo_health_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "repo_health.py"
    scripts_dir = str(module_path.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("repo_health", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


repo_health = _load_repo_health_module()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    _write_text(path, json.dumps(payload, indent=2) + "\n")


def test_root_junk_candidates_include_ignored_root_txt_and_tmp(monkeypatch, tmp_path):
    (tmp_path / "covtest.txt").write_text("old coverage\n", encoding="utf-8")
    (tmp_path / ".tmp-local.txt").write_text("scratch\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()

    monkeypatch.setattr(repo_health, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(repo_health, "_tracked_files", lambda: ["README.md"])
    monkeypatch.setattr(
        repo_health,
        "_git",
        lambda *args: subprocess.CompletedProcess(
            list(args),
            0,
            stdout="!! covtest.txt\n?? .tmp-local.txt\n",
            stderr="",
        ),
    )

    candidates = repo_health._root_junk_candidates()

    assert candidates == [
        {"path": ".tmp-local.txt", "kind": "tmp", "git_state": "untracked"},
        {"path": "covtest.txt", "kind": "txt", "git_state": "ignored"},
    ]


def test_largest_files_excludes_docs_and_generated_artifacts(monkeypatch, tmp_path):
    tracked_paths = [
        "artifacts/analysis/impact_analysis.json",
        "docs/exec-plans/tech-debt-tracker.md",
        "README.md",
        "src/pkg/module.py",
        "scripts/repo_health.py",
        "tests/test_repo_health_slice.py",
    ]
    for rel_path, line_count in {
        "artifacts/analysis/impact_analysis.json": 900,
        "docs/exec-plans/tech-debt-tracker.md": 800,
        "README.md": 700,
        "src/pkg/module.py": 20,
        "scripts/repo_health.py": 30,
        "tests/test_repo_health_slice.py": 40,
    }.items():
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("line\n" * line_count, encoding="utf-8")

    monkeypatch.setattr(repo_health, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(repo_health, "_tracked_files", lambda: tracked_paths)

    assert repo_health._largest_files() == [
        {"path": "tests/test_repo_health_slice.py", "lines": 40, "kind": "test"},
        {"path": "scripts/repo_health.py", "lines": 30, "kind": "source"},
        {"path": "src/pkg/module.py", "lines": 20, "kind": "source"},
    ]


def test_build_report_surfaces_root_junk_warning(monkeypatch, tmp_path):
    audit_dir = tmp_path / "artifacts" / "audit"
    pipeline_dir = audit_dir / "pipeline"
    _write_json(
        audit_dir / "status.json",
        {
            "overall_status": "pass",
            "finding_count": 0,
            "blocking_finding_count": 0,
            "severity_counts": {},
        },
    )
    _write_json(audit_dir / "summary.json", {"findings": []})
    _write_json(pipeline_dir / "ruff.json", {"finding_count": 0})
    _write_json(pipeline_dir / "pyright.json", {"error_count": 0, "warning_count": 0})
    _write_json(pipeline_dir / "pytest.json", {"duration_seconds": 1.25, "testcases": []})
    _write_json(tmp_path / "artifacts" / "analysis" / "coverage_ratchet.json", {"summary": {"total_line_rate": 1.0}})
    _write_json(tmp_path / "artifacts" / "analysis" / "structural_budget_ratchet.json", {"metrics": {}})

    monkeypatch.setattr(repo_health, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        repo_health, "DEFAULT_COVERAGE_RATCHET", tmp_path / "artifacts" / "analysis" / "coverage_ratchet.json"
    )
    monkeypatch.setattr(
        repo_health,
        "DEFAULT_STRUCTURAL_RATCHET",
        tmp_path / "artifacts" / "analysis" / "structural_budget_ratchet.json",
    )
    monkeypatch.setattr(
        repo_health.context_health,
        "build_report",
        lambda: {
            "status": "pass",
            "issues": [],
            "metrics": {
                "auto_loaded_context_budget": 80,
                "auto_loaded_context_lines": 10,
                "scoped_context_file_count": 2,
            },
        },
    )
    monkeypatch.setattr(repo_health, "_largest_files", lambda: [])
    monkeypatch.setattr(repo_health, "_slowest_tests", lambda _report: [])
    monkeypatch.setattr(repo_health, "_branch_health", lambda: {"branch": "main", "dirty_files": 0})
    monkeypatch.setattr(repo_health, "_handoff_metrics", lambda: {"ai_task_throughput": 0, "merge_success_rate": None})
    monkeypatch.setattr(repo_health, "_history_snapshots", lambda limit=20: [])
    monkeypatch.setattr(
        repo_health,
        "_root_junk_candidates",
        lambda: [
            {"path": "covtest.txt", "kind": "txt", "git_state": "ignored"},
            {"path": ".tmp-pyright-strict-summary.txt", "kind": "tmp", "git_state": "ignored"},
        ],
    )

    report = repo_health.build_report(audit_dir)

    assert report["status"] == "pass_with_findings"
    assert report["metrics"]["root_junk_file_count"] == 2
    assert report["ratchet_status"] == {
        "overall_status": "pass",
        "coverage": {
            "status": "pass",
            "current_line_rate": 1.0,
            "minimum_line_rate": 0.0,
            "minimum_changed_line_rate": 0.0,
            "minimum_touched_file_line_rate": 0.0,
        },
        "structural": {
            "status": "pass",
            "structural_budget_regression": False,
            "function_over_budget_count": 0,
            "class_over_budget_count": 0,
            "file_exception_count": 0,
        },
    }
    assert report["warnings"] == [
        {
            "id": "ignored-root-junk",
            "severity": "low",
            "message": "Repo root contains ignored or untracked scratch files.",
            "paths": ["covtest.txt", ".tmp-pyright-strict-summary.txt"],
            "candidates": [
                {"path": "covtest.txt", "kind": "txt", "git_state": "ignored"},
                {"path": ".tmp-pyright-strict-summary.txt", "kind": "tmp", "git_state": "ignored"},
            ],
            "suggestion": "Delete the files or move durable outputs under artifacts/, dumps/, or a test fixture directory.",
        }
    ]
    markdown = repo_health._render_markdown(report)
    assert "## Local Hygiene Warnings" in markdown
    assert "## Ratchets" in markdown
    assert "covtest.txt" in markdown


def test_build_ratchet_inventory_lists_allowlists_and_statuses() -> None:
    inventory = repo_health._build_ratchet_inventory(
        file_debt_ratchet={
            "files": {
                "src/demo.py": {
                    "coverage": {
                        "current_baseline": 8500,
                        "target": 9000,
                        "touch_rule": "must_reach_target_on_touch",
                        "reason": "Raise the floor.",
                    },
                    "structural": {
                        "current_baseline": 420,
                        "target": 300,
                        "touch_rule": "must_reduce_on_touch",
                        "reason": "Split the module.",
                    },
                    "typing": {
                        "touch_rule": "must_exit_allowlist_on_touch",
                        "reason": "Tighten types.",
                    },
                },
                "src/clean.py": {
                    "typing": {
                        "touch_rule": "must_exit_allowlist_on_touch",
                        "reason": "Finish strict typing.",
                    }
                },
            }
        },
        structural_ratchet={
            "file_line_exceptions": {"src/oversized.py": {"max_lines": 900, "reason": "Legacy split pending."}}
        },
        pyproject_payload={"tool": {"sattlint": {"typing_ratchet": {"debt_allowlist": ["src/demo.py"]}}}},
    )

    assert inventory["allow_lists"] == {
        "typing_debt_allowlist": [{"path": "src/demo.py"}],
        "structural_file_exceptions": [
            {"path": "src/oversized.py", "max_lines": 900, "reason": "Legacy split pending."}
        ],
    }
    assert inventory["ratcheted_file_statuses"] == [
        {
            "path": "src/clean.py",
            "kind": "typing",
            "touch_rule": "must_exit_allowlist_on_touch",
            "allow_rebaseline": False,
            "reason": "Finish strict typing.",
            "status": "tracked",
            "current_baseline": None,
            "target": None,
            "current_display": "n/a",
            "target_display": "n/a",
            "gap_display": "tracked typing debt",
        },
        {
            "path": "src/demo.py",
            "kind": "coverage",
            "touch_rule": "must_reach_target_on_touch",
            "allow_rebaseline": False,
            "reason": "Raise the floor.",
            "status": "below_target",
            "current_baseline": 8500,
            "target": 9000,
            "current_display": "85.00%",
            "target_display": "90.00%",
            "gap_display": "5.00 pp short",
        },
        {
            "path": "src/demo.py",
            "kind": "structural",
            "touch_rule": "must_reduce_on_touch",
            "allow_rebaseline": False,
            "reason": "Split the module.",
            "status": "over_target",
            "current_baseline": 420,
            "target": 300,
            "current_display": "420",
            "target_display": "300",
            "gap_display": "120 over target",
        },
        {
            "path": "src/demo.py",
            "kind": "typing",
            "touch_rule": "must_exit_allowlist_on_touch",
            "allow_rebaseline": False,
            "reason": "Tighten types.",
            "status": "allowlisted",
            "current_baseline": None,
            "target": None,
            "current_display": "n/a",
            "target_display": "n/a",
            "gap_display": "allowlisted typing debt",
        },
    ]


def test_main_prints_root_junk_warning_summary(monkeypatch, capsys):
    monkeypatch.setattr(
        repo_health,
        "build_report",
        lambda _audit_dir: {
            "status": "pass_with_findings",
            "metrics": {
                "finding_count": 0,
                "coverage_total_line_rate": 1.0,
                "auto_loaded_context_lines": 10,
                "context_auto_loaded_budget": 80,
                "largest_file_path": None,
                "largest_file_lines": 0,
                "ai_task_throughput": 0,
                "root_junk_file_count": 2,
            },
            "warnings": [
                {
                    "message": "Repo root contains ignored or untracked scratch files.",
                    "paths": ["covtest.txt", ".tmp-pyright-strict-summary.txt"],
                }
            ],
        },
    )

    exit_code = repo_health.main(["--audit-dir", "artifacts/audit"])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Root junk files: 2" in captured
    assert (
        "Warning: Repo root contains ignored or untracked scratch files. covtest.txt, .tmp-pyright-strict-summary.txt"
        in captured
    )


def test_render_html_contains_dashboard_sections() -> None:
    report = {
        "status": "pass_with_findings",
        "generated_at": "2026-05-11T12:00:00+00:00",
        "audit_dir": "artifacts/audit-sample",
        "audit_status": {"overall_status": "pass", "max_severity": "medium"},
        "context_status": {"status": "pass", "issue_count": 0},
        "metrics": {
            "finding_count": 3,
            "blocking_finding_count": 1,
            "coverage_total_line_rate": 0.9123,
            "coverage_min_line_rate": 0.88,
            "auto_loaded_context_lines": 90,
            "context_auto_loaded_budget": 180,
            "scoped_context_file_count": 4,
            "ruff_issue_count": 2,
            "pyright_error_count": 1,
            "pyright_warning_count": 5,
            "test_runtime_seconds": 2.5,
            "ai_task_throughput": 6,
            "dirty_files": 7,
            "largest_file_lines": 1234,
            "largest_file_path": "scripts/repo_health.py",
            "root_junk_file_count": 0,
            "function_over_budget_count": 2,
            "class_over_budget_count": 1,
        },
        "branch_health": {
            "branch": "main",
            "dirty_files": 7,
            "ahead_by": 1,
            "behind_by": 0,
            "tracked_worktrees": 2,
        },
        "handoffs": {"handoff_count": 4, "merge_success_rate": 0.75},
        "trend_summary": {
            "history_count": 5,
            "coverage_delta": 0.0123,
            "finding_delta": -2,
            "context_delta": 4,
            "largest_file_delta": 0,
        },
        "ratchet_status": {
            "overall_status": "pass_with_findings",
            "coverage": {
                "status": "pass",
                "current_line_rate": 0.9123,
                "minimum_line_rate": 0.88,
                "minimum_changed_line_rate": 1.0,
                "minimum_touched_file_line_rate": 0.9,
            },
            "structural": {
                "status": "pass_with_findings",
                "structural_budget_regression": False,
                "function_over_budget_count": 2,
                "class_over_budget_count": 1,
                "file_exception_count": 0,
            },
        },
        "top_findings": [
            {"message": "Example finding", "severity": "medium", "category": "quality", "path": "src/demo.py"}
        ],
        "warnings": [{"message": "Example warning", "paths": ["tmp.txt"]}],
        "largest_files": [{"path": "scripts/repo_health.py", "lines": 1234, "kind": "source"}],
        "slowest_tests": [{"name": "tests.demo.test_case", "time_seconds": 1.234, "outcome": "passed"}],
        "ratchet_inventory": {"allow_lists": {}, "ratcheted_file_statuses": []},
    }

    html = repo_health._render_html(
        report,
        current_page_path="repo-health.html",
        ratchet_page_path="repo-health-ratchets.html",
    )

    assert "<title>SattLint Repo Health</title>" in html
    assert "Snapshot-backed view of audit, context, branch, and throughput health for this repository." in html
    assert 'href="repo-health-ratchets.html"' in html
    assert (
        'href="command:workbench.action.tasks.runTask?%5B%22Metrics%3A%20Refresh%20Repo%20Health%20Dashboard%22%5D"'
        in html
    )
    assert "Refresh dashboard" in html
    assert "Reload page" not in html
    assert "Example finding" in html
    assert "Example warning" in html
    assert "scripts/repo_health.py" in html
    assert "tests.demo.test_case" in html
    assert "Ratchet status" in html
    assert "Ratcheting" in html
    assert "Coverage Ratchet" in html
    assert "91.23% current vs 88.00% floor" in html
    assert "Structural Ratchet" in html
    assert "2 functions, 1 classes, 0 exceptions" in html


def test_render_ratchet_html_contains_allowlists_and_file_statuses() -> None:
    report = {
        "ratchet_inventory": {
            "allow_lists": {
                "typing_debt_allowlist": [{"path": "src/demo.py"}],
                "structural_file_exceptions": [
                    {"path": "src/oversized.py", "max_lines": 900, "reason": "Legacy split pending."}
                ],
            },
            "ratcheted_file_statuses": [
                {
                    "path": "src/demo.py",
                    "kind": "coverage",
                    "status": "below_target",
                    "current_display": "85.00%",
                    "target_display": "90.00%",
                    "gap_display": "5.00 pp short",
                    "touch_rule": "must_reach_target_on_touch",
                    "reason": "Raise the floor.",
                },
                {
                    "path": "src/demo.py",
                    "kind": "typing",
                    "status": "allowlisted",
                    "current_display": "n/a",
                    "target_display": "n/a",
                    "gap_display": "allowlisted typing debt",
                    "touch_rule": "must_exit_allowlist_on_touch",
                    "reason": "Tighten types.",
                },
            ],
        }
    }

    html = repo_health._render_ratchet_html(
        report,
        current_page_path="repo-health-ratchets.html",
        main_page_path="repo-health.html",
    )

    assert "<title>SattLint Ratchet Details</title>" in html
    assert 'href="repo-health.html"' in html
    assert (
        'href="command:workbench.action.tasks.runTask?%5B%22Metrics%3A%20Refresh%20Repo%20Health%20Dashboard%22%5D"'
        in html
    )
    assert "Typing debt allow-list" in html
    assert "src/demo.py" in html
    assert "src/oversized.py" in html
    assert "SattLint Ratchet Details" in html
    assert "Ratcheted file status" in html
    assert 'id="ratchet-filter-query"' in html
    assert 'id="ratchet-sort-by"' in html
    assert 'id="ratcheted-status-table"' in html
    assert 'class="ratchet-row"' in html
    assert "applyTableState" in html
    assert html.index("<h2>Ratcheted file status</h2>") < html.index('id="ratchet-filter-query"')
    assert "must_exit_allowlist_on_touch" in html


def test_main_writes_html_output(monkeypatch, tmp_path, capsys):
    html_output = tmp_path / "artifacts" / "health" / "repo-health.html"
    ratchet_output = tmp_path / "artifacts" / "health" / "repo-health-ratchets.html"
    monkeypatch.setattr(
        repo_health,
        "build_report",
        lambda _audit_dir: {
            "status": "pass",
            "generated_at": "2026-05-11T12:00:00+00:00",
            "audit_dir": "artifacts/audit",
            "audit_status": {"overall_status": "pass", "max_severity": None},
            "context_status": {"status": "pass", "issue_count": 0},
            "metrics": {
                "finding_count": 0,
                "blocking_finding_count": 0,
                "coverage_total_line_rate": 1.0,
                "coverage_min_line_rate": 1.0,
                "auto_loaded_context_lines": 10,
                "context_auto_loaded_budget": 80,
                "scoped_context_file_count": 2,
                "ruff_issue_count": 0,
                "pyright_error_count": 0,
                "pyright_warning_count": 0,
                "test_runtime_seconds": 1.25,
                "ai_task_throughput": 0,
                "dirty_files": 0,
                "largest_file_lines": 0,
                "largest_file_path": None,
                "root_junk_file_count": 0,
                "function_over_budget_count": 0,
                "class_over_budget_count": 0,
            },
            "branch_health": {
                "branch": "main",
                "dirty_files": 0,
                "ahead_by": 0,
                "behind_by": 0,
                "tracked_worktrees": 1,
            },
            "handoffs": {"handoff_count": 0, "merge_success_rate": None},
            "trend_summary": {
                "history_count": 0,
                "coverage_delta": None,
                "finding_delta": None,
                "context_delta": None,
                "largest_file_delta": None,
            },
            "ratchet_status": {
                "overall_status": "pass",
                "coverage": {
                    "status": "pass",
                    "current_line_rate": 1.0,
                    "minimum_line_rate": 1.0,
                    "minimum_changed_line_rate": 1.0,
                    "minimum_touched_file_line_rate": 1.0,
                },
                "structural": {
                    "status": "pass",
                    "structural_budget_regression": False,
                    "function_over_budget_count": 0,
                    "class_over_budget_count": 0,
                    "file_exception_count": 0,
                },
            },
            "warnings": [],
            "top_findings": [],
            "largest_files": [],
            "slowest_tests": [],
            "ratchet_inventory": {
                "allow_lists": {
                    "typing_debt_allowlist": [{"path": "src/demo.py"}],
                    "structural_file_exceptions": [],
                },
                "ratcheted_file_statuses": [
                    {
                        "path": "src/demo.py",
                        "kind": "typing",
                        "status": "allowlisted",
                        "current_display": "n/a",
                        "target_display": "n/a",
                        "gap_display": "allowlisted typing debt",
                        "touch_rule": "must_exit_allowlist_on_touch",
                        "reason": "Tighten types.",
                    }
                ],
            },
        },
    )

    exit_code = repo_health.main(["--audit-dir", "artifacts/audit", "--html-output", str(html_output)])

    assert exit_code == 0
    html = html_output.read_text(encoding="utf-8")
    ratchet_html = ratchet_output.read_text(encoding="utf-8")
    captured = capsys.readouterr().out
    assert "<title>SattLint Repo Health</title>" in html
    assert 'href="repo-health-ratchets.html"' in html
    assert (
        'href="command:workbench.action.tasks.runTask?%5B%22Metrics%3A%20Refresh%20Repo%20Health%20Dashboard%22%5D"'
        in html
    )
    assert "Ratchet status" in html
    assert "Coverage Ratchet" in html
    assert "Structural Ratchet" in html
    assert "<title>SattLint Ratchet Details</title>" in ratchet_html
    assert "Ratcheted file status" in ratchet_html
    assert (
        'href="command:workbench.action.tasks.runTask?%5B%22Metrics%3A%20Refresh%20Repo%20Health%20Dashboard%22%5D"'
        in ratchet_html
    )
    assert 'id="ratchet-filter-query"' in ratchet_html
    assert 'id="ratchet-sort-direction"' in ratchet_html
    assert "src/demo.py" in ratchet_html
    assert "Repository health: pass" in captured
