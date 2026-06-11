from __future__ import annotations

from typing import Any, cast

from ..reporting.variables_report import IssueKind, VariableIssue
from ._sattline_semantic_models import SemanticIssue, SemanticRule
from ._sattline_semantic_rules import (
    RULE_CONTRACTS_BY_ID,
    SPEC_RULE_DESCRIPTIONS,
    TRACE_RULES,
    VARIABLE_RULES,
    attach_rule_contract,
)
from .framework import Issue


def map_variable_issues(issues: list[VariableIssue]) -> list[SemanticIssue]:
    semantic_issues: list[SemanticIssue] = []
    for issue in issues:
        rule = VARIABLE_RULES.get(issue.kind)
        if rule is None:
            continue
        semantic_issues.append(
            SemanticIssue(
                rule=rule,
                message=describe_variable_issue(issue),
                module_path=issue.module_path,
                data=variable_issue_data(issue),
                source_kind=issue.kind.value,
            )
        )
    return semantic_issues


def describe_variable_issue(issue: VariableIssue) -> str:
    variable_name = issue.variable.name if issue.variable is not None else None
    if issue.kind is IssueKind.UNUSED and variable_name is not None:
        return f"Variable {variable_name!r} is never used."
    if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD:
        datatype_name = issue.datatype_name or "<unknown datatype>"
        field_path = issue.field_path or "<unknown field>"
        return f"Datatype field {datatype_name}.{field_path} is never used."
    if issue.kind is IssueKind.READ_ONLY_NON_CONST and variable_name is not None:
        return f"Variable {variable_name!r} is read but never written, yet it is not CONST."
    if issue.kind is IssueKind.UI_ONLY and variable_name is not None:
        return f"Variable {variable_name!r} is only read through graphics or interact UI wiring."
    if issue.kind is IssueKind.PROCEDURE_STATUS and variable_name is not None:
        return issue.role or f"Procedure status output {variable_name!r} is not handled in control logic."
    if issue.kind is IssueKind.NEVER_READ and variable_name is not None:
        return f"Variable {variable_name!r} is written but never read."
    if issue.kind is IssueKind.WRITE_WITHOUT_EFFECT and variable_name is not None:
        return f"Variable {variable_name!r} is written and read internally, but its value never reaches a root-visible output."
    if issue.kind is IssueKind.HIGH_FAN_IN_OUT:
        return issue.role or "Variable has high fan-in or fan-out across module boundaries."
    if issue.kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION and variable_name is not None:
        return (
            issue.role
            or f"Global variable {variable_name!r} is only used inside one module subtree and can be localized."
        )
    if issue.kind is IssueKind.HIDDEN_GLOBAL_COUPLING and variable_name is not None:
        return issue.role or f"Global variable {variable_name!r} acts as an implicit interface across multiple modules."
    if issue.kind is IssueKind.UNKNOWN_PARAMETER_TARGET:
        return issue.role or "Unknown parameter mapping target."
    if issue.kind is IssueKind.CONTRACT_MISMATCH:
        return issue.role or "Connected module parameters use incompatible datatypes."
    if issue.kind is IssueKind.STRING_MAPPING_MISMATCH:
        source_name = issue.source_variable.name if issue.source_variable is not None else "<unknown source>"
        target_name = variable_name or "<unknown target>"
        return f"Parameter mapping from {source_name!r} to {target_name!r} uses incompatible string-like datatypes."
    if issue.kind is IssueKind.DATATYPE_DUPLICATION:
        datatype_name = issue.datatype_name or "<unknown datatype>"
        duplicates = issue.duplicate_count or 0
        return f"Datatype {datatype_name!r} appears {duplicates} times with the same structure."
    if issue.kind is IssueKind.NAME_COLLISION:
        return issue.role or "Declaration name collision."
    if issue.kind is IssueKind.LAYOUT_OVERLAP:
        return issue.role or "Layout elements overlap in the same scope."
    if issue.kind is IssueKind.MIN_MAX_MAPPING_MISMATCH:
        return issue.role or "Min_/Max_ parameter mappings do not align by base name."
    if issue.kind is IssueKind.SHADOWING:
        return issue.role or "Local declaration shadows an outer scope name."
    if issue.kind is IssueKind.RESET_CONTAMINATION:
        return issue.role or "Reset-state writes are incomplete across the sequence flow."
    if issue.kind is IssueKind.IMPLICIT_LATCH:
        return issue.role or "Boolean value may latch without a matching False write on complementary paths."
    return issue.role or str(issue)


