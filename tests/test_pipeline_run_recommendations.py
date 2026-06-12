# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false
from __future__ import annotations

import json
import runpy
import sys
from unittest.mock import patch

import pytest

from sattlint.devtools.pipeline import _pipeline_cli as pipeline_cli_helpers
from tests import test_pipeline_run as pipeline_run_tests


def test_build_pipeline_check_recommendations_routes_changed_files_to_matching_checks(tmp_path):
    recommendations = pipeline_run_tests.pipeline.build_pipeline_check_recommendations(
        profile="full",
        output_dir=tmp_path,
        changed_files=["src/sattlint/devtools/repo_audit.py"],
    )

    recommended_ids = set(recommendations["recommended_check_ids"])

    assert recommendations["kind"] == "sattlint.pipeline.check_recommendations"
    assert recommendations["fallback_required"] is False
    assert {"ruff", "pyright", "pytest", "vulture", "bandit"} <= recommended_ids
    assert "trace" not in recommended_ids
    assert recommendations["suggested_check_commands"]
    assert recommendations["suggested_finish_gate_commands"]
    assert recommendations["proof_requirements"]["focused_behavior_test"]["required"] is True
    assert recommendations["proof_requirements"]["focused_behavior_test"]["status"] == "satisfied"
    assert recommendations["proof_requirements"]["coverage"]["required"] is True
    assert recommendations["proof_requirements"]["coverage"]["touched_source_files"] == [
        "src/sattlint/devtools/repo_audit.py"
    ]
    assert "routing" in recommendations["proof_requirements"]["mutation_guidance"]["critical_surfaces"]
    assert recommendations["why_this_gate"]["matched_routes"]


def test_build_pipeline_check_recommendations_limits_control_surface_fallback(tmp_path):
    recommendations = pipeline_run_tests.pipeline.build_pipeline_check_recommendations(
        profile="full",
        output_dir=tmp_path,
        changed_files=["src/sattlint/devtools/pipeline.py"],
    )

    assert recommendations["fallback_required"] is True
    assert recommendations["recommended_check_ids"] == ["ruff", "pyright", "pytest"]


def test_run_recommended_pipeline_finish_gate_records_change_scoped_coverage(monkeypatch, tmp_path):
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
    assert result["finish_gate"]["coverage_proof"]["mode"] == "changed-lines"
    assert any(command["id"] == "owner-pytest-coverage" for command in result["finish_gate"]["commands"])


def test_main_recommend_checks_prints_json(tmp_path, capsys):
    exit_code = pipeline_run_tests.pipeline.main(
        [
            "--profile",
            "full",
            "--output-dir",
            str(tmp_path),
            "--recommend-checks",
            "--changed-file",
            "src/sattlint/devtools/repo_audit.py",
        ]
    )

    payload = pipeline_run_tests.json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["kind"] == "sattlint.pipeline.check_recommendations"
    assert "ruff" in payload["recommended_check_ids"]


