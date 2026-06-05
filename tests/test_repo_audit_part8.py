# ruff: noqa: F403, F405
from ._repo_audit_test_support import *


def test_main_check_routes_finding_checks(monkeypatch, tmp_path):
    summary = {
        "profile": "full",
        "output_dir": f"<external>/{tmp_path.name}",
        "finding_count": 1,
        "findings_schema": {"kind": "sattlint.findings", "schema_version": 1},
        "findings": [
            {
                "id": "public-readiness-example",
                "category": "public-readiness",
                "severity": "medium",
                "confidence": "high",
                "message": "Example terminal-visible finding.",
                "path": "README.md",
                "line": 12,
                "detail": "This should be printed to the terminal summary.",
                "suggestion": "Fix the example issue.",
                "source": "custom",
                "history_cleanup_recommended": False,
            }
        ],
    }

    with (
        patch.object(repo_audit, "_run_repo_audit_findings_checks", return_value=summary) as run_checks,
        patch.object(repo_audit, "_print_cli_summary") as print_cli_summary,
    ):
        exit_code = repo_audit.main(["--check", "public-readiness", "--output-dir", str(tmp_path), "--skip-pipeline"])

    assert exit_code == 0
    assert run_checks.call_args.kwargs["check_ids"] == ("public-readiness",)
    printed = print_cli_summary.call_args.args[0]
    assert printed["overall_status"] == "pass"
    assert printed["findings"] == summary["findings"]


def test_main_check_cli_consistency_exits_nonzero_and_writes_report(monkeypatch, tmp_path):
    cli_report = {
        "kind": "sattlint.cli_consistency",
        "schema_version": 1,
        "declared": {"scripts": ["sattlint"], "subcommands": ["syntax-check"]},
        "gaps": {
            "undeclared_subcommands": [{"subcommand": "ghost", "path": "README.md", "line": 1}],
            "undeclared_scripts": [],
            "undocumented_subcommands": [],
            "undocumented_scripts": [],
        },
        "summary": {
            "undeclared_subcommand_count": 1,
            "undeclared_script_count": 0,
            "undocumented_subcommand_count": 0,
            "undocumented_script_count": 0,
            "gap_count": 1,
        },
        "status": "fail",
    }

    with (
        patch.object(repo_audit, "build_cli_consistency_report", return_value=cli_report),
        patch.object(repo_audit, "_print_cli_summary"),
    ):
        exit_code = repo_audit.main(["--check", "cli-consistency", "--output-dir", str(tmp_path), "--skip-pipeline"])

    status_report = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    findings_report = json.loads((tmp_path / "findings.json").read_text(encoding="utf-8"))

    assert exit_code == 1
    assert (tmp_path / "cli_consistency.json").exists()
    assert status_report["overall_status"] == "fail"
    assert status_report["selected_checks"] == ["cli-consistency"]
    assert findings_report["finding_count"] == 1


