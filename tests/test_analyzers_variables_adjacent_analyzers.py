"""Adjacent analyzer scenarios re-exported by tests.test_analyzers_variables."""

from __future__ import annotations

from pathlib import Path

from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    IntLiteral,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCCodeBlocks,
    SFCStep,
    SFCTransition,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.cyclomatic_complexity import analyze_cyclomatic_complexity
from sattlint.analyzers.loop_output_refactor import analyze_loop_output_refactor
from sattlint.analyzers.mms import analyze_mms_interface_variables
from sattlint.analyzers.parameter_drift import analyze_parameter_drift
from sattlint.analyzers.scan_loop_resource_usage import analyze_scan_loop_resource_usage
from sattlint.reporting.icf_report import ICFEntry
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)
from tests.helpers.variable_test_support import (
    issue_kinds as _issue_kinds,
)
from tests.helpers.variable_test_support import (
    varref as _varref,
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


def test_mms_interface_collects_nested_typedef_mappings_and_write_locations():
    wrapper = ModuleTypeDef(
        name="WriterWrapper",
        moduleparameters=[Variable(name="MappedOut", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("SendToOpc"),
                moduletype_name="MMSWriteVar",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("WriteData"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("MappedOut"),
                        source_literal=None,
                    ),
                    ParameterMapping(
                        target=_varref("RemoteVarName"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source=None,
                        source_literal="Plant.Result",
                    ),
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="Program.s",
    )
    unit = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="ExportValue", datatype=Simple_DataType.INTEGER)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Wrapper"),
                moduletype_name="WriterWrapper",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("MappedOut"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("ExportValue"),
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
                    code=[(const.KEY_ASSIGN, _varref("ExportValue"), IntLiteral(1))],
                )
            ]
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[wrapper],
        localvariables=[],
        submodules=[unit],
        modulecode=None,
        moduledef=None,
        origin_file="Program.s",
    )

    report = analyze_mms_interface_variables(bp)

    assert report.issues == []
    assert len(report.hits) == 1
    hit = report.hits[0]
    assert hit.module_path == ["Program", "Unit", "Wrapper", "SendToOpc"]
    assert hit.source_variable == "ExportValue"
    assert hit.write_note is None
    assert any(field_path == "" for field_path, _locations in hit.write_fields)
    assert any(
        path == ("Program", "Unit") and count == 1
        for _field_path, locations in hit.write_fields
        for path, count in locations
    )


def test_mms_interface_uses_moduletype_default_tags_for_duplicate_and_dead_tag_checks():
    mms_write_type = ModuleTypeDef(
        name="MMSWriteVar",
        moduleparameters=[Variable(name="Tag", datatype=Simple_DataType.STRING, init_value="Plant.Default.Tag")],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    unit = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="FirstValue", datatype=Simple_DataType.INTEGER),
            Variable(name="SecondValue", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("SenderA"),
                moduletype_name="MMSWriteVar",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("WriteData"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("FirstValue"),
                        source_literal=None,
                    )
                ],
            ),
            ModuleTypeInstance(
                header=_hdr("SenderB"),
                moduletype_name="MMSWriteVar",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("WriteData"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("SecondValue"),
                        source_literal=None,
                    )
                ],
            ),
        ],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[mms_write_type],
        localvariables=[],
        submodules=[unit],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_mms_interface_variables(bp)

    duplicate_issues = [issue for issue in report.issues if issue.kind == "mms.duplicate_tag"]
    dead_tag_issues = [issue for issue in report.issues if issue.kind == "mms.dead_tag"]

    assert len(report.hits) == 2
    assert len(duplicate_issues) == 1
    assert duplicate_issues[0].data is not None
    assert duplicate_issues[0].data["tag"] == "Plant.Default.Tag"
    assert len(dead_tag_issues) == 2
    assert all("Plant.Default.Tag" in issue.message for issue in dead_tag_issues)


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
        moduleparameters=[Variable(name="Timeout", datatype=Simple_DataType.INTEGER, init_value=10)],
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
        moduleparameters=[Variable(name="Timeout", datatype=Simple_DataType.INTEGER, init_value=10)],
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
            [(_varref(f"Cond{index}"), [(const.KEY_ASSIGN, _varref("Output"), IntLiteral(index))])],
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
