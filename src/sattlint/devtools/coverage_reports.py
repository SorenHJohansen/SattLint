"""Shared coverage report builders used by repo audit and pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from defusedxml import ElementTree  # type: ignore[import-untyped]

COVERAGE_SUMMARY_SCHEMA_KIND = "sattlint.coverage_summary"
COVERAGE_SUMMARY_SCHEMA_VERSION = 1


def build_coverage_summary_report(root: Path) -> dict[str, Any]:
    """Build a machine-readable coverage summary from coverage.xml."""
    coverage_path = root / "coverage.xml"
    if not coverage_path.exists():
        return {
            "kind": COVERAGE_SUMMARY_SCHEMA_KIND,
            "schema_version": COVERAGE_SUMMARY_SCHEMA_VERSION,
            "skipped": True,
            "skip_reason": "coverage.xml not found",
            "modules": [],
            "findings": [],
            "summary": {
                "module_count": 0,
                "low_coverage_count": 0,
                "avg_line_rate": None,
            },
        }

    root_xml = ElementTree.fromstring(coverage_path.read_text(encoding="utf-8"))
    modules: list[dict[str, Any]] = []
    low_coverage: list[dict[str, Any]] = []
    line_rates: list[float] = []

    for class_node in root_xml.findall(".//class"):
        filename = class_node.attrib.get("filename", "")
        if not filename.startswith("src/"):
            continue
        line_rate = float(class_node.attrib.get("line-rate", "0"))
        lines_valid = int(class_node.attrib.get("lines-valid", "0"))
        lines_covered = int(class_node.attrib.get("lines-covered", "0") or round(line_rate * lines_valid))
        line_rates.append(line_rate)
        modules.append(
            {
                "path": filename,
                "line_rate": round(line_rate, 4),
                "lines_valid": lines_valid,
                "lines_covered": lines_covered,
            }
        )

        severity = None
        if line_rate < 0.10:
            severity = "high"
        elif line_rate < 0.40:
            severity = "medium"
        elif line_rate < 0.60:
            severity = "low"
        if severity is not None:
            low_coverage.append(
                {
                    "path": filename,
                    "line_rate": round(line_rate, 4),
                    "severity": severity,
                    "message": "Source module has low test coverage.",
                    "suggestion": "Add targeted tests for this module or reduce dead code within it.",
                }
            )

    avg_line_rate = round(sum(line_rates) / len(line_rates), 4) if line_rates else None
    return {
        "kind": COVERAGE_SUMMARY_SCHEMA_KIND,
        "schema_version": COVERAGE_SUMMARY_SCHEMA_VERSION,
        "skipped": False,
        "modules": sorted(modules, key=lambda module: module["path"]),
        "findings": sorted(low_coverage, key=lambda finding: (finding["severity"], finding["path"])),
        "summary": {
            "module_count": len(modules),
            "low_coverage_count": len(low_coverage),
            "avg_line_rate": avg_line_rate,
        },
    }


__all__ = [
    "COVERAGE_SUMMARY_SCHEMA_KIND",
    "COVERAGE_SUMMARY_SCHEMA_VERSION",
    "build_coverage_summary_report",
]