"""Discovery and import-graph helpers for repo-audit scans."""

from __future__ import annotations

import ast
import re
import tomllib
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any


def load_pyproject(root: Path) -> dict[str, Any]:
    raw = (root / "pyproject.toml").read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return tomllib.loads(raw.decode(encoding))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError):
            continue
    return tomllib.loads(raw.decode("utf-8", errors="replace"))


def extract_documented_commands(
    paths: Iterable[Path],
    *,
    root: Path,
    read_text_fn: Callable[[Path], str],
    relative_path: Callable[[Path, Path], str],
    documented_command_re: re.Pattern[str],
    documented_command_factory: Callable[..., Any],
) -> list[Any]:
    commands: list[Any] = []
    for path in paths:
        text = read_text_fn(path)
        rel_path = relative_path(path, root)
        for line_number, line in enumerate(text.splitlines(), 1):
            for match in documented_command_re.finditer(line):
                start_index, end_index = match.span(1)
                if (start_index > 0 and line[start_index - 1] in "/\\") or (
                    end_index < len(line) and line[end_index] in "/\\"
                ):
                    continue
                command = match.group(1)
                subcommand = match.group(2)
                if command == "sattlint" and subcommand in {"and", "is", "supports"}:
                    continue
                commands.append(
                    documented_command_factory(
                        command=command,
                        subcommand=subcommand,
                        path=rel_path,
                        line=line_number,
                    )
                )
    return commands


def collect_cli_metadata(
    *,
    repo_root: Path,
    load_pyproject_fn: Callable[[Path], dict[str, Any]],
    build_cli_parser: Callable[[], Any],
) -> tuple[set[str], set[str]]:
    pyproject = load_pyproject_fn(repo_root)
    scripts = set(pyproject.get("project", {}).get("scripts", {}).keys())
    parser = build_cli_parser()
    subcommands: set[str] = set()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if choices:
            subcommands.update(choices.keys())
    return scripts, subcommands


def find_documentation_command_gaps(
    documented_commands: Iterable[Any],
    scripts: set[str],
    subcommands: set[str],
    *,
    finding_factory: Callable[..., Any],
) -> list[Any]:
    findings: list[Any] = []
    for item in documented_commands:
        if item.command == "sattlint" and item.subcommand and item.subcommand not in subcommands:
            findings.append(
                finding_factory(
                    id="documented-missing-subcommand",
                    category="feature-wiring",
                    severity="medium",
                    confidence="high",
                    message=f"Documented CLI subcommand '{item.subcommand}' is not implemented.",
                    path=item.path,
                    line=item.line,
                    detail="The docs mention a `sattlint` subcommand that the parser does not expose.",
                    suggestion="Update the docs or add the missing subcommand.",
                )
            )
        if item.command.startswith("sattlint-") and item.command not in scripts:
            findings.append(
                finding_factory(
                    id="documented-missing-script",
                    category="feature-wiring",
                    severity="medium",
                    confidence="high",
                    message=f"Documented console script '{item.command}' is not declared in pyproject.",
                    path=item.path,
                    line=item.line,
                    suggestion="Keep project.scripts and docs in sync.",
                )
            )
    return findings


def find_unused_config_keys(
    source_root: Path,
    default_keys: Iterable[str],
    *,
    read_text_fn: Callable[[Path], str],
    finding_factory: Callable[..., Any],
    content_by_file: dict[Path, str] | None = None,
) -> list[Any]:
    if content_by_file is None:
        content_by_file = {}
        for path in source_root.rglob("*.py"):
            if path.name == "repo_audit.py":
                continue
            content_by_file[path] = read_text_fn(path)

    findings: list[Any] = []
    for key in default_keys:
        pattern = re.compile(rf"['\"]{re.escape(key)}['\"]")
        count = 0
        for path, text in content_by_file.items():
            if path.name == "config.py":
                count += max(0, len(pattern.findall(text)) - 1)
            else:
                count += len(pattern.findall(text))
        if count == 0:
            findings.append(
                finding_factory(
                    id="unused-config-key",
                    category="configuration-hygiene",
                    severity="medium",
                    confidence="medium",
                    message=f"Config key '{key}' appears to be declared but unused.",
                    path="src/sattlint/config.py",
                    suggestion="Remove the key, document it, or wire it into runtime behavior.",
                )
            )
    return findings


def module_name_from_path(path: Path, root: Path) -> str:
    return ".".join(path.relative_to(root).with_suffix("").parts)


def resolve_import(module_name: str, imported: str | None, level: int) -> str | None:
    parts = module_name.split(".")
    if level == 0:
        return imported
    if level > len(parts):
        return imported
    prefix = parts[:-level]
    if imported:
        prefix.extend(imported.split("."))
    return ".".join(part for part in prefix if part)


def build_local_import_graph(
    source_root: Path,
    *,
    read_text_fn: Callable[[Path], str],
    content_by_file: dict[Path, str] | None = None,
    ast_by_file: dict[Path, ast.AST] | None = None,
) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    known_modules: dict[str, Path] = {}
    module_paths = list((content_by_file or {}).keys()) or list(source_root.rglob("*.py"))
    for path in module_paths:
        module_name = module_name_from_path(path, source_root)
        known_modules[module_name] = path

    for module_name, path in known_modules.items():
        if ast_by_file is not None and path in ast_by_file:
            tree = ast_by_file[path]
        else:
            tree = ast.parse((content_by_file or {}).get(path) or read_text_fn(path), filename=str(path))
        imports: set[str] = set()
        type_checking_lines: set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            test = node.test
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                for guarded_node in node.body:
                    start = getattr(guarded_node, "lineno", None)
                    end = getattr(guarded_node, "end_lineno", start)
                    if start is None or end is None:
                        continue
                    type_checking_lines.update(range(start, end + 1))
        for node in ast.walk(tree):
            if getattr(node, "lineno", None) in type_checking_lines:
                continue
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in known_modules:
                        imports.add(alias.name)
                    else:
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
                else:
                    for candidate in known_modules:
                        if candidate.startswith(resolved + "."):
                            imports.add(resolved)
                            break
        graph[module_name] = imports
    return graph


def find_import_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            if node in stack:
                start = stack.index(node)
                cycles.append([*stack[start:], node])
            return
        visiting.add(node)
        stack.append(node)
        for neighbor in graph.get(node, set()):
            if neighbor in graph:
                visit(neighbor)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
    return cycles


__all__ = [
    "build_local_import_graph",
    "collect_cli_metadata",
    "extract_documented_commands",
    "find_documentation_command_gaps",
    "find_import_cycles",
    "find_unused_config_keys",
    "load_pyproject",
    "module_name_from_path",
    "resolve_import",
]
