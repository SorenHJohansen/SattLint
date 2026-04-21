"""Helpers for exporting normalized finding collections from tool reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sattlint.contracts import FindingCollection, FindingLocation, FindingRecord
from sattlint.path_sanitizer import sanitize_path_for_report


def _sanitize_path(value: Any, *, repo_root: Path) -> str | None:
    if value in (None, ""):
        return None
    return sanitize_path_for_report(value, repo_root=repo_root)


def _ruff_severity(code: str) -> str:
    normalized = code.upper()
    if normalized.startswith("F") or normalized.startswith("E9"):
        return "high"
    if normalized.startswith(("E", "B", "UP", "SIM")):
        return "medium"
    return "low"


def _vulture_confidence(confidence: Any) -> str:
    try:
        numeric = int(confidence)
    except (TypeError, ValueError):
        return "medium"
    if numeric >= 90:
        return "high"
    if numeric >= 80:
        return "medium"
    return "low"


def _normalized_severity(value: Any, *, default: str) -> str:
    normalized = str(value or default).lower()
    if normalized in {"critical", "high", "medium", "low"}:
        return normalized
    if normalized == "error":
        return "high"
    if normalized == "warning":
        return "medium"
    if normalized == "note":
        return "low"
    return default


def _build_ruff_findings(
    findings: list[dict[str, Any]],
    *,
    repo_root: Path,
) -> list[FindingRecord]:
    records: list[FindingRecord] = []
    for entry in findings:
        location = entry.get("location") or {}
        code = str(entry.get("code") or "unknown").lower()
        records.append(
            FindingRecord(
                id=f"ruff-{code}",
                rule_id=f"ruff.{code}",
                category="style",
                severity=_ruff_severity(code),
                confidence="high",
                message=str(entry.get("message") or "Ruff reported a lint issue."),
                source="ruff",
                analyzer="ruff",
                artifact="findings",
                location=FindingLocation(
                    path=_sanitize_path(entry.get("filename"), repo_root=repo_root),
                    line=location.get("row"),
                    column=location.get("column"),
                ),
                data={
                    "code": entry.get("code"),
                    "fix": entry.get("fix"),
                    "url": entry.get("url"),
                },
            )
        )
    return records


def _build_mypy_findings(
    findings: list[dict[str, Any]],
    *,
    repo_root: Path,
) -> list[FindingRecord]:
    records: list[FindingRecord] = []
    for entry in findings:
        severity = str(entry.get("severity") or "unknown").lower()
        code = str(entry.get("code") or severity or "unknown").lower()
        records.append(
            FindingRecord(
                id=f"mypy-{severity}-{code}",
                rule_id=f"mypy.{severity}.{code}",
                category="typing",
                severity=_normalized_severity(severity, default="medium"),
                confidence="high",
                message=str(entry.get("message") or "Mypy reported a typing issue."),
                source="mypy",
                analyzer="mypy",
                artifact="findings",
                location=FindingLocation(
                    path=_sanitize_path(entry.get("file"), repo_root=repo_root),
                    line=entry.get("line"),
                    column=entry.get("column"),
                ),
                data={
                    "code": entry.get("code"),
                    "severity": entry.get("severity"),
                },
            )
        )
    return records


def _build_vulture_findings(
    findings: list[dict[str, Any]],
    *,
    repo_root: Path,
) -> list[FindingRecord]:
    records: list[FindingRecord] = []
    for entry in findings:
        records.append(
            FindingRecord(
                id="vulture-dead-code",
                rule_id="vulture.dead-code",
                category="dead-code",
                severity="medium",
                confidence=_vulture_confidence(entry.get("confidence")),
                message=str(entry.get("message") or "Potential dead code found."),
                source="vulture",
                analyzer="vulture",
                artifact="findings",
                location=FindingLocation(
                    path=_sanitize_path(entry.get("file"), repo_root=repo_root),
                    line=entry.get("line"),
                ),
                data={
                    "confidence_percent": entry.get("confidence"),
                },
            )
        )
    return records


def _build_bandit_findings(
    findings: list[dict[str, Any]],
    *,
    repo_root: Path,
) -> list[FindingRecord]:
    records: list[FindingRecord] = []
    for entry in findings:
        test_id = str(entry.get("test_id") or "finding").lower()
        records.append(
            FindingRecord(
                id=f"bandit-{test_id}",
                rule_id=f"bandit.{test_id}",
                category="security",
                severity=_normalized_severity(entry.get("issue_severity"), default="medium"),
                confidence=_normalized_severity(entry.get("issue_confidence"), default="medium"),
                message=str(entry.get("issue_text") or "Bandit reported a security issue."),
                source="bandit",
                analyzer="bandit",
                artifact="findings",
                location=FindingLocation(
                    path=_sanitize_path(entry.get("filename"), repo_root=repo_root),
                    line=entry.get("line_number"),
                ),
                data={
                    "test_id": entry.get("test_id"),
                    "test_name": entry.get("test_name"),
                    "issue_cwe": entry.get("issue_cwe"),
                },
            )
        )
    return records


def _build_architecture_findings(findings: list[dict[str, Any]]) -> list[FindingRecord]:
    records: list[FindingRecord] = []
    for entry in findings:
        data = {key: value for key, value in entry.items() if key not in {"id", "severity", "message"}}
        records.append(
            FindingRecord(
                id=str(entry.get("id") or "architecture-finding"),
                rule_id=str(entry.get("id") or "architecture-finding"),
                category="architecture",
                severity=_normalized_severity(entry.get("severity"), default="medium"),
                confidence="high",
                message=str(entry.get("message") or "Architecture report finding."),
                source="pipeline",
                analyzer="architecture",
                artifact="findings",
                data=data,
            )
        )
    return records


def _build_pytest_findings(pytest_report: dict[str, Any]) -> list[FindingRecord]:
    summary = pytest_report.get("summary") or {}
    failures = int(summary.get("failures", 0))
    errors = int(summary.get("errors", 0))
    if not (failures or errors):
        return []
    return [
        FindingRecord(
            id="pytest-failures",
            rule_id="pytest.failures",
            category="correctness",
            severity="high",
            confidence="high",
            message="Pytest reported failing or erroring tests.",
            source="pytest",
            analyzer="pytest",
            artifact="findings",
            detail=f"failures={failures}, errors={errors}",
            data={
                "summary": summary,
            },
        )
    ]


def build_pipeline_finding_collection(
    *,
    repo_root: Path,
    ruff_findings: list[dict[str, Any]],
    mypy_findings: list[dict[str, Any]],
    pytest_report: dict[str, Any],
    vulture_findings: list[dict[str, Any]],
    bandit_findings: list[dict[str, Any]],
    architecture_findings: list[dict[str, Any]],
) -> FindingCollection:
    records = [
        *_build_ruff_findings(ruff_findings, repo_root=repo_root),
        *_build_mypy_findings(mypy_findings, repo_root=repo_root),
        *_build_pytest_findings(pytest_report),
        *_build_vulture_findings(vulture_findings, repo_root=repo_root),
        *_build_bandit_findings(bandit_findings, repo_root=repo_root),
        *_build_architecture_findings(architecture_findings),
    ]
    return FindingCollection(tuple(records))


__all__ = ["build_pipeline_finding_collection"]
