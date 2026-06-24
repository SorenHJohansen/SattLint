# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
# ruff: noqa: F403, F405
from sattlint.devtools.ai import ai_gc

from ._repo_audit_test_support import *


def test_main_check_routes_finding_checks(capsys):
    repo_audit._print_cli_summary(
        {
            "profile": "quick",
            "overall_status": "pass",
            "findings_schema": {
                "kind": "sattlint.findings",
                "schema_version": 1,
            },
            "finding_count": 2,
            "blocking_finding_count": 1,
            "fail_on": "medium",
            "status_report": "<external>/audit/status.json",
            "summary_report": "<external>/audit/summary.json",
        }
    )

    output = capsys.readouterr().out

    assert "Findings schema: sattlint.findings v1" in output
    assert "Findings: 2 total, 1 blocking at fail-on medium" in output


def test_default_corpus_manifest_dir_returns_none_when_empty(tmp_path):
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()

    with patch.object(repo_audit.pipeline_module, "DEFAULT_CORPUS_MANIFEST_DIR", manifest_dir):
        assert repo_audit._default_corpus_manifest_dir() is None


def test_default_corpus_manifest_dir_returns_resolved_manifest_root(tmp_path):
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    (manifest_dir / "case.json").write_text("{}", encoding="utf-8")

    with patch.object(repo_audit.pipeline_module, "DEFAULT_CORPUS_MANIFEST_DIR", manifest_dir):
        assert repo_audit._default_corpus_manifest_dir() == manifest_dir.resolve()


def test_audit_repository_mirrors_latest_reports_to_stable_directory(tmp_path):
    output_dir = tmp_path / "runs" / "audit-001"
    latest_dir = tmp_path / "artifacts" / "audit"
    stale_file = latest_dir / "obsolete.txt"
    stale_file.parent.mkdir(parents=True)
    stale_file.write_text("stale", encoding="utf-8")

    finding = repo_audit.Finding(
        "oversized-module",
        "architecture",
        "medium",
        "high",
        "Large module with high maintenance cost.",
        path="src/big.py",
    )
    pipeline_summary = {
        "profile": "quick",
        "output_dir": "<external>/audit/pipeline",
        "status": {"overall_status": "pass", "tool_statuses": {}},
    }

    with (
        patch.object(repo_audit, "collect_custom_findings", return_value=[finding]),
        patch.object(repo_audit, "find_pipeline_findings", return_value=[]),
        patch.object(repo_audit.pipeline_module, "_run_pipeline", return_value=pipeline_summary),
    ):
        repo_audit.audit_repository(
            output_dir,
            profile="quick",
            fail_on="high",
            include_generated=False,
            leaks_only=False,
            suspicious_identifiers=["SQHJ"],
            skip_pipeline=False,
            skip_vulture=False,
            skip_bandit=False,
            latest_output_dir=latest_dir,
        )

    latest_status = json.loads((latest_dir / "status.json").read_text(encoding="utf-8"))
    latest_summary = json.loads((latest_dir / "summary.json").read_text(encoding="utf-8"))
    mirrored_findings = json.loads((latest_dir / "findings.json").read_text(encoding="utf-8"))
    run_history = json.loads((latest_dir / "run_history.json").read_text(encoding="utf-8"))

    assert stale_file.exists() is True
    assert latest_status["latest_status_report"].endswith("/audit/status.json")
    assert latest_status["latest_summary_report"].endswith("/audit/summary.json")
    assert latest_summary["finding_count"] == 1
    assert_findings_collection(mirrored_findings, finding_count=1)
    assert mirrored_findings["findings"][0]["id"] == "oversized-module"
    assert run_history["kind"] == "sattlint.audit_run_history"
    assert run_history["run_count"] == 1
    assert run_history["latest_run_id"] == run_history["runs"][0]["run_id"]
    assert run_history["runs"][0]["latest"] is True
    assert run_history["runs"][0]["report_kind"] == "repo_audit"
    snapshot_dir = latest_dir / "history" / run_history["runs"][0]["snapshot_dir_name"]
    assert snapshot_dir.exists()