def test_main_list_checks_prints_json(tmp_path, capsys):
    exit_code = pipeline_run_tests.pipeline.main(
        [
            "--profile",
            "full",
            "--output-dir",
            str(tmp_path),
            "--list-checks",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["kind"] == "sattlint.pipeline.check_catalog"


def test_main_rejects_conflicting_check_modes(tmp_path):
    with pytest.raises(SystemExit):
        pipeline_run_tests.pipeline.main(
            [
                "--profile",
                "full",
                "--output-dir",
                str(tmp_path),
                "--check",
                "ruff",
                "--recommend-checks",
            ]
        )


def test_main_run_recommended_slice_uses_recommended_check_ids(monkeypatch, tmp_path):
    observed: dict[str, object] = {}

    def fake_run_pipeline(output_dir, **kwargs):
        observed["selected_checks"] = kwargs["selected_checks"]
        observed["pytest_workers"] = kwargs["pytest_workers"]
        return {
            "profile": "full",
            "output_dir": f"<external>/{tmp_path.name}",
            "status": {"overall_status": "pass", "tool_statuses": {}},
            "reports": {},
            "counts": {
                "baseline_new_findings": 0,
                "baseline_resolved_findings": 0,
                "baseline_changed_findings": 0,
                "baseline_unchanged_findings": 0,
            },
            "findings_schema": {"kind": "sattlint.findings", "schema_version": 1},
        }

    monkeypatch.setattr(pipeline_run_tests.pipeline, "_run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(pipeline_run_tests.pipeline, "_print_cli_summary", lambda *_args, **_kwargs: None)

    exit_code = pipeline_run_tests.pipeline.main(
        [
            "--profile",
            "full",
            "--output-dir",
            str(tmp_path),
            "--run-recommended-slice",
            "--pytest-workers",
            "4",
            "--changed-file",
            "tests/test_repo_audit_part8.py",
        ]
    )

    assert exit_code == 0
    assert observed["selected_checks"]
    assert observed["pytest_workers"] == "4"


def test_main_run_recommended_slice_supports_json_summary_output(monkeypatch, tmp_path, capsys):
    observed = {"printed": False}

    monkeypatch.setattr(
        pipeline_run_tests.pipeline,
        "build_pipeline_check_recommendations",
        lambda **_kwargs: {"recommended_check_ids": ["ruff"]},
    )
    monkeypatch.setattr(
        pipeline_run_tests.pipeline,
        "_run_pipeline",
        lambda *_args, **_kwargs: {
            "profile": "full",
            "output_dir": f"<external>/{tmp_path.name}",
            "status": {"overall_status": "pass", "tool_statuses": {}},
            "reports": {},
            "counts": {
                "baseline_new_findings": 0,
                "baseline_resolved_findings": 0,
                "baseline_changed_findings": 0,
                "baseline_unchanged_findings": 0,
            },
            "findings_schema": {"kind": "sattlint.findings", "schema_version": 1},
        },
    )
    monkeypatch.setattr(
        pipeline_run_tests.pipeline,
        "_print_cli_summary",
        lambda *_args, **_kwargs: observed.__setitem__("printed", True),
    )

    exit_code = pipeline_run_tests.pipeline.main(
        [
            "--profile",
            "full",
            "--output-dir",
            str(tmp_path),
            "--run-recommended-slice",
            "--format",
            "json",
            "--changed-file",
            "tests/test_repo_audit_part8.py",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["overall_status"] == "pass"
    assert payload["profile"] == "full"
    assert observed["printed"] is False


def test_main_run_recommended_finish_gate_uses_finish_gate_runner(monkeypatch, tmp_path):
    summary = {
        "profile": "full",
        "output_dir": f"<external>/{tmp_path.name}",
        "status": {"overall_status": "pass", "tool_statuses": {}},
        "reports": {},
        "counts": {
            "baseline_new_findings": 0,
            "baseline_resolved_findings": 0,
            "baseline_changed_findings": 0,
            "baseline_unchanged_findings": 0,
        },
        "findings_schema": {"kind": "sattlint.findings", "schema_version": 1},
    }

    with (
        patch.object(
            pipeline_run_tests.pipeline,
            "run_recommended_pipeline_finish_gate",
            return_value={"pipeline_summary": summary, "overall_status": "pass"},
        ) as run_finish_gate,
        patch.object(pipeline_run_tests.pipeline, "_print_cli_summary") as print_cli_summary,
    ):
        exit_code = pipeline_run_tests.pipeline.main(
            [
                "--profile",
                "full",
                "--output-dir",
                str(tmp_path),
                "--run-recommended-finish-gate",
                "--pytest-workers",
                "2",
                "--changed-file",
                "src/sattlint/devtools/repo_audit.py",
            ]
        )

    assert exit_code == 0
    assert run_finish_gate.call_args.kwargs["changed_files"] == ["src/sattlint/devtools/repo_audit.py"]
    assert run_finish_gate.call_args.kwargs["pytest_workers"] == "2"
    printed = print_cli_summary.call_args.args[0]
    assert printed["overall_status"] == "pass"


def test_pipeline_module_main_entrypoint_executes_main(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        pipeline_cli_helpers,
        "build_pipeline_check_catalog",
        lambda **kwargs: {"kind": "sattlint.pipeline.check_catalog", "checks": []},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["pipeline", "--list-checks", "--output-dir", str(tmp_path)],
    )

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("sattlint.devtools.pipeline", run_name="__main__")

    payload = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 0
    assert payload["kind"] == "sattlint.pipeline.check_catalog"
