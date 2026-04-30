import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from sattlint.devtools import doc_gardener, repo_audit

from .helpers.artifact_assertions import assert_findings_collection, assert_findings_schema


def _patch_doc_gardener_paths(repo_root: Path):
    return patch.multiple(
        doc_gardener,
        REPO_ROOT=repo_root,
        DOCS_DIR=repo_root / "docs",
        AGENTS_MD=repo_root / "AGENTS.md",
        QUALITY_SCORE=repo_root / "docs" / "quality-score.md",
        TECH_DEBT=repo_root / "docs" / "exec-plans" / "tech-debt-tracker.md",
        CURRENT_WORK=repo_root / ".github" / "coordination" / "current-work.md",
        AI_FIRST_PLAN=repo_root / "docs" / "exec-plans" / "active" / "ai-first-repo-hardening.md",
        AI_FIRST_DEBT=repo_root / "docs" / "exec-plans" / "tech-debt-tracker.md",
    )


def test_extract_documented_commands_reads_script_and_subcommand(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "Run `sattlint syntax-check demo.s` and `sattlint-repo-audit --output-dir artifacts/audit`.\n",
        encoding="utf-8",
    )

    commands = repo_audit._extract_documented_commands([readme], root=tmp_path)

    assert repo_audit.DocumentedCommand("sattlint", "syntax-check", "README.md", 1) in commands
    assert repo_audit.DocumentedCommand("sattlint-repo-audit", None, "README.md", 1) in commands


def test_find_documentation_command_gaps_flags_missing_command():
    commands = [
        repo_audit.DocumentedCommand("sattlint", "missing", "README.md", 10),
        repo_audit.DocumentedCommand("sattlint-missing", None, "README.md", 11),
    ]

    findings = repo_audit._find_documentation_command_gaps(commands, {"sattlint-repo-audit"}, {"syntax-check"})

    assert {finding.id for finding in findings} == {
        "documented-missing-subcommand",
        "documented-missing-script",
    }


def test_find_unused_config_keys_reports_unreferenced_key(tmp_path):
    source_root = tmp_path / "src" / "sattlint"
    source_root.mkdir(parents=True)
    (source_root / "config.py").write_text(
        'DEFAULT_CONFIG = {"used": 1, "unused": 2}\n',
        encoding="utf-8",
    )
    (source_root / "consumer.py").write_text(
        'cfg = {"used": True}\n',
        encoding="utf-8",
    )

    findings = repo_audit._find_unused_config_keys(source_root, ["used", "unused"])

    assert len(findings) == 1
    assert findings[0].message == "Config key 'unused' appears to be declared but unused."


def test_line_findings_redact_email_and_flag_path(tmp_path):
    sample = tmp_path / "sample.py"
    text = 'EMAIL = "person@example.com"\nROOT = r"C:/Users/SQHJ/Workspace"\n'

    findings = repo_audit._line_findings(sample, text, {"SQHJ"}, root=tmp_path)

    assert any(finding.id == "email-address" and "p***@example.com" in (finding.detail or "") for finding in findings)
    assert any(finding.id == "hardcoded-windows-path" for finding in findings)
    assert any(finding.id == "suspicious-identifier" for finding in findings)


def test_line_findings_skip_vendor_and_fixture_content(tmp_path):
    vendor_file = tmp_path / "Libs" / "HA" / "Sample.x"
    vendor_file.parent.mkdir(parents=True)
    fixture_file = tmp_path / "tests" / "fixtures" / "sample.s"
    fixture_file.parent.mkdir(parents=True)
    text = 'ROOT = r"C:/Users/SQHJ/Workspace"\n'

    vendor_findings = repo_audit._line_findings(vendor_file, text, {"SQHJ"}, root=tmp_path)
    fixture_findings = repo_audit._line_findings(fixture_file, text, {"SQHJ"}, root=tmp_path)

    assert vendor_findings == []
    assert fixture_findings == []


def test_iter_repo_text_files_skips_virtualenv_variants(tmp_path):
    venv_file = tmp_path / ".venv-py311-backup" / "Lib" / "site-packages" / "sample.py"
    venv_file.parent.mkdir(parents=True)
    venv_file.write_text('ROOT = r"C:/Users/SQHJ/Workspace"\n', encoding="utf-8")
    repo_file = tmp_path / "src" / "sample.py"
    repo_file.parent.mkdir(parents=True)
    repo_file.write_text("print('ok')\n", encoding="utf-8")

    files = {_path.as_posix() for _path in repo_audit._iter_repo_text_files(tmp_path, include_generated=False)}

    assert repo_file.as_posix() in files
    assert venv_file.as_posix() not in files


