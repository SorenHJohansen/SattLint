import json
import runpy
import sys
from unittest.mock import patch

import pytest

from sattlint.devtools import repo_audit


def test_run_check_my_changes_ai_feedback_prefers_failed_finish_gate_step(monkeypatch, tmp_path):
    recommendation = {
        "changed_files": ["src/sattlint/app.py"],
        "fallback_required": False,
        "fallback_reason": None,
        "recommended_check_ids": ["cli"],
        "recommended_pipeline_check_ids": [],
        "recommended_repo_audit_check_ids": ["cli"],
    }

    with (
        patch.object(
            repo_audit._repo_audit_entrypoints, "build_repo_audit_check_recommendations", return_value=recommendation
        ),
        patch.object(
            repo_audit._repo_audit_entrypoints,
            "run_recommended_repo_audit_finish_gate",
            return_value={
                "overall_status": "fail",
                "finish_gate": {
                    "status": "fail",
                    "commands": [
                        {
                            "id": "ruff",
                            "label": "Ruff on touched files",
                            "command": "ruff check src/sattlint/app.py",
                            "exit_code": 1,
                            "status": "fail",
                        }
                    ],
                },
            },
        ),
        patch.object(repo_audit.pipeline_module, "run_recommended_pipeline_finish_gate"),
    ):
        report = repo_audit.run_check_my_changes(
            tmp_path,
            profile="full",
            fail_on="high",
            include_generated=False,
            suspicious_identifiers=[],
            skip_vulture=False,
            skip_bandit=False,
            changed_files=["src/sattlint/app.py"],
        )

    feedback_payload = json.loads((tmp_path / "ai_feedback.json").read_text(encoding="utf-8"))

    assert report["ai_feedback"]["first_failed_step"]["id"] == "ruff"
    assert feedback_payload["first_failed_step"]["command"] == "ruff check src/sattlint/app.py"
    assert feedback_payload["suggested_next_command"] == "ruff check src/sattlint/app.py"


