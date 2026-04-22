"""Tests for analyzer behavior and reports."""

import logging
from pathlib import Path
from typing import Any, cast

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattlint import constants as const
from sattlint.analyzers.alarm_integrity import analyze_alarm_integrity
from sattlint.analyzers.cyclomatic_complexity import analyze_cyclomatic_complexity
from sattlint.analyzers.dataflow import analyze_dataflow
from sattlint.analyzers.initial_values import analyze_initial_values
from sattlint.analyzers.loop_output_refactor import analyze_loop_output_refactor
from sattlint.analyzers.mms import analyze_mms_interface_variables
from sattlint.analyzers.modules import analyze_version_drift
from sattlint.analyzers.naming import analyze_naming_consistency, get_configured_naming_rules
from sattlint.analyzers.parameter_drift import analyze_parameter_drift
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.safety_paths import analyze_safety_paths
from sattlint.analyzers.scan_loop_resource_usage import analyze_scan_loop_resource_usage
from sattlint.analyzers.sfc import analyze_sfc
from sattlint.analyzers.shadowing import analyze_shadowing
from sattlint.analyzers.taint_paths import analyze_taint_paths
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.engine import parse_source_file
from sattlint.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FloatLiteral,
    FrameModule,
    GraphObject,
    IntLiteral,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    SFCTransition,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattlint.reporting.icf_report import ICFEntry
from sattlint.reporting.variables_report import (
    ALL_VARIABLE_ANALYSIS_KINDS,
    VariableIssue,
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


def test_reset_contamination_detected_for_missing_reset_write():
    seq = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[],
    )

    eq = Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            (
                const.GRAMMAR_VALUE_IF,
                [
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OperationSequence.Reset")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Counter"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OprSeqResetOld")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Other"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                ],
                [],
            ),
            (
                const.KEY_ASSIGN,
                _varref("OprSeqResetOld"),
                _varref("OperationSequence.Reset"),
            ),
        ],
    )

    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="Other", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="OprSeqResetOld", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(sequences=[seq], equations=[eq]),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [i for i in analyzer.issues if i.kind is IssueKind.RESET_CONTAMINATION]
    assert any(i.variable and i.variable.name == "Counter" for i in issues)


def test_reset_contamination_cleared_when_reset_writes_present():
    seq = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[],
    )

    eq = Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            (
                const.GRAMMAR_VALUE_IF,
                [
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OperationSequence.Reset")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Counter"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OprSeqResetOld")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Counter"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                ],
                [],
            ),
            (
                const.KEY_ASSIGN,
                _varref("OprSeqResetOld"),
                _varref("OperationSequence.Reset"),
            ),
        ],
    )

    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="OprSeqResetOld", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(sequences=[seq], equations=[eq]),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(i.kind is IssueKind.RESET_CONTAMINATION for i in analyzer.issues)


def test_implicit_latch_detected_when_if_branch_sets_true_without_else_clear():
    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="AlarmLatched", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
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
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [i for i in analyzer.issues if i.kind is IssueKind.IMPLICIT_LATCH]
    assert len(issues) == 1
    assert issues[0].variable is not None
    assert issues[0].variable.name == "AlarmLatched"
    assert issues[0].site == "EQ:Main > IF"


def test_implicit_latch_not_reported_when_else_branch_clears_false():
    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Start", datatype=Simple_DataType.BOOLEAN),
            Variable(name="AlarmLatched", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
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
                            [
                                (
                                    const.KEY_ASSIGN,
                                    _varref("AlarmLatched"),
                                    False,
                                )
                            ],
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(i.kind is IssueKind.IMPLICIT_LATCH for i in analyzer.issues)


def test_implicit_latch_detected_for_step_without_exit_clear():
    seq = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Run",
                code=SFCCodeBlocks(
                    active=[
                        (
                            const.KEY_ASSIGN,
                            _varref("StepFlag"),
                            True,
                        )
                    ],
                    exit=[],
                ),
            )
        ],
    )

    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="StepFlag", datatype=Simple_DataType.BOOLEAN)],
        submodules=[],
        modulecode=ModuleCode(sequences=[seq], equations=[]),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [i for i in analyzer.issues if i.kind is IssueKind.IMPLICIT_LATCH]
    assert len(issues) == 1
    assert issues[0].variable is not None
    assert issues[0].variable.name == "StepFlag"
    assert issues[0].site == "SEQ:OperationSequence > STEP:Run"