def test_line_findings_ignore_grammar_token_constants(tmp_path):
    sample = tmp_path / "constants.py"
    text = 'TOKEN_NEW = "NEW"\nTOKEN_OLD = "OLD"\nTOKEN_VARNAME = "VARNAME"\n'

    findings = repo_audit._line_findings(sample, text, set(), root=tmp_path)

    assert not any(finding.id == "secret-assignment" for finding in findings)


def test_line_findings_flag_secret_assignment_suffix_names(tmp_path):
    sample = tmp_path / "config.py"
    text = 'github_token = "super-secret-value"\n'

    findings = repo_audit._line_findings(sample, text, set(), root=tmp_path)

    assert any(finding.id == "secret-assignment" for finding in findings)


def test_load_pyproject_accepts_cp1252_toml(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes('[project]\nname = "demo"\nauthors = [{ name = "Søren" }]\n'.encode("cp1252"))

    payload = repo_audit._load_pyproject(tmp_path)

    assert payload["project"]["name"] == "demo"


def test_find_logging_findings_ignore_fingerprint_identifier(tmp_path):
    source_root = tmp_path / "src"
    source_root.mkdir()
    sample = source_root / "sample.py"
    sample.write_text(
        "def build_name():\n    return ModuleFingerprint(value)\n",
        encoding="utf-8",
    )

    findings = repo_audit._find_logging_findings(source_root)

    assert findings == []


def test_iter_tracked_repo_text_files_includes_tracked_generated_files(tmp_path):
    tracked_artifact = tmp_path / "artifacts" / "audit" / "pipeline" / "trace.json"
    tracked_artifact.parent.mkdir(parents=True)
    tracked_artifact.write_text('{"source_file": "C:/Users/SQHJ/Workspace"}\n', encoding="utf-8")
    tracked_source = tmp_path / "src" / "sample.py"
    tracked_source.parent.mkdir(parents=True)
    tracked_source.write_text("print('ok')\n", encoding="utf-8")

    completed = subprocess.CompletedProcess(
        args=["git", "ls-files", "-z"],
        returncode=0,
        stdout=b"artifacts/audit/pipeline/trace.json\x00src/sample.py\x00",
        stderr=b"",
    )

    with (
        patch("sattlint.devtools.repo_audit.shutil.which", return_value="git"),
        patch("sattlint.devtools.repo_audit.subprocess.run", return_value=completed),
    ):
        files = {
            _path.relative_to(tmp_path).as_posix()
            for _path in repo_audit._iter_tracked_repo_text_files(tmp_path, include_generated=True)
        }

    assert "artifacts/audit/pipeline/trace.json" in files
    assert "src/sample.py" in files


def test_build_python_source_scan_context_uses_tracked_files_only(tmp_path):
    tracked_file = tmp_path / "src" / "tracked.py"
    tracked_file.parent.mkdir(parents=True)
    tracked_file.write_text("VALUE = 1\n", encoding="utf-8")
    untracked_file = tmp_path / "src" / "generated.py"
    untracked_file.write_text("VALUE = 2\n", encoding="utf-8")

    context = repo_audit._build_python_source_scan_context(
        tmp_path / "src",
        root=tmp_path,
        tracked_paths=("src/tracked.py",),
    )

    assert {path.relative_to(tmp_path).as_posix() for path in context.texts} == {"src/tracked.py"}


def test_build_python_source_scan_context_skips_missing_tracked_files(tmp_path):
    tracked_file = tmp_path / "src" / "tracked.py"
    tracked_file.parent.mkdir(parents=True)
    tracked_file.write_text("VALUE = 1\n", encoding="utf-8")

    context = repo_audit._build_python_source_scan_context(
        tmp_path / "src",
        root=tmp_path,
        tracked_paths=("src/tracked.py", "src/missing.py"),
    )

    assert {path.relative_to(tmp_path).as_posix() for path in context.texts} == {"src/tracked.py"}


def test_parse_coverage_findings_ignores_untracked_coverage_xml(tmp_path):
    coverage_path = tmp_path / "coverage.xml"
    coverage_path.write_text(
        """
<coverage>
    <packages>
        <package>
            <classes>
                <class filename="src/sample.py" line-rate="0.05" />
            </classes>
        </package>
    </packages>
</coverage>
""".strip(),
        encoding="utf-8",
    )

    findings = repo_audit._parse_coverage_findings(tmp_path, tracked_paths=("README.md",))

    assert findings == []


def test_find_public_readiness_findings_ignores_untracked_workflow(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8")
    workflow_path = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow_path.parent.mkdir(parents=True)
    workflow_path.write_text("name: CI\n", encoding="utf-8")

    findings = repo_audit._find_public_readiness_findings(
        tmp_path,
        tracked_paths=("README.md", "LICENSE", "CONTRIBUTING.md", ".gitignore", "pyproject.toml"),
    )

    assert any(finding.id == "missing-ci-workflow" for finding in findings)


def test_audit_repository_leaks_only_filters_findings_and_skips_pipeline(tmp_path):
    leak_finding = repo_audit.Finding(
        "hardcoded-windows-path",
        "portability",
        "high",
        "high",
        "Absolute Windows path committed to the repository.",
        path="artifacts/audit/pipeline/trace.json",
    )
    non_leak_finding = repo_audit.Finding(
        "oversized-module",
        "architecture",
        "medium",
        "high",
        "Large module with high maintenance cost.",
        path="src/big.py",
    )

    with (
        patch.object(repo_audit, "collect_custom_findings", return_value=[leak_finding, non_leak_finding]),
        patch.object(repo_audit.pipeline_module, "_run_pipeline") as run_pipeline,
    ):
        summary = repo_audit.audit_repository(
            tmp_path,
            profile="full",
            fail_on="medium",
            include_generated=False,
            leaks_only=True,
            suspicious_identifiers=["SQHJ"],
            skip_pipeline=False,
            skip_vulture=False,
            skip_bandit=False,
        )

    run_pipeline.assert_not_called()
    assert summary["output_dir"] == f"<external>/{tmp_path.name}"
    assert summary["profile"] == "leaks"
    assert summary["pipeline_ran"] is False
    assert [finding["id"] for finding in summary["findings"]] == ["hardcoded-windows-path"]


def test_find_pipeline_findings_prefers_normalized_findings_report(tmp_path):
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
        patch.object(repo_audit, "_build_python_source_scan_context", return_value=source_context) as build_context,
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
    build_context.assert_called_once_with(
        tmp_path / "src",
        root=tmp_path,
        tracked_paths=("README.md", "src/sattlint/alpha.py"),
    )
    extracted_paths = list(extract_commands.call_args.args[0])
    assert extracted_paths == [readme, vscode_readme]
    assert unused_keys.call_args.args[0] == tmp_path / "src" / "sattlint"
    assert unused_keys.call_args.kwargs["content_by_file"] == {
        tmp_path / "src" / "sattlint" / "alpha.py": "ALPHA = 1\n",
    }
    logging_findings.assert_called_once_with(tmp_path / "src", content_by_file=source_context.texts)
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

    with patch.object(
        repo_audit.structural_reports_module, "collect_architecture_report", return_value=architecture_report
    ):
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


def test_doc_gardener_flags_markdown_mojibake(tmp_path):
    docs_dir = tmp_path / "docs" / "exec-plans" / "active"
    docs_dir.mkdir(parents=True)
    markdown_file = docs_dir / "ai-first-repo-hardening.md"
    markdown_file.write_text(f"Broken sequence {doc_gardener.MOJIBAKE_TOKENS[1]} here\n", encoding="utf-8")

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_markdown_encoding_artifacts()

    assert len(findings) == 1
    assert findings[0].category == "encoding"
    assert findings[0].file == "docs/exec-plans/active/ai-first-repo-hardening.md"


def test_doc_gardener_flags_retired_source_file_reintroduced(tmp_path):
    debt_file = tmp_path / "docs" / "exec-plans" / "tech-debt-tracker.md"
    debt_file.parent.mkdir(parents=True)
    debt_file.write_text(
        """
## Consolidation Source Ledger

| Source | State | Snapshot | Sync Basis | Coverage | Notes |
|---|---|---|---|---|---|
| TODO_GUI.md | retired | 2026-04-29 | retired | Program E | Imported |
| TODO_REFACTOR.md | retired | 2026-04-29 | retired | Program B | Imported |
| TODO_SATTLINT.md | retired | 2026-04-29 | retired | Program C | Imported |
| TODO_TOOLS.md | retired | 2026-04-29 | retired | Program D | Imported |
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "TODO_GUI.md").write_text("restored backlog\n", encoding="utf-8")

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_ai_first_source_drift()

    assert len(findings) == 1
    assert findings[0].category == "drift"
    assert "marks it retired" in findings[0].message


def test_doc_gardener_flags_refactor_status_mismatch(tmp_path):
    debt_file = tmp_path / "docs" / "exec-plans" / "tech-debt-tracker.md"
    debt_file.parent.mkdir(parents=True)
    debt_file.write_text(
        """
## Program B: Refactor And Architecture Debt

| Debt ID | Priority | Owner | Target Window | Source Lane | Item | Status | Notes |
|---|---|---|---|---|---|---|---|
| B-W6 | P0 | Parser core | 2026-Q2 | W6 | Parser structural split for SLTransformer | Open | Still underway |
""".strip(),
        encoding="utf-8",
    )
    current_work = tmp_path / ".github" / "coordination" / "current-work.md"
    current_work.parent.mkdir(parents=True)
    current_work.write_text(
        """
## Active Workstreams

### Workstream w6-parser-transformer-split-068

- Status: active
""".strip(),
        encoding="utf-8",
    )

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_ai_first_status_drift()

    assert len(findings) == 1
    assert findings[0].category == "stale_status"
    assert "B-W6" in findings[0].message


def test_doc_gardener_main_exits_nonzero_when_findings_exist():
    result = {
        "total_findings": 1,
        "by_severity": {"Critical": 0, "High": 0, "Medium": 1, "Low": 0},
        "by_category": {
            "stale": 0,
            "dead_link": 0,
            "too_long": 0,
            "missing": 0,
            "structure": 0,
            "encoding": 1,
            "drift": 0,
            "stale_status": 0,
        },
        "findings": [
            {
                "file": "docs/exec-plans/active/ai-first-repo-hardening.md",
                "line": 1,
                "severity": "Medium",
                "category": "encoding",
                "message": "Possible mojibake tokens in markdown content: —",
            }
        ],
    }

    with (
        patch.object(doc_gardener, "run_scan", return_value=result),
        patch.object(doc_gardener, "update_quality_score"),
        patch.object(doc_gardener, "update_tech_debt_scan_log"),
        patch.object(doc_gardener, "open_fixup_pr", return_value=False),
        pytest.raises(SystemExit) as exc,
    ):
        doc_gardener.main()

    assert exc.value.code == 1


def test_print_cli_summary_includes_findings_schema(capsys):
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
        patch.object(repo_audit, "_find_pipeline_findings", return_value=[]),
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

    assert stale_file.exists() is True
    assert latest_status["latest_status_report"].endswith("/audit/status.json")
    assert latest_status["latest_summary_report"].endswith("/audit/summary.json")
    assert latest_summary["finding_count"] == 1
    assert_findings_collection(mirrored_findings, finding_count=1)
    assert mirrored_findings["findings"][0]["id"] == "oversized-module"


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


# --- ID 19: Coverage summary report tests ---

_COVERAGE_XML_TEMPLATE = """\
<coverage>
    <packages>
        <package>
            <classes>
                {classes}
            </classes>
        </package>
    </packages>
</coverage>
"""


def _write_coverage_xml(root: Path, classes_xml: str) -> None:
    (root / "coverage.xml").write_text(
        _COVERAGE_XML_TEMPLATE.format(classes=classes_xml).strip(),
        encoding="utf-8",
    )


def test_build_coverage_summary_report_returns_skipped_when_no_coverage_xml(tmp_path):
    report = repo_audit.build_coverage_summary_report(tmp_path)

    assert report["skipped"] is True
    assert report["kind"] == "sattlint.coverage_summary"
    assert report["schema_version"] == 1
    assert report["modules"] == []
    assert report["findings"] == []
    assert report["summary"]["module_count"] == 0


def test_build_coverage_summary_report_emits_low_coverage_findings(tmp_path):
    _write_coverage_xml(
        tmp_path,
        '<class filename="src/sattlint/some_module.py" line-rate="0.05" lines-valid="100" />'
        '<class filename="src/sattlint/other_module.py" line-rate="0.35" lines-valid="50" />'
        '<class filename="src/sattlint/good_module.py" line-rate="0.80" lines-valid="200" />',
    )

    report = repo_audit.build_coverage_summary_report(tmp_path)

    assert report["skipped"] is False
    assert report["summary"]["module_count"] == 3
    assert report["summary"]["low_coverage_count"] == 2

    severities = {f["severity"] for f in report["findings"]}
    assert "high" in severities  # 5% < 10%
    assert "medium" in severities  # 35% < 40%

    paths_in_findings = {f["path"] for f in report["findings"]}
    assert "src/sattlint/good_module.py" not in paths_in_findings


def test_build_coverage_summary_report_skips_non_src_modules(tmp_path):
    _write_coverage_xml(
        tmp_path,
        '<class filename="tests/test_something.py" line-rate="0.05" lines-valid="50" />'
        '<class filename="src/sattlint/real_module.py" line-rate="0.90" lines-valid="200" />',
    )

    report = repo_audit.build_coverage_summary_report(tmp_path)

    assert report["summary"]["module_count"] == 1
    assert report["summary"]["low_coverage_count"] == 0
    assert all(m["path"].startswith("src/") for m in report["modules"])


def test_build_coverage_summary_report_includes_avg_line_rate(tmp_path):
    _write_coverage_xml(
        tmp_path,
        '<class filename="src/a.py" line-rate="0.20" lines-valid="100" />'
        '<class filename="src/b.py" line-rate="0.80" lines-valid="100" />',
    )

    report = repo_audit.build_coverage_summary_report(tmp_path)

    assert report["summary"]["avg_line_rate"] == pytest.approx(0.5, abs=0.01)


# --- ID 31: CLI consistency report tests ---


def test_build_cli_consistency_report_has_required_schema_fields():
    report = repo_audit.build_cli_consistency_report()

    assert report["kind"] == "sattlint.cli_consistency"
    assert report["schema_version"] == 1
    assert "declared" in report
    assert "scripts" in report["declared"]
    assert "subcommands" in report["declared"]
    assert "gaps" in report
    assert "summary" in report
    assert "status" in report
    assert report["status"] in ("pass", "fail")


def test_build_cli_consistency_report_lists_declared_scripts_and_subcommands():
    report = repo_audit.build_cli_consistency_report()

    # sattlint itself should be in scripts
    assert any("sattlint" in s for s in report["declared"]["scripts"])
    # At least one subcommand should be declared
    assert len(report["declared"]["subcommands"]) > 0


def test_build_cli_consistency_report_gap_counts_match_gap_lists():
    report = repo_audit.build_cli_consistency_report()

    gaps = report["gaps"]
    summary = report["summary"]

    assert summary["undeclared_subcommand_count"] == len(gaps["undeclared_subcommands"])
    assert summary["undeclared_script_count"] == len(gaps["undeclared_scripts"])
    assert summary["undocumented_subcommand_count"] == len(gaps["undocumented_subcommands"])
    assert summary["undocumented_script_count"] == len(gaps["undocumented_scripts"])
    expected_gap_count = summary["undeclared_subcommand_count"] + summary["undeclared_script_count"]
    assert summary["gap_count"] == expected_gap_count


def test_build_cli_consistency_report_detects_undeclared_subcommand(tmp_path, monkeypatch):
    """Documented subcommand that is not in the parser should appear in undeclared_subcommands."""
    readme = tmp_path / "README.md"
    readme.write_text("Run `sattlint ghost-command` to do something.\n", encoding="utf-8")

    monkeypatch.setattr(
        repo_audit,
        "_collect_cli_metadata",
        lambda: ({"sattlint"}, {"syntax-check", "analyze"}),
    )

    report = repo_audit.build_cli_consistency_report(root=tmp_path)

    undeclared_names = [g["subcommand"] for g in report["gaps"]["undeclared_subcommands"]]
    assert "ghost-command" in undeclared_names
    assert report["summary"]["gap_count"] > 0
    assert report["status"] == "fail"


def test_build_cli_consistency_report_pass_when_all_documented_subcommands_are_declared(tmp_path, monkeypatch):
    readme = tmp_path / "README.md"
    readme.write_text("Run `sattlint syntax-check` to check syntax.\n", encoding="utf-8")

    monkeypatch.setattr(
        repo_audit,
        "_collect_cli_metadata",
        lambda: ({"sattlint"}, {"syntax-check"}),
    )

    report = repo_audit.build_cli_consistency_report(root=tmp_path)

    assert report["gaps"]["undeclared_subcommands"] == []
    assert report["summary"]["undeclared_subcommand_count"] == 0


def test_doc_gardener_relative_path_returns_repo_relative():
    from pathlib import Path

    with patch.multiple(
        doc_gardener,
        REPO_ROOT=Path("/repo"),
    ):
        result = doc_gardener._relative_path(Path("/repo/src/sample.py"))

        assert result == "src/sample.py"


def test_doc_gardener_relative_path_falls_back_to_posix_when_not_relative():
    from pathlib import Path

    with patch.multiple(
        doc_gardener,
        REPO_ROOT=Path("/repo"),
    ):
        result = doc_gardener._relative_path(Path("/other/sample.py"))

        assert result == "/other/sample.py"


def test_doc_gardener_read_text_handles_utf8(tmp_path):
    sample_file = tmp_path / "sample.txt"
    text = "Normal ASCII text\n"
    sample_file.write_bytes(text.encode("utf-8"))

    result = doc_gardener._read_text(sample_file)

    assert result == text


def test_doc_gardener_should_skip_path_identifies_venv_dirs():
    from pathlib import Path

    assert doc_gardener._should_skip_path(Path("/repo/.venv/lib/sample.py")) is True
    assert doc_gardener._should_skip_path(Path("/repo/.venv-backup/lib/sample.py")) is True
    assert doc_gardener._should_skip_path(Path("/repo/__pycache__/sample.py")) is True
    assert doc_gardener._should_skip_path(Path("/repo/src/sample.py")) is False


def test_doc_gardener_normalize_workstream_id_parses_w_prefixed():
    assert doc_gardener._normalize_workstream_id("W1") == "W1"
    assert doc_gardener._normalize_workstream_id("w1") == "W1"
    assert doc_gardener._normalize_workstream_id("w1-something") == "W1"
    assert doc_gardener._normalize_workstream_id("B-W3") == "W3"
    assert doc_gardener._normalize_workstream_id("invalid") is None


def test_doc_gardener_normalize_status_maps_common_aliases():
    assert doc_gardener._normalize_status("active") == "In progress"
    assert doc_gardener._normalize_status("in progress") == "In progress"
    assert doc_gardener._normalize_status("open") == "Open"
    assert doc_gardener._normalize_status("planned") == "Open"
    assert doc_gardener._normalize_status("blocked") == "Blocked"
    assert doc_gardener._normalize_status("done") == "Done"


def test_doc_gardener_parse_markdown_table_extracts_rows():
    lines = [
        "## Section Header",
        "| Name | Value |",
        "| --- | --- |",
        "| Item1 | 100 |",
        "| Item2 | 200 |",
    ]

    result = doc_gardener._parse_markdown_table(lines, "## Section Header")

    assert len(result) == 2
    assert result[0][1]["Name"] == "Item1"
    assert result[0][1]["Value"] == "100"
    assert result[1][1]["Name"] == "Item2"


def test_doc_gardener_parse_markdown_table_stops_at_next_section():
    lines = [
        "## Section 1",
        "| Name | Value |",
        "| --- | --- |",
        "| Item1 | 100 |",
        "## Section 2",
        "| Name | Value |",
        "| --- | --- |",
        "| Item2 | 200 |",
    ]

    result = doc_gardener._parse_markdown_table(lines, "## Section 1")

    assert len(result) == 1
    assert result[0][1]["Name"] == "Item1"


def test_doc_gardener_parse_current_work_statuses_extracts_status_from_workstream():
    text = """
### Workstream W1-something
- Status: active

### Workstream W2
- Status: blocked
"""

    result = doc_gardener._parse_current_work_statuses(text)

    assert result.get("W1") == "In progress"
    assert result.get("W2") == "Blocked"


def test_doc_gardener_source_sync_digest_is_deterministic():
    from pathlib import Path

    tmp_file = Path("/tmp/test_doc.txt")
    with patch.object(Path, "read_bytes", return_value=b"test content"):
        digest1 = doc_gardener._source_sync_digest(tmp_file)
        digest2 = doc_gardener._source_sync_digest(tmp_file)

    assert digest1 == digest2
    assert len(digest1) == 12
