"""Helpers for projecting analyzer findings into editor-facing diagnostics."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from sattline_parser.models.ast_model import BasePicture, FrameModule, ModuleTypeInstance, SingleModule

from ..analyzers.framework import Issue
from ..analyzers.rule_profiles import materialize_issue_metadata
from ..models._variable_issues import VariableIssue, materialize_variable_issue_metadata
from ..types import ProjectPath, TargetName


class _DeclarationSpanLike(Protocol):
    @property
    def line(self) -> int: ...

    @property
    def column(self) -> int: ...


class DefinitionLike(Protocol):
    @property
    def canonical_path(self) -> str: ...

    @property
    def field_path(self) -> str | None: ...

    @property
    def source_file(self) -> str | None: ...

    @property
    def source_library(self) -> str | None: ...

    @property
    def declaration_span(self) -> _DeclarationSpanLike | None: ...


type DefinitionLookup = Mapping[tuple[str, ...], DefinitionLike]

log = logging.getLogger("SattLint")


def _diagnostics_by_file_factory() -> dict[str, tuple[SemanticDiagnostic, ...]]:
    return {}


@dataclass(frozen=True, slots=True)
class SemanticDiagnostic:
    source_file: ProjectPath
    source_library: TargetName | None
    line: int
    column: int
    length: int
    message: str
    analyzer_key: str | None = None


@dataclass(frozen=True, slots=True)
class DroppedDiagnosticIssue:
    analyzer_key: str
    reason: str
    module_path: tuple[str, ...] = ()
    variable_name: str | None = None
    field_path: str | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class DiagnosticProjectionResult:
    diagnostics_by_file: dict[str, tuple[SemanticDiagnostic, ...]] = field(default_factory=_diagnostics_by_file_factory)
    dropped_issues: tuple[DroppedDiagnosticIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class _DiagnosticSite:
    source_file: ProjectPath
    source_library: TargetName | None
    line: int
    column: int
    length: int


def _cf(value: str) -> str:
    return value.casefold()


def _definition_label_length(definition: DefinitionLike) -> int:
    field_path = definition.field_path
    label = field_path.split(".")[-1] if field_path else definition.canonical_path.split(".")[-1]
    return max(len(label), 1)


def _format_semantic_diagnostic_message(issue: VariableIssue) -> str:
    metadata = materialize_variable_issue_metadata(issue)
    headline = metadata.label if issue.role is None else f"{metadata.label}: {issue.role}"
    if metadata.explanation is None or metadata.suggestion is None:
        return headline
    return "\n".join(
        [
            headline,
            f"Why it matters: {metadata.explanation}",
            f"Suggested fix: {metadata.suggestion}",
        ]
    )


def _format_issue_diagnostic_message(issue: Issue) -> str:
    materialized = materialize_issue_metadata(issue)
    lines = [materialized.message]
    if materialized.explanation:
        lines.append(f"Why it matters: {materialized.explanation}")
    if materialized.suggestion:
        lines.append(f"Suggested fix: {materialized.suggestion}")
    return "\n".join(lines)


def _sorted_semantic_diagnostics(
    diagnostics_by_file: dict[str, list[SemanticDiagnostic]],
) -> dict[str, tuple[SemanticDiagnostic, ...]]:
    result: dict[str, tuple[SemanticDiagnostic, ...]] = {}
    for file_key, diagnostics in diagnostics_by_file.items():
        unique = {
            (
                diagnostic.source_file.casefold(),
                diagnostic.source_library.casefold() if diagnostic.source_library is not None else None,
                diagnostic.line,
                diagnostic.column,
                diagnostic.length,
                diagnostic.message,
                diagnostic.analyzer_key,
            ): diagnostic
            for diagnostic in diagnostics
        }
        result[file_key] = tuple(
            sorted(
                unique.values(),
                key=lambda diagnostic: (
                    diagnostic.line,
                    diagnostic.column,
                    diagnostic.analyzer_key or "",
                    diagnostic.message,
                ),
            )
        )
    return result


def _register_site(
    sites_by_path: dict[tuple[str, ...], _DiagnosticSite],
    module_path: list[str],
    *,
    source_file: str | None,
    source_library: str | None,
    line: int | None,
    column: int | None,
    label: str,
) -> None:
    if source_file is None or line is None or column is None:
        return
    sites_by_path[tuple(_cf(segment) for segment in module_path)] = _DiagnosticSite(
        source_file=ProjectPath(source_file),
        source_library=TargetName(source_library) if source_library is not None else None,
        line=line,
        column=column,
        length=max(len(label), 1),
    )


def build_module_diagnostic_sites(base_picture: BasePicture) -> dict[tuple[str, ...], _DiagnosticSite]:
    sites_by_path: dict[tuple[str, ...], _DiagnosticSite] = {}
    root_path = [base_picture.header.name]
    _register_site(
        sites_by_path,
        root_path,
        source_file=getattr(base_picture, "origin_file", None),
        source_library=getattr(base_picture, "origin_lib", None),
        line=getattr(getattr(base_picture.header, "declaration_span", None), "line", None),
        column=getattr(getattr(base_picture.header, "declaration_span", None), "column", None),
        label=base_picture.header.name,
    )

    def walk_modules(
        children: list[SingleModule | FrameModule | ModuleTypeInstance],
        parent_paths: tuple[list[str], ...],
        *,
        current_file: str | None,
        current_library: str | None,
    ) -> None:
        for child in children or []:
            child_paths = tuple([*path, child.header.name] for path in parent_paths)
            for child_path in child_paths:
                _register_site(
                    sites_by_path,
                    child_path,
                    source_file=current_file,
                    source_library=current_library,
                    line=getattr(getattr(child.header, "declaration_span", None), "line", None),
                    column=getattr(getattr(child.header, "declaration_span", None), "column", None),
                    label=child.header.name,
                )
            if isinstance(child, SingleModule | FrameModule):
                walk_modules(
                    child.submodules or [],
                    child_paths,
                    current_file=current_file,
                    current_library=current_library,
                )

    walk_modules(
        base_picture.submodules or [],
        (root_path,),
        current_file=getattr(base_picture, "origin_file", None),
        current_library=getattr(base_picture, "origin_lib", None),
    )

    for moduletype in base_picture.moduletype_defs or []:
        source_file = getattr(moduletype, "origin_file", None) or getattr(base_picture, "origin_file", None)
        source_library = getattr(moduletype, "origin_lib", None) or getattr(base_picture, "origin_lib", None)
        moduletype_paths = (
            [base_picture.header.name, moduletype.name],
            [base_picture.header.name, f"TypeDef:{moduletype.name}"],
        )
        for moduletype_path in moduletype_paths:
            _register_site(
                sites_by_path,
                moduletype_path,
                source_file=source_file,
                source_library=source_library,
                line=getattr(getattr(moduletype, "declaration_span", None), "line", None),
                column=getattr(getattr(moduletype, "declaration_span", None), "column", None),
                label=moduletype.name,
            )
        walk_modules(
            moduletype.submodules or [],
            tuple(list(path) for path in moduletype_paths),
            current_file=source_file,
            current_library=source_library,
        )

    return sites_by_path


def project_report_issues(
    issues: tuple[Issue, ...],
    module_sites_by_path: dict[tuple[str, ...], _DiagnosticSite],
    *,
    analyzer_key: str,
) -> DiagnosticProjectionResult:
    by_file: dict[str, list[SemanticDiagnostic]] = {}
    dropped_issues: list[DroppedDiagnosticIssue] = []
    for issue in issues:
        if not issue.module_path:
            dropped_issues.append(
                DroppedDiagnosticIssue(
                    analyzer_key=analyzer_key,
                    reason="missing-module-path",
                    message=issue.message,
                )
            )
            continue
        site = module_sites_by_path.get(tuple(_cf(segment) for segment in issue.module_path))
        if site is None:
            dropped_issues.append(
                DroppedDiagnosticIssue(
                    analyzer_key=analyzer_key,
                    reason="missing-module-site",
                    module_path=tuple(issue.module_path),
                    message=issue.message,
                )
            )
            continue
        by_file.setdefault(site.source_file.casefold(), []).append(
            SemanticDiagnostic(
                source_file=site.source_file,
                source_library=site.source_library,
                line=site.line,
                column=site.column,
                length=site.length,
                message=_format_issue_diagnostic_message(issue),
                analyzer_key=analyzer_key,
            )
        )
    return DiagnosticProjectionResult(
        diagnostics_by_file=_sorted_semantic_diagnostics(by_file),
        dropped_issues=tuple(dropped_issues),
    )


def project_report_issues_by_file(
    issues: tuple[Issue, ...],
    module_sites_by_path: dict[tuple[str, ...], _DiagnosticSite],
    *,
    analyzer_key: str,
) -> dict[str, tuple[SemanticDiagnostic, ...]]:
    return project_report_issues(
        issues,
        module_sites_by_path,
        analyzer_key=analyzer_key,
    ).diagnostics_by_file


def merge_semantic_diagnostics_by_file(
    *diagnostic_maps: dict[str, tuple[SemanticDiagnostic, ...]],
) -> dict[str, tuple[SemanticDiagnostic, ...]]:
    merged: dict[str, list[SemanticDiagnostic]] = {}
    for diagnostic_map in diagnostic_maps:
        for file_key, diagnostics in diagnostic_map.items():
            merged.setdefault(file_key, []).extend(diagnostics)
    return _sorted_semantic_diagnostics(merged)


def merge_diagnostic_projection_results(
    *results: DiagnosticProjectionResult,
) -> DiagnosticProjectionResult:
    merged_maps = merge_semantic_diagnostics_by_file(*(result.diagnostics_by_file for result in results))
    dropped_issues: list[DroppedDiagnosticIssue] = []
    for result in results:
        dropped_issues.extend(result.dropped_issues)
    return DiagnosticProjectionResult(diagnostics_by_file=merged_maps, dropped_issues=tuple(dropped_issues))


def log_dropped_diagnostic_issues(
    dropped_issues: tuple[DroppedDiagnosticIssue, ...],
    *,
    logger: logging.Logger | None = None,
    limit: int = 10,
) -> None:
    if not dropped_issues:
        return

    sink = logger or log
    sink.warning("Dropped %d semantic diagnostic issue(s) during projection.", len(dropped_issues))
    for dropped_issue in dropped_issues[:limit]:
        sink.warning(
            "Dropped semantic diagnostic issue analyzer=%s reason=%s module_path=%s variable=%s field=%s message=%s",
            dropped_issue.analyzer_key,
            dropped_issue.reason,
            ".".join(dropped_issue.module_path) if dropped_issue.module_path else "<none>",
            dropped_issue.variable_name or "<none>",
            dropped_issue.field_path or "<none>",
            dropped_issue.message or "<none>",
        )
    remaining = len(dropped_issues) - limit
    if remaining > 0:
        sink.warning("Suppressed %d additional dropped semantic diagnostic issue(s).", remaining)


def project_variable_issues(
    issues: tuple[VariableIssue, ...],
    definitions_by_key: DefinitionLookup,
) -> DiagnosticProjectionResult:
    by_file: dict[str, list[SemanticDiagnostic]] = {}
    dropped_issues: list[DroppedDiagnosticIssue] = []
    for issue in issues:
        if issue.variable is None:
            dropped_issues.append(
                DroppedDiagnosticIssue(
                    analyzer_key="variables",
                    reason="missing-variable",
                    module_path=tuple(issue.module_path),
                    field_path=issue.field_path,
                    message=str(issue),
                )
            )
            continue

        base_query_segments = [*list(issue.module_path), issue.variable.name]
        query_segments = list(base_query_segments)
        if issue.field_path:
            query_segments.extend(segment for segment in issue.field_path.split(".") if segment)
        definition = definitions_by_key.get(tuple(_cf(segment) for segment in query_segments))
        if definition is None and issue.field_path:
            definition = definitions_by_key.get(tuple(_cf(segment) for segment in base_query_segments))
        if definition is None:
            dropped_issues.append(
                DroppedDiagnosticIssue(
                    analyzer_key="variables",
                    reason="missing-definition",
                    module_path=tuple(issue.module_path),
                    variable_name=issue.variable.name,
                    field_path=issue.field_path,
                    message=str(issue),
                )
            )
            continue
        if definition.source_file is None or definition.declaration_span is None:
            dropped_issues.append(
                DroppedDiagnosticIssue(
                    analyzer_key="variables",
                    reason="missing-definition-site",
                    module_path=tuple(issue.module_path),
                    variable_name=issue.variable.name,
                    field_path=issue.field_path,
                    message=str(issue),
                )
            )
            continue

        by_file.setdefault(definition.source_file.casefold(), []).append(
            SemanticDiagnostic(
                source_file=ProjectPath(definition.source_file),
                source_library=(
                    TargetName(definition.source_library) if definition.source_library is not None else None
                ),
                line=definition.declaration_span.line,
                column=definition.declaration_span.column,
                length=_definition_label_length(definition),
                message=_format_semantic_diagnostic_message(issue),
                analyzer_key="variables",
            )
        )

    return DiagnosticProjectionResult(
        diagnostics_by_file=_sorted_semantic_diagnostics(by_file),
        dropped_issues=tuple(dropped_issues),
    )


def project_variable_issues_by_file(
    issues: tuple[VariableIssue, ...],
    definitions_by_key: DefinitionLookup,
) -> dict[str, tuple[SemanticDiagnostic, ...]]:
    return project_variable_issues(issues, definitions_by_key).diagnostics_by_file
