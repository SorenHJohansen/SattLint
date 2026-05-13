from sattline_parser.models.ast_model import BasePicture, Equation, ModuleCode, ModuleHeader, Simple_DataType, Variable
from sattlint import constants as const
from sattlint.analyzers.registry import get_actual_cli_analyzer_keys, get_default_analyzers
from sattlint.analyzers.timing import analyze_timing


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def _state_ref(name: str, state: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name, "state": state}


def test_timing_analyzer_is_registered_and_in_default_cli_subset() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "timing" in specs
    assert specs["timing"].enabled is True
    assert "timing" in get_actual_cli_analyzer_keys()


def test_timing_reports_same_scan_temporal_hazards() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Flag", datatype=Simple_DataType.BOOLEAN, state=True),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _state_ref("Flag", "new"), True),
                        (const.KEY_ASSIGN, _varref("Output"), _state_ref("Flag", "old")),
                    ],
                )
            ]
        ),
    )

    report = analyze_timing(bp)

    assert any(issue.kind == "dataflow.scan_cycle_stale_read" for issue in report.issues)
    assert report.summary().startswith("Report: Timing")


def test_timing_reports_non_precision_scan_builtin_usage() -> None:
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
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "AssignSystemString",
                            [_varref("SysVarId"), _varref("Value"), _varref("Status")],
                        )
                    ],
                )
            ]
        ),
        moduledef=None,
    )

    report = analyze_timing(bp)

    assert any(issue.kind == "scan_cycle.resource_usage" for issue in report.issues)
