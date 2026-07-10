# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnusedImport=false
# ruff: noqa: F403, F405
from pathlib import Path
from types import SimpleNamespace

from sattline_parser.models.ast_model import GraphicsBinding

from ._analyzers_variables_test_support import *


def test_sample_fixture_contains_common_variable_quality_issues():
    fixture = Path(__file__).parent / "fixtures" / "corpus" / "semantic" / "workspace" / "CommonQualityIssues.s"

    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp).run()

    unused = {issue.variable.name for issue in issues if issue.kind is IssueKind.UNUSED and issue.variable is not None}
    read_only_non_const = {
        issue.variable.name
        for issue in issues
        if issue.kind is IssueKind.READ_ONLY_NON_CONST and issue.variable is not None
    }
    never_read = {
        issue.variable.name for issue in issues if issue.kind is IssueKind.NEVER_READ and issue.variable is not None
    }
    unused_fields = {
        (issue.datatype_name, issue.field_path) for issue in issues if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
    }

    assert "UnusedValue" in unused
    assert "ReadOnlyValue" in read_only_non_const
    assert "NeverReadValue" in never_read
    assert ("QualityRecord", "UnusedField") in unused_fields


def test_sample_fixture_catches_outletprod_sibling_field_miswire():
    fixture = Path(__file__).parent / "fixtures" / "sample_sattline_files" / "OutletProdSiblingMiswire.s"

    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp).run()

    field_read_only = {
        (issue.variable.name, issue.field_path)
        for issue in issues
        if issue.kind is IssueKind.FIELD_READ_ONLY and issue.variable is not None
    }
    field_never_read = {
        (issue.variable.name, issue.field_path)
        for issue in issues
        if issue.kind is IssueKind.FIELD_NEVER_READ and issue.variable is not None
    }
    unused_fields = {
        (issue.datatype_name, issue.field_path) for issue in issues if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
    }

    assert ("OutletConfig", "OutletProd_Def.Std") in field_read_only
    assert ("OutletConfig", "OutletProd_X_Def.Std") in field_never_read
    assert ("OutletProdPair", "OutletProd_Def.Std") not in unused_fields
    assert ("OutletProdPair", "OutletProd_X_Def.Std") not in unused_fields


def _build_record_field_asymmetry_basepicture(*, include_whole_read: bool) -> BasePicture:
    record_type = DataType(
        name="PayloadType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Used", datatype=Simple_DataType.INTEGER),
            Variable(name="Miswired", datatype=Simple_DataType.INTEGER),
        ],
    )

    payload = Variable(name="Payload", datatype="PayloadType")
    whole_peer = Variable(name="WholePeer", datatype="PayloadType")
    field_source = Variable(name="FieldSource", datatype=Simple_DataType.INTEGER)
    sink = Variable(name="Sink", datatype=Simple_DataType.INTEGER)

    whole_record_assignment = (
        (const.KEY_ASSIGN, _varref("WholePeer"), _varref("Payload"))
        if include_whole_read
        else (const.KEY_ASSIGN, _varref("Payload"), _varref("WholePeer"))
    )

    return BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[payload, whole_peer, field_source, sink],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="WholeRecordAccess",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[whole_record_assignment],
                ),
                Equation(
                    name="ReadUsedField",
                    position=(1.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Sink"), _varref("Payload.Used"))],
                ),
                Equation(
                    name="WriteMiswiredField",
                    position=(2.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Payload.Miswired"), _varref("FieldSource"))],
                ),
            ],
            sequences=[],
        ),
        moduledef=None,
    )


def test_whole_record_write_does_not_hide_field_never_read_issue():
    bp = _build_record_field_asymmetry_basepicture(include_whole_read=False)

    issues = VariablesAnalyzer(bp).run()

    field_read_only = {
        (issue.variable.name, issue.field_path)
        for issue in issues
        if issue.kind is IssueKind.FIELD_READ_ONLY and issue.variable is not None
    }
    field_never_read = {
        (issue.variable.name, issue.field_path)
        for issue in issues
        if issue.kind is IssueKind.FIELD_NEVER_READ and issue.variable is not None
    }

    assert ("Payload", "Used") not in field_read_only
    assert ("Payload", "Miswired") in field_never_read


