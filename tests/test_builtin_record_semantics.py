"""Tests for builtin record read/write semantics."""

import pytest

from sattlint import constants as const
from sattlint.analyzers.variables import VariablesAnalyzer
from sattlint.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    Simple_DataType,
    SingleModule,
    Variable,
)


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(s: str) -> dict:
    return {const.KEY_VAR_NAME: s}


def _eq(code: list) -> Equation:
    return Equation(
        name="E1",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=code,
    )


def test_copyvariable_marks_all_leaf_fields_read_and_written():
    dt = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.REAL),
        ],
    )

    src = Variable(name="Src", datatype="RecType")
    dst = Variable(name="Dst", datatype="RecType")
    status = Variable(name="Status", datatype=Simple_DataType.INTEGER)

    m1 = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[src, dst, status],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [_varref("Src"), _varref("Dst"), _varref("Status")],
                        )
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[dt],
        moduletype_defs=[],
        localvariables=[],
        submodules=[m1],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert src.field_reads is not None
    assert dst.field_writes is not None

    read_keys = {k.casefold() for k in src.field_reads.keys()}
    write_keys = {k.casefold() for k in dst.field_writes.keys()}

    assert {"a", "b"}.issubset(read_keys)
    assert {"a", "b"}.issubset(write_keys)
    assert status.written, "Expected Status to be written by CopyVariable"


def test_copyvarnosort_expands_nested_prefix_fields():
    dt_inner = DataType(
        name="InnerType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="X", datatype=Simple_DataType.INTEGER),
            Variable(name="Y", datatype=Simple_DataType.INTEGER),
        ],
    )
    dt_outer = DataType(
        name="OuterType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Inner", datatype="InnerType"),
            Variable(name="Other", datatype=Simple_DataType.INTEGER),
        ],
    )

    src = Variable(name="OuterSrc", datatype="OuterType")
    dst = Variable(name="OuterDst", datatype="OuterType")
    status = Variable(name="Status", datatype=Simple_DataType.INTEGER)

    m1 = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[src, dst, status],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVarNoSort",
                            [
                                _varref("OuterSrc.Inner"),
                                _varref("OuterDst.Inner"),
                                _varref("Status"),
                            ],
                        )
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[dt_outer, dt_inner],
        moduletype_defs=[],
        localvariables=[],
        submodules=[m1],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    read_keys = {k.casefold() for k in (src.field_reads or {}).keys()}
    write_keys = {k.casefold() for k in (dst.field_writes or {}).keys()}

    assert "inner.x" in read_keys
    assert "inner.y" in read_keys
    assert "inner.x" in write_keys
    assert "inner.y" in write_keys


def test_initvariable_writes_all_fields_and_reads_nothing():
    dt = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.REAL),
        ],
    )

    initrec = Variable(name="InitRec", datatype="RecType")
    rec = Variable(name="Rec", datatype="RecType")
    status = Variable(name="Status", datatype=Simple_DataType.INTEGER)

    m1 = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[initrec, rec, status],
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

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[dt],
        moduletype_defs=[],
        localvariables=[],
        submodules=[m1],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    # Rec is fully written
    write_keys = {k.casefold() for k in (rec.field_writes or {}).keys()}
    assert {"a", "b"}.issubset(write_keys)

    # InitRec is NOT read (per user semantics)
    assert not (initrec.read or initrec.field_reads), "InitRec must not be counted as read"


def test_copyvariable_fails_loudly_on_unknown_field_prefix():
    dt = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[Variable(name="A", datatype=Simple_DataType.INTEGER)],
    )

    src = Variable(name="Src", datatype="RecType")
    dst = Variable(name="Dst", datatype="RecType")
    status = Variable(name="Status", datatype=Simple_DataType.INTEGER)

    m1 = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[src, dst, status],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [_varref("Src.Nope"), _varref("Dst"), _varref("Status")],
                        )
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[dt],
        moduletype_defs=[],
        localvariables=[],
        submodules=[m1],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    with pytest.raises(ValueError):
        analyzer.run()