def test_sfc_step_contract_detects_missing_enter_initialization():
    sequence = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
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
            )
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="StepValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(
        bp,
        step_contracts={
            "Run": {"required_enter_writes": ["StepValue"]},
        },
    )

    issues = [issue for issue in report.issues if issue.kind == "sfc_missing_step_enter_contract"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["missing_enter_writes"] == ["StepValue"]


def test_sfc_step_contract_detects_missing_exit_cleanup():
    sequence = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Run",
                code=SFCCodeBlocks(
                    enter=[
                        (
                            const.KEY_ASSIGN,
                            _varref("StepValue"),
                            1,
                        )
                    ],
                    active=[],
                    exit=[],
                ),
            )
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="StepValue", datatype=Simple_DataType.INTEGER)],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(
        bp,
        step_contracts={
            "Run": {"required_exit_writes": ["StepValue"]},
        },
    )

    issues = [issue for issue in report.issues if issue.kind == "sfc_missing_step_exit_contract"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["missing_exit_writes"] == ["StepValue"]


def test_sfc_step_contract_detects_state_leakage_across_steps():
    sequence = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
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
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="StepValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(
        bp,
        step_contracts={
            "Run": {"required_enter_writes": ["StepValue"]},
        },
    )

    issues = [issue for issue in report.issues if issue.kind == "sfc_step_state_leakage"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["leaked_state"] == ["StepValue"]


def test_write_without_effect_detected_for_internal_value_chain():
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

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    write_without_effect = [issue for issue in analyzer.issues if issue.kind is IssueKind.WRITE_WITHOUT_EFFECT]
    assert [issue.variable.name for issue in write_without_effect if issue.variable is not None] == ["Stage1"]
    assert any(
        issue.kind is IssueKind.NEVER_READ and issue.variable is not None and issue.variable.name == "Stage2"
        for issue in analyzer.issues
    )


def test_write_without_effect_is_suppressed_for_mapped_output_path():
    child = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[Variable(name="Out", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Internal", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Internal"), 1),
                        (const.KEY_ASSIGN, _varref("Out"), _varref("Internal")),
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("Out"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("FinalOutput"),
                source_literal=None,
            )
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="FinalOutput", datatype=Simple_DataType.INTEGER)],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.WRITE_WITHOUT_EFFECT
        and issue.variable is not None
        and issue.variable.name in {"Internal", "Out"}
        for issue in analyzer.issues
    )


def test_hidden_global_coupling_is_reported_for_sibling_modules_using_root_global():
    shared_value = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)

    writer = SingleModule(
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
    )
    reader = SingleModule(
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
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[shared_value],
        submodules=[writer, reader],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    hidden_issues = [
        issue
        for issue in analyzer.issues
        if issue.kind is IssueKind.HIDDEN_GLOBAL_COUPLING and issue.variable is shared_value
    ]
    assert len(hidden_issues) == 1
    assert "Writer (write)" in (hidden_issues[0].role or "")
    assert "Reader (read)" in (hidden_issues[0].role or "")


def test_hidden_global_coupling_is_not_reported_for_explicit_parameter_mappings():
    writer = SingleModule(
        header=_hdr("Writer"),
        moduledef=None,
        moduleparameters=[Variable(name="Out", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Produce",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Out"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("Out"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("SharedValue"),
                source_literal=None,
            )
        ],
    )
    reader = SingleModule(
        header=_hdr("Reader"),
        moduledef=None,
        moduleparameters=[Variable(name="In", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Consume",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("In"))],
                )
            ],
            sequences=[],
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("In"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("SharedValue"),
                source_literal=None,
            )
        ],
    )
    coordinator = SingleModule(
        header=_hdr("Coordinator"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)],
        submodules=[writer, reader],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        submodules=[coordinator],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(issue.kind is IssueKind.HIDDEN_GLOBAL_COUPLING for issue in analyzer.issues)


def test_global_scope_minimization_is_reported_for_root_global_confined_to_one_module_subtree():
    confined = Variable(name="ConfinedValue", datatype=Simple_DataType.INTEGER)

    worker = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[
            SingleModule(
                header=_hdr("Nested"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=ModuleCode(
                    equations=[
                        Equation(
                            name="WriteConfined",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[(const.KEY_ASSIGN, _varref("ConfinedValue"), 1)],
                        )
                    ],
                    sequences=[],
                ),
                parametermappings=[],
            )
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadConfined",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("ConfinedValue"))],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[confined],
        submodules=[worker],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [
        issue
        for issue in analyzer.issues
        if issue.kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION and issue.variable is confined
    ]

    assert len(issues) == 1
    assert "Worker" in (issues[0].role or "")
    assert "Nested" in (issues[0].role or "")


def test_global_scope_minimization_is_not_reported_for_root_global_used_in_root_scope():
    confined = Variable(name="ConfinedValue", datatype=Simple_DataType.INTEGER)

    worker = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="WriteConfined",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("ConfinedValue"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[confined, Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[worker],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadAtRoot",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Observed"), _varref("ConfinedValue"))],
                )
            ],
            sequences=[],
        ),
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION and issue.variable is confined for issue in analyzer.issues
    )


def test_global_scope_minimization_is_suppressed_for_library_targets():
    confined = Variable(name="ConfinedValue", datatype=Simple_DataType.INTEGER)

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[confined],
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

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(issue.kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION for issue in analyzer.issues)
    assert not any(issue.kind is IssueKind.HIDDEN_GLOBAL_COUPLING for issue in analyzer.issues)


