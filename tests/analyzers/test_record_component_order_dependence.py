# pyright: reportPrivateUsage=false
"""Focused tests for positional record component analyzer findings."""

from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.variables import VariablesAnalyzer
from sattlint.reporting.variables_report import IssueKind


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def _eq(code: list[object]):
    return Equation(name="E1", position=(0.0, 0.0), size=(1.0, 1.0), code=code)


def test_getrecordcomponent_reports_record_component_order_dependence():
    dt = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="First", datatype=Simple_DataType.INTEGER),
            Variable(name="Second", datatype=Simple_DataType.REAL),
        ],
    )

    rec = Variable(name="Rec", datatype="RecType")
    result = Variable(name="ResultRec", datatype="AnyType")
    status = Variable(name="Status", datatype=Simple_DataType.INTEGER)

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[rec, result, status],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_FUNCTION_CALL,
                            "GetRecordComponent",
                            [_varref("Rec"), 2, _varref("ResultRec"), _varref("Status")],
                        )
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    analyzer = VariablesAnalyzer(
        BasePicture(
            header=_hdr("Root"),
            datatype_defs=[dt],
            moduletype_defs=[],
            localvariables=[],
            submodules=[module],
            modulecode=None,
            moduledef=None,
        )
    )
    analyzer.run()

    issues = [
        issue
        for issue in analyzer.issues
        if issue.kind is IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE and issue.variable is rec
    ]

    assert len(issues) == 1
    assert issues[0].datatype_name == "RecType"
    assert (
        issues[0].role
        == "GetRecordComponent reads record components by numeric position; reordering datatype fields can change behavior (index 2 => field 'Second')"
    )
    assert analyzer._get_usage(rec).read is True
    assert analyzer._get_usage(result).written is True
    assert analyzer._get_usage(status).written is True


def test_putrecordcomponent_reports_record_component_order_dependence():
    dt = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="First", datatype=Simple_DataType.INTEGER),
            Variable(name="Second", datatype=Simple_DataType.REAL),
        ],
    )

    rec = Variable(name="Rec", datatype="RecType")
    source = Variable(name="InputRec", datatype="AnyType")
    status = Variable(name="Status", datatype=Simple_DataType.INTEGER)

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[rec, source, status],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_FUNCTION_CALL,
                            "PutRecordComponent",
                            [_varref("Rec"), 1, _varref("InputRec"), _varref("Status")],
                        )
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    analyzer = VariablesAnalyzer(
        BasePicture(
            header=_hdr("Root"),
            datatype_defs=[dt],
            moduletype_defs=[],
            localvariables=[],
            submodules=[module],
            modulecode=None,
            moduledef=None,
        )
    )
    analyzer.run()

    issues = [
        issue
        for issue in analyzer.issues
        if issue.kind is IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE and issue.variable is rec
    ]

    assert len(issues) == 1
    assert issues[0].datatype_name == "RecType"
    assert (
        issues[0].role
        == "PutRecordComponent writes record components by numeric position; reordering datatype fields can change behavior (index 1 => field 'First')"
    )
    assert analyzer._get_usage(rec).written is True
    assert analyzer._get_usage(source).read is True
    assert analyzer._get_usage(status).written is True


def test_repeated_positional_access_reports_each_datatype_once():
    dt = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="First", datatype=Simple_DataType.INTEGER),
            Variable(name="Second", datatype=Simple_DataType.REAL),
        ],
    )

    rec_a = Variable(name="RecA", datatype="RecType")
    rec_b = Variable(name="RecB", datatype="RecType")
    result = Variable(name="ResultRec", datatype="AnyType")
    status = Variable(name="Status", datatype=Simple_DataType.INTEGER)

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[rec_a, rec_b, result, status],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_FUNCTION_CALL,
                            "GetRecordComponent",
                            [_varref("RecA"), 1, _varref("ResultRec"), _varref("Status")],
                        ),
                        (
                            const.KEY_FUNCTION_CALL,
                            "GetRecordComponent",
                            [_varref("RecB"), 2, _varref("ResultRec"), _varref("Status")],
                        ),
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    analyzer = VariablesAnalyzer(
        BasePicture(
            header=_hdr("Root"),
            datatype_defs=[dt],
            moduletype_defs=[],
            localvariables=[],
            submodules=[module],
            modulecode=None,
            moduledef=None,
        )
    )
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE]

    assert len(issues) == 1
    assert issues[0].datatype_name == "RecType"


def test_positional_record_component_wrapper_ignores_anytype_for_datatype_list():
    picklist_type = ModuleTypeDef(
        name="PicklistType",
        moduleparameters=[
            Variable(name="RecipeRecord", datatype="AnyType"),
            Variable(name="MaxNoOfIndex", datatype=Simple_DataType.INTEGER),
        ],
        localvariables=[
            Variable(name="GetComponentIndex", datatype=Simple_DataType.INTEGER),
            Variable(name="StateElement", datatype="AnyType"),
            Variable(name="RecipeArray", datatype="AnyType"),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_FUNCTION_CALL,
                            "GetRecordComponent",
                            [
                                _varref("RecipeRecord"),
                                _varref("GetComponentIndex"),
                                _varref("StateElement"),
                                _varref("Status"),
                            ],
                        ),
                        (
                            const.KEY_FUNCTION_CALL,
                            "PutArray",
                            [_varref("RecipeArray"), 1, _varref("StateElement"), _varref("Status")],
                        ),
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    analyzer = VariablesAnalyzer(
        BasePicture(
            header=_hdr("Root"),
            datatype_defs=[],
            moduletype_defs=[picklist_type],
            localvariables=[],
            submodules=[],
            modulecode=None,
            moduledef=None,
        )
    )
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE]

    assert issues == []
