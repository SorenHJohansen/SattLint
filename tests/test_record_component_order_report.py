from sattline_parser.models.ast_model import Variable
from sattlint.reporting.variables_report import IssueKind, VariableIssue, VariablesReport


def test_record_component_order_summary_renders_guidance() -> None:
    rec = Variable(name="RecipeRecord", datatype="AnyType")
    other = Variable(name="BufferRecord", datatype="OtherType")
    issues = [
        VariableIssue(
            kind=IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE,
            module_path=["BasePicture", "TypeDef:PicklistType"],
            variable=rec,
            datatype_name="RecipeType",
            role="GetRecordComponent reads record components by numeric position; reordering datatype fields can change behavior",
        ),
        VariableIssue(
            kind=IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE,
            module_path=["BasePicture", "Wrapper", "Leaf"],
            variable=other,
            datatype_name="RecipeType",
            role="PutRecordComponent writes record components by numeric position; reordering datatype fields can change behavior",
        ),
        VariableIssue(
            kind=IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE,
            module_path=["BasePicture", "OtherWrapper"],
            variable=other,
            datatype_name="OtherType",
            role="GetRecordComponent reads record components by numeric position; reordering datatype fields can change behavior",
        ),
    ]

    summary = VariablesReport(basepicture_name="BasePicture", issues=issues).summary()

    assert "Sorting-sensitive datatypes" in summary
    assert "      * OtherType" in summary
    assert "      * RecipeType" in summary
    assert summary.count("RecipeType") == 1
    assert "BasePicture.TypeDef:PicklistType" not in summary
    assert "RecipeRecord" not in summary