def test_audit_repository_run_history_keeps_last_ten_runs_and_marks_older_entries_stale(tmp_path):
    latest_dir = tmp_path / "artifacts" / "audit"
    finding = repo_audit.Finding(
        "oversized-module",
        "architecture",
        "high",
        "high",
        "Large module with high maintenance cost.",
        path="src/big.py",
    )
    pipeline_summary = {
        "profile": "quick",
        "output_dir": "<external>/audit/pipeline",
        "status": {"overall_status": "pass", "tool_statuses": {}},
    }

    with (
        patch.object(repo_audit, "collect_custom_findings", return_value=[finding]),
        patch.object(repo_audit, "find_pipeline_findings", return_value=[]),
        patch.object(repo_audit.pipeline_module, "_run_pipeline", return_value=pipeline_summary),
        patch.object(repo_audit, "_collect_audit_git_state", return_value={"head": "abc123", "dirty": False}),
    ):
        for index in range(11):
            repo_audit.audit_repository(
                tmp_path / "runs" / f"audit-{index:03d}",
                profile="quick",
                fail_on="high",
                include_generated=False,
                leaks_only=False,
                suspicious_identifiers=["SQHJ"],
                skip_pipeline=False,
                skip_vulture=False,
                skip_bandit=False,
                latest_output_dir=latest_dir,
            )

    run_history = json.loads((latest_dir / "run_history.json").read_text(encoding="utf-8"))

    assert run_history["run_count"] == 10
    assert len(run_history["runs"]) == 10
    assert run_history["runs"][0]["latest"] is True
    assert run_history["runs"][0]["likely_stale"] is False
    assert all(entry["likely_stale"] is True for entry in run_history["runs"][1:])
    assert all("superseded-by-newer-run" in entry["likely_stale_reasons"] for entry in run_history["runs"][1:])
    assert len(list((latest_dir / "history").iterdir())) == 10
    assert run_history["failure_patterns"][0]["occurrence_count"] == 10


def test_audit_repository_skips_pipeline_and_writes_full_cli_consistency_report(tmp_path):
    output_dir = tmp_path / "audit"
    finding = repo_audit.Finding(
        "oversized-module",
        "architecture",
        "medium",
        "high",
        "Large module with high maintenance cost.",
        path="src/big.py",
    )
    cli_report = {
        "kind": "sattlint.cli_consistency",
        "schema_version": 1,
        "declared": {"scripts": ["sattlint"], "subcommands": ["syntax-check"]},
        "gaps": {
            "undeclared_subcommands": [],
            "undeclared_scripts": [],
            "undocumented_subcommands": [],
            "undocumented_scripts": [],
        },
        "summary": {
            "undeclared_subcommand_count": 0,
            "undeclared_script_count": 0,
            "undocumented_subcommand_count": 0,
            "undocumented_script_count": 0,
            "gap_count": 0,
        },
        "status": "pass",
    }

    with (
        patch.object(repo_audit, "collect_custom_findings", return_value=[finding]) as collect_custom_findings,
        patch.object(repo_audit.pipeline_module, "_run_pipeline") as run_pipeline,
        patch.object(repo_audit, "build_cli_consistency_report", return_value=cli_report) as build_cli_consistency,
    ):
        summary = repo_audit.audit_repository(
            output_dir,
            profile="full",
            fail_on="high",
            include_generated=True,
            leaks_only=False,
            suspicious_identifiers=["SQHJ"],
            skip_pipeline=True,
            skip_vulture=True,
            skip_bandit=True,
        )

    status_report = json.loads((output_dir / "status.json").read_text(encoding="utf-8"))
    progress_report = json.loads((output_dir / "progress.json").read_text(encoding="utf-8"))
    cli_consistency_report = json.loads((output_dir / "cli_consistency.json").read_text(encoding="utf-8"))

    run_pipeline.assert_not_called()
    collect_custom_findings.assert_called_once_with(
        repo_audit.REPO_ROOT,
        include_generated=True,
        tracked_only=True,
        suspicious_identifiers=["SQHJ"],
    )
    build_cli_consistency.assert_called_once_with(root=repo_audit.REPO_ROOT)
    assert summary["pipeline_ran"] is False
    assert summary["reports"]["pipeline_status"] is None
    assert status_report["pipeline_status_report"] is None
    assert any(stage["key"] == "pipeline" and stage["status"] == "skipped" for stage in progress_report["stages"])
    assert cli_consistency_report == cli_report


