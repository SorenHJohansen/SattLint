"""Semantic rule declarations, part 2 (dataflow/safety/alarm/same-cycle/etc.)."""

from __future__ import annotations

from ._sattline_semantic_models import SemanticRule

DATAFLOW_RULES: dict[str, SemanticRule] = {
    "dataflow.dead_overwrite": SemanticRule(
        id="semantic.dead-overwrite",
        source="dataflow",
        category="variable-lifecycle",
        severity="warning",
        applies_to="variable",
        description="Writes whose value is overwritten before any later read can observe it.",
        name="Dead overwrite",
        example="ModuleCode\n   Flag = True;\n   Flag = Condition;   (* first write is overwritten before any read *)",
    ),
    "dataflow.condition_always_true": SemanticRule(
        id="semantic.condition-always-true",
        source="dataflow",
        category="control-flow",
        severity="warning",
        applies_to="condition",
        description="Conditions that always evaluate to true at a particular program point.",
        name="Condition always true",
        example="IF RawInput >= 0 OR RawInput < 0 THEN   (* covers every possible value *)\n   Output = 1;\nENDIF;",
    ),
    "dataflow.condition_always_false": SemanticRule(
        id="semantic.condition-always-false",
        source="dataflow",
        category="control-flow",
        severity="warning",
        applies_to="condition",
        description="Conditions that always evaluate to false at a particular program point.",
        name="Condition always false",
        example="IF RawInput < RawInput THEN   (* value can never be less than itself *)\n   Output = 1;\nENDIF;",
    ),
    "dataflow.unreachable_branch": SemanticRule(
        id="semantic.unreachable-branch",
        source="dataflow",
        category="control-flow",
        severity="warning",
        applies_to="branch",
        description="Branches that cannot execute because control-flow facts make them impossible.",
        name="Unreachable branch",
        example="IF Level > 100 AND Level < 50 THEN   (* impossible range *)\n   Output = 1;                         (* this branch can never run *)\nENDIF;",
    ),
    "dataflow.self_compare_condition": SemanticRule(
        id="semantic.self-compare-condition",
        source="dataflow",
        category="control-flow",
        severity="warning",
        applies_to="condition",
        description="Conditions that compare a symbol to itself and collapse to a constant result.",
        name="Self-compare condition",
        example="IF RawInput == RawInput THEN   (* always true, pointless check *)\n   Output = 1;\nENDIF;",
    ),
    "dataflow.scan_cycle_stale_read": SemanticRule(
        id="semantic.scan-cycle-stale-read",
        source="dataflow",
        category="control-flow",
        severity="warning",
        applies_to="state-variable",
        description=":OLD reads after a same-scan write where the expression still relies on the previous-scan snapshot.",
        name="Stale :OLD read",
        example="Counter = Counter + 1;   (* written this scan ... *)\nIF Counter:Old == 0 THEN   (* ... but :OLD reads the previous-scan value *)",
    ),
    "dataflow.scan_cycle_implicit_new": SemanticRule(
        id="semantic.scan-cycle-implicit-new",
        source="dataflow",
        category="control-flow",
        severity="warning",
        applies_to="state-variable",
        description="Implicit same-scan reads of a state variable after a write should use :NEW when they rely on the updated value.",
        name="Implicit :NEW read",
        example="SEQUENCE MainSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0\n   SEQSTEP WriteStep\n      ENTERCODE\n         Level = 5;\n   SEQTRANSITION TrNext WAIT_FOR Level == 5  (* implicit read may see the old value *)",
    ),
    "dataflow.scan_cycle_temporal_misuse": SemanticRule(
        id="semantic.scan-cycle-temporal-misuse",
        source="dataflow",
        category="control-flow",
        severity="error",
        applies_to="state-variable",
        description=":OLD references are read-only and cannot be used as write targets or out-parameters.",
        name=":OLD misuse",
        example="Counter:Old = 0;   (* :OLD is read-only and cannot be written *)",
    ),
    "dataflow.invalid_state_access": SemanticRule(
        id="semantic.invalid-state-access",
        source="dataflow",
        category="control-flow",
        severity="error",
        applies_to="state-variable",
        description=":OLD and :NEW access is only valid on variables or leaf fields declared State.",
        name="Invalid state access",
        example="LOCALVARIABLES\n   Counter: integer := 0;   (* not declared State *)\nModuleCode\n   IF Counter:Old == 0 THEN (* :Old is not allowed on a plain variable *)",
    ),
}

