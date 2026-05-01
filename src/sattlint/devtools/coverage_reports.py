"""Shared coverage report builders used by repo audit and pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from defusedxml import ElementTree  # type: ignore[import-untyped]

from sattlint.path_sanitizer import sanitize_path_for_report

COVERAGE_RATCHET_PATH = Path("artifacts") / "analysis" / "coverage_ratchet.json"
COVERAGE_RATCHET_SCHEMA_KIND = "sattlint.coverage_ratchet"
COVERAGE_RATCHET_SCHEMA_VERSION = 1
COVERAGE_SUMMARY_SCHEMA_KIND = "sattlint.coverage_summary"
COVERAGE_SUMMARY_SCHEMA_VERSION = 1
COVERAGE_RATCHET_SETPOINTS = {"min_line_rate_basis_points": 10000}


def _normalize_coverage_filename(filename: str) -> str:
    normalized = filename.replace("\\", "/").lstrip("./")
    if not normalized:
        return ""
    if normalized.startswith(("src/", "tests/")):
        return normalized
    if normalized.startswith("/") or (len(normalized) > 1 and normalized[1] == ":"):
        return normalized
    return f"src/{normalized}"


def _load_coverage_ratchet(root: Path) -> dict[str, Any]:
    resolved_path = root / COVERAGE_RATCHET_PATH
    sanitized_path = sanitize_path_for_report(resolved_path, repo_root=root) or resolved_path.as_posix()
    if not resolved_path.exists():
        return {"status": "missing", "path": sanitized_path, "metrics": {}}

    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid",
            "path": sanitized_path,
            "metrics": {},
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

    metrics = payload.get("metrics")
    if not isinstance(metrics, dict) or any(not isinstance(value, int) for value in metrics.values()):
        return {
            "status": "invalid",
            "path": sanitized_path,
            "metrics": {},
            "error": "ratchet metrics must be a JSON object with integer values",
            "error_type": "ValueError",
        }

    return {
        "status": "loaded",
        "path": sanitized_path,
        "kind": payload.get("kind"),
        "schema_version": payload.get("schema_version"),
        "metrics": {key: int(value) for key, value in metrics.items()},
    }


def _evaluate_coverage_ratchet(current_metrics: dict[str, int], ratchet_state: dict[str, Any]) -> dict[str, Any]:
    status = ratchet_state["status"]
    if status != "loaded":
        return {
            "status": status,
            "path": ratchet_state["path"],
            "expected_metrics": ratchet_state.get("metrics", {}),
            "setpoint_metrics": dict(COVERAGE_RATCHET_SETPOINTS),
            "current_metrics": current_metrics,
            "regressions": [],
            "error": ratchet_state.get("error"),
            "error_type": ratchet_state.get("error_type"),
        }

    regressions: list[dict[str, int | str]] = []
    expected_min = ratchet_state["metrics"].get("min_line_rate_basis_points")
    actual = current_metrics.get("line_rate_basis_points", 0)
    if expected_min is not None and actual < expected_min:
        regressions.append(
            {
                "metric": "line_rate_basis_points",
                "expected_min": expected_min,
                "actual": actual,
            }
        )

    return {
        "status": "fail" if regressions else "pass",
        "path": ratchet_state["path"],
        "expected_metrics": ratchet_state["metrics"],
        "setpoint_metrics": dict(COVERAGE_RATCHET_SETPOINTS),
        "current_metrics": current_metrics,
        "regressions": regressions,
    }


def build_coverage_summary_report(root: Path) -> dict[str, Any]:
    """Build a machine-readable coverage summary from coverage.xml."""
    coverage_path = root / "coverage.xml"
    ratchet_state = _load_coverage_ratchet(root)
    if not coverage_path.exists():
        return {
            "kind": COVERAGE_SUMMARY_SCHEMA_KIND,
            "schema_version": COVERAGE_SUMMARY_SCHEMA_VERSION,
            "skipped": True,
            "skip_reason": "coverage.xml not found",
            "modules": [],
            "findings": [],
            "ratchet": {
                "status": "skipped",
                "path": ratchet_state["path"],
                "expected_metrics": ratchet_state.get("metrics", {}),
                "setpoint_metrics": dict(COVERAGE_RATCHET_SETPOINTS),
                "current_metrics": {},
                "regressions": [],
                "error": "coverage.xml not found",
                "error_type": "FileNotFoundError",
            },
            "summary": {
                "module_count": 0,
                "low_coverage_count": 0,
                "avg_line_rate": None,
                "total_line_rate": None,
                "total_lines_valid": 0,
                "total_lines_covered": 0,
                "total_lines_missing": 0,
            },
        }

    root_xml = ElementTree.fromstring(coverage_path.read_text(encoding="utf-8"))
    modules: list[dict[str, Any]] = []
    low_coverage: list[dict[str, Any]] = []
    line_rates: list[float] = []

    for class_node in root_xml.findall(".//class"):
        filename = _normalize_coverage_filename(class_node.attrib.get("filename", ""))
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
    total_lines_valid = int(root_xml.attrib.get("lines-valid", "0") or 0)
    total_lines_covered = int(root_xml.attrib.get("lines-covered", "0") or 0)
    if total_lines_valid == 0:
        total_lines_valid = sum(module["lines_valid"] for module in modules)
    if total_lines_covered == 0:
        total_lines_covered = sum(module["lines_covered"] for module in modules)

    total_line_rate = float(root_xml.attrib.get("line-rate", "0") or 0)
    if total_lines_valid and ("line-rate" not in root_xml.attrib or total_line_rate == 0):
        total_line_rate = total_lines_covered / total_lines_valid
    total_line_rate = round(total_line_rate, 4) if total_lines_valid else None
    total_lines_missing = max(total_lines_valid - total_lines_covered, 0)
    current_metrics = {
        "line_rate_basis_points": 0 if total_line_rate is None else round(total_line_rate * 10000),
    }
    ratchet = _evaluate_coverage_ratchet(current_metrics, ratchet_state)

    findings = sorted(low_coverage, key=lambda finding: (finding["severity"], finding["path"]))
    if ratchet["status"] == "fail":
        findings.append(
            {
                "id": "coverage-ratchet-regression",
                "path": "coverage.xml",
                "line_rate": total_line_rate,
                "severity": "medium",
                "message": "Overall test coverage regressed below the checked-in ratchet baseline.",
                "suggestion": "Restore coverage before merging or refresh artifacts/analysis/coverage_ratchet.json after an intentional improvement.",
                "ratchet_path": ratchet["path"],
            }
        )

    return {
        "kind": COVERAGE_SUMMARY_SCHEMA_KIND,
        "schema_version": COVERAGE_SUMMARY_SCHEMA_VERSION,
        "skipped": False,
        "modules": sorted(modules, key=lambda module: module["path"]),
        "findings": findings,
        "ratchet": ratchet,
        "summary": {
            "module_count": len(modules),
            "low_coverage_count": len(low_coverage),
            "avg_line_rate": avg_line_rate,
            "total_line_rate": total_line_rate,
            "total_lines_valid": total_lines_valid,
            "total_lines_covered": total_lines_covered,
            "total_lines_missing": total_lines_missing,
        },
    }


__all__ = [
    "COVERAGE_SUMMARY_SCHEMA_KIND",
    "COVERAGE_SUMMARY_SCHEMA_VERSION",
    "build_coverage_summary_report",
]
