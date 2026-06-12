"""Repository audit core checks for portability, security, wiring, and public-readiness."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404 - audit intentionally executes trusted local developer tools
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from sattlint.contracts import FindingCollection
from sattlint.devtools import audit_core as _audit_core_module
from sattlint.devtools import audit_orchestration as _audit_orchestration_module
from sattlint.devtools import ledger as _ledger_module
from sattlint.devtools import pipeline as pipeline_module
from sattlint.devtools.ai import ai_gc as _ai_gc_module
from sattlint.devtools.artifact_registry import (
    AUDIT_ARTIFACTS,
    AUDIT_RUN_HISTORY_FILENAME,
    AUDIT_RUN_HISTORY_SCHEMA_KIND,
    AUDIT_RUN_HISTORY_SCHEMA_VERSION,
    artifact_reports_map,
)
from sattlint.devtools.progress_reporting import ProgressReporter
from sattlint.devtools.shared.pipeline_artifacts import write_json_artifact
from sattlint.path_sanitizer import sanitize_path_for_report
from sattlint.repo_paths import repo_root_from

from . import _repo_audit_check_runners as _repo_audit_check_runners_module
from . import repo_audit_cli as _repo_audit_cli_module
from . import repo_audit_compat as _repo_audit_compat_module
from . import repo_audit_entrypoints as _repo_audit_entrypoints
from . import repo_audit_shared as _repo_audit_shared_module

app_module = _repo_audit_compat_module.app_module

REPO_AUDIT_FINDING_CHECK_IDS = _repo_audit_entrypoints.REPO_AUDIT_FINDING_CHECK_IDS
REPO_AUDIT_INDIVIDUAL_CHECK_IDS = _repo_audit_entrypoints.REPO_AUDIT_INDIVIDUAL_CHECK_IDS
REPO_AUDIT_SPECIAL_CHECK_IDS = _repo_audit_entrypoints.REPO_AUDIT_SPECIAL_CHECK_IDS
_blocking_finding_count = _repo_audit_entrypoints._blocking_finding_count
_category_counts = _repo_audit_entrypoints._category_counts
_default_corpus_manifest_dir = _repo_audit_entrypoints._default_corpus_manifest_dir
_max_severity = _repo_audit_entrypoints._max_severity
_print_cli_summary = _repo_audit_entrypoints._print_cli_summary
_repo_audit_finding_check_definitions = _repo_audit_entrypoints._repo_audit_finding_check_definitions
_recommended_command = _repo_audit_entrypoints._recommended_command
_run_repo_audit_cli_consistency_check = _repo_audit_entrypoints._run_repo_audit_cli_consistency_check
_run_repo_audit_findings_checks = _repo_audit_entrypoints._run_repo_audit_findings_checks
_severity_counts = _repo_audit_entrypoints._severity_counts
_should_fail = _repo_audit_entrypoints._should_fail
build_repo_audit_check_catalog = _repo_audit_entrypoints.build_repo_audit_check_catalog
build_repo_audit_check_recommendations = _repo_audit_entrypoints.build_repo_audit_check_recommendations
collect_custom_findings = _repo_audit_entrypoints.collect_custom_findings
run_check_my_changes = _repo_audit_entrypoints.run_check_my_changes
run_recommended_repo_audit_finish_gate = _repo_audit_entrypoints.run_recommended_repo_audit_finish_gate
run_recommended_repo_audit_slice = _repo_audit_entrypoints.run_recommended_repo_audit_slice

REPO_ROOT = repo_root_from(Path(__file__))
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "audit"
PIPELINE_OUTPUT_DIRNAME = "pipeline"
AUDIT_RUN_HISTORY_DIRNAME = _ledger_module.AUDIT_RUN_HISTORY_DIRNAME
AUDIT_RUN_HISTORY_LIMIT = _ledger_module.AUDIT_RUN_HISTORY_LIMIT
TEXT_SUFFIXES = _repo_audit_shared_module.TEXT_SUFFIXES
SKIP_CONTENT_SCAN_PREFIXES = _repo_audit_shared_module.SKIP_CONTENT_SCAN_PREFIXES
GENERATED_PATH_PREFIXES = _repo_audit_shared_module.GENERATED_PATH_PREFIXES
TOP_LEVEL_TRACKED_ENTRY_ALLOWLIST = _repo_audit_shared_module.TOP_LEVEL_TRACKED_ENTRY_ALLOWLIST
IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PREFIXES = (
    _repo_audit_shared_module.IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PREFIXES
)
IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PATHS = _repo_audit_shared_module.IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PATHS
IGNORED_REPO_PATH_REFERENCE_PREFIXES = _repo_audit_shared_module.IGNORED_REPO_PATH_REFERENCE_PREFIXES
IGNORED_REPO_PATH_REFERENCE_EXACT = _repo_audit_shared_module.IGNORED_REPO_PATH_REFERENCE_EXACT
SKIP_SELF_SCAN_PATHS = _repo_audit_shared_module.SKIP_SELF_SCAN_PATHS
SKIP_DIRS = _repo_audit_shared_module.SKIP_DIRS
LEAK_RELEVANT_CATEGORIES = _repo_audit_shared_module.LEAK_RELEVANT_CATEGORIES
LEAK_RELEVANT_FINDING_IDS = _repo_audit_shared_module.LEAK_RELEVANT_FINDING_IDS
SEVERITY_RANK = _repo_audit_shared_module.SEVERITY_RANK
AUDIT_PROFILE_CHOICES = _repo_audit_shared_module.AUDIT_PROFILE_CHOICES
PLACEHOLDER_VALUES = _repo_audit_shared_module.PLACEHOLDER_VALUES
ALLOWED_PRINT_MODULES = _repo_audit_shared_module.ALLOWED_PRINT_MODULES
ALLOWED_PRINT_PREFIXES = _repo_audit_shared_module.ALLOWED_PRINT_PREFIXES
WINDOWS_PATH_RE = _repo_audit_shared_module.WINDOWS_PATH_RE
_DOCUMENTED_COMMAND_RE = _repo_audit_shared_module.DOCUMENTED_COMMAND_RE
UNIX_PATH_RE = _repo_audit_shared_module.UNIX_PATH_RE
LOCAL_ENDPOINT_RE = _repo_audit_shared_module.LOCAL_ENDPOINT_RE
EMAIL_RE = _repo_audit_shared_module.EMAIL_RE
PRIVATE_KEY_RE = _repo_audit_shared_module.PRIVATE_KEY_RE
SECRET_ASSIGNMENT_RE = _repo_audit_shared_module.SECRET_ASSIGNMENT_RE
PRINT_CALL_RE = _repo_audit_shared_module.PRINT_CALL_RE
OVERSIZED_MODULE_LINE_LIMIT = _repo_audit_shared_module.OVERSIZED_MODULE_LINE_LIMIT
STRUCTURAL_DEBT_FINDING_IDS = _repo_audit_shared_module.STRUCTURAL_DEBT_FINDING_IDS
HARNESS_FRESHNESS_DOC_SCANNERS = _repo_audit_shared_module.HARNESS_FRESHNESS_DOC_SCANNERS
IGNORED_NORMALIZED_PIPELINE_FINDINGS = _repo_audit_shared_module.IGNORED_NORMALIZED_PIPELINE_FINDINGS
LOCAL_CI_PARITY_LINE_FINDING_IDS = _repo_audit_shared_module.LOCAL_CI_PARITY_LINE_FINDING_IDS
LOCAL_DEPENDENCY_MARKERS = _repo_audit_shared_module.LOCAL_DEPENDENCY_MARKERS
_PATH_INJECTION_CALL_PATHS_ATTR = "PATH_INJECTION_CALL_PATHS"
_HOST_SIGNAL_ATTR_PATHS_ATTR = "HOST_SIGNAL_ATTR_PATHS"
_HOST_SIGNAL_CALL_PATHS_ATTR = "HOST_SIGNAL_CALL_PATHS"
PATH_INJECTION_CALL_PATHS = cast(
    set[tuple[str, ...]],
    getattr(_repo_audit_shared_module, _PATH_INJECTION_CALL_PATHS_ATTR),
)
HOST_SIGNAL_ATTR_PATHS = cast(
    set[tuple[str, ...]],
    getattr(_repo_audit_shared_module, _HOST_SIGNAL_ATTR_PATHS_ATTR),
)
HOST_SIGNAL_CALL_PATHS = cast(
    set[tuple[str, ...]],
    getattr(_repo_audit_shared_module, _HOST_SIGNAL_CALL_PATHS_ATTR),
)
Finding = _repo_audit_shared_module.Finding
DocumentedCommand = _repo_audit_shared_module.DocumentedCommand
PythonSourceScanContext = _repo_audit_shared_module.PythonSourceScanContext
RepoAuditScanContext = _repo_audit_shared_module.RepoAuditScanContext
_leading_string_args = _repo_audit_shared_module.leading_string_args
_attribute_path = _repo_audit_shared_module.attribute_path
_repo_relative_path_from_expr = _repo_audit_shared_module.repo_relative_path_from_expr
_normalize_repo_relative_literal = _repo_audit_shared_module.normalize_repo_relative_literal
_is_ignored_repo_path_reference = _repo_audit_shared_module.is_ignored_repo_path_reference
_source_segment_summary = _repo_audit_compat_module._source_segment_summary
_contains_host_signal = _repo_audit_compat_module._contains_host_signal
_is_pythonpath_target = _repo_audit_compat_module._is_pythonpath_target
_find_marker_in_segment = _repo_audit_compat_module._find_marker_in_segment
_find_ignored_repo_path_references = _repo_audit_compat_module._find_ignored_repo_path_references
_find_hidden_local_dependency_findings = _repo_audit_compat_module._find_hidden_local_dependency_findings
_find_host_specific_test_assumptions = _repo_audit_compat_module._find_host_specific_test_assumptions
_layer_linter_module = _repo_audit_check_runners_module._layer_linter_module
_doc_gardener_module = _repo_audit_check_runners_module._doc_gardener_module
_extract_documented_commands = _repo_audit_check_runners_module._extract_documented_commands
_find_documentation_command_gaps = _repo_audit_check_runners_module._find_documentation_command_gaps
_find_unused_config_keys = _repo_audit_check_runners_module._find_unused_config_keys
_build_local_import_graph = _repo_audit_check_runners_module._build_local_import_graph
_find_import_cycles = _repo_audit_check_runners_module._find_import_cycles
_run_local_ci_parity_check = _repo_audit_check_runners_module._run_local_ci_parity_check
build_ratchet_policy_report = _repo_audit_check_runners_module.build_ratchet_policy_report
_run_ratchet_policy_check = _repo_audit_check_runners_module._run_ratchet_policy_check


_relative_path = _repo_audit_compat_module._relative_path
app_module = _repo_audit_compat_module.app_module


def _write_text_artifact(path: Path, content: str) -> None:
    _ledger_module.write_text_artifact(
        path,
        content,
        replace_fn=os.replace,
        sleep_fn=time.sleep,
        temp_file_factory=tempfile.NamedTemporaryFile,
        range_factory=range,
    )


def _write_markdown(path: Path, findings: list[Finding], summary: dict[str, Any]) -> None:
    _ledger_module.write_markdown(path, findings, summary, write_text_artifact_fn=_write_text_artifact)


_mirror_latest_reports = _repo_audit_compat_module._mirror_latest_reports
_sanitize_report_path = _repo_audit_compat_module._sanitize_report_path


def _load_audit_run_history(path: Path) -> list[dict[str, Any]]:
    return _ledger_module.load_audit_run_history(path, read_text=_read_text)


_build_audit_run_id = _repo_audit_compat_module._build_audit_run_id


def _collect_audit_git_state(root: Path = REPO_ROOT) -> dict[str, Any]:
    return _ledger_module.collect_audit_git_state(root, git_which=shutil.which, run_command=subprocess.run)


_copy_audit_snapshot = _repo_audit_compat_module._copy_audit_snapshot


_history_stale_reasons = _ledger_module.history_stale_reasons


_failure_signature = _ledger_module.failure_signature


_build_failure_patterns = _ledger_module.build_failure_patterns


def _write_audit_run_history(
    source_dir: Path,
    *,
    latest_output_dir: Path | None,
    report_kind: str,
    primary_payload: dict[str, Any],
    status_payload: dict[str, Any] | None = None,
    summary_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _ledger_module.write_repo_audit_run_history(
        source_dir,
        latest_output_dir=latest_output_dir,
        report_kind=report_kind,
        primary_payload=primary_payload,
        status_payload=status_payload,
        summary_payload=summary_payload,
        history_filename=AUDIT_RUN_HISTORY_FILENAME,
        history_dirname=AUDIT_RUN_HISTORY_DIRNAME,
        history_limit=AUDIT_RUN_HISTORY_LIMIT,
        schema_kind=AUDIT_RUN_HISTORY_SCHEMA_KIND,
        schema_version=AUDIT_RUN_HISTORY_SCHEMA_VERSION,
        build_run_id=_build_audit_run_id,
        copy_snapshot=_copy_audit_snapshot,
        load_history_fn=_load_audit_run_history,
        collect_git_state_fn=_collect_audit_git_state,
        history_stale_reasons=_history_stale_reasons,
        build_failure_patterns=_build_failure_patterns,
        sanitize_report_path_fn=_sanitize_report_path,
        write_json=write_json_artifact,
        repo_root=REPO_ROOT,
    )


_read_text = _repo_audit_compat_module._read_text
_should_skip_dir = _repo_audit_compat_module._should_skip_dir
_list_tracked_repo_paths = _repo_audit_compat_module._list_tracked_repo_paths
_iter_repo_file_candidates = _repo_audit_compat_module._iter_repo_file_candidates
_iter_tracked_repo_file_candidates = _repo_audit_compat_module._iter_tracked_repo_file_candidates


_iter_repo_text_files = _repo_audit_compat_module._iter_repo_text_files
_iter_tracked_repo_text_files = _repo_audit_compat_module._iter_tracked_repo_text_files


_iter_repo_text_entries = _repo_audit_compat_module._iter_repo_text_entries
_redact_value = _repo_audit_compat_module._redact_value
_redact_email = _repo_audit_compat_module._redact_email
_severity_for_path = _repo_audit_compat_module._severity_for_path
_line_findings = _repo_audit_compat_module._line_findings
_load_pyproject = _repo_audit_compat_module._load_pyproject
_extract_documented_commands = _repo_audit_compat_module._extract_documented_commands
_collect_cli_metadata = _repo_audit_compat_module._collect_cli_metadata
_module_name_from_path = _repo_audit_compat_module._module_name_from_path
_resolve_import = _repo_audit_compat_module._resolve_import


def _find_architecture_findings(
    source_root: Path,
    *,
    content_by_file: dict[Path, str] | None = None,
    ast_by_file: dict[Path, Any] | None = None,
) -> list[Finding]:
    findings = _audit_core_module.find_architecture_findings(
        source_root,
        read_text_fn=_read_text,
        relative_path=lambda path: _relative_path(path),
        finding_factory=Finding,
        build_local_import_graph_fn=_build_local_import_graph,
        find_import_cycles_fn=_find_import_cycles,
        oversized_module_line_limit=OVERSIZED_MODULE_LINE_LIMIT,
        content_by_file=content_by_file,
        ast_by_file=ast_by_file,
    )
    try:
        policy = _layer_linter_module.load_policy()
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        findings.append(
            Finding(
                id="layer-lint-policy-load-error",
                category="architecture",
                severity="high",
                confidence="high",
                message=f"Failed to load layer-lint policy: {type(exc).__name__}: {exc}",
                path="metrics/layer_lint_policy.json",
                source="layer-linter",
            )
        )
        return findings

    file_iterable = list((content_by_file or {}).items()) or [
        (path, _read_text(path)) for path in source_root.rglob("*.py")
    ]
    repo_root = source_root.parent
    for path, text in file_iterable:
        violations = _layer_linter_module.check_file_for_arch_violations(
            path,
            repo_root=repo_root,
            content=text,
            tree=None if ast_by_file is None else ast_by_file.get(path),
            policy=policy,
        )
        for violation in violations:
            finding_id = "forbidden-import-policy" if violation.violation_kind == "policy" else "layer-import-violation"
            detail = None
            if violation.current_module and violation.imported_module:
                detail = f"{violation.current_module} -> {violation.imported_module}"
            try:
                finding_path = path.relative_to(repo_root).as_posix()
            except ValueError:
                finding_path = _relative_path(path)
            findings.append(
                Finding(
                    id=finding_id,
                    category="architecture",
                    severity="high",
                    confidence="high",
                    message=violation.message,
                    path=finding_path,
                    line=violation.line,
                    detail=detail,
                    suggestion=(
                        "Remove the dependency or move the shared seam behind a lower-level API."
                        if violation.violation_kind in {"layer", "policy"}
                        else None
                    ),
                    source="layer-linter",
                )
            )
    return findings


_find_cli_findings = _repo_audit_compat_module._find_cli_findings
build_coverage_summary_report = _repo_audit_compat_module.build_coverage_summary_report
build_ai_gc_report = _repo_audit_compat_module.build_ai_gc_report
apply_ai_gc = _repo_audit_compat_module.apply_ai_gc
_ai_gc_report_findings = _repo_audit_compat_module._ai_gc_report_findings
_is_active_output_ai_gc_path = _repo_audit_compat_module._is_active_output_ai_gc_path
_filter_ai_gc_report_for_output_dir = _repo_audit_compat_module._filter_ai_gc_report_for_output_dir
_filter_ai_gc_findings_for_output_dir = _repo_audit_compat_module._filter_ai_gc_findings_for_output_dir
CLI_CONSISTENCY_FILENAME = _repo_audit_compat_module.CLI_CONSISTENCY_FILENAME
CLI_CONSISTENCY_DOC_PATHS = _repo_audit_compat_module.CLI_CONSISTENCY_DOC_PATHS
_cli_consistency_doc_paths = _repo_audit_compat_module._cli_consistency_doc_paths
build_cli_consistency_report = _repo_audit_compat_module.build_cli_consistency_report
_find_logging_findings = _repo_audit_compat_module._find_logging_findings
_should_ignore_normalized_pipeline_finding = _repo_audit_compat_module._should_ignore_normalized_pipeline_finding
_build_python_source_scan_context = _repo_audit_compat_module._build_python_source_scan_context
_parse_coverage_findings = _repo_audit_compat_module._parse_coverage_findings
_find_public_readiness_findings = _repo_audit_compat_module._find_public_readiness_findings
_find_pipeline_findings = _repo_audit_compat_module._find_pipeline_findings
_dedupe_findings = _repo_audit_compat_module._dedupe_findings
_is_leak_finding = _repo_audit_compat_module._is_leak_finding
_structural_report_location_detail = _repo_audit_compat_module._structural_report_location_detail
_find_structural_report_findings = _repo_audit_compat_module._find_structural_report_findings


_build_repo_audit_scan_context = _repo_audit_check_runners_module._build_repo_audit_scan_context
_shared_text_line_findings = _repo_audit_check_runners_module._shared_text_line_findings
_with_shared_text_line_findings = _repo_audit_check_runners_module._with_shared_text_line_findings
_run_text_scan_check = _repo_audit_check_runners_module._run_text_scan_check
_run_documented_commands_check = _repo_audit_check_runners_module._run_documented_commands_check
_run_unused_config_keys_check = _repo_audit_check_runners_module._run_unused_config_keys_check
_run_architecture_check = _repo_audit_check_runners_module._run_architecture_check
_run_structural_report_check = _repo_audit_check_runners_module._run_structural_report_check
_run_cli_check = _repo_audit_check_runners_module._run_cli_check
_run_logging_check = _repo_audit_check_runners_module._run_logging_check
_run_ai_gc_check = _repo_audit_check_runners_module._run_ai_gc_check
_run_ignored_repo_paths_check = _repo_audit_check_runners_module._run_ignored_repo_paths_check
_run_coverage_check = _repo_audit_check_runners_module._run_coverage_check
_patch_doc_gardener_paths = _repo_audit_check_runners_module._patch_doc_gardener_paths
_run_harness_freshness_check = _repo_audit_check_runners_module._run_harness_freshness_check
_run_public_readiness_check = _repo_audit_check_runners_module._run_public_readiness_check


def __getattr__(name: str) -> Any:
    if name == "_ai_work_map_module":
        return _repo_audit_check_runners_module._ai_work_map_module
    if name in {"CLI_CONSISTENCY_SCHEMA_KIND", "CLI_CONSISTENCY_SCHEMA_VERSION"}:
        return getattr(_repo_audit_compat_module, name)
    raise AttributeError(name)


def audit_repository(
    output_dir: Path,
    *,
    profile: str,
    fail_on: str,
    include_generated: bool,
    leaks_only: bool,
    suspicious_identifiers: Iterable[str],
    skip_pipeline: bool,
    skip_vulture: bool,
    skip_bandit: bool,
    latest_output_dir: Path | None = None,
) -> dict[str, Any]:
    return _audit_orchestration_module.audit_repository(
        output_dir,
        profile=profile,
        fail_on=fail_on,
        include_generated=include_generated,
        leaks_only=leaks_only,
        suspicious_identifiers=suspicious_identifiers,
        skip_pipeline=skip_pipeline,
        skip_vulture=skip_vulture,
        skip_bandit=skip_bandit,
        latest_output_dir=latest_output_dir,
        repo_root=REPO_ROOT,
        pipeline_output_dirname=PIPELINE_OUTPUT_DIRNAME,
        sanitize_path_for_report_fn=lambda path: sanitize_path_for_report(path, repo_root=REPO_ROOT),
        progress_reporter_factory=ProgressReporter,
        recommended_command_fn=_recommended_command,
        default_corpus_manifest_dir_fn=_default_corpus_manifest_dir,
        pipeline_module=pipeline_module,
        find_pipeline_findings_fn=_find_pipeline_findings,
        collect_custom_findings_fn=collect_custom_findings,
        filter_ai_gc_findings_for_output_dir_fn=_filter_ai_gc_findings_for_output_dir,
        filter_ai_gc_report_for_output_dir_fn=_filter_ai_gc_report_for_output_dir,
        build_ai_gc_report_fn=build_ai_gc_report,
        dedupe_findings_fn=_dedupe_findings,
        is_leak_finding_fn=_is_leak_finding,
        severity_rank=SEVERITY_RANK,
        blocking_finding_count_fn=_blocking_finding_count,
        severity_counts_fn=_severity_counts,
        category_counts_fn=_category_counts,
        max_severity_fn=_max_severity,
        artifact_reports_map_fn=artifact_reports_map,
        audit_artifacts=AUDIT_ARTIFACTS,
        finding_collection_factory=FindingCollection,
        write_json_artifact_fn=write_json_artifact,
        ai_gc_report_filename=_ai_gc_module.AI_GC_REPORT_FILENAME,
        write_markdown_fn=_write_markdown,
        build_cli_consistency_report_fn=build_cli_consistency_report,
        write_audit_run_history_fn=_write_audit_run_history,
        mirror_latest_reports_fn=_mirror_latest_reports,
    )


def main(argv: list[str] | None = None) -> int:
    return _repo_audit_cli_module.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
