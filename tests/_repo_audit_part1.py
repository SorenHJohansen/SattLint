# ruff: noqa: F403, F405
from ._repo_audit_test_support import *


def test_iter_tracked_repo_text_files_includes_tracked_generated_files(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "Run `sattlint syntax-check demo.s` and `sattlint-repo-audit --output-dir artifacts/audit`.\n",
        encoding="utf-8",
    )

    commands = repo_audit._extract_documented_commands([readme], root=tmp_path)

    assert repo_audit.DocumentedCommand("sattlint", "syntax-check", "README.md", 1) in commands
    assert repo_audit.DocumentedCommand("sattlint-repo-audit", None, "README.md", 1) in commands


def test_extract_documented_commands_ignores_paths_with_sattlint_prefix_segments(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "Claim files in the shared `.git/sattlint-ai-coordination/current_work_lock.json` lock state.\n",
        encoding="utf-8",
    )

    commands = repo_audit._extract_documented_commands([readme], root=tmp_path)

    assert commands == []


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


def test_line_findings_skip_repo_audit_self_scan_shards_and_scanner_sources(tmp_path):
    shard_file = tmp_path / "tests" / "_repo_audit_part1.py"
    shard_file.parent.mkdir(parents=True)
    scanner_file = tmp_path / "src" / "sattlint" / "devtools" / "leak_detection.py"
    scanner_file.parent.mkdir(parents=True)
    text = 'HOST = "localhost:8080"\nROOT = r"C:/Users/SQHJ/Workspace"\nsecret_token = "super-secret-value"\n'

    shard_findings = repo_audit._line_findings(shard_file, text, {"SQHJ"}, root=tmp_path)
    scanner_findings = repo_audit._line_findings(scanner_file, text, {"SQHJ"}, root=tmp_path)

    assert shard_findings == []
    assert scanner_findings == []


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


def test_repo_audit_ast_path_helpers_cover_branchy_cases():
    assert repo_audit._leading_string_args(
        [
            ast.Constant(value=" docs "),
            ast.Constant(value=""),
            ast.Name(id="dynamic_value", ctx=ast.Load()),
        ]
    ) == ("docs",)

    invalid_attr = ast.parse("factory().value", mode="eval").body
    assert isinstance(invalid_attr, ast.Attribute)
    assert repo_audit._attribute_path(invalid_attr) is None

    assert repo_audit._repo_relative_path_from_expr(ast.parse("REPO_ROOT", mode="eval").body) == ()
    assert repo_audit._repo_relative_path_from_expr(ast.parse("config.REPO_ROOT", mode="eval").body) == ()
    assert repo_audit._repo_relative_path_from_expr(ast.parse('_repo_path("docs", "", "cli")', mode="eval").body) == (
        "docs",
        "cli",
    )
    assert repo_audit._repo_relative_path_from_expr(ast.parse('REPO_ROOT / ""', mode="eval").body) == ()
    assert repo_audit._repo_relative_path_from_expr(ast.parse("REPO_ROOT / dynamic_name", mode="eval").body) is None

    assert repo_audit._normalize_repo_relative_literal(" https://example.com/demo ") is None
    assert repo_audit._normalize_repo_relative_literal("./scratch") is None
    assert repo_audit._normalize_repo_relative_literal("docs/reference/") == "docs/reference"

    assert (
        repo_audit._is_ignored_repo_path_reference(
            "artifacts/audit",
            tracked_paths=("artifacts/audit/status.json",),
        )
        is False
    )
    assert repo_audit._is_ignored_repo_path_reference(".coverage.worker", tracked_paths=None) is True
    assert repo_audit._is_ignored_repo_path_reference("Libs/HA/demo.x", tracked_paths=None) is True


def test_repo_audit_source_signal_helpers_cover_edge_cases():
    assert repo_audit._source_segment_summary("value = 1\n", ast.Pass()) is None

    source_text = "result = helper(alpha, beta, gamma, delta)\n"
    statement = ast.parse(source_text).body[0]
    summary = repo_audit._source_segment_summary(source_text, statement, max_length=18)
    assert summary is not None and summary.endswith("...")

    assert repo_audit._contains_host_signal(ast.parse("platform.system()", mode="eval").body) is True
    assert repo_audit._contains_host_signal(ast.parse("value + 1", mode="eval").body) is False

    assert repo_audit._is_pythonpath_target(ast.parse('os.environ["PYTHONPATH"]', mode="eval").body) is True
    assert repo_audit._is_pythonpath_target(ast.parse('os.environ["HOME"]', mode="eval").body) is False

    assert repo_audit._find_marker_in_segment("prefix/site-packages/demo") == "site-packages"
    assert repo_audit._find_marker_in_segment("plain text only") is None


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
