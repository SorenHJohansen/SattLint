"""Tests for variable-quality analyzers: MMS, loop output, parameter drift, cyclomatic complexity, scan-loop resource, min/max, contract mismatch, magic numbers, shadowing, variables analysis, and datatype duplication."""

import logging
from pathlib import Path

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattlint import constants as const
from sattlint.analyzers.cyclomatic_complexity import analyze_cyclomatic_complexity
from sattlint.analyzers.loop_output_refactor import analyze_loop_output_refactor
from sattlint.analyzers.mms import analyze_mms_interface_variables
from sattlint.analyzers.parameter_drift import analyze_parameter_drift
from sattlint.analyzers.scan_loop_resource_usage import analyze_scan_loop_resource_usage
from sattlint.analyzers.shadowing import analyze_shadowing
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.engine import parse_source_file
from sattlint.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FloatLiteral,
    IntLiteral,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCCodeBlocks,
    SFCStep,
    SFCTransition,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattlint.reporting.icf_report import ICFEntry
from sattlint.reporting.variables_report import (
    VariablesReport,
)
from sattlint.resolution.scope import ScopeContext


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(s: str) -> dict:
    return {const.KEY_VAR_NAME: s}


def _state_ref(name: str, state: str) -> dict:
    return {const.KEY_VAR_NAME: name, "state": state}


def _issue_kinds(report) -> set[str]:
    return {issue.kind for issue in report.issues}


def _status_bridge_typedef() -> ModuleTypeDef:
    return ModuleTypeDef(
        name="StatusBridge",
        moduleparameters=[Variable(name="OperationStatus", datatype=Simple_DataType.INTEGER)],
        localvariables=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Destination", datatype=Simple_DataType.INTEGER),
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="BridgeEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [_varref("Source"), _varref("Destination"), _varref("OperationStatus")],
                        )
                    ],
                )
            ]
        ),
    )


def test_mms_interface_flags_dead_tags_for_unwritten_outgoing_variables():
    sender = ModuleTypeInstance(
        header=_hdr("SendToOpc"),
        moduletype_name="MMSWriteVar",
        parametermappings=[
            ParameterMapping(
                target=_varref("RemoteVarName"),
                source_type=const.KEY_VALUE,
                is_duration=False,
                is_source_global=False,
                source=None,
                source_literal="Plant.Result",
            ),
            ParameterMapping(
                target=_varref("LocalVariable"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("ExportValue"),
                source_literal=None,
            ),
        ],
    )

    unit = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="ExportValue", datatype=Simple_DataType.INTEGER)],
        submodules=[sender],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[unit],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_mms_interface_variables(bp)

    dead_tag_issues = [issue for issue in report.issues if issue.kind == "mms.dead_tag"]
    assert len(dead_tag_issues) == 1
    assert "Plant.Result" in dead_tag_issues[0].message


def test_mms_interface_flags_duplicate_tags_and_datatype_mismatch_from_icf_entries():
    unit_a = SingleModule(
        header=_hdr("UnitA"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Result", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    unit_b = SingleModule(
        header=_hdr("UnitB"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Result", datatype=Simple_DataType.BOOLEAN)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[unit_a, unit_b],
        modulecode=None,
        moduledef=None,
    )

    entries = [
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=1,
            section="JournalData_DCStoMES",
            key="ResultCode",
            value="Program:UnitA.Result",
        ),
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=2,
            section="JournalData_DCStoMES",
            key="ResultCode",
            value="Program:UnitB.Result",
        ),
    ]

    report = analyze_mms_interface_variables(bp, icf_entries=entries)

    assert "mms.duplicate_tag" in _issue_kinds(report)
    assert "mms.datatype_mismatch" in _issue_kinds(report)


