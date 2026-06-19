# pyright: reportUnknownVariableType=false, reportUnknownParameterType=false, reportMissingTypeArgument=false
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ModuleHeader,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.modules import analyze_version_drift
from sattlint.analyzers.registry import get_default_analyzers


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def test_version_drift_detects_small_code_delta_between_same_named_modules():
    variant_a = SingleModule(
        header=_hdr("Mixer"),
        datecode=100,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Mixer"),
        datecode=200,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 2)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    cast(Any, variant_a).origin_file = "Root.s"
    cast(Any, variant_b).origin_file = "Root.s"
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[variant_a, variant_b],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_version_drift(bp)

    issues = [issue for issue in report.issues if issue.kind == "module.version_drift"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert issues[0].data["module_name"] == "Mixer"
    assert issues[0].data["unique_variants"] == 2
    assert "code" in issues[0].data["material_differences"]
    assert "modified_equations" in issues[0].data["material_differences"]["code"]
    assert "Logic" in issues[0].data["material_differences"]["code"]["modified_equations"]
    assert issues[0].data["material_differences"]["code"]["modified_equations"]["Logic"]
    assert any("Equation 'Logic' changed" in note for note in issues[0].data["upgrade_notes"])


def test_version_drift_records_modified_variable_shape_diffs():
    variant_a = SingleModule(
        header=_hdr("Mixer"),
        datecode=100,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Mixer"),
        datecode=200,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.REAL)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    cast(Any, variant_a).origin_file = "Root.s"
    cast(Any, variant_b).origin_file = "Root.s"
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[variant_a, variant_b],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_version_drift(bp)

    issues = [issue for issue in report.issues if issue.kind == "module.version_drift"]
    assert len(issues) == 1
    assert issues[0].data is not None
    assert "localvariables" in issues[0].data["material_differences"]
    assert "Output" in issues[0].data["material_differences"]["localvariables"]["modified"]
    assert any(
        detail["path"] == "datatype"
        for detail in issues[0].data["material_differences"]["localvariables"]["modified"]["Output"]
    )
    assert any("Local variable 'Output' changed" in note for note in issues[0].data["upgrade_notes"])


def test_version_drift_ignores_datecode_only_differences():
    variant_a = SingleModule(
        header=_hdr("Mixer"),
        datecode=100,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Mixer"),
        datecode=200,
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Output", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Logic",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), 1)],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
    )
    cast(Any, variant_a).origin_file = "Root.s"
    cast(Any, variant_b).origin_file = "Root.s"
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[variant_a, variant_b],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
    )

    report = analyze_version_drift(bp)

    assert report.issues == []


def test_version_drift_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "version-drift" in specs
    assert specs["version-drift"].enabled is True
