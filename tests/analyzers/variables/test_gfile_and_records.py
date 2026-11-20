# pyright: reportPrivateUsage=false
from pathlib import Path

import pytest
from sattline_parser.models.ast_model import (
    Assignment,
    BasePicture,
    DataType,
    Equation,
    GraphicsBinding,
    GraphObject,
    ModuleCode,
    ModuleDef,
    ScalarDatatype,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattline_parser.models.expressions import FuncCall

from sattlint.analyzers.variables import (
    IssueKind,
    VariablesAnalyzer,
)
from sattlint.graphics.validation import GraphicsCompositeRecord
from sattlint.parser_api import parse_source_file
from sattlint.reporting.variables_report import (
    ALL_VARIABLE_ANALYSIS_KINDS,
    DATATYPE_FIELD_ANALYSIS_KINDS,
    NeverReadIssue,
    ReadOnlyNonConstIssue,
    UnusedDatatypeFieldIssue,
    UnusedIssue,
)
from tests.helpers.graphics_attachments_support import graphics_attachments
from tests.helpers.project_loading import load_target_project
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)
from tests.helpers.variable_test_support import (
    varref as _varref,
)


def test_sample_fixture_contains_common_variable_quality_issues():
    fixture = (
        Path(__file__).resolve().parents[2] / "fixtures" / "corpus" / "semantic" / "workspace" / "CommonQualityIssues.s"
    )

    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp, selected_issue_kinds=frozenset(ALL_VARIABLE_ANALYSIS_KINDS)).run()

    unused = {issue.variable.name for issue in issues if isinstance(issue, UnusedIssue)}
    read_only_non_const = {issue.variable.name for issue in issues if isinstance(issue, ReadOnlyNonConstIssue)}
    never_read = {issue.variable.name for issue in issues if isinstance(issue, NeverReadIssue)}
    unused_fields = {
        (issue.datatype_name, issue.field_path) for issue in issues if isinstance(issue, UnusedDatatypeFieldIssue)
    }

    assert "UnusedValue" in unused
    assert "ReadOnlyValue" in read_only_non_const
    assert "NeverReadValue" in never_read
    assert ("QualityRecord", "UnusedField") in unused_fields


def test_sample_fixture_reports_only_globally_unused_datatype_fields():
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "sample_sattline_files" / "OutletProdSiblingMiswire.s"

    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp, selected_issue_kinds=frozenset(DATATYPE_FIELD_ANALYSIS_KINDS)).run()

    unused_fields = {
        (issue.datatype_name, issue.field_path) for issue in issues if isinstance(issue, UnusedDatatypeFieldIssue)
    }

    # The sibling miswire is a per-instance asymmetry: one field is only read,
    # the other only written. Globally both are used, so neither is reported.
    assert not any(issue.kind in {IssueKind.FIELD_READ_ONLY, IssueKind.FIELD_NEVER_READ} for issue in issues)
    assert ("OutletProdPair", "OutletProd_Def.Std") not in unused_fields
    assert ("OutletProdPair", "OutletProd_X_Def.Std") not in unused_fields
    # Aux is never read or written anywhere, so it is genuinely unused.
    assert ("OutletProdState", "Aux") in unused_fields


def _build_whole_record_basepicture(*, read_payload: bool) -> BasePicture:
    record_type = DataType(
        name="PayloadType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Used", datatype=ScalarDatatype.INTEGER),
            Variable(name="Other", datatype=ScalarDatatype.INTEGER),
        ],
    )

    payload = Variable(name="Payload", datatype="PayloadType")
    peer = Variable(name="Peer", datatype="PayloadType")

    whole_record_assignment = (
        Assignment(target=_varref("Peer"), value=_varref("Payload"))
        if read_payload
        else Assignment(target=_varref("Payload"), value=_varref("Peer"))
    )

    return BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[payload, peer],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="WholeRecordAccess",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[whole_record_assignment],
                )
            ],
            sequences=[],
        ),
        moduledef=None,
    )


@pytest.mark.parametrize("read_payload", [True, False])
def test_whole_record_access_marks_every_field_used_globally(read_payload: bool):
    bp = _build_whole_record_basepicture(read_payload=read_payload)

    issues = VariablesAnalyzer(bp, selected_issue_kinds=frozenset(DATATYPE_FIELD_ANALYSIS_KINDS)).run()

    assert not [issue for issue in issues if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD]
    assert not any(issue.kind in {IssueKind.FIELD_READ_ONLY, IssueKind.FIELD_NEVER_READ} for issue in issues)


def test_gfile_var_and_expr_reads_count_as_used_for_unused_analysis():
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "sample_sattline_files" / "TestGFileParse.s"
    bp, graph = load_target_project(fixture)
    analyzer = VariablesAnalyzer(bp, graphics_attachments=graph.graphics_attachments_for(bp))
    issues = analyzer.run()

    usage_by_name = {variable.name: analyzer._get_usage(variable) for variable in bp.localvariables}
    unused = {issue.variable.name for issue in issues if isinstance(issue, UnusedIssue)}

    assert unused == set()
    assert all(usage.read for usage in usage_by_name.values())