def test_mms_interface_flags_naming_drift_from_icf_entries():
    unit = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="ResultText", datatype=Simple_DataType.STRING)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[unit],
        modulecode=None,
        moduledef=None,
    )

    entries = [
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=1,
            section="JournalData_DCStoMES",
            key="ResultText",
            value="Program:Unit.ResultText",
        ),
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=2,
            section="JournalData_DCStoMES",
            key="RESULT_TEXT",
            value="Program:Unit.ResultText",
        ),
    ]

    report = analyze_mms_interface_variables(bp, icf_entries=entries)

    naming_drift_issues = [issue for issue in report.issues if issue.kind == "mms.naming_drift"]
    assert len(naming_drift_issues) == 1
    assert "ResultText" in naming_drift_issues[0].message
    assert "RESULT_TEXT" in naming_drift_issues[0].message


def test_loop_output_refactor_detects_cycle_across_equations_and_active_step():
    eq_input = Equation(
        name="Input",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[(const.KEY_ASSIGN, _varref("A"), _varref("B"))],
    )
    eq_feedback = Equation(
        name="Feedback",
        position=(1.0, 0.0),
        size=(1.0, 1.0),
        code=[(const.KEY_ASSIGN, _varref("B"), _varref("C"))],
    )
    seq = Sequence(
        name="MainSeq",
        type="sequence",
        position=(0.0, 1.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Transfer",
                code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("C"), _varref("A"))]),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.INTEGER),
            Variable(name="C", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(equations=[eq_input, eq_feedback], sequences=[seq]),
        moduledef=None,
    )

    report = analyze_loop_output_refactor(bp)

    issues = [issue for issue in report.issues if issue.kind == "sorting.loop_output_refactor"]
    assert len(issues) == 1
    issue = issues[0]
    assert issue.data is not None
    assert issue.data["dependency_variables"] == ["a", "b", "c"]
    assert issue.data["blocks"] == [
        "EquationBlock 'Input'",
        "EquationBlock 'Feedback'",
        "Sequence 'MainSeq' step 'Transfer' ACTIVE",
    ]
    assert "Sequence 'MainSeq' step 'Transfer' ACTIVE" in issue.data["loop_text"]
    assert "At least one dependency in this cycle is delayed by one scan" in issue.data["loop_text"]

    summary = report.summary()
    assert "semantic.loop-output-refactor" in summary
    assert "Suggested fix:" in summary


def test_loop_output_refactor_ignores_acyclic_sorted_blocks():
    eq_source = Equation(
        name="Source",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[(const.KEY_ASSIGN, _varref("A"), _varref("B"))],
    )
    eq_sink = Equation(
        name="Sink",
        position=(1.0, 0.0),
        size=(1.0, 1.0),
        code=[(const.KEY_ASSIGN, _varref("C"), _varref("A"))],
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.INTEGER),
            Variable(name="C", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(equations=[eq_source, eq_sink], sequences=[]),
        moduledef=None,
    )

    report = analyze_loop_output_refactor(bp)

    assert not any(issue.kind == "sorting.loop_output_refactor" for issue in report.issues)


def test_parameter_drift_flags_diverging_literal_parameter_values():
    typedef = ModuleTypeDef(
        name="DoseValve",
        moduleparameters=[
            Variable(name="Timeout", datatype=Simple_DataType.INTEGER, init_value=10),
        ],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
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
        modulecode=None,
        moduledef=None,
    )

    report = analyze_parameter_drift(bp)

    drift_issues = [issue for issue in report.issues if issue.kind == "module.parameter_drift"]
    assert len(drift_issues) == 2
    assert all("Timeout" in issue.message for issue in drift_issues)
    assert any("Program.ValveA=10" in issue.message for issue in drift_issues)
    assert any("Program.ValveB=15" in issue.message for issue in drift_issues)


