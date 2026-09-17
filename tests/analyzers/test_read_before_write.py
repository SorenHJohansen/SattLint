# pyright: reportUnknownVariableType=false, reportUnknownParameterType=false, reportMissingTypeArgument=false
from collections.abc import Sequence

from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ModuleHeader,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import Assignment, VarRef

from sattlint.analyzers.variables import analyze_variables
from sattlint.reporting.variables_report import DEFAULT_VARIABLE_ANALYSIS_KINDS, IssueKind


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def _rbw_only_report(bp: BasePicture):
    return analyze_variables(bp, selected_issue_kinds=frozenset({IssueKind.READ_BEFORE_WRITE}))


def _equation(code: Sequence[Assignment]) -> Equation:
    return Equation(name="Main", position=(0.0, 0.0), size=(1.0, 1.0), code=list(code))


def test_read_before_write_reports_reads_before_writes():
    bp = BasePicture(
        header=_hdr("Program"),
        localvariables=[
            Variable(name="InputSignal", datatype=Simple_DataType.BOOLEAN),
            Variable(name="OutputSignal", datatype=Simple_DataType.BOOLEAN),
            Variable(name="ObservedSignal", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _equation(
                    [
                        Assignment(target=_varref("OutputSignal"), value=_varref("InputSignal")),
                        Assignment(target=_varref("InputSignal"), value=True),
                        Assignment(target=_varref("ObservedSignal"), value=_varref("OutputSignal")),
                    ]
                )
            ]
        ),
    )

    report = _rbw_only_report(bp)

    rbw = [issue for issue in report.issues if issue.kind is IssueKind.READ_BEFORE_WRITE]
    assert any(issue.context == "InputSignal" for issue in rbw)
    assert not any(issue.context == "OutputSignal" for issue in rbw)


def test_read_before_write_reports_initialization_order_hazard():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            equations=[
                _equation(
                    [
                        Assignment(target=_varref("Output"), value=_varref("Source")),
                        Assignment(target=_varref("Source"), value=3),
                    ]
                )
            ]
        ),
    )

    report = _rbw_only_report(bp)

    rbw = [issue for issue in report.issues if issue.kind is IssueKind.READ_BEFORE_WRITE]
    assert any(issue.context == "Source" for issue in rbw)


def test_read_before_write_is_default_variable_analysis_kind():
    assert IssueKind.READ_BEFORE_WRITE in DEFAULT_VARIABLE_ANALYSIS_KINDS


def test_read_before_write_ignores_initialized_and_parameter_values():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="Param", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="ChildOut", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(equations=[_equation([Assignment(target=_varref("ChildOut"), value=_varref("Param"))])]),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="PreInit", datatype=Simple_DataType.BOOLEAN, init_value=False),
            Variable(name="Out", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[child],
        modulecode=ModuleCode(equations=[_equation([Assignment(target=_varref("Out"), value=_varref("PreInit"))])]),
    )

    report = _rbw_only_report(bp)

    assert not any(issue.kind is IssueKind.READ_BEFORE_WRITE for issue in report.issues)


def test_read_before_write_clean_when_all_reads_follow_writes():
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Output", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            equations=[
                _equation(
                    [
                        Assignment(target=_varref("Source"), value=3),
                        Assignment(target=_varref("Output"), value=_varref("Source")),
                    ]
                )
            ]
        ),
    )

    report = _rbw_only_report(bp)

    assert not any(issue.kind is IssueKind.READ_BEFORE_WRITE for issue in report.issues)
