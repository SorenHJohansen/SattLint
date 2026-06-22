# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false
from __future__ import annotations

from typing import Any

from sattlint.devtools import repo_audit as compat_repo_audit
from tests import test_repo_audit as repo_audit_tests


def test_build_repo_audit_check_catalog_lists_pipeline_and_custom_checks(tmp_path):
    repo_audit_tests.test_build_repo_audit_check_catalog_lists_pipeline_and_custom_checks(tmp_path)


def test_build_repo_audit_check_recommendations_combines_pipeline_and_repo_audit_routes(tmp_path):
    recommendations = repo_audit_tests.repo_audit.build_repo_audit_check_recommendations(
        profile="full",
        output_dir=tmp_path,
        fail_on="high",
        changed_files=["docs/references/cli-commands.md"],
    )

    assert recommendations["kind"] == "sattlint.repo_audit.check_recommendations"
    assert recommendations["fallback_required"] is False
    assert "documented-commands" in recommendations["recommended_repo_audit_check_ids"]
    assert "cli-consistency" in recommendations["recommended_repo_audit_check_ids"]
    assert recommendations["suggested_check_commands"]
    assert recommendations["suggested_finish_gate_commands"]
    assert recommendations["proof_requirements"]["focused_behavior_test"]["required"] is False
    assert recommendations["proof_requirements"]["coverage"]["required"] is False
    assert recommendations["why_this_gate"]["matched_routes"]


def test_build_repo_audit_check_recommendations_limits_control_surface_fallback(tmp_path):
    recommendations = repo_audit_tests.repo_audit.build_repo_audit_check_recommendations(
        profile="full",
        output_dir=tmp_path,
        fail_on="high",
        changed_files=["src/sattlint/devtools/audit/repo_audit_entrypoints.py"],
    )

    assert recommendations["fallback_required"] is True
    assert recommendations["recommended_pipeline_check_ids"] == ["ruff", "pyright", "pytest"]
    assert recommendations["recommended_repo_audit_check_ids"] == ["verify-recommendations"]


def test_build_repo_audit_check_recommendations_routes_harness_freshness(tmp_path):
    recommendations = repo_audit_tests.repo_audit.build_repo_audit_check_recommendations(
        profile="full",
        output_dir=tmp_path,
        fail_on="high",
        changed_files=["AGENTS.md"],
    )

    assert "harness-freshness" in recommendations["recommended_repo_audit_check_ids"]


def test_main_list_checks_prints_catalog(tmp_path, capsys):
    exit_code = repo_audit_tests.repo_audit.main(["--profile", "full", "--output-dir", str(tmp_path), "--list-checks"])

    payload = repo_audit_tests.json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["kind"] == "sattlint.repo_audit.check_catalog"
    assert any(entry["id"] == "cli-consistency" for entry in payload["checks"])
    assert not any(entry["id"] == "ratchet-policy" for entry in payload["checks"])


def test_main_recommend_checks_prints_catalog(tmp_path, capsys):
    exit_code = repo_audit_tests.repo_audit.main(
        [
            "--profile",
            "full",
            "--output-dir",
            str(tmp_path),
            "--recommend-checks",
            "--changed-file",
            "docs/references/cli-commands.md",
        ]
    )

    payload = repo_audit_tests.json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["kind"] == "sattlint.repo_audit.check_recommendations"
    assert "documented-commands" in payload["recommended_repo_audit_check_ids"]


def test_main_planning_context_prints_machine_readable_report(monkeypatch, tmp_path, capsys):
    report = {
        "kind": "sattlint.planning_context",
        "schema_version": 1,
        "changed_files": ["src/sattlint/app.py"],
        "owning_surface": "repo-audit",
        "selected_surface": "repo-audit",
        "planning_context": {
            "primary_agent": "CLI App Menu",
            "instruction_files": [],
            "nearest_owner_suites": [],
            "blocking_invariants": [],
        },
        "finish_gate": {"command": "sattlint-repo-audit --run-recommended-finish-gate"},
    }

    with repo_audit_tests.patch.object(
        repo_audit_tests.repo_audit._repo_audit_entrypoints,
        "build_check_my_changes_planning_report",
        return_value=report,
    ) as build_planning_report:
        exit_code = repo_audit_tests.repo_audit.main(
            [
                "--planning-context",
                "--output-dir",
                str(tmp_path),
                "--changed-file",
                "src/sattlint/app.py",
            ]
        )

    payload = repo_audit_tests.json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["kind"] == "sattlint.planning_context"
    assert payload["planning_context"]["primary_agent"] == "CLI App Menu"
    assert payload["finish_gate"]["command"] == "sattlint-repo-audit --run-recommended-finish-gate"
    assert build_planning_report.call_args.kwargs["changed_files"] == ["src/sattlint/app.py"]


