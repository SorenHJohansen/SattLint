import json
import os
import subprocess
import time
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import call, patch

import pytest

from sattlint.devtools import doc_gardener, repo_audit, repo_audit_entrypoints
from sattlint.devtools.pipeline_artifacts import artifact_source_manifest_path, write_json_artifact

from .helpers.artifact_assertions import assert_findings_collection, assert_findings_schema


def _patch_doc_gardener_paths(repo_root: Path):
    return patch.multiple(
        doc_gardener,
        REPO_ROOT=repo_root,
        DOCS_DIR=repo_root / "docs",
        AGENTS_MD=repo_root / "AGENTS.md",
        QUALITY_SCORE=repo_root / "docs" / "quality-score.md",
        TECH_DEBT=repo_root / "docs" / "exec-plans" / "tech-debt-tracker.md",
        CURRENT_WORK=repo_root / ".github" / "coordination" / "current_work_lock.json",
        CURRENT_WORK_TEMPLATE=repo_root / ".github" / "coordination" / "current-work.template.md",
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


def test_build_local_import_graph_skips_type_checking_and_resolves_relative_imports(tmp_path):
    source_root = tmp_path / "src"
    package_dir = source_root / "pkg"
    package_dir.mkdir(parents=True)
    module_a = package_dir / "a.py"
    module_b = package_dir / "b.py"
    module_c = package_dir / "c.py"

    graph = repo_audit._build_local_import_graph(
        source_root,
        content_by_file={
            module_a: "import pkg.b\n",
            module_b: (
                "from typing import TYPE_CHECKING\nfrom .c import helper\nif TYPE_CHECKING:\n    import pkg.a\n"
            ),
            module_c: "helper = object()\n",
        },
    )

    assert graph == {
        "pkg.a": {"pkg.b"},
        "pkg.b": {"pkg.c"},
        "pkg.c": set(),
    }


def test_find_import_cycles_returns_back_edge_cycle():
    graph = {
        "pkg.a": {"pkg.b"},
        "pkg.b": {"pkg.c"},
        "pkg.c": {"pkg.a"},
        "pkg.d": set(),
    }

    assert repo_audit._find_import_cycles(graph) == [["pkg.a", "pkg.b", "pkg.c", "pkg.a"]]


def test_find_architecture_findings_reports_cycle_size_and_core_coupling(tmp_path):
    source_root = tmp_path / "src"
    package_dir = source_root / "pkg"
    semantic_path = source_root / "sattlint" / "core" / "semantic.py"
    package_dir.mkdir(parents=True)
    semantic_path.parent.mkdir(parents=True)
    module_a = package_dir / "a.py"
    module_b = package_dir / "b.py"
    oversized = package_dir / "oversized.py"
    semantic_path.write_text(
        "from sattlint.analyzers.variables import VariablesAnalyzer\n",
        encoding="utf-8",
    )

    findings = repo_audit._find_architecture_findings(
        source_root,
        content_by_file={
            module_a: "import pkg.b\n",
            module_b: "import pkg.a\n",
            oversized: "\n".join("value = 1" for _ in range(repo_audit.OVERSIZED_MODULE_LINE_LIMIT)),
            semantic_path: "from sattlint.analyzers.variables import VariablesAnalyzer\n",
        },
    )

    finding_ids = {finding.id for finding in findings}
    cycle_finding = next(finding for finding in findings if finding.id == "import-cycle")
    oversized_finding = next(finding for finding in findings if finding.id == "oversized-module")
    coupling_finding = next(finding for finding in findings if finding.id == "core-analyzer-coupling")

    assert finding_ids >= {"import-cycle", "oversized-module", "core-analyzer-coupling"}
    assert cycle_finding.severity == "high"
    assert cycle_finding.detail == "pkg.a -> pkg.b -> pkg.a"
    assert oversized_finding.severity == "medium"
    assert f"{repo_audit.OVERSIZED_MODULE_LINE_LIMIT} non-empty lines" == oversized_finding.detail
    assert coupling_finding.path is not None


def test_find_cli_findings_flags_missing_parser_and_subcommand_descriptions(monkeypatch):
    parser = SimpleNamespace(
        description=None,
        _actions=[SimpleNamespace(choices={"syntax-check": SimpleNamespace(description=None)})],
    )
    monkeypatch.setattr(repo_audit.app_module, "build_cli_parser", lambda: parser)

    findings = repo_audit._find_cli_findings()

    assert [finding.id for finding in findings] == [
        "cli-missing-description",
        "cli-missing-subcommand-description",
    ]


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


def test_copy_audit_snapshot_skips_files_removed_during_copy(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    snapshot_dir = tmp_path / "snapshot"
    missing_file = source_dir / "status.json"
    kept_file = source_dir / "summary.json"
    source_dir.mkdir(parents=True)
    missing_file.write_text("status", encoding="utf-8")
    kept_file.write_text("summary", encoding="utf-8")

    original_copy2 = repo_audit.shutil.copy2

    def fake_copy2(source: Path, target: Path):
        if source == missing_file:
            missing_file.unlink()
            raise FileNotFoundError(source)
        return original_copy2(source, target)

    monkeypatch.setattr(repo_audit.shutil, "copy2", fake_copy2)

    repo_audit._copy_audit_snapshot(source_dir, snapshot_dir)

    assert not (snapshot_dir / "status.json").exists()
    assert (snapshot_dir / "summary.json").read_text(encoding="utf-8") == "summary"


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


def test_run_text_scan_check_skips_local_ci_parity_findings(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("Contact person@example.com at C:/Users/SQHJ/Workspace\n", encoding="utf-8")

    context = repo_audit._build_repo_audit_scan_context(tmp_path, suspicious_identifiers=["SQHJ"])

    findings = repo_audit._run_text_scan_check(context)

    assert any(finding.id == "email-address" for finding in findings)
    assert any(finding.id == "suspicious-identifier" for finding in findings)
    assert not any(finding.id == "hardcoded-windows-path" for finding in findings)


def test_repo_audit_read_text_rejects_binary_and_falls_back_to_cp1252(tmp_path):
    binary_file = tmp_path / "sample.bin"
    binary_file.write_bytes(b"abc\x00def")

    with pytest.raises(ValueError, match="binary"):
        repo_audit._read_text(binary_file)

    encoded_file = tmp_path / "cp1252.txt"
    encoded_file.write_bytes('author = "S\xf8ren"\n'.encode("cp1252"))

    assert repo_audit._read_text(encoded_file) == 'author = "S\xf8ren"\n'


def test_list_tracked_repo_paths_returns_none_for_missing_git_and_failures(tmp_path):
    with patch("sattlint.devtools.repo_audit.shutil.which", return_value=None):
        assert repo_audit._list_tracked_repo_paths(tmp_path) is None

    with (
        patch("sattlint.devtools.repo_audit.shutil.which", return_value="git"),
        patch("sattlint.devtools.repo_audit.subprocess.run", side_effect=OSError("git missing")),
    ):
        assert repo_audit._list_tracked_repo_paths(tmp_path) is None

    completed = subprocess.CompletedProcess(args=["git", "ls-files", "-z"], returncode=1, stdout=b"", stderr=b"")
    with (
        patch("sattlint.devtools.repo_audit.shutil.which", return_value="git"),
        patch("sattlint.devtools.repo_audit.subprocess.run", return_value=completed),
    ):
        assert repo_audit._list_tracked_repo_paths(tmp_path) is None


def test_iter_repo_file_candidates_filters_generated_suffixes_and_large_files(tmp_path):
    readme = tmp_path / "README"
    readme.write_text("docs\n", encoding="utf-8")
    source_file = tmp_path / "src" / "sample.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("print('ok')\n", encoding="utf-8")
    generated_file = tmp_path / "artifacts" / "audit" / "report.json"
    generated_file.parent.mkdir(parents=True)
    generated_file.write_text("{}\n", encoding="utf-8")
    binary_suffix = tmp_path / "src" / "sample.bin"
    binary_suffix.write_bytes(b"bin")
    oversized = tmp_path / "src" / "huge.txt"
    oversized.write_bytes(b"a" * 2_000_001)

    files = {
        path.relative_to(tmp_path).as_posix()
        for path in repo_audit._iter_repo_file_candidates(tmp_path, include_generated=False)
    }
    generated_files = {
        path.relative_to(tmp_path).as_posix()
        for path in repo_audit._iter_repo_file_candidates(tmp_path, include_generated=True)
    }

    assert files == {"README", "src/sample.py"}
    assert generated_files == {"README", "artifacts/audit/report.json", "src/sample.py"}


def test_iter_tracked_repo_file_candidates_skips_missing_dirs_and_large_files(tmp_path):
    source_file = tmp_path / "src" / "sample.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("print('ok')\n", encoding="utf-8")
    readme = tmp_path / "README"
    readme.write_text("docs\n", encoding="utf-8")
    generated_file = tmp_path / "artifacts" / "audit" / "report.json"
    generated_file.parent.mkdir(parents=True)
    generated_file.write_text("{}\n", encoding="utf-8")
    venv_file = tmp_path / ".venv-local" / "Lib" / "site-packages" / "skip.py"
    venv_file.parent.mkdir(parents=True)
    venv_file.write_text("print('skip')\n", encoding="utf-8")
    huge = tmp_path / "src" / "huge.txt"
    huge.write_bytes(b"a" * 2_000_001)
    directory = tmp_path / "docs"
    directory.mkdir()

    tracked_paths = (
        "src/sample.py",
        "README",
        "artifacts/audit/report.json",
        ".venv-local/Lib/site-packages/skip.py",
        "src/huge.txt",
        "docs",
        "missing.py",
    )

    with patch.object(repo_audit, "_list_tracked_repo_paths", return_value=tracked_paths):
        files = {
            path.relative_to(tmp_path).as_posix()
            for path in repo_audit._iter_tracked_repo_file_candidates(tmp_path, include_generated=False)
        }

    with patch.object(repo_audit, "_list_tracked_repo_paths", return_value=tracked_paths):
        generated_files = {
            path.relative_to(tmp_path).as_posix()
            for path in repo_audit._iter_tracked_repo_file_candidates(tmp_path, include_generated=True)
        }

    assert files == {"README", "src/sample.py"}
    assert generated_files == {"README", "artifacts/audit/report.json", "src/sample.py"}


def test_iter_repo_text_entries_yields_text_and_skips_binary(tmp_path):
    text_file = tmp_path / "src" / "sample.py"
    text_file.parent.mkdir(parents=True)
    text_file.write_text("VALUE = 1\n", encoding="utf-8")
    binary_file = tmp_path / "src" / "sample.txt"
    binary_file.write_bytes(b"bad\x00text")

    entries = list(repo_audit._iter_repo_text_entries(tmp_path, include_generated=False, tracked_only=False))

    assert len(entries) == 1
    assert entries[0][0] == text_file
    assert entries[0][1].splitlines() == ["VALUE = 1"]


def test_repo_audit_redaction_and_severity_helpers_cover_default_paths():
    assert repo_audit._redact_value("secret") == "<redacted>"
    assert repo_audit._redact_value("supersecret") == "su...et"
    assert repo_audit._redact_email("person@example.com") == "p***@example.com"
    assert repo_audit._redact_email("@example.com") == "<redacted-email>"
    assert repo_audit._severity_for_path("tests/test_app.py", "high") == "medium"
    assert repo_audit._severity_for_path("Libs/HA/example.x", "high") == "medium"
    assert repo_audit._severity_for_path("README.md", "high") == "high"


def test_parse_coverage_findings_handles_missing_file_and_parse_error(tmp_path):
    from xml.etree.ElementTree import ParseError

    assert repo_audit._parse_coverage_findings(tmp_path) == []

    coverage_path = tmp_path / "coverage.xml"
    coverage_path.write_text("<coverage>", encoding="utf-8")

    with pytest.raises(ParseError, match="no element found"):
        repo_audit._parse_coverage_findings(tmp_path)


def test_load_pyproject_accepts_cp1252_toml(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes('[project]\nname = "demo"\nauthors = [{ name = "S\u00f8ren" }]\n'.encode("cp1252"))

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

    # Should not flag simple returns without error handling
    assert all(f.id != "missing-logging" for f in findings)
    # The function has `return` but no `except`, so failure-path check should not trigger
    # (it requires "except" in text)
    assert all(f.id != "failure-path-no-diagnostic" for f in findings)


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


def test_find_ignored_repo_path_references_flags_repo_local_gitignored_library_dependency(tmp_path):
    sample = tmp_path / "tests" / "test_sample.py"
    sample.parent.mkdir(parents=True)
    sample.write_text(
        'def test_library_fixture():\n    return _repo_path("Libs", "HA", "ABBLib", "SupportLib.x")\n',
        encoding="utf-8",
    )

    context = repo_audit._build_python_source_scan_context(
        tmp_path / "tests",
        root=tmp_path,
        tracked_paths=("tests/test_sample.py",),
    )

    findings = repo_audit._find_ignored_repo_path_references(
        context,
        root=tmp_path,
        tracked_paths=("tests/test_sample.py",),
    )

    assert len(findings) == 1
    assert findings[0].id == "gitignored-repo-path-reference"
    assert findings[0].path == "tests/test_sample.py"
    assert findings[0].line == 2
    assert findings[0].detail == "Matched ignored path Libs/HA/ABBLib/SupportLib.x"


def test_find_ignored_repo_path_references_skips_tracked_fixture_and_allowlisted_generated_output_tests(tmp_path):
    tracked_fixture = tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "official_library_files" / "Demo.x"
    tracked_fixture.parent.mkdir(parents=True, exist_ok=True)
    tracked_fixture.write_text("fixture\n", encoding="utf-8")
    sample = tmp_path / "tests" / "test_sample.py"
    sample.write_text(
        "def test_library_fixture():\n"
        '    return _repo_path("tests", "fixtures", "sample_sattline_files", "official_library_files", "Demo.x")\n',
        encoding="utf-8",
    )
    allowlisted = tmp_path / "tests" / "test_pipeline_run.py"
    allowlisted.write_text(
        'def test_generated_output_contract():\n    return "artifacts/analysis"\n',
        encoding="utf-8",
    )

    tracked_paths = (
        "tests/test_sample.py",
        "tests/test_pipeline_run.py",
        "tests/fixtures/sample_sattline_files/official_library_files/Demo.x",
    )

    context = repo_audit._build_python_source_scan_context(
        tmp_path / "tests",
        root=tmp_path,
        tracked_paths=tracked_paths,
    )

    findings = repo_audit._find_ignored_repo_path_references(
        context,
        root=tmp_path,
        tracked_paths=tracked_paths,
    )

    assert findings == []


def test_find_ignored_repo_path_references_skips_allowlisted_policy_and_helper_files(tmp_path):
    scripts_dir = tmp_path / "scripts"
    tests_dir = tmp_path / "tests"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    (scripts_dir / "check_ratchet_policy.py").write_text(
        'STRUCTURAL = "artifacts/analysis/structural_budget_ratchet.json"\n'
        'COVERAGE = "artifacts/analysis/coverage_ratchet.json"\n'
        'XML = "coverage.xml"\n',
        encoding="utf-8",
    )
    (scripts_dir / "repo_health.py").write_text(
        'DEFAULT_AUDIT_DIR = REPO_ROOT / "artifacts" / "audit"\n'
        'DEFAULT_COVERAGE_RATCHET = REPO_ROOT / "artifacts" / "analysis" / "coverage_ratchet.json"\n'
        'DEFAULT_STRUCTURAL_RATCHET = REPO_ROOT / "artifacts" / "analysis" / "structural_budget_ratchet.json"\n',
        encoding="utf-8",
    )
    (tests_dir / "test_ratchet_policy.py").write_text(
        'def test_coverage_fixture_name():\n    return "coverage.xml"\n',
        encoding="utf-8",
    )
    (tests_dir / "test_context_health.py").write_text(
        'def test_context_health_uses_audit_artifacts():\n    return "artifacts/analysis/coverage_ratchet.json"\n',
        encoding="utf-8",
    )
    (tests_dir / "test_recommendation_routing.py").write_text(
        "def test_structural_report_route_case():\n"
        '    return "artifacts/analysis/structural_budget_ratchet.json", "coverage.xml"\n',
        encoding="utf-8",
    )
    (tests_dir / "test_repo_health.py").write_text(
        'def test_repo_health_defaults():\n    return "artifacts/audit", "artifacts/analysis/coverage_ratchet.json"\n',
        encoding="utf-8",
    )
    (tests_dir / "test_run_markdownlint.py").write_text(
        'def test_markdownlint_wrapper_fixture_name():\n    return "coverage.xml"\n',
        encoding="utf-8",
    )
    (tests_dir / "test_repo_audit_entrypoints_helpers.py").write_text(
        'def test_finish_gate_report_paths():\n    return "artifacts/audit", "artifacts/audit/finish_gate.json"\n',
        encoding="utf-8",
    )

    tracked_paths = (
        "scripts/check_ratchet_policy.py",
        "scripts/repo_health.py",
        "tests/test_context_health.py",
        "tests/test_ratchet_policy.py",
        "tests/test_repo_health.py",
        "tests/test_recommendation_routing.py",
        "tests/test_repo_audit_entrypoints_helpers.py",
        "tests/test_run_markdownlint.py",
    )

    script_context = repo_audit._build_python_source_scan_context(
        scripts_dir,
        root=tmp_path,
        tracked_paths=tracked_paths,
    )
    test_context = repo_audit._build_python_source_scan_context(
        tests_dir,
        root=tmp_path,
        tracked_paths=tracked_paths,
    )

    findings = repo_audit._find_ignored_repo_path_references(
        script_context,
        root=tmp_path,
        tracked_paths=tracked_paths,
    )
    findings.extend(
        repo_audit._find_ignored_repo_path_references(
            test_context,
            root=tmp_path,
            tracked_paths=tracked_paths,
        )
    )

    assert findings == []


def test_find_hidden_local_dependency_findings_flags_site_packages_path_injection(tmp_path):
    sample = tmp_path / "tests" / "test_sample.py"
    sample.parent.mkdir(parents=True)
    sample.write_text(
        'import sys\n\ndef test_bootstrap():\n    sys.path.insert(0, ".venv/Lib/site-packages")\n',
        encoding="utf-8",
    )

    context = repo_audit._build_python_source_scan_context(
        tmp_path / "tests",
        root=tmp_path,
        tracked_paths=("tests/test_sample.py",),
    )

    findings = repo_audit._find_hidden_local_dependency_findings(context, root=tmp_path)

    assert len(findings) == 1
    assert findings[0].id == "hidden-local-dependency-root"
    assert findings[0].path == "tests/test_sample.py"
    assert findings[0].line == 4
    assert findings[0].detail == "Matched local dependency marker .venv/"


def test_find_host_specific_test_assumptions_flags_skipif_and_os_branch(tmp_path):
    sample = tmp_path / "tests" / "test_sample.py"
    sample.parent.mkdir(parents=True)
    sample.write_text(
        "import os\nimport pytest\n\n"
        '@pytest.mark.skipif(os.name != "nt", reason="Windows-specific")\n'
        "def test_windows_only():\n    assert True\n\n"
        "def test_branching_expectation():\n"
        '    separator = "\\\\" if os.name == "nt" else "/"\n'
        '    assert separator in {"/", "\\\\"}\n',
        encoding="utf-8",
    )

    context = repo_audit._build_python_source_scan_context(
        tmp_path / "tests",
        root=tmp_path,
        tracked_paths=("tests/test_sample.py",),
    )

    findings = repo_audit._find_host_specific_test_assumptions(context, root=tmp_path)

    assert [finding.id for finding in findings] == [
        "host-specific-test-assumption",
        "host-specific-test-assumption",
    ]
    assert [finding.line for finding in findings] == [4, 9]
    assert "skipif" in (findings[0].detail or "")
    assert 'os.name == "nt"' in (findings[1].detail or "")


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


def test_find_public_readiness_findings_flags_unexpected_tracked_root_entries(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
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
            ".github/workflows/ci.yml",
            "scripts/run_markdownlint.py",
            "_coverage_check.py",
            "_fix_cli.py",
        ),
    )

    root_hygiene_finding = next(finding for finding in findings if finding.id == "unexpected-tracked-root-entry")
    assert root_hygiene_finding.category == "public-readiness"
    assert root_hygiene_finding.severity == "medium"
    assert root_hygiene_finding.detail == "_coverage_check.py, _fix_cli.py"


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


def test_doc_gardener_read_text_falls_back_to_cp1252(tmp_path):
    sample = tmp_path / "notes.md"
    sample.write_bytes("Author: S\xf8ren\n".encode("cp1252"))

    assert doc_gardener._read_text(sample) == "Author: S\xf8ren\n"


def test_doc_gardener_iter_markdown_files_skips_venv_and_non_markdown(tmp_path):
    markdown = tmp_path / "docs" / "guide.md"
    markdown.parent.mkdir(parents=True)
    markdown.write_text("guide\n", encoding="utf-8")
    text_file = tmp_path / "notes.txt"
    text_file.write_text("notes\n", encoding="utf-8")
    python_file = tmp_path / "script.py"
    python_file.write_text("print('nope')\n", encoding="utf-8")
    skipped = tmp_path / ".venv-docs" / "skip.md"
    skipped.parent.mkdir(parents=True)
    skipped.write_text("skip\n", encoding="utf-8")

    with patch.object(doc_gardener, "REPO_ROOT", tmp_path):
        files = {path.relative_to(tmp_path).as_posix() for path in doc_gardener._iter_markdown_files()}

    assert files == {"docs/guide.md", "notes.txt"}


def test_doc_gardener_parse_markdown_table_handles_invalid_rows_and_section_breaks():
    rows = doc_gardener._parse_markdown_table(
        [
            "ignored intro",
            "## Target Section",
            "",
            "| Col A | Col B |",
            "|---|---|",
            "| keep | row |",
            "| too | many | cells |",
            "not a table row",
            "| skipped | after break |",
        ],
        "## Target Section",
    )

    assert rows == [(6, {"Col A": "keep", "Col B": "row"})]


def test_doc_gardener_scan_agents_md_reports_missing_and_structure_findings(tmp_path):
    with _patch_doc_gardener_paths(tmp_path):
        missing_findings = doc_gardener.scan_agents_md()

    assert missing_findings == [doc_gardener.DocFinding("AGENTS.md", 0, "Critical", "missing", "AGENTS.md not found")]

    agents = tmp_path / "AGENTS.md"
    agents.write_text("line\n" * 101, encoding="utf-8")

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_agents_md()

    assert any(finding.category == "too_long" for finding in findings)
    assert {finding.message for finding in findings if finding.category == "structure"} == {
        "Missing section: Quick Reference",
        "Missing section: Repo Map",
        "Missing section: Key Docs",
        "Missing section: Critical Invariants",
    }


def test_doc_gardener_scan_dead_links_and_structure_findings(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    valid_target = docs_dir / "existing.md"
    valid_target.write_text("exists\n", encoding="utf-8")
    readme = docs_dir / "index.md"
    readme.write_text(
        "[good](existing.md)\n[bad](missing.md)\n[ext](https://example.com)\n[anchor](#here)\n[mail](mailto:test@example.com)\n",
        encoding="utf-8",
    )

    with _patch_doc_gardener_paths(tmp_path):
        dead_link_findings = doc_gardener.scan_dead_links()
        structure_findings = doc_gardener.scan_docs_structure()

    assert dead_link_findings == [
        doc_gardener.DocFinding("docs/index.md", 2, "Medium", "dead_link", "Broken link: missing.md")
    ]
    assert any(finding.message == "Missing directory: docs/design-docs" for finding in structure_findings)
    assert any(finding.message == "Missing file: docs/design-docs/core-beliefs.md" for finding in structure_findings)


def test_doc_gardener_scan_completed_exec_plans_still_active(tmp_path):
    active_dir = tmp_path / "docs" / "exec-plans" / "active"
    active_dir.mkdir(parents=True)
    (active_dir / "done.md").write_text(
        "\n".join(
            [
                "# Done",
                "",
                "## Progress",
                "",
                "- [x] one",
                "- [x] two",
            ]
        ),
        encoding="utf-8",
    )
    (active_dir / "active.md").write_text(
        "\n".join(
            [
                "# Active",
                "",
                "## Progress",
                "",
                "- [x] one",
                "- [ ] two",
            ]
        ),
        encoding="utf-8",
    )

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_completed_exec_plans_still_active()

    assert findings == [
        doc_gardener.DocFinding(
            "docs/exec-plans/active/done.md",
            1,
            "High",
            "stale",
            "ExecPlan Progress is fully complete but the file still lives under docs/exec-plans/active/. Move it to docs/exec-plans/completed/.",
        )
    ]


def test_doc_gardener_scan_ai_first_source_drift_reports_missing_ledger_section(tmp_path):
    tech_debt = tmp_path / "docs" / "exec-plans" / "tech-debt-tracker.md"
    tech_debt.parent.mkdir(parents=True)
    tech_debt.write_text("# Tracker\n", encoding="utf-8")

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_ai_first_source_drift()

    assert findings == [
        doc_gardener.DocFinding(
            "docs/exec-plans/tech-debt-tracker.md",
            1,
            "High",
            "structure",
            "Missing consolidation source ledger in the canonical tech debt tracker.",
        )
    ]


def test_doc_gardener_scan_ai_first_source_drift_reports_row_and_digest_issues(tmp_path):
    tech_debt = tmp_path / "docs" / "exec-plans" / "tech-debt-tracker.md"
    tech_debt.parent.mkdir(parents=True)
    (tmp_path / "TODO_GUI.md").write_text("gui drift\n", encoding="utf-8")
    (tmp_path / "TODO_REFACTOR.md").write_text("retired but present\n", encoding="utf-8")

    tech_debt.write_text(
        "\n".join(
            [
                "## Consolidation Source Ledger",
                "| Source | State | Sync Basis |",
                "| --- | --- | --- |",
                "| TODO_GUI.md | active | sha1:deadbeefdead |",
                "| TODO_REFACTOR.md | retired | sha1:ignored |",
                "| TODO_TOOLS.md | active | manual-sync |",
            ]
        ),
        encoding="utf-8",
    )

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_ai_first_source_drift()

    messages = {finding.message for finding in findings}
    assert any(
        message.startswith("TODO_GUI.md drifted from the source-ledger sync basis (sha1:deadbeefdead != sha1:")
        for message in messages
    )
    assert "TODO_REFACTOR.md exists but the source ledger marks it retired." in messages
    assert "Canonical tech debt tracker is missing a source-ledger row for TODO_SATTLINT.md." in messages
    assert "TODO_TOOLS.md is marked active in the source ledger but the file is missing." in messages


def test_doc_gardener_scan_ai_first_status_drift_reports_mismatch(tmp_path):
    coordination_dir = tmp_path / ".github" / "coordination"
    coordination_dir.mkdir(parents=True)
    (coordination_dir / "current_work_lock.json").write_text(
        json.dumps(
            {
                "workstreams": [
                    {
                        "workstream_id": "W1-something",
                        "owner": "Copilot",
                        "status": "active",
                        "claimed_paths": ["src/demo.py"],
                        "updated_at": "2026-05-04T00:00:00Z",
                        "first_validation": "pytest tests/test_repo_audit.py -x -q --tb=short",
                    },
                    {
                        "workstream_id": "W2",
                        "owner": "Copilot",
                        "status": "blocked",
                        "claimed_paths": ["src/other.py"],
                        "updated_at": "2026-05-04T00:00:00Z",
                        "first_validation": "pytest tests/test_repo_audit.py -x -q --tb=short",
                    },
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    tech_debt = tmp_path / "docs" / "exec-plans" / "tech-debt-tracker.md"
    tech_debt.parent.mkdir(parents=True)
    tech_debt.write_text(
        "\n".join(
            [
                "## Program B: Refactor And Architecture Debt",
                "| Debt ID | Status |",
                "| --- | --- |",
                "| W1 | Done |",
                "| W2 | blocked |",
            ]
        ),
        encoding="utf-8",
    )

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_ai_first_status_drift()

    assert findings == [
        doc_gardener.DocFinding(
            "docs/exec-plans/tech-debt-tracker.md",
            4,
            "Medium",
            "stale_status",
            "W1 status is 'Done' but the active coordination lock state tracks 'In progress'.",
        )
    ]


def test_doc_gardener_scan_ai_first_status_drift_falls_back_to_template_when_local_ledger_missing(tmp_path):
    template = tmp_path / ".github" / "coordination" / "current-work.template.md"
    template.parent.mkdir(parents=True)
    template.write_text(
        "\n".join(
            [
                "### Workstream W1-something",
                "- Status: active",
                "- Claims: `src/demo.py`",
            ]
        ),
        encoding="utf-8",
    )
    tech_debt = tmp_path / "docs" / "exec-plans" / "tech-debt-tracker.md"
    tech_debt.parent.mkdir(parents=True)
    tech_debt.write_text(
        "\n".join(
            [
                "## Program B: Refactor And Architecture Debt",
                "| Debt ID | Status |",
                "| --- | --- |",
                "| W1 | Done |",
            ]
        ),
        encoding="utf-8",
    )

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_ai_first_status_drift()

    assert findings == []


def test_doc_gardener_run_scan_aggregates_findings(monkeypatch):
    monkeypatch.setattr(
        doc_gardener,
        "scan_agents_md",
        lambda: [doc_gardener.DocFinding("AGENTS.md", 1, "High", "missing", "missing")],
    )
    monkeypatch.setattr(
        doc_gardener,
        "scan_dead_links",
        lambda: [doc_gardener.DocFinding("docs/index.md", 2, "Medium", "dead_link", "dead")],
    )
    monkeypatch.setattr(doc_gardener, "scan_docs_structure", lambda: [])
    monkeypatch.setattr(doc_gardener, "scan_markdown_encoding_artifacts", lambda: [])
    monkeypatch.setattr(doc_gardener, "scan_ai_first_source_drift", lambda: [])
    monkeypatch.setattr(doc_gardener, "scan_ai_first_status_drift", lambda: [])
    monkeypatch.setattr(doc_gardener, "scan_completed_exec_plans_still_active", lambda: [])
    monkeypatch.setattr(doc_gardener, "scan_stale_docs", lambda: [])

    result = doc_gardener.run_scan()

    assert result["total_findings"] == 2
    assert result["by_severity"]["High"] == 1
    assert result["by_severity"]["Medium"] == 1
    assert result["by_category"]["missing"] == 1
    assert result["by_category"]["dead_link"] == 1
    assert len(result["findings"]) == 2


def test_run_harness_freshness_check_translates_ai_and_doc_findings(monkeypatch, tmp_path):
    monkeypatch.setattr(
        repo_audit._ai_work_map_module,
        "verify_ai_harness_freshness",
        lambda **kwargs: {
            "issues": [
                {
                    "issue_id": "generated-ai-work-map-drift",
                    "severity": "high",
                    "message": "ai map drift",
                    "path": ".github/skills/validation-routing/references/ai-work-map.json",
                }
            ]
        },
    )
    monkeypatch.setattr(repo_audit, "_patch_doc_gardener_paths", lambda root: nullcontext())
    monkeypatch.setattr(
        repo_audit._doc_gardener_module,
        "scan_agents_md",
        lambda: [doc_gardener.DocFinding("AGENTS.md", 101, "High", "too_long", "AGENTS too long")],
    )
    monkeypatch.setattr(
        repo_audit._doc_gardener_module,
        "scan_dead_links",
        lambda: [doc_gardener.DocFinding("docs/index.md", 4, "Medium", "dead_link", "Broken link")],
    )
    monkeypatch.setattr(
        repo_audit._doc_gardener_module,
        "scan_completed_exec_plans_still_active",
        lambda: [
            doc_gardener.DocFinding(
                "docs/exec-plans/active/done.md",
                1,
                "High",
                "stale",
                "completed plan still active",
            )
        ],
    )
    monkeypatch.setattr(repo_audit._doc_gardener_module, "scan_stale_docs", lambda: [])

    findings = repo_audit._run_harness_freshness_check(cast(Any, SimpleNamespace(root=tmp_path)))

    assert {(finding.id, finding.path) for finding in findings} == {
        (
            "harness-generated-ai-work-map-drift",
            ".github/skills/validation-routing/references/ai-work-map.json",
        ),
        ("harness-too-long", "AGENTS.md"),
        ("harness-dead-link", "docs/index.md"),
        ("harness-stale", "docs/exec-plans/active/done.md"),
    }
    assert {finding.category for finding in findings} == {"harness-freshness"}


def test_doc_gardener_updates_quality_score_and_scan_log(tmp_path):
    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 4, 30, 12, 0, tzinfo=UTC)

    quality_score = tmp_path / "docs" / "quality-score.md"
    quality_score.parent.mkdir(parents=True)
    quality_score.write_text(
        "## Trend\n| Date | Grade | Notes | Source |\n|---|---|---|---|\n",
        encoding="utf-8",
    )
    tech_debt = tmp_path / "docs" / "exec-plans" / "tech-debt-tracker.md"
    tech_debt.parent.mkdir(parents=True, exist_ok=True)
    tech_debt.write_text(
        "## Scan Log\n| Date | Summary | Notes | Source |\n|---|---|---|---|\n",
        encoding="utf-8",
    )
    findings = [doc_gardener.DocFinding("docs/index.md", 2, "Medium", "dead_link", "Broken link")]

    with _patch_doc_gardener_paths(tmp_path), patch.object(doc_gardener, "datetime", _FixedDateTime):
        doc_gardener.update_quality_score(findings)
        doc_gardener.update_tech_debt_scan_log(findings)

    assert "| 2026-04-30 | B | 1 findings | Scan |" in quality_score.read_text(encoding="utf-8")
    assert "| 2026-04-30 | 1 findings | Doc-gardening scan |" in tech_debt.read_text(encoding="utf-8")


def test_doc_gardener_main_updates_logs_without_exit_when_clean(monkeypatch, capsys):
    monkeypatch.setattr(
        doc_gardener,
        "run_scan",
        lambda: {
            "total_findings": 0,
            "by_severity": dict.fromkeys(doc_gardener.SEVERITY_ORDER, 0),
            "by_category": dict.fromkeys(doc_gardener.CATEGORY_ORDER, 0),
            "findings": [],
        },
    )
    monkeypatch.setattr(doc_gardener, "update_quality_score", lambda findings: None)
    monkeypatch.setattr(doc_gardener, "update_tech_debt_scan_log", lambda findings: None)
    monkeypatch.setattr(doc_gardener, "open_fixup_pr", lambda findings: pytest.fail("PR should not open when clean"))

    assert doc_gardener.main() == 0

    out = capsys.readouterr().out
    assert "Doc-gardening scan complete: 0 findings" in out
    assert "Tracking files updated." in out


def test_doc_gardener_main_reports_findings_without_opening_pr_by_default(monkeypatch, capsys):
    finding = doc_gardener.DocFinding("docs/index.md", 2, "Medium", "dead_link", "Broken link")
    monkeypatch.setattr(
        doc_gardener,
        "run_scan",
        lambda: {
            "total_findings": 1,
            "by_severity": {severity: (1 if severity == "Medium" else 0) for severity in doc_gardener.SEVERITY_ORDER},
            "by_category": {
                category: (1 if category == "dead_link" else 0) for category in doc_gardener.CATEGORY_ORDER
            },
            "findings": [finding._asdict()],
        },
    )
    monkeypatch.setattr(doc_gardener, "update_quality_score", lambda findings: None)
    monkeypatch.setattr(doc_gardener, "update_tech_debt_scan_log", lambda findings: None)
    monkeypatch.setattr(doc_gardener, "open_fixup_pr", lambda findings: pytest.fail("PR should be opt-in"))

    assert doc_gardener.main() == 1

    out = capsys.readouterr().out
    assert "[Medium] docs/index.md:2 - Broken link" in out
    assert "Tracking files updated." in out
    assert "Attempting to open fix-up PR..." not in out


def test_doc_gardener_main_check_only_does_not_update_logs_or_open_pr(monkeypatch, capsys):
    finding = doc_gardener.DocFinding("docs/index.md", 2, "Medium", "dead_link", "Broken link")
    monkeypatch.setattr(
        doc_gardener,
        "run_scan",
        lambda: {
            "total_findings": 1,
            "by_severity": {severity: (1 if severity == "Medium" else 0) for severity in doc_gardener.SEVERITY_ORDER},
            "by_category": {
                category: (1 if category == "dead_link" else 0) for category in doc_gardener.CATEGORY_ORDER
            },
            "findings": [finding._asdict()],
        },
    )
    monkeypatch.setattr(
        doc_gardener,
        "update_quality_score",
        lambda findings: pytest.fail("check-only mode should not update quality score"),
    )
    monkeypatch.setattr(
        doc_gardener,
        "update_tech_debt_scan_log",
        lambda findings: pytest.fail("check-only mode should not update scan log"),
    )
    monkeypatch.setattr(
        doc_gardener, "open_fixup_pr", lambda findings: pytest.fail("check-only mode should not open PR")
    )

    assert doc_gardener.main(["--check-only"]) == 1

    out = capsys.readouterr().out
    assert "Check-only mode: tracking files not updated." in out
    assert "Attempting to open fix-up PR..." not in out


def test_doc_gardener_main_opens_pr_when_requested(monkeypatch, capsys):
    finding = doc_gardener.DocFinding("docs/index.md", 2, "Medium", "dead_link", "Broken link")
    monkeypatch.setattr(
        doc_gardener,
        "run_scan",
        lambda: {
            "total_findings": 1,
            "by_severity": {severity: (1 if severity == "Medium" else 0) for severity in doc_gardener.SEVERITY_ORDER},
            "by_category": {
                category: (1 if category == "dead_link" else 0) for category in doc_gardener.CATEGORY_ORDER
            },
            "findings": [finding._asdict()],
        },
    )
    monkeypatch.setattr(doc_gardener, "update_quality_score", lambda findings: None)
    monkeypatch.setattr(doc_gardener, "update_tech_debt_scan_log", lambda findings: None)
    opened: list[tuple[doc_gardener.DocFinding, ...]] = []
    monkeypatch.setattr(doc_gardener, "open_fixup_pr", lambda findings: opened.append(tuple(findings)) or True)

    assert doc_gardener.main(["--open-fixup-pr"]) == 1

    out = capsys.readouterr().out
    assert "Attempting to open fix-up PR..." in out
    assert opened == [(finding,)]


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
    coordination_dir = tmp_path / ".github" / "coordination"
    coordination_dir.mkdir(parents=True)
    (coordination_dir / "current_work_lock.json").write_text(
        json.dumps(
            {
                "workstreams": [
                    {
                        "workstream_id": "w6-parser-transformer-split-068",
                        "owner": "Copilot",
                        "status": "active",
                        "claimed_paths": ["src/sattlint/core/parser.py"],
                        "updated_at": "2026-05-04T00:00:00Z",
                        "first_validation": "pytest tests/test_repo_audit.py -x -q --tb=short",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
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
                "message": "Possible mojibake tokens in markdown content: �",
            }
        ],
    }

    with (
        patch.object(doc_gardener, "run_scan", return_value=result),
        patch.object(doc_gardener, "update_quality_score"),
        patch.object(doc_gardener, "update_tech_debt_scan_log"),
        patch.object(doc_gardener, "open_fixup_pr", return_value=False),
    ):
        assert doc_gardener.main() == 1


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
        patch.object(repo_audit, "_find_pipeline_findings", return_value=[]),
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

    monkeypatch.setattr(repo_audit, "_build_repo_audit_scan_context", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        repo_audit,
        "_repo_audit_finding_check_definitions",
        lambda: (
            {"id": "text-scan", "runner": lambda context: calls.append("text-scan") or []},
            {"id": "public-readiness", "runner": lambda context: calls.append("public-readiness") or []},
        ),
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
            "generated_by": "sattlint.devtools.repo_audit",
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

    assert report["generated_by"] == "sattlint.devtools.ai_gc"
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
            "generated_by": "sattlint.devtools.repo_audit",
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
    assert ai_gc_entry["ai_instruction_files"] == [
        ".github/instructions/agent-customizations.instructions.md",
        ".github/instructions/repo-audit.instructions.md",
    ]

    harness_entry = next(entry for entry in catalog["checks"] if entry["id"] == "harness-freshness")
    assert "--check harness-freshness" in harness_entry["command"]
    assert harness_entry["owner_surface"] == "harness-freshness"
    assert harness_entry["ai_summary"]

    local_ci_entry = next(entry for entry in catalog["checks"] if entry["id"] == "local-ci-parity")
    assert "--check local-ci-parity" in local_ci_entry["command"]
    assert local_ci_entry["owner_surface"] == "local-ci-parity"


def test_build_repo_audit_check_recommendations_combines_pipeline_and_repo_audit_routes(tmp_path):
    recommendations = repo_audit.build_repo_audit_check_recommendations(
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


def test_build_repo_audit_check_recommendations_routes_harness_freshness(tmp_path):
    recommendations = repo_audit.build_repo_audit_check_recommendations(
        profile="full",
        output_dir=tmp_path,
        fail_on="high",
        changed_files=["AGENTS.md"],
    )

    assert "harness-freshness" in recommendations["recommended_repo_audit_check_ids"]


def test_main_list_checks_prints_catalog(tmp_path, capsys):
    exit_code = repo_audit.main(["--profile", "full", "--output-dir", str(tmp_path), "--list-checks"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["kind"] == "sattlint.repo_audit.check_catalog"
    assert any(entry["id"] == "cli-consistency" for entry in payload["checks"])


def test_main_recommend_checks_prints_catalog(tmp_path, capsys):
    exit_code = repo_audit.main(
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

    payload = json.loads(capsys.readouterr().out)

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

    with patch.object(
        repo_audit._repo_audit_entrypoints,
        "build_check_my_changes_planning_report",
        return_value=report,
    ) as build_planning_report:
        exit_code = repo_audit.main(
            [
                "--planning-context",
                "--output-dir",
                str(tmp_path),
                "--changed-file",
                "src/sattlint/app.py",
            ]
        )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["kind"] == "sattlint.planning_context"
    assert payload["planning_context"]["primary_agent"] == "CLI App Menu"
    assert payload["finish_gate"]["command"] == "sattlint-repo-audit --run-recommended-finish-gate"
    assert build_planning_report.call_args.kwargs["changed_files"] == ["src/sattlint/app.py"]


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
        patch.object(repo_audit, "run_recommended_repo_audit_slice", return_value=summary) as run_slice,
        patch.object(repo_audit, "_print_cli_summary") as print_cli_summary,
    ):
        exit_code = repo_audit.main(
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
        patch.object(repo_audit, "run_recommended_repo_audit_finish_gate", return_value=summary) as run_finish_gate,
        patch.object(repo_audit, "_print_cli_summary") as print_cli_summary,
    ):
        exit_code = repo_audit.main(
            [
                "--profile",
                "full",
                "--output-dir",
                str(tmp_path),
                "--run-recommended-finish-gate",
                "--changed-file",
                "docs/references/cli-commands.md",
            ]
        )

    assert exit_code == 0
    assert run_finish_gate.call_args.kwargs["changed_files"] == ["docs/references/cli-commands.md"]
    printed = print_cli_summary.call_args.args[0]
    assert printed["overall_status"] == "pass"


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
                "finish_gate": {"status": "pass"},
                "pipeline_summary": {},
            },
        ) as run_pipeline_finish_gate,
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
        )

    assert report["selected_surface"] == "pipeline"
    assert report["overall_status"] == "pass"
    assert "sattlint-analysis-pipeline" in report["selected_command"]
    assert report["reports"]["finish_gate"].endswith("/pipeline/finish_gate.json")
    assert report["reports"]["ai_feedback"].endswith("/ai_feedback.json")
    assert (tmp_path / "check_my_changes.json").exists()
    assert (tmp_path / "ai_feedback.json").exists()
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
        )

    assert report["selected_surface"] == "repo-audit"
    assert report["overall_status"] == "pass"
    assert "sattlint-repo-audit" in report["selected_command"]
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
    assert report["planning_context"]["owner_test_targets"] == ["tests/test_repo_audit.py"]
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
        "recommended_checks": [{"owner_test_targets": ["tests/test_repo_audit.py"]}],
        "proof_requirements": {
            "focused_behavior_test": {
                "required": True,
                "status": "satisfied",
                "owner_test_targets": ["tests/test_repo_audit.py"],
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

    assert [step[0] for step in executed_steps] == [
        "ruff-touched-python",
        "pyright-touched-python",
        "ratchet-policy",
        "owner-pytest-coverage",
    ]
    assert executed_steps[2][1][1:] == ["scripts/check_ratchet_policy.py"]
    assert [step["id"] for step in result["finish_gate"]["commands"]] == [
        "ruff-touched-python",
        "pyright-touched-python",
        "ratchet-policy",
        "owner-pytest-coverage",
    ]
    assert result["finish_gate"]["status"] == "pass"


def test_run_check_my_changes_ai_feedback_prefers_failed_finish_gate_step(monkeypatch, tmp_path):
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
            return_value={
                "overall_status": "fail",
                "finish_gate": {
                    "status": "fail",
                    "commands": [
                        {
                            "id": "ruff",
                            "label": "Ruff on touched files",
                            "command": "ruff check src/sattlint/app.py",
                            "exit_code": 1,
                            "status": "fail",
                        }
                    ],
                },
            },
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

    feedback_payload = json.loads((tmp_path / "ai_feedback.json").read_text(encoding="utf-8"))

    assert report["ai_feedback"]["first_failed_step"]["id"] == "ruff"
    assert feedback_payload["first_failed_step"]["command"] == "ruff check src/sattlint/app.py"
    assert feedback_payload["suggested_next_command"] == "ruff check src/sattlint/app.py"


def test_main_check_my_changes_prints_machine_readable_report(monkeypatch, tmp_path, capsys):
    report = {
        "kind": "sattlint.check_my_changes",
        "schema_version": 1,
        "selected_surface": "pipeline",
        "overall_status": "pass",
    }

    with patch.object(repo_audit, "run_check_my_changes", return_value=report) as run_check_my_changes:
        exit_code = repo_audit.main(["--check-my-changes", "--output-dir", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["kind"] == "sattlint.check_my_changes"
    assert payload["selected_surface"] == "pipeline"
    assert run_check_my_changes.call_args.args[0] == tmp_path


def test_main_apply_ai_gc_calls_apply_helper(monkeypatch, tmp_path, capsys):
    report = {
        "kind": "sattlint.ai_gc",
        "schema_version": 1,
        "status": "pass",
        "summary": {"candidate_count": 1, "applied_count": 1, "failure_count": 0},
        "candidates": [],
        "applied_actions": [{"path": "artifacts/audit-review-old", "action": "delete"}],
        "failures": [],
    }

    with patch.object(repo_audit, "apply_ai_gc", return_value=report) as apply_ai_gc:
        exit_code = repo_audit.main(["--apply-ai-gc", "--output-dir", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["kind"] == "sattlint.ai_gc"
    assert apply_ai_gc.call_args.kwargs["output_dir"] == tmp_path


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


def test_build_cli_consistency_report_ignores_exec_plan_markdown_noise(tmp_path, monkeypatch):
    cli_docs = tmp_path / "docs" / "references"
    cli_docs.mkdir(parents=True)
    (cli_docs / "cli-commands.md").write_text("Run `sattlint syntax-check` to validate syntax.\n", encoding="utf-8")

    exec_plan = tmp_path / "docs" / "exec-plans" / "active"
    exec_plan.mkdir(parents=True)
    (exec_plan / "plan.md").write_text(
        "Do not suppress the `sattlint-syntax-check` hook.\n"
        '    rg -n "sattlint|sattlint-repo-audit|sattlint-corpus-runner|sattlint-lsp" README.md docs\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        repo_audit,
        "_collect_cli_metadata",
        lambda: ({"sattlint", "sattlint-repo-audit"}, {"syntax-check"}),
    )

    report = repo_audit.build_cli_consistency_report(root=tmp_path)

    assert report["status"] == "pass"
    assert report["gaps"]["undeclared_scripts"] == []
    assert report["gaps"]["undeclared_subcommands"] == []


def test_cli_consistency_findings_preserve_report_script_and_path_fields():
    report = {
        "gaps": {
            "undeclared_subcommands": [
                {
                    "subcommand": "ghost-command",
                    "referenced_in": "docs/references/cli-commands.md",
                    "line": 12,
                }
            ],
            "undeclared_scripts": [
                {
                    "script": "sattlint-ghost",
                    "referenced_in": "docs/references/cli-commands.md",
                    "line": 24,
                }
            ],
        }
    }

    findings = repo_audit._repo_audit_entrypoints._cli_consistency_findings(report)

    assert [finding.id for finding in findings] == [
        "cli-consistency-undeclared-subcommand",
        "cli-consistency-undeclared-script",
    ]
    assert findings[0].path == "docs/references/cli-commands.md"
    assert findings[0].line == 12
    assert findings[1].path == "docs/references/cli-commands.md"
    assert findings[1].line == 24
    assert findings[1].message == "Documented CLI script 'sattlint-ghost' is not declared."


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


def test_doc_gardener_load_active_workstream_statuses_extracts_status_from_lock_state(tmp_path):
    coordination_dir = tmp_path / ".github" / "coordination"
    coordination_dir.mkdir(parents=True)
    (coordination_dir / "current_work_lock.json").write_text(
        json.dumps(
            {
                "workstreams": [
                    {
                        "workstream_id": "W1-something",
                        "owner": "Copilot",
                        "status": "active",
                        "claimed_paths": ["src/demo.py"],
                        "updated_at": "2026-05-04T00:00:00Z",
                        "first_validation": "pytest tests/test_repo_audit.py -x -q --tb=short",
                    },
                    {
                        "workstream_id": "W2",
                        "owner": "Copilot",
                        "status": "blocked",
                        "claimed_paths": ["src/other.py"],
                        "updated_at": "2026-05-04T00:00:00Z",
                        "first_validation": "pytest tests/test_repo_audit.py -x -q --tb=short",
                    },
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = doc_gardener._load_active_workstream_statuses(tmp_path)

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