def test_main_defaults_fail_on_medium_for_leaks_only():
    summary = {
        "profile": "leaks",
        "output_dir": "<external>/artifacts/audit",
        "finding_count": 1,
        "findings_schema": {"kind": "sattlint.findings", "schema_version": 1},
        "findings": [
            {
                "id": "hardcoded-windows-path",
                "category": "portability",
                "severity": "medium",
                "confidence": "high",
                "message": "Absolute Windows path committed to the repository.",
                "path": "README.md",
                "line": None,
                "detail": None,
                "suggestion": None,
                "source": "custom",
                "history_cleanup_recommended": False,
            }
        ],
    }

    with (
        patch.object(repo_audit, "audit_repository", return_value=summary) as audit_repository,
        patch.object(repo_audit, "_print_cli_summary") as print_cli_summary,
    ):
        exit_code = repo_audit.main(["--leaks-only"])

    assert exit_code == 1
    assert audit_repository.call_args.kwargs["fail_on"] == "medium"
    assert audit_repository.call_args.kwargs["leaks_only"] is True
    assert audit_repository.call_args.kwargs["latest_output_dir"] == repo_audit.DEFAULT_OUTPUT_DIR.resolve()
    printed_summary = print_cli_summary.call_args.args[0]
    assert printed_summary["findings"] == summary["findings"]
    assert printed_summary["latest_status_report"] is None
    assert printed_summary["latest_summary_report"] is None


def test_main_reports_latest_links_for_non_default_output_dir(tmp_path):
    output_dir = tmp_path / "runs" / "audit-002"
    summary = {
        "profile": "quick",
        "output_dir": f"<external>/{output_dir.parent.name}/{output_dir.name}",
        "finding_count": 0,
        "findings_schema": {"kind": "sattlint.findings", "schema_version": 1},
        "findings": [],
    }

    with (
        patch.object(repo_audit, "audit_repository", return_value=summary) as audit_repository,
        patch.object(repo_audit, "_print_cli_summary") as print_cli_summary,
    ):
        exit_code = repo_audit.main(
            [
                "--output-dir",
                str(output_dir),
                "--profile",
                "quick",
                "--fail-on",
                "low",
                "--skip-pipeline",
            ]
        )

    assert exit_code == 0
    assert audit_repository.call_args.kwargs["fail_on"] == "low"
    assert audit_repository.call_args.kwargs["skip_pipeline"] is True
    printed_summary = print_cli_summary.call_args.args[0]
    assert printed_summary["latest_status_report"].endswith("/status.json")
    assert printed_summary["latest_summary_report"].endswith("/summary.json")


