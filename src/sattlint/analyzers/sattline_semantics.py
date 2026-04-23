from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from sattlint.analyzers.initial_values import analyze_initial_values

from ..reporting.variables_report import IssueKind, VariableIssue
from ..tracing import (
    detect_transform_invariant_violations,
)
from .alarm_integrity import analyze_alarm_integrity
from .dataflow import analyze_dataflow
from .issue import Issue, format_report_header
from .safety_paths import analyze_safety_paths
from .sfc import analyze_sfc
from .shadowing import analyze_shadowing
from .spec_compliance import analyze_spec_compliance
from .taint_paths import analyze_taint_paths
from .unsafe_defaults import analyze_unsafe_defaults
from .variables import analyze_variables


@dataclass(frozen=True)
class SemanticRule:
    id: str
    source: str
    category: str
    severity: str
    applies_to: str
    description: str
    confidence: str = "likely"
    explanation: str | None = None
    suggestion: str | None = None
    acceptance_tests: tuple[str, ...] | None = None
    corpus_cases: tuple[str, ...] = ()
    mutation_applicability: str | None = None
    suppression_modes: tuple[str, ...] | None = None
    incremental_safe: bool | None = None


@dataclass(frozen=True)
class SemanticRuleContract:
    acceptance_tests: tuple[str, ...]
    mutation_applicability: str
    suppression_modes: tuple[str, ...]
    incremental_safe: bool


@dataclass(frozen=True)
class SemanticIssue:
    rule: SemanticRule
    message: str
    module_path: list[str] | None = None
    data: dict[str, Any] = field(default_factory=dict)
    source_kind: str | None = None


@dataclass(frozen=True)
class SemanticRuleGroup:
    source: str
    rules: tuple[SemanticRule, ...]


CATEGORY_ORDER: tuple[str, ...] = (
    "variable-lifecycle",
    "interface-contracts",
    "module-structure",
    "control-flow",
    "engineering-spec",
)

CATEGORY_LABELS = {
    "variable-lifecycle": "Variable lifecycle",
    "interface-contracts": "Interface contracts",
    "module-structure": "Module structure",
    "control-flow": "Control flow",
    "engineering-spec": "Engineering spec",
}


def _merge_acceptance_tests(*groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({path for group in groups for path in group}))


def _rule_contract_entries(
    contract: SemanticRuleContract,
    *rule_ids: str,
) -> dict[str, SemanticRuleContract]:
    return dict.fromkeys(rule_ids, contract)


def _attach_rule_contract(
    rule: SemanticRule,
    contract: SemanticRuleContract | None,
) -> SemanticRule:
    if contract is None:
        return rule
    return replace(
        rule,
        acceptance_tests=contract.acceptance_tests,
        mutation_applicability=contract.mutation_applicability,
        suppression_modes=contract.suppression_modes,
        incremental_safe=contract.incremental_safe,
    )


_SEMANTIC_LAYER_ACCEPTANCE_TESTS = (
    "tests/test_pipeline.py",
    "tests/test_sattline_semantics.py",
)
_VARIABLE_SOURCE_ACCEPTANCE_TESTS = (
    "tests/test_analyzers.py",
    "tests/test_app.py",
    "tests/test_editor_api.py",
    "tests/test_sattline_semantics.py",
)
_SFC_SOURCE_ACCEPTANCE_TESTS = (
    "tests/test_analyzers.py",
    "tests/test_sattline_semantics.py",
    "tests/test_sfc.py",
)
_ALARM_SOURCE_ACCEPTANCE_TESTS = (
    "tests/test_analyzers.py",
    "tests/test_sattline_semantics.py",
)
_INITIAL_VALUES_SOURCE_ACCEPTANCE_TESTS = ("tests/test_analyzers.py",)
_SAFETY_SOURCE_ACCEPTANCE_TESTS = (
    "tests/test_analyzers.py",
    "tests/test_editor_api.py",
    "tests/test_sattline_semantics.py",
)
_TAINT_SOURCE_ACCEPTANCE_TESTS = (
    "tests/test_analyzers.py",
    "tests/test_editor_api.py",
)
_DATAFLOW_SOURCE_ACCEPTANCE_TESTS = (
    "tests/test_analyzers.py",
    "tests/test_dataflow.py",
    "tests/test_sattline_semantics.py",
)
_UNSAFE_DEFAULTS_SOURCE_ACCEPTANCE_TESTS = (
    "tests/test_pipeline.py",
    "tests/test_sattline_semantics.py",
)
_SPEC_SOURCE_ACCEPTANCE_TESTS = (
    "tests/test_app.py",
    "tests/test_spec_compliance.py",
    "tests/test_sattline_semantics.py",
)

