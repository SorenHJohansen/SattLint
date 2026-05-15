"""Core helper logic for repo-audit scanning and finding orchestration."""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any


def find_architecture_findings(
    source_root: Path,
    *,
    read_text_fn: Callable[[Path], str],
    relative_path: Callable[[Path], str],
    finding_factory: Callable[..., Any],
    build_local_import_graph_fn: Callable[..., dict[str, set[str]]],
    find_import_cycles_fn: Callable[[dict[str, set[str]]], list[list[str]]],
    oversized_module_line_limit: int,
    content_by_file: dict[Path, str] | None = None,
    ast_by_file: dict[Path, ast.AST] | None = None,
) -> list[Any]:
    findings: list[Any] = []
    graph = build_local_import_graph_fn(
        source_root,
        content_by_file=content_by_file,
        ast_by_file=ast_by_file,
    )
    cycles = find_import_cycles_fn(graph)
    for cycle in cycles:
        cycle_str = " -> ".join(cycle)
        if "sattline_semantics" in cycle and "rule_profiles" in cycle:
            severity = "info"
            message = "Known aggregator cycle (rule metadata requires aggregator)."
        elif len(cycle) > 4:
            severity = "info"
            message = "Long import cycle through multiple analyzers."
        else:
            severity = "high"
            message = "Circular import detected."
        findings.append(
            finding_factory(
                id="import-cycle",
                category="architecture",
                severity=severity,
                confidence="high",
                message=message,
                detail=cycle_str,
                suggestion="Break the cycle with a lower-level shared module or dependency inversion.",
            )
        )

    file_iterable = list((content_by_file or {}).items()) or [
        (path, read_text_fn(path)) for path in source_root.rglob("*.py")
    ]
    for path, text in file_iterable:
        rel_path = relative_path(path)
        lines = text.splitlines()
        non_empty_lines = [line for line in lines if line.strip() and not line.strip().startswith("#")]
        if len(non_empty_lines) >= oversized_module_line_limit and not rel_path.endswith("_builtins.py"):
            findings.append(
                finding_factory(
                    id="oversized-module",
                    category="architecture",
                    severity="medium",
                    confidence="high",
                    message="Large module with high maintenance cost.",
                    path=rel_path,
                    detail=f"{len(non_empty_lines)} non-empty lines",
                    suggestion="Split unrelated responsibilities into smaller modules.",
                )
            )

    semantic_path = source_root / "sattlint" / "core" / "semantic.py"
    if semantic_path.exists():
        semantic_text = (content_by_file or {}).get(semantic_path) or read_text_fn(semantic_path)
        if (
            "from ..analyzers.variables import VariablesAnalyzer" in semantic_text
            or "from sattlint.analyzers.variables import VariablesAnalyzer" in semantic_text
        ):
            findings.append(
                finding_factory(
                    id="core-analyzer-coupling",
                    category="architecture",
                    severity="medium",
                    confidence="high",
                    message="Core semantic layer depends directly on analyzer code.",
                    path=relative_path(semantic_path),
                    suggestion="Keep `sattlint.core` analysis-agnostic or move shared logic into a lower-level package.",
                )
            )
    return findings


def find_cli_findings(
    *,
    build_cli_parser: Callable[[], Any],
    finding_factory: Callable[..., Any],
) -> list[Any]:
    parser = build_cli_parser()
    findings: list[Any] = []
    if not parser.description:
        findings.append(
            finding_factory(
                id="cli-missing-description",
                category="cli-ux",
                severity="low",
                confidence="high",
                message="Top-level CLI parser is missing a description.",
                path="src/sattlint/app.py",
                suggestion="Add a short parser description so `--help` is self-explanatory.",
            )
        )
    for action in parser._actions:
        choices = getattr(action, "choices", None) or {}
        for subparser in choices.values():
            if not subparser.description:
                findings.append(
                    finding_factory(
                        id="cli-missing-subcommand-description",
                        category="cli-ux",
                        severity="low",
                        confidence="high",
                        message="CLI subcommand is missing a description.",
                        path="src/sattlint/app.py",
                        suggestion="Give each subcommand a description for consistent help output.",
                    )
                )
    return findings


