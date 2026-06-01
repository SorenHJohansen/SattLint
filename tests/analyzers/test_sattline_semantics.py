from types import SimpleNamespace

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.models.ast_model import (
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
    SFCTransition,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers import registry as registry_module
from sattlint.analyzers.framework import AnalysisContext, AnalysisSharedArtifacts, AnalyzerSpec
from sattlint.analyzers.sattline_semantics import (
    analyze_sattline_semantics,
)
from sattlint.reporting.variables_report import IssueKind, VariableIssue


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


def test_sattline_semantics_includes_invalid_state_access_rule():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[
            DataType(
                name="RegressionType",
                description=None,
                datecode=None,
                var_list=[Variable(name="Running", datatype=Simple_DataType.BOOLEAN)],
            ),
            DataType(
                name="SelfType",
                description=None,
                datecode=None,
                var_list=[Variable(name="Regression", datatype="RegressionType")],
            ),
        ],
        localvariables=[
            Variable(name="Self", datatype="SelfType"),
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
                            {const.KEY_VAR_NAME: "Self.Regression.Running", "state": "old"},
                        )
                    ],
                )
            ],
        ),
    )

    report = analyze_sattline_semantics(bp)

    assert any(issue.rule.id == "semantic.invalid-state-access" for issue in report.issues)


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


def test_sattline_semantics_reuses_precomputed_reports(monkeypatch):
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="UnusedFlag", datatype=Simple_DataType.BOOLEAN)],
        submodules=[],
    )
    shared_artifacts = AnalysisSharedArtifacts()
    shared_artifacts.reports_by_analyzer_key["variables"] = SimpleNamespace(
        issues=[
            VariableIssue(
                kind=IssueKind.UNUSED,
                module_path=["Root"],
                variable=Variable(name="UnusedFlag", datatype=Simple_DataType.BOOLEAN),
            )
        ]
    )
    context = AnalysisContext(base_picture=bp, shared_artifacts=shared_artifacts)

    monkeypatch.setattr(
        registry_module,
        "get_default_analyzer_catalog",
        lambda: SimpleNamespace(
            analyzers=(
                SimpleNamespace(
                    spec=AnalyzerSpec(
                        key="variables",
                        name="Variable issues",
                        description="",
                        run=lambda _context: SimpleNamespace(issues=[]),
                        analyzer_attr="analyze_variables",
                        semantic_mapping_kind="variable",
                    )
                ),
            )
        ),
    )
    monkeypatch.setattr(
        registry_module,
        "analyze_variables",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should reuse precomputed report")),
    )

    report = analyze_sattline_semantics(bp, analysis_context=context)

    assert any(issue.rule.id == "semantic.unused-variable" for issue in report.issues)
    assert shared_artifacts.counters.semantic_precomputed_reports_used == 1
    assert shared_artifacts.counters.semantic_analyzer_reruns == 0
