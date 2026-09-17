# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Adjacent analyzer scenarios re-exported by tests.test_analyzers_variables."""

from __future__ import annotations

from sattline_parser.models.ast_model import (
    BasePicture,
    CodeItem,
    Equation,
    IntLiteral,
    ModuleCode,
    Sequence,
    SFCCodeBlocks,
    SFCStep,
    SFCTransition,
    Simple_DataType,
    Variable,
)
from sattline_parser.models.expressions import Assignment, IfStmt

from sattlint.analyzers.cyclomatic_complexity import analyze_cyclomatic_complexity
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)
from tests.helpers.variable_test_support import (
    varref as _varref,
)


def test_cyclomatic_complexity_ignores_low_complexity_program_modulecode():
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="MainEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[Assignment(target=_varref("Output"), value=IntLiteral(1))],
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_cyclomatic_complexity(bp)

    assert not any(issue.kind == "module.cyclomatic_complexity" for issue in report.issues)
    assert not any(issue.kind == "step.cyclomatic_complexity" for issue in report.issues)


def test_cyclomatic_complexity_flags_high_complexity_program_modulecode():
    decision_statements: list[CodeItem] = [
        IfStmt(
            branches=(
                (
                    _varref(f"Cond{index}"),
                    (Assignment(target=_varref("Output"), value=IntLiteral(index)),),
                ),
            ),
            else_block=None,
        )
        for index in range(10)
    ]
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name=f"Cond{index}", datatype=Simple_DataType.BOOLEAN) for index in range(10)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="MainEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=decision_statements,
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_cyclomatic_complexity(bp)

    issues = [issue for issue in report.issues if issue.kind == "module.cyclomatic_complexity"]
    assert len(issues) == 1
    assert issues[0].data == {
        "scope": "program",
        "complexity": 11,
        "threshold": 10,
        "site": ".".join(issues[0].module_path or []),
        "context": "complexity 11 > 10",
    }
    assert "Program" in issues[0].message


def test_cyclomatic_complexity_flags_high_complexity_sfc_step():
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            sequences=[
                Sequence(
                    name="MainSeq",
                    type="SEQUENCE",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        SFCStep(
                            kind="step",
                            name="HeatUp",
                            code=SFCCodeBlocks(
                                active=[
                                    IfStmt(
                                        branches=(
                                            (
                                                _varref(f"StepCond{index}"),
                                                (Assignment(target=_varref("Output"), value=IntLiteral(index)),),
                                            ),
                                        ),
                                        else_block=None,
                                    )
                                    for index in range(6)
                                ]
                            ),
                        ),
                        SFCTransition(name="Continue", condition=_varref("Proceed")),
                    ],
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_cyclomatic_complexity(bp)

    issues = [issue for issue in report.issues if issue.kind == "step.cyclomatic_complexity"]
    assert len(issues) == 1
    assert issues[0].data == {
        "scope": "step",
        "sequence": "MainSeq",
        "step": "HeatUp",
        "complexity": 7,
        "threshold": 6,
        "site": "SQ:MainSeq > STEP:HeatUp",
        "context": "complexity 7 > 6",
    }
    assert "HeatUp" in issues[0].message
    assert "MainSeq" in issues[0].message