def test_collect_custom_findings_selected_checks_only_run_requested_runner(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(
        repo_audit_entrypoints._repo_audit_check_runners_module,
        "_build_repo_audit_scan_context",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        repo_audit_entrypoints._repo_audit_check_runners_module,
        "_with_shared_text_line_findings",
        lambda _context: (_ for _ in ()).throw(AssertionError("shared text findings should not run")),
    )
    monkeypatch.setattr(
        repo_audit_entrypoints,
        "_repo_audit_finding_runner_overrides",
        lambda: {
            "text-scan": lambda context: calls.append("text-scan") or [],
            "public-readiness": lambda context: calls.append("public-readiness") or [],
            "verify-recommendations": lambda _context: [],
        },
    )

    findings = repo_audit.collect_custom_findings(selected_checks=["public-readiness"])

    assert findings == []
    assert calls == ["public-readiness"]


def test_build_ai_gc_report_flags_stale_untracked_allowlisted_artifact(tmp_path):
    artifact_dir = tmp_path / "artifacts" / "audit-review-old"
    artifact_dir.mkdir(parents=True)
    report_path = artifact_dir / "status.json"
    report_path.write_text("{}\n", encoding="utf-8")

    now_ts = time.time()
    stale_ts = now_ts - (20 * 24 * 60 * 60)
    os.utime(artifact_dir, (stale_ts, stale_ts))
    os.utime(report_path, (stale_ts, stale_ts))

    report = repo_audit.build_ai_gc_report(
        tmp_path,
        tracked_paths=(),
        now_ts=now_ts,
        stale_after_days=14,
    )

    assert report["status"] == "needs-attention"
    assert report["summary"]["candidate_count"] == 1
    candidate = report["candidates"][0]
    assert candidate["candidate_id"] == "stale-ai-artifact"
    assert candidate["path"] == "artifacts/audit-review-old"
    assert candidate["action"] == "delete"


def test_build_ai_gc_report_flags_manifest_drift_before_age_cutoff(tmp_path):
    artifact_dir = tmp_path / "artifacts" / "audit-review-fresh"
    artifact_dir.mkdir(parents=True)
    report_path = artifact_dir / "status.json"
    source_path = tmp_path / "src" / "generator.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("value = 1\n", encoding="utf-8")

    write_json_artifact(
        report_path,
        {
            "kind": "sattlint.repo_audit.status",
            "schema_version": 1,
            "generated_by": "sattlint.devtools.audit.repo_audit",
        },
        repo_root=tmp_path,
        source_paths=(source_path,),
    )
    source_path.write_text("value = 2\n", encoding="utf-8")

    report = repo_audit.build_ai_gc_report(
        tmp_path,
        tracked_paths=(),
        stale_after_days=14,
    )

    assert report["generated_by"] == "sattlint.devtools.ai.ai_gc"
    assert report["summary"]["manifest_drift_candidate_count"] == 1
    candidate = report["candidates"][0]
    assert candidate["candidate_id"] == "stale-generated-output-manifest"
    assert candidate["path"] == "artifacts/audit-review-fresh"
    assert candidate["drifted_sources"] == ["src/generator.py"]


def test_collect_custom_findings_ai_gc_surfaces_stale_artifacts(tmp_path):
    artifact_dir = tmp_path / "artifacts" / "audit-review-old"
    artifact_dir.mkdir(parents=True)
    report_path = artifact_dir / "status.json"
    report_path.write_text("{}\n", encoding="utf-8")

    stale_ts = time.time() - (20 * 24 * 60 * 60)
    os.utime(artifact_dir, (stale_ts, stale_ts))
    os.utime(report_path, (stale_ts, stale_ts))

    findings = repo_audit.collect_custom_findings(
        tmp_path,
        tracked_only=True,
        selected_checks=["ai-gc"],
    )

    assert [finding.id for finding in findings] == ["stale-ai-artifact"]
    assert findings[0].path == "artifacts/audit-review-old"


def test_apply_ai_gc_deletes_stale_artifacts_and_writes_report(tmp_path):
    artifact_dir = tmp_path / "artifacts" / "audit-review-old"
    artifact_dir.mkdir(parents=True)
    report_path = artifact_dir / "status.json"
    source_path = tmp_path / "src" / "generator.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("value = 1\n", encoding="utf-8")
    write_json_artifact(
        report_path,
        {
            "kind": "sattlint.repo_audit.status",
            "schema_version": 1,
            "generated_by": "sattlint.devtools.audit.repo_audit",
        },
        repo_root=tmp_path,
        source_paths=(source_path,),
    )
    output_dir = tmp_path / "out"

    source_path.write_text("value = 2\n", encoding="utf-8")
    manifest_path = artifact_source_manifest_path(report_path)

    report = repo_audit.apply_ai_gc(
        tmp_path,
        output_dir=output_dir,
        tracked_paths=(),
    )

    assert report["status"] == "pass"
    assert report["summary"]["applied_count"] == 1
    assert not artifact_dir.exists()
    assert not manifest_path.exists()
    assert (output_dir / "ai_gc.json").exists()


def test_ai_gc_list_tracked_paths_handles_missing_git_and_subprocess_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_gc.shutil, "which", lambda _name: None)
    assert ai_gc._list_tracked_paths(tmp_path) == ()

    monkeypatch.setattr(ai_gc.shutil, "which", lambda _name: "git")

    def _raise_oserror(*_args, **_kwargs):
        raise OSError("git unavailable")

    monkeypatch.setattr(ai_gc.subprocess, "run", _raise_oserror)
    assert ai_gc._list_tracked_paths(tmp_path) == ()