def test_nested_gfile_bindings_count_as_used_end_to_end(tmp_path: Path):
    source = """"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Shared: integer := 0;
SUBMODULES
    Panel Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 2
    LOCALVARIABLES
        NestedOnly, Shared: integer := 0;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    GraphObjects :
        CompositeObject
    ENDDEF (*Panel*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    graphics = """" Syntax version 2.23, date: 2026-05-26-00:00:00.000 N "

 1
 Var  True  10 NestedOnly
 Var  True   6 Shared
           0
"""

    fixture = tmp_path / "NestedGraphics.s"
    fixture.write_text(source, encoding="utf-8")
    fixture.with_suffix(".g").write_text(graphics, encoding="utf-8")

    bp, graph = load_target_project(fixture)
    analyzer = VariablesAnalyzer(bp, graphics_attachments=graph.graphics_attachments_for(bp))
    issues = analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is not None
        and issue.variable.name in {"NestedOnly", "Shared"}
        and issue.module_path == ["BasePicture", "Panel"]
        for issue in issues
    )
    assert any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is not None
        and issue.variable.name == "Shared"
        and issue.module_path == ["BasePicture"]
        for issue in issues
    )


def test_nested_composite_gfile_bindings_use_declaring_module_scope():
    module = SingleModule(
        header=_hdr("Panel"),
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        moduleparameters=[],
        localvariables=[
            Variable(name="NestedOnly", datatype=ScalarDatatype.INTEGER),
            Variable(name="Shared", datatype=ScalarDatatype.INTEGER),
        ],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="RootOnly", datatype=ScalarDatatype.INTEGER),
            Variable(name="Shared", datatype=ScalarDatatype.INTEGER),
        ],
        submodules=[module],
        modulecode=None,
        moduledef=ModuleDef(),
    )
    bp_attachments = graphics_attachments(
        bindings=[
            GraphicsBinding(
                kind="var",
                raw_text="NestedOnly",
                value=_varref("NestedOnly"),
                span=SourceSpan(start=0, end=0, line=9, column=1),
            ),
            GraphicsBinding(
                kind="var",
                raw_text="Shared",
                value=_varref("Shared"),
                span=SourceSpan(start=0, end=0, line=10, column=1),
            ),
        ],
        composite_records=[
            GraphicsCompositeRecord(record_index=1, record_start_line=8, record_end_line=12, family_code="")
        ],
    )

    analyzer = VariablesAnalyzer(bp, graphics_attachments=bp_attachments)
    issues = analyzer.run()

    assert not any(isinstance(issue, UnusedIssue) and issue.variable.name == "NestedOnly" for issue in issues)
    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is not None
        and issue.variable.name == "Shared"
        and issue.module_path == ["BasePicture", "Panel"]
        for issue in issues
    )
    assert any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is not None
        and issue.variable.name == "Shared"
        and issue.module_path == ["BasePicture"]
        for issue in issues
    )


def test_unparsed_gfile_expr_still_counts_named_variables_as_reads():
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="Alpha", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="Beta", datatype=ScalarDatatype.BOOLEAN),
        ],
        submodules=[],
        modulecode=None,
        moduledef=ModuleDef(),
    )
    bp_attachments = graphics_attachments(
        bindings=[
            GraphicsBinding(
                kind="expr",
                raw_text="Alpha ??? Beta",
                value="Alpha ??? Beta",
                span=SourceSpan(start=0, end=0, line=1, column=1),
            )
        ]
    )

    analyzer = VariablesAnalyzer(bp, graphics_attachments=bp_attachments)
    issues = analyzer.run()

    assert not any(isinstance(issue, UnusedIssue) and issue.variable.name in {"Alpha", "Beta"} for issue in issues)


def test_search_rec_component_found_record_output_is_not_flagged_never_read():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="CR", datatype=ScalarDatatype.INTEGER),
            Variable(name="Index", datatype=ScalarDatatype.INTEGER),
            Variable(name="SearchUnit", datatype=ScalarDatatype.INTEGER),
            Variable(name="FoundUnit", datatype=ScalarDatatype.INTEGER),
            Variable(name="srci", datatype=ScalarDatatype.INTEGER),
            Variable(name="SearchSucceeded", datatype=ScalarDatatype.BOOLEAN),
            Variable(name="Mirror", datatype=ScalarDatatype.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Search",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        Assignment(
                            target=_varref("SearchSucceeded"),
                            value=FuncCall(
                                name="SearchRecComponent",
                                args=(
                                    _varref("CR"),
                                    _varref("Index"),
                                    10,
                                    _varref("SearchUnit"),
                                    _varref("SearchUnit"),
                                    _varref("FoundUnit"),
                                    _varref("srci"),
                                ),
                            ),
                        ),
                        Assignment(target=_varref("Mirror"), value=_varref("Index")),
                    ],
                )
            ],
            sequences=[],
        ),
        moduledef=None,
    )

    issues = VariablesAnalyzer(bp).run()

    never_read = {issue.variable.name for issue in issues if isinstance(issue, NeverReadIssue)}

    assert "FoundUnit" not in never_read
