from __future__ import annotations

from dataclasses import replace

from ..reporting.variables_report import IssueKind
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


VARIABLE_RULES: dict[IssueKind, SemanticRule] = {
    IssueKind.UNUSED: SemanticRule(
        id="semantic.unused-variable",
        source="variables",
        category="variable-lifecycle",
        severity="warning",
        applies_to="variable",
        description="Declared variables that are never read or written.",
    ),
    IssueKind.UNUSED_DATATYPE_FIELD: SemanticRule(
        id="semantic.unused-datatype-field",
        source="variables",
        category="variable-lifecycle",
        severity="warning",
        applies_to="datatype-field",
        description="Datatype fields that are never used across the analyzed target.",
    ),
    IssueKind.READ_ONLY_NON_CONST: SemanticRule(
        id="semantic.read-only-non-const",
        source="variables",
        category="variable-lifecycle",
        severity="warning",
        applies_to="variable",
        description="Writable declarations that are only ever read.",
    ),
    IssueKind.NAMING_ROLE_MISMATCH: SemanticRule(
        id="semantic.naming-role-mismatch",
        source="variables",
        category="engineering-spec",
        severity="warning",
        applies_to="variable",
        description="Role-bearing variable prefixes or suffixes such as Cmd, Status, and Alarm should align with observed read and write behavior.",
    ),
    IssueKind.UI_ONLY: SemanticRule(
        id="semantic.ui-only-variable",
        source="variables",
        category="variable-lifecycle",
        severity="warning",
        applies_to="variable",
        description="Variables that are only consumed through graphics or interact display wiring.",
    ),
    IssueKind.PROCEDURE_STATUS: SemanticRule(
        id="semantic.procedure-status-handling",
        source="variables",
        category="control-flow",
        severity="warning",
        applies_to="procedure-status",
        description="Procedure status outputs should be checked in control logic instead of being ignored or shown only in UI.",
    ),
    IssueKind.NEVER_READ: SemanticRule(
        id="semantic.never-read-write",
        source="variables",
        category="variable-lifecycle",
        severity="warning",
        applies_to="variable",
        description="Variables that are written but never subsequently read.",
    ),
    IssueKind.WRITE_WITHOUT_EFFECT: SemanticRule(
        id="semantic.write-without-effect",
        source="variables",
        category="variable-lifecycle",
        severity="warning",
        applies_to="variable",
        description="Variables whose written values are read internally but never reach a root-visible output.",
    ),
    IssueKind.GLOBAL_SCOPE_MINIMIZATION: SemanticRule(
        id="semantic.global-scope-minimization",
        source="variables",
        category="interface-contracts",
        severity="warning",
        applies_to="global-variable",
        description="Root globals whose access never escapes a single module subtree and can be localized.",
    ),
    IssueKind.HIDDEN_GLOBAL_COUPLING: SemanticRule(
        id="semantic.hidden-global-coupling",
        source="variables",
        category="interface-contracts",
        severity="warning",
        applies_to="global-variable",
        description="Root globals that act as implicit interfaces across multiple module paths.",
    ),
    IssueKind.HIGH_FAN_IN_OUT: SemanticRule(
        id="semantic.high-fan-in-out-variable",
        source="variables",
        category="interface-contracts",
        severity="warning",
        applies_to="global-variable",
        description="Root globals that are read or written by many distinct module paths and become highly shared coordination points.",
    ),
    IssueKind.UNKNOWN_PARAMETER_TARGET: SemanticRule(
        id="semantic.unknown-parameter-target",
        source="variables",
        category="interface-contracts",
        severity="error",
        applies_to="parameter-mapping",
        description="Parameter mappings that target undeclared module parameters.",
    ),
    IssueKind.REQUIRED_PARAMETER_CONNECTION: SemanticRule(
        id="semantic.required-parameter-connection",
        source="variables",
        category="interface-contracts",
        severity="error",
        applies_to="parameter-mapping",
        description="Module instances that leave internally used moduletype parameters unmapped.",
    ),
    IssueKind.CONTRACT_MISMATCH: SemanticRule(
        id="semantic.cross-module-contract-mismatch",
        source="variables",
        category="interface-contracts",
        severity="error",
        applies_to="parameter-mapping",
        description="Parameter mappings whose connected datatypes are incompatible across module boundaries.",
    ),
    IssueKind.STRING_MAPPING_MISMATCH: SemanticRule(
        id="semantic.string-mapping-mismatch",
        source="variables",
        category="interface-contracts",
        severity="error",
        applies_to="parameter-mapping",
        description="Parameter mappings whose string-like datatypes are incompatible.",
    ),
    IssueKind.DATATYPE_DUPLICATION: SemanticRule(
        id="semantic.duplicated-datatype-layout",
        source="variables",
        category="module-structure",
        severity="warning",
        applies_to="datatype",
        description="Complex datatypes that appear duplicated by structure.",
    ),
    IssueKind.NAME_COLLISION: SemanticRule(
        id="semantic.name-collision",
        source="variables",
        category="module-structure",
        severity="warning",
        applies_to="scope",
        description="Case-insensitive declaration name collisions within a scope.",
    ),
    IssueKind.LAYOUT_OVERLAP: SemanticRule(
        id="semantic.layout-overlap",
        source="variables",
        category="module-structure",
        severity="warning",
        applies_to="layout",
        description="Sibling module invocations and rectangular graph or interact objects should not overlap in the same layout scope.",
    ),
    IssueKind.MIN_MAX_MAPPING_MISMATCH: SemanticRule(
        id="semantic.min-max-mapping-mismatch",
        source="variables",
        category="interface-contracts",
        severity="warning",
        applies_to="parameter-mapping",
        description="Min_/Max_ parameter mappings that do not line up by base name.",
    ),
    IssueKind.SHADOWING: SemanticRule(
        id="semantic.shadowing",
        source="shadowing",
        category="module-structure",
        severity="warning",
        applies_to="scope",
        description="Local declarations that shadow outer or global names.",
    ),
    IssueKind.RESET_CONTAMINATION: SemanticRule(
        id="semantic.reset-contamination",
        source="variables",
        category="control-flow",
        severity="warning",
        applies_to="sequence",
        description="Reset-state writes that are missing or incomplete across sequence flow.",
    ),
    IssueKind.IMPLICIT_LATCH: SemanticRule(
        id="semantic.implicit-latch",
        source="variables",
        category="control-flow",
        severity="warning",
        applies_to="boolean-variable",
        description="Boolean values that are set on some branches or steps without a matching False write on the complementary path.",
    ),
}

