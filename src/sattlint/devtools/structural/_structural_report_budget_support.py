"""Support helpers for structural budget reporting."""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, cast

from sattlint.devtools.audit_core_discovery import module_name_from_path, resolve_import


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
    for raw_path, payload in cast(dict[object, object], raw).items():
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"{label} file_line_exceptions keys must be non-empty strings.")
        if not isinstance(payload, dict):
            raise ValueError(f"{label} file_line_exceptions[{raw_path!r}] must be a JSON object.")

        payload_dict = cast(dict[str, Any], payload)
        max_lines = payload_dict.get("max_lines")
        reason = payload_dict.get("reason")
        if not isinstance(max_lines, int) or max_lines <= 0:
            raise ValueError(f"{label} file_line_exceptions[{raw_path!r}].max_lines must be a positive integer.")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{label} file_line_exceptions[{raw_path!r}].reason must be a non-empty string.")

        normalized[raw_path.replace("\\", "/").strip("/")] = {
            "max_lines": int(max_lines),
            "reason": reason.strip(),
        }

    return dict(sorted(normalized.items()))


def _evaluate_structural_budget_ratchet(
    current_metrics: dict[str, int],
    ratchet_state: dict[str, Any],
    current_file_line_counts: dict[str, int],
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module  # noqa: PLC0415

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
        "setpoint_metrics": dict(structural_reports_module.STRUCTURAL_BUDGET_SETPOINTS),
        "current_metrics": current_metrics,
        "regressions": regressions,
    }


def _module_name_for_relative_path(relative_path: str, *, repo_root: Path) -> str | None:
    path = repo_root / relative_path
    if relative_path.startswith("src/"):
        return module_name_from_path(path, repo_root / "src")
    if relative_path.startswith("tests/"):
        return module_name_from_path(path, repo_root)
    return None


def build_known_structural_modules(repo_root: Path) -> frozenset[str]:
    module_names: set[str] = set()
    src_root = repo_root / "src"
    if src_root.exists():
        for path in sorted(src_root.rglob("*.py")):
            if path.is_file():
                module_names.add(module_name_from_path(path, src_root))

    tests_root = repo_root / "tests"
    if tests_root.exists():
        for path in sorted(tests_root.rglob("*.py")):
            if path.is_file():
                module_names.add(module_name_from_path(path, repo_root))

    return frozenset(module_names)


def collect_python_structural_surface_metrics(
    tree: ast.AST,
    *,
    relative_path: str,
    repo_root: Path,
    known_modules: frozenset[str],
) -> dict[str, Any]:
    type_checking_lines = _type_checking_lines(tree)
    module_name = _module_name_for_relative_path(relative_path, repo_root=repo_root)
    dependency_count = 0
    if module_name is not None:
        dependency_count = len(
            _internal_dependencies_for_tree(
                tree, module_name=module_name, known_modules=known_modules, type_checking_lines=type_checking_lines
            )
        )

    return {
        "import_count": _count_import_bindings(tree, type_checking_lines=type_checking_lines),
        "dependency_count": dependency_count,
        "public_symbol_count": len(_public_symbol_names(tree)),
        "function_nesting_depths": _function_nesting_entries(tree, relative_path=relative_path),
    }


def _type_checking_lines(tree: ast.AST) -> set[int]:
    guarded_lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if not isinstance(node.test, ast.Name) or node.test.id != "TYPE_CHECKING":
            continue
        for guarded_node in node.body:
            start = getattr(guarded_node, "lineno", None)
            end = getattr(guarded_node, "end_lineno", start)
            if start is None or end is None:
                continue
            guarded_lines.update(range(start, end + 1))
    return guarded_lines


def _count_import_bindings(tree: ast.AST, *, type_checking_lines: set[int]) -> int:
    count = 0
    for node in ast.walk(tree):
        if getattr(node, "lineno", None) in type_checking_lines:
            continue
        if isinstance(node, ast.Import | ast.ImportFrom):
            count += len(node.names)
    return count


def _internal_dependencies_for_tree(
    tree: ast.AST,
    *,
    module_name: str,
    known_modules: frozenset[str],
    type_checking_lines: set[int],
) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if getattr(node, "lineno", None) in type_checking_lines:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in known_modules:
                    imports.add(alias.name)
                    continue
                for candidate in known_modules:
                    if candidate.startswith(alias.name + "."):
                        imports.add(alias.name)
                        break
        elif isinstance(node, ast.ImportFrom):
            resolved = resolve_import(module_name, node.module, node.level)
            if not resolved:
                continue
            if resolved in known_modules:
                imports.add(resolved)
                continue
            for candidate in known_modules:
                if candidate.startswith(resolved + "."):
                    imports.add(resolved)
                    break
    return imports


def _public_symbol_names(tree: ast.AST) -> set[str]:
    public_names: set[str] = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if not node.name.startswith("_"):
                public_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                public_names.update(_public_assignment_names(target))
        elif isinstance(node, ast.AnnAssign | ast.AugAssign):
            public_names.update(_public_assignment_names(node.target))
    return public_names


def _public_assignment_names(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id} if not target.id.startswith("_") else set()
    if isinstance(target, ast.Tuple | ast.List):
        names: set[str] = set()
        for element in target.elts:
            names.update(_public_assignment_names(element))
        return names
    return set()


def _iter_named_functions(
    nodes: Iterable[ast.stmt],
    prefix: tuple[str, ...] = (),
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    for node in nodes:
        if isinstance(node, ast.ClassDef):
            yield from _iter_named_functions(node.body, prefix=(*prefix, node.name))
            continue
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            qualname = ".".join((*prefix, node.name))
            yield qualname, node
            yield from _iter_named_functions(node.body, prefix=(*prefix, node.name))


def _function_nesting_entries(tree: ast.AST, *, relative_path: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    root_body = cast(Iterable[ast.stmt], getattr(tree, "body", []))
    for qualname, node in _iter_named_functions(root_body):
        nesting_depth = _max_statement_nesting(node.body)
        end_line = node.end_lineno if node.end_lineno is not None else node.lineno
        entries.append(
            {
                "path": relative_path,
                "qualname": qualname,
                "nesting_depth": nesting_depth,
                "start_line": node.lineno,
                "end_line": end_line,
            }
        )
    return entries


def _max_statement_nesting(statements: Iterable[ast.stmt], *, depth: int = 0) -> int:
    max_depth = depth
    for statement in statements:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        child_groups = _nested_statement_groups(statement)
        if not child_groups:
            continue
        current_depth = depth + 1
        max_depth = max(max_depth, current_depth)
        for group in child_groups:
            max_depth = max(max_depth, _max_statement_nesting(group, depth=current_depth))
    return max_depth


def _nested_statement_groups(statement: ast.stmt) -> tuple[list[ast.stmt], ...]:
    if isinstance(statement, ast.If | ast.For | ast.AsyncFor | ast.While):
        return (statement.body, statement.orelse)
    if isinstance(statement, ast.With | ast.AsyncWith):
        return (statement.body,)
    if isinstance(statement, ast.Try):
        return (
            statement.body,
            statement.orelse,
            statement.finalbody,
            *(handler.body for handler in statement.handlers),
        )
    if isinstance(statement, ast.Match):
        return tuple(case.body for case in statement.cases)
    return ()


__all__ = [
    "_collect_facade_private_entrypoints",
    "_evaluate_structural_budget_ratchet",
    "_normalize_file_line_exceptions",
    "build_known_structural_modules",
    "collect_python_structural_surface_metrics",
]