def test_high_fan_in_out_is_reported_for_root_global_shared_across_many_modules():
    shared = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)

    writer = SingleModule(
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
    )
    reader_a = SingleModule(
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
    )
    reader_b = SingleModule(
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
    )
    reader_c = SingleModule(
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
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[shared],
        submodules=[writer, reader_a, reader_b, reader_c],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [
        issue for issue in analyzer.issues if issue.kind is IssueKind.HIGH_FAN_IN_OUT and issue.variable is shared
    ]

    assert len(issues) == 1
    assert "high fan-in with 3 readers" in (issues[0].role or "")
    assert "ReaderA" in (issues[0].role or "")
    assert "ReaderB" in (issues[0].role or "")
    assert "ReaderC" in (issues[0].role or "")


def test_high_fan_in_out_is_not_reported_below_threshold():
    shared = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[shared],
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
        ],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(issue.kind is IssueKind.HIGH_FAN_IN_OUT and issue.variable is shared for issue in analyzer.issues)


def test_variables_report_summary_includes_name_collisions():
    variable = Variable(name="Value", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.NAME_COLLISION,
        module_path=["BasePicture", "TypeDef:Unit"],
        variable=variable,
        role="name collision with parameter 'Value'",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Sections:" in summary
    assert "  - Name collisions: 1" in summary
    assert "Name collisions" in summary
    assert ("BasePicture.TypeDef:Unit :: Value (integer) | " "name collision with parameter 'Value'") in summary


def test_variables_report_summary_includes_write_without_effect_section():
    variable = Variable(name="Stage1", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.WRITE_WITHOUT_EFFECT,
        module_path=["BasePicture", "Worker"],
        variable=variable,
        role="localvariable",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Write-without-effect variables" in summary
    assert "  - Write-without-effect variables: 1" in summary
    assert "Stage1" in summary


def test_variables_report_summary_includes_hidden_global_coupling_section():
    variable = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.HIDDEN_GLOBAL_COUPLING,
        module_path=["BasePicture"],
        variable=variable,
        role="hidden global coupling across modules: Writer (write), Reader (read)",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Hidden global coupling" in summary
    assert "SharedValue" in summary


def test_variables_report_summary_includes_high_fan_in_out_section():
    variable = Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.HIGH_FAN_IN_OUT,
        module_path=["BasePicture"],
        variable=variable,
        role="high fan-in with 3 readers: ReaderA, ReaderB, ReaderC",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "High fan-in or fan-out variables" in summary
    assert "SharedValue" in summary


def test_variables_report_summary_includes_global_scope_minimization_section():
    variable = Variable(name="ConfinedValue", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.GLOBAL_SCOPE_MINIMIZATION,
        module_path=["BasePicture"],
        variable=variable,
        role="global scope can be reduced to module subtree Worker: Worker, Worker.Nested",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Global scope minimization candidates" in summary
    assert "ConfinedValue" in summary


def test_variables_report_summary_includes_ui_only_section():
    variable = Variable(name="DisplayValue", datatype=Simple_DataType.INTEGER)
    issue = VariableIssue(
        kind=IssueKind.UI_ONLY,
        module_path=["BasePicture", "Panel"],
        variable=variable,
        role="localvariable",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "UI/display-only variables" in summary
    assert "DisplayValue" in summary


def test_variables_report_summary_includes_unknown_parameter_targets():
    issue = VariableIssue(
        kind=IssueKind.UNKNOWN_PARAMETER_TARGET,
        module_path=["BasePicture", "Child"],
        variable=None,
        role="unknown parameter mapping target 'MissingValue'",
    )

    summary = VariablesReport(basepicture_name="BasePicture", issues=[issue]).summary()

    assert "Unknown parameter mapping targets" in summary
    assert "BasePicture.Child :: unknown parameter mapping target 'MissingValue'" in summary


def test_variables_report_summary_lists_all_requested_categories_when_empty():
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[],
        visible_kinds=frozenset(ALL_VARIABLE_ANALYSIS_KINDS),
        include_empty_sections=True,
    )

    summary = report.summary()

    assert "Issues: 0" in summary
    assert "Sections:" in summary
    assert "  - Unused variables: 0" in summary
    assert "Unused variables" in summary
    assert "Unused fields in datatypes" in summary
    assert "Read-only but not Const variables" in summary
    assert "UI/display-only variables" in summary
    assert "Procedure status handling" in summary
    assert "Written but never read variables" in summary
    assert "Global scope minimization candidates" in summary
    assert "Hidden global coupling" in summary
    assert "Unknown parameter mapping targets" in summary
    assert "String mapping type mismatches" in summary
    assert "Duplicated complex datatypes (should be RECORD)" in summary
    assert "Min/Max mapping name mismatches" in summary
    assert "Magic numbers in code" in summary
    assert "Name collisions" in summary
    assert "Reset contamination (missing reset writes)" in summary
    assert "Implicit latching (missing matching False writes)" in summary
    assert summary.count("      none") == len(ALL_VARIABLE_ANALYSIS_KINDS)


def test_variables_report_summary_keeps_filtered_empty_output_scoped():
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[],
        visible_kinds=frozenset({IssueKind.RESET_CONTAMINATION}),
        include_empty_sections=True,
    )

    summary = report.summary()

    assert "Issues: 0" in summary
    assert "Sections:" in summary
    assert "  - Reset contamination (missing reset writes): 0" in summary
    assert "Reset contamination (missing reset writes)" in summary
    assert "      none" in summary
    assert "Unused variables" not in summary


def test_sfc_parallel_write_race_detected_for_same_variable():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCParallel(
                branches=[
                    [
                        SFCStep(
                            kind="step",
                            name="Left",
                            code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("Output"), 1)]),
                        )
                    ],
                    [
                        SFCStep(
                            kind="step",
                            name="Right",
                            code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("Output"), 2)]),
                        )
                    ],
                ]
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_parallel_write_race"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["conflicts"] == ["Root.Output"]


