from types import SimpleNamespace
from typing import Any, cast

from sattline_parser.models.ast_model import Simple_DataType, SourceSpan, Variable
from sattlint.core.diagnostics import project_variable_issues
from sattlint.reporting.variables_report import IssueKind, VariableIssue


def test_record_component_order_diagnostic_message_includes_guidance() -> None:
    issue = VariableIssue(
        kind=IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE,
        module_path=["BasePicture", "TypeDef:PicklistType"],
        variable=Variable(name="RecipeRecord", datatype=Simple_DataType.INTEGER),
        role="GetRecordComponent reads record components by numeric position; reordering datatype fields can change behavior",
    )
    definition = SimpleNamespace(
        source_file="/tmp/Main.s",
        source_library="MainLib",
        declaration_span=SourceSpan(12, 4),
        canonical_path="BasePicture.TypeDef:PicklistType.RecipeRecord",
        field_path=None,
    )

    result = project_variable_issues(
        (issue,),
        {("basepicture", "typedef:picklisttype", "reciperecord"): cast(Any, definition)},
    )

    diagnostic = result.diagnostics_by_file["/tmp/main.s"][0]
    assert diagnostic.message.startswith(
        "Positional record component access: GetRecordComponent reads record components by numeric position"
    )
    assert "Why it matters:" in diagnostic.message
    assert "Suggested fix:" in diagnostic.message
    assert "reordering datatype fields can silently read from or write to a different field" in diagnostic.message
