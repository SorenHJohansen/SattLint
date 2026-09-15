"""Semantic rule-group assembly: contracts, rule registries, and group builders."""

from __future__ import annotations

from dataclasses import replace

from ._sattline_semantic_contracts import (
    ALARM_RULE_CONTRACT,
    DATAFLOW_RULE_CONTRACT,
    SAME_CYCLE_RULE_CONTRACT,
    SFC_RULE_CONTRACT,
    SPEC_RULE_CONTRACT,
    TRACE_RULE_CONTRACT,
    VARIABLE_RULE_CONTRACT,
    SemanticRuleContract,
)
from ._sattline_semantic_models import SemanticRule, SemanticRuleGroup
from ._sattline_semantic_rules_data import (
    ALARM_RULES,
    DATAFLOW_RULES,
    SAME_CYCLE_RULES,
    SFC_RULES,
    SPEC_RULE_DESCRIPTIONS,
    SPEC_RULE_EXAMPLES,
    SPEC_RULE_NAMES,
    TRACE_RULES,
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
        "semantic.read-only-datatype-field",
        "semantic.read-only-non-const",
        "semantic.procedure-status-handling",
        "semantic.never-read-datatype-field",
        "semantic.never-read-write",
        "semantic.write-without-effect",
        "semantic.global-scope-minimization",
        "semantic.hidden-global-coupling",
        "semantic.high-fan-in-out-variable",
        "semantic.unknown-parameter-target",
        "semantic.string-mapping-mismatch",
        "semantic.duplicated-datatype-layout",
        "semantic.min-max-mapping-mismatch",
        "semantic.reset-contamination",
        "semantic.implicit-latch",
        "semantic.magic-number",
        "semantic.record-component-order-dependence",
        "semantic.shadowing",
        "semantic.unsafe-default-true",
        "semantic.read-before-write",
    ),
    **rule_contract_entries(
        SFC_RULE_CONTRACT,
        "semantic.unreachable-sequence-node",
        "semantic.unreachable-transition",
        "semantic.duplicate-transition-guard",
    ),
    **rule_contract_entries(
        ALARM_RULE_CONTRACT,
        "semantic.duplicate-alarm-tag",
        "semantic.duplicate-alarm-condition",
        "semantic.never-cleared-alarm",
    ),
    **rule_contract_entries(
        TRACE_RULE_CONTRACT,
        "semantic.duplicate-sibling-name",
        "semantic.unexpected-submodule-type",
    ),
    **rule_contract_entries(
        DATAFLOW_RULE_CONTRACT,
        "semantic.dead-overwrite",
        "semantic.conflicting-constants",
        "semantic.condition-always-true",
        "semantic.condition-always-false",
        "semantic.unreachable-branch",
        "semantic.self-compare-condition",
        "semantic.scan-cycle-stale-read",
        "semantic.scan-cycle-implicit-new",
        "semantic.non-state-multi-site",
    ),
    **rule_contract_entries(
        SAME_CYCLE_RULE_CONTRACT,
        "semantic.parallel-read-write-hazard",
        "semantic.parallel-write-race",
        "semantic.same-cycle-shared-access",
    ),
    **rule_contract_entries(SPEC_RULE_CONTRACT, *SPEC_RULE_DESCRIPTIONS.keys()),
}

for kind, rule in list(VARIABLE_RULES.items()):
    VARIABLE_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(SFC_RULES.items()):
    SFC_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(ALARM_RULES.items()):
    ALARM_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(TRACE_RULES.items()):
    TRACE_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(DATAFLOW_RULES.items()):
    DATAFLOW_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))
for kind, rule in list(SAME_CYCLE_RULES.items()):
    SAME_CYCLE_RULES[kind] = attach_rule_contract(rule, RULE_CONTRACTS_BY_ID.get(rule.id))

SPEC_FRAMEWORK_RULES: dict[str, SemanticRule] = {
    rule_id: attach_rule_contract(
        SemanticRule(
            id=rule_id,
            source="spec-compliance",
            description=description,
            explanation=description,
            name=SPEC_RULE_NAMES.get(rule_id, rule_id),
            example=SPEC_RULE_EXAMPLES.get(rule_id),
            suggestion="Rename, reconnect, or restructure the affected construct so it matches the engineering specification.",
        ),
        RULE_CONTRACTS_BY_ID.get(rule_id),
    )
    for rule_id, description in sorted(SPEC_RULE_DESCRIPTIONS.items())
}

FRAMEWORK_RULES_BY_KIND: dict[str, SemanticRule] = {
    **SFC_RULES,
    **ALARM_RULES,
    **DATAFLOW_RULES,
    **SAME_CYCLE_RULES,
    **SPEC_FRAMEWORK_RULES,
}


def build_semantic_rule_groups() -> tuple[SemanticRuleGroup, ...]:
    return (
        SemanticRuleGroup(source="variables", rules=tuple(VARIABLE_RULES.values())),
        SemanticRuleGroup(source="sfc", rules=tuple(SFC_RULES.values())),
        SemanticRuleGroup(source="alarm-integrity", rules=tuple(ALARM_RULES.values())),
        SemanticRuleGroup(source="tracing", rules=tuple(TRACE_RULES.values())),
        SemanticRuleGroup(source="dataflow", rules=tuple(DATAFLOW_RULES.values())),
        SemanticRuleGroup(source="same-cycle", rules=tuple(SAME_CYCLE_RULES.values())),
        SemanticRuleGroup(source="spec-compliance", rules=tuple(SPEC_FRAMEWORK_RULES.values())),
    )


__all__ = [
    "ALARM_RULES",
    "DATAFLOW_RULES",
    "FRAMEWORK_RULES_BY_KIND",
    "RULE_CONTRACTS_BY_ID",
    "SAME_CYCLE_RULES",
    "SFC_RULES",
    "SPEC_FRAMEWORK_RULES",
    "SPEC_RULE_DESCRIPTIONS",
    "SPEC_RULE_EXAMPLES",
    "SPEC_RULE_NAMES",
    "TRACE_RULES",
    "VARIABLE_RULES",
    "attach_rule_contract",
    "build_semantic_rule_groups",
]