def test_dataflow_flags_implicit_same_scan_state_read_in_sequence_step():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Drive",
                code=SFCCodeBlocks(
                    active=[
                        (const.KEY_ASSIGN, _state_ref("Flag", "new"), True),
                        (const.KEY_ASSIGN, _varref("Output"), _varref("Flag")),
                    ]
                ),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Flag", datatype=Simple_DataType.BOOLEAN, state=True),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_dataflow(bp)

    assert any(
        issue.kind == "dataflow.scan_cycle_implicit_new"
        and issue.data is not None
        and issue.data.get("symbol") == "Flag"
        for issue in report.issues
    )


def test_dataflow_flags_old_as_out_parameter_temporal_misuse():
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
                            [1.0, 2.0, 0.1, _state_ref("Flag", "old")],
                        )
                    ],
                )
            ]
        ),
    )

    report = analyze_dataflow(bp)

    assert any(
        issue.kind == "dataflow.scan_cycle_temporal_misuse"
        and issue.data is not None
        and issue.data.get("symbol") == "Flag:Old"
        and issue.data.get("operation") == "out parameter"
        for issue in report.issues
    )


def test_variables_analyzer_flags_ignored_procedure_status_output():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Destination", datatype=Simple_DataType.INTEGER),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [_varref("Source"), _varref("Destination"), _varref("Status")],
                        )
                    ],
                )
            ]
        ),
    )

    issues = VariablesAnalyzer(bp).run()

    status_issues = [issue for issue in issues if issue.kind is IssueKind.PROCEDURE_STATUS]
    assert len(status_issues) == 1
    assert status_issues[0].variable is not None
    assert status_issues[0].variable.name == "Status"
    assert "ignored" in (status_issues[0].role or "")
    assert not any(
        issue.kind in {IssueKind.NEVER_READ, IssueKind.WRITE_WITHOUT_EFFECT}
        and issue.variable is not None
        and issue.variable.name == "Status"
        for issue in issues
    )


def test_variables_analyzer_flags_dependency_mapped_status_that_only_reaches_ui():
    bridge = ModuleTypeInstance(
        header=_hdr("Bridge"),
        moduletype_name="StatusBridge",
        parametermappings=[
            ParameterMapping(
                target=_varref("OperationStatus"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("StatusSink"),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[_status_bridge_typedef()],
        localvariables=[Variable(name="StatusSink", datatype=Simple_DataType.INTEGER)],
        submodules=[bridge],
        moduledef=ModuleDef(graph_objects=[GraphObject(type="TextObject", properties={"text_vars": ["StatusSink"]})]),
    )

    issues = VariablesAnalyzer(bp).run()

    status_issues = [
        issue
        for issue in issues
        if issue.kind is IssueKind.PROCEDURE_STATUS
        and issue.variable is not None
        and issue.variable.name == "StatusSink"
    ]
    assert len(status_issues) == 1
    assert "UI" in (status_issues[0].role or "")


def test_variables_analyzer_flags_naming_to_behavior_mismatches():
    unit = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="StartCmd", datatype=Simple_DataType.BOOLEAN),
            Variable(name="CmdLatch", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="LocalLogic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("StartCmd"), True),
                        (const.KEY_ASSIGN, _varref("CmdLatch"), _varref("StartCmd")),
                    ],
                )
            ]
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="ValveStatus", datatype=Simple_DataType.INTEGER),
            Variable(name="HighAlarm", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Shutdown", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[unit],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("ValveStatus"), IntLiteral(1)),
                        (const.KEY_ASSIGN, _varref("Shutdown"), _varref("HighAlarm")),
                    ],
                )
            ]
        ),
        moduledef=None,
    )

    issues = VariablesAnalyzer(bp).run()

    naming_issues = [issue for issue in issues if issue.kind is IssueKind.NAMING_ROLE_MISMATCH]
    assert {
        (issue.variable.name, tuple(issue.module_path)) for issue in naming_issues if issue.variable is not None
    } == {
        ("StartCmd", ("Root", "Unit")),
        ("ValveStatus", ("Root",)),
        ("HighAlarm", ("Root",)),
    }
    roles_by_name = {issue.variable.name: (issue.role or "") for issue in naming_issues if issue.variable is not None}
    assert "internal state" in roles_by_name["StartCmd"]
    assert "written directly" in roles_by_name["ValveStatus"]
    assert "control input" in roles_by_name["HighAlarm"]


