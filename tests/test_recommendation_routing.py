from pathlib import Path
from typing import Any, cast

import pytest

from sattlint.devtools import _repo_audit_entrypoint_runs, pipeline, repo_audit
from sattlint.devtools.pipeline_checks import (
    collect_repo_file_inventory,
    normalize_changed_files,
    normalize_selected_checks,
    path_matches_globs,
    skipped_stage_report,
    verify_check_catalog,
)

PIPELINE_ROUTE_CASES = {
    "ruff": ("src/sattlint/devtools/pipeline.py", "docs/references/cli-commands.md"),
    "pyright": ("src/sattlint/devtools/pipeline.py", "docs/references/cli-commands.md"),
    "pytest": ("tests/test_pipeline.py", "docs/references/cli-commands.md"),
    "vulture": ("src/sattlint/devtools/pipeline.py", "docs/references/cli-commands.md"),
    "bandit": ("src/sattlint/devtools/pipeline.py", "docs/references/cli-commands.md"),
    "structural-reports": ("src/sattlint/devtools/repo_audit.py", "docs/references/cli-commands.md"),
    "trace": ("src/sattlint_lsp/server.py", "docs/references/cli-commands.md"),
    "corpus": ("tests/parser/test_corpus.py", "docs/references/cli-commands.md"),
}

REPO_AUDIT_ROUTE_CASES = {
    "text-scan": ("README.md", "LICENSE"),
    "local-ci-parity": ("tests/test_repo_audit.py", "LICENSE"),
    "documented-commands": ("docs/references/cli-commands.md", "src/sattline_parser/api.py"),
    "unused-config-keys": ("src/sattlint/config.py", "README.md"),
    "architecture": ("src/sattlint/devtools/repo_audit.py", "README.md"),
    "structural-report": ("artifacts/analysis/structural_budget_ratchet.json", "README.md"),
    "cli": ("src/sattlint/devtools/repo_audit_cli.py", "src/sattline_parser/api.py"),
    "logging": ("src/sattlint/devtools/repo_audit.py", "README.md"),
    "ai-gc": ("src/sattlint/devtools/ai_gc.py", "README.md"),
    "ignored-repo-paths": ("scripts/run_repo_python.py", "README.md"),
    "harness-freshness": ("AGENTS.md", "README.md"),
    "coverage": ("coverage.xml", "README.md"),
    "public-readiness": ("SECURITY.md", "src/sattlint/devtools/repo_audit.py"),
    "ratchet-policy": ("artifacts/analysis/file_debt_ratchet.json", "README.md"),
    "verify-recommendations": ("src/sattlint/devtools/pipeline_checks.py", "src/sattlint/config.py"),
    "cli-consistency": ("docs/references/cli-commands.md", "src/sattline_parser/api.py"),
}


def _catalog_entry_by_id(catalog: dict[str, Any], check_id: str) -> dict[str, Any]:
    checks = catalog["checks"]
    assert isinstance(checks, list)
    return next(cast(dict[str, Any], entry) for entry in checks if cast(dict[str, Any], entry)["id"] == check_id)


def test_pipeline_route_case_matrix_is_complete(tmp_path):
    catalog = pipeline.build_pipeline_check_catalog(profile="full", output_dir=tmp_path)

    assert {entry["id"] for entry in catalog["checks"]} == set(PIPELINE_ROUTE_CASES)


@pytest.mark.parametrize("check_id", sorted(PIPELINE_ROUTE_CASES))
def test_pipeline_route_cases_cover_positive_and_negative_paths(tmp_path, check_id):
    catalog = pipeline.build_pipeline_check_catalog(profile="full", output_dir=tmp_path)
    entry = _catalog_entry_by_id(catalog, check_id)
    positive_path, negative_path = PIPELINE_ROUTE_CASES[check_id]
    path_globs = cast(list[str], entry["path_globs"])

    assert path_matches_globs(positive_path, path_globs)
    assert not path_matches_globs(negative_path, path_globs)


def test_repo_audit_route_case_matrix_is_complete(tmp_path):
    catalog = repo_audit.build_repo_audit_check_catalog(profile="full", output_dir=tmp_path, fail_on="high")
    repo_audit_checks = {entry["id"] for entry in catalog["checks"] if entry["source"] == "repo-audit"}

    assert repo_audit_checks == set(REPO_AUDIT_ROUTE_CASES)


@pytest.mark.parametrize("check_id", sorted(REPO_AUDIT_ROUTE_CASES))
def test_repo_audit_route_cases_cover_positive_and_negative_paths(tmp_path, check_id):
    catalog = repo_audit.build_repo_audit_check_catalog(profile="full", output_dir=tmp_path, fail_on="high")
    entry = _catalog_entry_by_id(catalog, check_id)
    positive_path, negative_path = REPO_AUDIT_ROUTE_CASES[check_id]
    path_globs = cast(list[str], entry["path_globs"])

    assert path_matches_globs(positive_path, path_globs)
    assert not path_matches_globs(negative_path, path_globs)