def test_parameter_drift_ignores_aligned_literal_parameter_values():
    typedef = ModuleTypeDef(
        name="DoseValve",
        moduleparameters=[
            Variable(name="Timeout", datatype=Simple_DataType.INTEGER, init_value=10),
        ],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
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
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_parameter_drift(bp)

    assert not any(issue.kind == "module.parameter_drift" for issue in report.issues)


def test_cyclomatic_complexity_ignores_low_complexity_program_modulecode():
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="MainEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), IntLiteral(1))],
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_cyclomatic_complexity(bp)

    assert not any(issue.kind == "module.cyclomatic_complexity" for issue in report.issues)
    assert not any(issue.kind == "step.cyclomatic_complexity" for issue in report.issues)


def test_cyclomatic_complexity_flags_high_complexity_program_modulecode():
    decision_statements = [
        (
            const.GRAMMAR_VALUE_IF,
            [
                (
                    _varref(f"Cond{index}"),
                    [(const.KEY_ASSIGN, _varref("Output"), IntLiteral(index))],
                )
            ],
            [],
        )
        for index in range(10)
    ]
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name=f"Cond{index}", datatype=Simple_DataType.BOOLEAN) for index in range(10)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="MainEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=decision_statements,
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_cyclomatic_complexity(bp)

    issues = [issue for issue in report.issues if issue.kind == "module.cyclomatic_complexity"]
    assert len(issues) == 1
    assert issues[0].data == {"scope": "program", "complexity": 11, "threshold": 10}
    assert "Program" in issues[0].message


def test_cyclomatic_complexity_flags_high_complexity_sfc_step():
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            sequences=[
                Sequence(
                    name="MainSeq",
                    type="SEQUENCE",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        SFCStep(
                            kind="step",
                            name="HeatUp",
                            code=SFCCodeBlocks(
                                active=[
                                    (
                                        const.GRAMMAR_VALUE_IF,
                                        [
                                            (
                                                _varref(f"StepCond{index}"),
                                                [(const.KEY_ASSIGN, _varref("Output"), IntLiteral(index))],
                                            )
                                        ],
                                        [],
                                    )
                                    for index in range(6)
                                ]
                            ),
                        ),
                        SFCTransition(name="Continue", condition=_varref("Proceed")),
                    ],
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_cyclomatic_complexity(bp)

    issues = [issue for issue in report.issues if issue.kind == "step.cyclomatic_complexity"]
    assert len(issues) == 1
    assert issues[0].data == {
        "scope": "step",
        "sequence": "MainSeq",
        "step": "HeatUp",
        "complexity": 7,
        "threshold": 6,
    }
    assert "HeatUp" in issues[0].message
    assert "MainSeq" in issues[0].message


def test_scan_loop_resource_usage_flags_non_precision_builtin_in_equation_block():
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="MainEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "AssignSystemString",
                            [_varref("SysVarId"), _varref("Value"), _varref("Status")],
                        )
                    ],
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_scan_loop_resource_usage(bp)

    issues = [issue for issue in report.issues if issue.kind == "scan_cycle.resource_usage"]
    assert len(issues) == 1
    assert issues[0].data == {
        "call": "assignsystemstring",
        "context": "equation block 'MainEq'",
        "precision_scangroup": False,
    }
    assert "AssignSystemString" in issues[0].message


def test_scan_loop_resource_usage_flags_non_precision_builtin_in_active_step_code():
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            sequences=[
                Sequence(
                    name="MainSeq",
                    type="SEQUENCE",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        SFCStep(
                            kind="step",
                            name="Poll",
                            code=SFCCodeBlocks(
                                active=[
                                    (
                                        const.KEY_FUNCTION_CALL,
                                        "AssignSystemString",
                                        [_varref("SysVarId"), _varref("Value"), _varref("Status")],
                                    )
                                ]
                            ),
                        )
                    ],
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_scan_loop_resource_usage(bp)

    issues = [issue for issue in report.issues if issue.kind == "scan_cycle.resource_usage"]
    assert len(issues) == 1
    assert issues[0].data == {
        "call": "assignsystemstring",
        "context": "active code of step 'Poll' in sequence 'MainSeq'",
        "precision_scangroup": False,
    }
    assert "Poll" in issues[0].message
    assert "MainSeq" in issues[0].message


def test_scan_loop_resource_usage_ignores_non_precision_builtin_outside_active_scan_context():
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            sequences=[
                Sequence(
                    name="MainSeq",
                    type="SEQUENCE",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        SFCStep(
                            kind="step",
                            name="Setup",
                            code=SFCCodeBlocks(
                                enter=[
                                    (
                                        const.KEY_FUNCTION_CALL,
                                        "AssignSystemString",
                                        [_varref("SysVarId"), _varref("Value"), _varref("Status")],
                                    )
                                ]
                            ),
                        )
                    ],
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_scan_loop_resource_usage(bp)

    assert not any(issue.kind == "scan_cycle.resource_usage" for issue in report.issues)


def test_min_max_mapping_mismatch_detected():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="MaxValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("MaxValue"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("MinValue"),
                source_literal=None,
            )
        ],
    )

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="MinValue", datatype=Simple_DataType.INTEGER),
            Variable(name="MaxValue", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert any(i.kind is IssueKind.MIN_MAX_MAPPING_MISMATCH for i in analyzer.issues)


def test_min_max_mapping_mismatch_not_raised_for_aligned_names():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="MinValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("MinValue"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("MinValue"),
                source_literal=None,
            )
        ],
    )

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="MinValue", datatype=Simple_DataType.INTEGER)],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(i.kind is IssueKind.MIN_MAX_MAPPING_MISMATCH for i in analyzer.issues)


