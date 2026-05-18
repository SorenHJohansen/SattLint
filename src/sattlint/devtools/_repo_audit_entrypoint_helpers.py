"""Helper functions extracted from the repo audit entrypoints facade."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def _repo_audit_helpers_module() -> Any:
    from sattlint.devtools import repo_audit as repo_audit_module

    return repo_audit_module


def _normalize_repo_audit_finding_checks(
    selected_checks: Iterable[str] | None,
    *,
    supported_check_ids: Iterable[str],
) -> tuple[str, ...] | None:
    if selected_checks is None:
        return None
    supported = set(supported_check_ids)
    normalized: list[str] = []
    seen: set[str] = set()
    for check_id in selected_checks:
        normalized_id = str(check_id).strip()
        if not normalized_id:
            raise ValueError("At least one non-empty repo-audit finding check is required when selecting checks.")
        if normalized_id not in supported:
            supported_text = ", ".join(sorted(supported))
            raise ValueError(
                f"Unsupported repo-audit finding check '{normalized_id}'. Supported checks: {supported_text}."
            )
        if normalized_id in seen:
            continue
        seen.add(normalized_id)
        normalized.append(normalized_id)
    if not normalized:
        raise ValueError("At least one non-empty repo-audit finding check is required when selecting checks.")
    return tuple(normalized)


def _cli_consistency_findings(report: dict[str, Any]) -> list[Any]:
    repo_audit = _repo_audit_helpers_module()
    findings: list[Any] = []
    for entry in report.get("gaps", {}).get("undeclared_subcommands", []):
        findings.append(
            repo_audit.Finding(
                id="cli-consistency-undeclared-subcommand",
                category="feature-wiring",
                severity="medium",
                confidence="high",
                message=f"Documented CLI subcommand '{entry.get('subcommand')}' is not declared.",
                path=entry.get("referenced_in"),
                line=entry.get("line"),
                source="cli-consistency",
            )
        )
    for entry in report.get("gaps", {}).get("undeclared_scripts", []):
        findings.append(
            repo_audit.Finding(
                id="cli-consistency-undeclared-script",
                category="feature-wiring",
                severity="medium",
                confidence="high",
                message=f"Documented CLI script '{entry.get('script')}' is not declared.",
                path=entry.get("referenced_in"),
                line=entry.get("line"),
                source="cli-consistency",
            )
        )
    return findings


def _severity_counts(findings: Iterable[Any]) -> dict[str, int]:
    counts = Counter(finding.severity for finding in findings)
    return {severity: counts.get(severity, 0) for severity in ("critical", "high", "medium", "low")}


def _category_counts(findings: Iterable[Any]) -> dict[str, int]:
    counts = Counter(finding.category for finding in findings)
    return dict(sorted(counts.items()))


def _max_severity(findings: Iterable[Any]) -> str | None:
    repo_audit = _repo_audit_helpers_module()
    max_finding = max(findings, key=lambda item: repo_audit.SEVERITY_RANK[item.severity], default=None)
    return None if max_finding is None else max_finding.severity


def _should_fail(findings: Iterable[Any], threshold: str) -> bool:
    repo_audit = _repo_audit_helpers_module()
    minimum_rank = repo_audit.SEVERITY_RANK[threshold]
    return any(repo_audit.SEVERITY_RANK[finding.severity] >= minimum_rank for finding in findings)


def _blocking_finding_count(findings: Iterable[Any], threshold: str) -> int:
    repo_audit = _repo_audit_helpers_module()
    minimum_rank = repo_audit.SEVERITY_RANK[threshold]
    return sum(1 for finding in findings if repo_audit.SEVERITY_RANK[finding.severity] >= minimum_rank)


def _recommended_command(*, output_dir: str, profile: str, fail_on: str, leaks_only: bool) -> str:
    parts = ["sattlint-repo-audit"]
    if leaks_only:
        parts.append("--leaks-only")
    else:
        parts.extend(["--profile", profile])
    parts.extend(["--fail-on", fail_on, "--output-dir", output_dir])
    return " ".join(parts)


def _format_terminal_finding_path(path: str | None, line: int | None) -> str:
    if path is None:
        return ""
    if line is None:
        return f" [{path}]"
    return f" [{path}:{line}]"


def _print_terminal_findings(findings: Iterable[dict[str, Any]]) -> None:
    finding_list = list(findings)
    if not finding_list:
        return
    print("Detailed findings:")
    for finding in finding_list:
        path_suffix = _format_terminal_finding_path(finding.get("path"), finding.get("line"))
        print(
            f"- {finding['severity'].upper()} {finding['category']} {finding['id']}{path_suffix}: {finding['message']}"
        )
        detail = finding.get("detail")
        if detail:
            print(f"  detail: {detail}")
        suggestion = finding.get("suggestion")
        if suggestion:
            print(f"  suggestion: {suggestion}")


def _print_cli_summary(status_report: dict[str, Any]) -> None:
    print(f"Audit profile: {status_report['profile']}")
    print(f"Overall status: {status_report['overall_status']}")
    findings_schema = status_report.get("findings_schema")
    if findings_schema:
        print(
            f"Findings schema: {findings_schema.get('kind', 'unknown')} v{findings_schema.get('schema_version', '?')}"
        )
    print(
        "Findings: "
        f"{status_report['finding_count']} total, "
        f"{status_report['blocking_finding_count']} blocking at fail-on {status_report['fail_on']}"
    )
    print(f"Status report: {status_report['status_report']}")
    print(f"Summary report: {status_report['summary_report']}")
    latest_status_report = status_report.get("latest_status_report")
    latest_summary_report = status_report.get("latest_summary_report")
    if latest_status_report and latest_summary_report:
        print(f"Latest status report: {latest_status_report}")
        print(f"Latest summary report: {latest_summary_report}")
    _print_terminal_findings(status_report.get("findings", ()))


def _default_corpus_manifest_dir() -> Path | None:
    from sattlint.devtools import pipeline as pipeline_module

    manifest_dir = pipeline_module.DEFAULT_CORPUS_MANIFEST_DIR.resolve()
    if not manifest_dir.exists():
        return None
    if not any(manifest_dir.rglob("*.json")):
        return None
    return manifest_dir
