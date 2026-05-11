# ruff: noqa: F403, F405
from ._repo_audit_test_support import *


def test_find_pipeline_findings_prefers_normalized_findings_report(tmp_path):
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
