"""Repo-audit reporting helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from sattlint.devtools import _portable_command_text as _portable_command_text_module
from sattlint.devtools import coverage_reports as _coverage_reports_module
from sattlint.devtools._repo_audit_ai_gc import (
    _ai_gc_report_findings,
    _filter_ai_gc_findings_for_output_dir,
    _filter_ai_gc_report_for_output_dir,
    _is_active_output_ai_gc_path,
)
from sattlint.devtools._repo_audit_public_readiness import _find_public_readiness_findings
from sattlint.devtools.json_helpers import json_mapping as _json_mapping
from sattlint.devtools.pipeline_artifacts import write_json_artifact


def _repo_audit_reporting_module() -> Any:
    from sattlint.devtools import repo_audit as repo_audit_module  # noqa: PLC0415

    return repo_audit_module


def build_coverage_summary_report(root: Path) -> dict[str, Any]:
    return _coverage_reports_module.build_coverage_summary_report(root)


def _load_json_payload(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _normalize_pipeline_finding_path(path: object) -> str | None:
    if not isinstance(path, str):
        return None
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized or None


def _parse_coverage_findings(
    root: Path,
    *,
    tracked_paths: tuple[str, ...] | None = None,
) -> list[Any]:
    repo_audit = _repo_audit_reporting_module()
    coverage_path = root / "coverage.xml"
    if tracked_paths is not None and "coverage.xml" not in tracked_paths:
        return []
    if not coverage_path.exists():
        return []

    findings: list[Any] = []
    try:
        coverage_xml = coverage_path.read_text(encoding="utf-8")
        root_xml = _coverage_reports_module.ElementTree.fromstring(coverage_xml)
    except (OSError, UnicodeDecodeError, _coverage_reports_module.ElementTree.ParseError):
        return []
    for class_node in root_xml.findall(".//class"):
        filename = class_node.attrib.get("filename", "")
        line_rate = float(class_node.attrib.get("line-rate", "0"))
        if not filename.startswith("src/"):
            continue
        severity = None
        if line_rate < 0.10:
            severity = "high"
        elif line_rate < 0.40:
            severity = "medium"
        elif line_rate < 0.60:
            severity = "low"
        if severity is None:
            continue
        findings.append(
            repo_audit.Finding(
                id="low-test-coverage",
                category="test-coverage",
                severity=severity,
                confidence="high",
                message="Source module has low test coverage.",
                path=filename,
                detail=f"line-rate={line_rate:.0%}",
                suggestion="Add targeted tests for this module or reduce dead code within it.",
                source="coverage.xml",
            )
        )
    return findings


def build_ai_gc_report(
    root: Path,
    *,
    tracked_paths: Iterable[str] | None = None,
    stale_after_days: int,
    now_ts: float | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    repo_audit = _repo_audit_reporting_module()
    return repo_audit._ai_gc_module.build_ai_gc_report(
        root,
        tracked_paths=tracked_paths,
        stale_after_days=stale_after_days,
        now_ts=now_ts,
        apply=apply,
    )


def apply_ai_gc(
    root: Path,
    *,
    output_dir: Path | None = None,
    tracked_paths: Iterable[str] | None = None,
    stale_after_days: int,
    now_ts: float | None = None,
) -> dict[str, Any]:
    repo_audit = _repo_audit_reporting_module()
    report = build_ai_gc_report(
        root,
        tracked_paths=tracked_paths,
        stale_after_days=stale_after_days,
        now_ts=now_ts,
        apply=True,
    )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json_artifact(output_dir / repo_audit._ai_gc_module.AI_GC_REPORT_FILENAME, report)
    return report


def _cli_consistency_doc_paths(root: Path) -> list[Path]:
    repo_audit = _repo_audit_reporting_module()
    doc_paths: list[Path] = []
    for rel_path in repo_audit.CLI_CONSISTENCY_DOC_PATHS:
        path = root / rel_path
        if path.exists():
            doc_paths.append(path)
    return doc_paths


_REQUIRED_VSCODE_TASKS = (
    {
        "label": "Quality: Pre-push Gate",
        "command": _portable_command_text_module.repo_audit_command(
            "--profile",
            "full",
            "--output-dir",
            "artifacts/audit",
        ),
    },
    {
        "label": "Quality: AI Drift Check",
        "command": _portable_command_text_module.repo_audit_command(
            "--profile",
            "full",
            "--check-my-changes",
            "--output-dir",
            "artifacts/audit",
        ),
    },
)


def _line_number_for_literal(text: str, literal: str) -> int | None:
    index = text.find(literal)
    if index < 0:
        return None
    return text.count("\n", 0, index) + 1


def _normalize_vscode_task_command(command: object, args: object) -> str | None:
    if not isinstance(command, str):
        return None
    normalized_command = command.strip().replace("\\", "/")
    if not normalized_command:
        return None

    command_name = normalized_command.rsplit("/", 1)[-1].casefold()
    parts = ["python" if command_name in {"python", "python3", "python.exe"} else normalized_command]
    if isinstance(args, list):
        for arg in cast(list[object], args):
            if isinstance(arg, str) and arg.strip():
                parts.append(arg.strip().replace("\\", "/"))
    return " ".join(parts)


def _string_key_mapping(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    mapping: dict[str, object] = {}
    for key, item in cast(dict[object, object], value).items():
        if isinstance(key, str):
            mapping[key] = item
    return mapping


def _build_required_vscode_task_gaps(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tasks_path = root / ".vscode" / "tasks.json"
    rel_path = ".vscode/tasks.json"
    missing_tasks: list[dict[str, Any]] = []
    mismatched_tasks: list[dict[str, Any]] = []
    try:
        text = tasks_path.read_text(encoding="utf-8")
        payload = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        text = ""
        payload = None

    payload_mapping = _string_key_mapping(payload)
    task_entries = payload_mapping.get("tasks") if payload_mapping is not None else None
    tasks_by_label: dict[str, dict[str, object]] = {}
    if isinstance(task_entries, list):
        for task_entry in cast(list[object], task_entries):
            task_mapping = _string_key_mapping(task_entry)
            if task_mapping is None:
                continue
            label_value = task_mapping.get("label")
            if isinstance(label_value, str):
                tasks_by_label[label_value] = task_mapping

    for required_task in _REQUIRED_VSCODE_TASKS:
        label = required_task["label"]
        line = _line_number_for_literal(text, f'"label": "{label}"') if text else None
        task = tasks_by_label.get(label)
        if task is None:
            missing_tasks.append(
                {
                    "label": label,
                    "referenced_in": rel_path,
                    "line": line,
                    "expected_command": required_task["command"],
                }
            )
            continue
        actual_command = _normalize_vscode_task_command(task.get("command"), task.get("args"))
        if actual_command != required_task["command"]:
            mismatched_tasks.append(
                {
                    "label": label,
                    "referenced_in": rel_path,
                    "line": line,
                    "expected_command": required_task["command"],
                    "actual_command": actual_command,
                }
            )
    return missing_tasks, mismatched_tasks


def build_cli_consistency_report(*, root: Path) -> dict[str, Any]:
    repo_audit = _repo_audit_reporting_module()
    scripts, subcommands = repo_audit._collect_cli_metadata()
    doc_paths = _cli_consistency_doc_paths(root)
    documented_commands = repo_audit._extract_documented_commands(doc_paths, root=root)
    missing_tasks, mismatched_tasks = _build_required_vscode_task_gaps(root)

    undeclared_subcommands: list[dict[str, Any]] = []
    undeclared_scripts: list[dict[str, Any]] = []
    for item in documented_commands:
        if item.command == "sattlint" and item.subcommand and item.subcommand not in subcommands:
            undeclared_subcommands.append(
                {
                    "subcommand": item.subcommand,
                    "referenced_in": item.path,
                    "line": item.line,
                }
            )
        if item.command.startswith("sattlint-") and item.command not in scripts:
            undeclared_scripts.append(
                {
                    "script": item.command,
                    "referenced_in": item.path,
                    "line": item.line,
                }
            )

    documented_subcommand_names = {
        item.subcommand for item in documented_commands if item.command == "sattlint" and item.subcommand
    }
    undocumented_subcommands = sorted(subcommands - documented_subcommand_names)

    documented_script_names = {item.command for item in documented_commands if item.command.startswith("sattlint-")}
    undocumented_scripts = sorted(scripts - documented_script_names)

    gap_count = len(undeclared_subcommands) + len(undeclared_scripts) + len(missing_tasks) + len(mismatched_tasks)
    return {
        "kind": repo_audit.CLI_CONSISTENCY_SCHEMA_KIND,
        "schema_version": repo_audit.CLI_CONSISTENCY_SCHEMA_VERSION,
        "generated_by": "sattlint.devtools.repo_audit",
        "declared": {
            "scripts": sorted(scripts),
            "subcommands": sorted(subcommands),
        },
        "gaps": {
            "undeclared_subcommands": undeclared_subcommands,
            "undeclared_scripts": undeclared_scripts,
            "undocumented_subcommands": undocumented_subcommands,
            "undocumented_scripts": undocumented_scripts,
            "missing_tasks": missing_tasks,
            "mismatched_tasks": mismatched_tasks,
        },
        "summary": {
            "declared_script_count": len(scripts),
            "declared_subcommand_count": len(subcommands),
            "undeclared_subcommand_count": len(undeclared_subcommands),
            "undeclared_script_count": len(undeclared_scripts),
            "undocumented_subcommand_count": len(undocumented_subcommands),
            "undocumented_script_count": len(undocumented_scripts),
            "missing_task_count": len(missing_tasks),
            "mismatched_task_count": len(mismatched_tasks),
            "gap_count": gap_count,
        },
        "status": "fail" if gap_count > 0 else "pass",
    }


def _structural_report_location_detail(finding: dict[str, Any]) -> tuple[str | None, str | None]:
    finding_id = finding["id"]
    if finding_id in {"structural-source-file-budget", "structural-test-file-budget"}:
        entries = finding.get("over_budget_files", [])
        if entries:
            first_entry = entries[0]
            return first_entry.get("path"), f"{first_entry.get('line_count')} lines"
    if finding_id == "structural-function-budget":
        entries = finding.get("over_budget_functions", [])
        if entries:
            first_entry = entries[0]
            return first_entry.get("path"), f"{first_entry.get('qualname')} spans {first_entry.get('line_span')} lines"
    if finding_id == "structural-class-budget":
        entries = finding.get("over_budget_classes", [])
        if entries:
            first_entry = entries[0]
            return first_entry.get(
                "path"
            ), f"{first_entry.get('qualname')} defines {first_entry.get('method_count')} methods"
    if finding_id == "structural-private-helper-duplication":
        entries = finding.get("repeated_private_names", [])
        if entries:
            first_entry = entries[0]
            first_path = next(iter(first_entry.get("paths", [])), None)
            return first_path, f"{first_entry.get('name')} repeats across {first_entry.get('file_count')} files"
    if finding_id == "structural-facade-private-boundary":
        entries = finding.get("private_entrypoints", [])
        if entries:
            first_entry = entries[0]
            return first_entry.get("path"), f"calls {first_entry.get('target')} at line {first_entry.get('line')}"
    if finding_id == "structural-budget-ratchet-regression":
        regressions = finding.get("regressions", [])
        if regressions:
            first_regression = regressions[0]
            return None, (
                f"{first_regression.get('metric')}: {first_regression.get('actual')} > "
                f"{first_regression.get('expected_max')}"
            )
    return None, None


def _find_structural_report_findings(root: Path | None = None) -> list[Any]:
    repo_audit = _repo_audit_reporting_module()
    from sattlint.devtools import structural_reports as structural_reports_module  # noqa: PLC0415

    report_root = repo_audit.REPO_ROOT if root is None else root
    architecture_report = structural_reports_module.collect_architecture_report(report_root)
    structural_findings: list[Any] = []
    for finding in architecture_report.get("findings", []):
        finding_id = finding.get("id")
        if not isinstance(finding_id, str) or not finding_id.startswith("structural-"):
            continue
        if finding_id in repo_audit.STRUCTURAL_DEBT_FINDING_IDS:
            continue
        path, detail = _structural_report_location_detail(finding)
        structural_findings.append(
            repo_audit.Finding(
                id=finding_id,
                category="architecture",
                severity=str(finding.get("severity", "medium")),
                confidence="high",
                message=str(finding.get("message", "Structural report finding.")),
                path=path,
                detail=detail,
                source="structural-reports",
            )
        )
    return structural_findings


def _find_pipeline_findings(output_dir: Path) -> list[Any]:  # noqa: PLR0915
    repo_audit = _repo_audit_reporting_module()
    findings_path = output_dir / "findings.json"
    if findings_path.exists():
        payload_obj = _load_json_payload(findings_path)
        if payload_obj is not None:
            payload = _json_mapping(payload_obj) or {}
            normalized_findings: list[Any] = []
            finding_entries = payload.get("findings")
            for entry_obj in cast(list[object], finding_entries) if isinstance(finding_entries, list) else []:
                entry = _json_mapping(entry_obj)
                if entry is None:
                    continue
                finding_id = str(entry.get("id") or entry.get("rule_id") or "pipeline-finding")
                if finding_id in repo_audit.STRUCTURAL_DEBT_FINDING_IDS:
                    continue
                location = _json_mapping(entry.get("location")) or {}
                path = _normalize_pipeline_finding_path(location.get("path"))
                if repo_audit._should_ignore_normalized_pipeline_finding(finding_id, path):
                    continue
                normalized_findings.append(
                    repo_audit.Finding(
                        id=finding_id,
                        category=str(entry.get("category") or "unknown"),
                        severity=str(entry.get("severity") or "medium"),
                        confidence=str(entry.get("confidence") or "medium"),
                        message=str(entry.get("message") or "Pipeline reported a finding."),
                        path=path,
                        line=location.get("line"),
                        detail=entry.get("detail"),
                        suggestion=entry.get("suggestion"),
                        source=str(entry.get("source") or "pipeline"),
                    )
                )
            return normalized_findings

    findings: list[Any] = []
    vulture_path = output_dir / "vulture.json"
    if vulture_path.exists():
        payload = _json_mapping(_load_json_payload(vulture_path)) or {}
        finding_entries = payload.get("findings")
        for entry_obj in cast(list[object], finding_entries) if isinstance(finding_entries, list) else []:
            entry = _json_mapping(entry_obj)
            if entry is None:
                continue
            findings.append(
                repo_audit.Finding(
                    id="vulture-dead-code",
                    category="dead-code",
                    severity="medium",
                    confidence="medium",
                    message=entry.get("message", "Potential dead code found."),
                    path=entry.get("file"),
                    line=entry.get("line"),
                    source="vulture",
                )
            )

    bandit_path = output_dir / "bandit.json"
    if bandit_path.exists():
        payload = _json_mapping(_load_json_payload(bandit_path)) or {}
        for entry in cast(list[object], payload.get("findings")) if isinstance(payload.get("findings"), list) else []:
            entry_map = _json_mapping(entry)
            if entry_map is None:
                continue
            issue_severity = str(entry_map.get("issue_severity", "medium")).lower()
            filename = _normalize_pipeline_finding_path(entry_map.get("filename")) or ""
            issue_text = str(entry_map.get("issue_text", ""))
            if filename.replace("\\", "/").endswith("src/sattlint/cache.py") and "pickle" in issue_text.lower():
                issue_severity = "low"
            test_id = str(entry_map.get("test_id", "")).lower()
            finding_id = f"bandit-{test_id}" if test_id else "bandit-finding"
            if repo_audit._should_ignore_normalized_pipeline_finding(finding_id, filename or None):
                continue
            findings.append(
                repo_audit.Finding(
                    id=finding_id,
                    category="secrets-pii",
                    severity=issue_severity if issue_severity in repo_audit.SEVERITY_RANK else "medium",
                    confidence=str(entry_map.get("issue_confidence", "medium")).lower(),
                    message=issue_text or "Bandit reported a security issue.",
                    path=filename,
                    line=entry_map.get("line_number"),
                    source="bandit",
                )
            )

    pytest_path = output_dir / "pytest.json"
    if pytest_path.exists():
        payload = _json_mapping(_load_json_payload(pytest_path)) or {}
        summary = _json_mapping(payload.get("summary")) or {}
        failures = int(summary.get("failures", 0))
        errors = int(summary.get("errors", 0))
        if failures or errors:
            findings.append(
                repo_audit.Finding(
                    id="pytest-failures",
                    category="correctness",
                    severity="high",
                    confidence="high",
                    message="Pytest reported failing or erroring tests.",
                    detail=f"failures={failures}, errors={errors}",
                    source="pytest",
                )
            )
    return findings


__all__ = [
    "_ai_gc_report_findings",
    "_cli_consistency_doc_paths",
    "_filter_ai_gc_findings_for_output_dir",
    "_filter_ai_gc_report_for_output_dir",
    "_find_pipeline_findings",
    "_find_public_readiness_findings",
    "_find_structural_report_findings",
    "_is_active_output_ai_gc_path",
    "_normalize_pipeline_finding_path",
    "_parse_coverage_findings",
    "_structural_report_location_detail",
    "apply_ai_gc",
    "build_ai_gc_report",
    "build_cli_consistency_report",
    "build_coverage_summary_report",
]
