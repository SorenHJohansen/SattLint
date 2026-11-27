import pytest
from sattline_parser.models.ast_model import (
    BasePicture,
    CodeItem,
    Equation,
    IntLiteral,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ScalarDatatype,
    Sequence,
    SFCCodeBlocks,
    SFCStep,
    SFCTransition,
    Variable,
)
from sattline_parser.models.expressions import Assignment, IfStmt, VarRef

from sattlint.analyzers.cyclomatic_complexity import (
    DEFAULT_EQUATION_BLOCK_COMPLEXITY_THRESHOLD,
    DEFAULT_MODULE_COMPLEXITY_THRESHOLD,
    DEFAULT_STEP_COMPLEXITY_THRESHOLD,
    analyze_cyclomatic_complexity,
)
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.shared.instance_paths import rewrite_typedef_paths
from sattlint.config.analysis import (
    cyclomatic_equation_block_threshold,
    cyclomatic_module_threshold,
    cyclomatic_step_threshold,
)


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
            equationblocks=[
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


@pytest.mark.parametrize("decisions, expected", [(19, False), (20, True)])
def test_cyclomatic_complexity_flags_high_complexity_program_modulecode(decisions: int, expected: bool) -> None:
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
        for index in range(decisions)
    ]
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name=f"Cond{index}", datatype=ScalarDatatype.BOOLEAN) for index in range(decisions)],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
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
    assert bool(issues) is expected
    if not expected:
        return
    assert len(issues) == 1
    assert issues[0].data == {
        "scope": "program",
        "complexity": 21,
        "threshold": 20,
        "site": ".".join(issues[0].module_path or []),
        "context": "complexity 21 > 20",
    }


@pytest.mark.parametrize("decisions, expected", [(9, False), (10, True)])
def test_cyclomatic_complexity_flags_high_complexity_sfc_step(decisions: int, expected: bool) -> None:
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
                                    for index in range(decisions)
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
    assert bool(issues) is expected
    if not expected:
        return
    assert len(issues) == 1
    assert issues[0].data == {
        "scope": "step",
        "sequence": "MainSeq",
        "step": "HeatUp",
        "complexity": 11,
        "threshold": 10,
        "site": "SQ:MainSeq > STEP:HeatUp",
        "context": "complexity 11 > 10",
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
        localvariables=[Variable(name=f"EqCond{index}", datatype=ScalarDatatype.BOOLEAN) for index in range(10)],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
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


def _decision_statements(prefix: str, decisions: int) -> list[CodeItem]:
    return [
        IfStmt(
            branches=(
                (
                    _varref(f"{prefix}{index}"),
                    (Assignment(target=_varref("Output"), value=IntLiteral(index)),),
                ),
            ),
            else_block=(),
        )
        for index in range(decisions)
    ]


def _equation(name: str, decisions: int) -> Equation:
    return Equation(
        name=name,
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=_decision_statements(f"{name}Cond", decisions),
    )


def test_module_complexity_takes_the_worst_equation_block_not_the_sum() -> None:
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(equationblocks=[_equation("First", 15), _equation("Second", 15)]),
        moduledef=None,
    )

    report = analyze_cyclomatic_complexity(bp)

    equation_issues = [issue for issue in report.issues if issue.kind == "equation.cyclomatic_complexity"]
    assert len(equation_issues) == 2
    assert [issue.data["complexity"] for issue in equation_issues if issue.data] == [16, 16]
    assert not any(issue.kind == "module.cyclomatic_complexity" for issue in report.issues)


def test_module_complexity_takes_the_worst_step_not_the_sum() -> None:
    def _sequence(name: str, decisions: int) -> Sequence:
        return Sequence(
            name=name,
            type="SEQUENCE",
            position=(0.0, 0.0),
            size=(1.0, 1.0),
            code=[
                SFCStep(
                    kind="step",
                    name=f"{name}Step",
                    code=SFCCodeBlocks(active=_decision_statements(f"{name}Cond", decisions)),
                ),
                SFCTransition(name=f"{name}Continue", condition=_varref("Proceed")),
            ],
        )

    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(sequences=[_sequence("First", 11), _sequence("Second", 11)]),
        moduledef=None,
    )

    report = analyze_cyclomatic_complexity(bp)

    step_issues = [issue for issue in report.issues if issue.kind == "step.cyclomatic_complexity"]
    assert len(step_issues) == 2
    assert [issue.data["complexity"] for issue in step_issues if issue.data] == [12, 12]
    assert not any(issue.kind == "module.cyclomatic_complexity" for issue in report.issues)


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
        localvariables=[Variable(name=f"EqCond{index}", datatype=ScalarDatatype.BOOLEAN) for index in range(3)],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
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


def test_cyclomatic_complexity_moduletype_findings_land_on_the_invocation() -> None:
    decisions: list[CodeItem] = [
        IfStmt(
            branches=((_varref(f"Cond{index}"), (Assignment(target=_varref("Output"), value=IntLiteral(index)),)),),
            else_block=(),
        )
        for index in range(20)
    ]
    moduletype = ModuleTypeDef(
        name="Worker",
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equationblocks=[
                Equation(name="Work", position=(0.0, 0.0), size=(1.0, 1.0), code=decisions),
            ]
        ),
    )
    instance = ModuleTypeInstance(
        header=_hdr("Worker1"),
        moduletype_name="Worker",
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[moduletype],
        localvariables=[],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_cyclomatic_complexity(bp)

    issues = [issue for issue in report.issues if issue.kind == "module.cyclomatic_complexity"]
    assert len(issues) == 1
    assert issues[0].module_path == ["Program", "TypeDef:Worker"]
    assert issues[0].data is not None
    assert issues[0].data["site"] == "Program.TypeDef:Worker"

    rewritten = rewrite_typedef_paths(issues, bp)

    assert issues[0].module_path == ["Program", "TypeDef:Worker"]
    assert rewritten[0].module_path == ["Program", "Worker1"]
    assert rewritten[0].data is not None
    assert rewritten[0].data["site"] == "Program.Worker1"


def test_complexity_defaults_and_project_overrides_are_consistent() -> None:
    assert cyclomatic_module_threshold(None) == DEFAULT_MODULE_COMPLEXITY_THRESHOLD == 20
    assert cyclomatic_step_threshold(None) == DEFAULT_STEP_COMPLEXITY_THRESHOLD == 10
    assert cyclomatic_equation_block_threshold(None) == DEFAULT_EQUATION_BLOCK_COMPLEXITY_THRESHOLD == 10
    config = {
        "analysis": {
            "cyclomatic_module_threshold": 12,
            "cyclomatic_step_threshold": 8,
            "cyclomatic_equation_block_threshold": 15,
        }
    }
    assert cyclomatic_module_threshold(config) == 12
    assert cyclomatic_step_threshold(config) == 8
    assert cyclomatic_equation_block_threshold(config) == 15
