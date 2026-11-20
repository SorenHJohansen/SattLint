from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FrameModule,
    GraphicsBinding,
    GraphObject,
    ModuleCode,
    ModuleDef,
    ModuleTypeDef,
    ModuleTypeInstance,
    ScalarDatatype,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattline_parser.models.expressions import (
    FuncCall,
    FuncCallStmt,
)

from sattlint.analyzers.variables import (
    IssueKind,
    VariablesAnalyzer,
)
from sattlint.graphics.picture_display_paths import PictureDisplayOccurrence
from sattlint.graphics.validation import PictureDisplayPathRow, PictureDisplayRecord
from sattlint.reporting.variables_report import DATATYPE_FIELD_ANALYSIS_KINDS
from tests.helpers.analyzers_variables_part4_support import COLUMN_TYPE_STEP, FIRST_RECORD_STEP
from tests.helpers.graphics_attachments_support import graphics_attachments
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)
from tests.helpers.variable_test_support import (
    varref as _varref,
)


def test_library_target_picture_display_variable_rows_count_typedef_moduleparameter_usage_at_root():
    root_typedef = ModuleTypeDef(
        name="Column",
        moduleparameters=[Variable(name="ColumnType", datatype=ScalarDatatype.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        modulecode=None,
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )
    bp_attachments = graphics_attachments(
        picture_display_occurrences=[
            PictureDisplayOccurrence(
                program_name="BasePicture",
                declaring_module_path=("BasePicture", "Column"),
                record=PictureDisplayRecord(
                    record_index=1,
                    record_start_line=1,
                    record_end_line=5,
                    path_rows=(
                        PictureDisplayPathRow(
                            record_index=1,
                            index_token=COLUMN_TYPE_STEP,
                            index_value=None,
                            kind="variable",
                            raw_text="ColumnType",
                            span=SourceSpan(start=0, end=0, line=1, column=1),
                        ),
                    ),
                ),
            )
        ]
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True, graphics_attachments=bp_attachments)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.role == "moduleparameter"
        and issue.variable is not None
        and issue.variable.name == "ColumnType"
        and issue.module_path == ["BasePicture", "TypeDef:Column"]
        for issue in analyzer.issues
    )


def test_library_target_picture_display_index_variable_counts_typedef_moduleparameter_usage_at_root():
    root_typedef = ModuleTypeDef(
        name="Column",
        moduleparameters=[Variable(name="ColumnType", datatype=ScalarDatatype.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        modulecode=None,
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )
    bp_attachments = graphics_attachments(
        picture_display_occurrences=[
            PictureDisplayOccurrence(
                program_name="BasePicture",
                declaring_module_path=("BasePicture", "Column"),
                record=PictureDisplayRecord(
                    record_index=1,
                    record_start_line=1,
                    record_end_line=5,
                    path_rows=(
                        PictureDisplayPathRow(
                            record_index=1,
                            index_token=COLUMN_TYPE_STEP,
                            index_value=None,
                            kind="literal",
                            raw_text="+InletMPC+++Inlet_Z2",
                            span=SourceSpan(start=0, end=0, line=1, column=1),
                        ),
                    ),
                ),
            )
        ]
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True, graphics_attachments=bp_attachments)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.role == "moduleparameter"
        and issue.variable is not None
        and issue.variable.name == "ColumnType"
        and issue.module_path == ["BasePicture", "TypeDef:Column"]
        for issue in analyzer.issues
    )


def test_library_target_picture_display_record_binding_counts_typedef_moduleparameter_usage_at_root():
    root_typedef = ModuleTypeDef(
        name="Column",
        moduleparameters=[Variable(name="ColumnType", datatype=ScalarDatatype.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        modulecode=None,
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )
    bp_attachments = graphics_attachments(
        bindings=[
            GraphicsBinding(
                kind="var",
                raw_text="ColumnType",
                value=_varref("ColumnType"),
                span=SourceSpan(start=0, end=0, line=1, column=1),
            )
        ],
        picture_display_occurrences=[
            PictureDisplayOccurrence(
                program_name="BasePicture",
                declaring_module_path=("BasePicture", "Column"),
                record=PictureDisplayRecord(
                    record_index=1,
                    record_start_line=1,
                    record_end_line=5,
                    path_rows=(
                        PictureDisplayPathRow(
                            record_index=1,
                            index_token=FIRST_RECORD_STEP,
                            index_value=1,
                            kind="literal",
                            raw_text="+InletMPC+++Inlet_Z2",
                            span=SourceSpan(start=0, end=0, line=2, column=1),
                        ),
                    ),
                ),
            )
        ],
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True, graphics_attachments=bp_attachments)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.role == "moduleparameter"
        and issue.variable is not None
        and issue.variable.name == "ColumnType"
        and issue.module_path == ["BasePicture", "TypeDef:Column"]
        for issue in analyzer.issues
    )


def test_library_target_picture_display_runtime_instance_path_counts_typedef_moduleparameter_usage():
    root_typedef = ModuleTypeDef(
        name="Column",
        moduleparameters=[Variable(name="ColumnType", datatype=ScalarDatatype.INTEGER)],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("Panel"),
                moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            )
        ],
        moduledef=None,
        modulecode=None,
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[
            FrameModule(
                header=_hdr("L1"),
                submodules=[
                    ModuleTypeInstance(
                        header=_hdr("Column"),
                        moduletype_name="Column",
                        parametermappings=[],
                    )
                ],
                moduledef=None,
                modulecode=None,
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )
    bp_attachments = graphics_attachments(
        bindings=[
            GraphicsBinding(
                kind="var",
                raw_text="ColumnType",
                value=_varref("ColumnType"),
                span=SourceSpan(start=0, end=0, line=1, column=1),
            )
        ],
        picture_display_occurrences=[
            PictureDisplayOccurrence(
                program_name="BasePicture",
                declaring_module_path=("BasePicture", "L1", "Column", "Panel"),
                record=PictureDisplayRecord(
                    record_index=1,
                    record_start_line=1,
                    record_end_line=5,
                    path_rows=(
                        PictureDisplayPathRow(
                            record_index=1,
                            index_token=FIRST_RECORD_STEP,
                            index_value=1,
                            kind="literal",
                            raw_text="+InletMPC+++Inlet_Z2",
                            span=SourceSpan(start=0, end=0, line=2, column=1),
                        ),
                    ),
                ),
            )
        ],
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True, graphics_attachments=bp_attachments)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.role == "moduleparameter"
        and issue.variable is not None
        and issue.variable.name == "ColumnType"
        for issue in analyzer.issues
    )


def test_library_target_picture_display_variable_rows_count_typedef_moduleparameter_usage_in_submodule():
    root_typedef = ModuleTypeDef(
        name="Column",
        moduleparameters=[Variable(name="ColumnType", datatype=ScalarDatatype.INTEGER)],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("Panel"),
                moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            )
        ],
        moduledef=None,
        modulecode=None,
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )
    bp_attachments = graphics_attachments(
        picture_display_occurrences=[
            PictureDisplayOccurrence(
                program_name="BasePicture",
                declaring_module_path=("BasePicture", "Column", "Panel"),
                record=PictureDisplayRecord(
                    record_index=1,
                    record_start_line=1,
                    record_end_line=5,
                    path_rows=(
                        PictureDisplayPathRow(
                            record_index=1,
                            index_token=COLUMN_TYPE_STEP,
                            index_value=None,
                            kind="variable",
                            raw_text="ColumnType",
                            span=SourceSpan(start=0, end=0, line=1, column=1),
                        ),
                    ),
                ),
            )
        ]
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True, graphics_attachments=bp_attachments)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.role == "moduleparameter"
        and issue.variable is not None
        and issue.variable.name == "ColumnType"
        and issue.module_path == ["BasePicture", "TypeDef:Column"]
        for issue in analyzer.issues
    )


