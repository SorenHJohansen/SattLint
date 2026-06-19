# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
from __future__ import annotations

from sattlint.devtools.audit import repo_audit
from tests import test_pipeline_run as pipeline_run_tests


def test_run_recommended_repo_audit_finish_gate_fails_when_structural_surface_proof_fails(monkeypatch, tmp_path):
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

    monkeypatch.setattr(
        repo_audit._repo_audit_entrypoints,
        "build_repo_audit_check_recommendations",
        lambda **_kwargs: recommendation,
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
        lambda **_kwargs: {"status": "pass", "mode": "changed-lines", "coverage_path": "coverage_proof.xml"},
    )
    monkeypatch.setattr(
        repo_audit.pipeline_module,
        "evaluate_change_scoped_structural_surface_proof",
        lambda **_kwargs: {
            "status": "fail",
            "checked_files": ["src/sattlint/app.py"],
            "expected_metrics": {"import_max_count": 10},
            "metrics_by_path": {"src/sattlint/app.py": {"import_max_count": 12}},
            "violations": [
                {
                    "path": "src/sattlint/app.py",
                    "metric": "import_max_count",
                    "label": "imports",
                    "actual": 12,
                    "expected_max": 10,
                }
            ],
            "scan_failures": [],
            "reason": "Changed structural Python files would raise a recorded structural surface ceiling.",
        },
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

    assert result["overall_status"] == "fail"
    assert result["finish_gate"]["status"] == "fail"
    assert result["finish_gate"]["structural_surface_proof"]["status"] == "fail"
    assert result["finish_gate"]["commands"][-1]["id"] == "changed-file-structural-surface"


def test_run_recommended_pipeline_finish_gate_records_structural_surface_proof(monkeypatch, tmp_path):
    recommendation = {
        "changed_files": ["src/sattlint/devtools/repo_audit.py"],
        "recommended_check_ids": ["ruff", "pyright", "pytest"],
        "recommended_checks": [{"owner_test_targets": ["tests/test_pipeline_run.py"]}],
        "proof_requirements": {
            "focused_behavior_test": {
                "required": True,
                "status": "satisfied",
                "owner_test_targets": ["tests/test_pipeline_run.py"],
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
        pipeline_run_tests.pipeline, "build_pipeline_check_recommendations", lambda **_kwargs: recommendation
    )
    monkeypatch.setattr(
        pipeline_run_tests.pipeline,
        "_run_pipeline",
        lambda *_args, **_kwargs: {"status": {"overall_status": "pass"}},
    )
    monkeypatch.setattr(
        pipeline_run_tests.pipeline,
        "_run_command",
        lambda name, command, cwd=pipeline_run_tests.pipeline.REPO_ROOT: pipeline_run_tests.pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=0,
            duration_seconds=0.0,
            stdout="",
            stderr="",
        ),
    )
    monkeypatch.setattr(
        pipeline_run_tests.pipeline,
        "evaluate_change_scoped_coverage_proof",
        lambda **_kwargs: {"status": "pass", "mode": "changed-lines", "coverage_path": "coverage_proof.xml"},
    )
    monkeypatch.setattr(
        pipeline_run_tests.pipeline,
        "evaluate_change_scoped_structural_surface_proof",
        lambda **_kwargs: {
            "status": "pass",
            "checked_files": ["src/sattlint/devtools/repo_audit.py"],
            "expected_metrics": {"import_max_count": 133},
            "metrics_by_path": {"src/sattlint/devtools/repo_audit.py": {"import_max_count": 9}},
            "violations": [],
            "scan_failures": [],
            "reason": "Changed structural Python files stay within the recorded surface ceilings.",
        },
    )

    result = pipeline_run_tests.pipeline.run_recommended_pipeline_finish_gate(
        tmp_path,
        trace_target=None,
        profile="full",
        include_vulture=False,
        include_bandit=False,
        baseline_findings=None,
        corpus_manifest_dir=None,
        changed_files=["src/sattlint/devtools/repo_audit.py"],
        slow_phase_threshold_ms=25.0,
        phase_budget_ms=50.0,
        total_budget_ms=250.0,
        fail_on_drift=False,
        fail_on_budget=False,
    )

    assert result["finish_gate"]["status"] == "pass"
    assert result["finish_gate"]["structural_surface_proof"]["status"] == "pass"
