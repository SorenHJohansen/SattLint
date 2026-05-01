"""Helpers for exporting normalized finding collections from tool reports."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sattlint.contracts import FindingCollection, FindingLocation, FindingRecord
from sattlint.path_sanitizer import sanitize_path_for_report

_PYTEST_TRACEBACK_LOCATION_RE = re.compile(r"(?P<path>(?:[A-Za-z]:)?[^:\n]+?\.(?:py|s|x|l|z)):(?P<line>\d+)")


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


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pytest_failure_location(detail: str | None, *, repo_root: Path) -> tuple[str | None, int | None]:
    if not detail:
        return None, None
    match = _PYTEST_TRACEBACK_LOCATION_RE.search(detail)
    if match is None:
        return None, None
    return _sanitize_path(match.group("path"), repo_root=repo_root), _int_or_none(match.group("line"))


def _pytest_nodeid(testcase: dict[str, Any], *, sanitized_file: str | None) -> str | None:
    explicit = str(testcase.get("nodeid") or "").strip()
    if explicit:
        return explicit
    test_name = str(testcase.get("name") or "").strip()
    if sanitized_file and test_name:
        return f"{sanitized_file}::{test_name}"
    class_name = str(testcase.get("classname") or "").strip()
    if class_name and test_name:
        return f"{class_name}::{test_name}"
    return None


def _build_ruff_findings(
    findings: list[dict[str, Any]],
    *,
    repo_root: Path,
) -> list[FindingRecord]:
    records: list[FindingRecord] = []
    for entry in findings:
        location = entry.get("location") or {}
        code = str(entry.get("code") or "unknown").lower()
        path = _sanitize_path(entry.get("filename"), repo_root=repo_root)
        command = f"ruff check {path}" if path else "ruff check src tests"
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
                    path=path,
                    line=location.get("row"),
                    column=location.get("column"),
                ),
                owner_surface="python-style",
                minimal_reproducer=command,
                suggested_next_command=command,
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
        path = _sanitize_path(entry.get("file"), repo_root=repo_root)
        command = f"mypy {path}" if path else "mypy src tests"
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
                    path=path,
                    line=entry.get("line"),
                    column=entry.get("column"),
                ),
                owner_surface="python-types",
                minimal_reproducer=command,
                suggested_next_command=command,
                data={
                    "code": entry.get("code"),
                    "severity": entry.get("severity"),
                },
            )
        )
    return records


def _build_pyright_findings(
    findings: list[dict[str, Any]],
    *,
    repo_root: Path,
) -> list[FindingRecord]:
    records: list[FindingRecord] = []
    for entry in findings:
        severity = str(entry.get("severity") or "error").lower()
        rule = entry.get("rule") or ""
        code = str(entry.get("errorCode") or rule or "unknown")
        range_data = entry.get("range", {})
        start = range_data.get("start", {})
        path = _sanitize_path(entry.get("file"), repo_root=repo_root)
        command = f"pyright {path}" if path else "pyright src tests"
        records.append(
            FindingRecord(
                id=f"pyright-{severity}-{code}",
                rule_id=f"pyright.{code}" if code else "pyright",
                category="typing",
                severity=_normalized_severity(severity, default="medium"),
                confidence="high",
                message=str(entry.get("message") or "Pyright reported a typing issue."),
                source="pyright",
                analyzer="pyright",
                artifact="findings",
                location=FindingLocation(
                    path=path,
                    line=start.get("line") if start else entry.get("line"),
                    column=start.get("character") if start else entry.get("column"),
                ),
                owner_surface="python-types",
                minimal_reproducer=command,
                suggested_next_command=command,
                data={
                    "code": code,
                    "severity": severity,
                    "rule": rule,
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
        path = _sanitize_path(entry.get("file"), repo_root=repo_root)
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
                    path=path,
                    line=entry.get("line"),
                ),
                owner_surface="dead-code",
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
        path = _sanitize_path(entry.get("filename"), repo_root=repo_root)
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
                    path=path,
                    line=entry.get("line_number"),
                ),
                owner_surface="security",
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
                owner_surface="architecture",
                data=data,
            )
        )
    return records


def _build_pytest_findings(pytest_report: dict[str, Any], *, repo_root: Path) -> list[FindingRecord]:
    summary = pytest_report.get("summary") or {}
    failures = int(summary.get("failures", 0))
    errors = int(summary.get("errors", 0))
    failed_testcases = [
        testcase for testcase in pytest_report.get("testcases", []) if testcase.get("outcome") in {"failed", "error"}
    ]
    if failed_testcases:
        records: list[FindingRecord] = []
        for index, testcase in enumerate(failed_testcases, start=1):
            detail = str(testcase.get("detail") or "").strip() or None
            path = _sanitize_path(testcase.get("file"), repo_root=repo_root)
            line = _int_or_none(testcase.get("line"))
            if path is None or line is None:
                parsed_path, parsed_line = _pytest_failure_location(detail, repo_root=repo_root)
                path = path or parsed_path
                line = line if line is not None else parsed_line
            nodeid = _pytest_nodeid(testcase, sanitized_file=path)
            command = (
                f"python -m pytest {nodeid} -x -q --tb=short"
                if nodeid
                else f"python -m pytest {path} -x -q --tb=short"
                if path
                else "python -m pytest -x -q --tb=short"
            )
            outcome = "error" if testcase.get("outcome") == "error" else "failed"
            rule_id = "pytest.errors" if outcome == "error" else "pytest.failures"
            test_name = str(testcase.get("name") or nodeid or f"case-{index}")
            records.append(
                FindingRecord(
                    id=f"pytest-{outcome}-{index}",
                    rule_id=rule_id,
                    category="correctness",
                    severity="high",
                    confidence="high",
                    message=f"Pytest {outcome} in {test_name}.",
                    source="pytest",
                    analyzer="pytest",
                    artifact="findings",
                    location=FindingLocation(
                        path=path,
                        line=line,
                        symbol=nodeid or test_name,
                    ),
                    detail=detail,
                    owner_surface="python-tests",
                    minimal_reproducer=command,
                    suggested_next_command=command,
                    data={
                        "summary": summary,
                        "testcase": testcase,
                        "nodeid": nodeid,
                        "outcome": outcome,
                    },
                )
            )
        return records
    if not (failures or errors):
        return []
    command = "python -m pytest -x -q --tb=short"
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
            owner_surface="python-tests",
            minimal_reproducer=command,
            suggested_next_command=command,
            data={
                "summary": summary,
            },
        )
    ]


def build_pipeline_finding_collection(
    *,
    repo_root: Path,
    ruff_findings: list[dict[str, Any]],
    pyright_findings: list[dict[str, Any]],
    pytest_report: dict[str, Any],
    vulture_findings: list[dict[str, Any]],
    bandit_findings: list[dict[str, Any]],
    architecture_findings: list[dict[str, Any]],
) -> FindingCollection:
    records = [
        *_build_ruff_findings(ruff_findings, repo_root=repo_root),
        *_build_pyright_findings(pyright_findings, repo_root=repo_root),
        *_build_pytest_findings(pytest_report, repo_root=repo_root),
        *_build_vulture_findings(vulture_findings, repo_root=repo_root),
        *_build_bandit_findings(bandit_findings, repo_root=repo_root),
        *_build_architecture_findings(architecture_findings),
    ]
    return FindingCollection(tuple(records))


__all__ = ["build_pipeline_finding_collection"]
