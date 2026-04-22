import json
import subprocess
from unittest.mock import patch

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
    pyproject.write_bytes(
        '[project]\nname = "demo"\nauthors = [{ name = "Søren" }]\n'.encode("cp1252")
    )

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

    with patch("sattlint.devtools.repo_audit.shutil.which", return_value="git"):
        with patch("sattlint.devtools.repo_audit.subprocess.run", return_value=completed):
            files = {
                _path.relative_to(tmp_path).as_posix()
                for _path in repo_audit._iter_tracked_repo_text_files(tmp_path, include_generated=True)
            }

    assert "artifacts/audit/pipeline/trace.json" in files
    assert "src/sample.py" in files


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

    with patch.object(repo_audit, "collect_custom_findings", return_value=[leak_finding, non_leak_finding]):
        with patch.object(repo_audit.pipeline_module, "_run_pipeline") as run_pipeline:
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

    with patch.object(repo_audit, "collect_custom_findings", return_value=[finding]):
        with patch.object(repo_audit, "_find_pipeline_findings", return_value=[]):
            with patch.object(repo_audit.pipeline_module, "_run_pipeline", return_value=pipeline_summary) as run_pipeline:
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
    assert run_pipeline.call_args.kwargs["corpus_manifest_dir"] == repo_audit.pipeline_module.DEFAULT_CORPUS_MANIFEST_DIR.resolve()


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

    with patch.object(repo_audit, "collect_custom_findings", return_value=[finding]):
        with patch.object(repo_audit, "_find_pipeline_findings", return_value=[]):
            with patch.object(repo_audit.pipeline_module, "_run_pipeline", return_value=pipeline_summary):
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
