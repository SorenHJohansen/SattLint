"""Compatibility wrapper for the moved repo-audit facade."""

from __future__ import annotations

from typing import Any

from .audit import repo_audit as _owner

REPO_ROOT = _owner.REPO_ROOT
DEFAULT_OUTPUT_DIR = _owner.DEFAULT_OUTPUT_DIR
AUDIT_PROFILE_CHOICES = _owner.AUDIT_PROFILE_CHOICES
REPO_AUDIT_FINDING_CHECK_IDS = _owner.REPO_AUDIT_FINDING_CHECK_IDS
REPO_AUDIT_SPECIAL_CHECK_IDS = _owner.REPO_AUDIT_SPECIAL_CHECK_IDS
REPO_AUDIT_INDIVIDUAL_CHECK_IDS = _owner.REPO_AUDIT_INDIVIDUAL_CHECK_IDS

audit_repository = _owner.audit_repository
run_check_my_changes = _owner.run_check_my_changes
run_recommended_repo_audit_slice = _owner.run_recommended_repo_audit_slice
run_recommended_repo_audit_finish_gate = _owner.run_recommended_repo_audit_finish_gate
collect_custom_findings = _owner.collect_custom_findings
build_repo_audit_check_catalog = _owner.build_repo_audit_check_catalog
build_repo_audit_check_recommendations = _owner.build_repo_audit_check_recommendations
build_cli_consistency_report = _owner.build_cli_consistency_report
build_ai_gc_report = _owner.build_ai_gc_report
apply_ai_gc = _owner.apply_ai_gc


def __getattr__(name: str) -> Any:
    if name.startswith("_"):
        raise AttributeError(name)
    return getattr(_owner, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | {name for name in dir(_owner) if not name.startswith("_")})


def main(argv: list[str] | None = None) -> int:
    return _owner.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
