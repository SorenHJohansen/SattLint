"""SARIF 2.1.0 export for findings.

The document is a standard static-analysis result file: one run, one tool
driver, a rule entry per analyzer kind or rule, and one result per finding.
A finding without a source location is emitted without a ``locations`` array,
which SARIF treats as a document-level result. It is never given a synthetic
line or column.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ..__version__ import __version__
from ..application.findings import kind_human_label
from ._findings import FlatFinding

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
SARIF_VERSION = "2.1.0"

_LEVEL_BY_SEVERITY = {
    "error": "error",
    "warning": "warning",
    "info": "note",
}


def _rule_id(finding: FlatFinding) -> str:
    return finding.finding.rule_id or f"{finding.analyzer_key}.{finding.finding.kind}"


def _artifact_uri(path: str) -> str:
    """A SARIF artifact URI for a filesystem path, without inventing a scheme."""
    return Path(path).as_posix()


def _region(finding: FlatFinding) -> dict[str, object] | None:
    line = finding.finding.line
    if line is None or line < 1:
        return None
    region: dict[str, object] = {"startLine": line}
    column = finding.finding.column
    if column is not None and column > 0:
        region["startColumn"] = column
    end_line = finding.finding.end_line
    if end_line is not None and end_line >= line:
        region["endLine"] = end_line
    return region


def _location(finding: FlatFinding) -> list[dict[str, object]] | None:
    file = finding.finding.file
    region = _region(finding)
    if not file or region is None:
        return None
    return [
        {
            "physicalLocation": {
                "artifactLocation": {"uri": _artifact_uri(file)},
                "region": region,
            }
        }
    ]


def build_sarif(
    findings: Iterable[FlatFinding],
    *,
    run_id: str | None = None,
) -> dict[str, object]:
    """Build a SARIF 2.1.0 document for the selected findings."""
    rules: dict[str, dict[str, object]] = {}
    results: list[dict[str, object]] = []
    for finding in findings:
        rule_id = _rule_id(finding)
        level = _LEVEL_BY_SEVERITY.get(finding.severity, "warning")
        rules.setdefault(
            rule_id,
            {
                "id": rule_id,
                "name": kind_human_label(finding.finding.kind),
                "shortDescription": {"text": kind_human_label(finding.finding.kind)},
                "properties": {
                    "analyzer": finding.analyzer_key,
                    "kind": finding.finding.kind,
                    "severity": finding.severity,
                },
            },
        )
        result: dict[str, object] = {
            "ruleId": rule_id,
            "level": level,
            "message": {"text": finding.finding.message or kind_human_label(finding.finding.kind)},
            "properties": {
                "target": finding.target,
                "analyzer": finding.analyzer_key,
                "kind": finding.finding.kind,
                "severity": finding.severity,
                "module": finding.module,
                "occurrence_count": finding.occurrence_count,
            },
        }
        locations = _location(finding)
        if locations is not None:
            result["locations"] = locations
        results.append(result)

    driver: dict[str, object] = {
        "name": "SattLint",
        "version": __version__,
        "informationUri": "https://github.com/SorenHJohansen/SattLint",
        "rules": [rules[rule_id] for rule_id in sorted(rules)],
    }
    run: dict[str, object] = {
        "tool": {"driver": driver},
        "results": results,
    }
    if run_id:
        run["automationDetails"] = {"id": run_id}
    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [run],
    }


__all__ = ["SARIF_SCHEMA", "SARIF_VERSION", "build_sarif"]