def test_whole_record_read_does_not_hide_field_read_only_issue():
    bp = _build_record_field_asymmetry_basepicture(include_whole_read=True)

    issues = VariablesAnalyzer(bp).run()

    field_read_only = {
        (issue.variable.name, issue.field_path)
        for issue in issues
        if issue.kind is IssueKind.FIELD_READ_ONLY and issue.variable is not None
    }
    field_never_read = {
        (issue.variable.name, issue.field_path)
        for issue in issues
        if issue.kind is IssueKind.FIELD_NEVER_READ and issue.variable is not None
    }

    assert ("Payload", "Used") in field_read_only
    assert ("Payload", "Miswired") not in field_never_read


def test_gfile_var_and_expr_reads_count_as_used_for_unused_analysis():
    from sattlint.engine import (  # noqa: PLC0415
        CodeMode,
        SattLineProjectLoader,
        SattLineProjectLoaderConfig,
        merge_project_basepicture,
    )

    fixture = Path(__file__).parent / "fixtures" / "sample_sattline_files" / "TestGFileParse.s"
    loader = SattLineProjectLoader(
        SattLineProjectLoaderConfig(
            program_dir=fixture.parent,
            other_lib_dirs=[],
            abb_lib_dir=fixture.parent,
            mode=CodeMode.DRAFT,
            scan_root_only=True,
            debug=False,
            use_file_ast_cache=False,
        )
    )

    graph = loader.resolve(fixture.stem, strict=False)
    bp = merge_project_basepicture(graph.ast_by_name[fixture.stem], graph)
    analyzer = VariablesAnalyzer(bp)
    issues = analyzer.run()

    usage_by_name = {variable.name: analyzer._get_usage(variable) for variable in bp.localvariables}
    unused = {issue.variable.name for issue in issues if issue.kind is IssueKind.UNUSED and issue.variable is not None}

    assert unused == set()
    assert all(usage.read for usage in usage_by_name.values())


def test_nested_gfile_bindings_count_as_used_end_to_end(tmp_path: Path):
    from sattlint.engine import (  # noqa: PLC0415
        CodeMode,
        SattLineProjectLoader,
        SattLineProjectLoaderConfig,
        merge_project_basepicture,
    )

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

    loader = SattLineProjectLoader(
        SattLineProjectLoaderConfig(
            program_dir=tmp_path,
            other_lib_dirs=[],
            abb_lib_dir=tmp_path,
            mode=CodeMode.DRAFT,
            scan_root_only=True,
            debug=False,
            use_file_ast_cache=False,
        )
    )

    graph = loader.resolve(fixture.stem, strict=False)
    bp = merge_project_basepicture(graph.ast_by_name[fixture.stem], graph)
    analyzer = VariablesAnalyzer(bp)
    issues = analyzer.run()
    issue_tuples = {
        (
            issue.kind,
            tuple(issue.module_path),
            issue.variable.name if issue.variable is not None else None,
            issue.role,
            issue.field_path,
        )
        for issue in issues
    }

    assert (IssueKind.UI_ONLY, ("BasePicture", "Panel"), "NestedOnly", "localvariable", None) in issue_tuples
    assert (IssueKind.UI_ONLY, ("BasePicture", "Panel"), "Shared", "localvariable", None) in issue_tuples
    assert not any(
        issue.kind is IssueKind.UI_ONLY
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
            Variable(name="NestedOnly", datatype=Simple_DataType.INTEGER),
            Variable(name="Shared", datatype=Simple_DataType.INTEGER),
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
            Variable(name="RootOnly", datatype=Simple_DataType.INTEGER),
            Variable(name="Shared", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[module],
        modulecode=None,
        moduledef=ModuleDef(),
    )
    bp.graphics_bindings = [
        GraphicsBinding(
            kind="var",
            raw_text="NestedOnly",
            value=_varref("NestedOnly"),
            span=SourceSpan(line=9, column=1),
        ),
        GraphicsBinding(
            kind="var",
            raw_text="Shared",
            value=_varref("Shared"),
            span=SourceSpan(line=10, column=1),
        ),
    ]
    bp.graphics_composite_records = [SimpleNamespace(record_index=1, record_start_line=8, record_end_line=12)]

    analyzer = VariablesAnalyzer(bp)
    issues = analyzer.run()
    issue_tuples = {
        (
            issue.kind,
            tuple(issue.module_path),
            issue.variable.name if issue.variable is not None else None,
            issue.role,
            issue.field_path,
        )
        for issue in issues
    }

    assert not any(
        issue.kind is IssueKind.UNUSED and issue.variable is not None and issue.variable.name == "NestedOnly"
        for issue in issues
    )
    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is not None
        and issue.variable.name == "Shared"
        and issue.module_path == ["BasePicture", "Panel"]
        for issue in issues
    )
    assert not any(
        issue.kind is IssueKind.UI_ONLY
        and issue.variable is not None
        and issue.variable.name == "Shared"
        and issue.module_path == ["BasePicture"]
        for issue in issues
    )
    assert (IssueKind.UI_ONLY, ("BasePicture", "Panel"), "NestedOnly", "localvariable", None) in issue_tuples
    assert (IssueKind.UI_ONLY, ("BasePicture", "Panel"), "Shared", "localvariable", None) in issue_tuples


