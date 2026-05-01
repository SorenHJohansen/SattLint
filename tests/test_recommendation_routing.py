from pathlib import Path
from typing import Any, cast

import pytest

from sattlint.devtools import pipeline, repo_audit
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
    "corpus": ("tests/test_corpus.py", "docs/references/cli-commands.md"),
}

REPO_AUDIT_ROUTE_CASES = {
    "text-scan": ("README.md", "LICENSE"),
    "documented-commands": ("docs/references/cli-commands.md", "src/sattline_parser/api.py"),
    "unused-config-keys": ("src/sattlint/config.py", "README.md"),
    "architecture": ("src/sattlint/devtools/repo_audit.py", "README.md"),
    "structural-report": ("artifacts/analysis/structural_budget_ratchet.json", "README.md"),
    "cli": ("src/sattlint/devtools/repo_audit_cli.py", "src/sattline_parser/api.py"),
    "logging": ("src/sattlint/devtools/repo_audit.py", "README.md"),
    "ai-gc": ("src/sattlint/devtools/ai_gc.py", "README.md"),
    "ignored-repo-paths": ("scripts/run_repo_python.py", "README.md"),
    "coverage": ("coverage.xml", "README.md"),
    "public-readiness": ("SECURITY.md", "src/sattlint/devtools/repo_audit.py"),
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
    } <= issue_ids


def test_normalizers_and_skipped_stage_reports_cover_selection_helpers():
    assert normalize_changed_files(None) == []
    assert normalize_changed_files(["src\\main.py", "src/main.py", "", "tests\\test_main.py"]) == [
        "src/main.py",
        "tests/test_main.py",
    ]
    assert normalize_selected_checks("full", ["ruff", "ruff"], validate_profile=lambda _profile: None) == ("ruff",)
    with pytest.raises(ValueError):
        normalize_selected_checks("full", ["ghost"], validate_profile=lambda _profile: None)
    with pytest.raises(ValueError):
        normalize_selected_checks("full", ["   "], validate_profile=lambda _profile: None)

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
