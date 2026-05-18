from __future__ import annotations

from dataclasses import replace

from ._sattline_semantic_contracts import (
    ALARM_RULE_CONTRACT,
    CONFIG_DRIFT_RULE_CONTRACT,
    DATAFLOW_RULE_CONTRACT,
    FAULT_HANDLING_RULE_CONTRACT,
    INITIAL_VALUES_RULE_CONTRACT,
    LOOP_STABILITY_RULE_CONTRACT,
    NUMERIC_CONSTRAINTS_RULE_CONTRACT,
    SAFETY_RULE_CONTRACT,
    SFC_RULE_CONTRACT,
    SHADOWING_RULE_CONTRACT,
    SIGNAL_LIFECYCLE_RULE_CONTRACT,
    SPEC_RULE_CONTRACT,
    TAINT_RULE_CONTRACT,
    TRACE_RULE_CONTRACT,
    UNSAFE_DEFAULTS_RULE_CONTRACT,
    VARIABLE_RULE_CONTRACT,
    SemanticRuleContract,
)
from ._sattline_semantic_models import SemanticRule, SemanticRuleGroup
from ._sattline_semantic_rules_data import (
    ALARM_RULES,
    CONFIG_DRIFT_RULES,
    DATAFLOW_RULES,
    FAULT_HANDLING_RULES,
    INITIAL_VALUE_RULES,
    LOOP_STABILITY_RULES,
    NUMERIC_CONSTRAINT_RULES,
    SAFETY_PATH_RULES,
    SFC_RULES,
    SIGNAL_LIFECYCLE_RULES,
    SPEC_RULE_DESCRIPTIONS,
    TAINT_RULES,
    TRACE_RULES,
    UNSAFE_DEFAULT_RULES,
    VARIABLE_RULES,
)


def rule_contract_entries(
    contract: SemanticRuleContract,
    *rule_ids: str,
) -> dict[str, SemanticRuleContract]:
    return dict.fromkeys(rule_ids, contract)


def attach_rule_contract(
    rule: SemanticRule,
    contract: SemanticRuleContract | None,
) -> SemanticRule:
    if contract is None:
        return rule
    return replace(
        rule,
        acceptance_tests=contract.acceptance_tests,
        corpus_cases=contract.corpus_cases,
        mutation_applicability=contract.mutation_applicability,
        suppression_modes=contract.suppression_modes,
        incremental_safe=contract.incremental_safe,
    )


RULE_CONTRACTS_BY_ID: dict[str, SemanticRuleContract] = {
    **rule_contract_entries(
        VARIABLE_RULE_CONTRACT,
        "semantic.unused-variable",
        "semantic.unused-datatype-field",
        "semantic.read-only-non-const",
        "semantic.naming-role-mismatch",
        "semantic.ui-only-variable",
        "semantic.procedure-status-handling",
        "semantic.never-read-write",
        "semantic.write-without-effect",
        "semantic.global-scope-minimization",
        "semantic.hidden-global-coupling",
        "semantic.high-fan-in-out-variable",
        "semantic.unknown-parameter-target",
        "semantic.required-parameter-connection",
        "semantic.cross-module-contract-mismatch",
        "semantic.string-mapping-mismatch",
        "semantic.duplicated-datatype-layout",
        "semantic.name-collision",
        "semantic.layout-overlap",
        "semantic.min-max-mapping-mismatch",
        "semantic.reset-contamination",
        "semantic.implicit-latch",
    ),
    **rule_contract_entries(SHADOWING_RULE_CONTRACT, "semantic.shadowing"),
    **rule_contract_entries(
        SFC_RULE_CONTRACT,
        "semantic.parallel-write-race",
        "semantic.unreachable-sequence-node",
        "semantic.unreachable-transition",
        "semantic.transition-always-true",
        "semantic.transition-always-false",
        "semantic.duplicate-transition-guard",
        "semantic.illegal-state-combination",
        "semantic.missing-step-enter-contract",
        "semantic.missing-step-exit-contract",
        "semantic.step-state-leakage",
    ),
    **rule_contract_entries(
        ALARM_RULE_CONTRACT,
        "semantic.duplicate-alarm-tag",
        "semantic.duplicate-alarm-condition",
        "semantic.conflicting-alarm-priority",
        "semantic.never-cleared-alarm",
    ),
    **rule_contract_entries(
        INITIAL_VALUES_RULE_CONTRACT,
        "semantic.missing-parameter-initial-value",
    ),
    **rule_contract_entries(SAFETY_RULE_CONTRACT, "semantic.unconsumed-safety-signal"),
    **rule_contract_entries(TAINT_RULE_CONTRACT, "semantic.external-input-to-critical-sink"),
    **rule_contract_entries(
        TRACE_RULE_CONTRACT,
        "semantic.duplicate-sibling-name",
        "semantic.unexpected-submodule-type",
    ),
    **rule_contract_entries(
        DATAFLOW_RULE_CONTRACT,
        "semantic.read-before-write",
        "semantic.dead-overwrite",
        "semantic.condition-always-true",
        "semantic.condition-always-false",
        "semantic.unreachable-branch",
        "semantic.unreachable-sequence-node-dataflow",
        "semantic.self-compare-condition",
        "semantic.scan-cycle-stale-read",
        "semantic.scan-cycle-implicit-new",
        "semantic.scan-cycle-temporal-misuse",
    ),
    **rule_contract_entries(
        SIGNAL_LIFECYCLE_RULE_CONTRACT,
        "semantic.signal-lifecycle-read-before-write",
        "semantic.signal-lifecycle-unconsumed-write",
    ),
    **rule_contract_entries(LOOP_STABILITY_RULE_CONTRACT, "semantic.loop-conflicting-setpoint"),
    **rule_contract_entries(
        FAULT_HANDLING_RULE_CONTRACT,
        "semantic.fault-missing-recovery",
        "semantic.fault-unhandled-path",
    ),
    **rule_contract_entries(
        NUMERIC_CONSTRAINTS_RULE_CONTRACT,
        "semantic.numeric-limit-violation",
    ),
    **rule_contract_entries(CONFIG_DRIFT_RULE_CONTRACT, "semantic.instance-configuration-drift"),
    **rule_contract_entries(UNSAFE_DEFAULTS_RULE_CONTRACT, "semantic.unsafe-default-true"),
    **rule_contract_entries(SPEC_RULE_CONTRACT, *SPEC_RULE_DESCRIPTIONS.keys()),
}