def test_repo_audit_helper_filters_findings_to_changed_scope():
    related_finding = repo_audit.Finding(
        "related-gap",
        "public-readiness",
        "medium",
        "high",
        "Related finding.",
        path="src/sattlint/devtools/repo_audit.py",
    )
    directory_finding = repo_audit.Finding(
        "directory-gap",
        "public-readiness",
        "medium",
        "high",
        "Directory finding.",
        path="artifacts",
    )
    pathless_finding = repo_audit.Finding(
        "pathless-gap",
        "public-readiness",
        "low",
        "high",
        "Pathless finding.",
    )

    filtered = _repo_audit_entrypoint_runs._filter_custom_findings_to_changed_files(
        [related_finding, directory_finding, pathless_finding],
        ["src/sattlint/devtools/repo_audit.py"],
    )

    assert [finding.id for finding in filtered] == ["related-gap", "pathless-gap"]
    assert _repo_audit_entrypoint_runs._filter_custom_findings_to_changed_files([directory_finding], []) == [
        directory_finding
    ]


def test_find_public_readiness_findings_assigns_scope_paths_for_finish_gate_coverage(tmp_path):
    tracked_generated_path = "/".join(("build", "status.json"))
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n[project.urls]\nRepository = "https://example.invalid/demo"\n',
        encoding="utf-8",
    )

    findings = repo_audit._find_public_readiness_findings(
        tmp_path,
        tracked_paths=(
            "LICENSE",
            "CONTRIBUTING.md",
            ".gitignore",
            "pyproject.toml",
            tracked_generated_path,
        ),
    )
    findings_by_id = {finding.id: finding for finding in findings}

    assert findings_by_id["missing-public-file"].path == "README.md"
    assert findings_by_id["missing-ci-workflow"].path == ".github/workflows"
    assert findings_by_id["tracked-generated-artifacts"].path == "build"
    assert findings_by_id["unexpected-tracked-root-entry"].path == "build"


