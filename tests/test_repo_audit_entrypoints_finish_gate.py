from __future__ import annotations

import json
from types import SimpleNamespace

from sattlint.devtools.audit import repo_audit, repo_audit_entrypoints


def _artifact_path(*parts: str) -> str:
    return "/".join(("<external>", *parts))


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
    run_results = {
        "ruff-touched-python": SimpleNamespace(exit_code=0, duration_seconds=0.1),
        "pyright-touched-python": SimpleNamespace(exit_code=1, duration_seconds=0.2),
        "owner-pytest-coverage": SimpleNamespace(exit_code=0, duration_seconds=0.4),
    }

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
    monkeypatch.setattr(
        repo_audit_entrypoints.pipeline_module,
        "_run_command",
        lambda step_id, _argv: run_results[step_id],
    )
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
        "owner-pytest-coverage",
    ]
    assert finish_gate["commands"][1]["status"] == "fail"
    assert finish_gate["commands"][1]["exit_code"] == 1
    assert finish_gate["owner_test_targets"] == ["tests/test_app.py"]


def test_build_repo_audit_finish_gate_commands_include_pytest_workers(monkeypatch, tmp_path):
    fake_repo_audit = SimpleNamespace(REPO_ROOT=tmp_path)
    monkeypatch.setattr(repo_audit_entrypoints, "_repo_audit_module", lambda: fake_repo_audit)

    commands = repo_audit_entrypoints._build_repo_audit_finish_gate_commands(
        profile="full",
        output_dir=tmp_path,
        fail_on="high",
        changed_files=["src/sattlint/app.py"],
        recommended_checks=[],
        ruff_command=["ruff"],
        pyright_command=["pyright"],
        python_command=["python"],
        pytest_workers=" 3 ",
    )

    assert commands[0]["argv"][-2:] == ["--pytest-workers", "3"]


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
        "generated_by": "sattlint.devtools.ai.ai_gc",
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


