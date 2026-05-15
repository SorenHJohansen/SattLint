from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticRuleContract:
    acceptance_tests: tuple[str, ...]
    corpus_cases: tuple[str, ...]
    mutation_applicability: str
    suppression_modes: tuple[str, ...]
    incremental_safe: bool


def _merge_acceptance_tests(*groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({path for group in groups for path in group}))


_SEMANTIC_LAYER_ACCEPTANCE_TESTS = ("tests/test_pipeline.py", "tests/analyzers/test_sattline_semantics.py")
_VARIABLE_SOURCE_ACCEPTANCE_TESTS = (
    "tests/test_analyzers.py",
    "tests/test_app.py",
    "tests/test_editor_api.py",
    "tests/analyzers/test_sattline_semantics.py",
)
_SFC_SOURCE_ACCEPTANCE_TESTS = (
    "tests/test_analyzers.py",
    "tests/analyzers/test_sattline_semantics.py",
    "tests/analyzers/test_sfc.py",
)
_ALARM_SOURCE_ACCEPTANCE_TESTS = ("tests/test_analyzers.py", "tests/analyzers/test_sattline_semantics.py")
_INITIAL_VALUES_SOURCE_ACCEPTANCE_TESTS = ("tests/test_analyzers.py",)
_SAFETY_SOURCE_ACCEPTANCE_TESTS = (
    "tests/test_analyzers.py",
    "tests/test_editor_api.py",
    "tests/analyzers/test_sattline_semantics.py",
)
_TAINT_SOURCE_ACCEPTANCE_TESTS = (
    "tests/test_analyzers.py",
    "tests/test_editor_api.py",
)
_DATAFLOW_SOURCE_ACCEPTANCE_TESTS = (
    "tests/test_analyzers.py",
    "tests/analyzers/test_dataflow.py",
    "tests/analyzers/test_sattline_semantics.py",
)
_SIGNAL_LIFECYCLE_SOURCE_ACCEPTANCE_TESTS = (
    "tests/analyzers/test_signal_lifecycle.py",
    "tests/analyzers/test_sattline_semantics.py",
)
_LOOP_STABILITY_SOURCE_ACCEPTANCE_TESTS = (
    "tests/analyzers/test_loop_stability.py",
    "tests/analyzers/test_sattline_semantics.py",
)
_FAULT_HANDLING_SOURCE_ACCEPTANCE_TESTS = (
    "tests/analyzers/test_fault_handling.py",
    "tests/analyzers/test_sattline_semantics.py",
)
_NUMERIC_CONSTRAINTS_SOURCE_ACCEPTANCE_TESTS = (
    "tests/analyzers/test_numeric_constraints.py",
    "tests/analyzers/test_sattline_semantics.py",
)
_CONFIG_DRIFT_SOURCE_ACCEPTANCE_TESTS = (
    "tests/analyzers/test_config_drift.py",
    "tests/analyzers/test_sattline_semantics.py",
)
_UNSAFE_DEFAULTS_SOURCE_ACCEPTANCE_TESTS = ("tests/test_pipeline.py", "tests/analyzers/test_sattline_semantics.py")
_SPEC_SOURCE_ACCEPTANCE_TESTS = (
    "tests/test_app.py",
    "tests/analyzers/test_spec_compliance.py",
    "tests/analyzers/test_sattline_semantics.py",
)
_WORKSPACE_CORPUS_CASES = ("workspace-common-quality-issues",)

VARIABLE_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _VARIABLE_SOURCE_ACCEPTANCE_TESTS,
    ),
    corpus_cases=_WORKSPACE_CORPUS_CASES,
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=True,
)
SHADOWING_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        ("tests/test_analyzers.py", "tests/test_app.py"),
    ),
    corpus_cases=_WORKSPACE_CORPUS_CASES,
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
SFC_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _SFC_SOURCE_ACCEPTANCE_TESTS,
    ),
    corpus_cases=_WORKSPACE_CORPUS_CASES,
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
ALARM_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _ALARM_SOURCE_ACCEPTANCE_TESTS,
    ),
    corpus_cases=_WORKSPACE_CORPUS_CASES,
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
INITIAL_VALUES_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _INITIAL_VALUES_SOURCE_ACCEPTANCE_TESTS,
    ),
    corpus_cases=_WORKSPACE_CORPUS_CASES,
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
SAFETY_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _SAFETY_SOURCE_ACCEPTANCE_TESTS,
    ),
    corpus_cases=_WORKSPACE_CORPUS_CASES,
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
TAINT_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _TAINT_SOURCE_ACCEPTANCE_TESTS,
    ),
    corpus_cases=_WORKSPACE_CORPUS_CASES,
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
TRACE_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_SEMANTIC_LAYER_ACCEPTANCE_TESTS,
    corpus_cases=(),
    mutation_applicability="not_applicable",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
DATAFLOW_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _DATAFLOW_SOURCE_ACCEPTANCE_TESTS,
    ),
    corpus_cases=_WORKSPACE_CORPUS_CASES,
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
SIGNAL_LIFECYCLE_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _SIGNAL_LIFECYCLE_SOURCE_ACCEPTANCE_TESTS,
    ),
    corpus_cases=(),
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
LOOP_STABILITY_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _LOOP_STABILITY_SOURCE_ACCEPTANCE_TESTS,
    ),
    corpus_cases=(),
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
FAULT_HANDLING_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _FAULT_HANDLING_SOURCE_ACCEPTANCE_TESTS,
    ),
    corpus_cases=(),
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
NUMERIC_CONSTRAINTS_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _NUMERIC_CONSTRAINTS_SOURCE_ACCEPTANCE_TESTS,
    ),
    corpus_cases=(),
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
CONFIG_DRIFT_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _CONFIG_DRIFT_SOURCE_ACCEPTANCE_TESTS,
    ),
    corpus_cases=(),
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
UNSAFE_DEFAULTS_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _UNSAFE_DEFAULTS_SOURCE_ACCEPTANCE_TESTS,
    ),
    corpus_cases=_WORKSPACE_CORPUS_CASES,
    mutation_applicability="required",
    suppression_modes=("baseline",),
    incremental_safe=False,
)
SPEC_RULE_CONTRACT = SemanticRuleContract(
    acceptance_tests=_merge_acceptance_tests(
        _SEMANTIC_LAYER_ACCEPTANCE_TESTS,
        _SPEC_SOURCE_ACCEPTANCE_TESTS,
    ),
    corpus_cases=_WORKSPACE_CORPUS_CASES,
    mutation_applicability="optional",
    suppression_modes=("baseline",),
    incremental_safe=False,
)


__all__ = [
    "ALARM_RULE_CONTRACT",
    "CONFIG_DRIFT_RULE_CONTRACT",
    "DATAFLOW_RULE_CONTRACT",
    "FAULT_HANDLING_RULE_CONTRACT",
    "INITIAL_VALUES_RULE_CONTRACT",
    "LOOP_STABILITY_RULE_CONTRACT",
    "NUMERIC_CONSTRAINTS_RULE_CONTRACT",
    "SAFETY_RULE_CONTRACT",
    "SFC_RULE_CONTRACT",
    "SHADOWING_RULE_CONTRACT",
    "SIGNAL_LIFECYCLE_RULE_CONTRACT",
    "SPEC_RULE_CONTRACT",
    "TAINT_RULE_CONTRACT",
    "TRACE_RULE_CONTRACT",
    "UNSAFE_DEFAULTS_RULE_CONTRACT",
    "VARIABLE_RULE_CONTRACT",
    "SemanticRuleContract",
]
