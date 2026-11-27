# These tests deliberately exercise private analyzer seams.
# pyright: reportPrivateUsage=false

"""Focused regression tests for InitVariable record semantics."""

from sattline_parser.models.ast_model import (
    BasePicture,
    CodeItem,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    ScalarDatatype,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import FuncCall, FuncCallStmt, VarRef

from sattlint.analyzers.variables import VariablesAnalyzer
from sattlint.reporting.variables_report import UnusedIssue


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def _eq(code: list[CodeItem]) -> Equation:
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
            Variable(name="A", datatype=ScalarDatatype.INTEGER),
            Variable(name="B", datatype=ScalarDatatype.REAL),
        ],
    )

    init_record = Variable(name="InitRec", datatype="InitVariableType")
    record = Variable(name="Rec", datatype="InitVariableType")
    status = Variable(name="Status", datatype=ScalarDatatype.INTEGER)

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[init_record, record, status],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                _eq(
                    [
                        FuncCallStmt(
                            call=FuncCall(
                                name="InitVariable",
                                args=(_varref("Rec"), _varref("InitRec"), _varref("Status")),
                            )
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
    unused = {issue.variable.name for issue in issues if isinstance(issue, UnusedIssue)}

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
