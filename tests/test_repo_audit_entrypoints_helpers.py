from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from sattlint.devtools import repo_audit, repo_audit_entrypoints


def test_repo_audit_entrypoint_helper_normalizers_and_reason_selection():
    assert repo_audit_entrypoints._changed_file_flag_args(["src\\main.py", "src/main.py", ""]) == [
        "--changed-file",
        "src/main.py",
    ]
    assert repo_audit_entrypoints._focused_python_files(
        [
            "src/main.py",
            "tests/test_main.py",
            "scripts/build.py",
            "docs/readme.md",
            "pkg/ignored.py",
        ]
    ) == ["src/main.py", "tests/test_main.py", "scripts/build.py"]
    assert repo_audit_entrypoints._owner_test_targets_for_checks(
        [
            {"owner_test_targets": ["tests/test_a.py", "tests/test_a.py"]},
            {"owner_test_targets": ["tests/test_b.py"]},
        ]
    ) == ["tests/test_a.py", "tests/test_b.py"]
    assert repo_audit_entrypoints._normalize_repo_audit_finding_checks(None) is None
    assert repo_audit_entrypoints._normalize_repo_audit_finding_checks(["text-scan", "text-scan"]) == ("text-scan",)
    with pytest.raises(ValueError):
        repo_audit_entrypoints._normalize_repo_audit_finding_checks(["ghost"])
    with pytest.raises(ValueError):
        repo_audit_entrypoints._normalize_repo_audit_finding_checks(["   "])

    pipeline_surface, pipeline_reason = repo_audit_entrypoints._selected_surface_and_reason(
        {"recommended_repo_audit_check_ids": []}
    )
    repo_surface, repo_reason = repo_audit_entrypoints._selected_surface_and_reason(
        {"recommended_repo_audit_check_ids": ["cli"]}
    )

    assert pipeline_surface == "pipeline"
    assert "shared pipeline finish gate" in pipeline_reason
    assert repo_surface == "repo-audit"
    assert "Repo-audit-specific checks" in repo_reason
    assert (
        repo_audit_entrypoints._recommended_command(
            output_dir="artifacts/audit",
            profile="full",
            fail_on="medium",
            leaks_only=True,
        )
        == "sattlint-repo-audit --leaks-only --fail-on medium --output-dir artifacts/audit"
    )


def test_repo_audit_entrypoint_builds_finish_gate_commands_and_gate_reason(tmp_path):
    recommended_checks = [
        {
            "id": "cli",
            "source": "repo-audit",
            "owner_surface": "cli",
            "path_globs": ["src/sattlint/app.py"],
            "owner_test_targets": ["tests/test_app.py"],
            "reason": "Matched src/sattlint/app.py against the cli routing globs.",
        }
    ]

    commands = repo_audit_entrypoints._build_repo_audit_finish_gate_commands(
        profile="full",
        output_dir=tmp_path,
        fail_on="high",
        changed_files=["src/sattlint/app.py", "docs/references/cli-commands.md"],
        recommended_checks=recommended_checks,
        ruff_command=["ruff"],
        pyright_command=["pyright"],
        python_command=["python"],
    )
    why_this_gate = repo_audit_entrypoints._build_recommendation_why_this_gate(
        changed_files=["src/sattlint/app.py", "docs/references/cli-commands.md"],
        recommended_checks=recommended_checks,
        skipped_checks=[{"id": "bandit", "reason": "No changed-file route matched this check."}],
    )

    assert [entry["id"] for entry in commands] == [
        "recommended-finish-gate",
        "ruff-touched-python",
        "pyright-touched-python",
        "owner-pytest",
    ]
    assert why_this_gate["matched_routes"] == [
        {
            "check_id": "cli",
            "source": "repo-audit",
            "owner_surface": "cli",
            "matched_files": ["src/sattlint/app.py"],
            "path_globs": ["src/sattlint/app.py"],
            "reason": "Matched src/sattlint/app.py against the cli routing globs.",
        }
    ]
    assert why_this_gate["skipped_checks"] == [{"id": "bandit", "reason": "No changed-file route matched this check."}]