def test_run_recommended_repo_audit_slice_filters_findings_in_owner_covered_suite(monkeypatch, tmp_path):
    recommendation = {
        "recommended_check_ids": ["public-readiness"],
        "recommended_pipeline_check_ids": [],
        "recommended_repo_audit_check_ids": ["public-readiness"],
    }
    unrelated_finding = repo_audit.Finding(
        "tracked-generated-artifacts",
        "public-readiness",
        "high",
        "high",
        "Tracked generated artifacts.",
        path="artifacts",
    )
    related_finding = repo_audit.Finding(
        "changed-file-warning",
        "public-readiness",
        "medium",
        "high",
        "Changed file warning.",
        path="src/sattlint/devtools/repo_audit.py",
    )

    monkeypatch.setattr(
        repo_audit._repo_audit_entrypoints,
        "build_repo_audit_check_recommendations",
        lambda **_kwargs: recommendation,
    )
    monkeypatch.setattr(
        repo_audit._repo_audit_entrypoints,
        "collect_custom_findings",
        lambda *args, **kwargs: [unrelated_finding, related_finding],
    )
    monkeypatch.setattr(repo_audit, "_write_markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(repo_audit, "_write_audit_run_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(repo_audit, "_mirror_latest_reports", lambda *args, **kwargs: None)

    summary = repo_audit.run_recommended_repo_audit_slice(
        tmp_path,
        profile="full",
        fail_on="high",
        include_generated=False,
        suspicious_identifiers=[],
        skip_vulture=False,
        skip_bandit=False,
        changed_files=["src/sattlint/devtools/repo_audit.py"],
    )

    assert summary["finding_count"] == 1
    assert [finding["id"] for finding in summary["findings"]] == ["changed-file-warning"]


def test_verify_check_catalog_passes_for_pipeline_catalog(tmp_path):
    catalog = pipeline.build_pipeline_check_catalog(profile="full", output_dir=tmp_path)
    report = verify_check_catalog(catalog, repo_root=Path(pipeline.REPO_ROOT))

    assert report["status"] == "pass"
    assert report["issue_count"] == 0


def test_verify_check_catalog_passes_for_repo_audit_catalog(tmp_path):
    catalog = repo_audit.build_repo_audit_check_catalog(profile="full", output_dir=tmp_path, fail_on="high")
    report = verify_check_catalog(catalog, repo_root=Path(repo_audit.REPO_ROOT))

    assert report["status"] == "pass"
    assert report["issue_count"] == 0


def test_collect_repo_file_inventory_skips_ignored_directories(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "tracked.py").write_text("print('tracked')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_owner.py").write_text("def test_owner():\n    assert True\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "status.json").write_text("ignored\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "vendor.js").write_text("ignored\n", encoding="utf-8")
    (tmp_path / "htmlcov").mkdir()
    (tmp_path / "htmlcov" / "index.html").write_text("ignored\n", encoding="utf-8")

    assert collect_repo_file_inventory(tmp_path) == ["src/tracked.py", "tests/test_owner.py"]


def test_verify_check_catalog_reports_metadata_issues(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "tracked.py").write_text("print('tracked')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_owner.py").write_text("def test_owner():\n    assert True\n", encoding="utf-8")

    catalog = {
        "checks": [
            {
                "id": "missing-owner-surface",
                "estimated_cost": "low",
                "path_globs": ["src/**/*.py"],
                "owner_test_targets": ["tests/test_owner.py"],
            },
            {
                "id": "invalid-estimated-cost",
                "owner_surface": "cli",
                "estimated_cost": "wild",
                "path_globs": ["src/**/*.py"],
                "owner_test_targets": ["tests/test_owner.py"],
            },
            {
                "id": "missing-path-globs",
                "owner_surface": "cli",
                "estimated_cost": "low",
                "path_globs": [],
                "owner_test_targets": ["tests/test_owner.py"],
            },
            {
                "id": "backslash-path-glob",
                "owner_surface": "cli",
                "estimated_cost": "low",
                "path_globs": ["src\\**\\*.py"],
                "owner_test_targets": ["tests/test_owner.py"],
            },
            {
                "id": "dead-path-globs",
                "owner_surface": "cli",
                "estimated_cost": "low",
                "path_globs": ["docs/**/*.md"],
                "owner_test_targets": ["tests/test_owner.py"],
            },
            {
                "id": "overbroad-path-globs",
                "owner_surface": "cli",
                "estimated_cost": "low",
                "path_globs": ["**/*"],
                "owner_test_targets": ["tests/test_owner.py"],
            },
            {
                "id": "missing-owner-tests",
                "owner_surface": "cli",
                "estimated_cost": "low",
                "path_globs": ["src/**/*.py"],
                "owner_test_targets": [],
            },
            {
                "id": "missing-owner-test-targets",
                "owner_surface": "cli",
                "estimated_cost": "low",
                "path_globs": ["src/**/*.py"],
                "owner_test_targets": ["tests/test_missing.py"],
                "ai_summary": "summary",
                "ai_instruction_files": [".github/instructions/missing.instructions.md"],
            },
            {
                "id": "backslash-ai-instruction-file",
                "owner_surface": "cli",
                "estimated_cost": "low",
                "path_globs": ["src/**/*.py"],
                "owner_test_targets": ["tests/test_owner.py"],
                "ai_summary": "summary",
                "ai_instruction_files": [r".github\instructions\cli.instructions.md"],
            },
            {
                "id": "missing-ai-instruction-targets",
                "owner_surface": "cli",
                "estimated_cost": "low",
                "path_globs": ["src/**/*.py"],
                "owner_test_targets": ["tests/test_owner.py"],
                "ai_summary": "summary",
                "ai_instruction_files": [".github/instructions/missing.instructions.md"],
            },
        ]
    }

    report = verify_check_catalog(catalog, repo_root=tmp_path)
    issue_ids = {issue["issue_id"] for issue in report["issues"]}

    assert report["status"] == "fail"
    assert {
        "missing-owner-surface",
        "invalid-estimated-cost",
        "missing-path-globs",
        "backslash-path-glob",
        "dead-path-globs",
        "overbroad-path-globs",
        "missing-owner-tests",
        "missing-owner-test-targets",
        "backslash-ai-instruction-file",
        "missing-ai-instruction-targets",
        "missing-ai-summary",
        "missing-ai-instruction-files",
    } <= issue_ids


def test_normalizers_and_skipped_stage_reports_cover_selection_helpers():
    assert normalize_changed_files(None) == []
    assert normalize_changed_files(["src\\main.py", "src/main.py", "", "tests\\test_main.py"]) == [
        "src/main.py",
        "tests/test_main.py",
    ]
    assert normalize_selected_checks("full", None, validate_profile=lambda _profile: None) is None
    assert normalize_selected_checks("full", ["ruff", "ruff"], validate_profile=lambda _profile: None) == ("ruff",)
    with pytest.raises(ValueError):
        normalize_selected_checks("full", ["ghost"], validate_profile=lambda _profile: None)
    with pytest.raises(ValueError):
        normalize_selected_checks("full", ["   "], validate_profile=lambda _profile: None)

    quick_catalog = pipeline.build_pipeline_check_catalog(profile="quick", output_dir=Path("artifacts/audit"))
    assert {entry["id"] for entry in quick_catalog["checks"]}.isdisjoint({"vulture", "bandit", "trace", "corpus"})

    assert skipped_stage_report("ruff") == {
        "tool": "ruff",
        "skipped": True,
        "detail": "skipped by check selection",
        "exit_code": None,
        "finding_count": 0,
        "findings": [],
    }
    assert skipped_stage_report("pyright")["warning_count"] == 0
    assert skipped_stage_report("pytest")["summary"] == {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    assert skipped_stage_report("environment") == {
        "kind": "sattlint.pipeline.environment",
        "schema_version": 1,
        "skipped": True,
    }