def test_variables_analyzer_ignores_safe_naming_role_counterexamples():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="StartCmd", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Destination", datatype=Simple_DataType.INTEGER),
            Variable(name="HighAlarm", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Output"), _varref("StartCmd")),
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [_varref("Source"), _varref("Destination"), _varref("Status")],
                        ),
                    ],
                )
            ]
        ),
        moduledef=ModuleDef(graph_objects=[GraphObject(type="TextObject", properties={"text_vars": ["HighAlarm"]})]),
    )

    issues = VariablesAnalyzer(bp).run()

    assert not any(issue.kind is IssueKind.NAMING_ROLE_MISMATCH for issue in issues)


def test_variables_analyzer_supports_configured_naming_role_prefixes():
    unit = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="CmdStart", datatype=Simple_DataType.BOOLEAN),
            Variable(name="StatusValve", datatype=Simple_DataType.INTEGER),
            Variable(name="Hold", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("CmdStart"), True),
                        (const.KEY_ASSIGN, _varref("Hold"), _varref("CmdStart")),
                        (const.KEY_ASSIGN, _varref("StatusValve"), IntLiteral(1)),
                    ],
                )
            ]
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[unit],
        modulecode=None,
        moduledef=None,
    )

    default_issues = VariablesAnalyzer(bp).run()
    configured_issues = VariablesAnalyzer(
        bp,
        config={
            "analysis": {
                "naming": {
                    "role_patterns": {
                        "command": {"prefixes": ["cmd"]},
                        "status": {"prefixes": ["status"]},
                    }
                }
            }
        },
    ).run()

    assert not any(issue.kind is IssueKind.NAMING_ROLE_MISMATCH for issue in default_issues)
    configured_names = {
        issue.variable.name
        for issue in configured_issues
        if issue.kind is IssueKind.NAMING_ROLE_MISMATCH and issue.variable is not None
    }
    assert configured_names == {"CmdStart", "StatusValve"}


def test_variables_analyzer_treats_dependency_mapped_status_as_handled_when_read_in_logic():
    bridge = ModuleTypeInstance(
        header=_hdr("Bridge"),
        moduletype_name="StatusBridge",
        parametermappings=[
            ParameterMapping(
                target=_varref("OperationStatus"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("StatusSink"),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[_status_bridge_typedef()],
        localvariables=[
            Variable(name="StatusSink", datatype=Simple_DataType.INTEGER),
            Variable(name="Handled", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[bridge],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Handled"), _varref("StatusSink"))],
                )
            ]
        ),
    )

    issues = VariablesAnalyzer(bp).run()

    assert not any(
        issue.variable is not None
        and issue.variable.name == "StatusSink"
        and issue.kind in {IssueKind.PROCEDURE_STATUS, IssueKind.WRITE_WITHOUT_EFFECT, IssueKind.NEVER_READ}
        for issue in issues
    )


def test_dataflow_flags_contradictory_branch_condition_in_analyzer_suite():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Flag", datatype=Simple_DataType.BOOLEAN),
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
                            const.GRAMMAR_VALUE_IF,
                            [
                                (
                                    (
                                        const.GRAMMAR_VALUE_AND,
                                        [
                                            _varref("Flag"),
                                            (const.GRAMMAR_VALUE_NOT, _varref("Flag")),
                                        ],
                                    ),
                                    [
                                        (
                                            const.KEY_ASSIGN,
                                            _varref("Output"),
                                            True,
                                        )
                                    ],
                                )
                            ],
                            [
                                (
                                    const.KEY_ASSIGN,
                                    _varref("Output"),
                                    False,
                                )
                            ],
                        )
                    ],
                )
            ]
        ),
    )

    report = analyze_dataflow(bp)

    assert "dataflow.condition_always_false" in _issue_kinds(report)
    assert "dataflow.unreachable_branch" in _issue_kinds(report)


def test_dataflow_flags_impossible_inferred_compare_condition_in_analyzer_suite():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
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
                            const.GRAMMAR_VALUE_IF,
                            [
                                (
                                    (
                                        const.GRAMMAR_VALUE_AND,
                                        [
                                            (
                                                const.KEY_COMPARE,
                                                _varref("Counter"),
                                                [("==", 1)],
                                            ),
                                            (
                                                const.KEY_COMPARE,
                                                _varref("Counter"),
                                                [("==", 2)],
                                            ),
                                        ],
                                    ),
                                    [
                                        (
                                            const.KEY_ASSIGN,
                                            _varref("Output"),
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

    report = analyze_dataflow(bp)

    impossible_conditions = [
        issue
        for issue in report.issues
        if issue.kind == "dataflow.condition_always_false"
        and issue.data is not None
        and "Counter == 1" in str(issue.data.get("condition"))
        and "Counter == 2" in str(issue.data.get("condition"))
    ]

    assert impossible_conditions
    assert "dataflow.unreachable_branch" in _issue_kinds(report)


def test_sfc_parallel_write_race_detected_for_record_field_overlap():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCParallel(
                branches=[
                    [
                        SFCStep(
                            kind="step",
                            name="Left",
                            code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("Rec"), 1)]),
                        )
                    ],
                    [
                        SFCStep(
                            kind="step",
                            name="Right",
                            code=SFCCodeBlocks(active=[(const.KEY_ASSIGN, _varref("Rec.Field"), 2)]),
                        )
                    ],
                ]
            )
        ],
    )
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
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
        moduledef=None,
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_parallel_write_race"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["conflicts"] == ["Root.Rec"]