def test_ai_feedback_and_severity_helpers_cover_failure_reporting():
    findings = [
        repo_audit.Finding(
            "coverage-gap",
            "coverage",
            "medium",
            "high",
            "Coverage gap.",
            path="src/module.py",
        ),
        repo_audit.Finding(
            "architecture-gap",
            "architecture",
            "high",
            "high",
            "Architecture gap.",
            path="src/other.py",
        ),
    ]
    finish_gate = {
        "commands": [
            {"id": "pyright", "label": "Pyright", "command": "pyright src/module.py", "status": "pass"},
            {"id": "ruff", "label": "Ruff", "command": "ruff check src/module.py", "status": "fail", "exit_code": 1},
        ]
    }

    feedback = repo_audit_entrypoints._build_ai_feedback_report(
        changed_files=["src/module.py"],
        selected_surface="repo-audit",
        selected_reason="Repo-audit-specific checks were recommended.",
        selected_command="sattlint-repo-audit --run-recommended-finish-gate",
        overall_status="fail",
        finish_gate_status="fail",
        reports={"finish_gate": "artifacts/audit/finish_gate.json"},
        planning_context={
            "primary_agent": "Repo Audit",
            "instruction_files": [{"name": "Repo Audit Instructions"}],
            "owner_test_targets": ["tests/test_repo_audit.py"],
            "first_validation_commands": ["ruff check src/module.py"],
        },
        recommendation={
            "recommended_check_ids": ["cli"],
            "recommended_pipeline_check_ids": [],
            "recommended_repo_audit_check_ids": ["cli"],
        },
        selected_result={"finish_gate": finish_gate},
    )

    assert repo_audit_entrypoints._severity_counts(findings) == {
        "critical": 0,
        "high": 1,
        "medium": 1,
        "low": 0,
    }
    assert repo_audit_entrypoints._category_counts(findings) == {"architecture": 1, "coverage": 1}
    assert repo_audit_entrypoints._max_severity(findings) == "high"
    assert repo_audit_entrypoints._should_fail(findings, "medium") is True
    assert repo_audit_entrypoints._blocking_finding_count(findings, "medium") == 2
    assert repo_audit_entrypoints._first_failed_finish_gate_step(finish_gate) == {
        "id": "ruff",
        "label": "Ruff",
        "command": "ruff check src/module.py",
        "exit_code": 1,
    }
    assert feedback["first_failed_step"] == {
        "id": "ruff",
        "label": "Ruff",
        "command": "ruff check src/module.py",
        "exit_code": 1,
    }
    assert feedback["suggested_next_command"] == "ruff check src/module.py"


def test_run_verify_recommendations_check_converts_catalog_issues_to_findings(monkeypatch, tmp_path):
    fake_repo_audit = SimpleNamespace(
        DEFAULT_OUTPUT_DIR=tmp_path / "audit",
        PIPELINE_OUTPUT_DIRNAME="pipeline",
        REPO_ROOT=tmp_path,
        Finding=lambda **kwargs: SimpleNamespace(**kwargs),
    )
    reports = iter(
        [
            {
                "issues": [
                    {
                        "issue_id": "missing-owner-tests",
                        "check_id": "ruff",
                        "message": "Missing owner tests.",
                    }
                ]
            },
            {
                "issues": [
                    {
                        "issue_id": "dead-path-globs",
                        "check_id": "cli",
                        "message": "Dead path globs.",
                    }
                ]
            },
        ]
    )

    monkeypatch.setattr(repo_audit_entrypoints, "_repo_audit_module", lambda: fake_repo_audit)
    monkeypatch.setattr(
        repo_audit_entrypoints.pipeline_module, "build_pipeline_check_catalog", lambda **kwargs: {"checks": []}
    )
    monkeypatch.setattr(repo_audit_entrypoints, "build_repo_audit_check_catalog", lambda **kwargs: {"checks": []})
    monkeypatch.setattr(repo_audit_entrypoints, "verify_check_catalog", lambda catalog, repo_root: next(reports))

    findings = repo_audit_entrypoints._run_verify_recommendations_check(None)

    assert [finding.id for finding in findings] == [
        "recommendation-missing-owner-tests-ruff",
        "recommendation-dead-path-globs-cli",
    ]
    assert findings[0].severity == "high"
    assert findings[1].detail == '{"check_id": "cli", "issue_id": "dead-path-globs", "message": "Dead path globs."}'


def test_run_recommended_repo_audit_finish_gate_writes_failed_step_report(monkeypatch, tmp_path):
    recommendation = {
        "changed_files": ["src/sattlint/app.py"],
        "recommended_checks": [
            {
                "id": "cli",
                "source": "repo-audit",
                "owner_surface": "cli",
                "path_globs": ["src/sattlint/app.py"],
                "owner_test_targets": ["tests/test_app.py"],
                "reason": "Matched src/sattlint/app.py against the cli routing globs.",
            }
        ],
    }
    run_results = iter(
        [
            SimpleNamespace(exit_code=0, duration_seconds=0.1),
            SimpleNamespace(exit_code=1, duration_seconds=0.2),
            SimpleNamespace(exit_code=0, duration_seconds=0.3),
        ]
    )

    monkeypatch.setattr(
        repo_audit_entrypoints,
        "build_repo_audit_check_recommendations",
        lambda **kwargs: recommendation,
    )
    monkeypatch.setattr(
        repo_audit_entrypoints,
        "run_recommended_repo_audit_slice",
        lambda *args, **kwargs: {"overall_status": "pass", "finding_count": 0},
    )
    monkeypatch.setattr(
        repo_audit_entrypoints.pipeline_module,
        "_resolve_venv_tool",
        lambda tool: f".venv/Scripts/{tool}.exe",
    )
    monkeypatch.setattr(
        repo_audit_entrypoints.pipeline_module,
        "_resolve_python_executable",
        lambda: ".venv/Scripts/python.exe",
    )
    monkeypatch.setattr(repo_audit_entrypoints.pipeline_module, "_run_command", lambda *_args: next(run_results))
    monkeypatch.setattr(repo_audit, "_write_audit_run_history", lambda *args, **kwargs: None)

    summary = repo_audit_entrypoints.run_recommended_repo_audit_finish_gate(
        tmp_path,
        profile="full",
        fail_on="high",
        include_generated=False,
        suspicious_identifiers=[],
        skip_vulture=False,
        skip_bandit=False,
        changed_files=["src/sattlint/app.py"],
    )

    finish_gate = json.loads((tmp_path / "finish_gate.json").read_text(encoding="utf-8"))

    assert summary["overall_status"] == "fail"
    assert finish_gate["status"] == "fail"
    assert [entry["id"] for entry in finish_gate["commands"]] == [
        "ruff-touched-python",
        "pyright-touched-python",
        "owner-pytest",
    ]
    assert finish_gate["commands"][1]["status"] == "fail"
    assert finish_gate["commands"][1]["exit_code"] == 1
    assert finish_gate["owner_test_targets"] == ["tests/test_app.py"]