def test_ai_gc_path_mtime_ignores_child_stat_failures(tmp_path, monkeypatch):
    artifact_dir = tmp_path / "artifacts" / "audit-review"
    artifact_dir.mkdir(parents=True)
    base_mtime = artifact_dir.stat().st_mtime
    original_rglob = Path.rglob

    class _BrokenChild:
        def stat(self):
            raise OSError("stat failed")

    def _fake_rglob(self, pattern):
        if self == artifact_dir:
            return [_BrokenChild()]
        return list(original_rglob(self, pattern))

    monkeypatch.setattr(Path, "rglob", _fake_rglob)

    assert ai_gc._path_mtime(artifact_dir) == base_mtime


def test_build_ai_gc_report_collects_missing_manifest_sources_and_ignores_manifest_siblings(tmp_path):
    generated_dir = tmp_path / "docs" / "generated"
    generated_dir.mkdir(parents=True)
    (generated_dir / "ignored.sources.json").write_text("{}", encoding="utf-8")

    artifact_file = generated_dir / "fresh.json"
    artifact_file.write_text("{}", encoding="utf-8")
    artifact_source_manifest_path(artifact_file).write_text(
        json.dumps({"sources": [{"path": ""}, {"path": "missing.py"}]}),
        encoding="utf-8",
    )

    report = ai_gc.build_ai_gc_report(
        tmp_path,
        tracked_paths=(),
        stale_after_days=14,
    )

    assert report["summary"]["candidate_count"] == 1
    candidate = report["candidates"][0]
    assert candidate["path"] == "docs/generated/fresh.json"
    assert candidate["missing_sources"] == ["missing.py"]
    assert "missing sources: missing.py" in candidate["reason"]


def test_build_ai_gc_report_reports_invalid_manifest_payloads(tmp_path):
    artifact_dir = tmp_path / "artifacts" / "audit-review-invalid"
    artifact_dir.mkdir(parents=True)
    artifact_file = artifact_dir / "status.json"
    artifact_file.write_text("{}", encoding="utf-8")
    invalid_manifest = artifact_source_manifest_path(artifact_file)
    invalid_manifest.write_text("{", encoding="utf-8")

    report = ai_gc.build_ai_gc_report(
        tmp_path,
        tracked_paths=(),
        stale_after_days=14,
    )

    candidate = report["candidates"][0]
    assert candidate["path"] == "artifacts/audit-review-invalid"
    assert candidate["invalid_manifests"] == [invalid_manifest.as_posix()]
    assert "invalid manifests" in candidate["reason"]


def test_build_ai_gc_report_apply_deletes_stale_file_candidates(tmp_path):
    artifact_file = tmp_path / "docs" / "generated" / "orphan.json"
    artifact_file.parent.mkdir(parents=True)
    artifact_file.write_text("{}", encoding="utf-8")
    manifest_path = artifact_source_manifest_path(artifact_file)
    manifest_path.write_text("{}", encoding="utf-8")

    now_ts = time.time()
    stale_ts = now_ts - (20 * 24 * 60 * 60)
    os.utime(artifact_file, (stale_ts, stale_ts))
    os.utime(manifest_path, (stale_ts, stale_ts))

    report = ai_gc.build_ai_gc_report(
        tmp_path,
        tracked_paths=(),
        now_ts=now_ts,
        stale_after_days=14,
        apply=True,
    )

    assert report["status"] == "pass"
    assert report["summary"]["applied_count"] == 1
    assert not artifact_file.exists()
    assert not manifest_path.exists()


