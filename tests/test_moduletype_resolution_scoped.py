"""Tests for moduletype resolution within library scopes."""

import pytest

from sattlint import constants as const
from sattlint.analyzers.variables import VariablesAnalyzer, _resolve_moduletype_def_strict
from sattlint.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    Variable,
)


def _header(name: str = "BP") -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def test_resolves_same_library_first():
    mt_lib1 = ModuleTypeDef(name="CIP", origin_lib="Lib1")
    mt_lib2 = ModuleTypeDef(name="CIP", origin_lib="Lib2")
    bp = BasePicture(
        header=_header(),
        origin_lib="Lib1",
        moduletype_defs=[mt_lib1, mt_lib2],
        library_dependencies={"lib1": ["lib2"]},
    )

    resolved = _resolve_moduletype_def_strict(bp, "CIP", current_library="Lib1")

    assert resolved is mt_lib1


def test_resolves_via_dependency_when_missing_local():
    mt_lib2 = ModuleTypeDef(name="CIP", origin_lib="Lib2")
    bp = BasePicture(
        header=_header(),
        origin_lib="Lib1",
        moduletype_defs=[mt_lib2],
        library_dependencies={"lib1": ["lib2"]},
    )

    resolved = _resolve_moduletype_def_strict(bp, "CIP", current_library="Lib1")

    assert resolved is mt_lib2


def test_ambiguous_within_dependencies_raises():
    mt_lib2 = ModuleTypeDef(name="CIP", origin_lib="Lib2")
    mt_lib3 = ModuleTypeDef(name="CIP", origin_lib="Lib3")
    bp = BasePicture(
        header=_header(),
        origin_lib="Lib1",
        moduletype_defs=[mt_lib2, mt_lib3],
        library_dependencies={"lib1": ["lib2", "lib3"]},
    )

    with pytest.raises(ValueError):
        _resolve_moduletype_def_strict(bp, "CIP", current_library="Lib1")


def test_analyzer_uses_library_scoped_moduletype_defs():
    dt_lib1 = DataType(
        name="CIPType1",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Active", datatype=Simple_DataType.BOOLEAN),
            Variable(name="DefaultComm", datatype=Simple_DataType.STRING),
        ],
    )
    dt_lib2 = DataType(
        name="CIPType2",
        description=None,
        datecode=None,
        var_list=[Variable(name="Other", datatype=Simple_DataType.INTEGER)],
    )

    cip_lib1 = ModuleTypeDef(
        name="CIP",
        origin_lib="Lib1",
        origin_file="Lib1.x",
        localvariables=[Variable(name="DV", datatype="CIPType1")],
        moduleparameters=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="E1",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "InitVariable",
                            [{const.KEY_VAR_NAME: "DV.Active"}],
                        )
                    ],
                )
            ]
        ),
    )

    cip_lib2 = ModuleTypeDef(
        name="CIP",
        origin_lib="Lib2",
        origin_file="Lib2.x",
        localvariables=[Variable(name="DV", datatype="CIPType2")],
        moduleparameters=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="E1",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "InitVariable",
                            [{const.KEY_VAR_NAME: "DV.Active"}],
                        )
                    ],
                )
            ]
        ),
    )

    wrapper = ModuleTypeDef(
        name="Wrapper",
        origin_lib="Lib1",
        origin_file="Lib1Wrapper.x",
        localvariables=[],
        moduleparameters=[],
        submodules=[ModuleTypeInstance(header=_header("CIP1"), moduletype_name="CIP")],
        moduledef=None,
        modulecode=None,
    )

    bp = BasePicture(
        header=_header("BasePicture"),
        origin_lib="AppLib",
        origin_file="Root.x",
        datatype_defs=[dt_lib1, dt_lib2],
        moduletype_defs=[cip_lib1, cip_lib2, wrapper],
        localvariables=[],
        submodules=[ModuleTypeInstance(header=_header("WrapperInst"), moduletype_name="Wrapper")],
        modulecode=None,
        moduledef=None,
        library_dependencies={"applib": ["lib1", "lib2"]},
    )

    analyzer = VariablesAnalyzer(bp, debug=False, fail_loudly=False)
    analyzer.run()

    assert not any(
        "unknown field 'Active'" in warning for warning in analyzer.analysis_warnings
    )
