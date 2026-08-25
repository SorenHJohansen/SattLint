# pyright: reportPrivateUsage=false
from sattline_parser.models.ast_model import (
    Assignment,
    BasePicture,
    Equation,
    ModuleCode,
    ModuleHeader,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import VarRef

from sattlint.analyzers.variables import VariablesAnalyzer


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def _eq(code: list[object]) -> Equation:
    return Equation(
        name="E1",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=code,  # pyright: ignore[reportArgumentType]
    )


def test_builtin_progstationdata_fields_are_addressable() -> None:
    progstation_data = Variable(name="ProgStationData", datatype="ProgStationData")
    format_text = Variable(name="FormatText", datatype=Simple_DataType.STRING)
    warning_colour = Variable(name="WarningColour", datatype=Simple_DataType.INTEGER)

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[progstation_data, format_text, warning_colour],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        Assignment(
                            target=_varref("FormatText"),
                            value=_varref("ProgStationData.FormatString"),
                        ),
                        Assignment(
                            target=_varref("WarningColour"),
                            value=_varref("ProgStationData.WarningColour"),
                        ),
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[progstation_data, format_text, warning_colour],
        submodules=[module],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not analyzer.issues, f"Unexpected issues: {[(i.kind, i.field_path) for i in analyzer.issues]}"


def test_builtin_progstationdata_nested_field_addressable() -> None:
    pass
    progstation_data = Variable(name="ProgStationData", datatype="ProgStationData")
    result = Variable(name="Result", datatype=Simple_DataType.INTEGER)

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[progstation_data, result],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        Assignment(
                            target=_varref("Result"),
                            value=_varref("ProgStationData.Timestamp"),
                        ),
                    ]
                )
            ]
        ),
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert "variables.undefined_variable" not in {
        issue.kind for issue in analyzer.issues
    }


def test_builtin_record_fields_from_parameter_mapping() -> None:
    from sattline_parser.models.ast_model import ModuleTypeInstance, ModuleTypeDef

    record_var = Variable(name="MyRecord", datatype="InnerType")
    target_var = Variable(name="Target", datatype=Simple_DataType.INTEGER)

    typedef = ModuleTypeDef(
        name="InnerType",
        moduleparameters=[],
        localvariables=[
            Variable(name="X", datatype=Simple_DataType.INTEGER),
            Variable(name="Y", datatype=Simple_DataType.STRING),
        ],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[record_var, target_var],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Reader"),
                moduletype_name="InnerType",
                parametermappings=[],
            )
        ],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        Assignment(
                            target=_varref("Target"),
                            value=_varref("MyRecord.X"),
                        ),
                    ]
                )
            ]
        ),
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert "variables.undefined_variable" not in {
        issue.kind for issue in analyzer.issues
    }, f"Unexpected issues: {[(i.kind, i.field_path) for i in analyzer.issues]}"
