from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattlint import constants as const
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.sattline_semantics import (
    analyze_sattline_semantics,
    get_sattline_semantic_rule_groups,
)
from sattlint.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCBreak,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint.tracing import detect_unreachable_sequence_logic


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def _sequence(*nodes: object) -> Sequence:
    return Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=list(nodes),
    )


def test_sattline_semantics_aggregates_domain_checks():
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="DeclaredValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="SourceValue", datatype=Simple_DataType.INTEGER)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Child"),
                moduletype_name="ChildType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("MissingValue"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("SourceValue"),
                        source_literal=None,
                    )
                ],
            )
        ],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="UnusedFlag", datatype=Simple_DataType.BOOLEAN)],
        moduletype_defs=[typedef],
        submodules=[parent],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    SFCBreak(),
                    SFCStep(kind="step", name="AfterBreak", code=SFCCodeBlocks()),
                )
            ]
        ),
    )

    report = analyze_sattline_semantics(bp)

    rule_ids = {issue.rule.id for issue in report.issues}
    assert "semantic.unused-variable" in rule_ids
    assert "semantic.unknown-parameter-target" in rule_ids
    assert "semantic.unreachable-sequence-node" in rule_ids
    assert "spec.basepicture_direct_code" in rule_ids

    summary = report.summary()
    assert "Variable lifecycle" in summary
    assert "Interface contracts" in summary
    assert "Control flow" in summary
    assert "Engineering spec" in summary


def test_sattline_semantics_includes_read_before_write_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Input", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Output"),
                            _varref("Input"),
                        )
                    ],
                )
            ],
        ),
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.read-before-write" for issue in report.issues)


def test_sattline_semantics_includes_cross_module_contract_mismatch_rule():
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="ExpectedValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="SourceFlag", datatype=Simple_DataType.BOOLEAN)],
        moduletype_defs=[typedef],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Child"),
                moduletype_name="ChildType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("ExpectedValue"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("SourceFlag"),
                        source_literal=None,
                    )
                ],
            )
        ],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.cross-module-contract-mismatch" for issue in report.issues)


def test_sattline_semantics_includes_dead_overwrite_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Flag", datatype=Simple_DataType.BOOLEAN)],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Flag"),
                            True,
                        ),
                        (
                            const.KEY_ASSIGN,
                            _varref("Flag"),
                            False,
                        ),
                    ],
                )
            ],
        ),
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.dead-overwrite" for issue in report.issues)


def test_sattline_semantics_includes_scan_cycle_implicit_new_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Flag", datatype=Simple_DataType.BOOLEAN, state=True),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, {const.KEY_VAR_NAME: "Flag", "state": "new"}, True),
                        (const.KEY_ASSIGN, _varref("Output"), _varref("Flag")),
                    ],
                )
            ],
        ),
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.scan-cycle-implicit-new" for issue in report.issues)


def test_sattline_semantics_includes_scan_cycle_temporal_misuse_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Flag", datatype=Simple_DataType.BOOLEAN, state=True)],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "MaxLim",
                            [1.0, 2.0, 0.1, {const.KEY_VAR_NAME: "Flag", "state": "old"}],
                        )
                    ],
                )
            ],
        ),
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.scan-cycle-temporal-misuse" for issue in report.issues)


def test_sattline_semantics_includes_parallel_write_race_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[
            DataType(
                name="RecType",
                description=None,
                datecode=None,
                var_list=[Variable(name="Field", datatype=Simple_DataType.INTEGER)],
            )
        ],
        localvariables=[Variable(name="Rec", datatype="RecType")],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    SFCParallel(
                        branches=[
                            [
                                SFCStep(
                                    kind="step",
                                    name="Left",
                                    code=SFCCodeBlocks(
                                        active=[
                                            (
                                                const.KEY_ASSIGN,
                                                _varref("Rec"),
                                                1,
                                            )
                                        ]
                                    ),
                                )
                            ],
                            [
                                SFCStep(
                                    kind="step",
                                    name="Right",
                                    code=SFCCodeBlocks(
                                        active=[
                                            (
                                                const.KEY_ASSIGN,
                                                _varref("Rec.Field"),
                                                2,
                                            )
                                        ]
                                    ),
                                )
                            ],
                        ]
                    )
                )
            ],
            equations=[],
        ),
        moduledef=None,
    )

    report = analyze_sattline_semantics(bp)

    issues = [issue for issue in report.issues if issue.rule.id == "semantic.parallel-write-race"]
    assert len(issues) == 1
    assert issues[0].data["conflicts"] == ["Root.Rec"]


def test_sattline_semantics_includes_step_state_leakage_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="StepValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    SFCStep(
                        kind="step",
                        name="Prime",
                        code=SFCCodeBlocks(
                            active=[
                                (
                                    const.KEY_ASSIGN,
                                    _varref("StepValue"),
                                    1,
                                )
                            ]
                        ),
                    ),
                    SFCStep(
                        kind="step",
                        name="Run",
                        code=SFCCodeBlocks(
                            enter=[],
                            active=[
                                (
                                    const.KEY_ASSIGN,
                                    _varref("Output"),
                                    _varref("StepValue"),
                                )
                            ],
                            exit=[],
                        ),
                    ),
                )
            ],
            equations=[],
        ),
    )

    report = analyze_sattline_semantics(
        bp,
        sfc_step_contracts={
            "Run": {"required_enter_writes": ["StepValue"]},
        },
    )

    issues = [issue for issue in report.issues if issue.rule.id == "semantic.step-state-leakage"]
    assert len(issues) == 1
    assert issues[0].data["leaked_state"] == ["StepValue"]


