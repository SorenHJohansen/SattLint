# pyright: reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportMissingTypeArgument=false
from sattline_parser.models.ast_model import (
    BasePicture,
    CodeItem,
    Equation,
    IntLiteral,
    ModuleCode,
    ModuleHeader,
    Sequence,
    SFCCodeBlocks,
    SFCStep,
    SFCTransition,
    Simple_DataType,
    Variable,
)
from sattline_parser.models.expressions import Assignment, IfStmt, VarRef

from sattlint.analyzers.cyclomatic_complexity import analyze_cyclomatic_complexity
from sattlint.analyzers.registry import get_default_analyzers


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def test_cyclomatic_complexity_ignores_low_complexity_program_modulecode() -> None:
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


def test_cyclomatic_complexity_flags_high_complexity_program_modulecode() -> None:
    decision_statements: list[CodeItem] = [
        IfStmt(
            branches=(
                (
                    _varref(f"Cond{index}"),
                    (Assignment(target=_varref("Output"), value=IntLiteral(index)),),
                ),
            ),
            else_block=(),
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


def test_cyclomatic_complexity_flags_high_complexity_sfc_step() -> None:
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
                                        else_block=(),
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


def test_cyclomatic_complexity_analyzer_is_enabled_by_default() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "cyclomatic-complexity" in specs
    assert specs["cyclomatic-complexity"].enabled is True


def test_cyclomatic_complexity_flags_high_equation_block_complexity() -> None:
    decision_statements: list[CodeItem] = [
        IfStmt(
            branches=(
                (
                    _varref(f"EqCond{index}"),
                    (Assignment(target=_varref("Output"), value=IntLiteral(index)),),
                ),
            ),
            else_block=(),
        )
        for index in range(10)
    ]
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name=f"EqCond{index}", datatype=Simple_DataType.BOOLEAN) for index in range(10)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="BusyBlock",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=decision_statements,
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_cyclomatic_complexity(bp)

    issues = [issue for issue in report.issues if issue.kind == "equation.cyclomatic_complexity"]
    assert len(issues) == 1
    assert issues[0].data == {
        "scope": "equation-block",
        "equation": "BusyBlock",
        "complexity": 11,
        "threshold": 10,
        "site": "EQ:BusyBlock",
        "context": "complexity 11 > 10",
    }


def test_cyclomatic_complexity_honors_configured_thresholds() -> None:
    decision_statements: list[CodeItem] = [
        IfStmt(
            branches=(
                (
                    _varref(f"EqCond{index}"),
                    (Assignment(target=_varref("Output"), value=IntLiteral(index)),),
                ),
            ),
            else_block=(),
        )
        for index in range(3)
    ]
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name=f"EqCond{index}", datatype=Simple_DataType.BOOLEAN) for index in range(3)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="SmallBlock",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=decision_statements,
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_cyclomatic_complexity(
        bp,
        config={"analysis": {"cyclomatic_equation_block_threshold": 2}},
    )

    issues = [issue for issue in report.issues if issue.kind == "equation.cyclomatic_complexity"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["complexity"] == 4
    assert issues[0].data["threshold"] == 2
