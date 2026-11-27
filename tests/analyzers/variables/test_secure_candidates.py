# pyright: reportPrivateUsage=false
"""Secure-candidate detection for values that transitions depend on."""

from __future__ import annotations

from sattline_parser.models.ast_model import (
    BasePicture,
    CodeItem,
    Equation,
    FrameModule,
    ModuleCode,
    ScalarDatatype,
    Sequence,
    SFCCodeBlocks,
    SFCStep,
    SFCTransition,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import Assignment, BoolOp, IfStmt, NotOp, SLExpression

from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.models._variable_issues import SecureCandidateIssue
from sattlint.parser_api import parse_source_text
from tests.helpers.variable_test_support import hdr as _hdr
from tests.helpers.variable_test_support import varref as _varref


def _assign(name: str, value: SLExpression) -> Assignment:
    return Assignment(target=_varref(name), value=value)


def _sequence(step: SFCStep, transition: SFCTransition) -> Sequence:
    return Sequence(
        name="OpSeq",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[step, transition],
    )


def _picture(
    *,
    localvariables: list[Variable],
    moduleparameters: list[Variable] | None = None,
    step_code: list[CodeItem] | None = None,
    transition_condition: SLExpression | None = None,
    equations: list[Equation] | None = None,
) -> BasePicture:
    step = SFCStep(
        kind="step",
        name="Calc",
        code=SFCCodeBlocks(enter=list(step_code or [])),
    )
    transition = SFCTransition(
        name="Gate",
        condition=transition_condition or BoolOp(op="AND", operands=(_varref("MediaTargetVol"),)),
    )
    logic = FrameModule(
        header=_hdr("Logic"),
        modulecode=ModuleCode(sequences=[_sequence(step, transition)], equationblocks=list(equations or [])),
    )
    mixing = SingleModule(
        header=_hdr("MixingAfl"),
        moduleparameters=list(moduleparameters or []),
        localvariables=localvariables,
        submodules=[logic],
        moduledef=None,
        modulecode=None,
    )
    return BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mixing],
        modulecode=None,
        moduledef=None,
    )


def _secure_issues(bp: BasePicture) -> list[SecureCandidateIssue]:
    analyzer = VariablesAnalyzer(bp, selected_issue_kinds={IssueKind.SECURE_CANDIDATE})
    analyzer.run()
    return [issue for issue in analyzer.issues if isinstance(issue, SecureCandidateIssue)]


def _names(issues: list[SecureCandidateIssue]) -> list[str]:
    return sorted(issue.variable.name for issue in issues)


def test_numeric_and_boolean_values_used_by_a_transition_are_candidates() -> None:
    bp = _picture(
        localvariables=[
            Variable(name="MediaTargetVol", datatype=ScalarDatatype.REAL),
            Variable(name="Flag", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="NotWritten", datatype=ScalarDatatype.REAL),
        ],
        step_code=[
            _assign("MediaTargetVol", 10),
            _assign("Flag", True),
        ],
        transition_condition=BoolOp(
            op="AND",
            operands=(_varref("MediaTargetVol"), _varref("Flag"), _varref("NotWritten")),
        ),
    )

    issues = _secure_issues(bp)

    assert _names(issues) == ["Flag", "MediaTargetVol"]
    assert issues[0].site is not None


def test_already_secure_or_opsave_or_const_values_are_not_candidates() -> None:
    bp = _picture(
        localvariables=[
            Variable(name="MediaTargetVol", datatype=ScalarDatatype.REAL, secure=True),
            Variable(name="Persisted", datatype=ScalarDatatype.REAL, opsave=True),
            Variable(name="Fixed", datatype=ScalarDatatype.REAL, const=True),
        ],
        step_code=[
            _assign("MediaTargetVol", 10),
            _assign("Persisted", 10),
            _assign("Fixed", 10),
        ],
        transition_condition=BoolOp(
            op="OR",
            operands=(_varref("MediaTargetVol"), _varref("Persisted"), _varref("Fixed")),
        ),
    )

    assert _secure_issues(bp) == []


