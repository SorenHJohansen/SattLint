# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnusedImport=false


from sattline_parser.models.ast_model import GraphicsBinding

from sattlint.graphics_validation import PictureDisplayPathRow, PictureDisplayRecord
from sattlint.picture_display_paths import PictureDisplayOccurrence

from ._analyzers_variables_test_support import *


def test_unused_datatype_fields_are_aggregated_across_variables():
    record_type = DataType(
        name="SharedRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.INTEGER),
            Variable(name="C", datatype=Simple_DataType.INTEGER),
        ],
        origin_file="Root.x",
        origin_lib="ProjectLib",
    )

    first = Variable(name="First", datatype="SharedRecord")
    second = Variable(name="Second", datatype="SharedRecord")

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[first, second],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("sinkA"), _varref("First.A")),
                        (const.KEY_ASSIGN, _varref("sinkB"), _varref("Second.B")),
                    ],
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[
            Variable(name="sinkA", datatype=Simple_DataType.INTEGER),
            Variable(name="sinkB", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[module],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    unused_fields = {
        issue.field_path
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "SharedRecord"
    }

    assert unused_fields == {"C"}


def test_unused_datatype_fields_count_nested_record_field_accesses():
    op_type = DataType(
        name="KaHAOPType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="LOP19", datatype=Simple_DataType.BOOLEAN),
            Variable(name="LOP20", datatype=Simple_DataType.BOOLEAN),
            Variable(name="LOP21", datatype=Simple_DataType.BOOLEAN),
        ],
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )
    config_type = DataType(
        name="ConfigType",
        description=None,
        datecode=None,
        var_list=[Variable(name="ActiveOP", datatype="KaHAOPType")],
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )
    child_typedef = ModuleTypeDef(
        name="PanelType",
        moduleparameters=[Variable(name="ThisOPStation", datatype=Simple_DataType.BOOLEAN)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadThisOp",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[_varref("ThisOPStation")],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )
    root_typedef = ModuleTypeDef(
        name="RootType",
        moduleparameters=[],
        localvariables=[Variable(name="Config", datatype="ConfigType")],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Panel"),
                moduletype_name="PanelType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("ThisOPStation"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("Config.ActiveOP.LOP19"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=ModuleCode(equations=[], sequences=[]),
        parametermappings=[],
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[op_type, config_type],
        moduletype_defs=[root_typedef, child_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    unused_fields = {
        issue.field_path
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "KaHAOPType"
    }

    assert unused_fields == {"LOP20", "LOP21"}


def test_library_target_dependency_mapping_counts_root_record_field_usage_without_dependency_reads():
    record_type = DataType(
        name="ColumnShDataType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="TC601_AlarmDelay", datatype=Simple_DataType.INTEGER),
            Variable(name="TC601_GlitChDelay", datatype=Simple_DataType.INTEGER),
            Variable(name="Unused", datatype=Simple_DataType.INTEGER),
        ],
        origin_file="KaHASoejleLib.s",
        origin_lib="KaHASoejleLib",
    )
    dependency_typedef = ModuleTypeDef(
        name="MES_BatchControl",
        moduleparameters=[Variable(name="AlarmDelay", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(equations=[], sequences=[]),
        parametermappings=[],
        origin_file="NNEMESIFLib.s",
        origin_lib="NNEMESIFLib",
    )
    root_typedef = ModuleTypeDef(
        name="ColumnType",
        moduleparameters=[],
        localvariables=[
            Variable(name="ColumnSh", datatype="ColumnShDataType"),
            Variable(name="Sink", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("MES_BatchControl"),
                moduletype_name="MES_BatchControl",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("AlarmDelay"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("ColumnSh.TC601_AlarmDelay"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadField",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Sink"),
                            _varref("ColumnSh.TC601_GlitChDelay"),
                        )
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
        origin_file="KaHASoejleLib.s",
        origin_lib="KaHASoejleLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[root_typedef, dependency_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHASoejleLib.s",
        origin_lib="KaHASoejleLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True, include_dependency_moduletype_usage=True)
    analyzer.run()

    unused_fields = {
        issue.field_path
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "ColumnShDataType"
    }

    assert unused_fields == {"Unused"}


def test_picture_display_variable_rows_count_as_field_usage_for_datatype_reporting():
    record_type = DataType(
        name="StepTextType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="CleanCycle", datatype=Simple_DataType.STRING),
            Variable(name="WaitCleanCycle", datatype=Simple_DataType.STRING),
            Variable(name="Unused", datatype=Simple_DataType.STRING),
        ],
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )
    module = SingleModule(
        header=_hdr("DisplayModule"),
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        moduleparameters=[],
        localvariables=[Variable(name="StepTexts", datatype="StepTextType")],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[],
        submodules=[module],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )
    bp.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="BasePicture",
            declaring_module_path=("BasePicture", "DisplayModule"),
            record=PictureDisplayRecord(
                record_index=1,
                record_start_line=1,
                record_end_line=5,
                path_rows=(
                    PictureDisplayPathRow(
                        record_index=1,
                        index_token="<token>",
                        index_value=0,
                        kind="variable",
                        raw_text="StepTexts.CleanCycle",
                        span=SourceSpan(line=9, column=1),
                    ),
                    PictureDisplayPathRow(
                        record_index=1,
                        index_token="<token>",
                        index_value=1,
                        kind="variable",
                        raw_text="StepTexts.WaitCleanCycle",
                        span=SourceSpan(line=10, column=1),
                    ),
                ),
            ),
        )
    ]

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    unused_fields = {
        issue.field_path
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "StepTextType"
    }

    assert unused_fields == {"Unused"}


def test_invalid_picture_display_path_rows_do_not_count_as_usage():
    path_var = Variable(name="PathAIT", datatype=Simple_DataType.LINESTRING)
    module = SingleModule(
        header=_hdr("DisplayModule"),
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        moduleparameters=[],
        localvariables=[path_var],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[module],
        modulecode=None,
        moduledef=None,
    )
    bp.graphics_bindings = [
        GraphicsBinding(
            kind="var",
            raw_text="PathAIT",
            value=_varref("PathAIT"),
            span=SourceSpan(line=2, column=5),
        )
    ]
    bp.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="BasePicture",
            declaring_module_path=("BasePicture", "DisplayModule"),
            record=PictureDisplayRecord(
                record_index=1,
                record_start_line=1,
                record_end_line=5,
                path_row_lines=(2,),
                path_rows=(),
            ),
        )
    ]

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is path_var
        and issue.module_path == ["BasePicture", "DisplayModule"]
        for issue in analyzer.issues
    )
