from sattline_parser.models.ast_model import BasePicture, Equation, ModuleCode, ModuleHeader, Simple_DataType, Variable
from sattlint import constants as const
from sattlint.analyzers.fault_handling import analyze_fault_handling
from sattlint.analyzers.registry import get_default_analyzers


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def test_fault_handling_flags_unhandled_and_never_cleared_faults():
    bp = BasePicture(
        header=_hdr("Program"),
        localvariables=[
            Variable(name="HighFault", datatype=Simple_DataType.BOOLEAN),
            Variable(name="HandledFault", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Status", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("HighFault"), True),
                        (const.KEY_ASSIGN, _varref("HandledFault"), True),
                        (const.KEY_ASSIGN, _varref("Status"), _varref("HandledFault")),
                        (const.KEY_ASSIGN, _varref("HandledFault"), False),
                    ],
                )
            ]
        ),
    )

    report = analyze_fault_handling(bp)

    issue_kinds = {issue.kind for issue in report.issues}
    assert "fault_handling.missing_recovery" in issue_kinds
    assert "fault_handling.unhandled_fault" in issue_kinds
    assert any("HighFault" in issue.message for issue in report.issues)
    assert not any(
        "HandledFault" in issue.message and issue.kind == "fault_handling.unhandled_fault" for issue in report.issues
    )


def test_fault_handling_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "fault_handling" in specs
    assert specs["fault_handling"].enabled is True