def test_unparsed_gfile_expr_still_counts_named_variables_as_reads():
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="Alpha", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Beta", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=None,
        moduledef=ModuleDef(),
    )
    bp.graphics_bindings = [
        GraphicsBinding(
            kind="expr",
            raw_text="Alpha ??? Beta",
            value="Alpha ??? Beta",
            span=SourceSpan(line=1, column=1),
        )
    ]

    analyzer = VariablesAnalyzer(bp)
    issues = analyzer.run()
    issue_tuples = {
        (
            issue.kind,
            tuple(issue.module_path),
            issue.variable.name if issue.variable is not None else None,
            issue.role,
            issue.field_path,
        )
        for issue in issues
    }

    assert not any(
        issue.kind is IssueKind.UNUSED and issue.variable is not None and issue.variable.name in {"Alpha", "Beta"}
        for issue in issues
    )
    assert (IssueKind.UI_ONLY, ("BasePicture",), "Alpha", "localvariable", None) in issue_tuples
    assert (IssueKind.UI_ONLY, ("BasePicture",), "Beta", "localvariable", None) in issue_tuples


def test_search_rec_component_found_record_output_is_not_flagged_never_read():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="CR", datatype=Simple_DataType.INTEGER),
            Variable(name="Index", datatype=Simple_DataType.INTEGER),
            Variable(name="SearchUnit", datatype=Simple_DataType.INTEGER),
            Variable(name="FoundUnit", datatype=Simple_DataType.INTEGER),
            Variable(name="srci", datatype=Simple_DataType.INTEGER),
            Variable(name="SearchSucceeded", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Mirror", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Search",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("SearchSucceeded"),
                            (
                                const.KEY_FUNCTION_CALL,
                                "SearchRecComponent",
                                [
                                    _varref("CR"),
                                    _varref("Index"),
                                    10,
                                    _varref("SearchUnit"),
                                    _varref("SearchUnit"),
                                    _varref("FoundUnit"),
                                    _varref("srci"),
                                ],
                            ),
                        ),
                        (const.KEY_ASSIGN, _varref("Mirror"), _varref("Index")),
                    ],
                )
            ],
            sequences=[],
        ),
        moduledef=None,
    )

    issues = VariablesAnalyzer(bp).run()

    never_read = {
        issue.variable.name for issue in issues if issue.kind is IssueKind.NEVER_READ and issue.variable is not None
    }

    assert "FoundUnit" not in never_read
