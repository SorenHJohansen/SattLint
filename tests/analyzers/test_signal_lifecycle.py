from sattline_parser.models.ast_model import BasePicture, Equation, ModuleCode, ModuleHeader, Simple_DataType, Variable
from sattlint import constants as const
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.signal_lifecycle import analyze_signal_lifecycle


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def test_signal_lifecycle_reports_reads_before_writes_and_unconsumed_writes():
    bp = BasePicture(
        header=_hdr("Program"),
        localvariables=[
            Variable(name="InputSignal", datatype=Simple_DataType.BOOLEAN),
            Variable(name="OutputSignal", datatype=Simple_DataType.BOOLEAN),
            Variable(name="ObservedSignal", datatype=Simple_DataType.BOOLEAN),
            Variable(name="NeverConsumed", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("OutputSignal"), _varref("InputSignal")),
                        (const.KEY_ASSIGN, _varref("InputSignal"), True),
                        (const.KEY_ASSIGN, _varref("ObservedSignal"), _varref("OutputSignal")),
                        (const.KEY_ASSIGN, _varref("NeverConsumed"), False),
                    ],
                )
            ]
        ),
    )

    report = analyze_signal_lifecycle(bp)

    issue_kinds = {issue.kind for issue in report.issues}
    assert "signal_lifecycle.read_before_write" in issue_kinds
    assert "signal_lifecycle.unconsumed_write" in issue_kinds
    assert any("InputSignal" in issue.message for issue in report.issues)
    assert any("NeverConsumed" in issue.message for issue in report.issues)
    assert report.summary_data["written_then_read_count"] >= 1


def test_signal_lifecycle_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "signal-lifecycle" in specs
    assert specs["signal-lifecycle"].enabled is True
