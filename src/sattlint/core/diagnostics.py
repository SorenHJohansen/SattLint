"""Helpers for projecting analyzer findings into editor-facing diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..analyzers.framework import Issue
from ..models.ast_model import BasePicture, FrameModule, ModuleTypeInstance, SingleModule
from ..reporting.variables_report import IssueKind, VariableIssue


@dataclass(frozen=True, slots=True)
class SemanticDiagnostic:
    source_file: str
    source_library: str | None
    line: int
    column: int
    length: int
    message: str
    analyzer_key: str | None = None


@dataclass(frozen=True, slots=True)
class DiagnosticGuidance:
    explanation: str
    suggestion: str


@dataclass(frozen=True, slots=True)
class _DiagnosticSite:
    source_file: str
    source_library: str | None
    line: int
    column: int
    length: int


_ISSUE_LABELS = {
    IssueKind.UNUSED: "Unused variable",
    IssueKind.UNUSED_DATATYPE_FIELD: "Unused datatype field",
    IssueKind.READ_ONLY_NON_CONST: "Read-only variable should be CONST",
    IssueKind.UI_ONLY: "Variable is only used by UI or display wiring",
    IssueKind.PROCEDURE_STATUS: "Procedure status output is not handled",
    IssueKind.NEVER_READ: "Variable is written but never read",
    IssueKind.WRITE_WITHOUT_EFFECT: "Variable write has no observable output effect",
    IssueKind.GLOBAL_SCOPE_MINIMIZATION: "Root global can be localized",
    IssueKind.HIDDEN_GLOBAL_COUPLING: "Root global creates hidden coupling",
    IssueKind.REQUIRED_PARAMETER_CONNECTION: "Required parameter connection missing",
    IssueKind.CONTRACT_MISMATCH: "Cross-module contract mismatch",
    IssueKind.STRING_MAPPING_MISMATCH: "String mapping datatype mismatch",
    IssueKind.DATATYPE_DUPLICATION: "Datatype duplication",
    IssueKind.NAME_COLLISION: "Name collision",
    IssueKind.MIN_MAX_MAPPING_MISMATCH: "Min/Max mapping name mismatch",
    IssueKind.MAGIC_NUMBER: "Magic number",
    IssueKind.SHADOWING: "Variable shadows outer scope",
    IssueKind.RESET_CONTAMINATION: "Variable is contaminated across reset",
    IssueKind.IMPLICIT_LATCH: "Boolean value may latch unexpectedly",
}

_ISSUE_GUIDANCE = {
    IssueKind.UNUSED: DiagnosticGuidance(
        explanation="Stale declarations add noise and make it harder to tell which signals still matter.",
        suggestion="Delete the declaration, or add the missing read/write path if it is still part of the design.",
    ),
    IssueKind.UNUSED_DATATYPE_FIELD: DiagnosticGuidance(
        explanation="Unused fields make shared datatypes drift away from the actual interface the code relies on.",
        suggestion="Remove the field from the datatype, or add the missing read/write path that should use it.",
    ),
    IssueKind.READ_ONLY_NON_CONST: DiagnosticGuidance(
        explanation="A writable declaration that is only read obscures intent and weakens constant-safety checks.",
        suggestion="Mark the declaration CONST, or add the write path that is supposed to update it.",
    ),
    IssueKind.UI_ONLY: DiagnosticGuidance(
        explanation="The variable is only consumed through graphics or interact display wiring, not through control logic or module contracts.",
        suggestion="Rename or document it as display-only state, or connect it to the control path that is expected to use it.",
    ),
    IssueKind.PROCEDURE_STATUS: DiagnosticGuidance(
        explanation="Procedure status channels are intended to drive control decisions, retries, or escalation paths rather than disappearing into dead storage or UI-only state.",
        suggestion="Read the status in control logic or propagate it to the caller that owns the error path, or remove the unused status output if the contract does not require it.",
    ),
    IssueKind.NEVER_READ: DiagnosticGuidance(
        explanation="Writes that are never observed usually mean dead logic or a missing connection to the real output path.",
        suggestion="Remove the dead write, or connect the variable to the code, parameter mapping, or output that should consume it.",
    ),
    IssueKind.WRITE_WITHOUT_EFFECT: DiagnosticGuidance(
        explanation="The value changes internally but never escapes to a root-visible output or module contract.",
        suggestion="Map the value to an output or parent parameter, or remove the intermediate write chain if it is dead logic.",
    ),
    IssueKind.GLOBAL_SCOPE_MINIMIZATION: DiagnosticGuidance(
        explanation="A root global that is only accessed inside one module subtree widens scope unnecessarily and makes the real owning scope less explicit.",
        suggestion="Move the declaration into the narrowest owning module or moduletype scope, and only expose it upward through explicit parameter mappings when needed.",
    ),
    IssueKind.HIDDEN_GLOBAL_COUPLING: DiagnosticGuidance(
        explanation="When multiple modules share a root global directly, the dependency bypasses the explicit parameter contract and becomes harder to trace safely.",
        suggestion="Replace the shared global access with explicit parameter mappings or local coordination state so the interface stays visible in the module wiring.",
    ),
    IssueKind.REQUIRED_PARAMETER_CONNECTION: DiagnosticGuidance(
        explanation="A parameter that the moduletype actively reads or writes is part of the module contract and should be wired explicitly by each instance.",
        suggestion="Add a parameter mapping for the required parameter, or make the parameter optional by removing the internal dependency on it.",
    ),
    IssueKind.CONTRACT_MISMATCH: DiagnosticGuidance(
        explanation="Incompatible parameter datatypes across module boundaries can break the interface contract or force unsafe coercions.",
        suggestion="Align the source and target datatypes, or insert an explicit compatible conversion before the mapping.",
    ),
    IssueKind.STRING_MAPPING_MISMATCH: DiagnosticGuidance(
        explanation="Mismatched string-like datatypes can truncate values or break parameter expectations between modules.",
        suggestion="Use matching string datatypes on both sides of the mapping, or change the contract to the correct string type.",
    ),
    IssueKind.DATATYPE_DUPLICATION: DiagnosticGuidance(
        explanation="Duplicate datatype layouts are easy to let drift apart and make structural changes harder to maintain.",
        suggestion="Promote the shared layout to one named RECORD datatype and reuse that definition.",
    ),
    IssueKind.NAME_COLLISION: DiagnosticGuidance(
        explanation="Case-insensitive name collisions make the declaration set ambiguous and harder to reason about.",
        suggestion="Rename one of the declarations so the scope has a single canonical name for that concept.",
    ),
    IssueKind.MIN_MAX_MAPPING_MISMATCH: DiagnosticGuidance(
        explanation="Mismatched Min_/Max_ mappings suggest the parameter contract no longer describes the same base signal.",
        suggestion="Reconnect the matching Min_/Max_ pair, or rename the parameters so the pair lines up again.",
    ),
    IssueKind.MAGIC_NUMBER: DiagnosticGuidance(
        explanation="Unlabeled literals hide intent and make calibration or recipe changes harder to review safely.",
        suggestion="Extract the literal into a named constant, engineering parameter, or recipe parameter.",
    ),
    IssueKind.SHADOWING: DiagnosticGuidance(
        explanation="Shadowing hides which declaration is actually being referenced and increases the risk of accidental scope capture.",
        suggestion="Rename the inner declaration, or reference the intended outer symbol more explicitly.",
    ),
    IssueKind.RESET_CONTAMINATION: DiagnosticGuidance(
        explanation="Partial reset handling can leave stale state behind when the sequence or step is expected to restart cleanly.",
        suggestion="Write the reset value on every reset path, or centralize the reset assignment in the step or sequence cleanup path.",
    ),
    IssueKind.IMPLICIT_LATCH: DiagnosticGuidance(
        explanation="A one-sided TRUE assignment can leave a boolean latched longer than intended when the complementary path never clears it.",
        suggestion="Add the matching FALSE assignment in the ELSE, alternate branch, or step exit path, or document the intentional latch behavior.",
    ),
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


def _format_semantic_diagnostic_message(issue: VariableIssue) -> str:
    label = _ISSUE_LABELS.get(issue.kind, "SattLint issue")
    headline = label if issue.role is None else f"{label}: {issue.role}"
    guidance = _ISSUE_GUIDANCE.get(issue.kind)
    if guidance is None:
        return headline
    return "\n".join(
        [
            headline,
            f"Why it matters: {guidance.explanation}",
            f"Suggested fix: {guidance.suggestion}",
        ]
    )


def _format_issue_diagnostic_message(issue: Issue) -> str:
    from ..analyzers.rule_profiles import materialize_issue_metadata

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
        source_file=source_file,
        source_library=source_library,
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


def project_report_issues_by_file(
    issues: tuple[Issue, ...],
    module_sites_by_path: dict[tuple[str, ...], _DiagnosticSite],
    *,
    analyzer_key: str,
) -> dict[str, tuple[SemanticDiagnostic, ...]]:
    by_file: dict[str, list[SemanticDiagnostic]] = {}
    for issue in issues:
        if not issue.module_path:
            continue
        site = module_sites_by_path.get(tuple(_cf(segment) for segment in issue.module_path))
        if site is None:
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
    return _sorted_semantic_diagnostics(by_file)


def merge_semantic_diagnostics_by_file(
    *diagnostic_maps: dict[str, tuple[SemanticDiagnostic, ...]],
) -> dict[str, tuple[SemanticDiagnostic, ...]]:
    merged: dict[str, list[SemanticDiagnostic]] = {}
    for diagnostic_map in diagnostic_maps:
        for file_key, diagnostics in diagnostic_map.items():
            merged.setdefault(file_key, []).extend(diagnostics)
    return _sorted_semantic_diagnostics(merged)


def project_variable_issues_by_file(
    issues: tuple[VariableIssue, ...],
    definitions_by_key: dict[tuple[str, ...], Any],
) -> dict[str, tuple[SemanticDiagnostic, ...]]:
    by_file: dict[str, list[SemanticDiagnostic]] = {}
    for issue in issues:
        if issue.variable is None:
            continue

        base_query_segments = [*list(issue.module_path), issue.variable.name]
        query_segments = list(base_query_segments)
        if issue.field_path:
            query_segments.extend(segment for segment in issue.field_path.split(".") if segment)
        definition = definitions_by_key.get(tuple(_cf(segment) for segment in query_segments))
        if definition is None and issue.field_path:
            definition = definitions_by_key.get(tuple(_cf(segment) for segment in base_query_segments))
        if definition is None or definition.source_file is None or definition.declaration_span is None:
            continue

        by_file.setdefault(definition.source_file.casefold(), []).append(
            SemanticDiagnostic(
                source_file=definition.source_file,
                source_library=definition.source_library,
                line=definition.declaration_span.line,
                column=definition.declaration_span.column,
                length=_definition_label_length(definition),
                message=_format_semantic_diagnostic_message(issue),
                analyzer_key="variables",
            )
        )

    return _sorted_semantic_diagnostics(by_file)
