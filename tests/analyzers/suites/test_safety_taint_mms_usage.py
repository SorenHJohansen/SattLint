from sattline_parser.models.ast_model import (
    Assignment,
    BasePicture,
    DataType,
    Equation,
    IntLiteral,
    ModuleCode,
    ScalarDatatype,
    SingleModule,
    Variable,
)

from sattlint.analyzers.variable_usage_reporting import (
    debug_variable_usage,
    report_datatype_usage,
)
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)
from tests.helpers.variable_test_support import (
    varref as _varref,
)


def test_variable_usage_datatype_report_returns_not_found_message():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    report = report_datatype_usage(bp, "MissingValue")

    assert report == "Variable 'MissingValue' not found."


def test_variable_usage_reports_include_field_and_whole_variable_accesses():
    record_type = DataType(
        name="UsageRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Source", datatype=ScalarDatatype.INTEGER),
            Variable(name="Target", datatype=ScalarDatatype.INTEGER),
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("Unit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[
                    Variable(name="Dv", datatype="UsageRecord"),
                    Variable(name="Mirror", datatype="UsageRecord"),
                    Variable(name="Sink", datatype=ScalarDatatype.INTEGER),
                ],
                submodules=[],
                modulecode=ModuleCode(
                    equationblocks=[
                        Equation(
                            name="Usage",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[
                                Assignment(target=_varref("Sink"), value=_varref("Dv.Source")),
                                Assignment(target=_varref("Dv.Target"), value=IntLiteral(1)),
                                Assignment(target=_varref("Mirror"), value=_varref("Dv")),
                                Assignment(target=_varref("Dv"), value=_varref("Mirror")),
                            ],
                        )
                    ]
                ),
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
    )

    datatype_report = report_datatype_usage(bp, "Dv")
    debug_report = debug_variable_usage(bp, "Dv")

    assert "Field usage analysis for variable 'Dv':" in datatype_report
    assert "Fields accessed: 2" in datatype_report
    assert "source: read (r:1, w:0)" in datatype_report.lower()
    assert "target: write (r:0, w:1)" in datatype_report.lower()
    assert "Usage report for variable name 'Dv' (1 declaration(s)):" in debug_report
    assert "Field reads:" in debug_report
    assert "dv.source" in debug_report.lower()
    assert "Field writes:" in debug_report
    assert "dv.target" in debug_report.lower()
    assert "Whole variable:" in debug_report
    assert "R:1 W:1 | Root -> Unit" in debug_report
