# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sattlint.devtools.ai import ai_work_map
from sattlint.devtools.audit import repo_audit, repo_audit_entrypoints


def test_repo_audit_entrypoint_helper_normalizers_and_reason_selection():
    assert repo_audit_entrypoints.changed_file_flag_args(["src\\main.py", "src/main.py", ""]) == [
        "--changed-file",
        "src/main.py",
    ]
    assert repo_audit_entrypoints._planning_string_list(("not", "a", "list")) == []
    assert repo_audit_entrypoints.focused_python_files(
        [
            "src/main.py",
            "src/main.py",
            "tests/test_main.py",
            "scripts/build.py",
            "docs/readme.md",
            "pkg/ignored.py",
        ]
    ) == ["src/main.py", "tests/test_main.py", "scripts/build.py"]
    assert repo_audit_entrypoints.owner_test_targets_for_checks(
        [
            {"owner_test_targets": ["tests/test_a.py", "tests/test_a.py"]},
            {"owner_test_targets": ["tests/test_b.py"]},
        ]
    ) == ["tests/test_a.py", "tests/test_b.py"]
    assert repo_audit_entrypoints._normalize_repo_audit_finding_checks(None) is None
    assert repo_audit_entrypoints._normalize_repo_audit_finding_checks(["text-scan", "text-scan"]) == ("text-scan",)
    with pytest.raises(ValueError):
        repo_audit_entrypoints._normalize_repo_audit_finding_checks([])
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


def test_shell_command_uses_posix_joining():
    assert repo_audit_entrypoints.shell_command(["python", "-m", "sattlint", "path with space"]) == (
        "python -m sattlint 'path with space'"
    )


def test_focused_python_files_skips_duplicates_after_normalization(monkeypatch):
    monkeypatch.setattr(
        repo_audit_entrypoints,
        "normalize_changed_files",
        lambda _changed_files: ["src/main.py", "src/main.py", "tests/test_main.py"],
    )

    assert repo_audit_entrypoints.focused_python_files(["ignored"]) == ["src/main.py", "tests/test_main.py"]


def test_print_cli_summary_prints_terminal_findings(capsys):
    repo_audit_entrypoints._print_cli_summary(
        {
            "profile": "full",
            "overall_status": "fail",
            "findings_schema": {"kind": "sattlint.findings", "schema_version": 1},
            "finding_count": 2,
            "blocking_finding_count": 1,
            "fail_on": "high",
            "status_report": "artifacts/audit/status.json",
            "summary_report": "artifacts/audit/summary.json",
            "latest_status_report": "artifacts/audit/latest/status.json",
            "latest_summary_report": "artifacts/audit/latest/summary.json",
            "findings": [
                {
                    "id": "high-risk-path",
                    "category": "portability",
                    "severity": "high",
                    "message": "Absolute path leaked into the repo.",
                    "path": "README.md",
                    "line": 12,
                    "detail": "Found a machine-specific Windows path.",
                    "suggestion": "Replace it with a repo-relative path.",
                },
                {
                    "id": "missing-doc",
                    "category": "public-readiness",
                    "severity": "low",
                    "message": "A public-facing command is undocumented.",
                    "path": None,
                    "line": None,
                    "detail": None,
                    "suggestion": None,
                },
            ],
        }
    )

    output = capsys.readouterr().out

    assert "Detailed findings:" in output
    assert "Latest status report: artifacts/audit/latest/status.json" in output
    assert "Latest summary report: artifacts/audit/latest/summary.json" in output
    assert "- HIGH portability high-risk-path [README.md:12]: Absolute path leaked into the repo." in output
    assert "  detail: Found a machine-specific Windows path." in output
    assert "  suggestion: Replace it with a repo-relative path." in output
    assert "- LOW public-readiness missing-doc: A public-facing command is undocumented." in output
    assert repo_audit_entrypoints._format_terminal_finding_path("README.md", None) == " [README.md]"


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
        "owner-pytest-coverage",
    ]
    assert commands[3]["id"] == "owner-pytest-coverage"
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


