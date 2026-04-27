import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from sattlint.devtools import repo_audit

from .helpers.artifact_assertions import assert_findings_collection, assert_findings_schema


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
