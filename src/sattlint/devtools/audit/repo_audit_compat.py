"""Compatibility helper surface extracted from repo_audit."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

import ast
import os
import shutil
import subprocess  # nosec B404 - audit intentionally executes trusted local developer tools
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from unittest.mock import patch

from sattlint import app as app_module
from sattlint.devtools import artifact_registry as _artifact_registry_module
from sattlint.devtools import audit_core as _audit_core_module
from sattlint.devtools import audit_core_discovery as _audit_core_discovery_module
from sattlint.devtools import leak_detection as _leak_detection_module
from sattlint.devtools import leak_detection_scan_paths as _leak_detection_scan_paths_module
from sattlint.devtools import ledger as _ledger_module
from sattlint.devtools.ai import ai_gc as _ai_gc_module
from sattlint.repo_paths import repo_root_from

from . import _repo_audit_reporting as _reporting_module
from . import repo_audit_shared as _shared

REPO_ROOT = repo_root_from(Path(__file__))
AUDIT_RUN_HISTORY_FILENAME = _artifact_registry_module.AUDIT_RUN_HISTORY_FILENAME
CLI_CONSISTENCY_FILENAME = _artifact_registry_module.CLI_CONSISTENCY_FILENAME
AUDIT_RUN_HISTORY_DIRNAME = _ledger_module.AUDIT_RUN_HISTORY_DIRNAME
TEXT_SUFFIXES = _shared.TEXT_SUFFIXES
SKIP_SELF_SCAN_PATHS = _shared.SKIP_SELF_SCAN_PATHS
IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PATHS = _shared.IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PATHS
IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PREFIXES = _shared.IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PREFIXES
PATH_INJECTION_CALL_PATHS = _shared.PATH_INJECTION_CALL_PATHS
LEAK_RELEVANT_CATEGORIES = _shared.LEAK_RELEVANT_CATEGORIES
LEAK_RELEVANT_FINDING_IDS = _shared.LEAK_RELEVANT_FINDING_IDS
ALLOWED_PRINT_MODULES = _shared.ALLOWED_PRINT_MODULES
ALLOWED_PRINT_PREFIXES = _shared.ALLOWED_PRINT_PREFIXES
PRINT_CALL_RE = _shared.PRINT_CALL_RE
OVERSIZED_MODULE_LINE_LIMIT = _shared.OVERSIZED_MODULE_LINE_LIMIT
DOCUMENTED_COMMAND_RE = _shared.DOCUMENTED_COMMAND_RE
IGNORED_NORMALIZED_PIPELINE_FINDINGS = _shared.IGNORED_NORMALIZED_PIPELINE_FINDINGS
Finding = _shared.Finding


DocumentedCommand = _shared.DocumentedCommand
PythonSourceScanContext = _shared.PythonSourceScanContext

_attribute_path = _shared.attribute_path
_repo_relative_path_from_expr = _shared.repo_relative_path_from_expr
_normalize_repo_relative_literal = _shared.normalize_repo_relative_literal
_is_ignored_repo_path_reference = _shared.is_ignored_repo_path_reference
CLI_CONSISTENCY_DOC_PATHS = (
    "README.md",
    "CONTRIBUTING.md",
    "docs/references/cli-commands.md",
    "docs/references/ai-agent-reference.md",
)


def __getattr__(name: str) -> Any:
    if name == "CLI_CONSISTENCY_SCHEMA_KIND":
        return _artifact_registry_module.CLI_CONSISTENCY_SCHEMA_KIND
    if name == "CLI_CONSISTENCY_SCHEMA_VERSION":
        return _artifact_registry_module.CLI_CONSISTENCY_SCHEMA_VERSION
    raise AttributeError(name)


def _relative_path(path: Path, root: Path = REPO_ROOT) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _source_segment_summary(text: str, node: ast.AST, *, max_length: int = 160) -> str | None:
    return _leak_detection_module.source_segment_summary(text, node, max_length=max_length)


def _contains_host_signal(node: ast.AST) -> bool:
    return _leak_detection_module.contains_host_signal(node, attribute_path=_attribute_path)


def _is_pythonpath_target(node: ast.AST) -> bool:
    return _leak_detection_module.is_pythonpath_target(node, attribute_path=_attribute_path)


def _find_marker_in_segment(segment: str) -> str | None:
    return _leak_detection_module.find_marker_in_segment(segment)


def _find_ignored_repo_path_references(
    context: PythonSourceScanContext,
    *,
    root: Path = REPO_ROOT,
    tracked_paths: tuple[str, ...] | None = None,
) -> list[Finding]:
    return _leak_detection_module.find_ignored_repo_path_references(
        context,
        root=root,
        tracked_paths=tracked_paths,
        relative_path=_relative_path,
        normalize_repo_relative_literal=_normalize_repo_relative_literal,
        repo_relative_path_from_expr=_repo_relative_path_from_expr,
        is_ignored_repo_path_reference=_is_ignored_repo_path_reference,
        finding_factory=Finding,
        skip_self_scan_paths=SKIP_SELF_SCAN_PATHS,
        allowlist_paths=IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PATHS,
        allowlist_prefixes=IGNORED_REPO_PATH_REFERENCE_ALLOWLIST_PREFIXES,
    )


def _find_hidden_local_dependency_findings(
    context: PythonSourceScanContext,
    *,
    root: Path = REPO_ROOT,
) -> list[Finding]:
    return _leak_detection_module.find_hidden_local_dependency_findings(
        context,
        root=root,
        relative_path=_relative_path,
        attribute_path=_attribute_path,
        is_pythonpath_target_fn=_is_pythonpath_target,
        find_marker_in_segment_fn=_find_marker_in_segment,
        finding_factory=Finding,
        skip_self_scan_paths=SKIP_SELF_SCAN_PATHS,
        path_injection_call_paths=PATH_INJECTION_CALL_PATHS,
    )


def _find_host_specific_test_assumptions(
    context: PythonSourceScanContext,
    *,
    root: Path = REPO_ROOT,
) -> list[Finding]:
    return _leak_detection_module.find_host_specific_test_assumptions(
        context,
        root=root,
        relative_path=_relative_path,
        contains_host_signal_fn=_contains_host_signal,
        source_segment_summary_fn=_source_segment_summary,
        finding_factory=Finding,
        skip_self_scan_paths=SKIP_SELF_SCAN_PATHS,
    )


def _write_text_artifact(path: Path, content: str) -> None:
    _ledger_module.write_text_artifact(
        path,
        content,
        replace_fn=os.replace,
        sleep_fn=time.sleep,
        temp_file_factory=tempfile.NamedTemporaryFile,
        range_factory=range,
    )


def _mirror_latest_reports(source_dir: Path, latest_output_dir: Path | None) -> None:
    _ledger_module.mirror_latest_reports(source_dir, latest_output_dir, copy2_fn=shutil.copy2)


def _sanitize_report_path(path: Path) -> str:
    return _ledger_module.sanitize_report_path(path, repo_root=REPO_ROOT)


def _build_audit_run_id() -> str:
    return _ledger_module.build_audit_run_id()


def _copy_audit_snapshot(source_dir: Path, snapshot_dir: Path) -> None:
    _ledger_module.copy_audit_snapshot(
        source_dir,
        snapshot_dir,
        history_dirname=AUDIT_RUN_HISTORY_DIRNAME,
        history_filename=AUDIT_RUN_HISTORY_FILENAME,
        copy2_fn=shutil.copy2,
    )


def _read_text(path: Path) -> str:
    return _leak_detection_scan_paths_module.read_text(path)


def _should_skip_dir(dirname: str) -> bool:
    return _leak_detection_scan_paths_module.should_skip_dir(dirname)


def _list_tracked_repo_paths(root: Path) -> tuple[str, ...] | None:
    return _leak_detection_scan_paths_module.list_tracked_repo_paths(
        root,
        git_which=shutil.which,
        run_command=subprocess.run,
    )


def _iter_repo_file_candidates(root: Path, *, include_generated: bool) -> Iterable[Path]:
    yield from _leak_detection_scan_paths_module.iter_repo_file_candidates(
        root,
        include_generated=include_generated,
        relative_path=_relative_path,
        should_skip_dir_fn=_should_skip_dir,
        text_suffixes=TEXT_SUFFIXES,
    )


def _iter_tracked_repo_file_candidates(root: Path, *, include_generated: bool) -> Iterable[Path]:
    yield from _leak_detection_scan_paths_module.iter_tracked_repo_file_candidates(
        root,
        include_generated=include_generated,
        list_tracked_repo_paths_fn=_list_tracked_repo_paths,
        should_skip_dir_fn=_should_skip_dir,
        text_suffixes=TEXT_SUFFIXES,
    )


def _iter_repo_text_files(root: Path, *, include_generated: bool) -> Iterable[Path]:
    yield from _leak_detection_scan_paths_module.iter_repo_text_files(
        root,
        include_generated=include_generated,
        iter_repo_file_candidates_fn=lambda current_root, generated: _iter_repo_file_candidates(
            current_root,
            include_generated=generated,
        ),
        read_text_fn=_read_text,
    )


def _iter_tracked_repo_text_files(root: Path, *, include_generated: bool) -> Iterable[Path]:
    yield from _leak_detection_scan_paths_module.iter_tracked_repo_text_files(
        root,
        include_generated=include_generated,
        iter_tracked_repo_file_candidates_fn=lambda current_root, generated: _iter_tracked_repo_file_candidates(
            current_root,
            include_generated=generated,
        ),
        read_text_fn=_read_text,
    )


def _iter_repo_text_entries(
    root: Path,
    *,
    include_generated: bool,
    tracked_only: bool,
) -> Iterable[tuple[Path, str]]:
    yield from _leak_detection_scan_paths_module.iter_repo_text_entries(
        root,
        include_generated=include_generated,
        tracked_only=tracked_only,
        iter_repo_file_candidates_fn=lambda current_root, generated: _iter_repo_file_candidates(
            current_root,
            include_generated=generated,
        ),
        iter_tracked_repo_file_candidates_fn=lambda current_root, generated: _iter_tracked_repo_file_candidates(
            current_root,
            include_generated=generated,
        ),
        read_text_fn=_read_text,
    )


def _redact_value(value: str) -> str:
    return _leak_detection_module.redact_value(value)


def _redact_email(value: str) -> str:
    return _leak_detection_module.redact_email(value)


def _severity_for_path(rel_path: str, default: str) -> str:
    return _leak_detection_module.severity_for_path(rel_path, default)


def _line_findings(
    path: Path,
    text: str,
    suspicious_identifiers: set[str],
    *,
    root: Path = REPO_ROOT,
) -> list[Finding]:
    return _leak_detection_module.line_findings(
        path,
        text,
        suspicious_identifiers,
        root=root,
        relative_path=_relative_path,
        finding_factory=Finding,
    )


def _load_pyproject(root: Path) -> dict[str, Any]:
    return _audit_core_discovery_module.load_pyproject(root)


def _extract_documented_commands(paths: Iterable[Path], *, root: Path = REPO_ROOT) -> list[DocumentedCommand]:
    return _audit_core_discovery_module.extract_documented_commands(
        paths,
        root=root,
        read_text_fn=_read_text,
        relative_path=_relative_path,
        documented_command_re=DOCUMENTED_COMMAND_RE,
        documented_command_factory=DocumentedCommand,
    )


def _collect_cli_metadata() -> tuple[set[str], set[str]]:
    return _audit_core_discovery_module.collect_cli_metadata(
        repo_root=REPO_ROOT,
        load_pyproject_fn=_load_pyproject,
        build_cli_parser=app_module.build_cli_parser,
    )


def _find_documentation_command_gaps(
    documented_commands: Iterable[DocumentedCommand],
    scripts: set[str],
    subcommands: set[str],
) -> list[Finding]:
    return _audit_core_discovery_module.find_documentation_command_gaps(
        documented_commands,
        scripts,
        subcommands,
        finding_factory=Finding,
    )


def _find_unused_config_keys(
    source_root: Path,
    default_keys: Iterable[str],
    *,
    content_by_file: dict[Path, str] | None = None,
) -> list[Finding]:
    return _audit_core_discovery_module.find_unused_config_keys(
        source_root,
        default_keys,
        read_text_fn=_read_text,
        finding_factory=Finding,
        content_by_file=content_by_file,
    )


def _module_name_from_path(path: Path, root: Path) -> str:
    return _audit_core_discovery_module.module_name_from_path(path, root)


def _resolve_import(module_name: str, imported: str | None, level: int) -> str | None:
    return _audit_core_discovery_module.resolve_import(module_name, imported, level)


def _build_local_import_graph(
    source_root: Path,
    *,
    content_by_file: dict[Path, str] | None = None,
    ast_by_file: dict[Path, ast.AST] | None = None,
) -> dict[str, set[str]]:
    return _audit_core_discovery_module.build_local_import_graph(
        source_root,
        read_text_fn=_read_text,
        content_by_file=content_by_file,
        ast_by_file=ast_by_file,
    )


def _find_import_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    return _audit_core_discovery_module.find_import_cycles(graph)


def _find_architecture_findings(
    source_root: Path,
    *,
    content_by_file: dict[Path, str] | None = None,
    ast_by_file: dict[Path, ast.AST] | None = None,
) -> list[Finding]:
    return _audit_core_module.find_architecture_findings(
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


def _find_cli_findings() -> list[Finding]:
    return _audit_core_module.find_cli_findings(
        build_cli_parser=app_module.build_cli_parser,
        finding_factory=Finding,
    )


def build_coverage_summary_report(root: Path) -> dict[str, Any]:
    return _reporting_module.build_coverage_summary_report(root)


def build_ai_gc_report(
    root: Path = REPO_ROOT,
    *,
    tracked_paths: Iterable[str] | None = None,
    stale_after_days: int = _ai_gc_module.DEFAULT_STALE_AFTER_DAYS,
    now_ts: float | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    return _reporting_module.build_ai_gc_report(
        root,
        tracked_paths=tracked_paths,
        stale_after_days=stale_after_days,
        now_ts=now_ts,
        apply=apply,
    )


def apply_ai_gc(
    root: Path = REPO_ROOT,
    *,
    output_dir: Path | None = None,
    tracked_paths: Iterable[str] | None = None,
    stale_after_days: int = _ai_gc_module.DEFAULT_STALE_AFTER_DAYS,
    now_ts: float | None = None,
) -> dict[str, Any]:
    return _reporting_module.apply_ai_gc(
        root,
        output_dir=output_dir,
        tracked_paths=tracked_paths,
        stale_after_days=stale_after_days,
        now_ts=now_ts,
    )


def ai_gc_report_findings(report: dict[str, Any]) -> list[Finding]:
    return _reporting_module.ai_gc_report_findings(report)


def is_active_output_ai_gc_path(path: str | None, *, output_dir_path: str | None) -> bool:
    return _reporting_module.is_active_output_ai_gc_path(path, output_dir_path=output_dir_path)


def filter_ai_gc_report_for_output_dir(report: dict[str, Any], *, output_dir_path: str | None) -> dict[str, Any]:
    return _reporting_module.filter_ai_gc_report_for_output_dir(report, output_dir_path=output_dir_path)


def filter_ai_gc_findings_for_output_dir(findings: list[Finding], *, output_dir_path: str | None) -> list[Finding]:
    return _reporting_module.filter_ai_gc_findings_for_output_dir(findings, output_dir_path=output_dir_path)


def cli_consistency_doc_paths(root: Path) -> list[Path]:
    return _reporting_module.cli_consistency_doc_paths(root)


def build_cli_consistency_report(*, root: Path = REPO_ROOT) -> dict[str, Any]:
    return _reporting_module.build_cli_consistency_report(root=root)


def _find_logging_findings(
    source_root: Path,
    *,
    content_by_file: dict[Path, str] | None = None,
) -> list[Finding]:
    return _audit_core_module.find_logging_findings(
        source_root,
        read_text_fn=_read_text,
        relative_path=lambda path: _relative_path(path),
        finding_factory=Finding,
        print_call_re=PRINT_CALL_RE,
        allowed_print_modules=ALLOWED_PRINT_MODULES,
        allowed_print_prefixes=ALLOWED_PRINT_PREFIXES,
        content_by_file=content_by_file,
    )


def _should_ignore_normalized_pipeline_finding(finding_id: str, path: str | None) -> bool:
    if path is None:
        return False
    return (finding_id, path) in IGNORED_NORMALIZED_PIPELINE_FINDINGS


def _build_python_source_scan_context(
    source_root: Path,
    *,
    root: Path = REPO_ROOT,
    tracked_paths: tuple[str, ...] | None = None,
) -> PythonSourceScanContext:
    return _leak_detection_scan_paths_module.build_python_source_scan_context(
        source_root,
        root=root,
        tracked_paths=tracked_paths,
        relative_path=_relative_path,
        read_text_fn=_read_text,
        context_factory=PythonSourceScanContext,
    )


def parse_coverage_findings(
    root: Path,
    *,
    tracked_paths: tuple[str, ...] | None = None,
) -> list[Finding]:
    return _reporting_module.parse_coverage_findings(root, tracked_paths=tracked_paths)


def find_public_readiness_findings(
    root: Path,
    *,
    tracked_paths: tuple[str, ...] | None = None,
) -> list[Finding]:
    return _reporting_module.find_public_readiness_findings(root, tracked_paths=tracked_paths)


def find_pipeline_findings(output_dir: Path) -> list[Finding]:
    return _reporting_module.find_pipeline_findings(output_dir)


def _dedupe_findings(findings: Iterable[Finding]) -> list[Finding]:
    return _audit_core_module.dedupe_findings(findings)


def _is_leak_finding(finding: Finding) -> bool:
    return _audit_core_module.is_leak_finding(
        finding,
        leak_relevant_categories=LEAK_RELEVANT_CATEGORIES,
        leak_relevant_finding_ids=LEAK_RELEVANT_FINDING_IDS,
    )


def structural_report_location_detail(finding: dict[str, Any]) -> tuple[str | None, str | None]:
    return _reporting_module.structural_report_location_detail(finding)


def find_structural_report_findings(root: Path = REPO_ROOT) -> list[Finding]:
    return _reporting_module.find_structural_report_findings(root)


def patch_doc_gardener_paths(root: Path, *, doc_gardener_module: Any):
    return patch.multiple(
        doc_gardener_module,
        REPO_ROOT=root,
        DOCS_DIR=root / "docs",
        AGENTS_MD=root / "AGENTS.md",
        QUALITY_SCORE=root / "docs" / "quality-score.md",
        TECH_DEBT=root / "docs" / "exec-plans" / "tech-debt-tracker.md",
        CURRENT_WORK=root / ".github" / "coordination" / "current_work_lock.json",
        CURRENT_WORK_TEMPLATE=root / ".github" / "coordination" / "current-work.template.md",
        AI_FIRST_PLAN=root / "docs" / "exec-plans" / "active" / "ai-first-repo-hardening.md",
        AI_FIRST_DEBT=root / "docs" / "exec-plans" / "tech-debt-tracker.md",
    )
