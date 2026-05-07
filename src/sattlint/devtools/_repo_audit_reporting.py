"""Repo-audit reporting helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sattlint.devtools import coverage_reports as _coverage_reports_module
from sattlint.devtools._repo_audit_ai_gc import (
    _ai_gc_report_findings,
    _filter_ai_gc_findings_for_output_dir,
    _filter_ai_gc_report_for_output_dir,
    _is_active_output_ai_gc_path,
)
from sattlint.devtools.pipeline_artifacts import write_json_artifact


def _repo_audit_module() -> Any:
    from sattlint.devtools import repo_audit as repo_audit_module

    return repo_audit_module


def build_coverage_summary_report(root: Path) -> dict[str, Any]:
    return _coverage_reports_module.build_coverage_summary_report(root)


def _parse_coverage_findings(
    root: Path,
    *,
    tracked_paths: tuple[str, ...] | None = None,
) -> list[Any]:
    repo_audit = _repo_audit_module()
    coverage_path = root / "coverage.xml"
    if tracked_paths is not None and "coverage.xml" not in tracked_paths:
        return []
    if not coverage_path.exists():
        return []

    findings: list[Any] = []
    root_xml = _coverage_reports_module.ElementTree.fromstring(coverage_path.read_text(encoding="utf-8"))
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
    repo_audit = _repo_audit_module()
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
    repo_audit = _repo_audit_module()
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
    repo_audit = _repo_audit_module()
    doc_paths: list[Path] = []
    for rel_path in repo_audit.CLI_CONSISTENCY_DOC_PATHS:
        path = root / rel_path
        if path.exists():
            doc_paths.append(path)
    return doc_paths


def build_cli_consistency_report(*, root: Path) -> dict[str, Any]:
    repo_audit = _repo_audit_module()
    scripts, subcommands = repo_audit._collect_cli_metadata()
    doc_paths = _cli_consistency_doc_paths(root)
    documented_commands = repo_audit._extract_documented_commands(doc_paths, root=root)

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

    gap_count = len(undeclared_subcommands) + len(undeclared_scripts)
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
        },
        "summary": {
            "declared_script_count": len(scripts),
            "declared_subcommand_count": len(subcommands),
            "undeclared_subcommand_count": len(undeclared_subcommands),
            "undeclared_script_count": len(undeclared_scripts),
            "undocumented_subcommand_count": len(undocumented_subcommands),
            "undocumented_script_count": len(undocumented_scripts),
            "gap_count": gap_count,
        },
        "status": "fail" if gap_count > 0 else "pass",
    }


def _find_public_readiness_findings(
    root: Path,
    *,
    tracked_paths: tuple[str, ...] | None = None,
) -> list[Any]:
    repo_audit = _repo_audit_module()
    findings: list[Any] = []
    tracked_path_set = None if tracked_paths is None else set(tracked_paths)
    required_files = ["README.md", "LICENSE", "CONTRIBUTING.md", ".gitignore"]
    for filename in required_files:
        exists = (root / filename).exists() if tracked_path_set is None else filename in tracked_path_set
        if not exists:
            findings.append(
                repo_audit.Finding(
                    id="missing-public-file",
                    category="public-readiness",
                    severity="high",
                    confidence="high",
                    message=f"Expected public-facing file '{filename}' is missing.",
                    suggestion="Add the missing file before publishing the repository.",
                )
            )

    pyproject = repo_audit._load_pyproject(root)
    urls = pyproject.get("project", {}).get("urls", {})
    if not urls:
        findings.append(
            repo_audit.Finding(
                id="missing-project-urls",
                category="public-readiness",
                severity="low",
                confidence="high",
                message="pyproject metadata does not declare project URLs.",
                path="pyproject.toml",
                suggestion="Add homepage, repository, and issue tracker URLs.",
            )
        )

    if tracked_path_set is None:
        workflow_dir = root / ".github" / "workflows"
        has_workflow = workflow_dir.exists() and any(workflow_dir.glob("*.y*ml"))
    else:
        has_workflow = any(
            rel_path.startswith(".github/workflows/") and rel_path.endswith((".yml", ".yaml"))
            for rel_path in tracked_path_set
        )
    if not has_workflow:
        findings.append(
            repo_audit.Finding(
                id="missing-ci-workflow",
                category="public-readiness",
                severity="medium",
                confidence="high",
                message="Repository does not define a CI workflow.",
                suggestion="Add an audit or test workflow so external contributors get immediate feedback.",
            )
        )

    tracked = list(tracked_paths or ())
    if not tracked and tracked_path_set is None:
        git_executable = repo_audit.shutil.which("git")
        completed = None
        if git_executable is not None:
            try:
                completed = repo_audit.subprocess.run(  # nosec B603 - fixed git command with controlled arguments
                    [git_executable, "ls-files", "artifacts", "build", "htmlcov", "coverage.xml"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError:
                completed = None
        if completed and completed.returncode == 0:
            tracked = [line.strip() for line in completed.stdout.splitlines() if line.strip()]

    if tracked:
        generated = [
            line
            for line in tracked
            if any(line == prefix or line.startswith(prefix) for prefix in repo_audit.GENERATED_PATH_PREFIXES)
        ]
        if generated:
            findings.append(
                repo_audit.Finding(
                    id="tracked-generated-artifacts",
                    category="public-readiness",
                    severity="high",
                    confidence="high",
                    message="Generated artifacts are tracked in git and may embed workstation-specific data.",
                    detail=", ".join(generated[:5]) + (" ..." if len(generated) > 5 else ""),
                    suggestion="Remove generated outputs from version control and consider history cleanup for already-published leaks.",
                    history_cleanup_recommended=True,
                )
            )

    tracked_top_level_entries = sorted(
        {
            rel_path.split("/", 1)[0]
            for rel_path in (
                tracked_paths if tracked_paths is not None else (repo_audit._list_tracked_repo_paths(root) or ())
            )
            if rel_path
        }
    )
    unexpected_root_entries = [
        entry for entry in tracked_top_level_entries if entry not in repo_audit.TOP_LEVEL_TRACKED_ENTRY_ALLOWLIST
    ]
    if unexpected_root_entries:
        findings.append(
            repo_audit.Finding(
                id="unexpected-tracked-root-entry",
                category="public-readiness",
                severity="medium",
                confidence="high",
                message="Repository root contains tracked helper or scratch entries outside the approved top-level layout.",
                detail=", ".join(unexpected_root_entries[:5]) + (" ..." if len(unexpected_root_entries) > 5 else ""),
                suggestion="Move reusable tooling under scripts/ or another owner directory, and delete one-off scratch files from the repo root.",
            )
        )
    return findings


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
    repo_audit = _repo_audit_module()
    from sattlint.devtools import structural_reports as structural_reports_module

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


def _find_pipeline_findings(output_dir: Path) -> list[Any]:
    repo_audit = _repo_audit_module()
    findings_path = output_dir / "findings.json"
    if findings_path.exists():
        payload = json.loads(findings_path.read_text(encoding="utf-8"))
        normalized_findings: list[Any] = []
        for entry in payload.get("findings", []):
            finding_id = str(entry.get("id") or entry.get("rule_id") or "pipeline-finding")
            if finding_id in repo_audit.STRUCTURAL_DEBT_FINDING_IDS:
                continue
            location = entry.get("location") or {}
            path = location.get("path")
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
        payload = json.loads(vulture_path.read_text(encoding="utf-8"))
        for entry in payload.get("findings", []):
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
        payload = json.loads(bandit_path.read_text(encoding="utf-8"))
        for entry in payload.get("findings", []):
            issue_severity = str(entry.get("issue_severity", "medium")).lower()
            filename = str(entry.get("filename", ""))
            issue_text = str(entry.get("issue_text", ""))
            if filename.replace("\\", "/").endswith("src/sattlint/cache.py") and "pickle" in issue_text.lower():
                issue_severity = "low"
            findings.append(
                repo_audit.Finding(
                    id="bandit-finding",
                    category="secrets-pii",
                    severity=issue_severity if issue_severity in repo_audit.SEVERITY_RANK else "medium",
                    confidence=str(entry.get("issue_confidence", "medium")).lower(),
                    message=issue_text or "Bandit reported a security issue.",
                    path=filename,
                    line=entry.get("line_number"),
                    source="bandit",
                )
            )

    pytest_path = output_dir / "pytest.json"
    if pytest_path.exists():
        payload = json.loads(pytest_path.read_text(encoding="utf-8"))
        summary = payload.get("summary", {})
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
    "_parse_coverage_findings",
    "_structural_report_location_detail",
    "apply_ai_gc",
    "build_ai_gc_report",
    "build_cli_consistency_report",
    "build_coverage_summary_report",
]
