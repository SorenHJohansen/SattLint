# pyright: reportUnknownVariableType=false, reportUnknownParameterType=false, reportMissingTypeArgument=false
from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    IntLiteral,
    ModuleCode,
    ModuleHeader,
    Simple_DataType,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.numeric_constraints import analyze_numeric_constraints
from sattlint.analyzers.registry import get_default_analyzers


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def test_numeric_constraints_flags_assignments_outside_visible_bounds():
    bp = BasePicture(
        header=_hdr("Program"),
        localvariables=[
            Variable(name="Min_Output", datatype=Simple_DataType.INTEGER, init_value=0),
            Variable(name="Max_Output", datatype=Simple_DataType.INTEGER, init_value=10),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), IntLiteral(12))],
                )
            ]
        ),
    )

    report = analyze_numeric_constraints(bp)

    issues = [issue for issue in report.issues if issue.kind == "numeric_constraints.limit_violation"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["maximum"] == 10
    assert issues[0].data["value"] == 12
    assert report.summary_data["violation_count"] == 1


def test_numeric_constraints_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "numeric-constraints" in specs
    assert specs["numeric-constraints"].enabled is True
