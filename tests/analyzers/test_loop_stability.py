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
from sattlint.analyzers.loop_stability import analyze_loop_stability
from sattlint.analyzers.registry import get_default_analyzers


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def test_loop_stability_detects_conflicting_literal_setpoints():
    bp = BasePicture(
        header=_hdr("Program"),
        localvariables=[Variable(name="Setpoint", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Control",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("Setpoint"), IntLiteral(10)),
                        (const.KEY_ASSIGN, _varref("Setpoint"), IntLiteral(20)),
                    ],
                )
            ]
        ),
    )

    report = analyze_loop_stability(bp)

    issues = [issue for issue in report.issues if issue.kind == "loop_stability.conflicting_setpoint"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["distinct_values"] == ["10", "20"]
    assert report.summary_data["conflict_count"] == 1


def test_loop_stability_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "loop-stability" in specs
    assert specs["loop-stability"].enabled is True
