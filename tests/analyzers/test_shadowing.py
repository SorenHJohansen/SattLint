from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.shadowing import ShadowingAnalyzer, analyze_shadowing
from sattlint.reporting.variables_report import IssueKind


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


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

    report = analyze_shadowing(bp)

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

    report = analyze_shadowing(bp)

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

    report = analyze_shadowing(bp)

    assert not any(issue.kind is IssueKind.SHADOWING for issue in report.issues)


def test_shadowing_analyzer_is_enabled_by_default() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "shadowing" in specs
    assert specs["shadowing"].enabled is True


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

    report = analyze_shadowing(bp)

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

    assert analyze_shadowing(bp).issues == []


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

    assert analyze_shadowing(bp).issues == []


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

    assert analyze_shadowing(bp).issues == []


def test_shadowing_analyzer_exposes_empty_issue_property() -> None:
    analyzer = ShadowingAnalyzer(
        BasePicture(
            header=_hdr("Root"),
            datatype_defs=[],
            moduletype_defs=[],
            localvariables=[],
            submodules=[],
            modulecode=None,
            moduledef=None,
        )
    )

    assert analyzer.issues == []
    assert ShadowingAnalyzer.issues.fget(analyzer) == []