def find_logging_findings(
    source_root: Path,
    *,
    read_text_fn: Callable[[Path], str],
    relative_path: Callable[[Path], str],
    finding_factory: Callable[..., Any],
    print_call_re: re.Pattern[str],
    allowed_print_modules: set[str],
    allowed_print_prefixes: tuple[str, ...],
    content_by_file: dict[Path, str] | None = None,
) -> list[Any]:
    findings: list[Any] = []
    file_iterable = list((content_by_file or {}).items()) or [
        (path, read_text_fn(path)) for path in source_root.rglob("*.py")
    ]
    for path, text in file_iterable:
        rel_path = relative_path(path)
        allows_console_output = rel_path in allowed_print_modules or any(
            rel_path.startswith(prefix) for prefix in allowed_print_prefixes
        )
        if print_call_re.search(text) and not allows_console_output:
            findings.append(
                finding_factory(
                    id="unexpected-print",
                    category="logging-observability",
                    severity="medium",
                    confidence="medium",
                    message="Library module uses print() instead of structured logging or return values.",
                    path=rel_path,
                    suggestion="Keep prints in CLI entry points; use logging or reports in library code.",
                )
            )
    return findings


def dedupe_findings(findings: Iterable[Any]) -> list[Any]:
    seen: set[tuple[str, str | None, int | None, str]] = set()
    deduped: list[Any] = []
    for finding in findings:
        key = (finding.id, finding.path, finding.line, finding.message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


def is_leak_finding(
    finding: Any,
    *,
    leak_relevant_categories: set[str],
    leak_relevant_finding_ids: set[str],
) -> bool:
    return finding.category in leak_relevant_categories or finding.id in leak_relevant_finding_ids


def build_repo_audit_scan_context(
    root: Path,
    *,
    include_generated: bool,
    tracked_only: bool,
    suspicious_identifiers: Iterable[str],
    list_tracked_repo_paths_fn: Callable[[Path], tuple[str, ...] | None],
    build_python_source_scan_context_fn: Callable[..., Any],
    collect_cli_metadata_fn: Callable[[], tuple[set[str], set[str]]],
    extract_documented_commands_fn: Callable[..., list[Any]],
    context_factory: Callable[..., Any],
) -> Any:
    suspicious_set = frozenset(identifier.strip() for identifier in suspicious_identifiers if identifier.strip())
    tracked_paths = list_tracked_repo_paths_fn(root) if tracked_only else None
    docs_to_scan = [root / "README.md", root / "CONTRIBUTING.md", root / "vscode" / "sattline-vscode" / "README.md"]
    source_context = build_python_source_scan_context_fn(root / "src", root=root, tracked_paths=tracked_paths)
    test_context = build_python_source_scan_context_fn(root / "tests", root=root, tracked_paths=tracked_paths)
    scripts_context = build_python_source_scan_context_fn(root / "scripts", root=root, tracked_paths=tracked_paths)
    scripts, subcommands = collect_cli_metadata_fn()
    documented_commands = tuple(
        extract_documented_commands_fn((path for path in docs_to_scan if path.exists()), root=root)
    )
    return context_factory(
        root=root,
        include_generated=include_generated,
        tracked_only=tracked_only,
        tracked_paths=tracked_paths,
        suspicious_identifiers=suspicious_set,
        source_context=source_context,
        test_context=test_context,
        scripts_context=scripts_context,
        scripts=frozenset(scripts),
        subcommands=frozenset(subcommands),
        documented_commands=documented_commands,
    )


def shared_text_line_findings(
    context: Any,
    *,
    iter_repo_text_entries_fn: Callable[..., Iterable[tuple[Path, str]]],
    line_findings_fn: Callable[..., list[Any]],
) -> tuple[Any, ...]:
    if context.line_findings is not None:
        return context.line_findings

    findings: list[Any] = []
    suspicious_identifiers = set(context.suspicious_identifiers)
    for path, text in iter_repo_text_entries_fn(
        context.root,
        include_generated=context.include_generated,
        tracked_only=context.tracked_only,
    ):
        findings.extend(line_findings_fn(path, text, suspicious_identifiers, root=context.root))
    return tuple(findings)


def run_text_scan_check(
    context: Any,
    *,
    shared_text_line_findings_fn: Callable[[Any], tuple[Any, ...]],
    local_ci_parity_line_finding_ids: set[str],
) -> list[Any]:
    return [
        finding
        for finding in shared_text_line_findings_fn(context)
        if finding.id not in local_ci_parity_line_finding_ids
    ]


def run_documented_commands_check(
    context: Any,
    *,
    find_documentation_command_gaps_fn: Callable[[Iterable[Any], set[str], set[str]], list[Any]],
) -> list[Any]:
    return find_documentation_command_gaps_fn(
        context.documented_commands, set(context.scripts), set(context.subcommands)
    )


def run_unused_config_keys_check(
    context: Any,
    *,
    default_config_keys: Iterable[str],
    find_unused_config_keys_fn: Callable[..., list[Any]],
) -> list[Any]:
    return find_unused_config_keys_fn(
        context.root / "src" / "sattlint",
        default_config_keys,
        content_by_file={
            path: text
            for path, text in context.source_context.texts.items()
            if path.is_relative_to(context.root / "src" / "sattlint") and path.name != "repo_audit.py"
        },
    )


def run_architecture_check(
    context: Any,
    *,
    find_architecture_findings_fn: Callable[..., list[Any]],
) -> list[Any]:
    return find_architecture_findings_fn(
        context.root / "src",
        content_by_file=context.source_context.texts,
        ast_by_file=context.source_context.asts,
    )


def run_cli_check(
    _context: Any,
    *,
    find_cli_findings_fn: Callable[[], list[Any]],
) -> list[Any]:
    return find_cli_findings_fn()


def run_logging_check(
    context: Any,
    *,
    find_logging_findings_fn: Callable[..., list[Any]],
) -> list[Any]:
    return find_logging_findings_fn(context.root / "src", content_by_file=context.source_context.texts)


def run_ai_gc_check(
    context: Any,
    *,
    build_ai_gc_report_fn: Callable[..., dict[str, Any]],
    ai_gc_report_findings_fn: Callable[[dict[str, Any]], list[Any]],
) -> list[Any]:
    report = build_ai_gc_report_fn(context.root, tracked_paths=context.tracked_paths)
    return ai_gc_report_findings_fn(report)


def run_ignored_repo_paths_check(
    context: Any,
    *,
    find_ignored_repo_path_references_fn: Callable[..., list[Any]],
) -> list[Any]:
    findings: list[Any] = []
    findings.extend(
        find_ignored_repo_path_references_fn(
            context.source_context,
            root=context.root,
            tracked_paths=context.tracked_paths,
        )
    )
    findings.extend(
        find_ignored_repo_path_references_fn(
            context.test_context,
            root=context.root,
            tracked_paths=context.tracked_paths,
        )
    )
    findings.extend(
        find_ignored_repo_path_references_fn(
            context.scripts_context,
            root=context.root,
            tracked_paths=context.tracked_paths,
        )
    )
    return findings


def run_coverage_check(
    context: Any,
    *,
    parse_coverage_findings_fn: Callable[..., list[Any]],
) -> list[Any]:
    return parse_coverage_findings_fn(context.root, tracked_paths=context.tracked_paths)


def run_public_readiness_check(
    context: Any,
    *,
    find_public_readiness_findings_fn: Callable[..., list[Any]],
) -> list[Any]:
    return find_public_readiness_findings_fn(context.root, tracked_paths=context.tracked_paths)
