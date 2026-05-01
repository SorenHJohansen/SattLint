"""Shared coverage report builders used by repo audit and pipeline."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from defusedxml import ElementTree  # type: ignore[import-untyped]

from sattlint.path_sanitizer import sanitize_path_for_report

COVERAGE_RATCHET_PATH = Path("artifacts") / "analysis" / "coverage_ratchet.json"
COVERAGE_RATCHET_SCHEMA_KIND = "sattlint.coverage_ratchet"
COVERAGE_RATCHET_SCHEMA_VERSION = 1
COVERAGE_SUMMARY_SCHEMA_KIND = "sattlint.coverage_summary"
COVERAGE_SUMMARY_SCHEMA_VERSION = 1
COVERAGE_RATCHET_SETPOINTS = {
    "min_line_rate_basis_points": 10000,
    "min_changed_line_rate_basis_points": 10000,
    "min_touched_file_line_rate_basis_points": 9000,
}
_GIT_DIFF_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _normalize_coverage_filename(filename: str) -> str:
    normalized = filename.replace("\\", "/").lstrip("./")
    if not normalized:
        return ""
    if normalized.startswith(("src/", "tests/")):
        return normalized
    if normalized.startswith("/") or (len(normalized) > 1 and normalized[1] == ":"):
        return normalized
    return f"src/{normalized}"


def _normalize_changed_files(changed_files: Iterable[str] | None) -> list[str]:
    if changed_files is None:
        return []
    normalized: list[str] = []
    for raw_path in changed_files:
        path_text = str(raw_path).strip().replace("\\", "/")
        if not path_text or path_text in normalized:
            continue
        normalized.append(path_text)
    return normalized


def _changed_source_files(changed_files: Iterable[str] | None) -> list[str]:
    return [
        path_text
        for path_text in _normalize_changed_files(changed_files)
        if path_text.startswith("src/") and path_text.endswith(".py")
    ]


def _parse_git_changed_line_map(diff_text: str, *, allowed_paths: set[str]) -> dict[str, set[int]]:
    changed_line_map: dict[str, set[int]] = {}
    current_path: str | None = None
    for raw_line in diff_text.splitlines():
        if raw_line.startswith("+++ "):
            path_text = raw_line[4:].strip()
            if path_text == "/dev/null":
                current_path = None
                continue
            if path_text.startswith("b/"):
                path_text = path_text[2:]
            path_text = path_text.replace("\\", "/")
            current_path = path_text if path_text in allowed_paths else None
            continue
        if current_path is None:
            continue
        match = _GIT_DIFF_HUNK_RE.match(raw_line)
        if match is None:
            continue
        start_line = int(match.group(1))
        line_count = int(match.group(2) or "1")
        if line_count <= 0:
            continue
        changed_line_map.setdefault(current_path, set()).update(range(start_line, start_line + line_count))
    return changed_line_map


def _discover_changed_line_map(root: Path, changed_files: Iterable[str] | None) -> dict[str, list[int]]:
    changed_source_files = _changed_source_files(changed_files)
    if not changed_source_files:
        return {}
    git_executable = shutil.which("git")
    if git_executable is None:
        return {}

    merged_line_map: dict[str, set[int]] = {}
    allowed_paths = set(changed_source_files)
    commands = (
        [git_executable, "diff", "--unified=0", "--no-color", "--", *changed_source_files],
        [git_executable, "diff", "--cached", "--unified=0", "--no-color", "--", *changed_source_files],
    )
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
        except OSError:
            continue
        if completed.returncode != 0 or not completed.stdout:
            continue
        parsed_line_map = _parse_git_changed_line_map(completed.stdout, allowed_paths=allowed_paths)
        for path_text, line_numbers in parsed_line_map.items():
            merged_line_map.setdefault(path_text, set()).update(line_numbers)

    return {path_text: sorted(line_numbers) for path_text, line_numbers in sorted(merged_line_map.items())}


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


def _collect_modules(root_xml: Any) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[float]]:
    modules: list[dict[str, Any]] = []
    module_lookup: dict[str, dict[str, Any]] = {}
    line_rates: list[float] = []

    for class_node in root_xml.findall(".//class"):
        filename = _normalize_coverage_filename(class_node.attrib.get("filename", ""))
        if not filename.startswith("src/"):
            continue
        line_rate = float(class_node.attrib.get("line-rate", "0"))
        lines_valid = int(class_node.attrib.get("lines-valid", "0") or 0)
        lines_covered = int(class_node.attrib.get("lines-covered", "0") or round(line_rate * lines_valid))
        line_hits: dict[int, int] = {}
        for line_node in class_node.findall("lines/line"):
            line_number = int(line_node.attrib.get("number", "0") or 0)
            if line_number <= 0:
                continue
            line_hits[line_number] = int(line_node.attrib.get("hits", "0") or 0)
        line_rates.append(line_rate)
        module_entry = {
            "path": filename,
            "line_rate": round(line_rate, 4),
            "lines_valid": lines_valid,
            "lines_covered": lines_covered,
            "line_hits": line_hits,
        }
        modules.append(module_entry)
        module_lookup[filename] = module_entry

    return modules, module_lookup, line_rates


def _summarize_change_scoped_coverage(
    *,
    changed_files: Iterable[str] | None,
    changed_line_map: Mapping[str, Iterable[int]] | None,
    module_lookup: Mapping[str, dict[str, Any]],
    ratchet_state: dict[str, Any],
) -> dict[str, Any]:
    touched_source_files = _changed_source_files(changed_files)
    if not touched_source_files:
        return {
            "status": "skipped",
            "mode": "skipped",
            "changed_files": [],
            "touched_modules": [],
            "changed_line_details": [],
            "summary": {
                "touched_file_count": 0,
                "touched_line_rate": None,
                "touched_lines_valid": 0,
                "touched_lines_covered": 0,
                "changed_line_count": 0,
                "changed_lines_covered": 0,
                "changed_line_rate": None,
                "unmeasured_changed_line_count": 0,
                "unreported_file_count": 0,
            },
            "ratchet": {
                "status": "skipped",
                "metric": None,
                "expected_min": None,
                "actual": None,
                "regressions": [],
            },
        }

    normalized_changed_line_map = {
        str(path_text).replace("\\", "/"): sorted({int(line_number) for line_number in line_numbers})
        for path_text, line_numbers in (changed_line_map or {}).items()
    }
    touched_modules: list[dict[str, Any]] = []
    changed_line_details: list[dict[str, Any]] = []
    unreported_files: list[str] = []
    touched_lines_valid = 0
    touched_lines_covered = 0
    changed_line_count = 0
    changed_lines_covered = 0
    unmeasured_changed_line_count = 0

    for path_text in touched_source_files:
        module_entry = module_lookup.get(path_text)
        if module_entry is None:
            unreported_files.append(path_text)
            touched_modules.append(
                {
                    "path": path_text,
                    "reported": False,
                    "line_rate": None,
                    "lines_valid": 0,
                    "lines_covered": 0,
                }
            )
            continue

        touched_lines_valid += int(module_entry["lines_valid"])
        touched_lines_covered += int(module_entry["lines_covered"])
        touched_modules.append(
            {
                "path": path_text,
                "reported": True,
                "line_rate": module_entry["line_rate"],
                "lines_valid": module_entry["lines_valid"],
                "lines_covered": module_entry["lines_covered"],
            }
        )

        changed_lines = normalized_changed_line_map.get(path_text, [])
        if not changed_lines:
            continue
        line_hits = module_entry["line_hits"]
        measured_lines = [line_number for line_number in changed_lines if line_number in line_hits]
        covered_lines = [line_number for line_number in measured_lines if int(line_hits[line_number]) > 0]
        changed_line_count += len(measured_lines)
        changed_lines_covered += len(covered_lines)
        unmeasured_changed_line_count += len(changed_lines) - len(measured_lines)
        changed_line_details.append(
            {
                "path": path_text,
                "requested_changed_lines": changed_lines,
                "measured_changed_lines": measured_lines,
                "covered_changed_lines": covered_lines,
                "unmeasured_changed_line_count": len(changed_lines) - len(measured_lines),
            }
        )

    touched_line_rate = round(touched_lines_covered / touched_lines_valid, 4) if touched_lines_valid else None
    changed_line_rate = round(changed_lines_covered / changed_line_count, 4) if changed_line_count else None
    mode = "changed-lines" if changed_line_count else "touched-files"
    metric_name = "changed_line_rate_basis_points" if mode == "changed-lines" else "touched_file_line_rate_basis_points"
    expected_min = ratchet_state.get("metrics", {}).get(f"min_{metric_name}")
    actual = 0
    if mode == "changed-lines" and changed_line_rate is not None:
        actual = round(changed_line_rate * 10000)
    elif mode == "touched-files" and touched_line_rate is not None:
        actual = round(touched_line_rate * 10000)

    regressions: list[dict[str, Any]] = []
    if expected_min is not None and actual < expected_min:
        regressions.append({"metric": metric_name, "expected_min": expected_min, "actual": actual})
    if unreported_files:
        regressions.append(
            {
                "metric": "reported_touched_source_files",
                "expected": "all touched source files must appear in focused coverage output",
                "actual": "missing files",
                "paths": unreported_files,
            }
        )

    return {
        "status": "fail" if regressions else "pass",
        "mode": mode,
        "changed_files": touched_source_files,
        "touched_modules": touched_modules,
        "changed_line_details": changed_line_details,
        "summary": {
            "touched_file_count": len(touched_source_files),
            "touched_line_rate": touched_line_rate,
            "touched_lines_valid": touched_lines_valid,
            "touched_lines_covered": touched_lines_covered,
            "changed_line_count": changed_line_count,
            "changed_lines_covered": changed_lines_covered,
            "changed_line_rate": changed_line_rate,
            "unmeasured_changed_line_count": unmeasured_changed_line_count,
            "unreported_file_count": len(unreported_files),
        },
        "ratchet": {
            "status": "fail" if regressions else "pass",
            "metric": metric_name,
            "expected_min": expected_min,
            "actual": actual,
            "regressions": regressions,
        },
    }


def build_coverage_summary_report(
    root: Path,
    *,
    coverage_path: Path | None = None,
    changed_files: Iterable[str] | None = None,
    changed_line_map: Mapping[str, Iterable[int]] | None = None,
) -> dict[str, Any]:
    """Build a machine-readable coverage summary from coverage.xml."""
    resolved_coverage_path = coverage_path or (root / "coverage.xml")
    ratchet_state = _load_coverage_ratchet(root)
    if not resolved_coverage_path.exists():
        return {
            "kind": COVERAGE_SUMMARY_SCHEMA_KIND,
            "schema_version": COVERAGE_SUMMARY_SCHEMA_VERSION,
            "skipped": True,
            "skip_reason": "coverage.xml not found",
            "modules": [],
            "findings": [],
            "change_scoped": _summarize_change_scoped_coverage(
                changed_files=changed_files,
                changed_line_map=changed_line_map,
                module_lookup={},
                ratchet_state=ratchet_state,
            ),
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

    root_xml = ElementTree.fromstring(resolved_coverage_path.read_text(encoding="utf-8"))
    low_coverage: list[dict[str, Any]] = []
    modules, module_lookup, line_rates = _collect_modules(root_xml)

    for module_entry in modules:
        line_rate = float(module_entry["line_rate"])

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
                    "path": module_entry["path"],
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
    effective_changed_line_map = changed_line_map
    if effective_changed_line_map is None and changed_files is not None:
        effective_changed_line_map = _discover_changed_line_map(root, changed_files)
    change_scoped = _summarize_change_scoped_coverage(
        changed_files=changed_files,
        changed_line_map=effective_changed_line_map,
        module_lookup=module_lookup,
        ratchet_state=ratchet_state,
    )

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
    if change_scoped["status"] == "fail":
        findings.append(
            {
                "id": "change-scoped-coverage-ratchet-regression",
                "path": change_scoped["changed_files"][0] if change_scoped["changed_files"] else "coverage.xml",
                "severity": "medium",
                "message": "Changed source coverage proof fell below the checked-in diff-scoped ratchet.",
                "suggestion": "Run focused owner tests with coverage and raise changed-line coverage first; fall back to touched-file proof only when no executable changed lines exist.",
                "coverage_mode": change_scoped["mode"],
            }
        )

    return {
        "kind": COVERAGE_SUMMARY_SCHEMA_KIND,
        "schema_version": COVERAGE_SUMMARY_SCHEMA_VERSION,
        "skipped": False,
        "modules": sorted(modules, key=lambda module: module["path"]),
        "findings": findings,
        "change_scoped": change_scoped,
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
