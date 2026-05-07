import json
from unittest.mock import patch

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


def test_main_apply_ai_gc_calls_apply_helper(monkeypatch, tmp_path, capsys):
    report = {
        "kind": "sattlint.ai_gc",
        "schema_version": 1,
        "status": "pass",
        "summary": {"candidate_count": 1, "applied_count": 1, "failure_count": 0},
        "candidates": [],
        "applied_actions": [{"path": "artifacts/audit-review-old", "action": "delete"}],
        "failures": [],
    }

    with patch.object(repo_audit, "apply_ai_gc", return_value=report) as apply_ai_gc:
        exit_code = repo_audit.main(["--apply-ai-gc", "--output-dir", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["kind"] == "sattlint.ai_gc"
    assert apply_ai_gc.call_args.kwargs["output_dir"] == tmp_path