def test_unknown_parameter_target_detected_for_single_module_mapping():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="DeclaredValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
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

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="SourceValue", datatype=Simple_DataType.INTEGER)],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.UNKNOWN_PARAMETER_TARGET]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "Parent", "Child"]
    assert issues[0].role == "unknown parameter mapping target 'MissingValue'"


def test_contract_mismatch_detected_for_moduletype_parameter_mapping():
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
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[Variable(name="SourceFlag", datatype=Simple_DataType.BOOLEAN)],
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

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.CONTRACT_MISMATCH]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "Child"]
    assert issues[0].variable is not None
    assert issues[0].variable.name == "ExpectedValue"
    assert issues[0].source_variable is not None
    assert issues[0].source_variable.name == "SourceFlag"
    assert "boolean" in (issues[0].role or "")
    assert "integer" in (issues[0].role or "")


def test_contract_mismatch_ignores_anytype_targets():
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="ExpectedValue", datatype="AnyType")],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[Variable(name="SourceFlag", datatype=Simple_DataType.BOOLEAN)],
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

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(issue.kind is IssueKind.CONTRACT_MISMATCH for issue in analyzer.issues)


def test_unknown_parameter_target_detected_for_moduletype_instance_mapping():
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="DeclaredValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    instance = ModuleTypeInstance(
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
    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="SourceValue", datatype=Simple_DataType.INTEGER)],
        submodules=[instance],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.UNKNOWN_PARAMETER_TARGET]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "Parent", "Child"]
    assert issues[0].role == "unknown parameter mapping target 'MissingValue'"


def test_required_parameter_connection_flags_unmapped_used_moduletype_parameter():
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="RequiredValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Mirror", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="UseParam",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Mirror"),
                            _varref("RequiredValue"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
    )
    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Child"),
                moduletype_name="ChildType",
                parametermappings=[],
            )
        ],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.REQUIRED_PARAMETER_CONNECTION]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "Parent", "Child"]
    assert issues[0].variable is not None
    assert issues[0].variable.name == "RequiredValue"
    assert issues[0].role == "required parameter connection missing for 'RequiredValue'"


def test_required_parameter_connection_flags_unmapped_used_single_module_parameter():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="RequiredValue", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Mirror", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="UseParam",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Mirror"),
                            _varref("RequiredValue"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
    )
    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.REQUIRED_PARAMETER_CONNECTION]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "Parent", "Child"]
    assert issues[0].variable is not None
    assert issues[0].variable.name == "RequiredValue"
    assert issues[0].role == "required parameter connection missing for 'RequiredValue'"