def test_library_target_direct_typedef_code_counts_field_usage_for_datatype_reporting():
    record_type = DataType(
        name="StepTextType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="CleanCycle", datatype=ScalarDatatype.STRING),
            Variable(name="WaitCleanCycle", datatype=ScalarDatatype.STRING),
            Variable(name="Unused", datatype=ScalarDatatype.STRING),
        ],
        origin_file="DiluteLib.s",
        origin_lib="DiluteLib",
    )
    root_typedef = ModuleTypeDef(
        name="DiluteType",
        moduleparameters=[],
        localvariables=[
            Variable(name="StepText", datatype="StepTextType"),
            Variable(name="Sink", datatype=ScalarDatatype.STRING),
            Variable(name="Status", datatype=ScalarDatatype.INTEGER),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        FuncCallStmt(
                            call=FuncCall(
                                name="CopyString",
                                args=(
                                    _varref("StepText.CleanCycle"),
                                    _varref("Sink"),
                                    _varref("Status"),
                                ),
                            )
                        )
                    ],
                )
            ],
            sequences=[],
        ),
        origin_file="DiluteLib.s",
        origin_lib="DiluteLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="DiluteLib.s",
        origin_lib="DiluteLib",
    )

    analyzer = VariablesAnalyzer(
        bp,
        analyzed_target_is_library=True,
        selected_issue_kinds=frozenset(DATATYPE_FIELD_ANALYSIS_KINDS),
    )
    analyzer.run()

    unused_fields = {
        issue.field_path
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "StepTextType"
    }

    assert unused_fields == {"WaitCleanCycle", "Unused"}
