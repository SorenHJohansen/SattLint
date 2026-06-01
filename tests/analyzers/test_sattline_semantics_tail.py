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
    SingleModule,
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


def test_sattline_semantics_includes_duplicate_transition_guard_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Permit", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Ready", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    SFCTransition(
                        name="OpenPrimary",
                        condition=(const.GRAMMAR_VALUE_AND, [_varref("Permit"), _varref("Ready")]),
                    ),
                    SFCTransition(
                        name="OpenBackup",
                        condition=(const.GRAMMAR_VALUE_AND, [_varref("Ready"), _varref("Permit")]),
                    ),
                )
            ]
        ),
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.duplicate-transition-guard" for issue in report.issues)


def test_sattline_semantics_includes_alarm_integrity_rules():
    detector = ModuleTypeDef(
        name="EventDetector1",
        moduleparameters=[
            Variable(name="Tag", datatype=Simple_DataType.TAGSTRING),
            Variable(name="Severity", datatype=Simple_DataType.INTEGER, init_value=2),
            Variable(name="Condition", datatype=Simple_DataType.BOOLEAN),
        ],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="CondA", datatype=Simple_DataType.BOOLEAN),
            Variable(name="CondB", datatype=Simple_DataType.BOOLEAN),
        ],
        moduletype_defs=[detector],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("AlarmA"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Unit.Temp.High",
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("CondA"),
                        source_literal=None,
                    ),
                ],
            ),
            ModuleTypeInstance(
                header=_hdr("AlarmB"),
                moduletype_name="EventDetector1",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Tag"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal="Unit.Temp.High",
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("CondB"),
                        source_literal=None,
                    ),
                ],
            ),
        ],
        origin_file="Root.s",
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.duplicate-alarm-tag" for issue in report.issues)


def test_sattline_semantics_includes_initial_value_rule():
    parameter_type = ModuleTypeDef(
        name="RecParReal",
        moduleparameters=[
            Variable(name="Value", datatype=Simple_DataType.REAL),
            Variable(name="MinValue", datatype=Simple_DataType.REAL, init_value=0.0),
            Variable(name="MaxValue", datatype=Simple_DataType.REAL, init_value=100.0),
        ],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[parameter_type],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("RecipeSP"),
                moduletype_name="RecParReal",
                parametermappings=[],
            )
        ],
        origin_file="Root.s",
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.missing-parameter-initial-value" for issue in report.issues)


def test_sattline_semantics_includes_hidden_global_coupling_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)],
        submodules=[
            SingleModule(
                header=_hdr("Writer"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="WriteShared",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("SharedValue"), 1)],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            ),
            SingleModule(
                header=_hdr("Reader"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="ReadShared",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.hidden-global-coupling" for issue in report.issues)


def test_sattline_semantics_includes_global_scope_minimization_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="ConfinedValue", datatype=Simple_DataType.INTEGER)],
        submodules=[
            SingleModule(
                header=_hdr("Worker"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="UseConfined",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[
                                (const.KEY_ASSIGN, _varref("ConfinedValue"), 1),
                                (const.KEY_ASSIGN, _varref("Observed"), _varref("ConfinedValue")),
                            ],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.global-scope-minimization" for issue in report.issues)


def test_sattline_semantics_includes_high_fan_in_out_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)],
        submodules=[
            SingleModule(
                header=_hdr("Writer"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="WriteShared",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("SharedValue"), 1)],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            ),
            SingleModule(
                header=_hdr("ReaderA"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="ReadSharedA",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            ),
            SingleModule(
                header=_hdr("ReaderB"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="ReadSharedB",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            ),
            SingleModule(
                header=_hdr("ReaderC"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="ReadSharedC",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("SharedValue"))],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.high-fan-in-out-variable" for issue in report.issues)


def test_sattline_semantics_includes_signal_lifecycle_rules():
    bp = BasePicture(
        header=_hdr("Program"),
        localvariables=[
            Variable(name="InputSignal", datatype=Simple_DataType.BOOLEAN),
            Variable(name="OutputSignal", datatype=Simple_DataType.BOOLEAN),
            Variable(name="ObservedSignal", datatype=Simple_DataType.BOOLEAN),
            Variable(name="NeverConsumed", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("OutputSignal"), _varref("InputSignal")),
                        (const.KEY_ASSIGN, _varref("InputSignal"), True),
                        (const.KEY_ASSIGN, _varref("ObservedSignal"), _varref("OutputSignal")),
                        (const.KEY_ASSIGN, _varref("NeverConsumed"), False),
                    ],
                )
            ]
        ),
    )

    report = analyze_sattline_semantics(bp)

    rule_ids = {issue.rule.id for issue in report.issues}
    assert "semantic.signal-lifecycle-read-before-write" in rule_ids
    assert "semantic.signal-lifecycle-unconsumed-write" in rule_ids


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
    assert "signal-lifecycle" in groups
    assert "loop-stability" in groups
    assert "fault-handling" in groups
    assert "numeric-constraints" in groups
    assert "config-drift" in groups
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
    assert "semantic.signal-lifecycle-read-before-write" in groups["signal-lifecycle"]
    assert "semantic.signal-lifecycle-unconsumed-write" in groups["signal-lifecycle"]
    assert "semantic.loop-conflicting-setpoint" in groups["loop-stability"]
    assert "semantic.fault-missing-recovery" in groups["fault-handling"]
    assert "semantic.fault-unhandled-path" in groups["fault-handling"]
    assert "semantic.numeric-limit-violation" in groups["numeric-constraints"]
    assert "semantic.instance-configuration-drift" in groups["config-drift"]

    all_rule_ids = [rule_id for rule_ids in groups.values() for rule_id in rule_ids]
    assert len(all_rule_ids) == len(set(all_rule_ids))
