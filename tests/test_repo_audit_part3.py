# ruff: noqa: F403, F405
from ._repo_audit_test_support import *


def _write_public_readiness_baseline(tmp_path: Path) -> tuple[str, ...]:
    files = {
        "README.md": "# Demo\n\nSee SUPPORT.md, SECURITY.md, and docs/references/public-support-matrix.md.\n",
        "LICENSE": "MIT\n",
        "CONTRIBUTING.md": "# Contributing\n",
        "SECURITY.md": "# Security\n",
        "CODE_OF_CONDUCT.md": "# Conduct\n",
        "SUPPORT.md": "# Support\n",
        ".gitignore": "dist/\n",
        "pyproject.toml": (
            '[project]\nname = "demo"\nversion = "0.1.0"\n[project.urls]\nRepository = "https://example.invalid/demo"\n'
        ),
        "docs/references/public-support-matrix.md": "# Matrix\n",
    }
    for rel_path, text in files.items():
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tuple(files)


def test_find_pipeline_findings_prefers_normalized_findings_report(tmp_path: Path):
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


def test_find_host_specific_test_assumptions_flags_skipif_and_os_branch(tmp_path: Path):
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


def test_parse_coverage_findings_ignores_untracked_coverage_xml(tmp_path: Path):
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


def test_find_public_readiness_findings_ignores_untracked_workflow(tmp_path: Path):
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


def test_find_public_readiness_findings_flags_unexpected_tracked_root_entries(tmp_path: Path):
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


def test_find_public_readiness_findings_flags_missing_public_support_docs(tmp_path: Path):
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
        ),
    )

    support_finding = next(finding for finding in findings if finding.id == "missing-public-support-file")
    assert support_finding.path == "SECURITY.md"
    assert support_finding.severity == "high"
    assert "CODE_OF_CONDUCT.md" in (support_finding.detail or "")
    assert "docs/references/public-support-matrix.md" in (support_finding.detail or "")


def test_find_public_readiness_findings_flags_missing_readme_public_links(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Demo\n\nInstall from source.\n", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (tmp_path / "CONTRIBUTING.md").write_text("# Contributing\n", encoding="utf-8")
    (tmp_path / "SECURITY.md").write_text("# Security\n", encoding="utf-8")
    (tmp_path / "CODE_OF_CONDUCT.md").write_text("# Conduct\n", encoding="utf-8")
    (tmp_path / "SUPPORT.md").write_text("# Support\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("dist/\n", encoding="utf-8")
    workflow_path = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow_path.parent.mkdir(parents=True)
    workflow_path.write_text("name: CI\n", encoding="utf-8")
    support_matrix = tmp_path / "docs" / "references" / "public-support-matrix.md"
    support_matrix.parent.mkdir(parents=True)
    support_matrix.write_text("# Matrix\n", encoding="utf-8")
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
            "SECURITY.md",
            "CODE_OF_CONDUCT.md",
            "SUPPORT.md",
            ".gitignore",
            "pyproject.toml",
            ".github/workflows/ci.yml",
            "docs/references/public-support-matrix.md",
        ),
    )

    link_finding = next(finding for finding in findings if finding.id == "missing-readme-public-links")
    assert link_finding.path == "README.md"
    assert "SUPPORT.md" in (link_finding.detail or "")
    assert "SECURITY.md" in (link_finding.detail or "")
    assert "docs/references/public-support-matrix.md" in (link_finding.detail or "")


def test_find_public_readiness_findings_flags_publish_workflow_security_gaps(tmp_path: Path):
    tracked_paths = list(_write_public_readiness_baseline(tmp_path))
    publish_workflow = tmp_path / ".github" / "workflows" / "publish.yml"
    publish_workflow.parent.mkdir(parents=True, exist_ok=True)
    publish_workflow.write_text(
        "name: Publish\n\n"
        "on:\n"
        "  workflow_dispatch:\n\n"
        "permissions:\n"
        "  contents: read\n"
        "  id-token: write\n\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "  publish:\n"
        "    needs: build\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: echo publish\n",
        encoding="utf-8",
    )
    tracked_paths.append(".github/workflows/publish.yml")

    findings = repo_audit._find_public_readiness_findings(tmp_path, tracked_paths=tuple(tracked_paths))

    findings_by_id = {finding.id: finding for finding in findings}
    assert findings_by_id["workflow-level-id-token-write"].path == ".github/workflows/publish.yml"
    assert findings_by_id["publish-workflow-missing-environment"].path == ".github/workflows/publish.yml"
    assert findings_by_id["publish-workflow-missing-tag-guard"].path == ".github/workflows/publish.yml"