SIGNAL_LIFECYCLE_RULES: dict[str, SemanticRule] = {
    "signal_lifecycle.read_before_write": SemanticRule(
        id="semantic.signal-lifecycle-read-before-write",
        source="signal-lifecycle",
        category="variable-lifecycle",
        severity="warning",
        applies_to="signal",
        description="Signals should not be consumed before any definite write in the current scope.",
        name="Signal read before write",
        example="LOCALVARIABLES\n   Uninitialized: boolean;   (* no init value *)\nModuleCode\n   Output = Uninitialized;   (* read before any definite write *)",
    ),
}

LOOP_STABILITY_RULES: dict[str, SemanticRule] = {
    "loop_stability.conflicting_setpoint": SemanticRule(
        id="semantic.loop-conflicting-setpoint",
        source="loop-stability",
        category="control-flow",
        severity="warning",
        applies_to="setpoint",
        description="The same setpoint should not receive conflicting literal assignments in one scope.",
        name="Conflicting setpoint",
        example="ModuleCode\n   TemperatureSetpoint = 50;   (* setpoint fixed to 50 ... *)\n   TemperatureSetpoint = 80;   (* ... then reassigned to 80 in the same scope *)",
    ),
}

NUMERIC_CONSTRAINT_RULES: dict[str, SemanticRule] = {
    "numeric_constraints.limit_violation": SemanticRule(
        id="semantic.numeric-limit-violation",
        source="numeric-constraints",
        category="engineering-spec",
        severity="warning",
        applies_to="numeric-variable",
        description="Assignments should stay within the visible Min_/Max_ bounds declared for the target variable.",
        name="Limit violation",
        example="LOCALVARIABLES\n   OutputLevel: integer := 0;\n   Min_OutputLevel: integer := 0;\n   Max_OutputLevel: integer := 100;\nModuleCode\n   OutputLevel = 250;   (* exceeds the declared Max_OutputLevel bound *)",
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
        name="Unsafe boolean default",
        example="LOCALVARIABLES\n   SafetyBypass: boolean := True;   (* safety bypass active from startup *)",
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

SPEC_RULE_NAMES: dict[str, str] = {
    "spec.basepicture_direct_code": "Code outside a frame module",
    "spec.sequence_step_prefix": "Wrong sequence step prefix",
    "spec.transition_name_missing": "Transition has no name",
    "spec.transition_prefix": "Wrong transition prefix",
    "spec.opmessage_use_signature": "OPMessage UseSignature enabled",
    "spec.mes_batch_control_name": "Wrong MES_BatchControl name",
    "spec.mes_batch_control_max_try": "Wrong MES_BatchControl Max_TRY",
    "spec.mes_batch_control_repeat_try": "Wrong MES_BatchControl Repeat_TRY",
}

SPEC_RULE_EXAMPLES: dict[str, str] = {
    "spec.basepicture_direct_code": (
        "BasePicture Invocation\n"
        "   ( 0.0, 0.0, 0.0, 1.0, 1.0 ) : MODULEDEFINITION DateCode_ 1\n"
        "ModuleCode\n"
        "   Output = RawInput;   (* code written outside a frame module *)"
    ),
    "spec.sequence_step_prefix": "SEQSTEP step_mix   (* should use the required step prefix *)",
    "spec.transition_name_missing": "SEQTRANSITION WAIT_FOR Done   (* transition has no name *)",
    "spec.transition_prefix": "SEQTRANSITION MyTrans WAIT_FOR Done   (* MyTrans does not use the required prefix *)",
    "spec.opmessage_use_signature": "OPMsg Invocation\n   ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : OPMessage (UseSignature => True)",
    "spec.mes_batch_control_name": "MESBC Invocation\n   ( 0.5, 0.0, 0.0, 0.4, 0.4 ) : MES_BatchControl   (* instance name does not match the required name *)",
    "spec.mes_batch_control_max_try": "Batch Invocation\n   ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : MES_BatchControl (Max_TRY => 0)",
    "spec.mes_batch_control_repeat_try": "Batch Invocation\n   ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : MES_BatchControl (Repeat_TRY => 0)",
}

__all__ = [
    "DATAFLOW_RULES",
    "LOOP_STABILITY_RULES",
    "NUMERIC_CONSTRAINT_RULES",
    "SIGNAL_LIFECYCLE_RULES",
    "SPEC_RULE_DESCRIPTIONS",
    "SPEC_RULE_EXAMPLES",
    "SPEC_RULE_NAMES",
    "UNSAFE_DEFAULT_RULES",
]