def test_magic_number_detection_in_equations_and_sfc():
    eq = Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            (
                const.KEY_ASSIGN,
                _varref("Output"),
                IntLiteral(42, SourceSpan(12, 5)),
            ),
            (
                const.KEY_ASSIGN,
                _varref("Output"),
                IntLiteral(0, SourceSpan(13, 5)),
            ),
            (
                const.KEY_ASSIGN,
                _varref("Output"),
                (const.KEY_MINUS, IntLiteral(0, SourceSpan(14, 5))),
            ),
        ],
    )

    transition = SFCTransition(
        name="ToNext",
        condition=(
            const.KEY_COMPARE,
            _varref("Output"),
            [
                (">", FloatLiteral(2.5, SourceSpan(20, 7))),
                ("<", FloatLiteral(0.0, SourceSpan(21, 9))),
            ],
        ),
    )

    seq = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[transition],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        modulecode=ModuleCode(sequences=[seq], equations=[eq]),
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    magic = [i for i in analyzer.issues if i.kind is IssueKind.MAGIC_NUMBER]
    assert len(magic) == 2

    values = sorted(i.literal_value for i in magic if i.literal_value is not None)
    assert values == [2.5, 42]

    spans = {(i.literal_span.line, i.literal_span.column) for i in magic if i.literal_span is not None}
    assert (12, 5) in spans
    assert (20, 7) in spans
    assert (13, 5) not in spans
    assert (14, 5) not in spans
    assert (21, 9) not in spans


def test_shadowing_detected_for_nested_locals():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="value", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="Value", datatype=Simple_DataType.INTEGER)],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_shadowing(bp)

    assert any(i.kind is IssueKind.SHADOWING for i in report.issues)


def test_shadowing_detected_for_moduletype_instance_locals():
    mt = ModuleTypeDef(
        name="TypeA",
        moduleparameters=[],
        localvariables=[Variable(name="Setting", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )

    instance = ModuleTypeInstance(
        header=_hdr("InstanceA"),
        moduletype_name="TypeA",
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[mt],
        localvariables=[Variable(name="setting", datatype=Simple_DataType.INTEGER)],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_shadowing(bp)

    assert any(i.kind is IssueKind.SHADOWING for i in report.issues)


def test_variable_analysis_marks_invar_reads_across_graphics_and_interact_paths():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0 : InVar_ "PosX",0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    PosX: integer := 0;
    PanelResize: integer := 0;
    WidthSource: integer := 0;
    FormatSource: integer := 0;
    ColourSource: integer := 0;
    ButtonTypeSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 : InVar_ "PanelResize" ) ( 1.0 , 1.0 )
    GraphObjects :
        TextObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            "Value" VarName Width_ = 5 : InVar_ "WidthSource"
            Format_String_ = "" : InVar_ "FormatSource"
            OutlineColour : Colour0 = 5 : InVar_ "ColourSource"
    InteractObjects :
        ComBut_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            ButtonType = 0 : InVar_ "ButtonTypeSource"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    usage_by_name = {variable.name: analyzer._get_usage(variable) for variable in bp.localvariables}

    assert usage_by_name["PosX"].read is True
    assert usage_by_name["PanelResize"].read is True
    assert usage_by_name["WidthSource"].read is True
    assert usage_by_name["FormatSource"].read is True
    assert usage_by_name["ColourSource"].read is True
    assert usage_by_name["ButtonTypeSource"].read is True
    assert usage_by_name["WidthSource"].ui_read is True
    assert usage_by_name["ButtonTypeSource"].ui_read is True


def test_ui_only_variable_detected_for_graphics_invar_reads():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    WidthSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    GraphObjects :
        TextObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            "Value" VarName Width_ = 5 : InVar_ "WidthSource"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.UI_ONLY]

    assert len(issues) == 1
    assert issues[0].variable is not None
    assert issues[0].variable.name == "WidthSource"
    assert not any(issue.kind is IssueKind.READ_ONLY_NON_CONST for issue in analyzer.issues)


def test_ui_only_variable_detected_for_interact_invar_reads():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    ButtonTypeSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    InteractObjects :
        ComBut_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            ButtonType = 0 : InVar_ "ButtonTypeSource"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.UI_ONLY]

    assert len(issues) == 1
    assert issues[0].variable is not None
    assert issues[0].variable.name == "ButtonTypeSource"


def test_ui_only_variable_is_suppressed_by_non_ui_control_usage():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    WidthSource: integer := 0;
    Output: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    GraphObjects :
        TextObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            "Value" VarName Width_ = 5 : InVar_ "WidthSource"
    ModuleCode
        EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            Output = WidthSource;
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UI_ONLY and issue.variable is not None and issue.variable.name == "WidthSource"
        for issue in analyzer.issues
    )


