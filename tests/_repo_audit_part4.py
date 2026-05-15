# ruff: noqa: F403, F405
from ._repo_audit_test_support import *


def test_doc_gardener_flags_markdown_mojibake(tmp_path):
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(
        json.dumps(
            {
                "kind": "sattlint.findings",
                "schema_version": 1,
                "finding_count": 1,
                "findings": [
                    {
                        "id": "ruff-f401",
                        "rule_id": "ruff.f401",
                        "category": "style",
                        "severity": "high",
                        "confidence": "high",
                        "message": "Imported but unused",
                        "source": "ruff",
                        "analyzer": "ruff",
                        "artifact": "findings",
                        "location": {
                            "path": "src/sample.py",
                            "line": 4,
                            "column": 8,
                            "symbol": None,
                            "module_path": [],
                        },
                        "fingerprint": "ruff.f401|src/sample.py|4||Imported but unused",
                        "detail": None,
                        "suggestion": None,
                        "data": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    findings = repo_audit._find_pipeline_findings(tmp_path)

    assert len(findings) == 1
    assert findings[0].id == "ruff-f401"
    assert findings[0].source == "ruff"
    assert findings[0].path == "src/sample.py"
    assert findings[0].line == 4


def test_find_pipeline_findings_ignores_allowlisted_bandit_noise(tmp_path):
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(
        json.dumps(
            {
                "kind": "sattlint.findings",
                "schema_version": 1,
                "finding_count": 2,
                "findings": [
                    {
                        "id": "bandit-b603",
                        "rule_id": "bandit.b603",
                        "category": "security",
                        "severity": "medium",
                        "confidence": "high",
                        "message": "subprocess call - check for execution of untrusted input.",
                        "source": "bandit",
                        "analyzer": "bandit",
                        "artifact": "findings",
                        "location": {
                            "path": "src/sattlint/devtools/doc_gardener.py",
                            "line": 445,
                            "column": None,
                            "symbol": None,
                            "module_path": [],
                        },
                        "fingerprint": "bandit.b603|src/sattlint/devtools/doc_gardener.py|445||subprocess call",
                        "detail": None,
                        "suggestion": None,
                        "data": {},
                    },
                    {
                        "id": "bandit-b314",
                        "rule_id": "bandit.b314",
                        "category": "security",
                        "severity": "medium",
                        "confidence": "high",
                        "message": "Unsafe XML parse.",
                        "source": "bandit",
                        "analyzer": "bandit",
                        "artifact": "findings",
                        "location": {
                            "path": "src/sattlint/devtools/observability.py",
                            "line": 49,
                            "column": None,
                            "symbol": None,
                            "module_path": [],
                        },
                        "fingerprint": "bandit.b314|src/sattlint/devtools/observability.py|49||Unsafe XML parse.",
                        "detail": None,
                        "suggestion": None,
                        "data": {},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    findings = repo_audit._find_pipeline_findings(tmp_path)

    assert len(findings) == 1
    assert findings[0].id == "bandit-b314"


def test_audit_repository_writes_status_file_and_forwards_profile(tmp_path):
    pipeline_summary = {
        "profile": "quick",
        "output_dir": "<external>/audit/pipeline",
        "status": {"overall_status": "pass", "tool_statuses": {}},
    }
    finding = repo_audit.Finding(
        "oversized-module",
        "architecture",
        "medium",
        "high",
        "Large module with high maintenance cost.",
        path="src/big.py",
    )

    with (
        patch.object(repo_audit, "collect_custom_findings", return_value=[finding]),
        patch.object(repo_audit, "_find_pipeline_findings", return_value=[]),
        patch.object(repo_audit.pipeline_module, "_run_pipeline", return_value=pipeline_summary) as run_pipeline,
    ):
        summary = repo_audit.audit_repository(
            tmp_path,
            profile="quick",
            fail_on="high",
            include_generated=False,
            leaks_only=False,
            suspicious_identifiers=["SQHJ"],
            skip_pipeline=False,
            skip_vulture=False,
            skip_bandit=False,
        )

    status_report = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    findings_report = json.loads((tmp_path / "findings.json").read_text(encoding="utf-8"))

    assert summary["profile"] == "quick"
    assert summary["entry_report"] == "status.json"
    assert summary["reports"]["progress"] == "progress.json"
    assert summary["reports"]["pipeline_status"] == "pipeline/status.json"
    assert summary["reports"]["findings"] == "findings.json"
    assert_findings_schema(summary)
    assert status_report["profile"] == "quick"
    assert status_report["overall_status"] == "pass"
    assert_findings_schema(status_report)
    assert status_report["progress_report"] == f"<external>/{tmp_path.name}/progress.json"
    assert status_report["pipeline_status_report"] == f"<external>/{tmp_path.name}/pipeline/status.json"
    assert_findings_collection(findings_report, finding_count=1)
    assert findings_report["findings"][0]["location"] == {
        "path": "src/big.py",
        "line": None,
        "column": None,
        "symbol": None,
        "module_path": [],
    }
    run_pipeline.assert_called_once()
    assert run_pipeline.call_args.kwargs["profile"] == "quick"
    assert (
        run_pipeline.call_args.kwargs["corpus_manifest_dir"]
        == repo_audit.pipeline_module.DEFAULT_CORPUS_MANIFEST_DIR.resolve()
    )


def test_audit_repository_collects_custom_findings_from_tracked_files(tmp_path):
    pipeline_summary = {
        "profile": "quick",
        "output_dir": "<external>/audit/pipeline",
        "status": {"overall_status": "pass", "tool_statuses": {}},
    }

    with (
        patch.object(repo_audit, "collect_custom_findings", return_value=[]) as collect_custom_findings,
        patch.object(repo_audit, "_find_pipeline_findings", return_value=[]),
        patch.object(repo_audit.pipeline_module, "_run_pipeline", return_value=pipeline_summary),
    ):
        repo_audit.audit_repository(
            tmp_path,
            profile="quick",
            fail_on="high",
            include_generated=False,
            leaks_only=False,
            suspicious_identifiers=["SQHJ"],
            skip_pipeline=False,
            skip_vulture=False,
            skip_bandit=False,
        )

    assert collect_custom_findings.call_args.kwargs["tracked_only"] is True


def test_audit_repository_marks_pipeline_stage_failed_and_writes_failure_status(monkeypatch, tmp_path):
    with (
        pytest.raises(KeyboardInterrupt),
        patch.object(
            repo_audit.pipeline_module,
            "_run_pipeline",
            side_effect=KeyboardInterrupt("terminal interrupted"),
        ),
    ):
        repo_audit.audit_repository(
            tmp_path,
            profile="full",
            fail_on="high",
            include_generated=False,
            leaks_only=False,
            suspicious_identifiers=["SQHJ"],
            skip_pipeline=False,
            skip_vulture=False,
            skip_bandit=False,
        )

    progress_report = json.loads((tmp_path / "progress.json").read_text(encoding="utf-8"))
    status_report = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    summary_report = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    findings_report = json.loads((tmp_path / "findings.json").read_text(encoding="utf-8"))

    assert progress_report["overall_status"] == "failed"
    pipeline_stage = next(stage for stage in progress_report["stages"] if stage["key"] == "pipeline")
    assert pipeline_stage["status"] == "failed"
    assert "KeyboardInterrupt" in pipeline_stage["detail"]
    assert status_report["overall_status"] == "fail"
    assert status_report["error"]["stage"] == "pipeline"
    assert status_report["pipeline_status_report"].endswith("/pipeline/status.json")
    assert summary_report["error"]["type"] == "KeyboardInterrupt"
    assert findings_report["finding_count"] == 0


def test_collect_custom_findings_aggregates_scanners_and_filters_repo_audit_source(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("repo docs\n", encoding="utf-8")
    vscode_readme = tmp_path / "vscode" / "sattline-vscode" / "README.md"
    vscode_readme.parent.mkdir(parents=True)
    vscode_readme.write_text("extension docs\n", encoding="utf-8")

    source_context = repo_audit.PythonSourceScanContext(
        source_root=tmp_path / "src",
        texts={
            tmp_path / "src" / "sattlint" / "alpha.py": "ALPHA = 1\n",
            tmp_path / "src" / "sattlint" / "repo_audit.py": "SELF = 1\n",
            tmp_path / "src" / "other.py": "OTHER = 1\n",
        },
        asts={},
    )
    empty_test_context = repo_audit.PythonSourceScanContext(source_root=tmp_path / "tests", texts={}, asts={})
    empty_scripts_context = repo_audit.PythonSourceScanContext(source_root=tmp_path / "scripts", texts={}, asts={})
    text_finding = repo_audit.Finding(
        "hardcoded-windows-path",
        "portability",
        "high",
        "high",
        "Absolute Windows path committed to the repository.",
        path="README.md",
    )
    docs_finding = repo_audit.Finding(
        "documented-missing-subcommand",
        "feature-wiring",
        "medium",
        "high",
        "Documented CLI subcommand 'ghost' is not implemented.",
        path="README.md",
        line=1,
    )
    unused_key_finding = repo_audit.Finding(
        "unused-config-key",
        "configuration-hygiene",
        "medium",
        "medium",
        "Config key 'unused' appears to be declared but unused.",
        path="src/sattlint/config.py",
    )
    structural_finding = repo_audit.Finding(
        "structural-facade-private-boundary",
        "architecture",
        "medium",
        "high",
        "Facade calls private helper.",
        path="src/sattlint/app.py",
    )
    logging_finding = repo_audit.Finding(
        "unexpected-print",
        "logging-observability",
        "medium",
        "medium",
        "Library module uses print() instead of structured logging or return values.",
        path="src/sattlint/alpha.py",
    )
    readiness_finding = repo_audit.Finding(
        "missing-ci-workflow",
        "public-readiness",
        "medium",
        "high",
        "Repository has no CI workflow.",
    )

    with (
        patch.object(
            repo_audit, "_list_tracked_repo_paths", return_value=("README.md", "src/sattlint/alpha.py")
        ) as tracked,
        patch.object(repo_audit, "_iter_repo_text_entries", return_value=[(readme, "repo docs\n")]) as iter_entries,
        patch.object(repo_audit, "_line_findings", return_value=[text_finding]) as line_findings,
        patch.object(
            repo_audit,
            "_build_python_source_scan_context",
            side_effect=[source_context, empty_test_context, empty_scripts_context],
        ) as build_context,
        patch.object(repo_audit, "_collect_cli_metadata", return_value=({"sattlint-repo-audit"}, {"syntax-check"})),
        patch.object(
            repo_audit,
            "_extract_documented_commands",
            return_value=[repo_audit.DocumentedCommand("sattlint", "ghost", "README.md", 1)],
        ) as extract_commands,
        patch.object(repo_audit, "_find_documentation_command_gaps", return_value=[docs_finding]),
        patch.object(repo_audit, "_find_unused_config_keys", return_value=[unused_key_finding]) as unused_keys,
        patch.object(repo_audit, "_find_architecture_findings", return_value=[]),
        patch.object(repo_audit, "_find_structural_report_findings", return_value=[structural_finding]),
        patch.object(repo_audit, "_find_cli_findings", return_value=[]),
        patch.object(repo_audit, "_find_logging_findings", return_value=[logging_finding]) as logging_findings,
        patch.object(repo_audit, "_find_ignored_repo_path_references", return_value=[]) as ignored_path_refs,
        patch.object(repo_audit, "_run_harness_freshness_check", return_value=[]),
        patch.object(repo_audit_entrypoints, "_run_verify_recommendations_check", return_value=[]),
        patch.object(repo_audit, "_parse_coverage_findings", return_value=[docs_finding]) as coverage_findings,
        patch.object(
            repo_audit, "_find_public_readiness_findings", return_value=[readiness_finding]
        ) as readiness_findings,
    ):
        findings = repo_audit.collect_custom_findings(
            tmp_path,
            include_generated=True,
            tracked_only=True,
            suspicious_identifiers=[" SQHJ ", ""],
        )

    tracked.assert_called_once_with(tmp_path)
    iter_entries.assert_called_once_with(tmp_path, include_generated=True, tracked_only=True)
    line_findings.assert_called_once_with(readme, "repo docs\n", {"SQHJ"}, root=tmp_path)
    assert build_context.call_args_list == [
        call(
            tmp_path / "src",
            root=tmp_path,
            tracked_paths=("README.md", "src/sattlint/alpha.py"),
        ),
        call(
            tmp_path / "tests",
            root=tmp_path,
            tracked_paths=("README.md", "src/sattlint/alpha.py"),
        ),
        call(
            tmp_path / "scripts",
            root=tmp_path,
            tracked_paths=("README.md", "src/sattlint/alpha.py"),
        ),
    ]
    extracted_paths = list(extract_commands.call_args.args[0])
    assert extracted_paths == [readme, vscode_readme]
    assert unused_keys.call_args.args[0] == tmp_path / "src" / "sattlint"
    assert unused_keys.call_args.kwargs["content_by_file"] == {
        tmp_path / "src" / "sattlint" / "alpha.py": "ALPHA = 1\n",
    }
    logging_findings.assert_called_once_with(tmp_path / "src", content_by_file=source_context.texts)
    assert ignored_path_refs.call_count == 3
    coverage_findings.assert_called_once_with(tmp_path, tracked_paths=("README.md", "src/sattlint/alpha.py"))
    readiness_findings.assert_called_once_with(tmp_path, tracked_paths=("README.md", "src/sattlint/alpha.py"))
    assert [finding.id for finding in findings] == [
        "hardcoded-windows-path",
        "documented-missing-subcommand",
        "unused-config-key",
        "structural-facade-private-boundary",
        "unexpected-print",
        "missing-ci-workflow",
    ]


def test_find_structural_report_findings_translates_structural_architecture_findings(tmp_path):
    architecture_report = {
        "findings": [
            {
                "id": "structural-facade-private-boundary",
                "severity": "medium",
                "message": "Facade calls private helper.",
                "private_entrypoints": [
                    {
                        "path": "src/sattlint/app.py",
                        "line": 42,
                        "target": "app_analysis._run_checks",
                    }
                ],
            },
            {
                "id": "analyzer-exposure-gap",
                "severity": "medium",
                "message": "Non-structural finding should stay in architecture report only.",
            },
        ]
    }

    with patch("sattlint.devtools.structural_reports.collect_architecture_report", return_value=architecture_report):
        findings = repo_audit._find_structural_report_findings(tmp_path)

    assert len(findings) == 1
    assert findings[0].id == "structural-facade-private-boundary"
    assert findings[0].path == "src/sattlint/app.py"
    assert findings[0].detail == "calls app_analysis._run_checks at line 42"
    assert findings[0].source == "structural-reports"


def test_audit_repository_fail_policy_applies_to_structural_findings(tmp_path):
    pipeline_summary = {
        "profile": "quick",
        "output_dir": "<external>/audit/pipeline",
        "status": {"overall_status": "pass", "tool_statuses": {}},
    }
    structural_finding = repo_audit.Finding(
        "structural-budget-ratchet-regression",
        "architecture",
        "medium",
        "high",
        "Structural debt regressed beyond ratchet baseline.",
        detail="function_over_budget_count: 14 > 13",
        source="structural-reports",
    )

    with (
        patch.object(repo_audit, "collect_custom_findings", return_value=[structural_finding]),
        patch.object(repo_audit, "_find_pipeline_findings", return_value=[]),
        patch.object(repo_audit.pipeline_module, "_run_pipeline", return_value=pipeline_summary),
    ):
        summary = repo_audit.audit_repository(
            tmp_path,
            profile="quick",
            fail_on="medium",
            include_generated=False,
            leaks_only=False,
            suspicious_identifiers=["SQHJ"],
            skip_pipeline=False,
            skip_vulture=False,
            skip_bandit=False,
        )

    status_report = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))

    assert summary["finding_count"] == 1
    assert summary["findings"][0]["id"] == "structural-budget-ratchet-regression"
    assert status_report["overall_status"] == "fail"
    assert status_report["blocking_finding_count"] == 1