def variable_issue_data(issue: VariableIssue) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if issue.variable is not None:
        data["variable"] = issue.variable.name
    if issue.source_variable is not None:
        data["source_variable"] = issue.source_variable.name
    if issue.datatype_name is not None:
        data["datatype_name"] = issue.datatype_name
    if issue.field_path is not None:
        data["field_path"] = issue.field_path
    if issue.role is not None:
        data["role"] = issue.role
    if issue.sequence_name is not None:
        data["sequence_name"] = issue.sequence_name
    if issue.reset_variable is not None:
        data["reset_variable"] = issue.reset_variable
    if issue.duplicate_count is not None:
        data["duplicate_count"] = issue.duplicate_count
    return data


def map_framework_issues(
    issues: list[Issue],
    rule_map: dict[str, SemanticRule],
) -> list[SemanticIssue]:
    semantic_issues: list[SemanticIssue] = []
    for issue in issues:
        rule = rule_map.get(issue.kind)
        if rule is None:
            continue
        semantic_issues.append(
            SemanticIssue(
                rule=rule,
                message=issue.message,
                module_path=issue.module_path,
                data=issue.data or {},
                source_kind=issue.kind,
            )
        )
    return semantic_issues


def map_trace_findings(findings: list[dict[str, Any]]) -> list[SemanticIssue]:
    semantic_issues: list[SemanticIssue] = []
    for finding in findings:
        kind = str(finding.get("kind", ""))
        rule = TRACE_RULES.get(kind)
        if rule is None:
            continue
        semantic_issues.append(
            SemanticIssue(
                rule=rule,
                message=describe_trace_finding(finding),
                module_path=finding.get("module_path"),
                data=finding,
                source_kind=kind,
            )
        )
    return semantic_issues


def describe_trace_finding(finding: dict[str, Any]) -> str:
    kind = finding.get("kind")
    if kind == "duplicate_sibling_name":
        return f"Sibling module name {finding.get('module_name')!r} is declared more than once."
    if kind == "unexpected_submodule_type":
        return f"Unexpected submodule node {finding.get('node_label')!r} appeared in the module tree."
    if kind == "unreachable_sequence_node":
        terminated_by = finding.get("terminated_by")
        terminated_by_dict = cast(dict[str, Any], terminated_by) if isinstance(terminated_by, dict) else None
        if terminated_by_dict is None:
            terminated_by_dict = {}
        raw_terminator = terminated_by_dict.get("kind")
        terminator = raw_terminator if isinstance(raw_terminator, str) else "an earlier terminating node"
        targets = terminated_by_dict.get("targets")
        if isinstance(targets, list | tuple) and targets:
            target_texts: list[str] = []
            for raw_target in cast(list[object] | tuple[object, ...], targets):
                if isinstance(raw_target, str):
                    target_texts.append(repr(raw_target))
            rendered_targets = ", ".join(target_texts)
            if rendered_targets:
                terminator = f"{terminator} targeting {rendered_targets}"
        node_label = finding.get("node_label", "<unknown node>")
        sequence_name = finding.get("sequence_name", "<unnamed>")
        return f"Sequence {sequence_name!r} contains unreachable node {node_label!r} after {terminator}."
    return kind or "Unknown trace finding."


def map_spec_issues(issues: list[Issue]) -> list[SemanticIssue]:
    semantic_issues: list[SemanticIssue] = []
    for issue in issues:
        semantic_issues.append(
            SemanticIssue(
                rule=attach_rule_contract(
                    SemanticRule(
                        id=issue.kind,
                        source="spec-compliance",
                        category="engineering-spec",
                        severity="warning",
                        applies_to="sattline-construct",
                        description=SPEC_RULE_DESCRIPTIONS.get(issue.kind, issue.kind),
                    ),
                    RULE_CONTRACTS_BY_ID.get(issue.kind),
                ),
                message=issue.message,
                module_path=issue.module_path,
                data=issue.data or {},
                source_kind=issue.kind,
            )
        )
    return semantic_issues


__all__ = [
    "map_framework_issues",
    "map_spec_issues",
    "map_trace_findings",
    "map_variable_issues",
]
