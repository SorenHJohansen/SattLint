"""Semantic rule declarations, part 2 (dataflow/safety/alarm/same-cycle/etc.)."""

from __future__ import annotations

from ._sattline_semantic_models import SemanticRule

DATAFLOW_RULES: dict[str, SemanticRule] = {
    "dataflow.dead_overwrite": SemanticRule(
        id="semantic.dead-overwrite",
        source="dataflow",
        description="Writes whose value is overwritten before any later read can observe it.",
        name="Dead overwrite",
        example="ModuleCode\n   Flag = True;\n   Flag = Condition;   (* first write is overwritten before any read *)",
    ),
    "dataflow.conflicting_constants": SemanticRule(
        id="semantic.conflicting-constants",
        source="dataflow",
        description="The same variable is assigned two different constant values on one path with a read in between.",
        name="Conflicting constants",
        example="ModuleCode\n   Setpoint = 10;\n   Current = Setpoint;   (* Setpoint read here ... *)\n   Setpoint = 20;       (* ... then reassigned to a conflicting constant *)",
    ),
    "dataflow.condition_always_true": SemanticRule(
        id="semantic.condition-always-true",
        source="dataflow",
        description="Conditions that always evaluate to true at a particular program point.",
        name="Condition always true",
        example="IF RawInput >= 0 OR RawInput < 0 THEN   (* covers every possible value *)\n   Output = 1;\nENDIF;",
    ),
    "dataflow.condition_always_false": SemanticRule(
        id="semantic.condition-always-false",
        source="dataflow",
        description="Conditions that always evaluate to false at a particular program point.",
        name="Condition always false",
        example="IF RawInput < RawInput THEN   (* value can never be less than itself *)\n   Output = 1;\nENDIF;",
    ),
    "dataflow.unreachable_branch": SemanticRule(
        id="semantic.unreachable-branch",
        source="dataflow",
        description="Branches that cannot execute because control-flow facts make them impossible.",
        name="Unreachable branch",
        example="IF Level > 100 AND Level < 50 THEN   (* impossible range *)\n   Output = 1;                         (* this branch can never run *)\nENDIF;",
    ),
    "dataflow.self_compare_condition": SemanticRule(
        id="semantic.self-compare-condition",
        source="dataflow",
        description="Conditions that compare a symbol to itself and collapse to a constant result.",
        name="Self-compare condition",
        example="IF RawInput == RawInput THEN   (* always true, pointless check *)\n   Output = 1;\nENDIF;",
    ),
    "dataflow.scan_cycle_stale_read": SemanticRule(
        id="semantic.scan-cycle-stale-read",
        source="dataflow",
        description=":OLD reads after a same-scan write where the expression still relies on the previous-scan snapshot.",
        name="Stale :OLD read",
        example="Counter = Counter + 1;   (* written this scan ... *)\nIF Counter:Old == 0 THEN   (* ... but :OLD reads the previous-scan value *)",
    ),
    "dataflow.scan_cycle_implicit_new": SemanticRule(
        id="semantic.scan-cycle-implicit-new",
        source="dataflow",
        description="Implicit same-scan reads of a state variable after a write should use :NEW when they rely on the updated value.",
        name="Implicit :NEW read",
        example="SEQUENCE MainSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0\n   SEQSTEP WriteStep\n      ENTERCODE\n         Level = 5;\n   SEQTRANSITION TrNext WAIT_FOR Level == 5  (* implicit read may see the old value *)",
    ),
    "dataflow.non_state_multi_site": SemanticRule(
        id="semantic.non-state-multi-site",
        source="dataflow",
        description="Non-STATE variables that are read and written across multiple continuous scan sites within the same scan.",
        name="Non-state multi-site access",
        example="ModuleCode\n   EQUATIONBLOCK A COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n      Temp = RawInput;     (* Temp read/written here ... *)\n   EQUATIONBLOCK B COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n      Temp = Temp + 1;     (* ... and again later in the same scan *)",
    ),
}

SPEC_RULE_DESCRIPTIONS: dict[str, str] = {
    "spec.sequence_step_prefix": "Sequence steps must use the required engineering-spec naming prefix.",
    "spec.transition_name_missing": "All transitions must be named.",
    "spec.transition_prefix": "Transitions must use the required engineering-spec naming prefix.",
    "spec.sequence_name_prefix": "Sequences must use the configured engineering-spec naming prefix.",
    "spec.equation_block_prefix": "Equation blocks must use the configured engineering-spec naming prefix.",
}

SPEC_RULE_NAMES: dict[str, str] = {
    "spec.sequence_step_prefix": "Wrong sequence step prefix",
    "spec.transition_name_missing": "Transition has no name",
    "spec.transition_prefix": "Wrong transition prefix",
    "spec.sequence_name_prefix": "Wrong sequence name prefix",
    "spec.equation_block_prefix": "Wrong equation block name prefix",
}

SPEC_RULE_EXAMPLES: dict[str, str] = {
    "spec.sequence_step_prefix": "SEQSTEP step_mix   (* should use the required step prefix *)",
    "spec.transition_name_missing": "SEQTRANSITION WAIT_FOR Done   (* transition has no name *)",
    "spec.transition_prefix": "SEQTRANSITION MyTrans WAIT_FOR Done   (* MyTrans does not use the required prefix *)",
    "spec.sequence_name_prefix": "SEQUENCE MixSeq (SeqControl, SeqTimer)   (* should use the configured sequence prefix *)",
    "spec.equation_block_prefix": "EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :   (* should use the configured equation prefix *)",
}

__all__ = [
    "DATAFLOW_RULES",
    "SPEC_RULE_DESCRIPTIONS",
    "SPEC_RULE_EXAMPLES",
    "SPEC_RULE_NAMES",
]