def test_run_check_my_changes_uses_pipeline_finish_gate_when_no_repo_checks_are_recommended(monkeypatch, tmp_path):
    recommendation = {
        "changed_files": ["src/sattlint/devtools/pipeline.py"],
        "fallback_required": False,
        "fallback_reason": None,
        "recommended_check_ids": ["ruff", "pyright", "pytest"],
        "recommended_pipeline_check_ids": ["ruff", "pyright", "pytest"],
        "recommended_repo_audit_check_ids": [],
    }

    with (
        patch.object(
            repo_audit._repo_audit_entrypoints, "build_repo_audit_check_recommendations", return_value=recommendation
        ),
        patch.object(
            repo_audit.pipeline_module,
            "run_recommended_pipeline_finish_gate",
            return_value={
                "overall_status": "pass",
                "finish_gate": {"status": "pass", "timing": {"critical_path_duration_seconds": 1.25}},
                "pipeline_summary": {"timing": {"total_duration_seconds": 2.5}},
            },
        ) as run_pipeline_finish_gate,
        patch.object(
            repo_audit.pipeline_module,
            "run_command",
            return_value=repo_audit.pipeline_module.CommandResult(
                name="ratchet-policy",
                command=["python", "scripts/check_ratchet_policy.py"],
                exit_code=0,
                duration_seconds=0.1,
                stdout="",
                stderr="",
            ),
        ) as run_command,
        patch.object(repo_audit, "run_recommended_repo_audit_finish_gate") as run_repo_finish_gate,
    ):
        report = repo_audit.run_check_my_changes(
            tmp_path,
            profile="full",
            fail_on="high",
            include_generated=False,
            suspicious_identifiers=[],
            skip_vulture=False,
            skip_bandit=False,
            changed_files=["src/sattlint/devtools/pipeline.py"],
            pytest_workers="2",
        )

    assert report["selected_surface"] == "pipeline"
    assert report["overall_status"] == "pass"
    assert "sattlint-analysis-pipeline" in report["selected_command"]
    assert "--pytest-workers 2" in report["selected_command"]
    assert report["reports"]["finish_gate"].endswith("/pipeline/finish_gate.json")
    assert report["reports"]["ai_feedback"].endswith("/ai_feedback.json")
    assert report["timing"]["selected_run"]["total_duration_seconds"] == 2.5
    assert report["timing"]["finish_gate"]["critical_path_duration_seconds"] == 1.35
    assert (tmp_path / "check_my_changes.json").exists()
    assert (tmp_path / "ai_feedback.json").exists()
    assert run_command.call_args.args == (
        "ratchet-policy",
        [repo_audit.pipeline_module.resolve_python_executable(), "scripts/check_ratchet_policy.py"],
    )
    assert run_pipeline_finish_gate.called
    assert not run_repo_finish_gate.called


def test_run_check_my_changes_uses_repo_audit_finish_gate_when_repo_checks_are_recommended(monkeypatch, tmp_path):
    recommendation = {
        "changed_files": ["docs/references/cli-commands.md"],
        "fallback_required": False,
        "fallback_reason": None,
        "recommended_check_ids": ["documented-commands", "cli-consistency"],
        "recommended_pipeline_check_ids": [],
        "recommended_repo_audit_check_ids": ["documented-commands", "cli-consistency"],
    }

    with (
        patch.object(
            repo_audit._repo_audit_entrypoints, "build_repo_audit_check_recommendations", return_value=recommendation
        ),
        patch.object(
            repo_audit._repo_audit_entrypoints,
            "run_recommended_repo_audit_finish_gate",
            return_value={"overall_status": "pass", "finish_gate": {"status": "pass"}},
        ) as run_repo_finish_gate,
        patch.object(repo_audit.pipeline_module, "run_recommended_pipeline_finish_gate") as run_pipeline_finish_gate,
    ):
        report = repo_audit.run_check_my_changes(
            tmp_path,
            profile="full",
            fail_on="high",
            include_generated=False,
            suspicious_identifiers=[],
            skip_vulture=False,
            skip_bandit=False,
            changed_files=["docs/references/cli-commands.md"],
            pytest_workers="2",
        )

    assert report["selected_surface"] == "repo-audit"
    assert report["overall_status"] == "pass"
    assert "sattlint-repo-audit" in report["selected_command"]
    assert "--pytest-workers 2" in report["selected_command"]
    assert report["reports"]["finish_gate"].endswith("/finish_gate.json")
    assert report["reports"]["ai_feedback"].endswith("/ai_feedback.json")
    assert run_repo_finish_gate.called
    assert not run_pipeline_finish_gate.called