def test_build_ai_gc_report_apply_records_delete_failures(tmp_path, monkeypatch):
    artifact_file = tmp_path / "docs" / "generated" / "blocked.json"
    artifact_file.parent.mkdir(parents=True)
    artifact_file.write_text("{}", encoding="utf-8")

    now_ts = time.time()
    stale_ts = now_ts - (20 * 24 * 60 * 60)
    os.utime(artifact_file, (stale_ts, stale_ts))

    original_unlink = Path.unlink

    def _failing_unlink(self, *args, **kwargs):
        if self == artifact_file:
            raise OSError("permission denied")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _failing_unlink)

    report = ai_gc.build_ai_gc_report(
        tmp_path,
        tracked_paths=(),
        now_ts=now_ts,
        stale_after_days=14,
        apply=True,
    )

    assert report["status"] == "fail"
    assert report["summary"]["failure_count"] == 1
    assert report["failures"][0]["path"] == "docs/generated/blocked.json"
    assert report["failures"][0]["error_type"] == "OSError"


def test_build_ai_gc_report_apply_handles_non_delete_actions_and_missing_targets(monkeypatch, tmp_path):
    root = tmp_path.resolve()
    monkeypatch.setattr(
        ai_gc,
        "_iter_allowlisted_candidates",
        lambda _root, _tracked_paths: [
            {
                "path_obj": root / "docs" / "generated" / "virtual.json",
                "path": "docs/generated/virtual.json",
                "kind": "file",
                "action": "keep",
                "safe_to_apply": True,
            },
            {
                "path_obj": root / "docs" / "generated" / "missing.json",
                "path": "docs/generated/missing.json",
                "kind": "file",
                "action": "delete",
                "safe_to_apply": True,
            },
        ],
    )
    monkeypatch.setattr(ai_gc, "_manifest_drift_details", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ai_gc, "_path_mtime", lambda *_args, **_kwargs: 0.0)
    monkeypatch.setattr(ai_gc, "_path_size_bytes", lambda *_args, **_kwargs: 0)

    report = ai_gc.build_ai_gc_report(
        tmp_path,
        tracked_paths=(),
        now_ts=20 * 24 * 60 * 60,
        stale_after_days=14,
        apply=True,
    )

    assert report["status"] == "pass"
    assert report["summary"]["applied_count"] == 2
    assert {entry["path"] for entry in report["applied_actions"]} == {
        "docs/generated/virtual.json",
        "docs/generated/missing.json",
    }


def test_build_repo_audit_check_catalog_lists_pipeline_and_custom_checks(tmp_path):
    catalog = repo_audit.build_repo_audit_check_catalog(profile="full", output_dir=tmp_path, fail_on="high")

    assert catalog["kind"] == "sattlint.repo_audit.check_catalog"
    check_ids = {entry["id"] for entry in catalog["checks"]}
    assert {"ruff", "ai-gc", "harness-freshness", "public-readiness", "cli-consistency", "local-ci-parity"} <= check_ids
    public_readiness_entry = next(entry for entry in catalog["checks"] if entry["id"] == "public-readiness")
    assert public_readiness_entry["source"] == "repo-audit"
    assert "--check public-readiness" in public_readiness_entry["command"]
    assert public_readiness_entry["owner_surface"] == "public-readiness"

    ai_gc_entry = next(entry for entry in catalog["checks"] if entry["id"] == "ai-gc")
    assert "ai_gc" in ai_gc_entry["artifact_ids"]
    assert ai_gc_entry["owner_surface"] == "ai-hygiene"
    assert ai_gc_entry["ai_instruction_files"] == [".github/instructions/repo-audit.instructions.md"]

    harness_entry = next(entry for entry in catalog["checks"] if entry["id"] == "harness-freshness")
    assert "--check harness-freshness" in harness_entry["command"]
    assert harness_entry["owner_surface"] == "harness-freshness"
    assert harness_entry["ai_summary"]

    local_ci_entry = next(entry for entry in catalog["checks"] if entry["id"] == "local-ci-parity")
    assert "--check local-ci-parity" in local_ci_entry["command"]
    assert local_ci_entry["owner_surface"] == "local-ci-parity"
