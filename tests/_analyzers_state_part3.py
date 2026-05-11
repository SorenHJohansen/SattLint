# ruff: noqa: F403, F405
from ._analyzers_state_test_support import *


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


def test_implicit_latch_detected_in_root_modulecode():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
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
                            [(_varref("Start"), [(const.KEY_ASSIGN, _varref("AlarmLatched"), True)])],
                            [],
                        )
                    ],
                )
            ]
        ),
        moduledef=None,
    )

    issues = VariablesAnalyzer(bp).run()

    latch_issues = [issue for issue in issues if issue.kind is IssueKind.IMPLICIT_LATCH]
    assert len(latch_issues) == 1
    assert latch_issues[0].module_path == ["Root"]
    assert latch_issues[0].site == "EQ:Main > IF"


def test_limit_to_module_path_restricts_state_integrity_checks_to_matching_subtree():
    def _latching_module(name: str) -> SingleModule:
        return SingleModule(
            header=_hdr(name),
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
                                [(_varref("Start"), [(const.KEY_ASSIGN, _varref("AlarmLatched"), True)])],
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
        submodules=[_latching_module("UnitA"), _latching_module("UnitB")],
        modulecode=None,
        moduledef=None,
    )

    issues = VariablesAnalyzer(bp).run(limit_to_module_path=["Root", "UnitA"])

    latch_paths = [issue.module_path for issue in issues if issue.kind is IssueKind.IMPLICIT_LATCH]
    assert latch_paths == [["Root", "UnitA"]]


def test_frame_module_children_are_included_in_state_integrity_checks():
    child = SingleModule(
        header=_hdr("Nested"),
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
                            [(_varref("Start"), [(const.KEY_ASSIGN, _varref("AlarmLatched"), True)])],
                            [],
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
    )
    frame = FrameModule(
        header=_hdr("Frame"),
        datecode=None,
        submodules=[child],
        modulecode=None,
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[frame],
        modulecode=None,
        moduledef=None,
    )

    issues = VariablesAnalyzer(bp).run()

    latch_issues = [issue for issue in issues if issue.kind is IssueKind.IMPLICIT_LATCH]
    assert len(latch_issues) == 1
    assert latch_issues[0].module_path == ["Root", "Frame", "Nested"]


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