def test_run_check_my_changes_writes_run_history(monkeypatch, tmp_path):
    recommendation = {
        "changed_files": ["docs/references/cli-commands.md"],
        "fallback_required": False,
        "fallback_reason": None,
        "recommended_check_ids": ["documented-commands", "cli-consistency"],
        "recommended_pipeline_check_ids": [],
        "recommended_repo_audit_check_ids": ["documented-commands", "cli-consistency"],
    }

    with (
        patch.object(
            repo_audit._repo_audit_entrypoints, "build_repo_audit_check_recommendations", return_value=recommendation
        ),
        patch.object(
            repo_audit._repo_audit_entrypoints,
            "run_recommended_repo_audit_finish_gate",
            return_value={"overall_status": "pass", "finish_gate": {"status": "pass"}},
        ),
        patch.object(repo_audit.pipeline_module, "run_recommended_pipeline_finish_gate"),
    ):
        repo_audit.run_check_my_changes(
            tmp_path,
            profile="full",
            fail_on="high",
            include_generated=False,
            suspicious_identifiers=[],
            skip_vulture=False,
            skip_bandit=False,
            changed_files=["docs/references/cli-commands.md"],
        )

    run_history = json.loads((tmp_path / "run_history.json").read_text(encoding="utf-8"))

    assert run_history["run_count"] == 1
    assert run_history["runs"][0]["report_kind"] == "check_my_changes"
    assert run_history["runs"][0]["selected_surface"] == "repo-audit"
    assert run_history["runs"][0]["changed_files"] == ["docs/references/cli-commands.md"]


def test_run_check_my_changes_includes_planning_context(monkeypatch, tmp_path):
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
            return_value={"overall_status": "pass", "finish_gate": {"status": "pass"}},
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

    assert report["planning_context"]["primary_agent"] == "CLI App Menu"
    assert report["planning_context"]["owner_surfaces"] == ["cli"]
    assert report["planning_context"]["owner_test_targets"] == ["tests/test_repo_audit_part1.py"]
    assert any(item["name"] == "CLI App Instructions" for item in report["planning_context"]["instruction_files"])
    assert report["planning_context"]["nearest_owner_suites"] == []
    assert report["planning_context"]["first_validation_commands"] == []
    assert report["planning_context"]["finish_gate"]["selected_surface"] == "repo-audit"
    assert any(item["id"] == "focused-validation-first" for item in report["planning_context"]["blocking_invariants"])
    assert report["proof_requirements"]["focused_behavior_test"]["required"] is True
    assert report["ai_feedback"]["primary_agent"] == "CLI App Menu"
    assert (
        report["ai_feedback"]["first_validation_commands"]
        == report["planning_context"]["first_validation_commands"][:3]
    )


def test_run_recommended_repo_audit_finish_gate_fails_when_change_scoped_coverage_fails(monkeypatch, tmp_path):
    recommendation = {
        "changed_files": ["src/sattlint/devtools/repo_audit.py"],
        "recommended_checks": [{"owner_test_targets": ["tests/test_repo_audit_part8.py"]}],
        "proof_requirements": {
            "focused_behavior_test": {
                "required": True,
                "status": "satisfied",
                "owner_test_targets": ["tests/test_repo_audit_part8.py"],
                "reason": "Code changes require at least one focused owner pytest target.",
            },
            "coverage": {
                "required": True,
                "preferred_mode": "changed-lines",
                "fallback_mode": "touched-files",
                "touched_source_files": ["src/sattlint/devtools/repo_audit.py"],
                "reason": "Touched source files should be proven by focused coverage.",
            },
            "mutation_guidance": {
                "status": "advisory",
                "critical_surfaces": ["routing"],
                "suggested_commands": [],
                "suggestion": "Prefer mutation-style or property-style assertions.",
            },
        },
    }

    monkeypatch.setattr(
        repo_audit._repo_audit_entrypoints, "build_repo_audit_check_recommendations", lambda **_kwargs: recommendation
    )
    monkeypatch.setattr(
        repo_audit._repo_audit_entrypoints,
        "run_recommended_repo_audit_slice",
        lambda *_args, **_kwargs: {"overall_status": "pass"},
    )
    monkeypatch.setattr(
        repo_audit.pipeline_module,
        "_run_command",
        lambda name, command, cwd=repo_audit.pipeline_module.REPO_ROOT: repo_audit.pipeline_module.CommandResult(
            name=name,
            command=command,
            exit_code=0,
            duration_seconds=0.0,
            stdout="",
            stderr="",
        ),
    )
    monkeypatch.setattr(
        repo_audit.pipeline_module,
        "evaluate_change_scoped_coverage_proof",
        lambda **_kwargs: {"status": "fail", "mode": "changed-lines", "coverage_path": "coverage_proof.xml"},
    )

    result = repo_audit.run_recommended_repo_audit_finish_gate(
        tmp_path,
        profile="full",
        fail_on="high",
        include_generated=False,
        suspicious_identifiers=[],
        skip_vulture=False,
        skip_bandit=False,
        changed_files=["src/sattlint/devtools/repo_audit.py"],
    )

    assert result["overall_status"] == "fail"
    assert result["finish_gate"]["status"] == "fail"
    assert result["finish_gate"]["coverage_proof"]["mode"] == "changed-lines"


