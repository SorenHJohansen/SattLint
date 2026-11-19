# pyright: reportPrivateUsage=false
"""Variable report sections must describe what they count."""

from __future__ import annotations

from sattline_parser.models.ast_model import Variable

from sattlint.reporting import _variables_report_rendering as rendering
from sattlint.reporting.target_report import normalize_report_target_name
from sattlint.reporting.variables_report import (
    _SECTION_RENDERERS,
    IssueKind,
    VariableIssue,
    VariablesReport,
)


def _variable(name: str, datatype: str = "Integer") -> Variable:
    return Variable(name=name, datatype=datatype)


def _issue(
    kind: IssueKind,
    module_path: list[str],
    *,
    variable: Variable | None = None,
    source: Variable | None = None,
    datatype_name: str | None = None,
    role: str | None = None,
) -> VariableIssue:
    return VariableIssue(
        kind=kind,
        module_path=module_path,
        variable=variable,
        source_variable=source,
        datatype_name=datatype_name,
        role=role,
    )


def test_every_issue_kind_has_a_section_renderer() -> None:
    assert set(_SECTION_RENDERERS) == set(IssueKind)


def test_status_and_issue_count_describe_the_same_findings() -> None:
    report = VariablesReport(
        basepicture_name="BasePicture",
        issues=[_issue(IssueKind.UNUSED, ["BasePicture"], variable=_variable("Hidden"))],
        visible_kinds=frozenset({IssueKind.MAGIC_NUMBER}),
    )

    summary = report.summary()

    assert "Status: ok" in summary
    assert "Issues: 0" in summary
    assert "Status: issues" not in summary


def test_min_max_table_keeps_columns_aligned_for_missing_variables() -> None:
    issues = [
        _issue(
            IssueKind.MIN_MAX_MAPPING_MISMATCH,
            ["BasePicture", "Wrapper", "LongerLeaf"],
            variable=_variable("LevelMax"),
            source=_variable("LevelMin"),
            role="moduleparameter",
        ),
        _issue(
            IssueKind.MIN_MAX_MAPPING_MISMATCH,
            ["BasePicture", "Leaf"],
            variable=_variable("TargetB"),
            role="moduleparameter",
        ),
    ]

    lines: list[str] = []
    rendering.render_table_issue_rows(lines, issues, True, include_target_type=False)

    header, separator, first_row, second_row = lines
    assert len(separator) == len(header.strip()) + len("        ")
    assert first_row.index("LevelMin") == header.index("Source Var")
    assert second_row.index("?") == header.index("Source Var")
    assert first_row.index("LevelMax") == header.index("Target Var")
    assert second_row.index("TargetB") == header.index("Target Var")


def test_empty_module_path_uses_one_label() -> None:
    assert rendering.format_location([]) == "?"


def test_table_locations_use_one_path_spelling() -> None:
    issues = [
        _issue(
            IssueKind.MIN_MAX_MAPPING_MISMATCH,
            ["BasePicture", "TypeDef:PicklistType"],
            variable=_variable("Target"),
            source=_variable("Source"),
            role="moduleparameter",
        )
    ]

    moduletype_lines: list[str] = []
    rendering.render_table_issue_rows(moduletype_lines, issues, True, include_target_type=False)
    singlemodule_lines: list[str] = []
    rendering.render_table_issue_rows(singlemodule_lines, issues, False, include_target_type=False)

    assert "BasePicture.TypeDef:PicklistType" in moduletype_lines[2]
    assert "BasePicture.PicklistType" in singlemodule_lines[2]
    assert "BasePicture.TypeDef:PicklistType" not in singlemodule_lines[2]


def test_duplicated_datatype_rows_sort_case_insensitively() -> None:
    issues = [
        _issue(IssueKind.DATATYPE_DUPLICATION, ["BasePicture", "A"], variable=_variable("One", "BetaType")),
        _issue(IssueKind.DATATYPE_DUPLICATION, ["BasePicture", "B"], variable=_variable("Two", "alphaType")),
    ]

    lines: list[str] = []
    rendering.render_datatype_duplication_rows(lines, issues, True)

    assert "alphaType" in lines[0]
    assert "BetaType" in lines[2]


def test_sorting_sensitive_datatypes_collapse_case_variants() -> None:
    issues = [
        _issue(IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE, ["BasePicture", "A"], datatype_name="RecipeType"),
        _issue(IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE, ["BasePicture", "B"], datatype_name="recipetype"),
    ]

    report = VariablesReport(basepicture_name="BasePicture", issues=issues)

    summary = report.summary()

    assert summary.count("      * ") == 1


def test_target_name_normalization_renames_both_label_shapes() -> None:
    class _NameOnlyReport:
        def __init__(self) -> None:
            self.name = "BasePicture"

    report = VariablesReport(basepicture_name="BasePicture", issues=[])
    named_report = _NameOnlyReport()

    assert normalize_report_target_name(report, "Demo") is report
    assert report.basepicture_name == "Demo"
    assert normalize_report_target_name(named_report, "Demo") is named_report
    assert named_report.name == "Demo"
    assert normalize_report_target_name("plain", "Demo") == "plain"
    assert normalize_report_target_name(report, "") is report
    assert report.basepicture_name == "Demo"
