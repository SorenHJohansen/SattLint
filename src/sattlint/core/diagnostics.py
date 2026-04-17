"""Helpers for projecting analyzer findings into editor-facing diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..analyzers.variables import VariablesAnalyzer
from ..models.ast_model import BasePicture
from ..reporting.variables_report import IssueKind, VariableIssue


@dataclass(frozen=True, slots=True)
class SemanticDiagnostic:
    source_file: str
    source_library: str | None
    line: int
    column: int
    length: int
    message: str


_ISSUE_LABELS = {
    IssueKind.UNUSED: "Unused variable",
    IssueKind.UNUSED_DATATYPE_FIELD: "Unused datatype field",
    IssueKind.READ_ONLY_NON_CONST: "Read-only variable should be CONST",
    IssueKind.NEVER_READ: "Variable is written but never read",
    IssueKind.STRING_MAPPING_MISMATCH: "String mapping datatype mismatch",
    IssueKind.DATATYPE_DUPLICATION: "Datatype duplication",
    IssueKind.NAME_COLLISION: "Name collision",
    IssueKind.MIN_MAX_MAPPING_MISMATCH: "Min/Max mapping name mismatch",
    IssueKind.MAGIC_NUMBER: "Magic number",
    IssueKind.SHADOWING: "Variable shadows outer scope",
    IssueKind.RESET_CONTAMINATION: "Variable is contaminated across reset",
}


def _cf(value: str) -> str:
    return value.casefold()


def _definition_label_length(definition: Any) -> int:
    label = (
        definition.field_path.split(".")[-1]
        if getattr(definition, "field_path", None)
        else definition.canonical_path.split(".")[-1]
    )
    return max(len(label), 1)


def project_variable_issues_by_file(
    issues: tuple[VariableIssue, ...],
    definitions_by_key: dict[tuple[str, ...], Any],
) -> dict[str, tuple[SemanticDiagnostic, ...]]:
    by_file: dict[str, list[SemanticDiagnostic]] = {}
    for issue in issues:
        if issue.variable is None:
            continue

        query_segments = list(issue.module_path) + [issue.variable.name]
        if issue.field_path:
            query_segments.extend(segment for segment in issue.field_path.split(".") if segment)
        definition = definitions_by_key.get(tuple(_cf(segment) for segment in query_segments))
        if (
            definition is None
            or definition.source_file is None
            or definition.declaration_span is None
        ):
            continue

        label = _ISSUE_LABELS.get(issue.kind, "SattLint issue")
        message = label if issue.role is None else f"{label}: {issue.role}"
        by_file.setdefault(definition.source_file.casefold(), []).append(
            SemanticDiagnostic(
                source_file=definition.source_file,
                source_library=definition.source_library,
                line=definition.declaration_span.line,
                column=definition.declaration_span.column,
                length=_definition_label_length(definition),
                message=message,
            )
        )

    return {
        file_key: tuple(
            sorted(
                diagnostics,
                key=lambda diagnostic: (
                    diagnostic.line,
                    diagnostic.column,
                    diagnostic.message,
                ),
            )
        )
        for file_key, diagnostics in by_file.items()
    }


def collect_project_variable_diagnostics(
    base_picture: BasePicture,
    unavailable_libraries: set[str],
    *,
    debug: bool,
    definitions_by_key: dict[tuple[str, ...], Any],
) -> tuple[tuple[VariableIssue, ...], dict[str, tuple[SemanticDiagnostic, ...]]]:
    analyzer = VariablesAnalyzer(
        base_picture,
        debug=debug,
        fail_loudly=False,
        unavailable_libraries=unavailable_libraries,
    )
    diagnostics = tuple(analyzer.run())
    return diagnostics, project_variable_issues_by_file(diagnostics, definitions_by_key)
