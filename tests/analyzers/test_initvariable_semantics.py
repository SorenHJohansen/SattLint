# pyright: reportPrivateUsage=false
"""Focused regression tests for InitVariable record semantics."""

from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def _eq(code: list[object]) -> Equation:
    return Equation(
        name="E1",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=code,
    )


def _build_initvariable_picture() -> tuple[BasePicture, Variable, Variable]:
    datatype = DataType(
        name="InitVariableType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.REAL),
        ],
    )

    init_record = Variable(name="InitRec", datatype="InitVariableType")
    record = Variable(name="Rec", datatype="InitVariableType")
    status = Variable(name="Status", datatype=Simple_DataType.INTEGER)

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[init_record, record, status],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_FUNCTION_CALL,
                            "InitVariable",
                            [_varref("Rec"), _varref("InitRec"), _varref("Status")],
                        )
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    picture = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[datatype],
        moduletype_defs=[],
        localvariables=[],
        submodules=[module],
        modulecode=None,
        moduledef=None,
    )
    return picture, init_record, record


def test_initvariable_source_is_not_reported_unused() -> None:
    picture, _, _ = _build_initvariable_picture()

    issues = VariablesAnalyzer(picture).run()
    unused = {issue.variable.name for issue in issues if issue.kind is IssueKind.UNUSED and issue.variable is not None}

    assert "InitRec" not in unused


def test_initvariable_reads_source_and_writes_all_fields() -> None:
    picture, init_record, record = _build_initvariable_picture()

    analyzer = VariablesAnalyzer(picture)
    analyzer.run()

    record_usage = analyzer._get_usage(record)
    write_keys = {key.casefold() for key in (record_usage.field_writes or {})}
    assert {"a", "b"}.issubset(write_keys)

    init_record_usage = analyzer._get_usage(init_record)
    read_keys = {key.casefold() for key in (init_record_usage.field_reads or {})}
    assert init_record_usage.read
    assert {"a", "b"}.issubset(read_keys)
