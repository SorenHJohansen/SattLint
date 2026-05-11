# ruff: noqa: F403, F405
from ._analyzers_state_test_support import *


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