def test_sfc_transition_logic_detects_always_true_guard():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCTransition(
                name="AlwaysOpen",
                condition=(
                    const.GRAMMAR_VALUE_OR,
                    [_varref("Permit"), (const.GRAMMAR_VALUE_NOT, _varref("Permit"))],
                ),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Permit", datatype=Simple_DataType.BOOLEAN)],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_transition_always_true"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["transition_name"] == "AlwaysOpen"


def test_sfc_transition_logic_detects_always_false_guard():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCTransition(
                name="NeverOpen",
                condition=(
                    const.GRAMMAR_VALUE_AND,
                    [_varref("Permit"), (const.GRAMMAR_VALUE_NOT, _varref("Permit"))],
                ),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Permit", datatype=Simple_DataType.BOOLEAN)],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_transition_always_false"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["transition_name"] == "NeverOpen"


def test_sfc_transition_logic_detects_duplicate_guards_after_normalization():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCTransition(
                name="OpenPrimary",
                condition=(const.GRAMMAR_VALUE_AND, [_varref("Permit"), _varref("Ready")]),
            ),
            SFCTransition(
                name="OpenBackup",
                condition=(const.GRAMMAR_VALUE_AND, [_varref("Ready"), _varref("Permit")]),
            ),
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Permit", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Ready", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(sequences=[sequence], equations=[]),
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_duplicate_transition_guard"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["transition_names"] == ["OpenPrimary", "OpenBackup"]


def test_version_drift_detects_small_code_delta_between_same_named_modules():
    variant_a = SingleModule(
        header=_hdr("Mixer"),
        datecode=100,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Mixer"),
        datecode=200,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 2)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    cast(Any, variant_a).origin_file = "Root.s"
    cast(Any, variant_b).origin_file = "Root.s"
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[variant_a, variant_b],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_version_drift(bp)

    issues = [issue for issue in report.issues if issue.kind == "module.version_drift"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["module_name"] == "Mixer"
    assert issues[0].data["unique_variants"] == 2
    assert "code" in issues[0].data["material_differences"]
    assert "modified_equations" in issues[0].data["material_differences"]["code"]
    assert "Logic" in issues[0].data["material_differences"]["code"]["modified_equations"]
    assert issues[0].data["material_differences"]["code"]["modified_equations"]["Logic"]
    assert any("Equation 'Logic' changed" in note for note in issues[0].data["upgrade_notes"])


def test_version_drift_records_modified_variable_shape_diffs():
    variant_a = SingleModule(
        header=_hdr("Mixer"),
        datecode=100,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Mixer"),
        datecode=200,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.REAL)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    cast(Any, variant_a).origin_file = "Root.s"
    cast(Any, variant_b).origin_file = "Root.s"
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[variant_a, variant_b],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_version_drift(bp)

    issues = [issue for issue in report.issues if issue.kind == "module.version_drift"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert "localvariables" in issues[0].data["material_differences"]
    assert "Output" in issues[0].data["material_differences"]["localvariables"]["modified"]
    assert any(
        detail["path"] == "datatype"
        for detail in issues[0].data["material_differences"]["localvariables"]["modified"]["Output"]
    )
    assert any("Local variable 'Output' changed" in note for note in issues[0].data["upgrade_notes"])


def test_version_drift_ignores_datecode_only_differences():
    variant_a = SingleModule(
        header=_hdr("Mixer"),
        datecode=100,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Mixer"),
        datecode=200,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    cast(Any, variant_a).origin_file = "Root.s"
    cast(Any, variant_b).origin_file = "Root.s"
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[variant_a, variant_b],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_version_drift(bp)

    assert report.issues == []


def test_version_drift_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "version-drift" in specs
    assert specs["version-drift"].enabled is True


def test_initial_value_validation_flags_recipe_parameter_without_value_default():
    recipe_parameter = ModuleTypeDef(
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
        datatype_defs=[],
        moduletype_defs=[recipe_parameter],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("RecipeSP"),
                moduletype_name="RecParReal",
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_initial_values(bp)

    issues = [issue for issue in report.issues if issue.kind == "initial-values.missing_required_default"]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "RecipeSP"]
    assert issues[0].data == {
        "parameter_category": "recipe",
        "instance": "RecipeSP",
        "moduletype": "RecParReal",
        "moduletype_label": "RecParReal",
        "required_parameters": ["Value"],
        "parameter_statuses": {"Value": "not_configured"},
    }


def test_initial_value_validation_accepts_engineering_parameter_mapped_from_initialized_variable():
    engineering_parameter = ModuleTypeDef(
        name="EngParReal",
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
        datatype_defs=[],
        moduletype_defs=[engineering_parameter],
        localvariables=[Variable(name="ConfiguredLimit", datatype=Simple_DataType.REAL, init_value=42.5)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("EngineeringLimit"),
                moduletype_name="EngParReal",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Value"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("ConfiguredLimit"),
                        source_literal=None,
                    ),
                    ParameterMapping(
                        target=_varref("MinValue"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal=0.0,
                    ),
                    ParameterMapping(
                        target=_varref("MaxValue"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal=100.0,
                    ),
                ],
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_initial_values(bp)

    assert report.issues == []


def test_initial_value_validation_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "initial-values" in specs
    assert specs["initial-values"].enabled is True


def test_naming_consistency_flags_inconsistent_variable_names():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="FlowRate", datatype=Simple_DataType.INTEGER)],
        submodules=[
            SingleModule(
                header=_hdr("MixerUnit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="PumpSpeed", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            SingleModule(
                header=_hdr("HoldingUnit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="tank_level", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_naming_consistency(bp)

    issues = [
        issue
        for issue in report.issues
        if issue.kind == "naming.inconsistent_style"
        and issue.data is not None
        and issue.data.get("symbol_kind") == "variable"
    ]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "HoldingUnit"]
    assert issues[0].data == {
        "symbol_kind": "variable",
        "name": "tank_level",
        "actual_style": "snake",
        "expected_style": "pascal",
    }


def test_naming_consistency_flags_inconsistent_module_names():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("MixerUnit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            FrameModule(
                header=_hdr("HoldingFrame"),
                submodules=[],
                moduledef=None,
                modulecode=None,
            ),
            SingleModule(
                header=_hdr("cooling_stage"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_naming_consistency(bp)

    issues = [
        issue
        for issue in report.issues
        if issue.kind == "naming.inconsistent_style"
        and issue.data is not None
        and issue.data.get("symbol_kind") == "module"
    ]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "cooling_stage"]
    assert issues[0].data == {
        "symbol_kind": "module",
        "name": "cooling_stage",
        "actual_style": "snake",
        "expected_style": "pascal",
    }


def test_naming_consistency_flags_inconsistent_instance_names():
    typedef = ModuleTypeDef(
        name="ValveType",
        moduleparameters=[],
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
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("ValveFeed"),
                moduletype_name="ValveType",
                parametermappings=[],
            ),
            ModuleTypeInstance(
                header=_hdr("ValveDrain"),
                moduletype_name="ValveType",
                parametermappings=[],
            ),
            ModuleTypeInstance(
                header=_hdr("valve_return"),
                moduletype_name="ValveType",
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_naming_consistency(bp)

    issues = [
        issue
        for issue in report.issues
        if issue.kind == "naming.inconsistent_style"
        and issue.data is not None
        and issue.data.get("symbol_kind") == "instance"
    ]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "valve_return"]
    assert issues[0].data == {
        "symbol_kind": "instance",
        "name": "valve_return",
        "actual_style": "snake",
        "expected_style": "pascal",
    }


def test_naming_consistency_honors_case_insensitive_allowed_exceptions():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="FlowRate", datatype=Simple_DataType.INTEGER),
            Variable(name="PumpSpeed", datatype=Simple_DataType.INTEGER),
            Variable(name="legacyTemp", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_naming_consistency(
        bp,
        rules=get_configured_naming_rules(
            {
                "analysis": {
                    "naming": {
                        "variables": {
                            "style": "pascal",
                            "allow": ["LEGACYTEMP"],
                        }
                    }
                }
            }
        ),
    )

    assert report.issues == []


def test_naming_consistency_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "naming-consistency" in specs
    assert specs["naming-consistency"].enabled is True


def test_alarm_integrity_detects_duplicate_tags_across_instances():
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

    report = analyze_alarm_integrity(bp)

    duplicate_tag_issues = [issue for issue in report.issues if issue.kind == "alarm.duplicate_tag"]
    assert len(duplicate_tag_issues) == 2
    assert all("Unit.Temp.High" in issue.message for issue in duplicate_tag_issues)


def test_alarm_integrity_detects_duplicate_conditions_across_instances():
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
        localvariables=[Variable(name="SharedCondition", datatype=Simple_DataType.BOOLEAN)],
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
                        source=_varref("SharedCondition"),
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
                        source_literal="Unit.Temp.Low",
                    ),
                    ParameterMapping(
                        target=_varref("Condition"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("SharedCondition"),
                        source_literal=None,
                    ),
                ],
            ),
        ],
        origin_file="Root.s",
    )

    report = analyze_alarm_integrity(bp)

    duplicate_condition_issues = [issue for issue in report.issues if issue.kind == "alarm.duplicate_condition"]
    assert len(duplicate_condition_issues) == 2
    assert all("SharedCondition" in issue.message for issue in duplicate_condition_issues)


def test_alarm_integrity_detects_conflicting_priorities_for_same_tag():
    detector = ModuleTypeDef(
        name="EventDetector1",
        moduleparameters=[
            Variable(name="Tag", datatype=Simple_DataType.TAGSTRING),
            Variable(name="Severity", datatype=Simple_DataType.INTEGER),
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
                        target=_varref("Severity"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal=1,
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
                        target=_varref("Severity"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source_literal=3,
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

    report = analyze_alarm_integrity(bp)

    conflicting_priority_issues = [issue for issue in report.issues if issue.kind == "alarm.conflicting_priority"]
    assert len(conflicting_priority_issues) == 2
    assert all("1" in issue.message and "3" in issue.message for issue in conflicting_priority_issues)


def test_alarm_integrity_detects_never_cleared_alarm_variable():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="AlarmTrip", datatype=Simple_DataType.BOOLEAN)],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "SetBooleanValue",
                            [_varref("AlarmTrip"), True],
                        )
                    ],
                )
            ]
        ),
    )

    report = analyze_alarm_integrity(bp)

    never_cleared_issues = [issue for issue in report.issues if issue.kind == "alarm.never_cleared"]
    assert len(never_cleared_issues) == 1
    assert "AlarmTrip" in never_cleared_issues[0].message


def test_alarm_integrity_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "alarm-integrity" in specs
    assert specs["alarm-integrity"].enabled is True


def test_safety_paths_trace_emergency_signal_across_moduletype_mapping():
    guard_type = ModuleTypeDef(
        name="GuardType",
        moduleparameters=[
            Variable(name="InSignal", datatype=Simple_DataType.BOOLEAN),
        ],
        localvariables=[
            Variable(name="Seen", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="GuardEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Seen"),
                            _varref("InSignal"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="EmergencyShutdown", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        moduletype_defs=[guard_type],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Guard"),
                moduletype_name="GuardType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("InSignal"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("EmergencyShutdown"),
                        source_literal=None,
                    )
                ],
            )
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
                            _varref("EmergencyShutdown"),
                            True,
                        )
                    ],
                )
            ]
        ),
        origin_file="Root.s",
    )

    report = analyze_safety_paths(bp)

    assert report.issues == []
    assert len(report.traces) == 1
    assert report.traces[0].canonical_path == "Root.EmergencyShutdown"
    assert report.traces[0].writer_module_paths == (("Root",),)
    assert report.traces[0].reader_module_paths == (("Root", "Guard"),)
    assert report.traces[0].spans_multiple_modules is True


