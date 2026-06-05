# ruff: noqa: F403, F405
from ._analyzers_suites_test_support import *


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