_VARIABLE_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _VARIABLE_SOURCE_ACCEPTANCE_TESTS,
    ),
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=True,
)
_SHADOWING_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        ("tests/test_analyzers.py", "tests/test_app.py"),
    ),
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
_SFC_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _SFC_SOURCE_ACCEPTANCE_TESTS,
    ),
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
_ALARM_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _ALARM_SOURCE_ACCEPTANCE_TESTS,
    ),
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
_INITIAL_VALUES_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _INITIAL_VALUES_SOURCE_ACCEPTANCE_TESTS,
    ),
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
_SAFETY_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _SAFETY_SOURCE_ACCEPTANCE_TESTS,
    ),
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
_TAINT_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _TAINT_SOURCE_ACCEPTANCE_TESTS,
    ),
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
_TRACE_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_SEMANTIC_LAYER_ACCEPTANCE_TESTS,
    mutation_applicability="not_applicable",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
_DATAFLOW_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _DATAFLOW_SOURCE_ACCEPTANCE_TESTS,
    ),
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
_UNSAFE_DEFAULTS_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _UNSAFE_DEFAULTS_SOURCE_ACCEPTANCE_TESTS,
    ),
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
_SPEC_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _SPEC_SOURCE_ACCEPTANCE_TESTS,
    ),
    mutation_applicability="optional",
    suppression_modes=("baseline",),
    incremental_safe=False,
)

