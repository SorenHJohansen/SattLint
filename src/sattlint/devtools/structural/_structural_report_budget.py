"""Structural budget report helpers."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

from sattlint.devtools.json_helpers import json_mapping as _json_mapping

from ._structural_report_budget_support import (
    _collect_facade_private_entrypoints,
    _evaluate_structural_budget_ratchet,
    _normalize_file_line_exceptions,
    build_known_structural_modules,
    collect_python_structural_surface_metrics,
)


def _is_structural_budget_python_path(rel_path: str) -> bool:
    return rel_path.endswith(".py") and rel_path.startswith(("src/", "tests/", "scripts/"))


def _load_structural_budget_ratchet(
    repo_root: Path,
    *,
    ratchet_path: Path | None = None,
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module  # noqa: PLC0415

    resolved_path = ratchet_path or (repo_root / structural_reports_module.STRUCTURAL_BUDGET_RATCHET_PATH)
    sanitized_path = structural_reports_module.sanitize_path_for_report(resolved_path, repo_root=repo_root)
    sanitized_path = sanitized_path or resolved_path.as_posix()
    if not resolved_path.exists():
        return {"status": "missing", "path": sanitized_path, "metrics": {}, "file_line_exceptions": {}}

    try:
        payload = _json_mapping(json.loads(resolved_path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid",
            "path": sanitized_path,
            "metrics": {},
            "file_line_exceptions": {},
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
    if payload is None:
        return {
            "status": "invalid",
            "path": sanitized_path,
            "metrics": {},
            "file_line_exceptions": {},
            "error": "ratchet payload must be a JSON object",
            "error_type": "ValueError",
        }

    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        return {
            "status": "invalid",
            "path": sanitized_path,
            "metrics": {},
            "file_line_exceptions": {},
            "error": "ratchet metrics must be a JSON object with integer values",
            "error_type": "ValueError",
        }
    metrics_dict = cast(dict[str, Any], metrics)
    if any(not isinstance(value, int) for value in metrics_dict.values()):
        return {
            "status": "invalid",
            "path": sanitized_path,
            "metrics": {},
            "file_line_exceptions": {},
            "error": "ratchet metrics must be a JSON object with integer values",
            "error_type": "ValueError",
        }

    try:
        file_line_exceptions = {
            rel_path: entry
            for rel_path, entry in _normalize_file_line_exceptions(
                payload.get("file_line_exceptions"), label=sanitized_path
            ).items()
            if _is_structural_budget_python_path(rel_path)
        }
    except ValueError as exc:
        return {
            "status": "invalid",
            "path": sanitized_path,
            "metrics": {},
            "file_line_exceptions": {},
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

    file_debt_path = repo_root / structural_reports_module.FILE_DEBT_RATCHET_PATH
    if file_debt_path.exists():
        try:
            file_debt_payload = _json_mapping(json.loads(file_debt_path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return {
                "status": "invalid",
                "path": sanitized_path,
                "metrics": {},
                "file_line_exceptions": {},
                "error": (f"{structural_reports_module.FILE_DEBT_RATCHET_PATH.as_posix()} could not be loaded: {exc}"),
                "error_type": type(exc).__name__,
            }
        if file_debt_payload is None:
            return {
                "status": "invalid",
                "path": sanitized_path,
                "metrics": {},
                "file_line_exceptions": {},
                "error": f"{structural_reports_module.FILE_DEBT_RATCHET_PATH.as_posix()} must be a JSON object.",
                "error_type": "ValueError",
            }

        files_payload = file_debt_payload.get("files")
        if not isinstance(files_payload, dict):
            return {
                "status": "invalid",
                "path": sanitized_path,
                "metrics": {},
                "file_line_exceptions": {},
                "error": f"{structural_reports_module.FILE_DEBT_RATCHET_PATH.as_posix()} files must be a JSON object.",
                "error_type": "ValueError",
            }

        for raw_path, dimension_payload in cast(dict[object, object], files_payload).items():
            if not isinstance(raw_path, str) or not isinstance(dimension_payload, dict):
                return {
                    "status": "invalid",
                    "path": sanitized_path,
                    "metrics": {},
                    "file_line_exceptions": {},
                    "error": (
                        f"{structural_reports_module.FILE_DEBT_RATCHET_PATH.as_posix()} contains an invalid structural debt entry."
                    ),
                    "error_type": "ValueError",
                }

            dimension_payload_dict = cast(dict[str, Any], dimension_payload)
            raw_structural_payload = dimension_payload_dict.get("structural")
            if raw_structural_payload is None:
                continue
            structural_payload = _json_mapping(raw_structural_payload)
            if structural_payload is None:
                return {
                    "status": "invalid",
                    "path": sanitized_path,
                    "metrics": {},
                    "file_line_exceptions": {},
                    "error": (
                        f"{structural_reports_module.FILE_DEBT_RATCHET_PATH.as_posix()} structural debt for {raw_path!r} must be a JSON object."
                    ),
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
                        f"{structural_reports_module.FILE_DEBT_RATCHET_PATH.as_posix()} structural debt for {raw_path!r} must include "
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
                        f"{structural_reports_module.FILE_DEBT_RATCHET_PATH.as_posix()} structural debt for {raw_path!r} must include a non-empty reason."
                    ),
                    "error_type": "ValueError",
                }

            normalized_path = raw_path.replace("\\", "/").strip("/")
            if not _is_structural_budget_python_path(normalized_path):
                continue
            existing = file_line_exceptions.get(normalized_path)
            normalized_entry = {"max_lines": max_lines, "reason": reason.strip()}
            if existing is not None and existing != normalized_entry:
                return {
                    "status": "invalid",
                    "path": sanitized_path,
                    "metrics": {},
                    "file_line_exceptions": {},
                    "error": (
                        f"{structural_reports_module.FILE_DEBT_RATCHET_PATH.as_posix()} structural debt for {normalized_path!r} conflicts with "
                        f"{structural_reports_module.STRUCTURAL_BUDGET_RATCHET_PATH.as_posix()} file_line_exceptions."
                    ),
                    "error_type": "ValueError",
                }
            file_line_exceptions[normalized_path] = normalized_entry

    return {
        "status": "loaded",
        "path": sanitized_path,
        "kind": payload.get("kind"),
        "schema_version": payload.get("schema_version"),
        "metrics": {key: int(value) for key, value in metrics_dict.items()},
        "file_line_exceptions": file_line_exceptions,
    }


def collect_structural_budget_report(  # noqa: PLR0915
    repo_root: Path,
    *,
    ratchet_path: Path | None = None,
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module  # noqa: PLC0415

    thresholds = structural_reports_module.STRUCTURAL_BUDGET_THRESHOLDS
    source_file_max_lines = thresholds["source_file_max_lines"]
    test_file_max_lines = thresholds["test_file_max_lines"]
    function_max_lines = thresholds["function_max_lines"]
    class_method_max_count = thresholds["class_method_max_count"]
    duplicate_private_name_min_files = thresholds["duplicate_private_name_min_files"]
    duplicate_private_name_min_length = thresholds["duplicate_private_name_min_length"]
    ratchet_state = _load_structural_budget_ratchet(repo_root, ratchet_path=ratchet_path)
    file_line_exceptions = ratchet_state.get("file_line_exceptions", {})

    source_files_over_budget: list[dict[str, Any]] = []
    test_files_over_budget: list[dict[str, Any]] = []
    functions_over_budget: list[dict[str, Any]] = []
    classes_over_budget: list[dict[str, Any]] = []
    private_name_occurrences: dict[str, set[str]] = defaultdict(set)
    facade_private_entrypoints: list[dict[str, Any]] = []
    scan_failures: list[dict[str, Any]] = []
    source_file_line_counts: list[int] = []
    test_file_line_counts: list[int] = []
    current_file_line_counts: dict[str, int] = {}
    source_lines_by_path: dict[str, list[str]] = {}
    module_import_counts: list[dict[str, Any]] = []
    module_dependency_counts: list[dict[str, Any]] = []
    module_public_symbol_counts: list[dict[str, Any]] = []
    function_nesting_depths: list[dict[str, Any]] = []
    known_modules = build_known_structural_modules(repo_root)

    for scope, path in structural_reports_module.iter_structural_python_files(repo_root):
        relative_path = structural_reports_module.sanitize_path_for_report(path, repo_root=repo_root) or path.as_posix()
        text, line_count, scan_failure = structural_reports_module.read_structural_text(path)
        if scan_failure is not None:
            scan_failures.append({"path": relative_path, **scan_failure})
        if line_count is None:
            continue

        current_file_line_counts[relative_path] = line_count
        if scope == "src":
            source_file_line_counts.append(line_count)
        elif scope == "tests":
            test_file_line_counts.append(line_count)
        line_limit_exception = file_line_exceptions.get(relative_path)
        effective_max_lines = (
            line_limit_exception["max_lines"]
            if line_limit_exception is not None
            else (source_file_max_lines if scope == "src" else test_file_max_lines)
        )
        if scope == "src" and line_count > effective_max_lines:
            source_files_over_budget.append({"path": relative_path, "line_count": line_count})
        elif scope == "tests" and line_count > effective_max_lines:
            test_files_over_budget.append({"path": relative_path, "line_count": line_count})
        if text is None:
            continue

        source_lines_by_path[relative_path] = text.splitlines()

        try:
            tree = structural_reports_module.ast.parse(text, filename=relative_path)
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

        if relative_path in structural_reports_module.FACADE_PRIVATE_BOUNDARY_FILES:
            facade_private_entrypoints.extend(_collect_facade_private_entrypoints(tree, relative_path=relative_path))

        surface_metrics = collect_python_structural_surface_metrics(
            tree,
            relative_path=relative_path,
            repo_root=repo_root,
            known_modules=known_modules,
        )
        module_import_counts.append(
            {
                "path": relative_path,
                "import_count": surface_metrics["import_count"],
            }
        )
        module_dependency_counts.append(
            {
                "path": relative_path,
                "dependency_count": surface_metrics["dependency_count"],
            }
        )
        module_public_symbol_counts.append(
            {
                "path": relative_path,
                "public_symbol_count": surface_metrics["public_symbol_count"],
            }
        )
        function_nesting_depths.extend(surface_metrics["function_nesting_depths"])

        module_level_private_names = {
            node.name
            for node in getattr(tree, "body", [])
            if isinstance(
                node,
                structural_reports_module.ast.FunctionDef | structural_reports_module.ast.AsyncFunctionDef,
            )
            and node.name.startswith("_")
            and not node.name.startswith("__")
            and len(node.name) >= duplicate_private_name_min_length
        }
        if scope == "src":
            for name in module_level_private_names:
                private_name_occurrences[name].add(relative_path)

        for node in structural_reports_module.ast.walk(tree):
            if isinstance(
                node, structural_reports_module.ast.FunctionDef | structural_reports_module.ast.AsyncFunctionDef
            ):
                end_lineno = getattr(node, "end_lineno", None)
                if end_lineno is None:
                    continue
                function_lines = source_lines_by_path[relative_path][node.lineno - 1 : end_lineno]
                line_span = structural_reports_module.count_structural_lines("\n".join(function_lines))
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
            elif isinstance(node, structural_reports_module.ast.ClassDef):
                method_count = sum(
                    1
                    for child in node.body
                    if isinstance(
                        child,
                        structural_reports_module.ast.FunctionDef | structural_reports_module.ast.AsyncFunctionDef,
                    )
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
        "thresholds": dict(structural_reports_module.STRUCTURAL_BUDGET_THRESHOLDS),
        "setpoints": dict(structural_reports_module.STRUCTURAL_BUDGET_SETPOINTS),
        "current_file_line_counts": dict(sorted(current_file_line_counts.items())),
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
            source_files_over_budget,
            key=lambda item: (-item["line_count"], item["path"]),
        ),
        "test_files_over_budget": sorted(
            test_files_over_budget,
            key=lambda item: (-item["line_count"], item["path"]),
        ),
        "functions_over_budget": sorted(
            functions_over_budget,
            key=lambda item: (-item["line_span"], item["path"], item["qualname"]),
        ),
        "classes_over_budget": sorted(
            classes_over_budget,
            key=lambda item: (-item["method_count"], item["path"], item["qualname"]),
        ),
        "module_import_counts": sorted(
            module_import_counts,
            key=lambda item: (-item["import_count"], item["path"]),
        ),
        "module_dependency_counts": sorted(
            module_dependency_counts,
            key=lambda item: (-item["dependency_count"], item["path"]),
        ),
        "module_public_symbol_counts": sorted(
            module_public_symbol_counts,
            key=lambda item: (-item["public_symbol_count"], item["path"]),
        ),
        "function_nesting_depths": sorted(
            function_nesting_depths,
            key=lambda item: (-item["nesting_depth"], item["path"], item["qualname"]),
        ),
        "repeated_private_names": repeated_private_names,
        "facade_private_entrypoints": facade_private_entrypoints,
        "scan_failures": scan_failures,
        "summary": {
            "source_file_max_lines": max(source_file_line_counts, default=0),
            "test_file_max_lines": max(test_file_line_counts, default=0),
            "import_max_count": max((item["import_count"] for item in module_import_counts), default=0),
            "dependency_max_count": max((item["dependency_count"] for item in module_dependency_counts), default=0),
            "public_symbol_max_count": max(
                (item["public_symbol_count"] for item in module_public_symbol_counts), default=0
            ),
            "nesting_max_depth": max((item["nesting_depth"] for item in function_nesting_depths), default=0),
        },
    }
    current_metrics = structural_reports_module.summarize_structural_budget_metrics(report)
    report["metrics"] = current_metrics
    report["ratchet"] = _evaluate_structural_budget_ratchet(
        current_metrics,
        ratchet_state,
        current_file_line_counts,
    )
    return report


__all__ = [
    "_collect_facade_private_entrypoints",
    "_evaluate_structural_budget_ratchet",
    "_is_structural_budget_python_path",
    "_load_structural_budget_ratchet",
    "_normalize_file_line_exceptions",
    "collect_structural_budget_report",
]