def test_sattline_semantics_includes_implicit_latch_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="AlarmLatched", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [
                                (
                                    _varref("Start"),
                                    [
                                        (
                                            const.KEY_ASSIGN,
                                            _varref("AlarmLatched"),
                                            True,
                                        )
                                    ],
                                )
                            ],
                            [],
                        )
                    ],
                )
            ]
        ),
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.implicit-latch" for issue in report.issues)


def test_sattline_semantics_includes_write_without_effect_rule():
    child = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Stage1", datatype=Simple_DataType.INTEGER),
            Variable(name="Stage2", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Stage1"), 1),
                        (const.KEY_ASSIGN, _varref("Stage2"), _varref("Stage1")),
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.write-without-effect" for issue in report.issues)


def test_sattline_semantics_includes_external_input_to_critical_sink_rule():
    guard = SingleModule(
        header=_hdr("Guard"),
        moduledef=None,
        moduleparameters=[
            Variable(name="InCommand", datatype=Simple_DataType.BOOLEAN),
        ],
        localvariables=[
            Variable(name="ShutdownTrip", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="GuardEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("ShutdownTrip"), _varref("InCommand")),
                    ],
                )
            ]
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("InCommand"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("OperatorCommand"),
                source_literal=None,
            )
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="OperatorCommand", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        submodules=[guard],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("OperatorCommand"), True)],
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.external-input-to-critical-sink" for issue in report.issues)


def test_sattline_semantics_includes_ui_only_variable_rule():
    bp = parser_core_parse_source_text(
        """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    DisplayValue: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    GraphObjects :
        TextObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            "Value" VarName Width_ = 5 : InVar_ "DisplayValue"
ENDDEF (*BasePicture*);
"""
    )
    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.ui-only-variable" for issue in report.issues)


def test_sattline_semantics_includes_unreachable_transition_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    SFCBreak(),
                    SFCTransition(name="NeverFires", condition=True),
                )
            ]
        ),
    )

    report = analyze_sattline_semantics(bp)

    assert any(
        issue.rule.id == "semantic.unreachable-transition"
        and issue.data.get("node_label") == "SFCTransition:NeverFires"
        for issue in report.issues
    )

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

    all_rule_ids = [rule_id for rule_ids in groups.values() for rule_id in rule_ids]
    assert len(all_rule_ids) == len(set(all_rule_ids))


# ---------------------------------------------------------------------------
# ID15: Regression lock-in tests for recently added rules
# ---------------------------------------------------------------------------


def test_sattline_semantics_includes_unsafe_default_true_rule():
    """Lock-in: boolean variable with init_value=True triggers semantic.unsafe-default-true."""
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="EnableBypass", datatype=Simple_DataType.BOOLEAN, init_value=True),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("EnableBypass"), False),
                    ],
                )
            ],
        ),
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.unsafe-default-true" for issue in report.issues)


def test_sattline_semantics_includes_scan_cycle_stale_read_rule():
    """Lock-in: reading :OLD after a same-scan :NEW write triggers semantic.scan-cycle-stale-read."""
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER, state=True),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        # Write :NEW
                        (const.KEY_ASSIGN, {const.KEY_VAR_NAME: "Counter", "state": "new"}, 1),
                        # Read :OLD after same-scan :NEW write — stale read
                        (
                            const.KEY_ASSIGN,
                            _varref("Output"),
                            {const.KEY_VAR_NAME: "Counter", "state": "old"},
                        ),
                    ],
                )
            ],
        ),
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.scan-cycle-stale-read" for issue in report.issues)


def test_sattline_semantics_rule_ids_are_stable():
    """Lock-in: all rule IDs known at test-write time remain registered.

    Detects accidental removal of a rule from the semantic rule registry.
    """
    from sattlint.analyzers.sattline_semantics import get_sattline_semantic_rules

    registered_ids = {rule.id for rule in get_sattline_semantic_rules()}

    expected_rule_ids = {
        # Variable lifecycle
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
        "semantic.shadowing",
        "semantic.reset-contamination",
        "semantic.implicit-latch",
        # SFC / control-flow
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
        # Alarm
        "semantic.duplicate-alarm-tag",
        "semantic.duplicate-alarm-condition",
        "semantic.conflicting-alarm-priority",
        "semantic.never-cleared-alarm",
        # Initial values
        "semantic.missing-parameter-initial-value",
        # Safety / taint
        "semantic.unconsumed-safety-signal",
        "semantic.external-input-to-critical-sink",
        # Tracing
        "semantic.duplicate-sibling-name",
        "semantic.unexpected-submodule-type",
        # Dataflow
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
        # Unsafe defaults
        "semantic.unsafe-default-true",
    }

    missing = expected_rule_ids - registered_ids
    assert not missing, f"Rules removed from registry: {sorted(missing)}"