def test_run_recommended_repo_audit_slice_writes_combined_reports(monkeypatch, tmp_path):
    recommendation = {
        "recommended_check_ids": ["ruff", "cli", "ai-gc", "cli-consistency"],
        "recommended_pipeline_check_ids": ["ruff"],
        "recommended_repo_audit_check_ids": ["cli", "ai-gc", "cli-consistency"],
    }
    pipeline_finding = repo_audit.Finding(
        "pipeline-gap",
        "coverage",
        "medium",
        "high",
        "Pipeline gap.",
        path="src/pipeline.py",
    )
    custom_finding = repo_audit.Finding(
        "custom-gap",
        "architecture",
        "medium",
        "high",
        "Custom gap.",
        path="src/custom.py",
    )
    cli_consistency_report = {
        "status": "fail",
        "gaps": {
            "undeclared_subcommands": [{"subcommand": "ghost", "referenced_in": "README.md", "line": 7}],
            "undeclared_scripts": [{"script": "ghost-script", "referenced_in": "README.md", "line": 9}],
        },
    }
    ai_gc_report = {
        "kind": "sattlint.ai_gc",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.ai_gc",
        "mode": "report",
        "root": ".",
        "status": "needs-attention",
        "summary": {
            "candidate_count": 1,
            "artifact_candidate_count": 1,
            "manifest_drift_candidate_count": 0,
            "ledger_candidate_count": 0,
            "applied_count": 0,
            "failure_count": 0,
            "total_candidate_bytes": 12,
        },
        "candidates": [],
        "applied_actions": [],
        "failures": [],
    }

    monkeypatch.setattr(
        repo_audit_entrypoints,
        "build_repo_audit_check_recommendations",
        lambda **kwargs: recommendation,
    )
    monkeypatch.setattr(
        repo_audit_entrypoints.pipeline_module,
        "_run_pipeline",
        lambda *args, **kwargs: {"status": {"overall_status": "pass"}},
    )
    monkeypatch.setattr(repo_audit, "_find_pipeline_findings", lambda *_args: [pipeline_finding])
    monkeypatch.setattr(repo_audit_entrypoints, "collect_custom_findings", lambda *args, **kwargs: [custom_finding])
    monkeypatch.setattr(repo_audit, "build_ai_gc_report", lambda *_args, **_kwargs: ai_gc_report)
    monkeypatch.setattr(
        repo_audit,
        "build_cli_consistency_report",
        lambda *args, **kwargs: cli_consistency_report,
    )
    monkeypatch.setattr(repo_audit, "_write_markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(repo_audit, "_write_audit_run_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(repo_audit, "_mirror_latest_reports", lambda *args, **kwargs: None)

    summary = repo_audit_entrypoints.run_recommended_repo_audit_slice(
        tmp_path,
        profile="full",
        fail_on="high",
        include_generated=False,
        suspicious_identifiers=[],
        skip_vulture=False,
        skip_bandit=False,
        changed_files=["src/sattlint/app.py"],
    )

    status_report = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    summary_report = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert summary["cli_consistency_status"] == "fail"
    assert summary_report["pipeline_ran"] is True
    assert summary_report["selected_pipeline_checks"] == ["ruff"]
    assert summary_report["selected_repo_audit_checks"] == ["cli", "ai-gc", "cli-consistency"]
    assert summary_report["cli_consistency_status"] == "fail"
    assert status_report["overall_status"] == "fail"
    assert status_report["pipeline_status_report"].endswith("/pipeline/status.json")
    assert (tmp_path / "ai_gc.json").exists()
    assert (tmp_path / "cli_consistency.json").exists()