def test_main_check_my_changes_prints_machine_readable_report(monkeypatch, tmp_path, capsys):
    report = {
        "kind": "sattlint.check_my_changes",
        "schema_version": 1,
        "selected_surface": "pipeline",
        "overall_status": "pass",
    }

    with patch.object(repo_audit, "run_check_my_changes", return_value=report) as run_check_my_changes:
        exit_code = repo_audit.main(["--check-my-changes", "--output-dir", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["kind"] == "sattlint.check_my_changes"
    assert payload["selected_surface"] == "pipeline"
    assert run_check_my_changes.call_args.args[0] == tmp_path


def test_main_check_my_changes_compacts_verbose_report_fields(monkeypatch, tmp_path, capsys):
    changed_files = [f"src/module_{index}.py" for index in range(15)]
    long_command = "pyright " + " ".join(changed_files * 3)
    report = {
        "kind": "sattlint.check_my_changes",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "profile": "full",
        "fail_on": "high",
        "output_dir": str(tmp_path),
        "report_path": str(tmp_path / "check_my_changes.json"),
        "changed_files": changed_files,
        "selected_surface": "repo-audit",
        "selected_reason": "Repo-audit-specific checks were recommended.",
        "selected_command": long_command,
        "overall_status": "fail",
        "finish_gate_status": "fail",
        "reports": {
            "check_my_changes": "artifacts/audit/check_my_changes.json",
            "ai_feedback": "artifacts/audit/ai_feedback.json",
        },
        "planning_context": {"primary_agent": "Repo Audit"},
        "recommendation": {"recommended_check_ids": ["ruff", "pyright", "pytest"]},
        "ai_feedback": {
            "first_failed_step": {
                "id": "pyright-touched-python",
                "label": "Run Pyright on touched Python files",
                "command": long_command,
                "exit_code": 1,
            },
            "suggested_next_command": long_command,
        },
    }

    with patch.object(repo_audit, "run_check_my_changes", return_value=report):
        exit_code = repo_audit.main(["--check-my-changes", "--output-dir", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["changed_file_count"] == 15
    assert len(payload["changed_files"]) == 12
    assert payload["changed_files_truncated"] is True
    assert payload["changed_file_overflow_count"] == 3
    assert payload["selected_command_truncated"] is True
    assert payload["first_failed_step"]["command_truncated"] is True
    assert payload["suggested_next_command_truncated"] is True
    assert "planning_context" not in payload
    assert "ai_feedback" not in payload


def test_main_recommend_checks_compacts_verbose_report_fields(monkeypatch, tmp_path, capsys):
    changed_files = [f"src/module_{index}.py" for index in range(15)]
    long_command = "pyright " + " ".join(changed_files * 3)
    report = {
        "kind": "sattlint.repo_audit.check_recommendations",
        "schema_version": 1,
        "profile": "full",
        "fail_on": "high",
        "changed_files": changed_files,
        "fallback_required": True,
        "fallback_reason": "Changed files touch the repo-audit control surface.",
        "recommended_check_ids": ["ruff", "pyright", "pytest", "verify-recommendations"],
        "recommended_pipeline_check_ids": ["ruff", "pyright", "pytest"],
        "recommended_repo_audit_check_ids": ["verify-recommendations"],
        "suggested_check_commands": [long_command] * 10,
        "suggested_finish_gate_commands": [long_command] * 11,
        "proof_requirements": {
            "coverage": {
                "required": True,
                "preferred_mode": "changed-lines",
                "fallback_mode": "touched-files",
                "touched_source_files": changed_files,
            }
        },
        "recommended_checks": [{"id": "ruff", "command": long_command}] * 20,
    }

    with patch.object(repo_audit, "build_repo_audit_check_recommendations", return_value=report):
        exit_code = repo_audit.main(
            ["--recommend-checks", "--output-dir", str(tmp_path), "--changed-file", "src/demo.py"]
        )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["changed_file_count"] == 15
    assert len(payload["changed_files"]) == 12
    assert payload["suggested_check_command_count"] == 10
    assert payload["suggested_check_commands_truncated"] is True
    assert payload["suggested_check_commands_with_truncated_text"] == 8
    assert payload["suggested_finish_gate_command_count"] == 11
    assert payload["suggested_finish_gate_commands_truncated"] is True
    assert payload["proof_requirements"]["coverage"]["touched_source_file_count"] == 15
    assert "recommended_checks" not in payload


def test_main_planning_context_compacts_verbose_report_fields(monkeypatch, tmp_path, capsys):
    changed_files = [f"src/module_{index}.py" for index in range(15)]
    long_command = "pyright " + " ".join(changed_files * 3)
    report = {
        "kind": "sattlint.planning_context",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "profile": "full",
        "fail_on": "high",
        "output_dir": str(tmp_path),
        "changed_files": changed_files,
        "owning_surface": "repo-audit",
        "selected_surface": "repo-audit",
        "selected_reason": "Repo-audit-specific checks were recommended.",
        "recommendation": {
            "fallback_required": True,
            "fallback_reason": "Changed files touch the repo-audit control surface.",
            "recommended_check_ids": ["ruff", "pyright", "pytest", "verify-recommendations"],
            "recommended_pipeline_check_ids": ["ruff", "pyright", "pytest"],
            "recommended_repo_audit_check_ids": ["verify-recommendations"],
        },
        "proof_requirements": {
            "focused_behavior_test": {
                "required": True,
                "status": "satisfied",
                "owner_test_targets": [f"tests/test_{index}.py" for index in range(12)],
            }
        },
        "planning_context": {
            "primary_agent": "Repo Audit",
            "instruction_files": [{"name": f"Instruction {index}"} for index in range(11)],
            "owner_surfaces": [f"surface-{index}" for index in range(10)],
            "owner_test_targets": [f"tests/test_{index}.py" for index in range(11)],
            "first_validation_commands": [long_command] * 10,
            "blocking_invariants": [
                {"id": f"rule-{index}", "summary": f"Summary {index}", "details": "ignored"} for index in range(10)
            ],
            "finish_gate": {
                "selected_surface": "repo-audit",
                "output_dir": str(tmp_path),
                "command": long_command,
                "commands": [long_command] * 10,
                "includes": [f"include-{index}" for index in range(10)],
                "owner_test_targets": [f"tests/test_{index}.py" for index in range(10)],
                "recommended_check_ids": [f"check-{index}" for index in range(10)],
            },
        },
        "finish_gate": {
            "selected_surface": "repo-audit",
            "output_dir": str(tmp_path),
            "command": long_command,
            "commands": [long_command] * 10,
        },
    }

    with patch.object(
        repo_audit._repo_audit_entrypoints,
        "build_check_my_changes_planning_report",
        return_value=report,
    ):
        exit_code = repo_audit.main(
            ["--planning-context", "--output-dir", str(tmp_path), "--changed-file", "src/demo.py"]
        )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["changed_file_count"] == 15
    assert len(payload["changed_files"]) == 12
    assert payload["planning_context"]["instruction_name_count"] == 11
    assert payload["planning_context"]["instruction_names_truncated"] is True
    assert payload["planning_context"]["owner_surface_count"] == 10
    assert payload["planning_context"]["first_validation_command_count"] == 10
    assert payload["planning_context"]["first_validation_commands_with_truncated_text"] == 8
    assert payload["planning_context"]["blocking_invariants_truncated"] is True
    assert payload["planning_context"]["finish_gate"]["command_truncated"] is True
    assert payload["planning_context"]["finish_gate"]["command_count"] == 10
    assert "instruction_files" not in payload["planning_context"]


def test_main_apply_ai_gc_calls_apply_helper(monkeypatch, tmp_path, capsys):
    report = {
        "kind": "sattlint.ai_gc",
        "schema_version": 1,
        "status": "pass",
        "summary": {"candidate_count": 1, "applied_count": 1, "failure_count": 0},
        "candidates": [],
        "applied_actions": [{"path": "scratch/audit-review-old", "action": "delete"}],
        "failures": [],
    }

    with patch.object(repo_audit, "apply_ai_gc", return_value=report) as apply_ai_gc:
        exit_code = repo_audit.main(["--apply-ai-gc", "--output-dir", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["kind"] == "sattlint.ai_gc"
    assert apply_ai_gc.call_args.kwargs["output_dir"] == tmp_path


def test_repo_audit_module_main_runs_help(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["repo_audit", "--help"])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("sattlint.devtools.repo_audit", run_name="__main__")

    assert exit_info.value.code == 0