for kind, rule in list(VARIABLE_RULES.items()):
    VARIABLE_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(SFC_RULES.items()):
    SFC_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(ALARM_RULES.items()):
    ALARM_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(INITIAL_VALUE_RULES.items()):
    INITIAL_VALUE_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(SAFETY_PATH_RULES.items()):
    SAFETY_PATH_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(TRACE_RULES.items()):
    TRACE_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(DATAFLOW_RULES.items()):
    DATAFLOW_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(SIGNAL_LIFECYCLE_RULES.items()):
    SIGNAL_LIFECYCLE_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(LOOP_STABILITY_RULES.items()):
    LOOP_STABILITY_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(FAULT_HANDLING_RULES.items()):
    FAULT_HANDLING_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(NUMERIC_CONSTRAINT_RULES.items()):
    NUMERIC_CONSTRAINT_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(CONFIG_DRIFT_RULES.items()):
    CONFIG_DRIFT_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(TAINT_RULES.items()):
    TAINT_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(UNSAFE_DEFAULT_RULES.items()):
    UNSAFE_DEFAULT_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))

SPEC_FRAMEWORK_RULES: dict[str, SemanticRule] = {
    rule_id: attach_rule_contract(
        SemanticRule(
            id=rule_id,
            source="spec-compliance",
            category="engineering-spec",
            severity="warning",
            confidence="style",
            applies_to="sattline-construct",
            description=description,
            explanation=description,
            suggestion="Rename, reconnect, or restructure the affected construct so it matches the engineering specification.",
        ),
        RULE_CONTRACTS_BY_ID.get(rule_id),
    )
    for rule_id, description in sorted(SPEC_RULE_DESCRIPTIONS.items())
}

FRAMEWORK_RULES_BY_KIND: dict[str, SemanticRule] = {
    **SFC_RULES,
    **ALARM_RULES,
    **INITIAL_VALUE_RULES,
    **SAFETY_PATH_RULES,
    **TAINT_RULES,
    **DATAFLOW_RULES,
    **SIGNAL_LIFECYCLE_RULES,
    **LOOP_STABILITY_RULES,
    **FAULT_HANDLING_RULES,
    **NUMERIC_CONSTRAINT_RULES,
    **CONFIG_DRIFT_RULES,
    **UNSAFE_DEFAULT_RULES,
    **SPEC_FRAMEWORK_RULES,
}


def build_semantic_rule_groups() -> tuple[SemanticRuleGroup, ...]:
    return (
        SemanticRuleGroup(source="variables", rules=tuple(VARIABLE_RULES.values())),
        SemanticRuleGroup(source="sfc", rules=tuple(SFC_RULES.values())),
        SemanticRuleGroup(source="alarm-integrity", rules=tuple(ALARM_RULES.values())),
        SemanticRuleGroup(source="initial-values", rules=tuple(INITIAL_VALUE_RULES.values())),
        SemanticRuleGroup(source="safety-paths", rules=tuple(SAFETY_PATH_RULES.values())),
        SemanticRuleGroup(source="taint-paths", rules=tuple(TAINT_RULES.values())),
        SemanticRuleGroup(source="tracing", rules=tuple(TRACE_RULES.values())),
        SemanticRuleGroup(source="dataflow", rules=tuple(DATAFLOW_RULES.values())),
        SemanticRuleGroup(source="signal_lifecycle", rules=tuple(SIGNAL_LIFECYCLE_RULES.values())),
        SemanticRuleGroup(source="loop_stability", rules=tuple(LOOP_STABILITY_RULES.values())),
        SemanticRuleGroup(source="fault_handling", rules=tuple(FAULT_HANDLING_RULES.values())),
        SemanticRuleGroup(source="numeric_constraints", rules=tuple(NUMERIC_CONSTRAINT_RULES.values())),
        SemanticRuleGroup(source="config_drift", rules=tuple(CONFIG_DRIFT_RULES.values())),
        SemanticRuleGroup(source="unsafe-defaults", rules=tuple(UNSAFE_DEFAULT_RULES.values())),
        SemanticRuleGroup(source="spec-compliance", rules=tuple(SPEC_FRAMEWORK_RULES.values())),
    )


__all__ = [
    "ALARM_RULES",
    "CONFIG_DRIFT_RULES",
    "DATAFLOW_RULES",
    "FAULT_HANDLING_RULES",
    "FRAMEWORK_RULES_BY_KIND",
    "INITIAL_VALUE_RULES",
    "LOOP_STABILITY_RULES",
    "NUMERIC_CONSTRAINT_RULES",
    "RULE_CONTRACTS_BY_ID",
    "SAFETY_PATH_RULES",
    "SFC_RULES",
    "SIGNAL_LIFECYCLE_RULES",
    "SPEC_FRAMEWORK_RULES",
    "SPEC_RULE_DESCRIPTIONS",
    "TAINT_RULES",
    "TRACE_RULES",
    "UNSAFE_DEFAULT_RULES",
    "VARIABLE_RULES",
    "attach_rule_contract",
    "build_semantic_rule_groups",
]