def test_safety_paths_reports_unconsumed_shutdown_signal():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="EmergencyShutdown", datatype=Simple_DataType.BOOLEAN, init_value=False),
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
                            _varref("EmergencyShutdown"),
                            True,
                        )
                    ],
                )
            ]
        ),
    )

    report = analyze_safety_paths(bp)

    assert len(report.traces) == 1
    assert len(report.issues) == 1
    assert report.issues[0].kind == "safety-path.unconsumed_signal"
    assert report.issues[0].data is not None
    assert report.issues[0].data["canonical_path"] == "Root.EmergencyShutdown"


def test_taint_paths_trace_operator_input_to_shutdown_sink_across_moduletype_mapping():
    guard_type = ModuleTypeDef(
        name="GuardType",
        moduleparameters=[
            Variable(name="InCommand", datatype=Simple_DataType.BOOLEAN),
        ],
        localvariables=[
            Variable(name="EmergencyShutdown", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="GuardEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("EmergencyShutdown"),
                            _varref("InCommand"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="OperatorCommand", datatype=Simple_DataType.BOOLEAN, init_value=False),
        ],
        moduletype_defs=[guard_type],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Guard"),
                moduletype_name="GuardType",
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
                            _varref("OperatorCommand"),
                            True,
                        )
                    ],
                )
            ]
        ),
        origin_file="Root.s",
    )

    report = analyze_taint_paths(bp)

    assert len(report.traces) == 1
    assert len(report.issues) == 1
    assert report.traces[0].source_kind == "operator"
    assert report.traces[0].source_canonical_path == "Root.OperatorCommand"
    assert report.traces[0].sink_canonical_path == "Root.Guard.EmergencyShutdown"
    assert report.traces[0].path == (
        "Root.OperatorCommand",
        "Root.Guard.InCommand",
        "Root.Guard.EmergencyShutdown",
    )
    assert report.traces[0].spans_multiple_modules is True
    assert report.issues[0].kind == "taint-path.external_input_to_critical_sink"
    assert report.issues[0].data is not None
    assert report.issues[0].data["source_kind"] == "operator"


def test_safety_paths_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "safety-paths" in specs
    assert specs["safety-paths"].enabled is True


def test_taint_paths_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "taint-paths" in specs
    assert specs["taint-paths"].enabled is True
