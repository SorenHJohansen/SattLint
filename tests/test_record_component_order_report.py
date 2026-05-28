from sattline_parser.models.ast_model import Variable
from sattlint.reporting.variables_report import IssueKind, VariableIssue, VariablesReport


def test_record_component_order_summary_renders_guidance() -> None:
    rec = Variable(name="RecipeRecord", datatype="AnyType")
    issues = [
        VariableIssue(
            kind=IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE,
            module_path=["BasePicture", "TypeDef:PicklistType"],
            variable=rec,
            role="GetRecordComponent reads record components by numeric position; reordering datatype fields can change behavior",
        )
    ]

    summary = VariablesReport(basepicture_name="BasePicture", issues=issues).summary()

    assert "Positional record component access" in summary
    assert (
        "BasePicture.TypeDef:PicklistType :: RecipeRecord (AnyType) | "
        "GetRecordComponent reads record components by numeric position; "
        "reordering datatype fields can change behavior"
    ) in summary
