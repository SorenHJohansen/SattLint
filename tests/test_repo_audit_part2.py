# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
# ruff: noqa: F403, F405
from ._repo_audit_test_support import *


def test_find_hidden_local_dependency_findings_flags_site_packages_path_injection(tmp_path):
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
        patch("sattlint.devtools.audit.repo_audit.shutil.which", return_value="git"),
        patch("sattlint.devtools.audit.repo_audit.subprocess.run", return_value=completed),
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


def test_build_python_source_scan_context_skips_syntax_errors_and_builds_documented_commands(tmp_path):
    source_root = tmp_path / "src"
    source_root.mkdir(parents=True)
    (source_root / "good.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source_root / "broken.py").write_text("if True print('bad')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("Run `sattlint syntax-check demo.s`.\n", encoding="utf-8")

    context = repo_audit._build_python_source_scan_context(source_root, root=tmp_path)
    scan_context = repo_audit._build_repo_audit_scan_context(tmp_path, suspicious_identifiers=["  ", "SQHJ "])

    assert {path.name for path in context.texts} == {"broken.py", "good.py"}
    assert {path.name for path in context.asts} == {"good.py"}
    assert scan_context.suspicious_identifiers == frozenset({"SQHJ"})
    assert repo_audit.DocumentedCommand("sattlint", "syntax-check", "README.md", 1) in scan_context.documented_commands


def test_write_text_artifact_retries_permission_errors_and_raises_when_attempts_are_exhausted(tmp_path, monkeypatch):
    artifact_path = tmp_path / "artifacts" / "status.json"

    monkeypatch.setattr(repo_audit.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        repo_audit.os, "replace", lambda _source, _target: (_ for _ in ()).throw(PermissionError("locked"))
    )

    with pytest.raises(PermissionError, match="locked"):
        repo_audit._write_text_artifact(artifact_path, "payload")

    assert list(artifact_path.parent.glob(f".{artifact_path.name}.*.tmp")) == []

    monkeypatch.setattr(repo_audit, "range", lambda _count: (), raising=False)
    with pytest.raises(RuntimeError, match="Failed to write"):
        repo_audit._write_text_artifact(tmp_path / "no-attempts" / "status.json", "payload")


def test_report_copy_and_history_helpers_cover_edge_cases(tmp_path, monkeypatch):
    source_dir = tmp_path / "reports"
    latest_dir = tmp_path / "latest"
    nested_dir = source_dir / "nested"
    history_dir = source_dir / repo_audit.AUDIT_RUN_HISTORY_DIRNAME
    source_dir.mkdir(parents=True)
    nested_dir.mkdir()
    history_dir.mkdir()
    (nested_dir / "summary.json").write_text("summary", encoding="utf-8")
    (source_dir / repo_audit.AUDIT_RUN_HISTORY_FILENAME).write_text("[]", encoding="utf-8")
    (history_dir / "old.json").write_text("old", encoding="utf-8")

    repo_audit._mirror_latest_reports(source_dir, source_dir)
    repo_audit._mirror_latest_reports(source_dir, latest_dir)
    repo_audit._copy_audit_snapshot(source_dir, tmp_path / "snapshot")

    assert (latest_dir / "nested").is_dir()
    assert (latest_dir / "nested" / "summary.json").read_text(encoding="utf-8") == "summary"
    assert not (tmp_path / "snapshot" / repo_audit.AUDIT_RUN_HISTORY_FILENAME).exists()
    assert not (tmp_path / "snapshot" / repo_audit.AUDIT_RUN_HISTORY_DIRNAME).exists()

    history_path = tmp_path / "history.json"
    history_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(repo_audit, "_read_text", lambda _path: (_ for _ in ()).throw(ValueError("bad history")))
    assert repo_audit._load_audit_run_history(history_path) == []

    monkeypatch.setattr(repo_audit, "_read_text", lambda _path: "[]")
    assert repo_audit._load_audit_run_history(history_path) == []

    monkeypatch.setattr(repo_audit, "_read_text", lambda _path: '{"runs": "invalid"}')
    assert repo_audit._load_audit_run_history(history_path) == []

    monkeypatch.setattr(repo_audit.shutil, "which", lambda _name: None)
    assert repo_audit._collect_audit_git_state(tmp_path) == {"head": None, "dirty": None}

    monkeypatch.setattr(repo_audit.shutil, "which", lambda _name: "git")
    monkeypatch.setattr(
        repo_audit.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("git missing"))
    )
    assert repo_audit._collect_audit_git_state(tmp_path) == {"head": None, "dirty": None}


def test_build_local_import_graph_and_architecture_findings_cover_prefix_and_info_cycles(tmp_path, monkeypatch):
    source_root = tmp_path / "src"
    pkg_dir = source_root / "pkg"
    subpkg_dir = pkg_dir / "subpkg"
    pkg_dir.mkdir(parents=True)
    subpkg_dir.mkdir(parents=True)
    module_a = pkg_dir / "a.py"
    helper = subpkg_dir / "helper.py"

    graph = repo_audit._build_local_import_graph(
        source_root,
        content_by_file={
            module_a: "import pkg\nfrom . import subpkg\nfrom ... import outside\n",
            helper: "VALUE = 1\n",
        },
    )

    assert graph["pkg.a"] == {"pkg"}

    monkeypatch.setattr(repo_audit, "_build_local_import_graph", lambda *_args, **_kwargs: {"placeholder": set()})
    monkeypatch.setattr(
        repo_audit,
        "_find_import_cycles",
        lambda _graph: [
            ["sattline_semantics", "rule_profiles", "sattline_semantics"],
            ["a", "b", "c", "d", "a"],
        ],
    )

    findings = repo_audit._find_architecture_findings(source_root, content_by_file={})

    assert [finding.severity for finding in findings] == ["info", "info"]
    assert findings[0].message == "Known aggregator cycle (rule metadata requires aggregator)."
    assert findings[1].message == "Long import cycle through multiple analyzers."


def test_structural_detail_and_cached_line_findings_cover_delegate_paths(tmp_path):
    detail = repo_audit.structural_report_location_detail(
        {
            "id": "structural-budget-ratchet-regression",
            "regressions": [{"metric": "source_files", "actual": 3, "expected_max": 2}],
        }
    )
    empty_context = repo_audit.PythonSourceScanContext(source_root=tmp_path, texts={}, asts={})
    cached_finding = repo_audit.Finding(
        id="cached-finding",
        category="test-coverage",
        severity="low",
        confidence="high",
        message="cached",
    )
    context = repo_audit.RepoAuditScanContext(
        root=tmp_path,
        include_generated=False,
        tracked_only=False,
        tracked_paths=None,
        suspicious_identifiers=frozenset(),
        source_context=empty_context,
        test_context=empty_context,
        scripts_context=empty_context,
        scripts=frozenset(),
        subcommands=frozenset(),
        documented_commands=(),
        line_findings=(cached_finding,),
    )

    assert detail == (None, "source_files: 3 > 2")
    assert repo_audit._with_shared_text_line_findings(context) is context


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
    (tests_dir / "devtools").mkdir(parents=True, exist_ok=True)
    (tests_dir / "devtools" / "test_run_markdownlint.py").write_text(
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
        "tests/devtools/test_context_health.py",
        "tests/test_ratchet_policy.py",
        "tests/devtools/test_repo_health.py",
        "tests/test_recommendation_routing.py",
        "tests/test_repo_audit_entrypoints_helpers.py",
        "tests/devtools/test_run_markdownlint.py",
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
