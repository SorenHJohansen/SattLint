from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ScalarDatatype,
    Sequence,
    SFCCodeBlocks,
    SFCStep,
    SFCTransition,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import Assignment, BoolOp, IfStmt, NotOp

from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from tests.helpers.variable_test_support import hdr as _hdr
from tests.helpers.variable_test_support import varref as _varref


def _report(modulecode: ModuleCode, localvariables: list[Variable]) -> list[Variable]:
    module = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=localvariables,
        submodules=[],
        modulecode=modulecode,
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
    return [issue.variable for issue in analyzer.issues if issue.kind is IssueKind.RESET_CONTAMINATION]


def test_reset_contamination_uses_module_reset_input_block() -> None:
    sequence = Sequence(
        name="Seq",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Work",
                code=SFCCodeBlocks(enter=[Assignment(target=_varref("Counter"), value=1)]),
            ),
            SFCTransition(name="Done", condition=True),
        ],
    )
    reset_equation = Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            IfStmt(
                branches=(
                    (
                        BoolOp(op="AND", operands=(_varref("Reset"), NotOp(operand=_varref("ResetOld")))),
                        (Assignment(target=_varref("Counter"), value=0),),
                    ),
                ),
                else_block=(),
            ),
            Assignment(target=_varref("ResetOld"), value=_varref("Reset")),
        ],
    )
    sequence_reset = Equation(
        name="SeqReset",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[Assignment(target=_varref("Seq.Reset"), value=_varref("Busy"))],
    )

    variables = _report(
        ModuleCode(sequences=[sequence], equationblocks=[reset_equation, sequence_reset]),
        [
            Variable(name="Counter", datatype=ScalarDatatype.INTEGER),
            Variable(name="Reset", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="ResetOld", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="Busy", datatype=ScalarDatatype.BOOLEAN),
        ],
    )

    assert [variable.name for variable in variables] == []


def test_reset_contamination_ignores_sequence_reset_driven_by_assignment() -> None:
    sequence = Sequence(
        name="Seq",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            SFCStep(
                kind="step",
                name="Work",
                code=SFCCodeBlocks(enter=[Assignment(target=_varref("Counter"), value=1)]),
            ),
            SFCTransition(name="Done", condition=True),
        ],
    )
    sequence_reset = Equation(
        name="SeqReset",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[Assignment(target=_varref("Seq.Reset"), value=_varref("Busy"))],
    )

    variables = _report(
        ModuleCode(sequences=[sequence], equationblocks=[sequence_reset]),
        [
            Variable(name="Counter", datatype=ScalarDatatype.INTEGER),
            Variable(name="Busy", datatype=ScalarDatatype.BOOLEAN),
        ],
    )

    assert [variable.name for variable in variables] == []