def test_a_value_read_by_a_transition_but_not_written_here_is_not_a_candidate() -> None:
    bp = _picture(
        localvariables=[Variable(name="MediaTargetVol", datatype=ScalarDatatype.REAL)],
        step_code=[],
        transition_condition=BoolOp(op="AND", operands=(_varref("MediaTargetVol"),)),
    )

    assert _secure_issues(bp) == []


def test_an_unconditional_equation_write_disqualifies_a_candidate() -> None:
    bp = _picture(
        localvariables=[Variable(name="MediaTargetVol", datatype=ScalarDatatype.REAL)],
        step_code=[_assign("MediaTargetVol", 10)],
        transition_condition=BoolOp(op="AND", operands=(_varref("MediaTargetVol"),)),
        equations=[
            Equation(
                name="Main",
                position=(0.0, 0.0),
                size=(1.0, 1.0),
                code=[_assign("MediaTargetVol", 0)],
            )
        ],
    )

    assert _secure_issues(bp) == []


def test_a_conditional_equation_write_does_not_disqualify_a_candidate() -> None:
    bp = _picture(
        localvariables=[
            Variable(name="MediaTargetVol", datatype=ScalarDatatype.REAL),
            Variable(name="ResetRequested", datatype=ScalarDatatype.BOOLEAN),
        ],
        step_code=[_assign("MediaTargetVol", 10)],
        transition_condition=BoolOp(op="AND", operands=(_varref("MediaTargetVol"),)),
        equations=[
            Equation(
                name="Main",
                position=(0.0, 0.0),
                size=(1.0, 1.0),
                code=[
                    IfStmt(
                        branches=(
                            (
                                _varref("ResetRequested"),
                                (_assign("MediaTargetVol", 0),),
                            ),
                        ),
                        else_block=(),
                    )
                ],
            )
        ],
    )

    assert _names(_secure_issues(bp)) == ["MediaTargetVol"]


SECURE_CANDIDATE_SOURCE = """
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: SecureCandidate"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

SUBMODULES
   MixingAfl Invocation
      ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
       ) : MODULEDEFINITION DateCode_ 1
      LOCALVARIABLES
         MediaTargetVol: real ;
      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      ModuleCode
         SEQUENCE OpSeq (SeqControl, SeqTimer) COORD 0.0, 0.5 OBJSIZE 1.0, 0.5
            SEQINITSTEP Calc
               ENTERCODE
                  MediaTargetVol = 10.0;
            SEQTRANSITION Gate WAIT_FOR MediaTargetVol > 0
         ENDSEQUENCE
      ENDDEF (*MixingAfl*);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
"""


def test_a_secure_candidate_is_reported_from_parsed_source() -> None:
    base_picture = parse_source_text(SECURE_CANDIDATE_SOURCE)

    issues = _secure_issues(base_picture)

    assert _names(issues) == ["MediaTargetVol"]
    assert issues[0].site == "SQ:OpSeq > TRANSITION:Gate"


def test_a_module_parameter_is_not_a_candidate() -> None:
    bp = _picture(
        moduleparameters=[Variable(name="MediaTargetVol", datatype=ScalarDatatype.REAL)],
        localvariables=[],
        step_code=[_assign("MediaTargetVol", 10)],
        transition_condition=BoolOp(op="AND", operands=(_varref("MediaTargetVol"),)),
    )

    assert _secure_issues(bp) == []


def test_a_value_not_read_by_a_transition_is_not_a_candidate() -> None:
    bp = _picture(
        localvariables=[
            Variable(name="MediaTargetVol", datatype=ScalarDatatype.REAL),
            Variable(name="ResetRequested", datatype=ScalarDatatype.BOOLEAN),
        ],
        step_code=[_assign("MediaTargetVol", 10)],
        transition_condition=NotOp(operand=_varref("ResetRequested")),
        equations=[
            Equation(
                name="Main",
                position=(0.0, 0.0),
                size=(1.0, 1.0),
                code=[
                    IfStmt(
                        branches=(
                            (
                                _varref("ResetRequested"),
                                (_assign("MediaTargetVol", 0),),
                            ),
                        ),
                        else_block=(),
                    )
                ],
            )
        ],
    )

    assert _secure_issues(bp) == []