def test_run_recommended_repo_audit_finish_gate_runs_ratchet_policy(monkeypatch, tmp_path):
    recommendation = {
        "changed_files": ["src/sattlint/app.py"],
        "recommended_checks": [{"owner_test_targets": ["tests/test_app.py"]}],
        "proof_requirements": {
            "focused_behavior_test": {
                "required": True,
                "status": "satisfied",
                "owner_test_targets": ["tests/test_app.py"],
                "reason": "Code changes require at least one focused owner pytest target.",
            },
            "coverage": {
                "required": True,
                "preferred_mode": "changed-lines",
                "fallback_mode": "touched-files",
                "touched_source_files": ["src/sattlint/app.py"],
                "reason": "Touched source files should be proven by focused coverage.",
            },
            "mutation_guidance": {
                "status": "advisory",
                "critical_surfaces": [],
                "suggested_commands": [],
                "suggestion": "",
            },
        },
    }
    executed_steps: list[tuple[str, list[str]]] = []

    monkeypatch.setattr(
        repo_audit._repo_audit_entrypoints, "build_repo_audit_check_recommendations", lambda **_kwargs: recommendation
    )
    monkeypatch.setattr(
        repo_audit._repo_audit_entrypoints,
        "run_recommended_repo_audit_slice",
        lambda *_args, **_kwargs: {"overall_status": "pass"},
    )

    def _record_step(name, command, cwd=repo_audit.pipeline_module.REPO_ROOT):
        executed_steps.append((name, list(command)))
        return repo_audit.pipeline_module.CommandResult(
            name=name,
            command=command,
            exit_code=0,
            duration_seconds=0.0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(repo_audit.pipeline_module, "_run_command", _record_step)
    monkeypatch.setattr(
        repo_audit.pipeline_module,
        "evaluate_change_scoped_coverage_proof",
        lambda **_kwargs: {"status": "pass", "mode": "changed-lines", "coverage_path": "coverage_proof.xml"},
    )

    result = repo_audit.run_recommended_repo_audit_finish_gate(
        tmp_path,
        profile="full",
        fail_on="high",
        include_generated=False,
        suspicious_identifiers=[],
        skip_vulture=False,
        skip_bandit=False,
        changed_files=["src/sattlint/app.py"],
    )

    executed_step_commands = dict(executed_steps)
    assert set(executed_step_commands) == {
        "ruff-touched-python",
        "pyright-touched-python",
        "ratchet-policy",
        "owner-pytest-coverage",
    }
    assert executed_step_commands["ratchet-policy"][1:] == ["scripts/check_ratchet_policy.py"]
    assert [step["id"] for step in result["finish_gate"]["commands"]] == [
        "ruff-touched-python",
        "pyright-touched-python",
        "ratchet-policy",
        "owner-pytest-coverage",
    ]
    assert result["finish_gate"]["status"] == "pass"
