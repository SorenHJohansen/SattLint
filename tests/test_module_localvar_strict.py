import pytest

from sattlint import constants as const
from sattlint.analyzers.variables import analyze_module_localvar_fields
from sattlint.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ParameterMapping,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    SingleModule,
    Variable,
)


def _varref(s: str) -> dict:
    return {const.KEY_VAR_NAME: s}


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def test_module_localvar_strict_path_and_case_insensitive():
    # Define datatype for field resolution
    dt_dv = DataType(
        name="ApplDvType",
        description=None,
        datecode=None,
        var_list=[Variable(name="AckText", datatype=Simple_DataType.STRING)],
    )

    # Typedef from a library
    mt_appltank = ModuleTypeDef(
        name="ApplTank",
        origin_lib="KaHAApplLib",
        localvariables=[Variable(name="Dv", datatype="ApplDvType")],
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
                            const.KEY_ASSIGN,
                            _varref("Dv.AckText"),
                            "Hello",
                        )
                    ],
                )
            ]
        ),
    )

    inst = ModuleTypeInstance(header=_hdr("KaHA251A"), moduletype_name="ApplTank")
    startmaster = SingleModule(
        header=_hdr("StartMaster"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[inst],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[dt_dv],
        moduletype_defs=[mt_appltank],
        localvariables=[],
        submodules=[startmaster],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_module_localvar_fields(bp, "StartMaster.KaHA251A", "Dv", debug=False)
    assert "Module type: KaHAApplLib:ApplTank" in report
    assert "FIELD-LEVEL ACCESSES" in report
    assert "acktext" in report.lower()

    # Case-insensitive path + variable
    report2 = analyze_module_localvar_fields(bp, "startmaster.kaha251a", "dv", debug=False)
    assert "FIELD-LEVEL ACCESSES" in report2


def test_module_localvar_strict_path_fails_loudly():
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    with pytest.raises(ValueError):
        analyze_module_localvar_fields(bp, "StartMaster.KaHA251A", "Dv", debug=False)


def test_module_localvar_alias_prefix_uses_source_fields_only():
    # Parent module owns Dv; child module parameter 'control' is mapped to Dv.empty.
    # The child writes control.Cmd, which should be reported as Dv.empty.cmd.
    # It must NOT show up as Dv.control.*

    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="control", datatype=Simple_DataType.STRING)],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="E1",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("control.Cmd"),
                            "1",
                        )
                    ],
                )
            ]
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("control"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("Dv.empty"),
                source_literal=None,
            )
        ],
    )

    parent = SingleModule(
        header=_hdr("StartMaster"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Dv", datatype=Simple_DataType.STRING)],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_module_localvar_fields(bp, "StartMaster", "Dv", debug=False)
    assert "Dv.empty.cmd" in report
    assert "Dv.control" not in report
