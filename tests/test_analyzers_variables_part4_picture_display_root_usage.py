# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnusedImport=false
# ruff: noqa: F403, F405

from sattline_parser.models.ast_model import FrameModule, GraphicsBinding
from sattlint.graphics_validation import PictureDisplayPathRow, PictureDisplayRecord
from sattlint.picture_display_paths import PictureDisplayOccurrence

from ._analyzers_variables_part4_support import COLUMN_TYPE_STEP, FIRST_RECORD_STEP
from ._analyzers_variables_test_support import *


def test_library_target_picture_display_variable_rows_count_typedef_moduleparameter_usage_at_root():
    root_typedef = ModuleTypeDef(
        name="Soejle",
        moduleparameters=[Variable(name="ColumnType", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="BasePicture",
            declaring_module_path=("BasePicture", "Soejle"),
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
                        span=SourceSpan(line=1, column=1),
                    ),
                ),
            ),
        )
    ]

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.role == "moduleparameter"
        and issue.variable is not None
        and issue.variable.name == "ColumnType"
        and issue.module_path == ["BasePicture", "TypeDef:Soejle"]
        for issue in analyzer.issues
    )


def test_library_target_picture_display_index_variable_counts_typedef_moduleparameter_usage_at_root():
    root_typedef = ModuleTypeDef(
        name="Soejle",
        moduleparameters=[Variable(name="ColumnType", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="BasePicture",
            declaring_module_path=("BasePicture", "Soejle"),
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
                        span=SourceSpan(line=1, column=1),
                    ),
                ),
            ),
        )
    ]

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.role == "moduleparameter"
        and issue.variable is not None
        and issue.variable.name == "ColumnType"
        and issue.module_path == ["BasePicture", "TypeDef:Soejle"]
        for issue in analyzer.issues
    )


def test_library_target_picture_display_record_binding_counts_typedef_moduleparameter_usage_at_root():
    root_typedef = ModuleTypeDef(
        name="Soejle",
        moduleparameters=[Variable(name="ColumnType", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp.graphics_bindings = [
        GraphicsBinding(
            kind="var",
            raw_text="ColumnType",
            value=_varref("ColumnType"),
            span=SourceSpan(line=1, column=1),
        )
    ]
    bp.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="BasePicture",
            declaring_module_path=("BasePicture", "Soejle"),
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
                        span=SourceSpan(line=2, column=1),
                    ),
                ),
            ),
        )
    ]

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.role == "moduleparameter"
        and issue.variable is not None
        and issue.variable.name == "ColumnType"
        and issue.module_path == ["BasePicture", "TypeDef:Soejle"]
        for issue in analyzer.issues
    )


def test_library_target_picture_display_runtime_instance_path_counts_typedef_moduleparameter_usage():
    root_typedef = ModuleTypeDef(
        name="Soejle",
        moduleparameters=[Variable(name="ColumnType", datatype=Simple_DataType.INTEGER)],
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
        parametermappings=[],
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
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
                        header=_hdr("KaHASoejle"),
                        moduletype_name="Soejle",
                        parametermappings=[],
                    )
                ],
                moduledef=None,
                modulecode=None,
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp.graphics_bindings = [
        GraphicsBinding(
            kind="var",
            raw_text="ColumnType",
            value=_varref("ColumnType"),
            span=SourceSpan(line=1, column=1),
        )
    ]
    bp.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="BasePicture",
            declaring_module_path=("BasePicture", "L1", "KaHASoejle", "Panel"),
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
                        span=SourceSpan(line=2, column=1),
                    ),
                ),
            ),
        )
    ]

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
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
        name="Soejle",
        moduleparameters=[Variable(name="ColumnType", datatype=Simple_DataType.INTEGER)],
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
        parametermappings=[],
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="BasePicture",
            declaring_module_path=("BasePicture", "Soejle", "Panel"),
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
                        span=SourceSpan(line=1, column=1),
                    ),
                ),
            ),
        )
    ]

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.role == "moduleparameter"
        and issue.variable is not None
        and issue.variable.name == "ColumnType"
        and issue.module_path == ["BasePicture", "TypeDef:Soejle"]
        for issue in analyzer.issues
    )


def test_library_target_direct_typedef_code_counts_field_usage_for_datatype_reporting():
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
    root_typedef = ModuleTypeDef(
        name="DiluteType",
        moduleparameters=[],
        localvariables=[
            Variable(name="StepText", datatype="StepTextType"),
            Variable(name="Sink", datatype=Simple_DataType.STRING),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyString",
                            [_varref("StepText.CleanCycle"), _varref("Sink"), _varref("Status")],
                        )
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    unused_fields = {
        issue.field_path
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "StepTextType"
    }

    assert unused_fields == {"WaitCleanCycle", "Unused"}
