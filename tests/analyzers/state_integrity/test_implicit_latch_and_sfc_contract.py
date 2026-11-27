from sattline_parser.models.ast_model import (
    BasePicture,
    CodeItem,
    DataType,
    Equation,
    FrameModule,
    ModuleCode,
    ScalarDatatype,
    Sequence,
    SFCCodeBlocks,
    SFCStep,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import Assignment, IfStmt

from sattlint.analyzers.variables import (
    IssueKind,
    VariablesAnalyzer,
)
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)
from tests.helpers.variable_test_support import (
    varref as _varref,
)


def test_implicit_latch_detected_when_if_branch_sets_true_without_else_clear():
    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Start", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="AlarmLatched", datatype=ScalarDatatype.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        IfStmt(
                            branches=((_varref("Start"), (Assignment(target=_varref("AlarmLatched"), value=True),)),),
                            else_block=None,
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
            Variable(name="Start", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="AlarmLatched", datatype=ScalarDatatype.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        IfStmt(
                            branches=((_varref("Start"), (Assignment(target=_varref("AlarmLatched"), value=True),)),),
                            else_block=(Assignment(target=_varref("AlarmLatched"), value=False),),
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
            Variable(name="Start", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="AlarmLatched", datatype=ScalarDatatype.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        IfStmt(
                            branches=((_varref("Start"), (Assignment(target=_varref("AlarmLatched"), value=True),)),),
                            else_block=None,
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
                Variable(name="Start", datatype=ScalarDatatype.BOOLEAN),
                Variable(name="AlarmLatched", datatype=ScalarDatatype.BOOLEAN),
            ],
            submodules=[],
            modulecode=ModuleCode(
                equationblocks=[
                    Equation(
                        name="Main",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[
                            IfStmt(
                                branches=(
                                    (_varref("Start"), (Assignment(target=_varref("AlarmLatched"), value=True),)),
                                ),
                                else_block=None,
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
            Variable(name="Start", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="AlarmLatched", datatype=ScalarDatatype.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        IfStmt(
                            branches=((_varref("Start"), (Assignment(target=_varref("AlarmLatched"), value=True),)),),
                            else_block=None,
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
                        Assignment(target=_varref("StepFlag"), value=True),  # pyright: ignore[reportArgumentType]
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
        localvariables=[Variable(name="StepFlag", datatype=ScalarDatatype.BOOLEAN)],
        submodules=[],
        modulecode=ModuleCode(sequences=[seq], equationblocks=[]),
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
    assert issues[0].site == "SQ:OperationSequence > STEP:Run"


def _latch_issues_for_code(code: list[CodeItem], variables: list[Variable]) -> list[object]:
    module = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=variables,
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[Equation(name="Main", position=(0.0, 0.0), size=(1.0, 1.0), code=code)],
            sequences=[],
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[module],
        modulecode=None,
        moduledef=None,
    )
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()
    return [issue for issue in analyzer.issues if issue.kind is IssueKind.IMPLICIT_LATCH]


def test_implicit_latch_not_reported_when_prior_assignment_clears() -> None:
    variables = [
        Variable(name="Start", datatype=ScalarDatatype.BOOLEAN),
        Variable(name="Running", datatype=ScalarDatatype.BOOLEAN),
    ]
    issues = _latch_issues_for_code(
        [
            Assignment(target=_varref("Running"), value=False),
            IfStmt(
                branches=((_varref("Start"), (Assignment(target=_varref("Running"), value=True),)),),
                else_block=None,
            ),
        ],
        variables,
    )

    assert issues == []


def test_implicit_latch_not_reported_when_later_assignment_clears() -> None:
    variables = [
        Variable(name="Start", datatype=ScalarDatatype.BOOLEAN),
        Variable(name="Running", datatype=ScalarDatatype.BOOLEAN),
    ]
    issues = _latch_issues_for_code(
        [
            IfStmt(
                branches=((_varref("Start"), (Assignment(target=_varref("Running"), value=True),)),),
                else_block=None,
            ),
            Assignment(target=_varref("Running"), value=False),
        ],
        variables,
    )

    assert issues == []


def test_implicit_latch_not_reported_when_branch_ends_false() -> None:
    variables = [
        Variable(name="Start", datatype=ScalarDatatype.BOOLEAN),
        Variable(name="Running", datatype=ScalarDatatype.BOOLEAN),
    ]
    issues = _latch_issues_for_code(
        [
            IfStmt(
                branches=(
                    (
                        _varref("Start"),
                        (
                            Assignment(target=_varref("Running"), value=True),
                            Assignment(target=_varref("Running"), value=False),
                        ),
                    ),
                ),
                else_block=None,
            )
        ],
        variables,
    )

    assert issues == []


def test_implicit_latch_not_reported_when_sequence_init_clears() -> None:
    variables = [
        Variable(name="Done", datatype=ScalarDatatype.BOOLEAN),
    ]
    module = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=variables,
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[],
            sequences=[
                Sequence(
                    name="MainSeq",
                    type="sequence",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        SFCStep(
                            kind="init",
                            name="Init",
                            code=SFCCodeBlocks(enter=[Assignment(target=_varref("Done"), value=False)]),
                        ),
                        SFCStep(
                            kind="step",
                            name="Finish",
                            code=SFCCodeBlocks(enter=[Assignment(target=_varref("Done"), value=True)]),
                        ),
                    ],
                )
            ],
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[module],
        modulecode=None,
        moduledef=None,
    )
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not [issue for issue in analyzer.issues if issue.kind is IssueKind.IMPLICIT_LATCH]


def test_implicit_latch_reported_for_record_field() -> None:
    datatype = DataType(
        name="Flags",
        description=None,
        datecode=None,
        var_list=[Variable(name="Active", datatype=ScalarDatatype.BOOLEAN)],
    )
    variables = [
        Variable(name="Start", datatype=ScalarDatatype.BOOLEAN),
        Variable(name="State", datatype="Flags"),
    ]
    module = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=variables,
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        IfStmt(
                            branches=(
                                (
                                    _varref("Start"),
                                    (Assignment(target=_varref("State.Active"), value=True),),
                                ),
                            ),
                            else_block=None,
                        )
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[datatype],
        moduletype_defs=[],
        localvariables=[],
        submodules=[module],
        modulecode=None,
        moduledef=None,
    )
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.IMPLICIT_LATCH]
    assert len(issues) == 1
    assert issues[0].field_path == "Active"
