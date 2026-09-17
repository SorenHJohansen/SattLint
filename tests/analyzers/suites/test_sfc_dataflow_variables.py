from sattline_parser.models.expressions import Assignment, FuncCall, FuncCallStmt

from tests.helpers.analyzers_suites_support import *


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
                            code=SFCCodeBlocks(active=[Assignment(target=_varref("Output"), value=1)]),
                        )
                    ],
                    [
                        SFCStep(
                            kind="step",
                            name="Right",
                            code=SFCCodeBlocks(active=[Assignment(target=_varref("Output"), value=2)]),
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

    report = analyze_same_cycle(bp)

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
                        Assignment(target=_state_ref("Flag", "new"), value=True),
                        Assignment(target=_varref("Output"), value=_varref("Flag")),
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
                        FuncCallStmt(
                            call=FuncCall(
                                name="CopyVariable", args=(_varref("Source"), _varref("Destination"), _varref("Status"))
                            )
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
                    code=[Assignment(target=_varref("Handled"), value=_varref("StatusSink"))],
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