def test_find_public_readiness_findings_flags_missing_npm_dependabot_monitoring(tmp_path: Path):
    tracked_paths = list(_write_public_readiness_baseline(tmp_path))
    workflow_path = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text("name: CI\n", encoding="utf-8")
    dependabot_path = tmp_path / ".github" / "dependabot.yml"
    dependabot_path.parent.mkdir(parents=True, exist_ok=True)
    dependabot_path.write_text(
        'version: 2\nupdates:\n  - package-ecosystem: "pip"\n    directory: "/"\n',
        encoding="utf-8",
    )
    package_json = tmp_path / "vscode" / "sattline-vscode" / "package.json"
    package_json.parent.mkdir(parents=True, exist_ok=True)
    package_json.write_text('{"name": "demo-extension"}\n', encoding="utf-8")
    tracked_paths.extend((".github/workflows/ci.yml", ".github/dependabot.yml", "vscode/sattline-vscode/package.json"))

    findings = repo_audit._find_public_readiness_findings(tmp_path, tracked_paths=tuple(tracked_paths))

    npm_finding = next(finding for finding in findings if finding.id == "missing-npm-dependabot-monitoring")
    assert npm_finding.path == ".github/dependabot.yml"
    assert npm_finding.detail == "/vscode/sattline-vscode"


def test_find_public_readiness_findings_ignores_hardened_publish_and_monitored_npm(tmp_path: Path):
    tracked_paths = list(_write_public_readiness_baseline(tmp_path))
    publish_workflow = tmp_path / ".github" / "workflows" / "publish.yml"
    publish_workflow.parent.mkdir(parents=True, exist_ok=True)
    publish_workflow.write_text(
        "name: Publish\n\n"
        "on:\n"
        "  push:\n"
        "    tags:\n"
        '      - "v*"\n'
        "  workflow_dispatch:\n\n"
        "permissions:\n"
        "  contents: read\n\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "  publish:\n"
        "    if: ${{ github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v') }}\n"
        "    needs: build\n"
        "    runs-on: ubuntu-latest\n"
        "    environment: pypi-release\n"
        "    permissions:\n"
        "      contents: read\n"
        "      id-token: write\n"
        "    steps:\n"
        "      - run: echo publish\n",
        encoding="utf-8",
    )
    dependabot_path = tmp_path / ".github" / "dependabot.yml"
    dependabot_path.parent.mkdir(parents=True, exist_ok=True)
    dependabot_path.write_text(
        'version: 2\nupdates:\n  - package-ecosystem: "npm"\n    directory: "/vscode/sattline-vscode"\n',
        encoding="utf-8",
    )
    package_json = tmp_path / "vscode" / "sattline-vscode" / "package.json"
    package_json.parent.mkdir(parents=True, exist_ok=True)
    package_json.write_text('{"name": "demo-extension"}\n', encoding="utf-8")
    tracked_paths.extend(
        (".github/workflows/publish.yml", ".github/dependabot.yml", "vscode/sattline-vscode/package.json")
    )

    findings = repo_audit._find_public_readiness_findings(tmp_path, tracked_paths=tuple(tracked_paths))

    finding_ids = {finding.id for finding in findings}
    assert "workflow-level-id-token-write" not in finding_ids
    assert "publish-workflow-missing-environment" not in finding_ids
    assert "publish-workflow-missing-tag-guard" not in finding_ids
    assert "missing-npm-dependabot-monitoring" not in finding_ids


def test_find_public_readiness_findings_flags_unverified_workflow_downloads_and_unsafe_scripts(tmp_path: Path):
    tracked_paths = list(_write_public_readiness_baseline(tmp_path))
    workflow_path = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(
        "name: CI\n\n"
        "on: [push]\n\n"
        "jobs:\n"
        "  audit:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: curl -fsSL https://example.invalid/tool.tar.gz -o tool.tar.gz\n",
        encoding="utf-8",
    )
    helper_path = tmp_path / "scripts" / "unsafe-helper.sh"
    helper_path.parent.mkdir(parents=True, exist_ok=True)
    helper_path.write_text(
        "surreal start --bind 0.0.0.0:3004 --user root --pass root memory\n",
        encoding="utf-8",
    )
    tracked_paths.extend((".github/workflows/ci.yml", "scripts/unsafe-helper.sh"))

    findings = repo_audit._find_public_readiness_findings(tmp_path, tracked_paths=tuple(tracked_paths))

    findings_by_id = {finding.id: finding for finding in findings}
    assert findings_by_id["workflow-download-without-verification"].path == ".github/workflows/ci.yml"
    assert findings_by_id["unsafe-local-db-helper"].path == "scripts/unsafe-helper.sh"


def test_audit_repository_leaks_only_filters_findings_and_skips_pipeline(tmp_path: Path):
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