SFC_RULES: dict[str, SemanticRule] = {
    "sfc_parallel_write_race": SemanticRule(
        id="semantic.parallel-write-race",
        source="sfc",
        category="control-flow",
        severity="error",
        applies_to="sequence",
        description="Parallel SFC branches that write to the same variable or field.",
    ),
    "sfc_unreachable_sequence_node": SemanticRule(
        id="semantic.unreachable-sequence-node",
        source="sfc",
        category="control-flow",
        severity="warning",
        applies_to="sequence-node",
        description="Sequence nodes that cannot execute because an earlier node terminates the branch.",
    ),
    "sfc_unreachable_transition": SemanticRule(
        id="semantic.unreachable-transition",
        source="sfc",
        category="control-flow",
        severity="warning",
        applies_to="transition",
        description="Transitions that can never fire because an earlier node structurally terminates the branch.",
    ),
    "sfc_transition_always_true": SemanticRule(
        id="semantic.transition-always-true",
        source="sfc",
        category="control-flow",
        severity="warning",
        applies_to="transition",
        description="Transitions with guards that simplify to true and therefore always fire when reached.",
    ),
    "sfc_transition_always_false": SemanticRule(
        id="semantic.transition-always-false",
        source="sfc",
        category="control-flow",
        severity="warning",
        applies_to="transition",
        description="Transitions with guards that simplify to false and therefore can never fire.",
    ),
    "sfc_duplicate_transition_guard": SemanticRule(
        id="semantic.duplicate-transition-guard",
        source="sfc",
        category="control-flow",
        severity="warning",
        applies_to="transition",
        description="Transitions in the same sequence branch that normalize to the same guard logic.",
    ),
    "sfc_illegal_state_combination": SemanticRule(
        id="semantic.illegal-state-combination",
        source="sfc",
        category="control-flow",
        severity="error",
        applies_to="sequence",
        description="Configured mutually exclusive SFC steps can become active at the same time.",
    ),
    "sfc_missing_step_enter_contract": SemanticRule(
        id="semantic.missing-step-enter-contract",
        source="sfc",
        category="control-flow",
        severity="warning",
        applies_to="step",
        description="Configured SFC steps should initialize their required state in the enter block.",
    ),
    "sfc_missing_step_exit_contract": SemanticRule(
        id="semantic.missing-step-exit-contract",
        source="sfc",
        category="control-flow",
        severity="warning",
        applies_to="step",
        description="Configured SFC steps should clean up their required state in the exit block.",
    ),
    "sfc_step_state_leakage": SemanticRule(
        id="semantic.step-state-leakage",
        source="sfc",
        category="control-flow",
        severity="warning",
        applies_to="step",
        description="Configured SFC steps can inherit stale state from earlier steps when required enter writes are missing.",
    ),
}

