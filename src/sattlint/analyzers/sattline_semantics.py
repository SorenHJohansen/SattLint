from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sattline_parser.models.ast_model import BasePicture
from sattlint.analyzers.initial_values import analyze_initial_values

from ..tracing import (
    detect_transform_invariant_violations,
)
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
    ALARM_RULES,
    CONFIG_DRIFT_RULES,
    DATAFLOW_RULES,
    FAULT_HANDLING_RULES,
    FRAMEWORK_RULES_BY_KIND,
    INITIAL_VALUE_RULES,
    LOOP_STABILITY_RULES,
    NUMERIC_CONSTRAINT_RULES,
    SAFETY_PATH_RULES,
    SFC_RULES,
    SIGNAL_LIFECYCLE_RULES,
    TAINT_RULES,
    UNSAFE_DEFAULT_RULES,
    build_semantic_rule_groups,
)
from .alarm_integrity import analyze_alarm_integrity
from .config_drift import analyze_config_drift
from .dataflow import analyze_dataflow
from .fault_handling import analyze_fault_handling
from .issue import format_report_header
from .loop_stability import analyze_loop_stability
from .numeric_constraints import analyze_numeric_constraints
from .safety_paths import analyze_safety_paths
from .sfc import analyze_sfc
from .shadowing import analyze_shadowing
from .signal_lifecycle import analyze_signal_lifecycle
from .spec_compliance import analyze_spec_compliance
from .taint_paths import analyze_taint_paths
from .unsafe_defaults import analyze_unsafe_defaults
from .variables import analyze_variables


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

    variable_report = analyze_variables(
        base_picture,
        debug=debug,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
        config=config,
    )
    shadowing_report = analyze_shadowing(
        base_picture,
        debug=debug,
        unavailable_libraries=unavailable_libraries,
    )
    spec_report = analyze_spec_compliance(
        base_picture,
        debug=debug,
        unavailable_libraries=unavailable_libraries,
    )
    alarm_report = analyze_alarm_integrity(
        base_picture,
        debug=debug,
        unavailable_libraries=unavailable_libraries,
    )
    initial_value_report = analyze_initial_values(
        base_picture,
        debug=debug,
        unavailable_libraries=unavailable_libraries,
    )
    safety_path_report = analyze_safety_paths(
        base_picture,
        debug=debug,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
    )
    taint_path_report = analyze_taint_paths(
        base_picture,
        debug=debug,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
    )
    unsafe_defaults_report = analyze_unsafe_defaults(base_picture)
    sfc_report = analyze_sfc(
        base_picture,
        mutually_exclusive_steps=sfc_mutually_exclusive_steps,
        step_contracts=sfc_step_contracts,
    )
    dataflow_report = analyze_dataflow(
        base_picture,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
    )
    signal_lifecycle_report = analyze_signal_lifecycle(base_picture)
    loop_stability_report = analyze_loop_stability(base_picture)
    fault_handling_report = analyze_fault_handling(base_picture)
    numeric_constraints_report = analyze_numeric_constraints(base_picture)
    config_drift_report = analyze_config_drift(
        base_picture,
        unavailable_libraries=unavailable_libraries,
    )

    issues.extend(map_variable_issues(variable_report.issues))
    issues.extend(map_variable_issues(shadowing_report.issues))
    issues.extend(map_framework_issues(sfc_report.issues, SFC_RULES))
    issues.extend(map_framework_issues(alarm_report.issues, ALARM_RULES))
    issues.extend(map_framework_issues(initial_value_report.issues, INITIAL_VALUE_RULES))
    issues.extend(map_framework_issues(safety_path_report.issues, SAFETY_PATH_RULES))
    issues.extend(map_framework_issues(taint_path_report.issues, TAINT_RULES))
    issues.extend(map_framework_issues(dataflow_report.issues, DATAFLOW_RULES))
    issues.extend(map_framework_issues(signal_lifecycle_report.issues, SIGNAL_LIFECYCLE_RULES))
    issues.extend(map_framework_issues(loop_stability_report.issues, LOOP_STABILITY_RULES))
    issues.extend(map_framework_issues(fault_handling_report.issues, FAULT_HANDLING_RULES))
    issues.extend(map_framework_issues(numeric_constraints_report.issues, NUMERIC_CONSTRAINT_RULES))
    issues.extend(map_framework_issues(config_drift_report.issues, CONFIG_DRIFT_RULES))
    issues.extend(map_framework_issues(unsafe_defaults_report.issues, UNSAFE_DEFAULT_RULES))
    issues.extend(map_trace_findings(detect_transform_invariant_violations(base_picture)))
    issues.extend(map_spec_issues(spec_report.issues))

    return SattLineSemanticsReport(
        basepicture_name=base_picture.header.name,
        issues=issues,
    )