def test_build_selected_finish_gate_plan_uses_selected_surface_commands(monkeypatch, tmp_path):
    fake_repo_audit = SimpleNamespace(PIPELINE_OUTPUT_DIRNAME="pipeline", REPO_ROOT=tmp_path)
    planning_context = {
        "finish_gate_template": {
            "description": "shared pipeline gate",
            "includes": ["recommended pipeline slice", "owner pytest targets"],
        },
        "owner_test_targets": ["tests/test_pipeline_run.py"],
    }
    recommendation = {
        "recommended_check_ids": ["ruff"],
        "suggested_finish_gate_commands": ["sattlint-repo-audit --run-recommended-finish-gate"],
    }

    monkeypatch.setattr(repo_audit_entrypoints, "_repo_audit_module", lambda: fake_repo_audit)
    monkeypatch.setattr(
        repo_audit_entrypoints.pipeline_module,
        "build_pipeline_check_recommendations",
        lambda **kwargs: {
            "recommended_check_ids": ["ruff", "pyright"],
            "suggested_finish_gate_commands": [
                "sattlint-analysis-pipeline --run-recommended-finish-gate",
                "ruff check src/module.py",
            ],
        },
    )

    plan = repo_audit_entrypoints._build_selected_finish_gate_plan(
        profile="full",
        output_dir=tmp_path,
        fail_on="high",
        selected_surface="pipeline",
        changed_files=["src/module.py"],
        planning_context=planning_context,
        recommendation=recommendation,
    )

    assert plan == {
        "selected_surface": "pipeline",
        "output_dir": "pipeline",
        "command": "sattlint-analysis-pipeline --run-recommended-finish-gate",
        "commands": [
            "sattlint-analysis-pipeline --run-recommended-finish-gate",
            "ruff check src/module.py",
            "python scripts/check_ratchet_policy.py",
        ],
        "description": "shared pipeline gate",
        "includes": ["recommended pipeline slice", "owner pytest targets"],
        "owner_test_targets": ["tests/test_pipeline_run.py"],
        "recommended_check_ids": ["ruff", "pyright"],
    }


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
            "owner_test_targets": ["tests/test_repo_audit_part1.py"],
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
    work_map_path = tmp_path / "docs" / "maintainers" / "ai" / "ai-work-map.json"
    session_map_path = work_map_path.with_name("ai-session-context-map.json")
    check_catalog_path = work_map_path.with_name("ai-check-catalog.md")
    work_map_path.parent.mkdir(parents=True, exist_ok=True)
    work_map_path.write_text('{"kind": "work"}\n', encoding="utf-8")
    session_map_path.write_text('{"kind": "session"}\n', encoding="utf-8")
    check_catalog_path.write_text("# Check Catalog\n", encoding="utf-8")
    monkeypatch.setattr(ai_work_map, "DEFAULT_OUTPUT_PATH", work_map_path)
    monkeypatch.setattr(ai_work_map, "DEFAULT_SESSION_CONTEXT_OUTPUT_PATH", session_map_path)
    monkeypatch.setattr(ai_work_map, "DEFAULT_CHECK_CATALOG_OUTPUT_PATH", check_catalog_path)
    monkeypatch.setattr(ai_work_map, "render_ai_work_map", lambda: '{"kind": "work"}\n')
    monkeypatch.setattr(ai_work_map, "render_session_context_map", lambda: '{"kind": "session"}\n')
    monkeypatch.setattr(ai_work_map, "render_ai_check_catalog", lambda: "# Check Catalog\n")

    findings = repo_audit_entrypoints._run_verify_recommendations_check(None)

    assert [finding.id for finding in findings] == [
        "recommendation-missing-owner-tests-ruff",
        "recommendation-dead-path-globs-cli",
    ]
    assert findings[0].severity == "high"
    assert findings[1].detail == '{"check_id": "cli", "issue_id": "dead-path-globs", "message": "Dead path globs."}'


def test_run_verify_recommendations_check_flags_generated_artifact_drift(monkeypatch, tmp_path):
    fake_repo_audit = SimpleNamespace(
        DEFAULT_OUTPUT_DIR=tmp_path / "audit",
        PIPELINE_OUTPUT_DIRNAME="pipeline",
        REPO_ROOT=tmp_path,
        Finding=lambda **kwargs: SimpleNamespace(**kwargs),
    )
    work_map_path = tmp_path / "docs" / "maintainers" / "ai" / "ai-work-map.json"
    session_map_path = work_map_path.with_name("ai-session-context-map.json")
    check_catalog_path = work_map_path.with_name("ai-check-catalog.md")
    work_map_path.parent.mkdir(parents=True, exist_ok=True)
    work_map_path.write_text('{"kind": "stale-work"}\n', encoding="utf-8")
    session_map_path.write_text('{"kind": "stale-session"}\n', encoding="utf-8")
    check_catalog_path.write_text("stale-catalog\n", encoding="utf-8")

    monkeypatch.setattr(repo_audit_entrypoints, "_repo_audit_module", lambda: fake_repo_audit)
    monkeypatch.setattr(
        repo_audit_entrypoints.pipeline_module, "build_pipeline_check_catalog", lambda **kwargs: {"checks": []}
    )
    monkeypatch.setattr(repo_audit_entrypoints, "build_repo_audit_check_catalog", lambda **kwargs: {"checks": []})
    monkeypatch.setattr(repo_audit_entrypoints, "verify_check_catalog", lambda catalog, repo_root: {"issues": []})
    monkeypatch.setattr(ai_work_map, "DEFAULT_OUTPUT_PATH", work_map_path)
    monkeypatch.setattr(ai_work_map, "DEFAULT_SESSION_CONTEXT_OUTPUT_PATH", session_map_path)
    monkeypatch.setattr(ai_work_map, "DEFAULT_CHECK_CATALOG_OUTPUT_PATH", check_catalog_path)
    monkeypatch.setattr(ai_work_map, "render_ai_work_map", lambda: '{"kind": "fresh-work"}\n')
    monkeypatch.setattr(ai_work_map, "render_session_context_map", lambda: '{"kind": "fresh-session"}\n')
    monkeypatch.setattr(ai_work_map, "render_ai_check_catalog", lambda: "# Fresh Catalog\n")

    findings = repo_audit_entrypoints._run_verify_recommendations_check(None)

    assert [finding.id for finding in findings] == [
        "recommendation-generated-artifact-drift-ai-work-map",
        "recommendation-generated-artifact-drift-ai-session-context-map",
        "recommendation-generated-artifact-drift-ai-check-catalog",
    ]
    assert all(finding.severity == "high" for finding in findings)
    assert findings[0].path == "docs/maintainers/ai/ai-work-map.json"
    assert "python -m sattlint.devtools.ai --write" in findings[0].detail
