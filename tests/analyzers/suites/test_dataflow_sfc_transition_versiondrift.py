from sattline_parser.models.ast_model import (
    Assignment,
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ScalarDatatype,
    Sequence,
    SFCAlternative,
    SFCCodeBlocks,
    SFCParallel,
    SFCStep,
    SFCTransition,
    Variable,
)
from sattline_parser.models.expressions import (
    BoolOp,
    Compare,
    IfStmt,
    NotOp,
)

from sattlint.analyzers.dataflow import analyze_dataflow
from sattlint.analyzers.same_cycle import analyze_same_cycle
from sattlint.analyzers.sfc import analyze_sfc
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)
from tests.helpers.variable_test_support import (
    issue_kinds as _issue_kinds,
)
from tests.helpers.variable_test_support import (
    varref as _varref,
)


def test_dataflow_flags_contradictory_branch_condition_in_analyzer_suite():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Flag", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="Output", datatype=ScalarDatatype.BOOLEAN),
        ],
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
                                    BoolOp(op="AND", operands=(_varref("Flag"), NotOp(operand=_varref("Flag")))),
                                    (Assignment(target=_varref("Output"), value=True),),
                                ),
                            ),
                            else_block=(Assignment(target=_varref("Output"), value=False),),
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
            Variable(name="Counter", datatype=ScalarDatatype.INTEGER),
            Variable(name="Output", datatype=ScalarDatatype.BOOLEAN),
        ],
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
                                    BoolOp(
                                        op="AND",
                                        operands=(
                                            Compare(left=_varref("Counter"), op="==", right=1),
                                            Compare(left=_varref("Counter"), op="==", right=2),
                                        ),
                                    ),
                                    (Assignment(target=_varref("Output"), value=True),),
                                ),
                            ),
                            else_block=None,
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
                            code=SFCCodeBlocks(active=[Assignment(target=_varref("Rec"), value=1)]),
                        )
                    ],
                    [
                        SFCStep(
                            kind="step",
                            name="Right",
                            code=SFCCodeBlocks(active=[Assignment(target=_varref("Rec.Field"), value=2)]),
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
                var_list=[Variable(name="Field", datatype=ScalarDatatype.INTEGER)],
            )
        ],
        localvariables=[Variable(name="Rec", datatype="RecType")],
        modulecode=ModuleCode(sequences=[sequence], equationblocks=[]),
        moduledef=None,
    )

    report = analyze_same_cycle(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_parallel_write_race"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["conflicts"] == ["Root.Rec"]


def test_dataflow_detects_always_true_transition_guard():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCTransition(
                name="AlwaysOpen",
                condition=BoolOp(op="OR", operands=(_varref("Permit"), NotOp(operand=_varref("Permit")))),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Permit", datatype=ScalarDatatype.BOOLEAN)],
        modulecode=ModuleCode(sequences=[sequence], equationblocks=[]),
    )

    report = analyze_dataflow(bp)

    issues = [issue for issue in report.issues if issue.kind == "dataflow.condition_always_true"]
    assert len(issues) == 1


def test_dataflow_detects_always_false_transition_guard():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCTransition(
                name="NeverOpen",
                condition=BoolOp(op="AND", operands=(_varref("Permit"), NotOp(operand=_varref("Permit")))),
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Permit", datatype=ScalarDatatype.BOOLEAN)],
        modulecode=ModuleCode(sequences=[sequence], equationblocks=[]),
    )

    report = analyze_dataflow(bp)

    issues = [issue for issue in report.issues if issue.kind == "dataflow.condition_always_false"]
    assert len(issues) == 1


def test_sfc_transition_logic_detects_duplicate_guards_after_normalization():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCAlternative(
                branches=[
                    [
                        SFCTransition(
                            name="OpenPrimary",
                            condition=BoolOp(op="AND", operands=(_varref("Permit"), _varref("Ready"))),
                        )
                    ],
                    [
                        SFCTransition(
                            name="OpenBackup",
                            condition=BoolOp(op="AND", operands=(_varref("Ready"), _varref("Permit"))),
                        )
                    ],
                ]
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Permit", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="Ready", datatype=ScalarDatatype.BOOLEAN),
        ],
        modulecode=ModuleCode(sequences=[sequence], equationblocks=[]),
    )

    report = analyze_sfc(bp)

    issues = [issue for issue in report.issues if issue.kind == "sfc_duplicate_transition_guard"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["transition_names"] == ["OpenPrimary", "OpenBackup"]
    assert issues[0].data["branch_indices"] == [1, 2]


def test_sfc_transition_logic_ignores_equivalent_guards_in_linear_steps():
    sequence = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCTransition(name="Tr2", condition=_varref("Permit")),
            SFCStep(kind="step", name="OpenValve", code=SFCCodeBlocks()),
            SFCTransition(name="Tr5", condition=_varref("Permit")),
            SFCStep(kind="step", name="CloseValve", code=SFCCodeBlocks()),
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="Permit", datatype=ScalarDatatype.BOOLEAN)],
        modulecode=ModuleCode(sequences=[sequence], equationblocks=[]),
    )

    report = analyze_sfc(bp)

    assert not [issue for issue in report.issues if issue.kind == "sfc_duplicate_transition_guard"]
