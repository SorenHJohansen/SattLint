"""Ad-hoc validation for the field validation fix."""

from sattline_parser.models.ast_model import BasePicture, DataType, ModuleHeader, ScalarDatatype, Variable

from sattlint.analyzers.variables import VariablesAnalyzer


def _bp_with_datatypes() -> BasePicture:
    appl_dv_type = DataType(
        name="ApplDvType",
        description="Application Dv Type",
        datecode=None,
        var_list=[
            Variable(name="SomeField", datatype=ScalarDatatype.REAL),
            Variable(name="OtherField", datatype=ScalarDatatype.INTEGER),
        ],
    )

    mes_batch_type = DataType(
        name="MESBatchCtrlType",
        description="MES Batch Control Type",
        datecode=None,
        var_list=[
            Variable(name="APPL", datatype="ApplType"),
            Variable(name="BatchID", datatype=ScalarDatatype.INTEGER),
        ],
    )

    appl_type = DataType(
        name="ApplType",
        description="Application Type",
        datecode=None,
        var_list=[
            Variable(name="Abort", datatype=ScalarDatatype.BOOLEAN),
        ],
    )

    return BasePicture(
        header=ModuleHeader(name="BasePicture", invoke_coord=(0, 0, 0, 0, 0)),
        datatype_defs=[appl_dv_type, mes_batch_type, appl_type],
    )


def test_type_graph_does_not_invent_fields():
    bp = _bp_with_datatypes()
    analyzer = VariablesAnalyzer(bp, debug=False, fail_loudly=False)
    tg = analyzer.type_graph

    assert tg.has_record("ApplDvType")
    assert tg.field("ApplDvType", "APPL") is None
    assert tg.field("MESBatchCtrlType", "APPL") is not None
