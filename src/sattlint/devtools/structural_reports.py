"""Structural pipeline report builders and shared graph inputs."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)
from sattlint.analyzers.registry import (
    get_actual_cli_analyzer_keys,
    get_actual_lsp_analyzer_keys,
    get_declared_cli_analyzer_keys,
    get_declared_lsp_analyzer_keys,
    get_default_analyzer_catalog,
)
from sattlint.app import VARIABLE_ANALYSES
from sattlint.core.semantic import discover_workspace_sources, load_workspace_snapshot
from sattlint.devtools._structural_budget_inventory import (
    iter_structural_markdown_files,
    iter_structural_python_files,
    read_structural_text,
    summarize_structural_budget_metrics,
)
from sattlint.devtools._structural_report_impact import collect_impact_analysis_report
from sattlint.path_sanitizer import sanitize_path_for_report
from sattlint.reporting.variables_report import IssueKind, VariablesReport
from sattlint.resolution.common import resolve_moduletype_def_strict
from sattlint.semantic_analysis import build_variable_semantic_artifacts

REPO_ROOT = Path(__file__).resolve().parents[3]
STRUCTURAL_ENTRY_ROOTS = (Path("tests") / "fixtures" / "sample_sattline_files",)
PHASE2_ENFORCED_RULE_METADATA_FINDING_IDS = frozenset(
    {
        "rule-acceptance-test-gap",
        "rule-mutation-metadata-gap",
    }
)
PHASE2_ADVISORY_RULE_METADATA_FINDING_IDS = frozenset({"rule-corpus-link-gap"})


@dataclass(frozen=True, slots=True)
class WorkspaceGraphInputs:
    discovery: Any
    snapshots: list[Any]
    snapshot_failures: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class StructuralReportsBundle:
    architecture_report: dict[str, Any]
    analyzer_registry_report: dict[str, Any]
    graph_inputs: WorkspaceGraphInputs
    dependency_graph_report: dict[str, Any]
    call_graph_report: dict[str, Any]
    graphics_layout_report: dict[str, Any]
    impact_analysis_report: dict[str, Any]


_GRAPHICS_LAYOUT_COMPARISON_FIELDS = (
    "invocation.coords",
    "invocation.arguments",
    "invocation.layer",
    "invocation.zoom_limits",
    "invocation.zoomable",
    "moduledef.clipping_origin",
    "moduledef.clipping_size",
    "moduledef.zoom_limits",
    "moduledef.grid",
    "moduledef.zoomable",
)

STRUCTURAL_BUDGET_THRESHOLDS = {
    "source_file_max_lines": 500,
    "test_file_max_lines": 500,
    "markdown_file_max_lines": 500,
    "function_max_lines": 150,
    "class_method_max_count": 40,
    "duplicate_private_name_min_files": 4,
    "duplicate_private_name_min_length": 5,
}
STRUCTURAL_BUDGET_SETPOINTS = {
    "source_file_max_lines": 500,
    "test_file_max_lines": 500,
    "markdown_file_max_lines": 500,
}
STRUCTURAL_BUDGET_RATCHET_PATH = Path("artifacts") / "analysis" / "structural_budget_ratchet.json"
FILE_DEBT_RATCHET_PATH = Path("artifacts") / "analysis" / "file_debt_ratchet.json"
FACADE_PRIVATE_BOUNDARY_FILES = frozenset(
    {
        "src/sattlint/app.py",
        "src/sattlint/app_base.py",
        "src/sattlint/editor_api.py",
    }
)


def _collect_facade_private_entrypoints(tree: ast.AST, *, relative_path: str) -> list[dict[str, Any]]:
    module_aliases: dict[str, str] = {}
    imported_private_names: dict[str, str] = {}

    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.rsplit(".", 1)[-1]
                if local_name.endswith("_module"):
                    module_aliases[local_name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module_prefix = "." * node.level + (node.module or "")
            for alias in node.names:
                local_name = alias.asname or alias.name
                if local_name.endswith("_module"):
                    full_module_name = f"{module_prefix}.{alias.name}" if module_prefix else alias.name
                    module_aliases[local_name] = full_module_name.lstrip(".")
                if alias.name.startswith("_"):
                    full_symbol_name = f"{module_prefix}.{alias.name}" if module_prefix else alias.name
                    imported_private_names[local_name] = full_symbol_name.lstrip(".")

    violations: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            target_module = module_aliases.get(node.func.value.id)
            if target_module and node.func.attr.startswith("_"):
                violations.append(
                    {
                        "path": relative_path,
                        "line": node.lineno,
                        "target": f"{target_module}.{node.func.attr}",
                    }
                )
        elif isinstance(node.func, ast.Name):
            target = imported_private_names.get(node.func.id)
            if target is not None:
                violations.append(
                    {
                        "path": relative_path,
                        "line": node.lineno,
                        "target": target,
                    }
                )
    return sorted(violations, key=lambda item: (item["path"], item["line"], item["target"]))


def _normalize_file_line_exceptions(raw: Any, *, label: str) -> dict[str, dict[str, Any]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{label} file_line_exceptions must be a JSON object keyed by repo-relative path.")

    normalized: dict[str, dict[str, Any]] = {}
    for raw_path, payload in raw.items():
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"{label} file_line_exceptions keys must be non-empty strings.")
        if not isinstance(payload, dict):
            raise ValueError(f"{label} file_line_exceptions[{raw_path!r}] must be a JSON object.")

        max_lines = payload.get("max_lines")
        reason = payload.get("reason")
        if not isinstance(max_lines, int) or max_lines <= 0:
            raise ValueError(f"{label} file_line_exceptions[{raw_path!r}].max_lines must be a positive integer.")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{label} file_line_exceptions[{raw_path!r}].reason must be a non-empty string.")

        normalized[raw_path.replace("\\", "/").strip("/")] = {
            "max_lines": int(max_lines),
            "reason": reason.strip(),
        }

    return dict(sorted(normalized.items()))


def _load_structural_budget_ratchet(
    repo_root: Path,
    *,
    ratchet_path: Path | None = None,
) -> dict[str, Any]:
    resolved_path = ratchet_path or (repo_root / STRUCTURAL_BUDGET_RATCHET_PATH)
    sanitized_path = sanitize_path_for_report(resolved_path, repo_root=repo_root) or resolved_path.as_posix()
    if not resolved_path.exists():
        return {"status": "missing", "path": sanitized_path, "metrics": {}, "file_line_exceptions": {}}

    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid",
            "path": sanitized_path,
            "metrics": {},
            "file_line_exceptions": {},
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

    metrics = payload.get("metrics")
    if not isinstance(metrics, dict) or any(not isinstance(value, int) for value in metrics.values()):
        return {
            "status": "invalid",
            "path": sanitized_path,
            "metrics": {},
            "file_line_exceptions": {},
            "error": "ratchet metrics must be a JSON object with integer values",
            "error_type": "ValueError",
        }

    try:
        file_line_exceptions = _normalize_file_line_exceptions(
            payload.get("file_line_exceptions"), label=sanitized_path
        )
    except ValueError as exc:
        return {
            "status": "invalid",
            "path": sanitized_path,
            "metrics": {},
            "file_line_exceptions": {},
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

    file_debt_path = repo_root / FILE_DEBT_RATCHET_PATH
    if file_debt_path.exists():
        try:
            file_debt_payload = json.loads(file_debt_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return {
                "status": "invalid",
                "path": sanitized_path,
                "metrics": {},
                "file_line_exceptions": {},
                "error": f"{FILE_DEBT_RATCHET_PATH.as_posix()} could not be loaded: {exc}",
                "error_type": type(exc).__name__,
            }

        files_payload = file_debt_payload.get("files")
        if not isinstance(files_payload, dict):
            return {
                "status": "invalid",
                "path": sanitized_path,
                "metrics": {},
                "file_line_exceptions": {},
                "error": f"{FILE_DEBT_RATCHET_PATH.as_posix()} files must be a JSON object.",
                "error_type": "ValueError",
            }

        for raw_path, dimension_payload in files_payload.items():
            if not isinstance(raw_path, str) or not isinstance(dimension_payload, dict):
                return {
                    "status": "invalid",
                    "path": sanitized_path,
                    "metrics": {},
                    "file_line_exceptions": {},
                    "error": f"{FILE_DEBT_RATCHET_PATH.as_posix()} contains an invalid structural debt entry.",
                    "error_type": "ValueError",
                }

            structural_payload = dimension_payload.get("structural")
            if structural_payload is None:
                continue
            if not isinstance(structural_payload, dict):
                return {
                    "status": "invalid",
                    "path": sanitized_path,
                    "metrics": {},
                    "file_line_exceptions": {},
                    "error": f"{FILE_DEBT_RATCHET_PATH.as_posix()} structural debt for {raw_path!r} must be a JSON object.",
                    "error_type": "ValueError",
                }

            max_lines = structural_payload.get("current_baseline")
            reason = structural_payload.get("reason")
            if not isinstance(max_lines, int) or max_lines <= 0:
                return {
                    "status": "invalid",
                    "path": sanitized_path,
                    "metrics": {},
                    "file_line_exceptions": {},
                    "error": (
                        f"{FILE_DEBT_RATCHET_PATH.as_posix()} structural debt for {raw_path!r} must include "
                        "a positive integer current_baseline."
                    ),
                    "error_type": "ValueError",
                }
            if not isinstance(reason, str) or not reason.strip():
                return {
                    "status": "invalid",
                    "path": sanitized_path,
                    "metrics": {},
                    "file_line_exceptions": {},
                    "error": (
                        f"{FILE_DEBT_RATCHET_PATH.as_posix()} structural debt for {raw_path!r} must include a non-empty reason."
                    ),
                    "error_type": "ValueError",
                }

            normalized_path = raw_path.replace("\\", "/").strip("/")
            existing = file_line_exceptions.get(normalized_path)
            if existing is not None and existing != {"max_lines": max_lines, "reason": reason.strip()}:
                return {
                    "status": "invalid",
                    "path": sanitized_path,
                    "metrics": {},
                    "file_line_exceptions": {},
                    "error": (
                        f"{FILE_DEBT_RATCHET_PATH.as_posix()} structural debt for {normalized_path!r} conflicts with "
                        f"{STRUCTURAL_BUDGET_RATCHET_PATH.as_posix()} file_line_exceptions."
                    ),
                    "error_type": "ValueError",
                }
            file_line_exceptions[normalized_path] = {"max_lines": max_lines, "reason": reason.strip()}

    return {
        "status": "loaded",
        "path": sanitized_path,
        "kind": payload.get("kind"),
        "schema_version": payload.get("schema_version"),
        "metrics": {key: int(value) for key, value in metrics.items()},
        "file_line_exceptions": file_line_exceptions,
    }


def _evaluate_structural_budget_ratchet(
    current_metrics: dict[str, int],
    ratchet_state: dict[str, Any],
    current_file_line_counts: dict[str, int],
) -> dict[str, Any]:
    status = ratchet_state["status"]
    if status != "loaded":
        return {
            "status": status,
            "path": ratchet_state["path"],
            "expected_metrics": ratchet_state.get("metrics", {}),
            "expected_file_line_exceptions": ratchet_state.get("file_line_exceptions", {}),
            "current_metrics": current_metrics,
            "regressions": [],
            "error": ratchet_state.get("error"),
            "error_type": ratchet_state.get("error_type"),
        }

    regressions = [
        {
            "metric": metric,
            "expected_max": expected_value,
            "actual": current_metrics.get(metric, 0),
        }
        for metric, expected_value in sorted(ratchet_state["metrics"].items())
        if current_metrics.get(metric, 0) > expected_value
    ]
    regressions.extend(
        {
            "path": path,
            "expected_max": entry["max_lines"],
            "actual": current_file_line_counts[path],
            "reason": entry["reason"],
        }
        for path, entry in sorted(ratchet_state["file_line_exceptions"].items())
        if path in current_file_line_counts and current_file_line_counts[path] > entry["max_lines"]
    )
    return {
        "status": "fail" if regressions else "pass",
        "path": ratchet_state["path"],
        "expected_metrics": ratchet_state["metrics"],
        "expected_file_line_exceptions": ratchet_state["file_line_exceptions"],
        "setpoint_metrics": dict(STRUCTURAL_BUDGET_SETPOINTS),
        "current_metrics": current_metrics,
        "regressions": regressions,
    }


def _append_structural_budget_findings(findings: list[dict[str, Any]], structural_budgets: dict[str, Any]) -> None:
    if structural_budgets["source_files_over_budget"]:
        findings.append(
            {
                "id": "structural-source-file-budget",
                "severity": "medium",
                "message": "Some source modules exceed the structural line budget and should be split before they grow further.",
                "count": len(structural_budgets["source_files_over_budget"]),
                "over_budget_files": structural_budgets["source_files_over_budget"][:10],
            }
        )

    if structural_budgets["test_files_over_budget"]:
        findings.append(
            {
                "id": "structural-test-file-budget",
                "severity": "medium",
                "message": "Some test modules exceed the structural line budget and should be split by owning surface.",
                "count": len(structural_budgets["test_files_over_budget"]),
                "over_budget_files": structural_budgets["test_files_over_budget"][:10],
            }
        )

    if structural_budgets.get("markdown_files_over_budget"):
        findings.append(
            {
                "id": "structural-markdown-file-budget",
                "severity": "medium",
                "message": "Some tracked Markdown files exceed the structural line budget and should be split or reorganized.",
                "count": len(structural_budgets["markdown_files_over_budget"]),
                "over_budget_files": structural_budgets["markdown_files_over_budget"][:10],
            }
        )

    if structural_budgets["functions_over_budget"]:
        findings.append(
            {
                "id": "structural-function-budget",
                "severity": "medium",
                "message": "Some Python functions exceed the structural function budget and should be decomposed.",
                "count": len(structural_budgets["functions_over_budget"]),
                "over_budget_functions": structural_budgets["functions_over_budget"][:10],
            }
        )

    if structural_budgets["classes_over_budget"]:
        findings.append(
            {
                "id": "structural-class-budget",
                "severity": "medium",
                "message": "Some classes exceed the structural method-count budget and should be split by responsibility.",
                "count": len(structural_budgets["classes_over_budget"]),
                "over_budget_classes": structural_budgets["classes_over_budget"][:10],
            }
        )

    if structural_budgets["repeated_private_names"]:
        findings.append(
            {
                "id": "structural-private-helper-duplication",
                "severity": "medium",
                "message": "Some private helper names repeat across many files, which often signals duplicated local implementations.",
                "count": len(structural_budgets["repeated_private_names"]),
                "repeated_private_names": structural_budgets["repeated_private_names"][:10],
            }
        )

    if structural_budgets["facade_private_entrypoints"]:
        findings.append(
            {
                "id": "structural-facade-private-boundary",
                "severity": "medium",
                "message": "Some facade modules call private cross-module entrypoints instead of stable owner APIs.",
                "count": len(structural_budgets["facade_private_entrypoints"]),
                "private_entrypoints": structural_budgets["facade_private_entrypoints"][:10],
            }
        )

    if structural_budgets["ratchet"]["status"] == "fail":
        findings.append(
            {
                "id": "structural-budget-ratchet-regression",
                "severity": "medium",
                "message": "Structural debt regressed beyond the checked-in ratchet baseline.",
                "count": len(structural_budgets["ratchet"]["regressions"]),
                "regressions": structural_budgets["ratchet"]["regressions"],
                "ratchet_path": structural_budgets["ratchet"]["path"],
            }
        )


def collect_structural_budget_report(
    repo_root: Path = REPO_ROOT,
    *,
    ratchet_path: Path | None = None,
) -> dict[str, Any]:
    source_file_max_lines = STRUCTURAL_BUDGET_THRESHOLDS["source_file_max_lines"]
    test_file_max_lines = STRUCTURAL_BUDGET_THRESHOLDS["test_file_max_lines"]
    markdown_file_max_lines = STRUCTURAL_BUDGET_THRESHOLDS["markdown_file_max_lines"]
    function_max_lines = STRUCTURAL_BUDGET_THRESHOLDS["function_max_lines"]
    class_method_max_count = STRUCTURAL_BUDGET_THRESHOLDS["class_method_max_count"]
    duplicate_private_name_min_files = STRUCTURAL_BUDGET_THRESHOLDS["duplicate_private_name_min_files"]
    duplicate_private_name_min_length = STRUCTURAL_BUDGET_THRESHOLDS["duplicate_private_name_min_length"]
    ratchet_state = _load_structural_budget_ratchet(repo_root, ratchet_path=ratchet_path)
    file_line_exceptions = ratchet_state.get("file_line_exceptions", {})

    source_files_over_budget: list[dict[str, Any]] = []
    test_files_over_budget: list[dict[str, Any]] = []
    markdown_files_over_budget: list[dict[str, Any]] = []
    functions_over_budget: list[dict[str, Any]] = []
    classes_over_budget: list[dict[str, Any]] = []
    private_name_occurrences: dict[str, set[str]] = defaultdict(set)
    facade_private_entrypoints: list[dict[str, Any]] = []
    scan_failures: list[dict[str, Any]] = []
    source_file_line_counts: list[int] = []
    test_file_line_counts: list[int] = []
    markdown_file_line_counts: list[int] = []
    current_file_line_counts: dict[str, int] = {}

    for scope, path in chain(iter_structural_python_files(repo_root), iter_structural_markdown_files(repo_root)):
        relative_path = sanitize_path_for_report(path, repo_root=repo_root) or path.as_posix()
        text, line_count, scan_failure = read_structural_text(path)
        if scan_failure is not None:
            scan_failures.append({"path": relative_path, **scan_failure})
        if line_count is None:
            continue

        current_file_line_counts[relative_path] = line_count
        if scope == "src":
            source_file_line_counts.append(line_count)
        if scope == "tests":
            test_file_line_counts.append(line_count)
        if scope == "markdown":
            markdown_file_line_counts.append(line_count)
        line_limit_exception = file_line_exceptions.get(relative_path)
        effective_max_lines = (
            line_limit_exception["max_lines"]
            if line_limit_exception is not None
            else (
                source_file_max_lines
                if scope == "src"
                else (test_file_max_lines if scope == "tests" else markdown_file_max_lines)
            )
        )
        if scope == "src" and line_count > effective_max_lines:
            source_files_over_budget.append({"path": relative_path, "line_count": line_count})
        if scope == "tests" and line_count > effective_max_lines:
            test_files_over_budget.append({"path": relative_path, "line_count": line_count})
        if scope == "markdown" and line_count > effective_max_lines:
            markdown_files_over_budget.append({"path": relative_path, "line_count": line_count})

        if text is None or scope == "markdown":
            continue

        try:
            tree = ast.parse(text, filename=relative_path)
        except SyntaxError as exc:
            scan_failures.append(
                {
                    "path": relative_path,
                    "error": exc.msg,
                    "error_type": type(exc).__name__,
                    "line": exc.lineno,
                }
            )
            continue

        if relative_path in FACADE_PRIVATE_BOUNDARY_FILES:
            facade_private_entrypoints.extend(_collect_facade_private_entrypoints(tree, relative_path=relative_path))

        module_level_private_names = {
            node.name
            for node in getattr(tree, "body", [])
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name.startswith("_")
            and not node.name.startswith("__")
            and len(node.name) >= duplicate_private_name_min_length
        }
        if scope == "src":
            for name in module_level_private_names:
                private_name_occurrences[name].add(relative_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                end_lineno = getattr(node, "end_lineno", None)
                if end_lineno is None:
                    continue
                line_span = end_lineno - node.lineno + 1
                if line_span > function_max_lines:
                    functions_over_budget.append(
                        {
                            "path": relative_path,
                            "qualname": node.name,
                            "line_span": line_span,
                            "start_line": node.lineno,
                            "end_line": end_lineno,
                        }
                    )
            elif isinstance(node, ast.ClassDef):
                method_count = sum(
                    1 for child in node.body if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
                )
                if method_count > class_method_max_count:
                    classes_over_budget.append(
                        {
                            "path": relative_path,
                            "qualname": node.name,
                            "method_count": method_count,
                            "start_line": node.lineno,
                            "end_line": getattr(node, "end_lineno", node.lineno),
                        }
                    )

    repeated_private_names = [
        {
            "name": name,
            "file_count": len(paths),
            "paths": sorted(paths),
        }
        for name, paths in sorted(private_name_occurrences.items())
        if len(paths) >= duplicate_private_name_min_files
    ]

    report = {
        "thresholds": dict(STRUCTURAL_BUDGET_THRESHOLDS),
        "setpoints": dict(STRUCTURAL_BUDGET_SETPOINTS),
        "line_limit_exceptions": [
            {
                "path": path,
                "line_count": current_file_line_counts.get(path),
                "max_lines": entry["max_lines"],
                "reason": entry["reason"],
                "status": (
                    "missing"
                    if path not in current_file_line_counts
                    else ("fail" if current_file_line_counts[path] > entry["max_lines"] else "pass")
                ),
            }
            for path, entry in sorted(file_line_exceptions.items())
        ],
        "source_files_over_budget": sorted(
            source_files_over_budget, key=lambda item: (-item["line_count"], item["path"])
        ),
        "test_files_over_budget": sorted(test_files_over_budget, key=lambda item: (-item["line_count"], item["path"])),
        "markdown_files_over_budget": sorted(
            markdown_files_over_budget, key=lambda item: (-item["line_count"], item["path"])
        ),
        "functions_over_budget": sorted(
            functions_over_budget,
            key=lambda item: (-item["line_span"], item["path"], item["qualname"]),
        ),
        "classes_over_budget": sorted(
            classes_over_budget,
            key=lambda item: (-item["method_count"], item["path"], item["qualname"]),
        ),
        "repeated_private_names": repeated_private_names,
        "facade_private_entrypoints": facade_private_entrypoints,
        "scan_failures": scan_failures,
        "summary": {
            "source_file_max_lines": max(source_file_line_counts, default=0),
            "test_file_max_lines": max(test_file_line_counts, default=0),
            "markdown_file_max_lines": max(markdown_file_line_counts, default=0),
        },
    }
    current_metrics = summarize_structural_budget_metrics(report)
    report["metrics"] = current_metrics
    report["ratchet"] = _evaluate_structural_budget_ratchet(current_metrics, ratchet_state, current_file_line_counts)
    return report


def collect_phase2_rule_metadata_gate(
    architecture_report: dict[str, Any],
) -> dict[str, Any]:
    findings = architecture_report.get("findings", []) or []
    blocking_findings = [
        finding for finding in findings if finding.get("id") in PHASE2_ENFORCED_RULE_METADATA_FINDING_IDS
    ]
    advisory_findings = [
        finding for finding in findings if finding.get("id") in PHASE2_ADVISORY_RULE_METADATA_FINDING_IDS
    ]
    blocking_rule_ids = sorted(
        {rule_id for finding in blocking_findings for rule_id in finding.get("missing_rule_ids", [])}
    )
    advisory_rule_ids = sorted(
        {rule_id for finding in advisory_findings for rule_id in finding.get("missing_rule_ids", [])}
    )
    return {
        "status": "fail" if blocking_rule_ids else "pass",
        "enforced_fields": ["acceptance_tests", "mutation_applicability"],
        "advisory_fields": ["corpus_cases"],
        "blocking_finding_ids": [finding["id"] for finding in blocking_findings],
        "advisory_finding_ids": [finding["id"] for finding in advisory_findings],
        "blocking_rule_ids": blocking_rule_ids,
        "advisory_rule_ids": advisory_rule_ids,
    }


def collect_architecture_report(
    repo_root: Path = REPO_ROOT,
    *,
    ratchet_path: Path | None = None,
) -> dict[str, Any]:
    structural_budgets = collect_structural_budget_report(repo_root, ratchet_path=ratchet_path)
    cli_filter_kinds = sorted(
        {issue_kind.value for _label, kinds in VARIABLE_ANALYSES.values() if kinds is not None for issue_kind in kinds}
    )
    summary_supported = {
        IssueKind.UNUSED.value: isinstance(getattr(VariablesReport, "unused", None), property),
        IssueKind.UNUSED_DATATYPE_FIELD.value: isinstance(
            getattr(VariablesReport, "unused_datatype_fields", None), property
        ),
        IssueKind.READ_ONLY_NON_CONST.value: isinstance(
            getattr(VariablesReport, "read_only_non_const", None), property
        ),
        IssueKind.UI_ONLY.value: isinstance(getattr(VariablesReport, "ui_only", None), property),
        IssueKind.NEVER_READ.value: isinstance(getattr(VariablesReport, "never_read", None), property),
        IssueKind.GLOBAL_SCOPE_MINIMIZATION.value: isinstance(
            getattr(VariablesReport, "global_scope_minimization", None), property
        ),
        IssueKind.HIGH_FAN_IN_OUT.value: isinstance(getattr(VariablesReport, "high_fan_in_out", None), property),
        IssueKind.STRING_MAPPING_MISMATCH.value: isinstance(
            getattr(VariablesReport, "string_mapping_mismatch", None), property
        ),
        IssueKind.HIDDEN_GLOBAL_COUPLING.value: isinstance(
            getattr(VariablesReport, "hidden_global_coupling", None), property
        ),
        IssueKind.DATATYPE_DUPLICATION.value: isinstance(
            getattr(VariablesReport, "datatype_duplication", None), property
        ),
        IssueKind.MIN_MAX_MAPPING_MISMATCH.value: isinstance(
            getattr(VariablesReport, "min_max_mapping_mismatch", None), property
        ),
        IssueKind.MAGIC_NUMBER.value: isinstance(getattr(VariablesReport, "magic_numbers", None), property),
        IssueKind.NAME_COLLISION.value: isinstance(getattr(VariablesReport, "name_collisions", None), property),
        IssueKind.SHADOWING.value: isinstance(getattr(VariablesReport, "shadowing", None), property),
        IssueKind.RESET_CONTAMINATION.value: isinstance(
            getattr(VariablesReport, "reset_contamination", None), property
        ),
        IssueKind.IMPLICIT_LATCH.value: isinstance(getattr(VariablesReport, "implicit_latches", None), property),
    }

    catalog = get_default_analyzer_catalog()
    analyzers = catalog.analyzers
    registry_keys = [analyzer.spec.key for analyzer in analyzers]
    live_diagnostic_analyzers = [analyzer.spec.key for analyzer in analyzers if analyzer.spec.supports_live_diagnostics]
    declared_cli_analyzers = list(get_declared_cli_analyzer_keys())
    actual_cli_analyzers = sorted(get_actual_cli_analyzer_keys())
    semantic_layer_sources = list(get_actual_lsp_analyzer_keys())
    declared_lsp_analyzers = list(get_declared_lsp_analyzer_keys())
    analyzers_missing_exposure = sorted(
        analyzer.spec.key
        for analyzer in analyzers
        if not (analyzer.delivery.cli_exposed or analyzer.delivery.lsp_exposed or analyzer.delivery.exposed_via)
    )
    analyzers_missing_acceptance_tests = sorted(
        analyzer.spec.key for analyzer in analyzers if analyzer.spec.enabled and not analyzer.delivery.acceptance_tests
    )
    rules_missing_acceptance_tests = sorted(rule.id for rule in catalog.rules if not rule.acceptance_tests)
    rules_missing_corpus_links = sorted(
        rule.id for rule in catalog.rules if rule.mutation_applicability != "not_applicable" and not rule.corpus_cases
    )
    rules_missing_mutation_applicability = sorted(
        rule.id for rule in catalog.rules if rule.mutation_applicability in (None, "unspecified")
    )
    rules_missing_suppression_modes = sorted(rule.id for rule in catalog.rules if rule.suppression_modes is None)
    rules_missing_incremental_safety_markers = sorted(
        rule.id for rule in catalog.rules if rule.incremental_safe is None
    )
    promised_output_artifacts = sorted(
        {output for analyzer in analyzers for output in analyzer.delivery.output_artifacts}
    )
    delivered_output_artifacts = sorted(
        {analyzer.summary_output for analyzer in analyzers}
        | {output for rule in catalog.rules for output in rule.outputs}
    )
    missing_output_artifacts = sorted(
        output for output in promised_output_artifacts if output not in delivered_output_artifacts
    )

    findings: list[dict[str, Any]] = []
    missing_cli_filters = sorted(
        kind for kind, supported in summary_supported.items() if supported and kind not in cli_filter_kinds
    )
    if missing_cli_filters:
        findings.append(
            {
                "id": "cli-variable-filter-gap",
                "severity": "medium",
                "message": "Some variable issue kinds are rendered in reports but not exposed as CLI quick filters.",
                "missing_issue_kinds": missing_cli_filters,
            }
        )

    if declared_cli_analyzers != actual_cli_analyzers:
        findings.append(
            {
                "id": "cli-analyzer-metadata-drift",
                "severity": "medium",
                "message": "Analyzer metadata and the default CLI analyzer subset disagree about which checks are directly exposed.",
                "declared_cli_analyzers": declared_cli_analyzers,
                "actual_cli_analyzers": actual_cli_analyzers,
            }
        )

    if declared_lsp_analyzers != semantic_layer_sources:
        findings.append(
            {
                "id": "lsp-analyzer-metadata-drift",
                "severity": "medium",
                "message": "Analyzer metadata and the semantic-layer/LSP rule sources disagree about which checks surface in editor diagnostics.",
                "declared_lsp_analyzers": declared_lsp_analyzers,
                "actual_lsp_analyzers": semantic_layer_sources,
            }
        )

    if analyzers_missing_exposure:
        findings.append(
            {
                "id": "analyzer-exposure-gap",
                "severity": "medium",
                "message": "Some enabled analyzers are registered and tested but still have no declared delivery surface.",
                "missing_analyzers": analyzers_missing_exposure,
            }
        )

    if analyzers_missing_acceptance_tests:
        findings.append(
            {
                "id": "analyzer-acceptance-test-gap",
                "severity": "medium",
                "message": "Some enabled analyzers do not declare acceptance-test coverage.",
                "missing_analyzers": analyzers_missing_acceptance_tests,
            }
        )

    if rules_missing_acceptance_tests:
        findings.append(
            {
                "id": "rule-acceptance-test-gap",
                "severity": "medium",
                "message": "Some semantic rules do not declare acceptance-test coverage.",
                "missing_rule_ids": rules_missing_acceptance_tests,
            }
        )

    if rules_missing_corpus_links:
        findings.append(
            {
                "id": "rule-corpus-link-gap",
                "severity": "medium",
                "message": "Some semantic rules are not linked to any checked-in corpus manifest cases.",
                "missing_rule_ids": rules_missing_corpus_links,
            }
        )

    if rules_missing_mutation_applicability:
        findings.append(
            {
                "id": "rule-mutation-metadata-gap",
                "severity": "medium",
                "message": "Some semantic rules do not declare mutation applicability metadata.",
                "missing_rule_ids": rules_missing_mutation_applicability,
            }
        )

    if rules_missing_suppression_modes:
        findings.append(
            {
                "id": "rule-suppression-metadata-gap",
                "severity": "medium",
                "message": "Some semantic rules do not declare suppression metadata.",
                "missing_rule_ids": rules_missing_suppression_modes,
            }
        )

    if rules_missing_incremental_safety_markers:
        findings.append(
            {
                "id": "rule-incremental-safety-gap",
                "severity": "medium",
                "message": "Some semantic rules do not declare whether incremental analysis is safe.",
                "missing_rule_ids": rules_missing_incremental_safety_markers,
            }
        )

    if missing_output_artifacts:
        findings.append(
            {
                "id": "analyzer-output-artifact-gap",
                "severity": "medium",
                "message": "Some analyzer metadata promises output artifacts that are not represented in the analyzer catalog outputs.",
                "missing_outputs": missing_output_artifacts,
            }
        )

    _append_structural_budget_findings(findings, structural_budgets)

    phase2_rule_metadata_gate = collect_phase2_rule_metadata_gate({"findings": findings})

    return {
        "registered_analyzers": registry_keys,
        "live_diagnostic_analyzers": live_diagnostic_analyzers,
        "declared_cli_analyzers": declared_cli_analyzers,
        "actual_cli_analyzers": actual_cli_analyzers,
        "declared_lsp_analyzers": declared_lsp_analyzers,
        "actual_lsp_analyzers": semantic_layer_sources,
        "analyzers_missing_exposure": analyzers_missing_exposure,
        "analyzers_missing_acceptance_tests": analyzers_missing_acceptance_tests,
        "rules_missing_acceptance_tests": rules_missing_acceptance_tests,
        "rules_missing_corpus_links": rules_missing_corpus_links,
        "rules_missing_mutation_applicability": rules_missing_mutation_applicability,
        "rules_missing_suppression_modes": rules_missing_suppression_modes,
        "rules_missing_incremental_safety_markers": rules_missing_incremental_safety_markers,
        "promised_output_artifacts": promised_output_artifacts,
        "delivered_output_artifacts": delivered_output_artifacts,
        "cli_variable_filter_issue_kinds": cli_filter_kinds,
        "variables_report_summary_support": summary_supported,
        "structural_budgets": structural_budgets,
        "phase2_rule_metadata_gate": phase2_rule_metadata_gate,
        "findings": findings,
    }


def collect_analyzer_registry_report() -> dict[str, Any]:
    catalog = get_default_analyzer_catalog()
    return catalog.to_report(generated_by="sattlint.devtools.pipeline")


def _structural_entry_files(
    workspace_root: Path,
    program_files: tuple[Path, ...],
) -> tuple[Path, ...]:
    scoped_files = tuple(
        path
        for path in program_files
        if any(
            path.resolve().is_relative_to((workspace_root / relative_root).resolve())
            for relative_root in STRUCTURAL_ENTRY_ROOTS
        )
    )
    return scoped_files or program_files


def _structural_report_discovery(workspace_root: Path, discovery: Any) -> Any:
    selected_program_files = _structural_entry_files(workspace_root, tuple(discovery.program_files))
    if selected_program_files == tuple(discovery.program_files):
        return discovery
    return type(discovery)(
        workspace_root=discovery.workspace_root,
        source_dirs=discovery.source_dirs,
        program_files=selected_program_files,
        dependency_files=discovery.dependency_files,
        abb_lib_dir=discovery.abb_lib_dir,
        program_files_by_stem=discovery.program_files_by_stem,
        dependency_files_by_stem=discovery.dependency_files_by_stem,
    )


def collect_workspace_graph_inputs(
    workspace_root: Path = REPO_ROOT,
) -> WorkspaceGraphInputs:
    discovery = discover_workspace_sources(workspace_root)
    snapshots: list[Any] = []
    failures: list[dict[str, Any]] = []

    for entry_file in discovery.program_files:
        try:
            snapshot = load_workspace_snapshot(
                entry_file,
                workspace_root=workspace_root,
                collect_variable_diagnostics=False,
                _analysis_provider=build_variable_semantic_artifacts,
            )
        except Exception as exc:
            failures.append(
                {
                    "entry_file": sanitize_path_for_report(entry_file, repo_root=workspace_root),
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            )
            continue
        snapshots.append(snapshot)

    return WorkspaceGraphInputs(
        discovery=discovery,
        snapshots=snapshots,
        snapshot_failures=failures,
    )


def _accumulate_dependency_graph_snapshot(
    snapshot: Any,
    *,
    workspace_root: Path,
    node_index: dict[str, dict[str, Any]],
    edge_index: dict[tuple[str, str], dict[str, Any]],
) -> None:
    entry_file = sanitize_path_for_report(snapshot.entry_file, repo_root=workspace_root)
    for source, targets in sorted(snapshot.project_graph.library_dependencies.items()):
        node_index.setdefault(source, {"id": source, "kind": "library"})
        for target in sorted(targets):
            node_index.setdefault(target, {"id": target, "kind": "library"})
            key = (source.casefold(), target.casefold())
            edge = edge_index.setdefault(
                key,
                {
                    "source": source,
                    "target": target,
                    "kind": "depends_on",
                    "entries": set(),
                },
            )
            edge["entries"].add(entry_file)


def _accumulate_call_graph_snapshot(
    snapshot: Any,
    *,
    workspace_root: Path,
    node_index: dict[str, dict[str, Any]],
    edge_index: dict[tuple[str, str], dict[str, Any]],
) -> None:
    entry_file = sanitize_path_for_report(snapshot.entry_file, repo_root=workspace_root)
    root_module = getattr(snapshot.base_picture, "name", snapshot.entry_file.stem)
    for definition, accesses in _iter_snapshot_accesses_by_definition(snapshot):
        target_path = definition.declaration_module_path or (root_module,)
        target_module = ".".join(target_path)
        node_index.setdefault(target_module.casefold(), {"id": target_module, "kind": "module"})

        for access in accesses:
            source_path = access.use_module_path or (root_module,)
            source_module = ".".join(source_path)
            node_index.setdefault(source_module.casefold(), {"id": source_module, "kind": "module"})

            key = (source_module.casefold(), target_module.casefold())
            edge = edge_index.setdefault(
                key,
                {
                    "source": source_module,
                    "target": target_module,
                    "kind": "module-access",
                    "reads": 0,
                    "writes": 0,
                    "symbols": set(),
                    "entries": set(),
                },
            )
            access_kind = getattr(access.kind, "value", access.kind)
            if access_kind == "read":
                edge["reads"] += 1
            elif access_kind == "write":
                edge["writes"] += 1
            edge["symbols"].add(definition.canonical_path)
            edge["entries"].add(entry_file)


def _build_dependency_graph_report(
    *,
    workspace_root: Path,
    discovery: Any,
    node_index: dict[str, dict[str, Any]],
    edge_index: dict[tuple[str, str], dict[str, Any]],
    snapshot_count: int,
    snapshot_failures: list[dict[str, Any]],
) -> dict[str, Any]:
    edges = [
        {
            "source": edge["source"],
            "target": edge["target"],
            "kind": edge["kind"],
            "entries": sorted(edge["entries"]),
        }
        for edge in sorted(
            edge_index.values(),
            key=lambda item: (item["source"].casefold(), item["target"].casefold()),
        )
    ]

    return {
        "generated_by": "sattlint.devtools.pipeline",
        "workspace_root": sanitize_path_for_report(workspace_root, repo_root=workspace_root),
        "source_files": {
            "program_files": [
                sanitize_path_for_report(path, repo_root=workspace_root) for path in discovery.program_files
            ],
            "dependency_files": [
                sanitize_path_for_report(path, repo_root=workspace_root) for path in discovery.dependency_files
            ],
        },
        "nodes": sorted(node_index.values(), key=lambda item: item["id"].casefold()),
        "edges": edges,
        "snapshot_count": snapshot_count,
        "snapshot_failures": snapshot_failures,
    }


def _build_call_graph_report(
    *,
    workspace_root: Path,
    node_index: dict[str, dict[str, Any]],
    edge_index: dict[tuple[str, str], dict[str, Any]],
    snapshot_count: int,
    snapshot_failures: list[dict[str, Any]],
) -> dict[str, Any]:
    edges = [
        {
            "source": edge["source"],
            "target": edge["target"],
            "kind": edge["kind"],
            "reads": edge["reads"],
            "writes": edge["writes"],
            "access_count": edge["reads"] + edge["writes"],
            "symbol_count": len(edge["symbols"]),
            "symbols": sorted(edge["symbols"]),
            "entries": sorted(edge["entries"]),
        }
        for edge in sorted(
            edge_index.values(),
            key=lambda item: (item["source"].casefold(), item["target"].casefold()),
        )
    ]

    return {
        "generated_by": "sattlint.devtools.pipeline",
        "workspace_root": sanitize_path_for_report(workspace_root, repo_root=workspace_root),
        "graph_kind": "module-access",
        "nodes": sorted(node_index.values(), key=lambda item: item["id"].casefold()),
        "edges": edges,
        "snapshot_count": snapshot_count,
        "snapshot_failures": snapshot_failures,
    }


def _should_emit_snapshot_progress(index: int, total: int) -> bool:
    if total <= 10:
        return True
    if index in {1, total}:
        return True
    return index % 10 == 0


def _stream_workspace_graph_reports(
    workspace_root: Path,
    *,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[WorkspaceGraphInputs, dict[str, Any], dict[str, Any]]:
    full_discovery = discover_workspace_sources(workspace_root)
    discovery = _structural_report_discovery(workspace_root, full_discovery)
    snapshot_failures: list[dict[str, Any]] = []
    dependency_node_index: dict[str, dict[str, Any]] = {}
    dependency_edge_index: dict[tuple[str, str], dict[str, Any]] = {}
    call_node_index: dict[str, dict[str, Any]] = {}
    call_edge_index: dict[tuple[str, str], dict[str, Any]] = {}
    total_program_files = len(discovery.program_files)
    snapshot_count = 0

    for index, entry_file in enumerate(discovery.program_files, start=1):
        sanitized_entry = sanitize_path_for_report(entry_file, repo_root=workspace_root) or entry_file.name
        if progress_callback is not None and _should_emit_snapshot_progress(index, total_program_files):
            progress_callback(f"Structural: loading {index}/{total_program_files} {sanitized_entry}")
        try:
            snapshot = load_workspace_snapshot(
                entry_file,
                workspace_root=workspace_root,
                discovery=full_discovery,
                collect_variable_diagnostics=False,
                _analysis_provider=build_variable_semantic_artifacts,
            )
        except Exception as exc:
            snapshot_failures.append(
                {
                    "entry_file": sanitized_entry,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            )
            if progress_callback is not None:
                progress_callback(
                    f"Structural: failed {index}/{total_program_files} {sanitized_entry} ({type(exc).__name__})"
                )
            continue

        snapshot_count += 1
        _accumulate_dependency_graph_snapshot(
            snapshot,
            workspace_root=workspace_root,
            node_index=dependency_node_index,
            edge_index=dependency_edge_index,
        )
        _accumulate_call_graph_snapshot(
            snapshot,
            workspace_root=workspace_root,
            node_index=call_node_index,
            edge_index=call_edge_index,
        )

    graph_inputs = WorkspaceGraphInputs(
        discovery=discovery,
        snapshots=[],
        snapshot_failures=snapshot_failures,
    )
    dependency_graph_report = _build_dependency_graph_report(
        workspace_root=workspace_root,
        discovery=discovery,
        node_index=dependency_node_index,
        edge_index=dependency_edge_index,
        snapshot_count=snapshot_count,
        snapshot_failures=snapshot_failures,
    )
    call_graph_report = _build_call_graph_report(
        workspace_root=workspace_root,
        node_index=call_node_index,
        edge_index=call_edge_index,
        snapshot_count=snapshot_count,
        snapshot_failures=snapshot_failures,
    )
    return graph_inputs, dependency_graph_report, call_graph_report


def collect_dependency_graph_report(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: WorkspaceGraphInputs | tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    resolved_inputs = _normalize_graph_inputs(graph_inputs, workspace_root=workspace_root)

    node_index: dict[str, dict[str, Any]] = {}
    edge_index: dict[tuple[str, str], dict[str, Any]] = {}

    for snapshot in resolved_inputs.snapshots:
        _accumulate_dependency_graph_snapshot(
            snapshot,
            workspace_root=workspace_root,
            node_index=node_index,
            edge_index=edge_index,
        )

    return _build_dependency_graph_report(
        workspace_root=workspace_root,
        discovery=resolved_inputs.discovery,
        node_index=node_index,
        edge_index=edge_index,
        snapshot_count=len(resolved_inputs.snapshots),
        snapshot_failures=resolved_inputs.snapshot_failures,
    )


def collect_call_graph_report(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: WorkspaceGraphInputs | tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    resolved_inputs = _normalize_graph_inputs(graph_inputs, workspace_root=workspace_root)

    node_index: dict[str, dict[str, Any]] = {}
    edge_index: dict[tuple[str, str], dict[str, Any]] = {}

    for snapshot in resolved_inputs.snapshots:
        _accumulate_call_graph_snapshot(
            snapshot,
            workspace_root=workspace_root,
            node_index=node_index,
            edge_index=edge_index,
        )

    return _build_call_graph_report(
        workspace_root=workspace_root,
        node_index=node_index,
        edge_index=edge_index,
        snapshot_count=len(resolved_inputs.snapshots),
        snapshot_failures=resolved_inputs.snapshot_failures,
    )


def _iter_snapshot_accesses_by_definition(
    snapshot: Any,
) -> Iterator[tuple[Any, tuple[Any, ...] | list[Any]]]:
    iterator = getattr(snapshot, "iter_access_events_by_definition", None)
    if callable(iterator):
        iterable = cast(Iterable[tuple[Any, tuple[Any, ...] | list[Any]]], iterator(roots_only=True))
        yield from iterable
        return

    for definition in snapshot.definitions:
        if definition.field_path is not None:
            continue
        yield definition, snapshot.find_accesses_to(definition)


def _serialize_invoke_coord(header: ModuleHeader) -> dict[str, Any]:
    return {
        "coords": [float(value) for value in header.invoke_coord],
        "arguments": list(getattr(header, "invocation_arguments", ()) or ()),
        "layer": header.layer_info,
        "zoom_limits": ([float(value) for value in header.zoom_limits] if header.zoom_limits is not None else None),
        "zoomable": bool(header.zoomable),
    }


def _serialize_moduledef(moduledef: ModuleDef | None) -> dict[str, Any] | None:
    if moduledef is None:
        return None

    clipping_origin: list[float] | None = None
    clipping_size: list[float] | None = None
    if moduledef.clipping_bounds is not None:
        clipping_origin = [float(value) for value in moduledef.clipping_bounds[0]]
        clipping_size = [float(value) for value in moduledef.clipping_bounds[1]]

    return {
        "clipping_origin": clipping_origin,
        "clipping_size": clipping_size,
        "zoom_limits": (
            [float(value) for value in moduledef.zoom_limits] if moduledef.zoom_limits is not None else None
        ),
        "grid": float(moduledef.grid),
        "zoomable": bool(moduledef.zoomable),
    }


def _stable_json_marker(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _graphics_field_value(entry: dict[str, Any], field_name: str) -> Any:
    value: Any = entry
    for segment in field_name.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(segment)
    return value


def _graphics_layout_group_payload(
    *,
    module_kind: str,
    module_name: str,
    members: list[dict[str, Any]],
) -> dict[str, Any]:
    differing_fields: list[str] = []
    field_variants: dict[str, list[Any]] = {}

    for field_name in _GRAPHICS_LAYOUT_COMPARISON_FIELDS:
        variants: dict[str, Any] = {}
        for member in members:
            value = _graphics_field_value(member, field_name)
            variants.setdefault(_stable_json_marker(value), value)
        if len(variants) > 1:
            differing_fields.append(field_name)
            field_variants[field_name] = list(variants.values())

    return {
        "group_key": f"{module_kind}:{module_name.casefold()}",
        "module_kind": module_kind,
        "module_name": module_name,
        "status": "drift" if differing_fields else "consistent",
        "entry_count": len(members),
        "module_paths": [member["module_path"] for member in members],
        "differing_fields": differing_fields,
        "field_variants": field_variants,
    }


def _graphics_layout_entry(
    *,
    workspace_root: Path,
    entry_file: Path,
    module_path: tuple[str, ...],
    module_kind: str,
    header: ModuleHeader,
    moduledef: ModuleDef | None,
    definition_scope: str,
    moduledef_origin_kind: str,
    moduletype_name: str | None = None,
    resolved_moduletype: ModuleTypeDef | None = None,
    resolution_error: str | None = None,
) -> dict[str, Any]:
    relative_path = ".".join(module_path[1:]) if len(module_path) > 1 else ""
    module_name = module_path[-1] if module_path else ""
    payload = {
        "entry_file": sanitize_path_for_report(entry_file, repo_root=workspace_root),
        "module_path": ".".join(module_path),
        "relative_module_path": relative_path,
        "module_name": module_name,
        "module_kind": module_kind,
        "definition_scope": definition_scope,
        "moduledef_origin_kind": moduledef_origin_kind,
        "invocation": _serialize_invoke_coord(header),
        "moduledef": _serialize_moduledef(moduledef),
    }
    if moduletype_name is not None:
        payload["moduletype_name"] = moduletype_name
    if resolved_moduletype is not None:
        payload["resolved_moduletype"] = {
            "name": resolved_moduletype.name,
            "origin_file": resolved_moduletype.origin_file,
            "origin_lib": resolved_moduletype.origin_lib,
        }
    if resolution_error is not None:
        payload["resolution_error"] = resolution_error
    return payload


def _walk_graphics_layout_children(
    *,
    bp: BasePicture,
    children: list[SingleModule | FrameModule | ModuleTypeInstance],
    entry_file: Path,
    workspace_root: Path,
    snapshot: Any,
    entries: list[dict[str, Any]],
    parent_path: tuple[str, ...],
    current_library: str | None,
    definition_scope: str,
    active_moduletype_keys: set[tuple[str, str]],
) -> None:
    unavailable_libraries = getattr(snapshot.project_graph, "unavailable_libraries", set())

    for child in children:
        child_path = (*parent_path, child.header.name)
        if isinstance(child, SingleModule):
            entries.append(
                _graphics_layout_entry(
                    workspace_root=workspace_root,
                    entry_file=entry_file,
                    module_path=child_path,
                    module_kind="module",
                    header=child.header,
                    moduledef=child.moduledef,
                    definition_scope=definition_scope,
                    moduledef_origin_kind="local-module",
                )
            )
            _walk_graphics_layout_children(
                bp=bp,
                children=child.submodules or [],
                entry_file=entry_file,
                workspace_root=workspace_root,
                snapshot=snapshot,
                entries=entries,
                parent_path=child_path,
                current_library=current_library,
                definition_scope=definition_scope,
                active_moduletype_keys=active_moduletype_keys,
            )
            continue

        if isinstance(child, FrameModule):
            entries.append(
                _graphics_layout_entry(
                    workspace_root=workspace_root,
                    entry_file=entry_file,
                    module_path=child_path,
                    module_kind="frame",
                    header=child.header,
                    moduledef=child.moduledef,
                    definition_scope=definition_scope,
                    moduledef_origin_kind="local-module",
                )
            )
            _walk_graphics_layout_children(
                bp=bp,
                children=child.submodules or [],
                entry_file=entry_file,
                workspace_root=workspace_root,
                snapshot=snapshot,
                entries=entries,
                parent_path=child_path,
                current_library=current_library,
                definition_scope=definition_scope,
                active_moduletype_keys=active_moduletype_keys,
            )
            continue

        resolved_moduletype: ModuleTypeDef | None = None
        resolution_error: str | None = None
        try:
            resolved_moduletype = resolve_moduletype_def_strict(
                bp,
                child.moduletype_name,
                current_library=current_library,
                unavailable_libraries=unavailable_libraries,
            )
        except Exception as exc:
            resolution_error = str(exc)

        entries.append(
            _graphics_layout_entry(
                workspace_root=workspace_root,
                entry_file=entry_file,
                module_path=child_path,
                module_kind="moduletype-instance",
                header=child.header,
                moduledef=(resolved_moduletype.moduledef if resolved_moduletype is not None else None),
                definition_scope=definition_scope,
                moduledef_origin_kind=(
                    "moduletype-definition" if resolved_moduletype is not None else "unresolved-moduletype"
                ),
                moduletype_name=child.moduletype_name,
                resolved_moduletype=resolved_moduletype,
                resolution_error=resolution_error,
            )
        )
        if resolved_moduletype is None:
            continue

        moduletype_key = (
            (resolved_moduletype.origin_lib or current_library or "").casefold(),
            resolved_moduletype.name.casefold(),
        )
        if moduletype_key in active_moduletype_keys:
            continue

        active_moduletype_keys.add(moduletype_key)
        try:
            _walk_graphics_layout_children(
                bp=bp,
                children=resolved_moduletype.submodules or [],
                entry_file=entry_file,
                workspace_root=workspace_root,
                snapshot=snapshot,
                entries=entries,
                parent_path=child_path,
                current_library=resolved_moduletype.origin_lib or current_library,
                definition_scope=f"moduletype:{resolved_moduletype.name}",
                active_moduletype_keys=active_moduletype_keys,
            )
        finally:
            active_moduletype_keys.discard(moduletype_key)


def collect_graphics_layout_report(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: WorkspaceGraphInputs | tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    resolved_inputs = _normalize_graph_inputs(graph_inputs, workspace_root=workspace_root)
    entries: list[dict[str, Any]] = []

    for snapshot in resolved_inputs.snapshots:
        bp = snapshot.base_picture
        root_path = (bp.header.name,)
        entries.append(
            _graphics_layout_entry(
                workspace_root=workspace_root,
                entry_file=snapshot.entry_file,
                module_path=root_path,
                module_kind="basepicture",
                header=bp.header,
                moduledef=bp.moduledef,
                definition_scope="root",
                moduledef_origin_kind="local-module",
            )
        )
        _walk_graphics_layout_children(
            bp=bp,
            children=bp.submodules or [],
            entry_file=snapshot.entry_file,
            workspace_root=workspace_root,
            snapshot=snapshot,
            entries=entries,
            parent_path=root_path,
            current_library=getattr(bp, "origin_lib", None),
            definition_scope="root",
            active_moduletype_keys=set(),
        )

    entries.sort(key=lambda item: (item["entry_file"] or "", item["module_path"].casefold()))

    grouped_entries: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        if entry["module_kind"] == "basepicture":
            continue
        grouped_entries.setdefault(
            (entry["module_kind"], entry["module_name"].casefold()),
            [],
        ).append(entry)

    groups = [
        _graphics_layout_group_payload(
            module_kind=members[0]["module_kind"],
            module_name=members[0]["module_name"],
            members=members,
        )
        for _key, members in sorted(grouped_entries.items(), key=lambda item: item[0])
        if len(members) > 1
    ]
    findings = [
        {
            "id": "graphics-layout-drift",
            "severity": "medium",
            "message": (
                f"Repeated {group['module_kind']} modules named {group['module_name']!r} "
                "have inconsistent graphics layout settings."
            ),
            "module_kind": group["module_kind"],
            "module_name": group["module_name"],
            "entry_count": group["entry_count"],
            "differing_fields": group["differing_fields"],
            "module_paths": group["module_paths"],
        }
        for group in groups
        if group["status"] == "drift"
    ]

    return {
        "generated_by": "sattlint.devtools.pipeline",
        "report_kind": "graphics-layout",
        "workspace_root": sanitize_path_for_report(workspace_root, repo_root=workspace_root),
        "comparison_fields": list(_GRAPHICS_LAYOUT_COMPARISON_FIELDS),
        "entries": entries,
        "groups": groups,
        "findings": findings,
        "snapshot_count": len(resolved_inputs.snapshots),
        "snapshot_failures": resolved_inputs.snapshot_failures,
    }


def collect_structural_reports(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: WorkspaceGraphInputs | tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> StructuralReportsBundle:
    architecture_report = collect_architecture_report()
    analyzer_registry_report = collect_analyzer_registry_report()
    if graph_inputs is None:
        resolved_graph_inputs, dependency_graph_report, call_graph_report = _stream_workspace_graph_reports(
            workspace_root,
            progress_callback=progress_callback,
        )
    else:
        resolved_graph_inputs = _normalize_graph_inputs(graph_inputs, workspace_root=workspace_root)
        dependency_graph_report = collect_dependency_graph_report(
            workspace_root,
            graph_inputs=resolved_graph_inputs,
        )
        call_graph_report = collect_call_graph_report(
            workspace_root,
            graph_inputs=resolved_graph_inputs,
        )
    graphics_layout_report = collect_graphics_layout_report(
        workspace_root,
        graph_inputs=resolved_graph_inputs,
    )
    impact_analysis_report = collect_impact_analysis_report(
        workspace_root,
        graph_inputs=resolved_graph_inputs,
        dependency_graph_report=dependency_graph_report,
        call_graph_report=call_graph_report,
    )
    return StructuralReportsBundle(
        architecture_report=architecture_report,
        analyzer_registry_report=analyzer_registry_report,
        graph_inputs=resolved_graph_inputs,
        dependency_graph_report=dependency_graph_report,
        call_graph_report=call_graph_report,
        graphics_layout_report=graphics_layout_report,
        impact_analysis_report=impact_analysis_report,
    )


def _normalize_graph_inputs(
    graph_inputs: WorkspaceGraphInputs | tuple[Any, list[Any], list[dict[str, Any]]] | None,
    *,
    workspace_root: Path,
) -> WorkspaceGraphInputs:
    if graph_inputs is None:
        return collect_workspace_graph_inputs(workspace_root)
    if isinstance(graph_inputs, WorkspaceGraphInputs):
        return graph_inputs
    discovery, snapshots, failures = graph_inputs
    return WorkspaceGraphInputs(
        discovery=discovery,
        snapshots=list(snapshots),
        snapshot_failures=list(failures),
    )


def _dedupe_snapshot_failures(*failure_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    failures: list[dict[str, Any]] = []
    for items in failure_lists:
        for item in items:
            marker = repr(sorted(item.items()))
            if marker in seen:
                continue
            seen.add(marker)
            failures.append(item)
    return failures


def _collect_reverse_impact(
    node_id: str,
    incoming_edges: dict[str, list[dict[str, Any]]],
    *,
    list_fields: tuple[str, ...] = (),
    count_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    direct_dependents: set[str] = set()
    direct_entry_files: set[str] = set()
    direct_list_values: dict[str, set[str]] = {field: set() for field in list_fields}
    direct_count_values = dict.fromkeys(count_fields, 0)

    for edge in incoming_edges.get(node_id, []):
        direct_dependents.add(edge["source"])
        direct_entry_files.update(edge.get("entries", []))
        for field in list_fields:
            direct_list_values[field].update(edge.get(field, []))
        for field in count_fields:
            direct_count_values[field] += int(edge.get(field, 0))

    transitive_dependents: set[str] = set()
    transitive_entry_files: set[str] = set()
    transitive_list_values: dict[str, set[str]] = {field: set() for field in list_fields}
    transitive_count_values = dict.fromkeys(count_fields, 0)
    pending = [node_id]
    visited_targets: set[str] = set()

    while pending:
        target = pending.pop()
        target_key = target.casefold()
        if target_key in visited_targets:
            continue
        visited_targets.add(target_key)
        for edge in incoming_edges.get(target, []):
            source = edge["source"]
            transitive_dependents.add(source)
            transitive_entry_files.update(edge.get("entries", []))
            for field in list_fields:
                transitive_list_values[field].update(edge.get(field, []))
            for field in count_fields:
                transitive_count_values[field] += int(edge.get(field, 0))
            pending.append(source)

    impact = {
        "direct_dependents": sorted(direct_dependents, key=str.casefold),
        "transitive_dependents": sorted(transitive_dependents, key=str.casefold),
        "direct_entry_files": sorted(direct_entry_files, key=str.casefold),
        "transitive_entry_files": sorted(transitive_entry_files, key=str.casefold),
        "direct_dependent_count": len(direct_dependents),
        "transitive_dependent_count": len(transitive_dependents),
    }
    for field in list_fields:
        direct_values = sorted(direct_list_values[field], key=str.casefold)
        transitive_values = sorted(transitive_list_values[field], key=str.casefold)
        impact[f"direct_{field}"] = direct_values
        impact[f"transitive_{field}"] = transitive_values
        impact[f"direct_{field[:-1]}_count"] = len(direct_values)
        impact[f"transitive_{field[:-1]}_count"] = len(transitive_values)
    for field in count_fields:
        impact[f"direct_{field}"] = direct_count_values[field]
        impact[f"transitive_{field}"] = transitive_count_values[field]
    return impact


def _parse_ratchet_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check the structural budget ratchet against the current repository metrics."
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Repository root to scan for structural budget metrics",
    )
    parser.add_argument(
        "--ratchet-path",
        default=None,
        help="Optional override path for the structural budget ratchet JSON file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the ratchet status payload as JSON instead of the human-readable summary",
    )
    return parser.parse_args(list(argv) if argv is not None else sys.argv[1:])


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_ratchet_args(argv)
    repo_root = Path(args.repo_root).resolve()
    ratchet_path = None if args.ratchet_path is None else Path(args.ratchet_path).resolve()

    report = collect_structural_budget_report(repo_root, ratchet_path=ratchet_path)
    ratchet = report["ratchet"]

    if args.json:
        print(json.dumps(ratchet, indent=2))
    else:
        print(f"Structural ratchet: {ratchet['status']}")
        print(f"Ratchet file: {ratchet['path']}")
        regressions = ratchet.get("regressions", [])
        if regressions:
            print("Regressions:")
            for regression in regressions:
                if "metric" in regression:
                    print(f"  - {regression['metric']}: {regression['actual']} > {regression['expected_max']}")
                else:
                    print(
                        f"  - {regression['path']}: {regression['actual']} > {regression['expected_max']}"
                        f" ({regression['reason']})"
                    )
        else:
            print("Regressions: []")

    return 0 if ratchet["status"] == "pass" else 1


__all__ = [
    "StructuralReportsBundle",
    "WorkspaceGraphInputs",
    "collect_analyzer_registry_report",
    "collect_architecture_report",
    "collect_call_graph_report",
    "collect_dependency_graph_report",
    "collect_graphics_layout_report",
    "collect_impact_analysis_report",
    "collect_phase2_rule_metadata_gate",
    "collect_structural_reports",
    "collect_workspace_graph_inputs",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
