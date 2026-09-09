"""SattLine semantic rule engine (registry-backed facade).

Owns the analyzer-facing semantic rules: rule groups/definitions
(``_sattline_semantic_models``, ``_sattline_semantic_rules*``), issue
mapping (``_sattline_semantic_issue_mapping``), and the
``analyze_sattline_semantics`` entry point that runs the semantic
contributor analyzers through the registry and folds their findings into a
``SattLineSemanticsReport``.

Not to be confused with ``core/semantic.py`` (and ``core/_semantic_*``),
which owns the shared semantic *snapshot* — symbol index, access graph,
diagnostics, safety/taint traces — used as cross-cutting infrastructure by
``change_review`` and the public package surface. This module is the rules
layer; that module is the data layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

from sattline_parser.models.ast_model import BasePicture

from ..core.tracing import (
    detect_transform_invariant_violations,
)
from ..reporting.variables_report import VariableIssue
from ._registry_dispatch import get_semantic_contributor_specs, run_registry_analyzer
from ._sattline_semantic_issue_mapping import (
    map_framework_issues,
    map_profiled_issues,
    map_spec_issues,
    map_trace_findings,
    map_variable_issues,
)
from ._sattline_semantic_models import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    SemanticIssue,
    SemanticRule,
    SemanticRuleGroup,
)
from ._sattline_semantic_rules import (
    FRAMEWORK_RULES_BY_KIND,
    build_semantic_rule_groups,
)
from .framework import AnalysisContext, Issue, build_analysis_context, format_report_header


def get_sattline_semantic_rule_groups() -> tuple[SemanticRuleGroup, ...]:
    return build_semantic_rule_groups()


def get_sattline_semantic_rules() -> tuple[SemanticRule, ...]:
    return tuple(rule for group in get_sattline_semantic_rule_groups() for rule in group.rules)


def get_rule_for_framework_issue_kind(issue_kind: str) -> SemanticRule | None:
    return FRAMEWORK_RULES_BY_KIND.get(issue_kind)


def _dedupe_semantic_issues(issues: list[SemanticIssue]) -> list[SemanticIssue]:
    seen: set[tuple[object, ...]] = set()
    deduped: list[SemanticIssue] = []
    for issue in issues:
        data_key = tuple(sorted((k, repr(v)) for k, v in issue.data.items()))
        key = (issue.rule.id, tuple(issue.module_path or ()), data_key)
        if key not in seen:
            seen.add(key)
            deduped.append(issue)
    return deduped


@dataclass
class SattLineSemanticsReport:
    basepicture_name: str
    issues: list[SemanticIssue]

    @property
    def name(self) -> str:
        return self.basepicture_name

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header("SattLine semantics", self.basepicture_name, status="ok")
            lines.append("No semantic issues found.")
            return "\n".join(lines)

        lines = format_report_header("SattLine semantics", self.basepicture_name, status="issues")
        lines.append(f"Issues: {len(self.issues)}")

        for category in CATEGORY_ORDER:
            category_issues = [issue for issue in self.issues if issue.rule.category == category]
            if not category_issues:
                continue

            lines.append("")
            lines.append(f"  - {CATEGORY_LABELS[category]}:")
            for issue in sorted(
                category_issues,
                key=lambda item: (
                    item.module_path or [],
                    item.rule.id,
                    item.message,
                ),
            ):
                location = ".".join(issue.module_path or [self.basepicture_name])
                lines.append(f"      * [{location}] {issue.rule.id}: {issue.message}")

        return "\n".join(lines)


def analyze_sattline_semantics(
    base_picture: BasePicture,
    analysis_context: AnalysisContext | None = None,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
    config: dict[str, object] | None = None,
) -> SattLineSemanticsReport:
    issues: list[SemanticIssue] = []
    trace_findings = detect_transform_invariant_violations(base_picture)
    trace_issues = map_trace_findings(trace_findings)
    if any(finding.get("kind") == "unexpected_submodule_type" for finding in trace_findings):
        return SattLineSemanticsReport(
            basepicture_name=base_picture.header.name,
            issues=_dedupe_semantic_issues(trace_issues),
        )

    fallback_graph = SimpleNamespace(unavailable_libraries=set(unavailable_libraries or ()))
    if analysis_context is None:
        context = build_analysis_context(
            base_picture,
            graph=fallback_graph,
            debug=debug,
            target_is_library=analyzed_target_is_library,
            config=config,
            create_shared_artifacts=True,
        )
    else:
        context = build_analysis_context(
            base_picture,
            graph=analysis_context.graph if analysis_context.graph is not None else fallback_graph,
            debug=analysis_context.debug,
            target_is_library=analysis_context.target_is_library,
            selected_issue_kinds=analysis_context.selected_issue_kinds,
            config=analysis_context.config or config,
            shared_artifacts=analysis_context.shared_artifacts,
            create_shared_artifacts=True,
        )

    for spec in get_semantic_contributor_specs():
        report = run_registry_analyzer(
            spec,
            context,
            use_shared_artifacts=True,
        )

        report_issues = getattr(report, "issues", None)
        if not isinstance(report_issues, list):
            continue

        if spec.semantic_mapping_kind == "variable":
            issues.extend(map_variable_issues(cast(list[VariableIssue], report_issues)))
        elif spec.semantic_mapping_kind == "framework":
            issues.extend(map_framework_issues(cast(list[Issue], report_issues), FRAMEWORK_RULES_BY_KIND))
        elif spec.semantic_mapping_kind == "spec":
            issues.extend(map_spec_issues(cast(list[Issue], report_issues)))
        elif spec.semantic_rule_source is not None:
            issues.extend(map_profiled_issues(cast(list[Issue], report_issues), spec.semantic_rule_source))

    issues.extend(trace_issues)
    issues = _dedupe_semantic_issues(issues)

    return SattLineSemanticsReport(
        basepicture_name=base_picture.header.name,
        issues=issues,
    )