_VARIABLE_RULES: dict[IssueKind, SemanticRule] = {
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

_SFC_RULES: dict[str, SemanticRule] = {
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

_ALARM_RULES: dict[str, SemanticRule] = {
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

_INITIAL_VALUE_RULES: dict[str, SemanticRule] = {
    "initial-values.missing_required_default": SemanticRule(
        id="semantic.missing-parameter-initial-value",
        source="initial-values",
        category="interface-contracts",
        severity="warning",
        applies_to="parameter-module",
        description="Recipe and engineering parameter modules should resolve a startup value through a default or an explicitly initialized mapping.",
    ),
}

_SAFETY_PATH_RULES: dict[str, SemanticRule] = {
    "safety-path.unconsumed_signal": SemanticRule(
        id="semantic.unconsumed-safety-signal",
        source="safety-paths",
        category="control-flow",
        severity="warning",
        applies_to="signal",
        description="Safety-critical signals that are written but never consumed across the analyzed target.",
    ),
}

_TRACE_RULES: dict[str, SemanticRule] = {
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

_DATAFLOW_RULES: dict[str, SemanticRule] = {
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
        description="Reads of :OLD after a same-scan write where the expression still relies on the previous-scan snapshot.",
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

_TAINT_RULES: dict[str, SemanticRule] = {
    "taint-path.external_input_to_critical_sink": SemanticRule(
        id="semantic.external-input-to-critical-sink",
        source="taint-paths",
        category="interface-contracts",
        severity="warning",
        applies_to="flow-path",
        description="External MES, operator, or sensor inputs that propagate into safety-critical sinks across modules.",
    ),
}

_UNSAFE_DEFAULT_RULES: dict[str, SemanticRule] = {
    "unsafe_defaults.true_boolean_default": SemanticRule(
        id="semantic.unsafe-default-true",
        source="unsafe-defaults",
        category="engineering-spec",
        severity="warning",
        applies_to="variable",
        description="Boolean defaults that enable logic or bypass safeguards from startup.",
    ),
}

_SPEC_RULE_DESCRIPTIONS = {
    "spec.basepicture_direct_code": "BasePicture code must stay inside frame modules.",
    "spec.sequence_step_prefix": "Sequence steps must use the required engineering-spec naming prefix.",
    "spec.transition_name_missing": "All transitions must be named.",
    "spec.transition_prefix": "Transitions must use the required engineering-spec naming prefix.",
    "spec.opmessage_use_signature": "OPMessage instances must not enable UseSignature=True.",
    "spec.mes_batch_control_name": "MES_BatchControl instances must use the required instance name.",
    "spec.mes_batch_control_max_try": "MES_BatchControl Max_TRY must resolve to the required value.",
    "spec.mes_batch_control_repeat_try": "MES_BatchControl Repeat_TRY must resolve to the required value.",
}

_RULE_CONTRACTS_BY_ID: dict[str, SemanticRuleContract] = {
    **_rule_contract_entries(
        _VARIABLE_RULE_CONTRACT,
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
        "semantic.min-max-mapping-mismatch",
        "semantic.reset-contamination",
        "semantic.implicit-latch",
    ),
    **_rule_contract_entries(_SHADOWING_RULE_CONTRACT, "semantic.shadowing"),
    **_rule_contract_entries(
        _SFC_RULE_CONTRACT,
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
    **_rule_contract_entries(
        _ALARM_RULE_CONTRACT,
        "semantic.duplicate-alarm-tag",
        "semantic.duplicate-alarm-condition",
        "semantic.conflicting-alarm-priority",
        "semantic.never-cleared-alarm",
    ),
    **_rule_contract_entries(
        _INITIAL_VALUES_RULE_CONTRACT,
        "semantic.missing-parameter-initial-value",
    ),
    **_rule_contract_entries(
        _SAFETY_RULE_CONTRACT,
        "semantic.unconsumed-safety-signal",
    ),
    **_rule_contract_entries(
        _TAINT_RULE_CONTRACT,
        "semantic.external-input-to-critical-sink",
    ),
    **_rule_contract_entries(
        _TRACE_RULE_CONTRACT,
        "semantic.duplicate-sibling-name",
        "semantic.unexpected-submodule-type",
    ),
    **_rule_contract_entries(
        _DATAFLOW_RULE_CONTRACT,
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
    **_rule_contract_entries(
        _UNSAFE_DEFAULTS_RULE_CONTRACT,
        "semantic.unsafe-default-true",
    ),
    **_rule_contract_entries(_SPEC_RULE_CONTRACT, *_SPEC_RULE_DESCRIPTIONS.keys()),
}

_VARIABLE_RULES = {
    kind: _attach_rule_contract(rule, _RULE_CONTRACTS_BY_ID.get(rule.id)) for kind, rule in _VARIABLE_RULES.items()
}
_SFC_RULES = {
    kind: _attach_rule_contract(rule, _RULE_CONTRACTS_BY_ID.get(rule.id)) for kind, rule in _SFC_RULES.items()
}
_ALARM_RULES = {
    kind: _attach_rule_contract(rule, _RULE_CONTRACTS_BY_ID.get(rule.id)) for kind, rule in _ALARM_RULES.items()
}
_INITIAL_VALUE_RULES = {
    kind: _attach_rule_contract(rule, _RULE_CONTRACTS_BY_ID.get(rule.id)) for kind, rule in _INITIAL_VALUE_RULES.items()
}
_SAFETY_PATH_RULES = {
    kind: _attach_rule_contract(rule, _RULE_CONTRACTS_BY_ID.get(rule.id)) for kind, rule in _SAFETY_PATH_RULES.items()
}
_TRACE_RULES = {
    kind: _attach_rule_contract(rule, _RULE_CONTRACTS_BY_ID.get(rule.id)) for kind, rule in _TRACE_RULES.items()
}
_DATAFLOW_RULES = {
    kind: _attach_rule_contract(rule, _RULE_CONTRACTS_BY_ID.get(rule.id)) for kind, rule in _DATAFLOW_RULES.items()
}
_TAINT_RULES = {
    kind: _attach_rule_contract(rule, _RULE_CONTRACTS_BY_ID.get(rule.id)) for kind, rule in _TAINT_RULES.items()
}
_UNSAFE_DEFAULT_RULES = {
    kind: _attach_rule_contract(rule, _RULE_CONTRACTS_BY_ID.get(rule.id))
    for kind, rule in _UNSAFE_DEFAULT_RULES.items()
}
_SPEC_FRAMEWORK_RULES = {
    rule_id: _attach_rule_contract(
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
        _RULE_CONTRACTS_BY_ID.get(rule_id),
    )
    for rule_id, description in sorted(_SPEC_RULE_DESCRIPTIONS.items())
}
_FRAMEWORK_RULES_BY_KIND: dict[str, SemanticRule] = {
    **_SFC_RULES,
    **_ALARM_RULES,
    **_INITIAL_VALUE_RULES,
    **_SAFETY_PATH_RULES,
    **_TAINT_RULES,
    **_DATAFLOW_RULES,
    **_UNSAFE_DEFAULT_RULES,
    **_SPEC_FRAMEWORK_RULES,
}


def get_sattline_semantic_rule_groups() -> tuple[SemanticRuleGroup, ...]:
    spec_rules = tuple(_SPEC_FRAMEWORK_RULES.values())

    return (
        SemanticRuleGroup(source="variables", rules=tuple(_VARIABLE_RULES.values())),
        SemanticRuleGroup(source="sfc", rules=tuple(_SFC_RULES.values())),
        SemanticRuleGroup(source="alarm-integrity", rules=tuple(_ALARM_RULES.values())),
        SemanticRuleGroup(source="initial-values", rules=tuple(_INITIAL_VALUE_RULES.values())),
        SemanticRuleGroup(source="safety-paths", rules=tuple(_SAFETY_PATH_RULES.values())),
        SemanticRuleGroup(source="taint-paths", rules=tuple(_TAINT_RULES.values())),
        SemanticRuleGroup(source="tracing", rules=tuple(_TRACE_RULES.values())),
        SemanticRuleGroup(source="dataflow", rules=tuple(_DATAFLOW_RULES.values())),
        SemanticRuleGroup(source="unsafe-defaults", rules=tuple(_UNSAFE_DEFAULT_RULES.values())),
        SemanticRuleGroup(source="spec-compliance", rules=spec_rules),
    )


def get_sattline_semantic_rules() -> tuple[SemanticRule, ...]:
    return tuple(rule for group in get_sattline_semantic_rule_groups() for rule in group.rules)


def get_rule_for_framework_issue_kind(issue_kind: str) -> SemanticRule | None:
    return _FRAMEWORK_RULES_BY_KIND.get(issue_kind)


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
    base_picture,
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
    )

    issues.extend(_map_variable_issues(variable_report.issues))
    issues.extend(_map_variable_issues(shadowing_report.issues))
    issues.extend(_map_framework_issues(sfc_report.issues, _SFC_RULES))
    issues.extend(_map_framework_issues(alarm_report.issues, _ALARM_RULES))
    issues.extend(_map_framework_issues(initial_value_report.issues, _INITIAL_VALUE_RULES))
    issues.extend(_map_framework_issues(safety_path_report.issues, _SAFETY_PATH_RULES))
    issues.extend(_map_framework_issues(taint_path_report.issues, _TAINT_RULES))
    issues.extend(_map_framework_issues(dataflow_report.issues, _DATAFLOW_RULES))
    issues.extend(_map_framework_issues(unsafe_defaults_report.issues, _UNSAFE_DEFAULT_RULES))
    issues.extend(_map_trace_findings(detect_transform_invariant_violations(base_picture)))
    issues.extend(_map_spec_issues(spec_report.issues))

    return SattLineSemanticsReport(
        basepicture_name=base_picture.header.name,
        issues=issues,
    )


def _map_variable_issues(issues: list[VariableIssue]) -> list[SemanticIssue]:
    semantic_issues: list[SemanticIssue] = []
    for issue in issues:
        rule = _VARIABLE_RULES.get(issue.kind)
        if rule is None:
            continue
        semantic_issues.append(
            SemanticIssue(
                rule=rule,
                message=_describe_variable_issue(issue),
                module_path=issue.module_path,
                data=_variable_issue_data(issue),
                source_kind=issue.kind.value,
            )
        )
    return semantic_issues


def _describe_variable_issue(issue: VariableIssue) -> str:
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
    if issue.kind is IssueKind.MIN_MAX_MAPPING_MISMATCH:
        return issue.role or "Min_/Max_ parameter mappings do not align by base name."
    if issue.kind is IssueKind.SHADOWING:
        return issue.role or "Local declaration shadows an outer scope name."
    if issue.kind is IssueKind.RESET_CONTAMINATION:
        return issue.role or "Reset-state writes are incomplete across the sequence flow."
    if issue.kind is IssueKind.IMPLICIT_LATCH:
        return issue.role or "Boolean value may latch without a matching False write on complementary paths."
    return issue.role or str(issue)


def _variable_issue_data(issue: VariableIssue) -> dict[str, Any]:
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


def _map_framework_issues(
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


def _map_trace_findings(findings: list[dict[str, Any]]) -> list[SemanticIssue]:
    semantic_issues: list[SemanticIssue] = []
    for finding in findings:
        kind = str(finding.get("kind", ""))
        rule = _TRACE_RULES.get(kind)
        if rule is None:
            continue
        semantic_issues.append(
            SemanticIssue(
                rule=rule,
                message=_describe_trace_finding(finding),
                module_path=finding.get("module_path"),
                data=finding,
                source_kind=kind,
            )
        )
    return semantic_issues


def _describe_trace_finding(finding: dict[str, Any]) -> str:
    kind = finding.get("kind")
    if kind == "duplicate_sibling_name":
        return f"Sibling module name {finding.get('module_name')!r} is declared more than once."
    if kind == "unexpected_submodule_type":
        return f"Unexpected submodule node {finding.get('node_label')!r} appeared in the module tree."
    if kind == "unreachable_sequence_node":
        terminated_by = finding.get("terminated_by") or {}
        terminator = terminated_by.get("kind", "an earlier terminating node")
        if terminated_by.get("target"):
            terminator = f"{terminator} targeting {terminated_by['target']!r}"
        node_label = finding.get("node_label", "<unknown node>")
        sequence_name = finding.get("sequence_name", "<unnamed>")
        return f"Sequence {sequence_name!r} contains unreachable node {node_label!r} after {terminator}."
    return kind or "Unknown trace finding."


def _map_spec_issues(issues: list[Issue]) -> list[SemanticIssue]:
    semantic_issues: list[SemanticIssue] = []
    for issue in issues:
        semantic_issues.append(
            SemanticIssue(
                rule=_attach_rule_contract(
                    SemanticRule(
                        id=issue.kind,
                        source="spec-compliance",
                        category="engineering-spec",
                        severity="warning",
                        applies_to="sattline-construct",
                        description=_SPEC_RULE_DESCRIPTIONS.get(issue.kind, issue.kind),
                    ),
                    _RULE_CONTRACTS_BY_ID.get(issue.kind),
                ),
                message=issue.message,
                module_path=issue.module_path,
                data=issue.data or {},
                source_kind=issue.kind,
            )
        )
    return semantic_issues
