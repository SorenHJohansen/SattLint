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
from sattlint.analyzers.config_drift import analyze_config_drift
from sattlint.analyzers.registry import get_default_analyzers


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def test_config_drift_reports_drifting_instance_configuration():
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
    )

    report = analyze_config_drift(bp)

    issues = [issue for issue in report.issues if issue.kind == "config_drift.instance_configuration"]
    assert len(issues) == 1
    assert report.summary_data["config_drift"] == ["DoseValve.Timeout"]
    assert "ValveA" in issues[0].message
    assert "ValveB" in issues[0].message


def test_config_drift_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "config-drift" in specs
    assert specs["config-drift"].enabled is True
