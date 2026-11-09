# pyright: reportUnknownVariableType=false, reportUnknownParameterType=false, reportMissingTypeArgument=false
from collections.abc import Sequence

import pytest
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
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


def test_read_before_write_ignores_module_parameter_inherited_by_frame_module():
    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[Variable(name="InputSignal", datatype=Simple_DataType.BOOLEAN)],
        localvariables=[Variable(name="OutputSignal", datatype=Simple_DataType.BOOLEAN)],
        submodules=[
            FrameModule(
                header=_hdr("Frame"),
                modulecode=ModuleCode(
                    equations=[_equation([Assignment(target=_varref("OutputSignal"), value=_varref("InputSignal"))])]
                ),
                submodules=[],
            )
        ],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(header=_hdr("Root"), localvariables=[], submodules=[parent], modulecode=None)

    report = _rbw_only_report(bp)

    assert not any(
        issue.kind is IssueKind.READ_BEFORE_WRITE and issue.context == "InputSignal" for issue in report.issues
    )


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


@pytest.mark.parametrize("dependency", [False, True])
@pytest.mark.parametrize("reusable_parent", [False, True])
def test_child_output_mapping_is_not_an_unwritten_local(dependency: bool, reusable_parent: bool):
    child = SingleModule(
        header=_hdr("Producer"),
        moduledef=None,
        moduleparameters=[Variable(name="Error", datatype=Simple_DataType.BOOLEAN)],
        modulecode=ModuleCode(equations=[_equation([Assignment(target=_varref("Error"), value=False)])]),
        parametermappings=[
            ParameterMapping(
                target=_varref("Error"),
                source_type="variable_name",
                is_duration=False,
                is_source_global=False,
                source=_varref("ErrorSignal"),
                source_literal=None,
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        origin_file="Root.s",
        localvariables=[
            Variable(name="ErrorSignal", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Unwritten", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[child],
        modulecode=ModuleCode(
            equations=[
                _equation(
                    [
                        Assignment(target=_varref("Output"), value=_varref("ErrorSignal")),
                        Assignment(target=_varref("Output"), value=_varref("Unwritten")),
                    ]
                )
            ]
        ),
    )
    if dependency:
        bp.moduletype_defs = [
            ModuleTypeDef(
                name="ProducerType",
                moduleparameters=child.moduleparameters,
                modulecode=child.modulecode,
                origin_file="Dependency.s",
            )
        ]
        bp.submodules = [
            ModuleTypeInstance(
                header=child.header,
                moduletype_name="ProducerType",
                parametermappings=child.parametermappings,
            )
        ]
    if reusable_parent:
        parent = ModuleTypeDef(
            name="Container",
            localvariables=bp.localvariables,
            submodules=bp.submodules,
            modulecode=bp.modulecode,
            origin_file="Root.s",
        )
        bp.moduletype_defs.append(parent)
        bp.localvariables = []
        bp.modulecode = None
        bp.submodules = [ModuleTypeInstance(header=_hdr("ContainerInstance"), moduletype_name="Container")]

    report = analyze_variables(
        bp,
        analyzed_target_is_library=True,
        selected_issue_kinds=frozenset({IssueKind.READ_BEFORE_WRITE}),
    )

    assert not any(issue.context == "ErrorSignal" for issue in report.issues)
    assert any(issue.context == "Unwritten" for issue in report.issues)


def test_child_field_output_does_not_initialize_sibling():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[
            DataType(
                name="SignalsType",
                description=None,
                datecode=None,
                var_list=[
                    Variable(name="Provided", datatype=Simple_DataType.BOOLEAN),
                    Variable(name="Missing", datatype=Simple_DataType.BOOLEAN),
                ],
            )
        ],
        localvariables=[
            Variable(name="Signals", datatype="SignalsType"),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[
            SingleModule(
                header=_hdr("Producer"),
                moduledef=None,
                moduleparameters=[Variable(name="Error", datatype=Simple_DataType.BOOLEAN)],
                modulecode=ModuleCode(equations=[_equation([Assignment(target=_varref("Error"), value=False)])]),
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Error"),
                        source_type="variable_name",
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("Signals.Provided"),
                        source_literal=None,
                    )
                ],
            )
        ],
        modulecode=ModuleCode(
            equations=[
                _equation(
                    [
                        Assignment(target=_varref("Output"), value=_varref("Signals.Provided")),
                        Assignment(target=_varref("Output"), value=_varref("Signals.Missing")),
                    ]
                )
            ]
        ),
    )
    report = _rbw_only_report(bp)
    assert [issue.context for issue in report.issues if issue.kind is IssueKind.READ_BEFORE_WRITE] == [
        "Signals.Missing"
    ]