def test_collect_custom_findings_uses_injected_owner_seam_and_outer_wrapper_hides_private_hooks(tmp_path):
    text_finding = repo_audit_tests.repo_audit.Finding(
        "hardcoded-windows-path",
        "portability",
        "high",
        "high",
        "Absolute Windows path committed to the repository.",
        path="README.md",
    )
    readiness_finding = repo_audit_tests.repo_audit.Finding(
        "missing-ci-workflow",
        "public-readiness",
        "medium",
        "high",
        "Repository has no CI workflow.",
    )
    base_context = object()
    context_with_shared_lines = object()
    seen_contexts: list[object] = []

    def record_text_scan_finding(context: object) -> list[Any]:
        seen_contexts.append(context)
        return [text_finding]

    def record_public_readiness_finding(context: object) -> list[Any]:
        seen_contexts.append(context)
        return [readiness_finding]

    def record_verify_recommendations(_context: object) -> list[Any]:
        return []

    with (
        repo_audit_tests.patch.object(
            repo_audit_tests.repo_audit_entrypoints._repo_audit_check_runners_module,
            "_build_repo_audit_scan_context",
            return_value=base_context,
        ) as build_context,
        repo_audit_tests.patch.object(
            repo_audit_tests.repo_audit_entrypoints._repo_audit_check_runners_module,
            "_with_shared_text_line_findings",
            return_value=context_with_shared_lines,
        ) as with_shared_text_line_findings,
        repo_audit_tests.patch.object(
            repo_audit_tests.repo_audit_entrypoints,
            "_repo_audit_finding_runner_overrides",
            return_value={
                "text-scan": record_text_scan_finding,
                "public-readiness": record_public_readiness_finding,
                "verify-recommendations": record_verify_recommendations,
            },
        ),
    ):
        findings = compat_repo_audit.collect_custom_findings(
            tmp_path,
            selected_checks=["text-scan", "public-readiness"],
        )

    assert [finding.id for finding in findings] == ["hardcoded-windows-path", "missing-ci-workflow"]
    assert seen_contexts == [context_with_shared_lines, context_with_shared_lines]
    build_context.assert_called_once_with(
        tmp_path,
        include_generated=False,
        tracked_only=False,
        suspicious_identifiers=(),
    )
    with_shared_text_line_findings.assert_called_once_with(base_context)
    with repo_audit_tests.pytest.raises(AttributeError):
        _ = compat_repo_audit._build_repo_audit_scan_context
    with repo_audit_tests.pytest.raises(AttributeError):
        _ = compat_repo_audit._repo_audit_finding_check_definitions


def test_main_run_recommended_slice_uses_combined_recommendation(monkeypatch, tmp_path):
    summary = {
        "profile": "full",
        "output_dir": f"<external>/{tmp_path.name}",
        "finding_count": 0,
        "findings_schema": {"kind": "sattlint.findings", "schema_version": 1},
        "findings": [],
        "cli_consistency_status": None,
    }

    with (
        repo_audit_tests.patch.object(
            repo_audit_tests.repo_audit, "run_recommended_repo_audit_slice", return_value=summary
        ) as run_slice,
        repo_audit_tests.patch.object(repo_audit_tests.repo_audit, "_print_cli_summary") as print_cli_summary,
    ):
        exit_code = repo_audit_tests.repo_audit.main(
            [
                "--profile",
                "full",
                "--output-dir",
                str(tmp_path),
                "--run-recommended-slice",
                "--changed-file",
                "docs/references/cli-commands.md",
            ]
        )

    assert exit_code == 0
    assert run_slice.call_args.kwargs["changed_files"] == ["docs/references/cli-commands.md"]
    printed = print_cli_summary.call_args.args[0]
    assert printed["overall_status"] == "pass"


def test_main_run_recommended_finish_gate_uses_combined_recommendation(monkeypatch, tmp_path):
    summary = {
        "profile": "full",
        "output_dir": f"<external>/{tmp_path.name}",
        "finding_count": 0,
        "findings_schema": {"kind": "sattlint.findings", "schema_version": 1},
        "findings": [],
        "cli_consistency_status": None,
        "finish_gate": {"status": "pass"},
    }

    with (
        repo_audit_tests.patch.object(
            repo_audit_tests.repo_audit,
            "run_recommended_repo_audit_finish_gate",
            return_value=summary,
        ) as run_finish_gate,
        repo_audit_tests.patch.object(repo_audit_tests.repo_audit, "_print_cli_summary") as print_cli_summary,
    ):
        exit_code = repo_audit_tests.repo_audit.main(
            [
                "--profile",
                "full",
                "--output-dir",
                str(tmp_path),
                "--run-recommended-finish-gate",
                "--pytest-workers",
                "2",
                "--changed-file",
                "docs/references/cli-commands.md",
            ]
        )

    assert exit_code == 0
    assert run_finish_gate.call_args.kwargs["changed_files"] == ["docs/references/cli-commands.md"]
    assert run_finish_gate.call_args.kwargs["pytest_workers"] == "2"
    printed = print_cli_summary.call_args.args[0]
    assert printed["overall_status"] == "pass"
