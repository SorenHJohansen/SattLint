"""Tail rule coverage tests for the Sattline semantics analyzer."""

from __future__ import annotations

from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    SFCBreak,
    SFCCodeBlocks,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    Simple_DataType,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.sattline_semantics import analyze_sattline_semantics, get_sattline_semantic_rule_groups
from sattlint.tracing import detect_unreachable_sequence_logic
from tests.analyzers.test_sattline_semantics import _hdr, _sequence, _varref


def test_sattline_semantics_includes_loop_stability_rule():
    bp = BasePicture(
        header=_hdr("Program"),
        localvariables=[Variable(name="Setpoint", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Control",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Setpoint"), 10),
                        (const.KEY_ASSIGN, _varref("Setpoint"), 20),
                    ],
                )
            ]
        ),
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.loop-conflicting-setpoint" for issue in report.issues)


def test_sattline_semantics_includes_fault_handling_rules():
    bp = BasePicture(
        header=_hdr("Program"),
        localvariables=[
            Variable(name="HighFault", datatype=Simple_DataType.BOOLEAN),
            Variable(name="HandledFault", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Status", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("HighFault"), True),
                        (const.KEY_ASSIGN, _varref("HandledFault"), True),
                        (const.KEY_ASSIGN, _varref("Status"), _varref("HandledFault")),
                        (const.KEY_ASSIGN, _varref("HandledFault"), False),
                    ],
                )
            ]
        ),
    )

    report = analyze_sattline_semantics(bp)

    rule_ids = {issue.rule.id for issue in report.issues}
    assert "semantic.fault-missing-recovery" in rule_ids
    assert "semantic.fault-unhandled-path" in rule_ids


def test_sattline_semantics_includes_numeric_constraints_rule():
    bp = BasePicture(
        header=_hdr("Program"),
        localvariables=[
            Variable(name="Min_Output", datatype=Simple_DataType.INTEGER, init_value=0),
            Variable(name="Max_Output", datatype=Simple_DataType.INTEGER, init_value=10),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 12)],
                )
            ]
        ),
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.numeric-limit-violation" for issue in report.issues)


def test_sattline_semantics_includes_config_drift_rule():
    typedef = ModuleTypeDef(
        name="DoseValve",
        moduleparameters=[Variable(name="Timeout", datatype=Simple_DataType.INTEGER, init_value=10)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Program"),
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("ValveA"),
                moduletype_name="DoseValve",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Timeout"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source=None,
                        source_literal=10,
                    )
                ],
            ),
            ModuleTypeInstance(
                header=_hdr("ValveB"),
                moduletype_name="DoseValve",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Timeout"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source=None,
                        source_literal=15,
                    )
                ],
            ),
        ],
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.instance-configuration-drift" for issue in report.issues)


def test_detect_unreachable_sequence_logic_walks_nested_subsequence_bodies():
    bp = BasePicture(
        header=_hdr("Root"),
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    SFCSubsequence(
                        name="Nested",
                        body=[
                            SFCBreak(),
                            SFCStep(kind="step", name="AfterNestedBreak", code=SFCCodeBlocks()),
                        ],
                    )
                )
            ]
        ),
    )

    findings = detect_unreachable_sequence_logic(bp)

    assert len(findings) == 1
    assert findings[0]["kind"] == "unreachable_sequence_node"
    assert findings[0]["node_label"] == "SFCStep:AfterNestedBreak"


def test_detect_unreachable_sequence_logic_reports_nested_transition_reachability():
    bp = BasePicture(
        header=_hdr("Root"),
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    SFCSubsequence(
                        name="Nested",
                        body=[
                            SFCBreak(),
                            SFCTransition(name="NeverFires", condition=True),
                        ],
                    )
                )
            ]
        ),
    )

    findings = detect_unreachable_sequence_logic(bp)

    assert len(findings) == 1
    assert findings[0]["kind"] == "unreachable_sequence_node"
    assert findings[0]["node_type"] == "SFCTransition"
    assert findings[0]["node_label"] == "SFCTransition:NeverFires"


def test_sattline_semantics_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "sattline-semantics" in specs
    assert specs["sattline-semantics"].enabled is True


def test_sattline_semantic_rule_groups_cover_core_analyzers():
    groups = {group.source: {rule.id for rule in group.rules} for group in get_sattline_semantic_rule_groups()}

    assert "variables" in groups
    assert "dataflow" in groups
    assert "sfc" in groups
    assert "alarm-integrity" in groups
    assert "initial-values" in groups
    assert "signal_lifecycle" in groups
    assert "loop_stability" in groups
    assert "fault_handling" in groups
    assert "numeric_constraints" in groups
    assert "config_drift" in groups
    assert "semantic.unused-variable" in groups["variables"]
    assert "semantic.implicit-latch" in groups["variables"]
    assert "semantic.global-scope-minimization" in groups["variables"]
    assert "semantic.hidden-global-coupling" in groups["variables"]
    assert "semantic.read-before-write" in groups["dataflow"]
    assert "semantic.parallel-write-race" in groups["sfc"]
    assert "semantic.duplicate-transition-guard" in groups["sfc"]
    assert "semantic.missing-step-enter-contract" in groups["sfc"]
    assert "semantic.missing-step-exit-contract" in groups["sfc"]
    assert "semantic.step-state-leakage" in groups["sfc"]
    assert "semantic.high-fan-in-out-variable" in groups["variables"]
    assert "semantic.duplicate-alarm-tag" in groups["alarm-integrity"]
    assert "semantic.missing-parameter-initial-value" in groups["initial-values"]
    assert "semantic.signal-lifecycle-read-before-write" in groups["signal_lifecycle"]
    assert "semantic.signal-lifecycle-unconsumed-write" in groups["signal_lifecycle"]
    assert "semantic.loop-conflicting-setpoint" in groups["loop_stability"]
    assert "semantic.fault-missing-recovery" in groups["fault_handling"]
    assert "semantic.fault-unhandled-path" in groups["fault_handling"]
    assert "semantic.numeric-limit-violation" in groups["numeric_constraints"]
    assert "semantic.instance-configuration-drift" in groups["config_drift"]

    all_rule_ids = [rule_id for rule_ids in groups.values() for rule_id in rule_ids]
    assert len(all_rule_ids) == len(set(all_rule_ids))
