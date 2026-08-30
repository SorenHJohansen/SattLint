"""Repo-audit family package."""

from __future__ import annotations

from . import repo_audit, repo_audit_cli, repo_audit_entrypoints, repo_audit_runs, repo_audit_shared
from .repo_audit import (
    AUDIT_PROFILE_CHOICES,
    DEFAULT_OUTPUT_DIR,
    REPO_AUDIT_FINDING_CHECK_IDS,
    REPO_AUDIT_INDIVIDUAL_CHECK_IDS,
    REPO_AUDIT_SPECIAL_CHECK_IDS,
    REPO_ROOT,
    apply_ai_gc,
    audit_repository,
    main,
)

run_check_my_changes = repo_audit.run_check_my_changes
run_recommended_repo_audit_slice = repo_audit.run_recommended_repo_audit_slice
run_recommended_repo_audit_finish_gate = repo_audit.run_recommended_repo_audit_finish_gate
collect_custom_findings = repo_audit.collect_custom_findings
build_repo_audit_check_catalog = repo_audit.build_repo_audit_check_catalog
build_repo_audit_check_recommendations = repo_audit.build_repo_audit_check_recommendations
build_cli_consistency_report = repo_audit.build_cli_consistency_report
build_ai_gc_report = repo_audit.build_ai_gc_report

__all__ = [
    "AUDIT_PROFILE_CHOICES",
    "DEFAULT_OUTPUT_DIR",
    "REPO_AUDIT_FINDING_CHECK_IDS",
    "REPO_AUDIT_INDIVIDUAL_CHECK_IDS",
    "REPO_AUDIT_SPECIAL_CHECK_IDS",
    "REPO_ROOT",
    "apply_ai_gc",
    "audit_repository",
    "build_ai_gc_report",
    "build_cli_consistency_report",
    "build_repo_audit_check_catalog",
    "build_repo_audit_check_recommendations",
    "collect_custom_findings",
    "main",
    "repo_audit",
    "repo_audit_cli",
    "repo_audit_entrypoints",
    "repo_audit_runs",
    "repo_audit_shared",
    "run_check_my_changes",
    "run_recommended_repo_audit_finish_gate",
    "run_recommended_repo_audit_slice",
]
