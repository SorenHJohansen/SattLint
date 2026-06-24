"""Owner module for repo-audit finding check implementations."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

import ast
import json
import re
import subprocess  # nosec B404 - audit intentionally executes trusted local developer tools
import sys
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

from sattlint import config as config_module
from sattlint.devtools import ai_work_map as _ai_work_map_module
from sattlint.devtools import audit_core as _audit_core_module
from sattlint.devtools import audit_orchestration as _audit_orchestration_module
from sattlint.devtools import doc_gardener as _doc_gardener_module
from sattlint.devtools import layer_linter as _layer_linter_module
from sattlint.repo_paths import repo_root_from

from . import repo_audit_compat as _repo_audit_compat_module
from . import repo_audit_shared as _repo_audit_shared_module

REPO_ROOT = repo_root_from(Path(__file__))
LOCAL_CI_PARITY_LINE_FINDING_IDS = _repo_audit_shared_module.LOCAL_CI_PARITY_LINE_FINDING_IDS
OVERSIZED_MODULE_LINE_LIMIT = _repo_audit_shared_module.OVERSIZED_MODULE_LINE_LIMIT
HARNESS_FRESHNESS_DOC_SCANNERS = _repo_audit_shared_module.HARNESS_FRESHNESS_DOC_SCANNERS
Finding = _repo_audit_shared_module.Finding
RepoAuditScanContext = _repo_audit_shared_module.RepoAuditScanContext

_read_text = _repo_audit_compat_module._read_text
_relative_path = _repo_audit_compat_module._relative_path
_iter_repo_text_entries = _repo_audit_compat_module._iter_repo_text_entries
_line_findings = _repo_audit_compat_module._line_findings
_collect_cli_metadata = _repo_audit_compat_module._collect_cli_metadata
_extract_documented_commands = _repo_audit_compat_module._extract_documented_commands
_find_documentation_command_gaps = _repo_audit_compat_module._find_documentation_command_gaps
_find_unused_config_keys = _repo_audit_compat_module._find_unused_config_keys
_build_local_import_graph = _repo_audit_compat_module._build_local_import_graph
_find_import_cycles = _repo_audit_compat_module._find_import_cycles
_find_hidden_local_dependency_findings = _repo_audit_compat_module._find_hidden_local_dependency_findings
_find_host_specific_test_assumptions = _repo_audit_compat_module._find_host_specific_test_assumptions
_find_ignored_repo_path_references = _repo_audit_compat_module._find_ignored_repo_path_references
_find_cli_findings = _repo_audit_compat_module._find_cli_findings
build_ai_gc_report = _repo_audit_compat_module.build_ai_gc_report
ai_gc_report_findings = _repo_audit_compat_module.ai_gc_report_findings
_find_logging_findings = _repo_audit_compat_module._find_logging_findings
_build_python_source_scan_context = _repo_audit_compat_module._build_python_source_scan_context
parse_coverage_findings = _repo_audit_compat_module.parse_coverage_findings
find_public_readiness_findings = _repo_audit_compat_module.find_public_readiness_findings
find_structural_report_findings = _repo_audit_compat_module.find_structural_report_findings


def run_local_ci_parity_check(context: RepoAuditScanContext) -> list[Finding]:
    findings = [
        finding for finding in _shared_text_line_findings(context) if finding.id in LOCAL_CI_PARITY_LINE_FINDING_IDS
    ]
    findings.extend(_find_hidden_local_dependency_findings(context.source_context, root=context.root))
    findings.extend(_find_hidden_local_dependency_findings(context.test_context, root=context.root))
    findings.extend(_find_hidden_local_dependency_findings(context.scripts_context, root=context.root))
    findings.extend(_find_host_specific_test_assumptions(context.test_context, root=context.root))
    return findings


_RATCHET_POLICY_PREFIX = "ratchet-policy:"
_RATCHET_POLICY_ERROR_PATH_RE = re.compile(r"(?P<path>(?:src|tests|docs|scripts)/[^:\s]+)")


def _ratchet_policy_command() -> list[str]:
    return [sys.executable, "scripts/check_ratchet_policy.py"]


def _normalize_ratchet_policy_errors(*, stdout: str, stderr: str) -> list[str]:
    errors: list[str] = []
    for raw_line in (*stderr.splitlines(), *stdout.splitlines()):
        line = raw_line.strip()
        if not line or line == "ratchet-policy: OK" or line == "ratchet-policy: blocked":
            continue
        if line.startswith("- "):
            errors.append(line[2:].strip())
            continue
        if line.startswith(_RATCHET_POLICY_PREFIX):
            errors.append(line.removeprefix(_RATCHET_POLICY_PREFIX).strip())
            continue
        errors.append(line)
    return errors


def _ratchet_policy_finding_id(message: str) -> str:
    lowered = message.casefold()
    if "coverage" in lowered:
        return "ratchet-policy-coverage"
    if "structural" in lowered:
        return "ratchet-policy-structural"
    if "typing" in lowered or "strict" in lowered:
        return "ratchet-policy-typing"
    return "ratchet-policy-blocked"


def _ratchet_policy_finding_category(message: str) -> str:
    if "coverage" in message.casefold():
        return "coverage"
    return "architecture"


def build_ratchet_policy_report(root: Path = REPO_ROOT) -> dict[str, Any]:
    result = subprocess.run(  # nosec B603 - fixed interpreter and repo-local script path
        _ratchet_policy_command(),
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    errors = _normalize_ratchet_policy_errors(stdout=result.stdout, stderr=result.stderr)
    return {
        "kind": "sattlint.ratchet_policy",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.audit.repo_audit",
        "command": _ratchet_policy_command(),
        "status": "pass" if result.returncode == 0 else "fail",
        "exit_code": result.returncode,
        "errors": errors,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _run_ratchet_policy_check(context: RepoAuditScanContext) -> list[Finding]:
    report = build_ratchet_policy_report(context.root)
    if report["status"] == "pass":
        return []

    findings: list[Finding] = []
    for message in report["errors"]:
        path_match = _RATCHET_POLICY_ERROR_PATH_RE.search(message)
        findings.append(
            Finding(
                id=_ratchet_policy_finding_id(message),
                category=_ratchet_policy_finding_category(message),
                severity="high",
                confidence="high",
                message=message,
                path=None if path_match is None else path_match.group("path"),
                source="ratchet-policy",
            )
        )
    return findings


def _scan_architecture_findings(
    source_root: Path,
    *,
    content_by_file: dict[Path, str] | None = None,
    ast_by_file: dict[Path, ast.AST] | None = None,
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
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
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


_find_architecture_findings = _scan_architecture_findings


def _build_repo_audit_scan_context(
    root: Path = REPO_ROOT,
    *,
    include_generated: bool = False,
    tracked_only: bool = False,
    suspicious_identifiers: Iterable[str] = (),
) -> RepoAuditScanContext:
    return _audit_core_module.build_repo_audit_scan_context(
        root,
        include_generated=include_generated,
        tracked_only=tracked_only,
        suspicious_identifiers=suspicious_identifiers,
        list_tracked_repo_paths_fn=_repo_audit_compat_module._list_tracked_repo_paths,
        build_python_source_scan_context_fn=_build_python_source_scan_context,
        collect_cli_metadata_fn=_collect_cli_metadata,
        extract_documented_commands_fn=_extract_documented_commands,
        context_factory=RepoAuditScanContext,
    )


def _shared_text_line_findings(context: RepoAuditScanContext) -> tuple[Finding, ...]:
    return _audit_core_module.shared_text_line_findings(
        context,
        iter_repo_text_entries_fn=_iter_repo_text_entries,
        line_findings_fn=_line_findings,
    )


def _with_shared_text_line_findings(context: RepoAuditScanContext) -> RepoAuditScanContext:
    if context.line_findings is not None:
        return context
    return replace(context, line_findings=_shared_text_line_findings(context))


def run_text_scan_check(context: RepoAuditScanContext) -> list[Finding]:
    return _audit_core_module.run_text_scan_check(
        context,
        shared_text_line_findings_fn=_shared_text_line_findings,
        local_ci_parity_line_finding_ids=LOCAL_CI_PARITY_LINE_FINDING_IDS,
    )


def run_documented_commands_check(context: RepoAuditScanContext) -> list[Finding]:
    return _audit_core_module.run_documented_commands_check(
        context,
        find_documentation_command_gaps_fn=_find_documentation_command_gaps,
    )


def run_unused_config_keys_check(context: RepoAuditScanContext) -> list[Finding]:
    return _audit_core_module.run_unused_config_keys_check(
        context,
        default_config_keys=config_module.DEFAULT_CONFIG.keys(),
        find_unused_config_keys_fn=_find_unused_config_keys,
    )


def run_architecture_check(context: RepoAuditScanContext) -> list[Finding]:
    return _audit_core_module.run_architecture_check(
        context,
        find_architecture_findings_fn=_find_architecture_findings,
    )


def run_structural_report_check(context: RepoAuditScanContext) -> list[Finding]:
    return find_structural_report_findings(context.root)


def run_cli_check(context: RepoAuditScanContext) -> list[Finding]:
    return _audit_core_module.run_cli_check(context, find_cli_findings_fn=_find_cli_findings)


def run_logging_check(context: RepoAuditScanContext) -> list[Finding]:
    return _audit_core_module.run_logging_check(
        context,
        find_logging_findings_fn=_find_logging_findings,
    )


def run_ai_gc_check(context: RepoAuditScanContext) -> list[Finding]:
    return _audit_core_module.run_ai_gc_check(
        context,
        build_ai_gc_report_fn=build_ai_gc_report,
        ai_gc_report_findings_fn=ai_gc_report_findings,
    )


def run_ignored_repo_paths_check(context: RepoAuditScanContext) -> list[Finding]:
    return _audit_core_module.run_ignored_repo_paths_check(
        context,
        find_ignored_repo_path_references_fn=_find_ignored_repo_path_references,
    )


def run_coverage_check(context: RepoAuditScanContext) -> list[Finding]:
    return _audit_core_module.run_coverage_check(
        context,
        parse_coverage_findings_fn=parse_coverage_findings,
    )


def _patch_doc_gardener_paths(root: Path) -> Any:
    return _repo_audit_compat_module.patch_doc_gardener_paths(
        root,
        doc_gardener_module=_doc_gardener_module,
    )


def _doc_gardener_finding_to_repo_audit(finding: Any) -> Finding:
    return _audit_orchestration_module.doc_gardener_finding_to_repo_audit(
        finding,
        finding_factory=Finding,
    )


def _ai_harness_issue_to_finding(issue: Any) -> Finding:
    return _audit_orchestration_module.ai_harness_issue_to_finding(
        issue,
        finding_factory=Finding,
    )


def run_harness_freshness_check(context: RepoAuditScanContext) -> list[Finding]:
    return _audit_orchestration_module.run_harness_freshness_check(
        context,
        verify_ai_harness_freshness_fn=_ai_work_map_module.verify_ai_harness_freshness,
        patch_doc_gardener_paths_fn=_patch_doc_gardener_paths,
        doc_gardener_module=_doc_gardener_module,
        ai_harness_issue_to_finding_fn=_ai_harness_issue_to_finding,
        doc_gardener_finding_to_repo_audit_fn=_doc_gardener_finding_to_repo_audit,
        harness_freshness_doc_scanners=HARNESS_FRESHNESS_DOC_SCANNERS,
    )


def run_public_readiness_check(context: RepoAuditScanContext) -> list[Finding]:
    return _audit_core_module.run_public_readiness_check(
        context,
        find_public_readiness_findings_fn=find_public_readiness_findings,
    )


__all__ = [
    "OVERSIZED_MODULE_LINE_LIMIT",
    "_build_local_import_graph",
    "_build_repo_audit_scan_context",
    "_doc_gardener_module",
    "_extract_documented_commands",
    "_find_architecture_findings",
    "_find_documentation_command_gaps",
    "_find_import_cycles",
    "_find_unused_config_keys",
    "_layer_linter_module",
    "_patch_doc_gardener_paths",
    "_run_ratchet_policy_check",
    "_shared_text_line_findings",
    "_with_shared_text_line_findings",
    "build_ratchet_policy_report",
    "run_ai_gc_check",
    "run_architecture_check",
    "run_cli_check",
    "run_coverage_check",
    "run_documented_commands_check",
    "run_harness_freshness_check",
    "run_ignored_repo_paths_check",
    "run_local_ci_parity_check",
    "run_logging_check",
    "run_public_readiness_check",
    "run_structural_report_check",
    "run_text_scan_check",
    "run_unused_config_keys_check",
]