ALARM_RULES: dict[str, SemanticRule] = {
    "alarm.duplicate_tag": SemanticRule(
        id="semantic.duplicate-alarm-tag",
        source="alarm-integrity",
        category="interface-contracts",
        severity="error",
        applies_to="alarm-source",
        description="Alarm sources should not reuse the same tag across the analyzed target.",
    ),
    "alarm.duplicate_condition": SemanticRule(
        id="semantic.duplicate-alarm-condition",
        source="alarm-integrity",
        category="control-flow",
        severity="warning",
        applies_to="alarm-source",
        description="Alarm sources should not reuse the same condition without deliberate deduplication.",
    ),
    "alarm.conflicting_priority": SemanticRule(
        id="semantic.conflicting-alarm-priority",
        source="alarm-integrity",
        category="interface-contracts",
        severity="warning",
        applies_to="alarm-source",
        description="The same alarm tag or condition should not be configured with conflicting priorities or severities.",
    ),
    "alarm.never_cleared": SemanticRule(
        id="semantic.never-cleared-alarm",
        source="alarm-integrity",
        category="control-flow",
        severity="warning",
        applies_to="alarm-variable",
        description="Alarm variables that are only forced true and never explicitly cleared can latch unexpectedly.",
    ),
}

INITIAL_VALUE_RULES: dict[str, SemanticRule] = {
    "initial-values.missing_required_default": SemanticRule(
        id="semantic.missing-parameter-initial-value",
        source="initial-values",
        category="interface-contracts",
        severity="warning",
        applies_to="parameter-module",
        description="Recipe and engineering parameter modules should resolve a startup value through a default or an explicitly initialized mapping.",
    ),
}

SAFETY_PATH_RULES: dict[str, SemanticRule] = {
    "safety-path.unconsumed_signal": SemanticRule(
        id="semantic.unconsumed-safety-signal",
        source="safety-paths",
        category="control-flow",
        severity="warning",
        applies_to="signal",
        description="Safety-critical signals that are written but never consumed across the analyzed target.",
    ),
}

TRACE_RULES: dict[str, SemanticRule] = {
    "duplicate_sibling_name": SemanticRule(
        id="semantic.duplicate-sibling-name",
        source="tracing",
        category="module-structure",
        severity="error",
        applies_to="module",
        description="Sibling modules with the same case-insensitive name.",
    ),
    "unexpected_submodule_type": SemanticRule(
        id="semantic.unexpected-submodule-type",
        source="tracing",
        category="module-structure",
        severity="error",
        applies_to="module",
        description="Unexpected non-module nodes under the submodule tree.",
    ),
}

DATAFLOW_RULES: dict[str, SemanticRule] = {
    "dataflow.read_before_write": SemanticRule(
        id="semantic.read-before-write",
        source="dataflow",
        category="variable-lifecycle",
        severity="warning",
        applies_to="variable",
        description="Variable reads that can occur before any definite assignment on the current path.",
    ),
    "dataflow.dead_overwrite": SemanticRule(
        id="semantic.dead-overwrite",
        source="dataflow",
        category="variable-lifecycle",
        severity="warning",
        applies_to="variable",
        description="Writes whose value is overwritten before any later read can observe it.",
    ),
    "dataflow.condition_always_true": SemanticRule(
        id="semantic.condition-always-true",
        source="dataflow",
        category="control-flow",
        severity="warning",
        applies_to="condition",
        description="Conditions that always evaluate to true at a particular program point.",
    ),
    "dataflow.condition_always_false": SemanticRule(
        id="semantic.condition-always-false",
        source="dataflow",
        category="control-flow",
        severity="warning",
        applies_to="condition",
        description="Conditions that always evaluate to false at a particular program point.",
    ),
    "dataflow.unreachable_branch": SemanticRule(
        id="semantic.unreachable-branch",
        source="dataflow",
        category="control-flow",
        severity="warning",
        applies_to="branch",
        description="Branches that cannot execute because control-flow facts make them impossible.",
    ),
    "dataflow.unreachable_sequence_node": SemanticRule(
        id="semantic.unreachable-sequence-node-dataflow",
        source="dataflow",
        category="control-flow",
        severity="warning",
        applies_to="sequence-node",
        description="Sequence nodes that cannot execute after an earlier terminating node in the same branch.",
    ),
    "dataflow.self_compare_condition": SemanticRule(
        id="semantic.self-compare-condition",
        source="dataflow",
        category="control-flow",
        severity="warning",
        applies_to="condition",
        description="Conditions that compare a symbol to itself and collapse to a constant result.",
    ),
    "dataflow.scan_cycle_stale_read": SemanticRule(
        id="semantic.scan-cycle-stale-read",
        source="dataflow",
        category="control-flow",
        severity="warning",
        applies_to="state-variable",
        description=":OLD reads after a same-scan write where the expression still relies on the previous-scan snapshot.",
    ),
    "dataflow.scan_cycle_implicit_new": SemanticRule(
        id="semantic.scan-cycle-implicit-new",
        source="dataflow",
        category="control-flow",
        severity="warning",
        applies_to="state-variable",
        description="Implicit same-scan reads of a state variable after a write should use :NEW when they rely on the updated value.",
    ),
    "dataflow.scan_cycle_temporal_misuse": SemanticRule(
        id="semantic.scan-cycle-temporal-misuse",
        source="dataflow",
        category="control-flow",
        severity="error",
        applies_to="state-variable",
        description=":OLD references are read-only and cannot be used as write targets or out-parameters.",
    ),
}

