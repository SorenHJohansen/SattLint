"""Tests for builtin record read/write semantics."""

import pytest

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
from sattlint.analyzers.variables import VariablesAnalyzer
from sattlint.reporting.variables_report import IssueKind


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(s: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: s}


def _eq(code: list[object]) -> Equation:
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

    src_usage = analyzer._get_usage(src)
    dst_usage = analyzer._get_usage(dst)
    status_usage = analyzer._get_usage(status)

    assert src_usage.field_reads is not None
    assert dst_usage.field_writes is not None

    read_keys = {k.casefold() for k in src_usage.field_reads}
    write_keys = {k.casefold() for k in dst_usage.field_writes}

    assert {"a", "b"}.issubset(read_keys)
    assert {"a", "b"}.issubset(write_keys)
    assert status_usage.written, "Expected Status to be written by CopyVariable"


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

    src_u = analyzer._get_usage(src)
    dst_u = analyzer._get_usage(dst)

    read_keys = {k.casefold() for k in (src_u.field_reads or {})}
    write_keys = {k.casefold() for k in (dst_u.field_writes or {})}

    assert "inner.x" in read_keys
    assert "inner.y" in read_keys
    assert "inner.x" in write_keys
    assert "inner.y" in write_keys


def test_partial_record_usage_reports_unused_leaf_fields():
    dt = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.REAL),
        ],
    )

    rec = Variable(name="Rec", datatype="RecType")

    m1 = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[rec],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_ASSIGN,
                            _varref("Rec.A"),
                            1,
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

    unused_fields = {
        issue.field_path.casefold()
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
        and issue.datatype_name == "RecType"
        and issue.field_path is not None
    }

    assert "b" in unused_fields
    assert "a" not in unused_fields


def test_whole_record_access_does_not_report_unused_leaf_fields():
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

    m1 = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[src, dst],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_ASSIGN,
                            _varref("Dst"),
                            _varref("Src"),
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

    assert not any(
        issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "RecType" for issue in analyzer.issues
    )


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


def test_copyvariable_allows_opaque_builtin_record_type():
    src = Variable(name="Random", datatype="RandomGenerator")
    dst = Variable(name="Random2", datatype="RandomGenerator")

    m1 = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[src, dst],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [_varref("Random"), _varref("Random2")],
                        )
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
        localvariables=[],
        submodules=[m1],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp, fail_loudly=False)
    analyzer.run()
    assert analyzer._get_usage(src).read
    assert analyzer._get_usage(dst).written


def test_array_builtins_bind_record_element_contracts_and_mark_whole_record_access() -> None:
    dt = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.REAL),
        ],
    )

    array_var = Variable(name="Arr", datatype="ArrayObject")
    seed = Variable(name="Seed", datatype="RecType")
    out = Variable(name="Out", datatype="RecType")
    status = Variable(name="Status", datatype=Simple_DataType.INTEGER)

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[array_var, seed, out, status],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_FUNCTION_CALL,
                            "CreateArray",
                            [_varref("Arr"), 1, 2, _varref("Seed"), _varref("Status")],
                        ),
                        (const.KEY_FUNCTION_CALL, "GetArray", [_varref("Arr"), 1, _varref("Out"), _varref("Status")]),
                        (const.KEY_FUNCTION_CALL, "PutArray", [_varref("Arr"), 2, _varref("Seed"), _varref("Status")]),
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
        submodules=[module],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    array_usage = analyzer._get_usage(array_var)
    seed_usage = analyzer._get_usage(seed)
    out_usage = analyzer._get_usage(out)

    assert array_usage.read is True
    assert array_usage.written is True
    assert {key.casefold() for key in seed_usage.field_reads or {}} >= {"a", "b"}
    assert {key.casefold() for key in out_usage.field_writes or {}} >= {"a", "b"}


def test_getarray_reports_dynamic_array_contract_mismatch_for_incompatible_target() -> None:
    array_var = Variable(name="Arr", datatype="ArrayObject")
    seed = Variable(name="Seed", datatype=Simple_DataType.INTEGER)
    out = Variable(name="Out", datatype=Simple_DataType.BOOLEAN)
    status = Variable(name="Status", datatype=Simple_DataType.INTEGER)

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[array_var, seed, out, status],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_FUNCTION_CALL,
                            "CreateArray",
                            [_varref("Arr"), 1, 2, _varref("Seed"), _varref("Status")],
                        ),
                        (const.KEY_FUNCTION_CALL, "GetArray", [_varref("Arr"), 1, _varref("Out"), _varref("Status")]),
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
        localvariables=[],
        submodules=[module],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.CONTRACT_MISMATCH]

    assert len(issues) == 1
    assert issues[0].role is not None
    assert "dynamic array element mismatch" in issues[0].role