def test_graphics_format_tail_keywords_do_not_log_missing_variables(caplog):
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="RealSource", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    analyzer = VariablesAnalyzer(bp, debug=True)
    context = ScopeContext(
        env={"realsource": bp.localvariables[0]},
        param_mappings={},
        module_path=[bp.header.name],
        display_module_path=[bp.header.name],
    )

    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        for token in ("Real_Value", "Relative_", "Decimal_", "Int_Value", "Abs_"):
            analyzer._walk_tail(token, context, [bp.header.name])
        analyzer._walk_tail("RealSource", context, [bp.header.name])
        analyzer._walk_tail("MissingVar", context, [bp.header.name])

    messages = [record.message for record in caplog.records]

    assert not any("real_value" in message.lower() for message in messages)
    assert not any("relative_" in message.lower() for message in messages)
    assert not any("decimal_" in message.lower() for message in messages)
    assert not any("int_value" in message.lower() for message in messages)
    assert not any("abs_" in message.lower() for message in messages)
    assert any("missingvar" in message.lower() for message in messages)
    assert analyzer._get_usage(bp.localvariables[0]).read is True


def test_variables_fallback_warnings_are_not_logged_without_debug(caplog):
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    analyzer = VariablesAnalyzer(bp, debug=False, fail_loudly=False)

    with caplog.at_level(logging.WARNING, logger="SattLint"):
        analyzer._warn("test fallback warning")

    assert analyzer.analysis_warnings == ["test fallback warning"]
    assert not caplog.records


def test_interact_litstring_invar_tail_does_not_crash_variable_analysis():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    WidthSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    InteractObjects :
        ComBut_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            Abs_ TextObject = "" : InVar_ LitString "Start Sim"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    width_source = bp.localvariables[0]

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert analyzer._get_usage(width_source).read is False


def test_shadowing_ignores_external_moduletype_instance_locals_for_program_target():
    mt = ModuleTypeDef(
        name="TypeA",
        moduleparameters=[],
        localvariables=[Variable(name="Setting", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="TypeA.x",
        origin_lib="SomeLib",
    )

    instance = ModuleTypeInstance(
        header=_hdr("InstanceA"),
        moduletype_name="TypeA",
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[mt],
        localvariables=[Variable(name="setting", datatype=Simple_DataType.INTEGER)],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProgramLib",
    )

    report = analyze_shadowing(bp)

    assert not any(i.kind is IssueKind.SHADOWING for i in report.issues)


def test_variable_analysis_ignores_external_moduletype_usage_for_program_target():
    library_mt = ModuleTypeDef(
        name="LibType",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="E1",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[_varref("Input")],
                )
            ]
        ),
        parametermappings=[],
        origin_file="LibType.x",
        origin_lib="SomeLib",
    )

    instance = ModuleTypeInstance(
        header=_hdr("LibInst"),
        moduletype_name="LibType",
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("ProgramVar"),
                source_literal=None,
            )
        ],
    )

    program_var = Variable(name="ProgramVar", datatype=Simple_DataType.INTEGER)
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[library_mt],
        localvariables=[program_var],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProgramLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert any(issue.kind is IssueKind.UNUSED and issue.variable is program_var for issue in analyzer.issues)


def test_variable_analysis_treats_external_moduletype_usage_as_used_for_library_target():
    library_mt = ModuleTypeDef(
        name="LibType",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="E1",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[_varref("Input")],
                )
            ]
        ),
        parametermappings=[],
        origin_file="LibType.x",
        origin_lib="SomeLib",
    )

    instance = ModuleTypeInstance(
        header=_hdr("LibInst"),
        moduletype_name="LibType",
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("LibraryVar"),
                source_literal=None,
            )
        ],
    )

    library_var = Variable(name="LibraryVar", datatype=Simple_DataType.INTEGER)
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[library_mt],
        localvariables=[library_var],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(issue.variable is library_var for issue in analyzer.issues)