def test_run_recommended_repo_audit_slice_filters_custom_findings_outside_changed_scope(monkeypatch, tmp_path):
    recommendation = {
        "recommended_check_ids": ["public-readiness"],
        "recommended_pipeline_check_ids": [],
        "recommended_repo_audit_check_ids": ["public-readiness"],
    }
    unrelated_finding = repo_audit.Finding(
        "tracked-generated-artifacts",
        "public-readiness",
        "high",
        "high",
        "Tracked generated artifacts.",
        path="artifacts",
    )
    related_finding = repo_audit.Finding(
        "changed-file-warning",
        "public-readiness",
        "medium",
        "high",
        "Changed file warning.",
        path="src/sattlint/app.py",
    )

    monkeypatch.setattr(
        repo_audit_entrypoints,
        "build_repo_audit_check_recommendations",
        lambda **kwargs: recommendation,
    )
    monkeypatch.setattr(
        repo_audit_entrypoints, "collect_custom_findings", lambda *args, **kwargs: [unrelated_finding, related_finding]
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

    assert status_report["overall_status"] == "pass"
    assert summary["finding_count"] == 1
    assert [finding["id"] for finding in summary["findings"]] == ["changed-file-warning"]


def test_find_public_readiness_findings_assigns_change_scope_paths(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    tracked_generated_path = "/".join(("build", "status.json"))
    pyproject.write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n[project.urls]\nRepository = "https://example.invalid/demo"\n',
        encoding="utf-8",
    )

    findings = repo_audit._find_public_readiness_findings(
        tmp_path,
        tracked_paths=(
            "README.md",
            "LICENSE",
            "CONTRIBUTING.md",
            ".gitignore",
            "pyproject.toml",
            tracked_generated_path,
        ),
    )

    findings_by_id = {finding.id: finding for finding in findings}

    assert findings_by_id["missing-ci-workflow"].path == ".github/workflows"
    assert findings_by_id["tracked-generated-artifacts"].path == "build"
    assert findings_by_id["unexpected-tracked-root-entry"].path == "build"


def test_repo_audit_entrypoints_cover_delegate_and_default_manifest_branches(monkeypatch, tmp_path):
    from sattlint.devtools import _repo_audit_full_run as full_run_helper  # noqa: PLC0415

    sentinel_summary = {"summary": "selected-check"}
    monkeypatch.setattr(full_run_helper, "_run_repo_audit_findings_checks", lambda *args, **kwargs: sentinel_summary)

    result = repo_audit_entrypoints._run_repo_audit_findings_checks(
        tmp_path,
        profile="full",
        check_ids=["text-scan"],
        fail_on="high",
        include_generated=False,
        suspicious_identifiers=(),
    )

    fake_repo_audit = SimpleNamespace(PIPELINE_OUTPUT_DIRNAME="pipeline", REPO_ROOT=tmp_path)
    monkeypatch.setattr(repo_audit_entrypoints, "_repo_audit_module", lambda: fake_repo_audit)
    monkeypatch.setattr(
        repo_audit_entrypoints.pipeline_module,
        "build_pipeline_check_recommendations",
        lambda **kwargs: {
            "recommended_check_ids": ["ruff"],
            "suggested_finish_gate_commands": ["sattlint-analysis-pipeline --run-recommended-finish-gate"],
        },
    )

    planning_report = repo_audit_entrypoints._build_selected_finish_gate_plan(
        profile="full",
        output_dir=tmp_path,
        fail_on="high",
        selected_surface="pipeline",
        changed_files=["src/main.py"],
        planning_context={"finish_gate_template": "invalid", "owner_test_targets": ["tests/test_main.py"]},
        recommendation={"recommended_check_ids": ["cli"]},
    )

    manifest_dir = tmp_path / "corpus-manifests"
    monkeypatch.setattr(repo_audit_entrypoints.pipeline_module, "DEFAULT_CORPUS_MANIFEST_DIR", manifest_dir)

    assert result is sentinel_summary
    assert planning_report["description"] == ""
    assert planning_report["includes"] == []
    assert repo_audit_entrypoints._default_corpus_manifest_dir() is None

    manifest_dir.mkdir(parents=True)
    assert repo_audit_entrypoints._default_corpus_manifest_dir() is None


def test_run_repo_audit_findings_checks_writes_selected_check_reports(monkeypatch, tmp_path):
    from sattlint.devtools import _repo_audit_full_run as full_run_helper  # noqa: PLC0415

    findings = [
        repo_audit.Finding(
            "cleanup-candidate",
            "maintenance",
            "high",
            "high",
            "Cleanup recommended.",
            path=_artifact_path("old.json"),
            history_cleanup_recommended=True,
        ),
        repo_audit.Finding(
            "cli-gap",
            "architecture",
            "medium",
            "high",
            "CLI gap.",
            path="src/sattlint/app.py",
            line=12,
        ),
    ]
    ai_gc_report = {
        "kind": "sattlint.ai_gc",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.ai.ai_gc",
        "mode": "report",
        "status": "needs-attention",
        "summary": {"candidate_count": 1},
        "candidates": [{"candidate_id": "stale-ai-artifact", "path": _artifact_path("old.json")}],
        "applied_actions": [],
        "failures": [],
    }
    markdown_calls: list[tuple[object, ...]] = []
    history_calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(repo_audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(repo_audit, "build_ai_gc_report", lambda _root: ai_gc_report)
    monkeypatch.setattr(repo_audit, "_write_markdown", lambda *args, **kwargs: markdown_calls.append(args))
    monkeypatch.setattr(
        repo_audit,
        "_write_audit_run_history",
        lambda *args, **kwargs: history_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        full_run_helper,
        "_entrypoints_module",
        lambda: SimpleNamespace(
            _repo_audit_module=lambda: repo_audit,
            collect_custom_findings=lambda *args, **kwargs: findings,
            _blocking_finding_count=lambda _findings, _fail_on: 1,
            _severity_counts=lambda _findings: {"high": 1, "medium": 1},
            _category_counts=lambda _findings: {"maintenance": 1, "architecture": 1},
            _max_severity=lambda _findings: "high",
        ),
    )

    latest_output_dir = tmp_path / "latest"
    summary = full_run_helper._run_repo_audit_findings_checks(
        tmp_path / "selected-checks",
        profile="full",
        check_ids=["ai-gc", "cli", "ai-gc"],
        fail_on="high",
        include_generated=False,
        suspicious_identifiers=("SQHJ",),
        latest_output_dir=latest_output_dir,
    )

    status_report = json.loads((tmp_path / "selected-checks" / "status.json").read_text(encoding="utf-8"))
    findings_report = json.loads((tmp_path / "selected-checks" / "findings.json").read_text(encoding="utf-8"))

    assert summary["selected_checks"] == ["ai-gc", "cli"]
    assert summary["finding_count"] == 2
    assert summary["history_cleanup_findings"] == [findings[0].to_dict()]
    assert summary["reports"]["pipeline_status"] is None
    assert summary["reports"]["pipeline_summary"] is None
    assert status_report["overall_status"] == "fail"
    assert status_report["blocking_finding_count"] == 1
    assert status_report["latest_status_report"].endswith("latest/status.json")
    assert status_report["top_findings"][0]["id"] == "cleanup-candidate"
    assert findings_report["kind"] == "sattlint.findings"
    assert [item["id"] for item in findings_report["findings"]] == ["cleanup-candidate", "cli-gap"]
    assert (tmp_path / "selected-checks" / "ai_gc.json").exists()
    assert markdown_calls
    assert history_calls
