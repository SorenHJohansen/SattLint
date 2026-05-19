from __future__ import annotations

from ._sattline_semantic_models import SemanticRule

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
    "dataflow.invalid_state_access": SemanticRule(
        id="semantic.invalid-state-access",
        source="dataflow",
        category="control-flow",
        severity="error",
        applies_to="state-variable",
        description=":OLD and :NEW access is only valid on variables or leaf fields declared State.",
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

__all__ = [
    "CONFIG_DRIFT_RULES",
    "DATAFLOW_RULES",
    "FAULT_HANDLING_RULES",
    "LOOP_STABILITY_RULES",
    "NUMERIC_CONSTRAINT_RULES",
    "SIGNAL_LIFECYCLE_RULES",
    "SPEC_RULE_DESCRIPTIONS",
    "TAINT_RULES",
    "UNSAFE_DEFAULT_RULES",
]
