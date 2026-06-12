"""Compatibility wrapper for the moved repo-audit facade."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager, suppress
from typing import Any

from .audit import repo_audit as _owner

_MISSING = object()
_PUBLIC_WRAPPERS: dict[str, Any] = {}

_OWNER_SEAM_NAMES = (
    "audit_repository",
    "run_check_my_changes",
    "run_recommended_repo_audit_slice",
    "run_recommended_repo_audit_finish_gate",
    "_print_cli_summary",
    "_run_repo_audit_findings_checks",
    "apply_ai_gc",
    "build_repo_audit_check_recommendations",
    "build_cli_consistency_report",
    "build_ai_gc_report",
    "collect_custom_findings",
    "_collect_audit_git_state",
    "_find_pipeline_findings",
    "_build_repo_audit_scan_context",
    "_build_python_source_scan_context",
    "_repo_audit_finding_check_definitions",
    "_with_shared_text_line_findings",
    "_dedupe_findings",
    "_list_tracked_repo_paths",
    "_iter_repo_text_entries",
    "_line_findings",
    "_collect_cli_metadata",
    "_extract_documented_commands",
    "_find_documentation_command_gaps",
    "_find_unused_config_keys",
    "_find_architecture_findings",
    "_find_structural_report_findings",
    "_find_cli_findings",
    "_find_logging_findings",
    "_find_ignored_repo_path_references",
    "_run_harness_freshness_check",
    "_run_ratchet_policy_check",
    "_parse_coverage_findings",
    "_find_public_readiness_findings",
    "_build_local_import_graph",
    "_find_import_cycles",
    "_patch_doc_gardener_paths",
    "_read_text",
    "range",
)

_CHECK_RUNNER_SEAM_NAMES = (
    "_build_python_source_scan_context",
    "_collect_cli_metadata",
    "_extract_documented_commands",
    "_find_architecture_findings",
    "_find_cli_findings",
    "_find_documentation_command_gaps",
    "_find_ignored_repo_path_references",
    "_find_import_cycles",
    "_find_logging_findings",
    "_find_public_readiness_findings",
    "_find_structural_report_findings",
    "_find_unused_config_keys",
    "_iter_repo_text_entries",
    "_line_findings",
    "_parse_coverage_findings",
    "_patch_doc_gardener_paths",
    "_run_harness_freshness_check",
    "_run_ratchet_policy_check",
    "_build_local_import_graph",
)

_COMPAT_SEAM_NAMES = ("_list_tracked_repo_paths",)

_OWNER_AUDIT_REPOSITORY = _owner.audit_repository
_OWNER_RUN_CHECK_MY_CHANGES = _owner.run_check_my_changes
_OWNER_RUN_RECOMMENDED_SLICE = _owner.run_recommended_repo_audit_slice
_OWNER_RUN_RECOMMENDED_FINISH_GATE = _owner.run_recommended_repo_audit_finish_gate
_OWNER_PRINT_CLI_SUMMARY = _owner._print_cli_summary
_OWNER_RUN_REPO_AUDIT_FINDINGS_CHECKS = _owner._run_repo_audit_findings_checks
_OWNER_APPLY_AI_GC = _owner.apply_ai_gc
_OWNER_BUILD_RECOMMENDATIONS = _owner.build_repo_audit_check_recommendations
_OWNER_BUILD_CLI_CONSISTENCY_REPORT = _owner.build_cli_consistency_report
_OWNER_BUILD_AI_GC_REPORT = _owner.build_ai_gc_report
_OWNER_COLLECT_CUSTOM_FINDINGS = _owner.collect_custom_findings
_OWNER_COLLECT_AUDIT_GIT_STATE = _owner._collect_audit_git_state
_OWNER_FIND_PIPELINE_FINDINGS = _owner._find_pipeline_findings


def _call_owner_with_test_seams(name: str, *args: Any, **kwargs: Any) -> Any:
    with _patched_owner_test_seams():
        return getattr(_owner, name)(*args, **kwargs)


def _seam_override(name: str, original: Any) -> Any:
    candidate = globals().get(name, _MISSING)
    if candidate is _MISSING or candidate is _PUBLIC_WRAPPERS.get(name):
        return original
    return candidate


def _capture_module_seams(module: Any, seam_names: tuple[str, ...]) -> dict[str, Any]:
    return {name: getattr(module, name, _MISSING) for name in seam_names}


def _apply_module_seams(module: Any, seam_names: tuple[str, ...]) -> None:
    for name in seam_names:
        original = getattr(module, name, _MISSING)
        override = _seam_override(name, original)
        if override is _MISSING:
            continue
        setattr(module, name, override)


def _restore_module_seams(module: Any, originals: dict[str, Any]) -> None:
    for name, original in originals.items():
        if original is _MISSING:
            with suppress(AttributeError):
                delattr(module, name)
            continue
        setattr(module, name, original)


@contextmanager
def _patched_owner_test_seams() -> Generator[None]:
    originals = {name: getattr(_owner, name, _MISSING) for name in _OWNER_SEAM_NAMES}
    check_runner_module = _owner._repo_audit_check_runners_module
    compat_module = _owner._repo_audit_compat_module
    check_runner_originals = _capture_module_seams(check_runner_module, _CHECK_RUNNER_SEAM_NAMES)
    compat_originals = _capture_module_seams(compat_module, _COMPAT_SEAM_NAMES)
    _owner.audit_repository = _seam_override("audit_repository", _OWNER_AUDIT_REPOSITORY)
    _owner.run_check_my_changes = _seam_override("run_check_my_changes", _OWNER_RUN_CHECK_MY_CHANGES)
    _owner.run_recommended_repo_audit_slice = _seam_override(
        "run_recommended_repo_audit_slice", _OWNER_RUN_RECOMMENDED_SLICE
    )
    _owner.run_recommended_repo_audit_finish_gate = _seam_override(
        "run_recommended_repo_audit_finish_gate", _OWNER_RUN_RECOMMENDED_FINISH_GATE
    )
    _owner._print_cli_summary = _seam_override("_print_cli_summary", _OWNER_PRINT_CLI_SUMMARY)
    _owner._run_repo_audit_findings_checks = _seam_override(
        "_run_repo_audit_findings_checks", _OWNER_RUN_REPO_AUDIT_FINDINGS_CHECKS
    )
    _owner.apply_ai_gc = _seam_override("apply_ai_gc", _OWNER_APPLY_AI_GC)
    _owner.build_repo_audit_check_recommendations = _seam_override(
        "build_repo_audit_check_recommendations", _OWNER_BUILD_RECOMMENDATIONS
    )
    _owner.build_cli_consistency_report = _seam_override(
        "build_cli_consistency_report", _OWNER_BUILD_CLI_CONSISTENCY_REPORT
    )
    _owner.build_ai_gc_report = _seam_override("build_ai_gc_report", _OWNER_BUILD_AI_GC_REPORT)
    _owner.collect_custom_findings = _seam_override("collect_custom_findings", _OWNER_COLLECT_CUSTOM_FINDINGS)
    _owner._collect_audit_git_state = _seam_override("_collect_audit_git_state", _OWNER_COLLECT_AUDIT_GIT_STATE)
    _owner._find_pipeline_findings = _seam_override("_find_pipeline_findings", _OWNER_FIND_PIPELINE_FINDINGS)
    for name, original in originals.items():
        override = _seam_override(name, original)
        if override is _MISSING:
            continue
        setattr(_owner, name, override)
    _apply_module_seams(check_runner_module, _CHECK_RUNNER_SEAM_NAMES)
    _apply_module_seams(compat_module, _COMPAT_SEAM_NAMES)
    try:
        yield
    finally:
        _owner.audit_repository = _OWNER_AUDIT_REPOSITORY
        _owner.run_check_my_changes = _OWNER_RUN_CHECK_MY_CHANGES
        _owner.run_recommended_repo_audit_slice = _OWNER_RUN_RECOMMENDED_SLICE
        _owner.run_recommended_repo_audit_finish_gate = _OWNER_RUN_RECOMMENDED_FINISH_GATE
        _owner._print_cli_summary = _OWNER_PRINT_CLI_SUMMARY
        _owner._run_repo_audit_findings_checks = _OWNER_RUN_REPO_AUDIT_FINDINGS_CHECKS
        _owner.apply_ai_gc = _OWNER_APPLY_AI_GC
        _owner.build_repo_audit_check_recommendations = _OWNER_BUILD_RECOMMENDATIONS
        _owner.build_cli_consistency_report = _OWNER_BUILD_CLI_CONSISTENCY_REPORT
        _owner.build_ai_gc_report = _OWNER_BUILD_AI_GC_REPORT
        _owner.collect_custom_findings = _OWNER_COLLECT_CUSTOM_FINDINGS
        _owner._collect_audit_git_state = _OWNER_COLLECT_AUDIT_GIT_STATE
        _owner._find_pipeline_findings = _OWNER_FIND_PIPELINE_FINDINGS
        for name, original in originals.items():
            if original is _MISSING:
                with suppress(AttributeError):
                    delattr(_owner, name)
                continue
            setattr(_owner, name, original)
        _restore_module_seams(check_runner_module, check_runner_originals)
        _restore_module_seams(compat_module, compat_originals)


def audit_repository(*args: Any, **kwargs: Any) -> Any:
    return _call_owner_with_test_seams("audit_repository", *args, **kwargs)


def run_check_my_changes(*args: Any, **kwargs: Any) -> Any:
    return _call_owner_with_test_seams("run_check_my_changes", *args, **kwargs)


def run_recommended_repo_audit_slice(*args: Any, **kwargs: Any) -> Any:
    return _call_owner_with_test_seams("run_recommended_repo_audit_slice", *args, **kwargs)


def run_recommended_repo_audit_finish_gate(*args: Any, **kwargs: Any) -> Any:
    return _call_owner_with_test_seams("run_recommended_repo_audit_finish_gate", *args, **kwargs)


def collect_custom_findings(*args: Any, **kwargs: Any) -> Any:
    return _call_owner_with_test_seams("collect_custom_findings", *args, **kwargs)


def _forward_architecture_findings(*args: Any, **kwargs: Any) -> Any:
    return _call_owner_with_test_seams("_find_architecture_findings", *args, **kwargs)


_find_architecture_findings = _forward_architecture_findings


def _load_audit_run_history(*args: Any, **kwargs: Any) -> Any:
    return _call_owner_with_test_seams("_load_audit_run_history", *args, **kwargs)


def _run_harness_freshness_check(*args: Any, **kwargs: Any) -> Any:
    return _call_owner_with_test_seams("_run_harness_freshness_check", *args, **kwargs)


def _write_text_artifact(*args: Any, **kwargs: Any) -> Any:
    return _call_owner_with_test_seams("_write_text_artifact", *args, **kwargs)


def main(argv: list[str] | None = None) -> int:
    return _call_owner_with_test_seams("main", argv)


_PUBLIC_WRAPPERS.update(
    {
        "audit_repository": audit_repository,
        "collect_custom_findings": collect_custom_findings,
        "_find_architecture_findings": _find_architecture_findings,
        "_load_audit_run_history": _load_audit_run_history,
        "_run_harness_freshness_check": _run_harness_freshness_check,
        "_write_text_artifact": _write_text_artifact,
        "run_check_my_changes": run_check_my_changes,
        "run_recommended_repo_audit_slice": run_recommended_repo_audit_slice,
        "run_recommended_repo_audit_finish_gate": run_recommended_repo_audit_finish_gate,
    }
)


def __getattr__(name: str) -> Any:
    return getattr(_owner, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_owner)))


if __name__ == "__main__":
    raise SystemExit(main())
