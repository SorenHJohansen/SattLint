from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleHeader,
    ModuleTypeDef,
    Simple_DataType,
    Variable,
)
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.unsafe_defaults import analyze_unsafe_defaults


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def test_unsafe_defaults_reports_true_boolean_enable_default() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="EnablePump", datatype=Simple_DataType.BOOLEAN, init_value=True)],
        modulecode=None,
    )

    report = analyze_unsafe_defaults(bp)

    assert any(issue.kind == "unsafe_defaults.true_boolean_default" for issue in report.issues)
    assert any("EnablePump" in issue.message for issue in report.issues)
    assert any("activate equipment or logic from startup" in issue.message for issue in report.issues)


def test_unsafe_defaults_reports_true_boolean_bypass_default_in_root_typedef() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[
            ModuleTypeDef(
                name="ValveType",
                moduleparameters=[Variable(name="SafetyBypass", datatype=Simple_DataType.BOOLEAN, init_value=True)],
                localvariables=[],
                submodules=[],
                moduledef=None,
                modulecode=None,
                parametermappings=[],
                origin_file="Root.s",
            )
        ],
        localvariables=[],
        submodules=[],
        modulecode=None,
        origin_file="Root.s",
    )

    report = analyze_unsafe_defaults(bp)

    issues = [issue for issue in report.issues if issue.kind == "unsafe_defaults.true_boolean_default"]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "TypeDef:ValveType"]
    assert "bypass safety checks from startup" in issues[0].message


def test_unsafe_defaults_ignores_false_and_external_typedef_defaults() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[
            ModuleTypeDef(
                name="ExternalValveType",
                moduleparameters=[Variable(name="EnablePump", datatype=Simple_DataType.BOOLEAN, init_value=True)],
                localvariables=[],
                submodules=[],
                moduledef=None,
                modulecode=None,
                parametermappings=[],
                origin_file="ExternalType.s",
            )
        ],
        localvariables=[
            Variable(name="EnablePump", datatype=Simple_DataType.BOOLEAN, init_value=False),
            Variable(name="AlarmTrip", datatype=Simple_DataType.BOOLEAN, init_value=True),
        ],
        submodules=[],
        modulecode=None,
        origin_file="Root.s",
    )

    report = analyze_unsafe_defaults(bp)

    assert report.issues == []


def test_unsafe_defaults_analyzer_is_enabled_by_default() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "unsafe-defaults" in specs
    assert specs["unsafe-defaults"].enabled is True
