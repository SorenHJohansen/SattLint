from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    Variable,
)
from sattlint.analyzers.powerup import analyze_powerup
from sattlint.analyzers.registry import get_actual_cli_analyzer_keys, get_default_analyzers


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def test_powerup_analyzer_is_registered_and_in_default_cli_subset() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "powerup" in specs
    assert specs["powerup"].enabled is True
    assert "powerup" in get_actual_cli_analyzer_keys()


def test_powerup_reports_missing_startup_value() -> None:
    recipe_parameter = ModuleTypeDef(
        name="RecParReal",
        moduleparameters=[Variable(name="Value", datatype=Simple_DataType.REAL)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[recipe_parameter],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("RecipeSP"),
                moduletype_name="RecParReal",
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_powerup(bp)

    assert any(issue.kind == "initial-values.missing_required_default" for issue in report.issues)
    assert report.summary().startswith("Report: Power-up")


def test_powerup_reports_unsafe_true_default() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="EnableBypass", datatype=Simple_DataType.BOOLEAN, init_value=True)],
        modulecode=None,
    )

    report = analyze_powerup(bp)

    assert any(issue.kind == "unsafe_defaults.true_boolean_default" for issue in report.issues)
    assert any("EnableBypass" in issue.message for issue in report.issues)