def test_library_typedef_moduleparameter_unused_fields_are_suppressed():
    record_type = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Used", datatype=Simple_DataType.INTEGER),
            Variable(name="Unused", datatype=Simple_DataType.INTEGER),
        ],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    exported = ModuleTypeDef(
        name="ExportedType",
        moduleparameters=[Variable(name="p", datatype="RecType")],
        localvariables=[Variable(name="sink", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("sink"),
                            _varref("p.Used"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[exported],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    program_analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=False)
    program_analyzer.run()
    assert any(
        issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
        and issue.datatype_name == "RecType"
        and issue.field_path == "Unused"
        for issue in program_analyzer.issues
    )

    library_analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    library_analyzer.run()
    assert not any(
        issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
        and issue.datatype_name == "RecType"
        and issue.field_path == "Unused"
        for issue in library_analyzer.issues
    )


def test_unused_datatype_fields_are_aggregated_across_variables():
    record_type = DataType(
        name="SharedRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.INTEGER),
            Variable(name="C", datatype=Simple_DataType.INTEGER),
        ],
        origin_file="Root.x",
        origin_lib="ProjectLib",
    )

    first = Variable(name="First", datatype="SharedRecord")
    second = Variable(name="Second", datatype="SharedRecord")

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[first, second],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("sinkA"), _varref("First.A")),
                        (const.KEY_ASSIGN, _varref("sinkB"), _varref("Second.B")),
                    ],
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[
            Variable(name="sinkA", datatype=Simple_DataType.INTEGER),
            Variable(name="sinkB", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[module],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    unused_fields = {
        issue.field_path
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "SharedRecord"
    }

    assert unused_fields == {"C"}


def test_sample_fixture_contains_common_variable_quality_issues():
    fixture = Path(__file__).parent / "fixtures" / "sample_sattline_files" / "CommonQualityIssues.s"

    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp).run()

    unused = {issue.variable.name for issue in issues if issue.kind is IssueKind.UNUSED and issue.variable is not None}
    read_only_non_const = {
        issue.variable.name
        for issue in issues
        if issue.kind is IssueKind.READ_ONLY_NON_CONST and issue.variable is not None
    }
    never_read = {
        issue.variable.name for issue in issues if issue.kind is IssueKind.NEVER_READ and issue.variable is not None
    }
    unused_fields = {
        (issue.datatype_name, issue.field_path) for issue in issues if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
    }

    assert "UnusedValue" in unused
    assert "ReadOnlyValue" in read_only_non_const
    assert "NeverReadValue" in never_read
    assert ("QualityRecord", "UnusedField") in unused_fields


def test_datatype_duplication_is_scoped_per_module_and_excludes_anytype():
    fyld = ModuleTypeDef(
        name="Fyld",
        moduleparameters=[
            Variable(name="WildcardA", datatype="AnyType"),
            Variable(name="WildcardB", datatype="AnyType"),
        ],
        localvariables=[
            Variable(name="PhaseTimer", datatype="Timer"),
            Variable(name="PhaseTimerCopy", datatype="Timer"),
        ],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )
    applik = ModuleTypeDef(
        name="Applik",
        moduleparameters=[Variable(name="WildcardC", datatype="AnyType")],
        localvariables=[Variable(name="PhaseTimer", datatype="Timer")],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[fyld, applik],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    duplication_issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.DATATYPE_DUPLICATION]
    assert len(duplication_issues) == 1

    issue = duplication_issues[0]
    assert issue.module_path == ["BasePicture", "TypeDef:Fyld"]
    assert issue.variable is not None
    assert issue.variable.name == "PhaseTimer"
    assert issue.variable.datatype_text == "Timer"
    assert issue.duplicate_count == 2
    assert issue.duplicate_locations == [(["BasePicture", "TypeDef:Fyld"], "localvariable", "PhaseTimerCopy")]

    summary = VariablesReport(basepicture_name=bp.header.name, issues=duplication_issues).summary()
    assert "Datatype 'Timer' declared 2 times in BasePicture.TypeDef:Fyld:" in summary
    assert "+ PhaseTimerCopy (localvariable)" in summary
    assert "AnyType" not in summary
    assert "TypeDef:Applik" not in summary
