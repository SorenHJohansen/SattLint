# ruff: noqa: F403, F405
from ._analyzers_state_test_support import *


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
    assert ("BasePicture.TypeDef:Unit :: Value (integer) | name collision with parameter 'Value'") in summary


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


def test_variable_issue_str_formats_datatype_literal_and_role_only_variants():
    datatype_issue = VariableIssue(
        kind=IssueKind.UNUSED_DATATYPE_FIELD,
        module_path=["BasePicture", "UnitA"],
        variable=None,
        datatype_name="Payload",
        field_path="Value",
    )
    literal_issue = VariableIssue(
        kind=IssueKind.MAGIC_NUMBER,
        module_path=["BasePicture", "UnitA"],
        variable=None,
        literal_value=42,
        literal_span=SourceSpan(line=9, column=4),
        site="EquationBlock",
    )
    role_issue = VariableIssue(
        kind=IssueKind.UNKNOWN_PARAMETER_TARGET,
        module_path=["BasePicture", "Child"],
        variable=None,
        role="missing target",
    )
    variable_issue = VariableIssue(
        kind=IssueKind.IMPLICIT_LATCH,
        module_path=["BasePicture", "Step"],
        variable=Variable(name="Flag", datatype=Simple_DataType.BOOLEAN),
        role="localvariable",
        field_path="State",
        sequence_name="SeqA",
        reset_variable="ResetCmd",
    )
    empty_issue = VariableIssue(
        kind=IssueKind.UNUSED,
        module_path=["BasePicture"],
        variable=None,
    )

    assert str(datatype_issue) == "[BasePicture.UnitA] datatype 'Payload'.Value"
    assert str(literal_issue) == "[BasePicture.UnitA] magic number 42"
    assert str(role_issue) == "[BasePicture.Child] missing target"
    assert "'Flag'.State (boolean)" in str(variable_issue)
    assert "seq='SeqA'" in str(variable_issue)
    assert "reset='ResetCmd'" in str(variable_issue)
    assert str(empty_issue) == "[BasePicture]"
