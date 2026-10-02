# pyright: reportOptionalCall=false
import pytest
from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import FuncCall, FuncCallStmt, VarRef

from sattlint.analyzers.variables import analyze_variables
from sattlint.reporting.variables_report import DEFAULT_VARIABLE_ANALYSIS_KINDS, IssueKind


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _shadowing_only_report(bp: BasePicture):
    return analyze_variables(bp, selected_issue_kinds=frozenset({IssueKind.SHADOWING}))


def _nested_shadowing_report(
    parent_variable: Variable,
    child_variables: list[Variable],
    *,
    child_module_code: ModuleCode | None = None,
):
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[],
        localvariables=child_variables,
        submodules=[],
        modulecode=child_module_code,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[parent_variable],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )
    return _shadowing_only_report(bp)


@pytest.mark.parametrize("name", ["si", "SI1", "si2", "si3", "si4", "si5", "si14"])
def test_shadowing_ignores_integer_status_indicator_names(name: str) -> None:
    report = _nested_shadowing_report(
        Variable(name=name, datatype=Simple_DataType.INTEGER),
        [Variable(name=name, datatype=Simple_DataType.INTEGER)],
    )

    assert report.issues == []


def test_shadowing_still_reports_noninteger_si_name_collision() -> None:
    report = _nested_shadowing_report(
        Variable(name="si", datatype=Simple_DataType.STRING),
        [Variable(name="si", datatype=Simple_DataType.STRING)],
    )

    assert any(issue.kind is IssueKind.SHADOWING for issue in report.issues)


def test_shadowing_ignores_integer_variable_bound_to_status_channel() -> None:
    status_name = "OperationStatus"
    report = _nested_shadowing_report(
        Variable(name=status_name, datatype=Simple_DataType.INTEGER),
        [
            Variable(name=status_name, datatype=Simple_DataType.INTEGER),
            Variable(name="Text", datatype=Simple_DataType.STRING),
        ],
        child_module_code=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        FuncCallStmt(
                            call=FuncCall(
                                name="SetStringPos",
                                args=(VarRef(name="Text"), 1, VarRef(name=status_name)),
                            )
                        )
                    ],
                )
            ]
        ),
    )

    assert report.issues == []


def test_shadowing_detected_for_nested_locals() -> None:
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="value", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="Value", datatype=Simple_DataType.INTEGER)],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    report = _shadowing_only_report(bp)

    assert any(issue.kind is IssueKind.SHADOWING for issue in report.issues)


def test_shadowing_detected_for_moduletype_instance_locals() -> None:
    mt = ModuleTypeDef(
        name="TypeA",
        moduleparameters=[],
        localvariables=[Variable(name="Setting", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )

    instance = ModuleTypeInstance(
        header=_hdr("InstanceA"),
        moduletype_name="TypeA",
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[mt],
        localvariables=[Variable(name="setting", datatype=Simple_DataType.INTEGER)],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
    )

    report = _shadowing_only_report(bp)

    assert any(issue.kind is IssueKind.SHADOWING for issue in report.issues)


def test_shadowing_ignores_external_moduletype_instance_locals_for_program_target() -> None:
    mt = ModuleTypeDef(
        name="TypeA",
        moduleparameters=[],
        localvariables=[Variable(name="Setting", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="TypeA.x",
        origin_lib="SomeLib",
    )

    instance = ModuleTypeInstance(
        header=_hdr("InstanceA"),
        moduletype_name="TypeA",
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[mt],
        localvariables=[Variable(name="setting", datatype=Simple_DataType.INTEGER)],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProgramLib",
    )

    report = _shadowing_only_report(bp)

    assert not any(issue.kind is IssueKind.SHADOWING for issue in report.issues)


def test_shadowing_is_default_variable_analysis_kind() -> None:
    assert IssueKind.SHADOWING in DEFAULT_VARIABLE_ANALYSIS_KINDS


def test_shadowing_traverses_frames_and_nested_single_modules() -> None:
    grandchild = SingleModule(
        header=_hdr("Grandchild"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="VALUE", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Other", datatype=Simple_DataType.INTEGER)],
        submodules=[grandchild],
        modulecode=None,
        parametermappings=[],
    )
    frame = FrameModule(header=_hdr("Frame"), submodules=[child])
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="Value", datatype=Simple_DataType.INTEGER)],
        submodules=[frame],
        modulecode=None,
        moduledef=None,
    )

    report = _shadowing_only_report(bp)

    assert [issue.module_path for issue in report.issues] == [["Root", "Frame", "Child", "Grandchild"]]


def test_shadowing_ignores_moduletype_instances_when_root_origin_is_unknown() -> None:
    mt = ModuleTypeDef(
        name="TypeA",
        moduleparameters=[],
        localvariables=[Variable(name="Setting", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="TypeA.x",
    )
    instance = ModuleTypeInstance(
        header=_hdr("InstanceA"),
        moduletype_name="TypeA",
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[mt],
        localvariables=[Variable(name="setting", datatype=Simple_DataType.INTEGER)],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
    )

    assert _shadowing_only_report(bp).issues == []


def test_shadowing_ignores_unresolvable_moduletype_instances() -> None:
    instance = ModuleTypeInstance(
        header=_hdr("MissingType"),
        moduletype_name="DoesNotExist",
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="setting", datatype=Simple_DataType.INTEGER)],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
    )

    assert _shadowing_only_report(bp).issues == []


def test_shadowing_report_is_empty_without_collisions() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="RootValue", datatype=Simple_DataType.INTEGER)],
        submodules=[
            SingleModule(
                header=_hdr("Child"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[Variable(name="ChildValue", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
    )

    assert _shadowing_only_report(bp).issues == []
