from sattline_parser.models.expressions import Assignment, VarRef

from tests.helpers.analyzers_state_support import *


def test_write_without_effect_detected_for_internal_value_chain():
    child = SingleModule(
        header=_hdr("Worker"),
        moduledefs=[],
        moduleparameters=[],
        localvariables=[
            Variable(name="Stage1", datatype=Simple_DataType.INTEGER),
            Variable(name="Stage2", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="Main",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            Assignment(target=_varref("Stage1"), value=1),
                            Assignment(target=_varref("Stage2"), value=_varref("Stage1")),
                        ],
                    )
                ],
                sequences=[],
            )
        ],
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        submodules=[child],
        modulecodes=[],
        moduledefs=[],
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    write_without_effect = [issue for issue in analyzer.issues if issue.kind is IssueKind.WRITE_WITHOUT_EFFECT]
    assert [issue.variable.name for issue in write_without_effect if issue.variable is not None] == ["Stage1"]
    assert any(
        issue.kind is IssueKind.NEVER_READ and issue.variable is not None and issue.variable.name == "Stage2"
        for issue in analyzer.issues
    )


def test_write_without_effect_is_not_reported_for_module_parameters() -> None:
    child = SingleModule(
        header=_hdr("Worker"),
        moduledefs=[],
        moduleparameters=[Variable(name="OutParam", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Sink", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="Main",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            Assignment(target=_varref("OutParam"), value=1),
                            Assignment(target=_varref("Sink"), value=_varref("OutParam")),
                        ],
                    )
                ],
                sequences=[],
            )
        ],
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        submodules=[child],
        modulecodes=[],
        moduledefs=[],
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not [issue for issue in analyzer.issues if issue.kind is IssueKind.WRITE_WITHOUT_EFFECT]


def test_write_without_effect_is_not_reported_for_typedef_module_parameters() -> None:
    moduletype = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[Variable(name="OutParam", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Sink", datatype=Simple_DataType.INTEGER)],
        moduledefs=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="Main",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            Assignment(target=_varref("OutParam"), value=1),
                            Assignment(target=_varref("Sink"), value=_varref("OutParam")),
                        ],
                    )
                ],
                sequences=[],
            )
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        submodules=[],
        moduletype_defs=[moduletype],
        modulecodes=[],
        moduledefs=[],
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not [issue for issue in analyzer.issues if issue.kind is IssueKind.WRITE_WITHOUT_EFFECT]


def test_write_without_effect_is_suppressed_for_mapped_output_path():
    out_target: VarRef = _varref("Out")
    final_output_source: VarRef = _varref("FinalOutput")

    child = SingleModule(
        header=_hdr("Worker"),
        moduledefs=[],
        moduleparameters=[Variable(name="Out", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Internal", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="Main",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            Assignment(target=_varref("Internal"), value=1),
                            Assignment(target=_varref("Out"), value=_varref("Internal")),
                        ],
                    )
                ],
                sequences=[],
            )
        ],
        parametermappings=[
            ParameterMapping(
                target=out_target,
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=final_output_source,
                source_literal=None,
            )
        ],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="FinalOutput", datatype=Simple_DataType.INTEGER)],
        submodules=[child],
        modulecodes=[],
        moduledefs=[],
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
        moduledefs=[],
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="WriteShared",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[Assignment(target=_varref("SharedValue"), value=1)],
                    )
                ],
                sequences=[],
            )
        ],
        parametermappings=[],
    )
    reader = SingleModule(
        header=_hdr("Reader"),
        moduledefs=[],
        moduleparameters=[],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="ReadShared",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[Assignment(target=_varref("Observed"), value=_varref("SharedValue"))],
                    )
                ],
                sequences=[],
            )
        ],
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[shared_value],
        submodules=[writer, reader],
        modulecodes=[],
        moduledefs=[],
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
    writer_out_target: VarRef = _varref("Out")
    writer_shared_source: VarRef = _varref("SharedValue")
    reader_in_target: VarRef = _varref("In")
    reader_shared_source: VarRef = _varref("SharedValue")

    writer = SingleModule(
        header=_hdr("Writer"),
        moduledefs=[],
        moduleparameters=[Variable(name="Out", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="Produce",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[Assignment(target=_varref("Out"), value=1)],
                    )
                ],
                sequences=[],
            )
        ],
        parametermappings=[
            ParameterMapping(
                target=writer_out_target,
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=writer_shared_source,
                source_literal=None,
            )
        ],
    )
    reader = SingleModule(
        header=_hdr("Reader"),
        moduledefs=[],
        moduleparameters=[Variable(name="In", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="Consume",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[Assignment(target=_varref("Observed"), value=_varref("In"))],
                    )
                ],
                sequences=[],
            )
        ],
        parametermappings=[
            ParameterMapping(
                target=reader_in_target,
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=reader_shared_source,
                source_literal=None,
            )
        ],
    )
    coordinator = SingleModule(
        header=_hdr("Coordinator"),
        moduledefs=[],
        moduleparameters=[],
        localvariables=[Variable(name="SharedValue", datatype=Simple_DataType.INTEGER)],
        submodules=[writer, reader],
        modulecodes=[],
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        submodules=[coordinator],
        modulecodes=[],
        moduledefs=[],
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(issue.kind is IssueKind.HIDDEN_GLOBAL_COUPLING for issue in analyzer.issues)


def test_global_scope_minimization_is_reported_for_root_global_confined_to_one_module_subtree():
    confined = Variable(name="ConfinedValue", datatype=Simple_DataType.INTEGER)

    worker = SingleModule(
        header=_hdr("Worker"),
        moduledefs=[],
        moduleparameters=[],
        localvariables=[Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[
            SingleModule(
                header=_hdr("Nested"),
                moduledefs=[],
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecodes=[
                    ModuleCode(
                        equationblocks=[
                            Equation(
                                name="WriteConfined",
                                position=(0.0, 0.0),
                                size=(1.0, 1.0),
                                code=[Assignment(target=_varref("ConfinedValue"), value=1)],
                            )
                        ],
                        sequences=[],
                    )
                ],
                parametermappings=[],
            )
        ],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="ReadConfined",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[Assignment(target=_varref("Observed"), value=_varref("ConfinedValue"))],
                    )
                ],
                sequences=[],
            )
        ],
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[confined],
        submodules=[worker],
        modulecodes=[],
        moduledefs=[],
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
        moduledefs=[],
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="WriteConfined",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[Assignment(target=_varref("ConfinedValue"), value=1)],
                    )
                ],
                sequences=[],
            )
        ],
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[confined, Variable(name="Observed", datatype=Simple_DataType.INTEGER)],
        submodules=[worker],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="ReadAtRoot",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[Assignment(target=_varref("Observed"), value=_varref("ConfinedValue"))],
                    )
                ],
                sequences=[],
            )
        ],
        moduledefs=[],
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.GLOBAL_SCOPE_MINIMIZATION and issue.variable is confined for issue in analyzer.issues
    )
