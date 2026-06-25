"""Change-scoped proof helpers for pipeline and repo-audit finish gates."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sattlint.path_sanitizer import sanitize_path_for_report

from .json_helpers import json_mapping as _json_mapping

_STRUCTURAL_SURFACE_METRICS = {
    "import_max_count": "imports",
    "dependency_max_count": "dependencies",
    "public_symbol_max_count": "public symbols",
    "nesting_max_depth": "nesting",
}


def _mutation_guidance(changed_files: Iterable[str]) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module  # noqa: PLC0415
    from sattlint.devtools._portable_command_text import pytest_command  # noqa: PLC0415

    normalized_changed_files = pipeline_module.normalize_changed_files(changed_files)
    matched_surfaces: list[str] = []
    suggested_commands: list[str] = []
    rules = (
        (
            "parser",
            ("src/sattline_parser/", "tests/parser/", "src/sattlint/grammar/"),
            pytest_command(
                "--no-cov",
                "tests/parser/test_parser_core.py",
                "tests/parser/test_parser_validation.py",
                "-x",
                "-q",
                "--tb=short",
            ),
        ),
        (
            "validation",
            (
                "src/sattlint/validation.py",
                "src/sattlint/_validation",
                "tests/parser/test_parser_validation.py",
            ),
            pytest_command("--no-cov", "tests/parser/test_parser_validation.py", "-x", "-q", "--tb=short"),
        ),
        (
            "routing",
            (
                "src/sattlint/devtools/pipeline.py",
                "src/sattlint/devtools/shared/pipeline_checks.py",
                "src/sattlint/devtools/repo_audit.py",
                "src/sattlint/devtools/repo_audit_cli.py",
                "src/sattlint/devtools/repo_audit_entrypoints.py",
                "src/sattlint/devtools/ai_work_map.py",
                "tests/test_recommendation_routing.py",
            ),
            pytest_command(
                "--no-cov",
                "tests/test_pipeline_run.py",
                "tests/test_repo_audit_part8.py",
                "tests/test_recommendation_routing.py",
                "-x",
                "-q",
                "--tb=short",
            ),
        ),
    )
    for surface_name, prefixes, command in rules:
        if not any(path_text.startswith(prefix) for prefix in prefixes for path_text in normalized_changed_files):
            continue
        matched_surfaces.append(surface_name)
        if command not in suggested_commands:
            suggested_commands.append(command)

    if not matched_surfaces:
        return {
            "status": "not-applicable",
            "critical_surfaces": [],
            "suggested_commands": [],
            "suggestion": None,
        }
    return {
        "status": "advisory",
        "critical_surfaces": matched_surfaces,
        "suggested_commands": suggested_commands,
        "suggestion": (
            "Prefer mutation-style or property-style assertions for parser, validation, and routing seams before "
            "treating the repo-wide coverage percentage as sufficient proof."
        ),
    }


def _changed_source_python_files(changed_files: Iterable[str]) -> list[str]:
    return [path_text for path_text in changed_files if path_text.endswith(".py") and path_text.startswith("src/")]


def _is_structural_budget_python_path(path_text: str) -> bool:
    return path_text.endswith(".py") and path_text.startswith(("src/", "tests/"))


def _load_structural_budget_ratchet(repo_root: Path, *, ratchet_path: Path) -> dict[str, Any]:
    if not ratchet_path.exists():
        return {"status": "missing", "path": ratchet_path.as_posix(), "metrics": {}}
    try:
        payload = _json_mapping(json.loads(ratchet_path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid",
            "path": ratchet_path.as_posix(),
            "metrics": {},
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
    if payload is None:
        return {
            "status": "invalid",
            "path": ratchet_path.as_posix(),
            "metrics": {},
            "error": "ratchet payload must be a JSON object",
            "error_type": "ValueError",
        }
    return dict(payload)


def build_change_proof_requirements(
    *,
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    from sattlint.devtools import _pipeline_finish_gate as finish_gate_module  # noqa: PLC0415
    from sattlint.devtools import pipeline as pipeline_module  # noqa: PLC0415

    normalized_changed_files = pipeline_module.normalize_changed_files(changed_files)
    owner_test_targets = finish_gate_module.owner_test_targets_for_checks(
        recommended_checks,
        changed_files=normalized_changed_files,
    )
    touched_python_files = finish_gate_module.focused_python_files(normalized_changed_files)
    touched_source_files = _changed_source_python_files(touched_python_files)
    focused_behavior_required = bool(touched_python_files)
    focused_behavior_status = "satisfied" if (not focused_behavior_required or owner_test_targets) else "missing"
    return {
        "focused_behavior_test": {
            "required": focused_behavior_required,
            "status": focused_behavior_status,
            "owner_test_targets": owner_test_targets,
            "reason": (
                "Code changes require at least one focused owner pytest target."
                if focused_behavior_required
                else "No changed Python files require a focused owner pytest target."
            ),
        },
        "coverage": {
            "required": bool(touched_source_files),
            "preferred_mode": "changed-lines" if touched_source_files else None,
            "fallback_mode": "touched-files" if touched_source_files else None,
            "touched_source_files": touched_source_files,
            "reason": (
                "Touched source files should be proven by focused changed-line coverage when executable diff lines "
                "exist, or touched-file coverage otherwise."
                if touched_source_files
                else "No changed source files require focused coverage proof."
            ),
        },
        "mutation_guidance": _mutation_guidance(normalized_changed_files),
    }


def evaluate_change_scoped_coverage_proof(
    *,
    repo_root: Path,
    coverage_output_path: Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module  # noqa: PLC0415

    report = pipeline_module.build_coverage_summary_report(
        repo_root,
        coverage_path=coverage_output_path,
        changed_files=changed_files,
    )
    change_scoped = dict(report["change_scoped"])
    change_scoped["coverage_path"] = (
        sanitize_path_for_report(coverage_output_path.resolve(), repo_root=repo_root)
        or coverage_output_path.resolve().as_posix()
    )
    return change_scoped


def evaluate_change_scoped_structural_surface_proof(
    *,
    repo_root: Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module  # noqa: PLC0415
    from sattlint.devtools.structural import structural_reports as structural_reports_module  # noqa: PLC0415
    from sattlint.devtools.structural._structural_report_budget_support import (  # noqa: PLC0415
        build_known_structural_modules,
        collect_python_structural_surface_metrics,
    )

    normalized_changed_files = pipeline_module.normalize_changed_files(changed_files)
    structural_files = [
        path_text for path_text in normalized_changed_files if _is_structural_budget_python_path(path_text)
    ]
    if not structural_files:
        return {
            "status": "not-required",
            "checked_files": [],
            "expected_metrics": {},
            "metrics_by_path": {},
            "violations": [],
            "scan_failures": [],
            "reason": "No changed structural Python files require structural surface proof.",
        }

    ratchet_state = _load_structural_budget_ratchet(
        repo_root,
        ratchet_path=repo_root / structural_reports_module.STRUCTURAL_BUDGET_RATCHET_PATH,
    )
    expected_metrics = {
        metric: int(value)
        for metric, value in ratchet_state.get("metrics", {}).items()
        if metric in _STRUCTURAL_SURFACE_METRICS and isinstance(value, int)
    }
    if not expected_metrics:
        return {
            "status": "not-required",
            "checked_files": structural_files,
            "expected_metrics": {},
            "metrics_by_path": {},
            "violations": [],
            "scan_failures": [],
            "reason": "Structural ratchet does not yet record structural surface ceilings.",
        }

    known_modules = build_known_structural_modules(repo_root)
    metrics_by_path: dict[str, dict[str, int]] = {}
    violations: list[dict[str, Any]] = []
    scan_failures: list[dict[str, Any]] = []

    for rel_path in structural_files:
        path = repo_root / rel_path
        if not path.is_file():
            continue
        text, _line_count, scan_failure = structural_reports_module.read_structural_text(path)
        if scan_failure is not None or text is None:
            scan_failures.append({"path": rel_path, **(scan_failure or {"error": "file could not be read"})})
            continue
        try:
            tree = structural_reports_module.ast.parse(text, filename=rel_path)
        except SyntaxError as exc:
            scan_failures.append(
                {
                    "path": rel_path,
                    "error": exc.msg,
                    "error_type": type(exc).__name__,
                    "line": exc.lineno,
                }
            )
            continue

        surface_metrics = collect_python_structural_surface_metrics(
            tree,
            relative_path=rel_path,
            repo_root=repo_root,
            known_modules=known_modules,
        )
        actual_metrics = {
            "import_max_count": int(surface_metrics["import_count"]),
            "dependency_max_count": int(surface_metrics["dependency_count"]),
            "public_symbol_max_count": int(surface_metrics["public_symbol_count"]),
            "nesting_max_depth": max(
                (int(entry["nesting_depth"]) for entry in surface_metrics["function_nesting_depths"]),
                default=0,
            ),
        }
        metrics_by_path[rel_path] = actual_metrics
        for metric, expected_max in expected_metrics.items():
            actual = actual_metrics[metric]
            if actual > expected_max:
                violations.append(
                    {
                        "path": rel_path,
                        "metric": metric,
                        "label": _STRUCTURAL_SURFACE_METRICS[metric],
                        "actual": actual,
                        "expected_max": expected_max,
                    }
                )

    status = "fail" if violations or scan_failures else "pass"
    return {
        "status": status,
        "checked_files": structural_files,
        "expected_metrics": expected_metrics,
        "metrics_by_path": metrics_by_path,
        "violations": violations,
        "scan_failures": scan_failures,
        "reason": (
            "Changed structural Python files stay within the recorded surface ceilings."
            if status == "pass"
            else "Changed structural Python files would raise a recorded structural surface ceiling."
        ),
    }


def compact_pipeline_summary_timing(pipeline_summary: dict[str, Any] | None) -> dict[str, Any]:
    if pipeline_summary is None:
        return {}
    mapping = _json_mapping(pipeline_summary)
    if mapping is None:
        return {}
    return dict(mapping.get("timing") or {})


__all__ = [
    "build_change_proof_requirements",
    "compact_pipeline_summary_timing",
    "evaluate_change_scoped_coverage_proof",
    "evaluate_change_scoped_structural_surface_proof",
]
