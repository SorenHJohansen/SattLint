from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

from sattline_parser.models.ast_model import BasePicture

from ..reporting.variables_report import VariableIssue
from ..tracing import (
    detect_transform_invariant_violations,
)
from ._registry_specs import build_context_kwargs
from ._sattline_semantic_issue_mapping import (
    map_framework_issues,
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
from .framework import AnalysisContext
from .issue import Issue, format_report_header


def get_sattline_semantic_rule_groups() -> tuple[SemanticRuleGroup, ...]:
    return build_semantic_rule_groups()


def get_sattline_semantic_rules() -> tuple[SemanticRule, ...]:
    return tuple(rule for group in get_sattline_semantic_rule_groups() for rule in group.rules)


def get_rule_for_framework_issue_kind(issue_kind: str) -> SemanticRule | None:
    return FRAMEWORK_RULES_BY_KIND.get(issue_kind)


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
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
    sfc_mutually_exclusive_steps: list[tuple[str, ...]] | tuple[tuple[str, ...], ...] | None = None,
    sfc_step_contracts: Mapping[str, object] | None = None,
    config: dict[str, object] | None = None,
) -> SattLineSemanticsReport:
    issues: list[SemanticIssue] = []

    from . import registry as registry_module

    context = AnalysisContext(
        base_picture=base_picture,
        graph=SimpleNamespace(unavailable_libraries=set(unavailable_libraries or ())),
        debug=debug,
        target_is_library=analyzed_target_is_library,
        config=config,
    )
    overrides: dict[str, object] = {}
    if sfc_mutually_exclusive_steps is not None:
        configured_steps = tuple(sfc_mutually_exclusive_steps)
        overrides["mutually_exclusive_steps"] = configured_steps
        overrides["sfc_mutually_exclusive_steps"] = configured_steps
    if sfc_step_contracts is not None:
        overrides["step_contracts"] = sfc_step_contracts
        overrides["sfc_step_contracts"] = sfc_step_contracts

    for analyzer in registry_module.get_default_analyzer_catalog().analyzers:
        spec = analyzer.spec
        if not spec.enabled or spec.semantic_mapping_kind is None:
            continue
        if spec.key == registry_module.SEMANTIC_LAYER_ANALYZER_KEY:
            continue

        analyzer_fn = getattr(registry_module, spec.analyzer_attr)
        if spec.direct_context:
            report = analyzer_fn(context)
        else:
            kwargs = build_context_kwargs(spec, registry_module, context, overrides=overrides)
            report = analyzer_fn(base_picture, **kwargs)

        report_issues = getattr(report, "issues", None)
        if not isinstance(report_issues, list):
            continue

        if spec.semantic_mapping_kind == "variable":
            issues.extend(map_variable_issues(cast(list[VariableIssue], report_issues)))
        elif spec.semantic_mapping_kind == "framework":
            issues.extend(map_framework_issues(cast(list[Issue], report_issues), FRAMEWORK_RULES_BY_KIND))
        elif spec.semantic_mapping_kind == "spec":
            issues.extend(map_spec_issues(cast(list[Issue], report_issues)))

    issues.extend(map_trace_findings(detect_transform_invariant_violations(base_picture)))

    return SattLineSemanticsReport(
        basepicture_name=base_picture.header.name,
        issues=issues,
    )