SIGNAL_LIFECYCLE_RULES: dict[str, SemanticRule] = {
    "signal_lifecycle.read_before_write": SemanticRule(
        id="semantic.signal-lifecycle-read-before-write",
        source="signal_lifecycle",
        category="variable-lifecycle",
        severity="warning",
        applies_to="signal",
        description="Signals should not be consumed before any definite write in the current scope.",
    ),
    "signal_lifecycle.unconsumed_write": SemanticRule(
        id="semantic.signal-lifecycle-unconsumed-write",
        source="signal_lifecycle",
        category="variable-lifecycle",
        severity="warning",
        applies_to="signal",
        description="Signals that are written in a scope should be consumed later in that same scope.",
    ),
}

LOOP_STABILITY_RULES: dict[str, SemanticRule] = {
    "loop_stability.conflicting_setpoint": SemanticRule(
        id="semantic.loop-conflicting-setpoint",
        source="loop_stability",
        category="control-flow",
        severity="warning",
        applies_to="setpoint",
        description="The same setpoint should not receive conflicting literal assignments in one scope.",
    ),
}

FAULT_HANDLING_RULES: dict[str, SemanticRule] = {
    "fault_handling.missing_recovery": SemanticRule(
        id="semantic.fault-missing-recovery",
        source="fault_handling",
        category="control-flow",
        severity="warning",
        applies_to="fault-path",
        description="Fault paths that are raised should also be explicitly cleared or acknowledged in the same scope.",
    ),
    "fault_handling.unhandled_fault": SemanticRule(
        id="semantic.fault-unhandled-path",
        source="fault_handling",
        category="control-flow",
        severity="warning",
        applies_to="fault-path",
        description="Fault paths that are raised should be consumed by reachable handling logic in the same scope.",
    ),
}

NUMERIC_CONSTRAINT_RULES: dict[str, SemanticRule] = {
    "numeric_constraints.limit_violation": SemanticRule(
        id="semantic.numeric-limit-violation",
        source="numeric_constraints",
        category="engineering-spec",
        severity="warning",
        applies_to="numeric-variable",
        description="Assignments should stay within the visible Min_/Max_ bounds declared for the target variable.",
    ),
}

CONFIG_DRIFT_RULES: dict[str, SemanticRule] = {
    "config_drift.instance_configuration": SemanticRule(
        id="semantic.instance-configuration-drift",
        source="config_drift",
        category="interface-contracts",
        severity="warning",
        applies_to="module-instance-group",
        description="Instances of the same moduletype should not drift on mapped configuration parameter values without intent.",
    ),
}

TAINT_RULES: dict[str, SemanticRule] = {
    "taint-path.external_input_to_critical_sink": SemanticRule(
        id="semantic.external-input-to-critical-sink",
        source="taint-paths",
        category="interface-contracts",
        severity="warning",
        applies_to="flow-path",
        description="External MES, operator, or sensor inputs that propagate into safety-critical sinks across modules.",
    ),
}

UNSAFE_DEFAULT_RULES: dict[str, SemanticRule] = {
    "unsafe_defaults.true_boolean_default": SemanticRule(
        id="semantic.unsafe-default-true",
        source="unsafe-defaults",
        category="engineering-spec",
        severity="warning",
        applies_to="variable",
        description="Boolean defaults that enable logic or bypass safeguards from startup.",
    ),
}

SPEC_RULE_DESCRIPTIONS: dict[str, str] = {
    "spec.basepicture_direct_code": "BasePicture code must stay inside frame modules.",
    "spec.sequence_step_prefix": "Sequence steps must use the required engineering-spec naming prefix.",
    "spec.transition_name_missing": "All transitions must be named.",
    "spec.transition_prefix": "Transitions must use the required engineering-spec naming prefix.",
    "spec.opmessage_use_signature": "OPMessage instances must not enable UseSignature=True.",
    "spec.mes_batch_control_name": "MES_BatchControl instances must use the required instance name.",
    "spec.mes_batch_control_max_try": "MES_BatchControl Max_TRY must resolve to the required value.",
    "spec.mes_batch_control_repeat_try": "MES_BatchControl Repeat_TRY must resolve to the required value.",
}

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
