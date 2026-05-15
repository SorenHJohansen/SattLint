from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.parameter_drift import analyze_parameter_drift
from sattlint.analyzers.registry import get_default_analyzers


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def test_parameter_drift_flags_diverging_literal_parameter_values() -> None:
    typedef = ModuleTypeDef(
        name="DoseValve",
        moduleparameters=[Variable(name="Timeout", datatype=Simple_DataType.INTEGER, init_value=10)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("ValveA"),
                moduletype_name="DoseValve",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Timeout"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source=None,
                        source_literal=10,
                    )
                ],
            ),
            ModuleTypeInstance(
                header=_hdr("ValveB"),
                moduletype_name="DoseValve",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Timeout"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source=None,
                        source_literal=15,
                    )
                ],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_parameter_drift(bp)

    drift_issues = [issue for issue in report.issues if issue.kind == "module.parameter_drift"]
    assert len(drift_issues) == 2
    assert all("Timeout" in issue.message for issue in drift_issues)
    assert any("Program.ValveA=10" in issue.message for issue in drift_issues)
    assert any("Program.ValveB=15" in issue.message for issue in drift_issues)


def test_parameter_drift_ignores_aligned_literal_parameter_values() -> None:
    typedef = ModuleTypeDef(
        name="DoseValve",
        moduleparameters=[Variable(name="Timeout", datatype=Simple_DataType.INTEGER, init_value=10)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("ValveA"),
                moduletype_name="DoseValve",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Timeout"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source=None,
                        source_literal=10,
                    )
                ],
            ),
            ModuleTypeInstance(
                header=_hdr("ValveB"),
                moduletype_name="DoseValve",
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_parameter_drift(bp)

    assert not any(issue.kind == "module.parameter_drift" for issue in report.issues)


def test_parameter_drift_analyzer_is_enabled_by_default() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "parameter-drift" in specs
    assert specs["parameter-drift"].enabled is True
